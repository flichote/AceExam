"""OCR service — Pix2Text ONNX local inference for photo-to-question.

Uses Pix2Text's `recognize_text_formula()` for mixed text + formula (LaTeX)
recognition from textbook/screenshot photos.

MVP: simple wrapper with graceful degradation (returns a clear error when
Pix2Text is not installed / model not downloaded).  Production path requires
`pip install pix2text[multilingual]` and first-run model download (~1-2 GB).

Architecture (per PRD):
  - ONNX local inference, zero API cost
  - Supports ch_sim (Simplified Chinese) + mixed formula recognition
  - Output: Markdown with LaTeX formulas
  - MVP: give interface + stub impl + error fallback; user must confirm OCR
    results before ingestion into the question bank
"""

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# ── Output structures ──────────────────────────────────────────────────────


@dataclass
class OCRResult:
    """Structured OCR output for a question photo."""

    success: bool
    raw_markdown: str = ""  # Markdown with LaTeX formulas
    text_only: str = ""  # plain-text version (for search / embedding)
    formulas: list[str] = None  # list of extracted LaTeX expressions
    confidence: float = 0.0  # overall confidence [0, 1]
    error: str | None = None  # non-empty when success=False

    def __post_init__(self) -> None:
        if self.formulas is None:
            self.formulas = []


# ── Pix2Text wrapper ───────────────────────────────────────────────────────


class OCRService:
    """Photo-to-question OCR via Pix2Text (ONNX local)."""

    # Languages that Pix2Text supports for mixed recognition
    _SUPPORTED_LANGS = {
        "ch_sim": "简体中文",
        "ch_tra": "繁體中文",
        "en": "English",
        "ja": "日本語",
        "ko": "한국어",
    }

    def __init__(self, lang: str = "ch_sim", enable_formula: bool = True) -> None:
        self._lang = lang
        self._enable_formula = enable_formula
        self._p2t: Any = None  # lazy-loaded Pix2Text instance
        self._available: bool | None = None  # tri-state: None=unchecked

    @property
    def is_available(self) -> bool:
        """Check whether Pix2Text is installed and usable (cached)."""
        if self._available is None:
            self._available = self._check_dependency()
        return self._available

    # ── public API ─────────────────────────────────────────────────────────

    async def recognize_file(self, file_path: str | Path) -> OCRResult:
        """Recognize text + formulas from an image file.

        Args:
            file_path: path to the image (jpg, png, etc.)

        Returns:
            OCRResult with success=True and structured output, or success=False with error.
        """
        fp = Path(file_path)
        if not fp.exists():
            return OCRResult(
                success=False,
                error=f"文件不存在: {file_path}",
            )

        if not self.is_available:
            return OCRResult(
                success=False,
                error=(
                    "Pix2Text 未安装或模型未下载。"
                    "请运行: pip install pix2text[multilingual]"
                    "并首次运行时下载 ONNX 模型（约 1-2 GB）。"
                ),
            )

        try:
            return await self._recognize(fp)
        except Exception as exc:
            logger.exception("OCR recognize_file failed for %s", fp)
            return OCRResult(
                success=False,
                error=f"OCR 识别失败: {exc}",
            )

    async def recognize_bytes(
        self,
        data: bytes,
        filename: str = "upload.jpg",
    ) -> OCRResult:
        """Recognize text + formulas from image bytes (in-memory)."""
        import tempfile

        with tempfile.NamedTemporaryFile(
            suffix=".jpg", delete=False
        ) as tmp:
            tmp.write(data)
            tmp.flush()
            try:
                return await self.recognize_file(tmp.name)
            finally:
                Path(tmp.name).unlink(missing_ok=True)

    # ── internal ───────────────────────────────────────────────────────────

    @staticmethod
    def _check_dependency() -> bool:
        """Check if pix2text is importable."""
        try:
            import pix2text  # noqa: F401
            return True
        except ImportError:
            logger.warning(
                "Pix2Text not installed — OCR will return errors. "
                "Install with: pip install pix2text[multilingual]"
            )
            return False

    async def _recognize(self, file_path: Path) -> OCRResult:
        """Actual OCR call via Pix2Text (runs in thread to keep async)."""
        import asyncio
        import re

        # Initialize Pix2Text lazily (first call)
        if self._p2t is None:
            self._p2t = await asyncio.to_thread(self._init_p2t)

        # Run recognition in thread (Pix2Text is CPU/ONNX, not async)
        result = await asyncio.to_thread(
            self._p2t.recognize_text_formula,
            str(file_path),
            resized_shape=768,
            return_text=True,
            auto_line_break=True,
        )

        raw = result if isinstance(result, str) else str(result)

        # Extract LaTeX formulas
        formulas = re.findall(r"\$\$?(.+?)\$\$?", raw)

        # Plain text (strip LaTeX markers)
        text_only = re.sub(r"\$\$?[^$]+\$\$?", "", raw)
        text_only = re.sub(r"\s+", " ", text_only).strip()

        # Confidence — Pix2Text doesn't give per-result confidence in MVP;
        # use a heuristic based on output length vs expected.
        confidence = 0.85 if len(raw) > 10 else 0.5

        return OCRResult(
            success=True,
            raw_markdown=raw,
            text_only=text_only,
            formulas=formulas,
            confidence=round(confidence, 2),
        )

    def _init_p2t(self):
        """Blocking init — called in a thread."""
        from pix2text import Pix2Text

        return Pix2Text.from_config()


# ── module-level convenience ──

ocr_service = OCRService()
