"""OCR service — Pix2Text ONNX local inference for photo-to-question.

Uses Pix2Text's `recognize_text_formula()` for mixed text + formula (LaTeX)
recognition from textbook/screenshot photos.  Output flows through a structured
question pipeline: OCR → structured question JSON (LLM-assisted) → knowledge
point suggestion.

Architecture (per PRD):
  - ONNX local inference, zero API cost
  - Supports ch_sim (Simplified Chinese) + mixed formula recognition
  - Output: Markdown with LaTeX formulas → structured question → KP attribution
  - User must confirm OCR results before ingestion into the question bank
"""

import asyncio
import json
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from app.services.llm_gateway import LLMGateway, llm_gateway

logger = logging.getLogger(__name__)

# ── Output structures ──────────────────────────────────────────────────────


@dataclass
class OCRResult:
    """Structured OCR output for a question photo."""

    success: bool
    raw_markdown: str = ""  # Markdown with LaTeX formulas
    text_only: str = ""  # plain-text version (for search / embedding)
    formulas: list[str] = field(default_factory=list)
    confidence: float = 0.0  # overall confidence [0, 1]
    error: str | None = None  # non-empty when success=False


@dataclass
class StructuredQuestion:
    """OCR result after LLM structuring into a question object."""

    type: str = ""  # single / multi / blank / essay
    content: str = ""  # question stem (with LaTeX)
    options: dict[str, str] | None = None  # {"A": "...", ...} for choice questions
    answer: dict | str | None = None  # {"correct": "A"} or "exact answer"
    analysis: str = ""  # solution / explanation
    confidence: float = 0.0  # LLM structuring confidence [0, 1]
    raw_ocr_text: str = ""  # the original OCR text used for structuring


@dataclass
class KnowledgePointSuggestion:
    """Suggested knowledge point match for a question."""

    id: str = ""
    name: str = ""
    score: float = 0.0  # match score [0, 1]


# ── Pix2Text wrapper ───────────────────────────────────────────────────────


