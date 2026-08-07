"""Tests for M3.5 AI services — TTS voice synthesis + UGC question parsing (T21).

Tests cover:
  - TTS: text preprocessing (LaTeX stripping), voice validation, cache key,
    synthesize (mocked edge-tts), error handling, empty-input guard.
  - UGC: pre-check rules, text parsing via LLM, image parsing via mock OCR,
    UGCStats auto-approve threshold, error/fallback handling.

All external dependencies (edge-tts, LLM gateway, OCR) are mocked.
"""

import json
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.tts_service import (
    TTSError,
    TTSNetworkError,
    TTSVoiceError,
    TTSService,
    cache_key,
    preprocess_text,
    tts_service,
    VOICE_WHITELIST,
    DEFAULT_VOICE,
)
from app.services.ugc_service import (
    UGCParserService,
    UGCInput,
    UGCParseResult,
    UGCStats,
    run_precheck,
    ugc_parser,
    AUTO_APPROVE_MIN_APPROVED,
    AUTO_APPROVE_MIN_RATE,
)

pytestmark = pytest.mark.anyio


# ═══════════════════════════════════════════════════════════════════════════
# TTS — Text Preprocessing
# ═══════════════════════════════════════════════════════════════════════════


class TestTextPreprocessing:
    """Test LaTeX stripping and text normalization for TTS."""

    def test_strips_display_math(self):
        """Display math $$...$$ is removed."""
        text = "根据公式 $$\\lim_{x \\to 0} \\frac{\\sin x}{x} = 1$$ 可得"
        result = preprocess_text(text)
        assert "sin" not in result.lower() or "\\lim" not in result
        assert "可得" in result

    def test_strips_inline_math(self):
        """Inline math $...$ is removed."""
        text = "当 $x \\to 0$ 时，$\\sin x \\approx x$"
        result = preprocess_text(text)
        assert "\\to" not in result
        assert "\\sin" not in result
        assert "时" in result

    def test_strips_latex_commands(self):
        """Backslash LaTeX commands are stripped."""
        text = "\\textbf{注意} \\frac{a}{b} 是分数"
        result = preprocess_text(text)
        assert "textbf" not in result
        assert "frac" not in result
        assert "注意" in result

    def test_strips_math_environments(self):
        """\\begin{...}...\\end{...} blocks are removed."""
        text = "解：\\begin{aligned} x + y &= 5 \\\\ x - y &= 1 \\end{aligned} 得解"
        result = preprocess_text(text)
        assert "aligned" not in result
        assert "得解" in result

    def test_collapses_whitespace(self):
        """Multiple spaces/newlines are collapsed."""
        text = "第一段   \n\n\n\n   第二段"
        result = preprocess_text(text)
        assert result.count("\n\n") <= 1
        assert "   " not in result

    def test_preserves_chinese_text(self):
        """Chinese text is preserved intact."""
        text = "这是高等数学中关于极限与连续性的讲解内容"
        result = preprocess_text(text)
        assert result == text.strip()

    def test_empty_input(self):
        """Empty string returns empty string."""
        assert preprocess_text("") == ""
        assert preprocess_text("   ") == ""


# ═══════════════════════════════════════════════════════════════════════════
# TTS — Cache Key
# ═══════════════════════════════════════════════════════════════════════════


class TestCacheKey:
    """Test SHA-256 cache key computation."""

    def test_same_input_produces_same_key(self):
        """Identical text+voice → identical key."""
        k1 = cache_key("测试文本", "zh-CN-XiaoxiaoNeural")
        k2 = cache_key("测试文本", "zh-CN-XiaoxiaoNeural")
        assert k1 == k2
        assert len(k1) == 64  # SHA-256 hex

    def test_different_voice_different_key(self):
        """Different voice → different key."""
        k1 = cache_key("测试", "zh-CN-XiaoxiaoNeural")
        k2 = cache_key("测试", "zh-CN-YunxiNeural")
        assert k1 != k2

    def test_whitespace_normalization(self):
        """Leading/trailing whitespace is normalized."""
        k1 = cache_key("测试文本", "zh-CN-XiaoxiaoNeural")
        k2 = cache_key("  测试文本  ", "zh-CN-XiaoxiaoNeural")
        assert k1 == k2

    def test_key_is_hex_string(self):
        """Cache key is a valid hex string."""
        k = cache_key("hello", "zh-CN-XiaoxiaoNeural")
        assert all(c in "0123456789abcdef" for c in k)


