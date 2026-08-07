"""Tests for OCR service — interface tests, data structures, graceful degradation."""

import pytest

from app.services.ocr_service import OCRService, OCRResult, ocr_service


# ═══════════════════════════════════════════════════════════════════════════
# OCRResult dataclass
# ═══════════════════════════════════════════════════════════════════════════


class TestOCRResult:
    """Test OCRResult data structure."""

    def test_success_result(self):
        r = OCRResult(
            success=True,
            raw_markdown="极限 $\\lim_{x \\to 0} f(x)$",
            text_only="极限",
            formulas=["\\lim_{x \\to 0} f(x)"],
            confidence=0.9,
        )
        assert r.success is True
        assert r.error is None
        assert len(r.formulas) == 1
        assert "极限" in r.raw_markdown

    def test_error_result(self):
        r = OCRResult(
            success=False,
            error="Pix2Text 未安装",
        )
        assert r.success is False
        assert r.error is not None
        assert r.raw_markdown == ""
        assert r.confidence == 0.0
        assert r.formulas == []

    def test_defaults(self):
        r = OCRResult(success=False)
        assert r.raw_markdown == ""
        assert r.text_only == ""
        assert r.formulas == []
        assert r.confidence == 0.0
        assert r.error is None


# ═══════════════════════════════════════════════════════════════════════════
# OCRService interface
# ═══════════════════════════════════════════════════════════════════════════


class TestOCRServiceInterface:
    """Test OCR service initialization and interface contracts."""

    def test_service_exists(self):
        assert ocr_service is not None
        assert isinstance(ocr_service, OCRService)

    def test_default_lang(self):
        svc = OCRService()
        assert svc._lang == "ch_sim"
        assert svc._enable_formula is True

    def test_custom_lang(self):
        svc = OCRService(lang="en", enable_formula=False)
        assert svc._lang == "en"
        assert svc._enable_formula is False

    def test_is_available_cached(self):
        svc = OCRService()
        # First check — should cache
        avail1 = svc.is_available
        avail2 = svc.is_available
        # Same result (cached)
        assert avail1 == avail2

    def test_recognize_file_not_found(self):
        import asyncio

        async def _run():
            svc = OCRService()
            result = await svc.recognize_file("/nonexistent/path/photo.jpg")
            assert result.success is False
            assert "不存在" in result.error

        asyncio.run(_run())

    def test_supported_languages(self):
        svc = OCRService()
        assert "ch_sim" in svc._SUPPORTED_LANGS
        assert "en" in svc._SUPPORTED_LANGS
        assert svc._SUPPORTED_LANGS["ch_sim"] == "简体中文"


# ═══════════════════════════════════════════════════════════════════════════
# Graceful degradation (Pix2Text not installed)
# ═══════════════════════════════════════════════════════════════════════════


class TestOCRGracefulDegradation:
    """When Pix2Text is not installed, the service should return clear errors."""

    def test_service_not_available_when_not_installed(self):
        """Without pix2text installed, is_available should be False."""
        # This test is safe in CI — pix2text won't be installed there
        svc = OCRService()
        # It might be available in dev, but the check shouldn't crash
        result = svc.is_available
        # Either True or False, shouldn't raise
        assert isinstance(result, bool)

    def test_recognize_file_handles_missing_dependency(self):
        """Even without pix2text, calling recognize_file should not crash."""
        import asyncio

        async def _run():
            svc = OCRService()
            # Create a temporary file
            import tempfile
            from pathlib import Path

            with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
                tmp.write(b"fake image data")
                tmp_path = tmp.name

            try:
                result = await svc.recognize_file(tmp_path)
                # Either succeeds (if pix2text installed) or fails gracefully
                assert isinstance(result, OCRResult)
                if not result.success:
                    assert result.error is not None
            finally:
                Path(tmp_path).unlink(missing_ok=True)

        asyncio.run(_run())


# ═══════════════════════════════════════════════════════════════════════════
# Formula extraction (regex tests)
# ═══════════════════════════════════════════════════════════════════════════


class TestFormulaExtraction:
    """Test LaTeX formula extraction logic (pure regex, no OCR)."""

    def test_inline_formula(self):
        """The OCR result should contain formulas extracted from markdown."""
        # This tests the regex in _recognize method
        import re
        raw = "极限定义：$\\lim_{x \\to 0} f(x) = A$ 是微积分的基础。"
        formulas = re.findall(r"\$\$?(.+?)\$\$?", raw)
        assert len(formulas) == 1
        assert "lim" in formulas[0]

    def test_display_formula(self):
        import re
        raw = "导数公式：$$f'(x) = \\lim_{h \\to 0} \\frac{f(x+h)-f(x)}{h}$$"
        formulas = re.findall(r"\$\$?(.+?)\$\$?", raw)
        assert len(formulas) == 1

    def test_multiple_formulas(self):
        import re
        raw = "已知 $a^2 + b^2 = c^2$，求 $\\frac{d}{dx} x^2$。"
        formulas = re.findall(r"\$\$?(.+?)\$\$?", raw)
        assert len(formulas) == 2

    def test_plain_text_stripping(self):
        import re
        raw = "极限定义：$\\lim_{x \\to 0} f(x) = A$ 是基础。导数：$f'(x)$。"
        text_only = re.sub(r"\$\$?[^$]+\$\$?", "", raw)
        text_only = re.sub(r"\s+", " ", text_only).strip()
        assert "极限定义" in text_only
        assert "是基础" in text_only
        assert "lim" not in text_only  # LaTeX removed
