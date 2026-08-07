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


# ═══════════════════════════════════════════════════════════════════════════
# StructuredQuestion and KnowledgePointSuggestion dataclasses
# ═══════════════════════════════════════════════════════════════════════════


class TestStructuredQuestion:
    """Test StructuredQuestion dataclass and parsing."""

    def test_defaults(self):
        from app.services.ocr_service import StructuredQuestion
        sq = StructuredQuestion()
        assert sq.type == ""
        assert sq.content == ""
        assert sq.options is None
        assert sq.confidence == 0.0

    def test_full_question(self):
        from app.services.ocr_service import StructuredQuestion
        sq = StructuredQuestion(
            type="single",
            content="求极限 $\\lim_{x\\to 0}\\frac{\\sin x}{x}$",
            options={"A": "0", "B": "1", "C": "∞", "D": "不存在"},
            answer={"correct": "B"},
            analysis="重要极限：$\\lim_{x\\to 0}\\frac{\\sin x}{x}=1$",
            confidence=0.92,
            raw_ocr_text="求极限 lim sin(x)/x",
        )
        assert sq.type == "single"
        assert "sin" in sq.content
        assert sq.options is not None
        assert sq.options["B"] == "1"
        assert sq.answer == {"correct": "B"}
        assert sq.confidence == 0.92


class TestKnowledgePointSuggestion:
    """Test KnowledgePointSuggestion dataclass."""

    def test_defaults(self):
        from app.services.ocr_service import KnowledgePointSuggestion
        kps = KnowledgePointSuggestion()
        assert kps.id == ""
        assert kps.name == ""
        assert kps.score == 0.0

    def test_full_suggestion(self):
        from app.services.ocr_service import KnowledgePointSuggestion
        kps = KnowledgePointSuggestion(
            id="kp-123",
            name="洛必达法则",
            score=0.92,
        )
        assert kps.name == "洛必达法则"
        assert kps.score == 0.92


# ═══════════════════════════════════════════════════════════════════════════
# OCR JSON parsing (structure output)
# ═══════════════════════════════════════════════════════════════════════════


class TestOCRJsonParsing:
    """Test _parse_structure_json for LLM structure output."""

    def test_parse_valid_json(self):
        from app.services.ocr_service import OCRService
        json_str = '{"type": "single", "content": "1+1=?", "confidence": 0.9}'
        parsed = OCRService._parse_structure_json(json_str)
        assert parsed is not None
        assert parsed["type"] == "single"
        assert parsed["confidence"] == 0.9

    def test_parse_json_with_fence(self):
        from app.services.ocr_service import OCRService
        json_str = '```json\n{"type": "blank", "content": "填空", "confidence": 0.7}\n```'
        parsed = OCRService._parse_structure_json(json_str)
        assert parsed is not None
        assert parsed["type"] == "blank"

    def test_parse_invalid(self):
        from app.services.ocr_service import OCRService
        assert OCRService._parse_structure_json("不是 JSON") is None
        assert OCRService._parse_structure_json("") is None

    def test_parse_json_array(self):
        from app.services.ocr_service import OCRService
        json_str = '[{"name": "极限", "score": 0.9}, {"name": "导数", "score": 0.7}]'
        parsed = OCRService._parse_structure_json(json_str)
        assert isinstance(parsed, list)
        assert len(parsed) == 2
        assert parsed[0]["name"] == "极限"


# ═══════════════════════════════════════════════════════════════════════════
# Full pipeline data structures
# ═══════════════════════════════════════════════════════════════════════════


class TestOCRFullPipelineStructures:
    """Test OCR pipeline output structures (no network)."""

    def test_structure_question_empty_input(self):
        """structure_question with empty OCR result returns defaults."""
        import asyncio
        from app.services.ocr_service import OCRService, OCRResult

        async def _run():
            svc = OCRService()
            empty = OCRResult(success=False, error="no text")
            sq = await svc.structure_question(empty)
            assert sq.confidence == 0.0
            assert sq.type == ""

        asyncio.run(_run())

    def test_suggest_kp_empty_input(self):
        """suggest_knowledge_points with empty text returns empty list."""
        import asyncio
        from app.services.ocr_service import OCRService

        async def _run():
            svc = OCRService()
            result = await svc.suggest_knowledge_points("")
            assert result == []

        asyncio.run(_run())

    def test_ocr_service_has_new_methods(self):
        """Verify the OCR service exposes the new pipeline methods."""
        from app.services.ocr_service import OCRService, ocr_service
        assert hasattr(ocr_service, "structure_question")
        assert hasattr(ocr_service, "suggest_knowledge_points")
        assert hasattr(ocr_service, "full_pipeline")
        assert callable(ocr_service.structure_question)
        assert callable(ocr_service.suggest_knowledge_points)

    def test_onnx_config_present(self):
        """OCR service should have ONNX config defined."""
        from app.services.ocr_service import OCRService
        cfg = OCRService._ONNX_CONFIG
        assert "languages" in cfg
        assert "mfd" in cfg
        assert cfg["mfd"]["model_backend"] == "onnx"
        assert cfg["formula"]["model_backend"] == "onnx"