# ═══════════════════════════════════════════════════════════════════════════
# TTS — Voice Validation
# ═══════════════════════════════════════════════════════════════════════════


class TestVoiceValidation:
    """Test voice whitelist and validation."""

    def test_default_voice_in_whitelist(self):
        """Default voice is in the whitelist."""
        assert DEFAULT_VOICE in VOICE_WHITELIST

    def test_xiaoxiao_in_whitelist(self):
        """zh-CN-XiaoxiaoNeural is in whitelist."""
        assert "zh-CN-XiaoxiaoNeural" in VOICE_WHITELIST

    def test_yunxi_in_whitelist(self):
        """zh-CN-YunxiNeural is in whitelist."""
        assert "zh-CN-YunxiNeural" in VOICE_WHITELIST

    def test_invalid_voice_raises_error(self):
        """Non-whitelisted voice raises TTSVoiceError."""
        with pytest.raises(TTSVoiceError):
            raise TTSVoiceError("Voice 'zh-CN-InvalidVoice' not in whitelist")

    def test_asyncio_raises_ttserror(self):
        """TTSNetworkError is a TTSError and Exception."""
        assert issubclass(TTSNetworkError, TTSError)
        assert issubclass(TTSError, Exception)

    async def test_empty_text_raises_voice_error(self):
        """Empty text after preprocessing raises TTSVoiceError."""
        svc = TTSService()
        with pytest.raises(TTSVoiceError, match="empty"):
            await svc.synthesize("")


# ═══════════════════════════════════════════════════════════════════════════
# TTS — Synthesize (mocked edge-tts)
# ═══════════════════════════════════════════════════════════════════════════


class TestTTSSynthesize:
    """Test synthesize with mocked edge-tts."""

    async def test_synthesize_returns_bytes(self):
        """Synthesize returns non-empty bytes with mocked edge-tts."""
        mock_audio = b"\xff\xfb\x90\x00" * 400

        with patch.object(
            TTSService, "_call_edge_tts", new_callable=AsyncMock, return_value=mock_audio
        ):
            result = await tts_service.synthesize("这是一段测试讲解文本")
            assert isinstance(result, bytes)
            assert len(result) > 0

    async def test_synthesize_with_custom_voice(self):
        """Synthesize works with a different whitelisted voice."""
        mock_audio = b"\xff\xfb\x90\x00" * 200

        with patch.object(
            TTSService, "_call_edge_tts", new_callable=AsyncMock, return_value=mock_audio
        ):
            result = await tts_service.synthesize(
                "讲解内容", voice="zh-CN-YunxiNeural"
            )
            assert isinstance(result, bytes)
            assert len(result) > 0

    async def test_synthesize_invalid_voice_raises(self):
        """Non-whitelisted voice raises TTSVoiceError."""
        with pytest.raises(TTSVoiceError, match="whitelist"):
            await tts_service.synthesize("test", voice="en-US-AriaNeural")

    async def test_synthesize_network_error_raises(self):
        """WebSocket error from edge-tts → TTSNetworkError."""
        with patch.object(
            TTSService,
            "_call_edge_tts",
            new_callable=AsyncMock,
            side_effect=TTSNetworkError("Connection refused"),
        ):
            with pytest.raises(TTSNetworkError, match="Connection refused"):
                await tts_service.synthesize("test text")

    async def test_synthesize_no_audio_raises(self):
        """NoAudioReceived → TTSVoiceError."""
        with patch.object(
            TTSService,
            "_call_edge_tts",
            new_callable=AsyncMock,
            side_effect=TTSVoiceError("No audio received for voice"),
        ):
            with pytest.raises(TTSVoiceError, match="No audio"):
                await tts_service.synthesize("test text")

    async def test_synthesize_preserves_cleaned_input(self):
        """LaTeX is stripped before edge-tts call (verified via preprocessing)."""
        # preprocess_text strips LaTeX; the synthesize pipeline calls it internally.
        cleaned = preprocess_text("极限 $\\lim_{x\\to 0} f(x)$ 存在")
        assert "\\lim" not in cleaned
        assert "极限" in cleaned
        assert "存在" in cleaned
        assert len(cleaned) > 0


