"""TTS service — edge-tts voice synthesis for AI explanations.

Uses Microsoft Edge's free TTS endpoint via the `edge_tts` Python library.
Per architecture.md §12.1 (decision D9): backend edge-tts → mp3 bytes →
disk cache keyed by sha256(text+voice).

Architecture:
  - zh-CN-XiaoxiaoNeural (default female), zh-CN-YunxiNeural (male alt)
  - LaTeX preprocessing: strip math markup for Chinese-readable spoken text
  - Disk cache: backend/media/tts/{sha256}.mp3, no DB table (decision D14)
  - No-network → raise TTSError (caller maps to 501/502)
"""

import hashlib
import logging
import re
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# ── Constants ─────────────────────────────────────────────────────────────

DEFAULT_VOICE = "zh-CN-XiaoxiaoNeural"
VOICE_WHITELIST = frozenset({
    "zh-CN-XiaoxiaoNeural",   # 晓晓 (female, default)
    "zh-CN-YunxiNeural",      # 云希 (male)
    "zh-CN-YunyangNeural",    # 云扬 (male, news-style)
    "zh-CN-XiaoyiNeural",     # 晓伊 (female)
})
DEFAULT_RATE = "+0%"
DEFAULT_VOLUME = "+0%"
DEFAULT_PITCH = "+0Hz"
CACHE_DIR = Path("backend/media/tts")


# ── Exceptions ────────────────────────────────────────────────────────────


class TTSError(Exception):
    """TTS synthesis failed — network, voice, or upstream issue."""


class TTSNetworkError(TTSError):
    """edge-tts unreachable (no network / proxy down)."""


class TTSVoiceError(TTSError):
    """Voice not in whitelist or unavailable."""


# ── Text preprocessing ────────────────────────────────────────────────────

# LaTeX math patterns to strip or replace for TTS readability
_LATEX_DISPLAY = re.compile(r"\$\$[^$]+\$\$")
_LATEX_INLINE = re.compile(r"\$([^$]+?)\$")
_LATEX_CMD_WITH_BRACES = re.compile(r"\\[a-zA-Z]+\{([^}]*)\}")   # \cmd{text} → text
_LATEX_CMD_BARE = re.compile(r"\\[a-zA-Z]+")                         # bare \cmd → ""
_MATH_ENV = re.compile(r"\\begin\{.*?\}.*?\\end\{.*?\}", re.DOTALL)
_MULTI_NEWLINE = re.compile(r"\n{3,}")
_MULTI_SPACE = re.compile(r"[ \t]{2,}")


def preprocess_text(text: str) -> str:
    """Strip LaTeX markup for Chinese-readable TTS input.

    Transformation:
      - Display math $$...$$ → removed (replaced with spacing)
      - Inline math $...$ → removed
      - LaTeX backslash commands → stripped
      - Math environments → removed
      - Excess whitespace → collapsed

    Args:
        text: raw explanation text with possible LaTeX

    Returns:
        clean plain text suitable for zh-CN TTS
    """
    if not text:
        return ""

    # Remove math environments first (they can be multiline)
    cleaned = _MATH_ENV.sub(" ", text)

    # Remove display math
    cleaned = _LATEX_DISPLAY.sub(" ", cleaned)

    # Remove inline math
    cleaned = _LATEX_INLINE.sub("", cleaned)

    # Remove remaining LaTeX commands: \cmd{text} → text, then bare \cmd → ""
    cleaned = _LATEX_CMD_WITH_BRACES.sub(r"\1", cleaned)
    cleaned = _LATEX_CMD_BARE.sub("", cleaned)

    # Normalize whitespace
    cleaned = _MULTI_SPACE.sub(" ", cleaned)
    cleaned = _MULTI_NEWLINE.sub("\n\n", cleaned)
    cleaned = cleaned.strip()

    return cleaned


def _strip_think_tags(text: str) -> str:
    """Remove <｜end▁of▁thinking｜>... content inserted by reasoning models."""
    cleaned = re.sub(r"思考.*?思考", "", text, flags=re.DOTALL)
    cleaned = re.sub(r"\\boxed\{.*?\}", " ", cleaned)
    return cleaned.strip()


# ── Cache utilities ───────────────────────────────────────────────────────


