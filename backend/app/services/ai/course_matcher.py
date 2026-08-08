"""Course matcher — school course name → template course candidates (M5 T31).

Strategy:
  1. Alias exact match (source='alias', confidence=1.0)
  2. AI semantic match via DeepSeek flash (source='ai')

Output contract per api.md §14.2:
  {"candidates": [{"template_subject_id", "name", "code", "confidence", "reason", "source"}], "strategy": "alias"|"ai"}
"""

import json
import logging
import re
from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import CourseAlias, Subject
from app.services.llm_gateway import LLMGateway, llm_gateway

logger = logging.getLogger(__name__)

# ── Normalization ────────────────────────────────────────────────────────────

_NORMALIZE_RE = re.compile(r"[\\(（].*?[\\)）]|\s|\d{4}春?|学期")
_WHITESPACE_RE = re.compile(r"\s+")


def normalize_course_name(name: str) -> str:
    """Normalize course name: strip brackets, semester/year, whitespace, lowercase."""
    cleaned = _NORMALIZE_RE.sub("", name)
    cleaned = _WHITESPACE_RE.sub("", cleaned)
    return cleaned.strip().lower()


# ── Output structures ────────────────────────────────────────────────────────


@dataclass
class CourseCandidate:
    """A matched template course candidate."""
    template_subject_id: str
    name: str
    code: str
    confidence: float
    reason: str
    source: str  # "alias" | "ai"


@dataclass
class CourseMatchResult:
    """Result of course matching."""
    candidates: list[CourseCandidate] = field(default_factory=list)
    strategy: str = "ai"  # "alias" | "ai"


# ── AI prompt ────────────────────────────────────────────────────────────────

_COURSE_MATCH_SYSTEM_PROMPT = """你是 AceExam 课程匹配助手。给定一个校本课程名称和一组模板课程列表，找出最匹配的模板课程。

输出必须是严格的 JSON 数组，每项包含：
{
  "template_subject_id": "模板课程的 UUID",
  "name": "模板课程名",
  "code": "模板课程 code",
  "confidence": 0.92,   // 匹配置信度 [0, 1]，越高越确定，≥0.85 为高置信
  "reason": "匹配理由（≤30字）"
}

规则：
1. 按语义相似度匹配：课程名含义相同/相近的高分，仅名称相近但不相关的低分
2. 如果名称中提到教材（如"同济第七版"），应将其视为高等数学的加分项
3. 结果按 confidence 降序排列，最多返回 5 条
4. 如果没有任何课程匹配（所有候选置信度均 <0.5），返回空数组 []
5. 输出严格 JSON，不要包含 markdown 代码块标记
"""


# ── CourseMatcherService ─────────────────────────────────────────────────────