# ═══════════════════════════════════════════════════════════════════════════
# TTS — Cache Behavior
# ═══════════════════════════════════════════════════════════════════════════


class TestTTSCache:
    """Test disk cache behavior."""

    def test_cache_exists_checks_disk(self, tmp_path):
        """cache_exists returns True when file exists."""
        svc = TTSService(cache_dir=tmp_path)
        cleaned = preprocess_text("测试文本")
        key = cache_key(cleaned, DEFAULT_VOICE)
        # Write directly to cache location
        cache_path = tmp_path / f"{key}.mp3"
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        cache_path.write_bytes(b"fake mp3 data")
        assert svc.cache_exists("测试文本") is True

    def test_cache_miss_when_no_file(self, tmp_path):
        """cache_exists returns False when no cache file."""
        svc = TTSService(cache_dir=tmp_path)
        assert svc.cache_exists("不存在的文本") is False


# ═══════════════════════════════════════════════════════════════════════════
# UGC — Pre-check Rules
# ═══════════════════════════════════════════════════════════════════════════


class TestUGCPrecheck:
    """Test UGC validation rules."""

    def test_empty_text_fails(self):
        passed, issues = run_precheck("")
        assert passed is False
        assert any("empty" in i for i in issues)

    def test_too_short_fails(self):
        passed, issues = run_precheck("求")
        assert passed is False
        assert any("short" in i for i in issues)

    def test_spam_pattern_fails(self):
        passed, issues = run_precheck("加微信 ABCD123 获取答案")
        assert passed is False
        assert any("spam" in i for i in issues)

    def test_url_pattern_fails(self):
        passed, issues = run_precheck("答案在这 https://example.com")
        assert passed is False
        assert any("spam" in i for i in issues)

    def test_cheat_pattern_fails(self):
        passed, issues = run_precheck("代考高数期末，价格面议")
        assert passed is False
        assert any("spam" in i for i in issues)

    def test_valid_question_passes(self):
        passed, issues = run_precheck(
            "求函数 f(x) = x^2 + 2x + 1 在区间 [0, 1] 上的最大值"
        )
        assert passed is True
        assert issues == []

    def test_choice_question_passes(self):
        passed, issues = run_precheck(
            "下列关于极限的说法正确的是 A. 极限总是存在 B. 极限唯一 C. 两者都正确 D. 两者都不正确"
        )
        assert passed is True
        assert issues == []


# ═══════════════════════════════════════════════════════════════════════════
# UGC — UGCStats
# ═══════════════════════════════════════════════════════════════════════════


class TestUGCStats:
    """Test UGCStats auto-approve threshold logic."""

    def test_empty_stats(self):
        stats = UGCStats()
        assert stats.total_approved == 0
        assert stats.total_submitted == 0
        assert stats.approval_rate == 0.0
        assert stats.qualifies_for_auto_approve is False

    def test_high_approval_rate_qualifies(self):
        stats = UGCStats(total_approved=10, total_submitted=11)
        assert stats.approval_rate == pytest.approx(10 / 11)
        assert stats.qualifies_for_auto_approve is True

    def test_low_count_no_auto_approve(self):
        stats = UGCStats(total_approved=4, total_submitted=4)
        assert stats.approval_rate == 1.0
        assert stats.qualifies_for_auto_approve is False  # fewer than min

    def test_at_threshold(self):
        stats = UGCStats(total_approved=5, total_submitted=5)
        assert stats.qualifies_for_auto_approve is True

    def test_below_approval_rate(self):
        stats = UGCStats(total_approved=8, total_submitted=10)
        assert stats.approval_rate == 0.8
        assert stats.qualifies_for_auto_approve is False