def cache_key(text: str, voice: str) -> str:
    """SHA-256 hex digest of (normalized text + voice name).

    Normalization strips whitespace so that minor formatting changes
    still hit the same cache entry.
    """
    normalized = text.strip() + "|" + voice
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def _ensure_cache_dir() -> Path:
    """Create cache directory if it doesn't exist."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    return CACHE_DIR


# ── TTSService ────────────────────────────────────────────────────────────


class TTSService:
    """Async TTS synthesis via edge-tts with disk caching.

    Usage::

        tts = TTSService()
        audio_bytes = await tts.synthesize("这是一段讲解文字")

    Args:
        cache_dir: override default caching directory
        default_voice: override DEFAULT_VOICE
    """

    def __init__(
        self,
        cache_dir: Path | None = None,
        default_voice: str = DEFAULT_VOICE,
    ) -> None:
        self._cache_dir = cache_dir or CACHE_DIR
        self._default_voice = default_voice

    # ── public API ────────────────────────────────────────────────────────

    async def synthesize(
        self,
        text: str,
        voice: str | None = None,
        rate: str = DEFAULT_RATE,
        volume: str = DEFAULT_VOLUME,
        pitch: str = DEFAULT_PITCH,
    ) -> bytes:
        """Synthesize speech from text, returning mp3 bytes.

        Args:
            text: 讲解文本（含 LaTeX 标记，内部自动清洗）
            voice: zh-CN voice ShortName; defaults to zh-CN-XiaoxiaoNeural
            rate:  speed modifier e.g. "+0%", "-10%"
            volume: volume modifier
            pitch:  pitch modifier e.g. "+0Hz"

        Returns:
            mp3 audio bytes (24 kHz / 48 kbps CBR mono)

        Raises:
            TTSVoiceError: voice not in whitelist
            TTSNetworkError: edge-tts unreachable
            TTSError: other synthesis failures
        """
        # ── preprocess ────────────────────────────────────────────────
        cleaned = preprocess_text(text)
        if not cleaned:
            raise TTSVoiceError("text is empty after preprocessing")

        # ── voice validation ──────────────────────────────────────────
        use_voice = voice or self._default_voice
        if use_voice not in VOICE_WHITELIST:
            raise TTSVoiceError(
                f"Voice '{use_voice}' not in whitelist. "
                f"Available: {', '.join(sorted(VOICE_WHITELIST))}"
            )

        # ── cache check ───────────────────────────────────────────────
        key = cache_key(cleaned, use_voice)
        cached = self._load_cache(key)
        if cached is not None:
            logger.info("TTS cache hit: %s", key[:12])
            return cached

        # ── synthesize via edge-tts ───────────────────────────────────
        logger.info("TTS synthesizing: key=%s voice=%s len=%d", key[:12], use_voice, len(cleaned))
        try:
            audio_data = await self._call_edge_tts(
                text=cleaned,
                voice=use_voice,
                rate=rate,
                volume=volume,
                pitch=pitch,
            )
        except TTSError:
            raise
        except Exception as exc:
            logger.exception("Unexpected TTS error")
            raise TTSError(f"Unexpected synthesis error: {exc}") from exc

        # ── save to cache ─────────────────────────────────────────────
        self._save_cache(key, audio_data)

        return audio_data

    async def synthesize_to_file(
        self,
        text: str,
        output_path: str | Path,
        voice: str | None = None,
        rate: str = DEFAULT_RATE,
    ) -> int:
        """Synthesize and save to a file path. Returns byte count.

        This is the preferred path when the caller wants a file on disk
        (e.g. for FastAPI FileResponse). It reuses the disk cache.
        """
        audio_data = await self.synthesize(text=text, voice=voice, rate=rate)

        key = cache_key(preprocess_text(text), voice or self._default_voice)
        cache_path = self._cache_path(key)

        # If synthesize already cached it, just verify
        if not cache_path.exists():
            self._save_cache(key, audio_data)

        # If output_path differs from cache path, copy it
        dest = Path(output_path)
        if dest.absolute() != cache_path.absolute():
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(audio_data)

        return len(audio_data)

    def cache_exists(self, text: str, voice: str | None = None) -> bool:
        """Check if cached audio exists for this text+voice pair."""
        cleaned = preprocess_text(text)
        use_voice = voice or self._default_voice
        key = cache_key(cleaned, use_voice)
        return self._cache_path(key).exists()

    # ── cache I/O ─────────────────────────────────────────────────────────

    def _cache_path(self, key: str) -> Path:
        self._cache_dir.mkdir(parents=True, exist_ok=True)
        return self._cache_dir / f"{key}.mp3"

    def _load_cache(self, key: str) -> bytes | None:
        p = self._cache_path(key)
        try:
            return p.read_bytes()
        except FileNotFoundError:
            return None
        except OSError as exc:
            logger.warning("TTS cache read error for %s: %s", key[:12], exc)
            return None

    def _save_cache(self, key: str, data: bytes) -> None:
        p = self._cache_path(key)
        try:
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes(data)
            logger.debug("TTS cached: %s (%d bytes)", key[:12], len(data))
        except OSError as exc:
            logger.warning("TTS cache write error for %s: %s", key[:12], exc)

    # ── edge-tts call ─────────────────────────────────────────────────────

    @staticmethod
    async def _call_edge_tts(
        text: str,
        voice: str,
        rate: str = DEFAULT_RATE,
        volume: str = DEFAULT_VOLUME,
        pitch: str = DEFAULT_PITCH,
    ) -> bytes:
        """Call edge-tts Communicate.stream() and collect audio bytes."""
        from edge_tts import Communicate
        from edge_tts.exceptions import (
            EdgeTTSException,
            NoAudioReceived,
            UnexpectedResponse,
            WebSocketError,
        )

        try:
            communicate = Communicate(
                text=text,
                voice=voice,
                rate=rate,
                volume=volume,
                pitch=pitch,
            )
        except Exception as exc:
            logger.error("edge-tts initialization failed: %s", exc)
            raise TTSNetworkError(f"edge-tts init failed: {exc}") from exc

        chunks: list[bytes] = []
        try:
            async for chunk in communicate.stream():
                if chunk["type"] == "audio":
                    chunks.append(chunk["data"])
        except WebSocketError as exc:
            logger.error("edge-tts WebSocket error for voice=%s: %s", voice, exc)
            raise TTSNetworkError(f"edge-tts WebSocket error: {exc}") from exc
        except NoAudioReceived as exc:
            logger.error("edge-tts returned no audio for voice=%s, len=%d", voice, len(text))
            raise TTSVoiceError(f"No audio received for voice '{voice}'") from exc
        except UnexpectedResponse as exc:
            logger.error("edge-tts unexpected response: %s", exc)
            raise TTSError(f"edge-tts unexpected response: {exc}") from exc
        except EdgeTTSException as exc:
            logger.error("edge-tts error: %s", exc)
            raise TTSError(f"edge-tts error: {exc}") from exc

        if not chunks:
            raise TTSNetworkError("edge-tts returned empty audio stream")

        return b"".join(chunks)


# ── module-level singleton ────────────────────────────────────────────────

tts_service = TTSService()
