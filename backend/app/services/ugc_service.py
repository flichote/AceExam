"""UGC (User-Generated Content) question parsing service.

Handles student-submitted questions: text-based or image-based input →
structured question JSON with knowledge point attribution.
Reuses the existing OCR pipeline (Pix2Text + LLM structuring) and LLM Gateway.

Per architecture.md §12.2:
  - /questions/ugc → pending (gate) → admin review → active/rejected
  - source=ugc annotation
  - Pre-check rules guard against empty/spam/inappropriate content
  - Auto-approve for trusted contributors (configurable threshold)

Workflow:
  1. Input validation (text not empty / image readable)
  2. If image → OCR pipeline (OCRService)
  3. If text → LLM structuring directly
  4. Pre-check rules
  5. Knowledge point suggestion
  6. Return structured result with source=ugc
"""

import logging
import re
from dataclasses import dataclass, field
from typing import Optional

from app.services.llm_gateway import LLMGateway, llm_gateway
from app.services.ocr_service import OCRService, ocr_service

logger = logging.getLogger(__name__)

# ── Constants ─────────────────────────────────────────────────────────────

# Pre-check: minimum content length to be considered a valid question
MIN_CONTENT_LENGTH = 8
MAX_CONTENT_LENGTH = 5000
# Auto-approve threshold (UGC task body: ≥5 approved + ≥90% approval rate)
AUTO_APPROVE_MIN_APPROVED = 5
AUTO_APPROVE_MIN_RATE = 0.90

# Blacklist patterns (spam / inappropriate)
_SPAM_PATTERNS = [
    re.compile(r"(加微信|扫码|关注公众号|添加好友)", re.IGNORECASE),
    re.compile(r"(代考|替考|作弊|答案购买)", re.IGNORECASE),
    re.compile(r"(http[s]?://|www\.)", re.IGNORECASE),
]
# Minimum meaningful Chinese/English characters for a question
_MIN_MEANINGFUL_CHARS = 4


# ── Output structures ─────────────────────────────────────────────────────


@dataclass
class UGCParseResult:
    """Result of parsing a UGC question submission."""

    success: bool
    source: str = "ugc"
    type: str = ""                       # single | multi | blank | essay
    content: str = ""                    # question stem
    options: dict[str, str] | None = None
    answer: dict | str | None = None
    analysis: str = ""
    confidence: float = 0.0              # overall parse confidence [0,1]
    suggested_kps: list[dict] = field(default_factory=list)
    precheck_passed: bool = False
    precheck_issues: list[str] = field(default_factory=list)
    auto_approved: bool = False
    error: str | None = None


@dataclass
class UGCInput:
    """Student-submitted UGC question input."""

    text_content: str = ""
    image_data: bytes | None = None
    image_filename: str = "upload.jpg"
    subject_name: str = ""
    is_trusted_contributor: bool = False
    contributor_stats: dict | None = None
    # contributor_stats shape: {"total_approved": int, "total_submitted": int}


@dataclass
class UGCStats:
    """Aggregated UGC contributor stats for auto-approve threshold check."""

    total_approved: int = 0
    total_submitted: int = 0

    @property
    def approval_rate(self) -> float:
        if self.total_submitted == 0:
            return 0.0
        return self.total_approved / self.total_submitted

    @property
    def qualifies_for_auto_approve(self) -> bool:
        return (
            self.total_approved >= AUTO_APPROVE_MIN_APPROVED
            and self.approval_rate >= AUTO_APPROVE_MIN_RATE
        )


# ── UGC parse system prompt ───────────────────────────────────────────────

_UGC_STRUCTURE_PROMPT = """你是 AceExam UGC 题目解析助手。学生提交了一段题目文本，你需要将其结构化。

输出必须是严格的JSON对象：
{
  "type": "single",         // single | multi | blank | essay
  "content": "题目题干（保留原格式，数学公式用 $...$ 包裹）",
  "options": {"A": "...", "B": "...", "C": "...", "D": "..."},  // 无选项填 null
  "answer": {"correct": "A"},  // 或填空 = "精确答案"，简答 = {"key_points":["..."]}，无法确定填 null
  "analysis": "解析/解题步骤（如果输入中有）",
  "confidence": 0.85    // 确信度 [0,1]，如果题目不完整或模糊则降低
}

规则：
1. 严格从输入文本提取，不编造
2. 如果输入不像一道题（闲聊/广告/不完整），type="" 且 confidence < 0.3
3. 公式用 $...$ 包裹
4. 文本是出题者写的，你在结构化，不是在做题
"""