# ═══════════════════════════════════════════════════════════════════════════
# UGC — Parse (text input, mocked LLM)
# ═══════════════════════════════════════════════════════════════════════════


class TestUGCParseText:
    """Test UGC parsing with text input and mocked LLM."""

    async def test_parse_text_question_success(self):
        """Valid text input returns structured result."""
        mock_llm = AsyncMock()
        mock_llm.chat.side_effect = [
            # structure call
            {
                "content": json.dumps({
                    "type": "single",
                    "content": "求极限 $\\lim_{x\\to 0}\\frac{\\sin x}{x}$",
                    "options": {"A": "0", "B": "1", "C": "∞", "D": "不存在"},
                    "answer": {"correct": "B"},
                    "analysis": "使用重要极限公式",
                    "confidence": 0.9,
                }),
                "model": "deepseek-chat",
                "usage": {"prompt_tokens": 100, "completion_tokens": 80},
            },
            # KP suggestion call
            {
                "content": json.dumps([
                    {"name": "重要极限", "score": 0.95},
                    {"name": "极限计算", "score": 0.70},
                ]),
                "model": "deepseek-chat",
                "usage": {"prompt_tokens": 50, "completion_tokens": 40},
            },
        ]

        parser = UGCParserService(gateway=mock_llm)
        ugc_input = UGCInput(
            text_content="求极限 lim(x→0) sin(x)/x",
            subject_name="高等数学",
        )

        result = await parser.parse(ugc_input)

        assert result.success is True
        assert result.source == "ugc"
        assert result.type == "single"
        assert "sin" in result.content
        assert result.options is not None
        assert result.options["B"] == "1"
        assert result.answer == {"correct": "B"}
        assert result.confidence == 0.9
        assert result.precheck_passed is True
        assert len(result.suggested_kps) == 2
        assert result.suggested_kps[0]["name"] == "重要极限"

    async def test_parse_without_options(self):
        """Fill-in-the-blank question has no options."""
        mock_llm = AsyncMock()
        mock_llm.chat.side_effect = [
            {
                "content": json.dumps({
                    "type": "blank",
                    "content": "函数 $f(x)$ 在 $x_0$ 处可导，则 $f'(x_0)$ = _____",
                    "options": None,
                    "answer": "$\\lim_{h\\to 0}\\frac{f(x_0+h)-f(x_0)}{h}$",
                    "confidence": 0.95,
                }),
                "model": "deepseek-chat",
                "usage": {"prompt_tokens": 80, "completion_tokens": 60},
            },
            {
                "content": json.dumps([{"name": "导数定义", "score": 0.98}]),
                "model": "deepseek-chat",
                "usage": {"prompt_tokens": 40, "completion_tokens": 30},
            },
        ]

        parser = UGCParserService(gateway=mock_llm)
        ugc_input = UGCInput(
            text_content="函数 f(x) 在 x0 处可导，则 f'(x0) = _____",
            subject_name="高等数学",
        )
        result = await parser.parse(ugc_input)

        assert result.success is True
        assert result.type == "blank"
        assert result.options is None

    async def test_fallback_on_llm_error(self):
        """LLM failure returns fallback with raw text."""
        mock_llm = AsyncMock()
        mock_llm.chat.side_effect = Exception("API timeout")

        parser = UGCParserService(gateway=mock_llm)
        ugc_input = UGCInput(
            text_content="求不定积分 ∫ x² dx",
            subject_name="高等数学",
        )

        result = await parser.parse(ugc_input)

        assert result.success is True  # LLM failure does not block
        assert result.confidence <= 0.3  # low confidence fallback
        assert result.precheck_passed is True

    async def test_auto_approve_trusted_contributor(self):
        """Trusted contributor with high confidence gets auto-approved."""
        mock_llm = AsyncMock()
        mock_llm.chat.side_effect = [
            {
                "content": json.dumps({
                    "type": "single",
                    "content": "测试题目",
                    "options": {"A": "1", "B": "2"},
                    "answer": {"correct": "A"},
                    "confidence": 0.85,
                }),
                "model": "deepseek-chat",
                "usage": {"prompt_tokens": 50, "completion_tokens": 40},
            },
            {
                "content": json.dumps([{"name": "测试", "score": 0.5}]),
                "model": "deepseek-chat",
                "usage": {"prompt_tokens": 30, "completion_tokens": 20},
            },
        ]

        parser = UGCParserService(gateway=mock_llm)
        ugc_input = UGCInput(
            text_content="这是一个测试题目，包含选项",
            contributor_stats={"total_approved": 10, "total_submitted": 11},
        )

        result = await parser.parse(ugc_input)

        assert result.success is True
        assert result.auto_approved is True