class CourseMatcherService:
    """Match school-local course names to template subjects.

    Usage::

        matcher = CourseMatcherService()
        result = await matcher.match(db_session, normalized_name="高等数学a")
    """

    def __init__(self, gateway: LLMGateway | None = None) -> None:
        self._gateway = gateway or llm_gateway

    async def match(
        self,
        db: AsyncSession,
        name: str,
        school: str = "",
        textbook: str = "",
        limit: int = 5,
    ) -> CourseMatchResult:
        """Match a school course name to template subjects.

        Args:
            db: Database session for alias / subject queries.
            name: Raw course name from user input.
            school: Optional school name for context.
            textbook: Optional textbook reference for matching hints.
            limit: Max candidates to return (default 5, max 10).

        Returns:
            CourseMatchResult with candidates and strategy.
        """
        normalized = normalize_course_name(name)
        limit = max(1, min(limit, 10))

        # Strategy 1: alias exact match
        alias_result = await self._alias_lookup(db, normalized)
        if alias_result is not None:
            return alias_result

        # Strategy 2: AI semantic match
        template_subjects = await self._load_template_subjects(db)
        return await self._ai_match(
            normalized=normalized,
            raw_name=name,
            school=school,
            textbook=textbook,
            template_subjects=template_subjects,
            limit=limit,
        )

    # ── Strategy 1: alias lookup ──────────────────────────────────────────

    async def _alias_lookup(
        self, db: AsyncSession, normalized: str
    ) -> CourseMatchResult | None:
        """Check course_aliases for an exact match (after normalization).

        Returns None if no match found, so caller falls through to AI.
        """
        stmt = (
            select(CourseAlias, Subject.name, Subject.code)
            .join(Subject, CourseAlias.template_subject_id == Subject.id)
            .where(CourseAlias.is_verified == True)
        )
        result = await db.execute(stmt)
        rows = result.all()

        for ca, subj_name, subj_code in rows:
            if normalize_course_name(ca.alias) == normalized:
                return CourseMatchResult(
                    candidates=[
                        CourseCandidate(
                            template_subject_id=str(ca.template_subject_id),
                            name=subj_name,
                            code=subj_code,
                            confidence=1.0,
                            reason=f"别名精确命中：{ca.alias}",
                            source="alias",
                        )
                    ],
                    strategy="alias",
                )

        return None

    # ── template subjects lookup ───────────────────────────────────────────

    async def _load_template_subjects(self, db: AsyncSession) -> list[dict]:
        """Load active template (public-level) subjects as the AI candidate pool."""
        stmt = (
            select(Subject.id, Subject.name, Subject.code)
            .where(Subject.is_active == True, Subject.level == "public")
            .order_by(Subject.sort_order, Subject.name)
        )
        result = await db.execute(stmt)
        return [
            {"template_subject_id": str(row[0]), "name": row[1], "code": row[2]}
            for row in result.all()
        ]

    # ── Strategy 2: AI semantic match ─────────────────────────────────────

    async def _ai_match(
        self,
        normalized: str,
        raw_name: str,
        school: str,
        textbook: str,
        template_subjects: list[dict],
        limit: int,
    ) -> CourseMatchResult:
        """Use DeepSeek flash to find best-matching template subjects.

        Falls back to empty result on any error.
        """
        if not template_subjects:
            return CourseMatchResult(candidates=[], strategy="ai")

        # Build candidate pool text
        pool_text = "\n".join(
            f"- id={s['template_subject_id']} name={s['name']} code={s['code']}"
            for s in template_subjects
        )

        context_parts = [f"校本课程名：{raw_name}（归一化：{normalized}）"]
        if school:
            context_parts.append(f"学校：{school}")
        if textbook:
            context_parts.append(f"教材：{textbook}")

        user_prompt = "\n".join(context_parts) + f"\n\n模板课程列表：\n{pool_text}\n\n请输出匹配候选 JSON 数组（最多 {limit} 条）。"

        messages = [
            {"role": "system", "content": _COURSE_MATCH_SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ]

        try:
            llm_result = await self._gateway.chat(
                "flash", messages, temperature=0.2, max_tokens=512,
            )
            content = llm_result.get("content", "")
            candidates = self._parse_candidates_json(content, limit)
            return CourseMatchResult(candidates=candidates, strategy="ai")
        except Exception as exc:
            logger.warning("course_matcher AI match failed: %s", exc)
            return CourseMatchResult(candidates=[], strategy="ai")

    # ── JSON parsing ───────────────────────────────────────────────────────

    @staticmethod
    def _parse_candidates_json(content: str, limit: int) -> list[CourseCandidate]:
        """Robustly extract candidate list from LLM output.

        Handles: plain JSON array, markdown-fenced JSON, extra text.
        """
        if not content:
            return []

        text = content.strip()

        # Strip markdown fences
        if text.startswith("```"):
            lines = text.split("\n")
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].startswith("```"):
                lines = lines[:-1]
            text = "\n".join(lines).strip()

        # Try direct parse
        items = None
        try:
            items = json.loads(text)
        except json.JSONDecodeError:
            # Extract JSON array from surrounding text
            m = re.search(r"\[.*\]", content, re.DOTALL)
            if m:
                try:
                    items = json.loads(m.group(0))
                except json.JSONDecodeError:
                    pass

        if not isinstance(items, list):
            return []

        candidates = []
        for item in items:
            if not isinstance(item, dict):
                continue
            tid = item.get("template_subject_id", "")
            confidence = float(item.get("confidence", 0))
            if confidence < 0.5:
                continue  # filter low-confidence noise
            candidates.append(
                CourseCandidate(
                    template_subject_id=str(tid),
                    name=str(item.get("name", "")),
                    code=str(item.get("code", "")),
                    confidence=min(max(confidence, 0.0), 1.0),
                    reason=str(item.get("reason", ""))[:100],
                    source="ai",
                )
            )

        # Sort by confidence descending
        candidates.sort(key=lambda c: c.confidence, reverse=True)
        return candidates[:limit]


# ── Module-level convenience singleton ───────────────────────────────────────

course_matcher = CourseMatcherService()