_UGC_KP_PROMPT = """你是 AceExam 知识点匹配助手。根据题目内容，推荐知识点。

输出 JSON 数组，最多 3 个：
[
  {"name": "洛必达法则", "score": 0.92},
  {"name": "极限计算", "score": 0.65}
]
按 score 降序。score ∈ [0,1]。
"""


# ── Pre-check logic ───────────────────────────────────────────────────────


def run_precheck(text: str) -> tuple[bool, list[str]]:
    """Run validation rules against UGC question text.

    Args:
        text: the question stem / OCR result text

    Returns:
        (passed, issues) — passed is True if all checks pass
    """
    issues: list[str] = []
    stripped = text.strip()

    if not stripped:
        issues.append("content_empty: 题目内容为空")
        return False, issues

    if len(stripped) < MIN_CONTENT_LENGTH:
        issues.append(f"content_too_short: 题目内容过短（{len(stripped)} < {MIN_CONTENT_LENGTH} 字符）")

    if len(stripped) > MAX_CONTENT_LENGTH:
        issues.append(f"content_too_long: 题目内容过长（{len(stripped)} > {MAX_CONTENT_LENGTH} 字符）")

    # Check for spam/inappropriate patterns
    for pattern in _SPAM_PATTERNS:
        if pattern.search(stripped):
            issues.append(f"spam_pattern: 匹配到敏感模式 '{pattern.pattern}'")

    # Minimum meaningful characters (exclude whitespace, punctuation, math)
    meaningful = re.sub(r"[\s\d()\[\]{}，。；：""''！？、…—+*/=<>^-]", "", stripped)
    if len(meaningful) < _MIN_MEANINGFUL_CHARS:
        issues.append(f"low_meaningful_chars: 有效字符过少（{len(meaningful)} < {_MIN_MEANINGFUL_CHARS}）")

    return len(issues) == 0, issues


# ── UGCParserService ──────────────────────────────────────────────────────