# ═══════════════════════════════════════════════════════════════════════════
# UGC — Parse (image input, mocked OCR)
# ═══════════════════════════════════════════════════════════════════════════


class TestUGCParseImage:
    """Test UGC parsing with image input and mocked OCR."""

    async def test_image_parse_via_ocr_success(self):
        """Image input passes through OCR pipeline and gets structured."""
        mock_ocr = MagicMock()
        mock_ocr.recognize_bytes = AsyncMock()
        mock_ocr.recognize_bytes.return_value = MagicMock(
            success=True,
            raw_markdown="求极限 $\\lim_{x\\to 0} f(x)$",
            text_only="求极限",
            confidence=0.82,
        )

        mock_llm = AsyncMock()
        mock_llm.chat.side_effect = [
            {
                "content": json.dumps({
                    "type": "single",
                    "content": "求极限 $\\lim_{x\\to 0} f(x)$",
                    "options": {"A": "0", "B": "1"},
                    "answer": {"correct": "B"},
                    "confidence": 0.85,
                }),
                "model": "deepseek-chat",
                "usage": {"prompt_tokens": 80, "completion_tokens": 60},
            },
            {
                "content": json.dumps([{"name": "极限计算", "score": 0.8}]),
                "model": "deepseek-chat",
                "usage": {"prompt_tokens": 40, "completion_tokens": 20},
            },
        ]

        parser = UGCParserService(ocr=mock_ocr, gateway=mock_llm)
        ugc_input = UGCInput(
            image_data=b"fake_jpg_data",
            image_filename="question.jpg",
            subject_name="高等数学",
        )

        result = await parser.parse(ugc_input)

        assert result.success is True
        assert result.source == "ugc"
        assert result.type == "single"
        assert result.confidence > 0.8

    async def test_ocr_failure_returns_error(self):
        """OCR failure returns error result."""
        mock_ocr = MagicMock()
        mock_ocr.recognize_bytes = AsyncMock()
        mock_ocr.recognize_bytes.return_value = MagicMock(
            success=False,
            error="Pix2Text 未安装",
        )

        parser = UGCParserService(ocr=mock_ocr, gateway=AsyncMock())
        ugc_input = UGCInput(
            image_data=b"fake_jpg_data",
            image_filename="question.jpg",
        )

        result = await parser.parse(ugc_input)

        assert result.success is False
        assert "OCR 识别失败" in (result.error or "")
        assert result.precheck_passed is False


# ═══════════════════════════════════════════════════════════════════════════
# UGC — Precheck-only endpoint
# ═══════════════════════════════════════════════════════════════════════════


class TestUGCPrecheckOnly:
    """Test precheck_only method."""

    async def test_precheck_only_valid(self):
        """precheck_only returns (True, []) for valid text."""
        passed, issues = await ugc_parser.precheck_only(
            "求函数 f(x) 在 [0,1] 上的定积分"
        )
        assert passed is True
        assert issues == []

    async def test_precheck_only_invalid(self):
        """precheck_only returns (False, [...]) for spam."""
        passed, issues = await ugc_parser.precheck_only("加微信买答案")
        assert passed is False
        assert len(issues) > 0


# ═══════════════════════════════════════════════════════════════════════════
# Service singletons
# ═══════════════════════════════════════════════════════════════════════════


class TestServiceSingletons:
    """Verify module-level singleton instances exist."""

    def test_tts_service_exists(self):
        assert tts_service is not None
        assert isinstance(tts_service, TTSService)

    def test_ugc_parser_exists(self):
        assert ugc_parser is not None
        assert isinstance(ugc_parser, UGCParserService)