class OCRService:
    """Photo-to-question OCR via Pix2Text (ONNX local).

    Pipeline:
      1. recognize_file / recognize_bytes → OCRResult (raw text + formulas)
      2. structure_question(ocr_result) → StructuredQuestion (LLM parsing)
      3. suggest_knowledge_points(text) → list of KnowledgePointSuggestion
    """

    # Languages that Pix2Text supports for mixed recognition
    _SUPPORTED_LANGS = {
        "ch_sim": "简体中文",
        "ch_tra": "繁體中文",
        "en": "English",
        "ja": "日本語",
        "ko": "한국어",
    }

    # ONNX config for Pix2Text — per context7-verified API (2026-08)
    _ONNX_CONFIG = {
        "languages": ("en", "ch_sim"),
        "mfd": {"model_name": "mfd-pro-1.5", "model_backend": "onnx"},
        "formula": {"model_name": "mfr-pro-1.5", "model_backend": "onnx"},
        "text": {"rec_model_name": "doc-densenet_lite_666-gru_large"},
    }

    # ── system prompts for LLM structuring ─────────────────────────────

    _STRUCTURE_SYSTEM_PROMPT = """你是 AceExam 题目结构化助手。根据OCR识别的题目照片文本，输出标准化的题目JSON。

输出必须是严格的JSON对象，格式如下：
{
  "type": "single",       // single | multi | blank | essay
  "content": "题目题干（保留LaTeX公式：$...$）",
  "options": {"A": "...", "B": "...", "C": "...", "D": "..."},  // 选择题必填，填空/简答填 null
  "answer": {"correct": "A"},  // 选择题={"correct":"A"}，填空题="精确答案"，简答题={"key_points":["..."]}
  "analysis": "解题步骤/解析（如果OCR文本包含了）",
  "confidence": 0.85    // 你对结构化结果的确信度 [0, 1]
}

规则：
1. 仅从OCR文本提取信息，不要编造OCR没有的内容
2. 如果OCR文本不完整或模糊，confidence调低(<0.6)并标注
3. 公式必须用LaTeX $...$ 或 $$...$$ 包裹
4. 如果选项解析不出来，options 填 null
5. 如果答案解析不出来，answer 填 null
"""

    _KP_SYSTEM_PROMPT = """你是 AceExam 知识点匹配助手。根据题目内容，推荐最相关的知识点。

输入包含：
- 题目文本
- 可选的知识点列表：{knowledge_points_list}

输出必须是严格的JSON数组，最多3个推荐：
[
  {{"name": "洛必达法则", "score": 0.92}},
  {{"name": "极限计算", "score": 0.65}}
]

如果输入中提供了知识点列表，从中选择匹配的；如果没有提供列表，根据题目内容推断合理的知识点名称。
按 match score 降序排列，score ∈ [0, 1]。
"""

    def __init__(
        self,
        lang: str = "ch_sim",
        enable_formula: bool = True,
        gateway: LLMGateway | None = None,
    ) -> None:
        self._lang = lang
        self._enable_formula = enable_formula
        self._gateway = gateway or llm_gateway
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

    async def structure_question(
        self,
        ocr_result: OCRResult,
        subject_name: str = "",
    ) -> StructuredQuestion:
        """Convert raw OCR text into a structured question JSON via LLM (flash).

        Args:
            ocr_result: the raw OCR output
            subject_name: optional subject name for context

        Returns:
            StructuredQuestion with parsed fields, or defaults on failure
        """
        if not ocr_result.success or not ocr_result.raw_markdown.strip():
            return StructuredQuestion(
                confidence=0.0,
                raw_ocr_text=ocr_result.raw_markdown,
            )

        raw = ocr_result.raw_markdown
        user_prompt = f"OCR识别文本：\n{raw}\n\n科目：{subject_name or '未知'}\n请输出结构化题目JSON。"
        messages = [
            {"role": "system", "content": self._STRUCTURE_SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ]

        for attempt in range(3):
            try:
                result = await self._gateway.chat("flash", messages, temperature=0.2)
                content = result.get("content", "")
                parsed = self._parse_structure_json(content)
                if parsed:
                    return StructuredQuestion(
                        type=parsed.get("type", "single"),
                        content=parsed.get("content", raw),
                        options=parsed.get("options"),
                        answer=parsed.get("answer"),
                        analysis=parsed.get("analysis", ""),
                        confidence=float(parsed.get("confidence", 0.7)),
                        raw_ocr_text=raw,
                    )
            except Exception as exc:
                logger.warning("structure_question attempt %d failed: %s", attempt + 1, exc)

            # Retry with hint
            if attempt < 2:
                messages.append(
                    {"role": "user", "content": "请确保输出严格的JSON格式，confidence要真实评估。"}
                )

        # Fallback: return raw text as content
        logger.warning("structure_question: all attempts failed, returning raw text")
        return StructuredQuestion(
            type="single",
            content=raw,
            confidence=0.3,
            raw_ocr_text=raw,
        )

    async def suggest_knowledge_points(
        self,
        question_text: str,
        knowledge_points: list[dict] | None = None,
        top_k: int = 3,
    ) -> list[KnowledgePointSuggestion]:
        """Suggest knowledge points for a question via LLM (flash).

        Args:
            question_text: the question content (or OCR raw text)
            knowledge_points: optional list of known KPs [{id, name}, ...]
            top_k: max number of suggestions

        Returns:
            list of KnowledgePointSuggestion sorted by score descending
        """
        if not question_text.strip():
            return []

        # Build KP list for prompt
        kp_list_str = "无预定义知识点列表，请根据题目内容推断。"
        kp_map: dict[str, dict] = {}
        if knowledge_points:
            kp_lines = []
            for kp in knowledge_points:
                kp_id = kp.get("id", "")
                kp_name = kp.get("name", "")
                kp_lines.append(f"  - id={kp_id}, name={kp_name}")
                if kp_name:
                    kp_map[kp_name] = kp
            if kp_lines:
                kp_list_str = "\n".join(kp_lines)

        system_prompt = self._KP_SYSTEM_PROMPT.format(knowledge_points_list=kp_list_str)
        user_prompt = f"题目内容：\n{question_text[:1500]}\n\n请推荐最相关的知识点。"
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        try:
            result = await self._gateway.chat("flash", messages, temperature=0.2)
            content = result.get("content", "")
            parsed = self._parse_structure_json(content)
        except Exception as exc:
            logger.warning("suggest_knowledge_points LLM call failed: %s", exc)
            return []

        if not parsed or not isinstance(parsed, list):
            return []

        suggestions: list[KnowledgePointSuggestion] = []
        for item in parsed[:top_k]:
            name = item.get("name", "")
            kp_id = ""
            if kp_map and name in kp_map:
                kp_id = kp_map[name].get("id", "")
            suggestions.append(
                KnowledgePointSuggestion(
                    id=kp_id,
                    name=name,
                    score=round(float(item.get("score", 0.5)), 2),
                )
            )

        # Sort by score descending
        suggestions.sort(key=lambda s: s.score, reverse=True)
        return suggestions

    async def full_pipeline(
        self,
        file_path: str | Path,
        subject_name: str = "",
        knowledge_points: list[dict] | None = None,
    ) -> dict:
        """Run the full OCR pipeline: recognize → structure → suggest KPs.

        Returns a dict suitable for the OCR upload response:
        {
            "ocr_result": OCRResult,
            "structured_question": StructuredQuestion,
            "suggested_kps": [KnowledgePointSuggestion, ...],
        }
        """
        ocr_result = await self.recognize_file(file_path)

        structured = None
        suggested_kps = None

        if ocr_result.success and ocr_result.raw_markdown.strip():
            structured = await self.structure_question(ocr_result, subject_name=subject_name)
            question_text = structured.content or ocr_result.raw_markdown
            suggested_kps = await self.suggest_knowledge_points(
                question_text, knowledge_points=knowledge_points
            )

        return {
            "ocr_result": ocr_result,
            "structured_question": structured,
            "suggested_kps": suggested_kps or [],
        }

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

        # Confidence heuristic based on output richness
        if len(raw) > 100:
            confidence = 0.85
        elif len(raw) > 10:
            confidence = 0.65
        else:
            confidence = 0.4

        return OCRResult(
            success=True,
            raw_markdown=raw,
            text_only=text_only,
            formulas=formulas,
            confidence=round(confidence, 2),
        )

    def _init_p2t(self):
        """Blocking init with ONNX backend — called in a thread.

        Per context7-verified API (breezedeus/pix2text, 2026-08):
        Pix2Text.from_config() accepts total_configs for model backend selection.
        ONNX backend is used for mfd (formula detection) and mfr (formula recognition)
        to keep zero API cost.
        """
        from pix2text import Pix2Text

        try:
            return Pix2Text.from_config(total_configs=self._ONNX_CONFIG)
        except Exception:
            logger.warning(
                "Pix2Text ONNX init failed — falling back to default config.\n"
                "This may use PyTorch backend instead of ONNX."
            )
            return Pix2Text.from_config()

    @staticmethod
    def _parse_structure_json(content: str) -> dict | list | None:
        """Robust JSON extraction from LLM output (may contain markdown fences)."""
        if not content:
            return None

        text = content.strip()
        # Strip markdown code fences
        if text.startswith("```"):
            lines = text.split("\n")
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].startswith("```"):
                lines = lines[:-1]
            text = "\n".join(lines)

        try:
            return json.loads(text)
        except json.JSONDecodeError:
            # Try to find JSON object or array
            m = re.search(r"(\[.*\]|\{.*\})", content, re.DOTALL)
            if m:
                try:
                    return json.loads(m.group(1))
                except json.JSONDecodeError:
                    pass
        return None


# ── module-level convenience ──

ocr_service = OCRService()