class UGCParserService:
    """Parse student-submitted UGC questions into structured format.

    Reuses OCRService for image-based input and LLMGateway for text parsing.

    Usage::

        ugc = UGCParserService()
        result = await ugc.parse(UGGInput(text_content="求极限 lim(x→0) sin(x)/x"))
    """

    def __init__(
        self,
        ocr: OCRService | None = None,
        gateway: LLMGateway | None = None,
    ) -> None:
        self._ocr = ocr or ocr_service
        self._gateway = gateway or llm_gateway

    # ── public API ────────────────────────────────────────────────────────

    async def parse(self, ugc_input: UGCInput) -> UGCParseResult:
        """Main entry: parse a UGC input into a structured question.

        Args:
            ugc_input: the student's submission (text or image)

        Returns:
            UGCParseResult with structured fields + precheck status
        """
        # Step 1: get question text (OCR if image, direct if text)
        question_text = ""
        ocr_confidence = 0.0

        if ugc_input.image_data is not None and len(ugc_input.image_data) > 0:
            # Image-based → OCR pipeline
            ocr_result = await self._ocr.recognize_bytes(
                data=ugc_input.image_data,
                filename=ugc_input.image_filename,
            )
            if not ocr_result.success:
                return UGCParseResult(
                    success=False,
                    error=f"OCR 识别失败: {ocr_result.error}",
                    precheck_passed=False,
                    precheck_issues=["ocr_failed"],
                )
            question_text = ocr_result.raw_markdown or ocr_result.text_only
            ocr_confidence = ocr_result.confidence
        else:
            # Text-based input
            question_text = ugc_input.text_content.strip()

        if not question_text:
            return UGCParseResult(
                success=False,
                error="题目内容为空",
                precheck_passed=False,
                precheck_issues=["content_empty"],
            )

        # Step 2: pre-check
        passed, issues = run_precheck(question_text)
        if not passed:
            return UGCParseResult(
                success=False,
                content=question_text,
                precheck_passed=False,
                precheck_issues=issues,
                error="precheck_failed: " + "; ".join(issues),
                confidence=0.0,
            )

        # Step 3: LLM structuring
        structured = await self._structure_ugc_question(
            text=question_text,
            subject_name=ugc_input.subject_name,
        )

        # Step 4: knowledge point suggestion
        suggested_kps = await self._suggest_kps(
            text=structured.get("content", question_text),
        )

        # Step 5: auto-approve check
        auto_approved = False
        if ugc_input.contributor_stats:
            stats = UGCStats(
                total_approved=ugc_input.contributor_stats.get("total_approved", 0),
                total_submitted=ugc_input.contributor_stats.get("total_submitted", 0),
            )
            if stats.qualifies_for_auto_approve and structured.get("confidence", 0) >= 0.6:
                auto_approved = True

        return UGCParseResult(
            success=True,
            source="ugc",
            type=structured.get("type", "single"),
            content=structured.get("content", question_text),
            options=structured.get("options"),
            answer=structured.get("answer"),
            analysis=structured.get("analysis", ""),
            confidence=max(
                float(structured.get("confidence", 0.5)),
                ocr_confidence,
            ),
            suggested_kps=suggested_kps,
            precheck_passed=True,
            auto_approved=auto_approved,
        )

    async def precheck_only(self, text: str) -> tuple[bool, list[str]]:
        """Run pre-check rules only, without full parsing.

        Useful when the frontend wants quick validation before submission.
        """
        return run_precheck(text)

    # ── internal ───────────────────────────────────────────────────────────

    async def _structure_ugc_question(
        self,
        text: str,
        subject_name: str = "",
    ) -> dict:
        """Use LLM to structure raw UGC text into a question JSON."""
        user_prompt = f"学生提交的题目文本：\n{text[:3000]}\n\n科目：{subject_name or '未知'}\n请输出结构化JSON。"
        messages = [
            {"role": "system", "content": _UGC_STRUCTURE_PROMPT},
            {"role": "user", "content": user_prompt},
        ]

        # Try up to 2 attempts
        for attempt in range(2):
            try:
                llm_result = await self._gateway.chat(
                    "flash", messages, temperature=0.2, max_tokens=1024,
                )
                content = llm_result.get("content", "")
                parsed = self._parse_json(content)
                if parsed and isinstance(parsed, dict):
                    return parsed
            except Exception as exc:
                logger.warning(
                    "UGC structure attempt %d failed: %s", attempt + 1, exc
                )
            if attempt < 1:
                messages.append(
                    {"role": "user", "content": "请输出严格的JSON格式。"}
                )

        # Fallback
        logger.warning("UGC structure: all attempts failed")
        return {
            "type": "single",
            "content": text,
            "confidence": 0.3,
        }

    async def _suggest_kps(self, text: str) -> list[dict]:
        """Use LLM to suggest knowledge points for a UGC question."""
        if not text.strip():
            return []

        messages = [
            {"role": "system", "content": _UGC_KP_PROMPT},
            {"role": "user", "content": f"题目内容：\n{text[:1500]}\n请推荐知识点。"},
        ]

        try:
            llm_result = await self._gateway.chat(
                "flash", messages, temperature=0.2, max_tokens=256,
            )
            content = llm_result.get("content", "")
            parsed = self._parse_json(content)
            if isinstance(parsed, list):
                return [dict(item) for item in parsed[:3] if isinstance(item, dict)]
        except Exception as exc:
            logger.warning("UGC KP suggestion failed: %s", exc)

        return []

    @staticmethod
    def _parse_json(content: str) -> dict | list | None:
        """Robust JSON extraction from LLM output."""
        if not content:
            return None

        text = content.strip()
        # Strip markdown fences
        if text.startswith("```"):
            lines = text.split("\n")
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].startswith("```"):
                lines = lines[:-1]
            text = "\n".join(lines)

        import json
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            m = re.search(r"(\[.*\]|\{.*\})", content, re.DOTALL)
            if m:
                try:
                    return json.loads(m.group(1))
                except json.JSONDecodeError:
                    pass
        return None


# ── module-level convenience ──────────────────────────────────────────────

ugc_parser = UGCParserService()
