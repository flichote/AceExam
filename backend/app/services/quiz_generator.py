"""AI Quiz Generator — generate practice questions targeting weak knowledge points.

Tier routing (per PRD):
  - Simple questions (single/multi choice, fill-blank) → flash (cheap/fast)
  - Complex questions (essay, proof, calculation) → pro (deep reasoning)
"""

import json
import logging

from app.services.llm_gateway import LLMGateway, llm_gateway

logger = logging.getLogger(__name__)

# ── Output structures ──────────────────────────────────────────────────────

from dataclasses import dataclass, field


@dataclass
class GeneratedQuiz:
    """A batch of generated practice questions targeting weak areas."""

    subject: str = ""  # subject name
    knowledge_points: list[str] = field(default_factory=list)
    questions: list[dict] = field(default_factory=list)
    token_usage: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "subject": self.subject,
            "knowledge_points": self.knowledge_points,
            "questions": self.questions,
            "token_usage": self.token_usage,
        }


# ── Prompt templates ───────────────────────────────────────────────────────

_QUIZ_SYSTEM_PROMPT = """你是 AceExam 智能出题助手。根据用户提供的薄弱知识点列表，生成针对性练习题。

输出必须是严格的 JSON 数组，每条题目一个对象，格式如下：
[
  {
    "type": "single",           // single | multi | blank | essay
    "content": "题目内容（可用 LaTeX: $公式$）",
    "options": {"A": "...", "B": "...", "C": "...", "D": "..."},  // 选择题必填，填空/简答可为 null
    "answer": {"correct": "A"},  // 选择题填选项，填空题填 exact 答案，简答填要点
    "analysis": "详细解析，说明解题思路和易错点",
    "difficulty": 3,            // 1-5
    "knowledge_point": "关联的知识点名称"
  }
]

要求：
- 题目难度应与薄弱知识点的掌握程度成反比（弱点多出基础题逐步提高）
- 选择题提供 4 个选项，仅 1 个正确
- 解析要详细，指出易错点
- 如果知识点列表很长，聚焦最薄弱的 3-5 个点出题
- 总共生成 3-5 道题目
"""

_SIMPLE_QUIZ_PROMPT = """生成 {n} 道选择题和填空题，难度 1-3，覆盖以下薄弱知识点：
{weak_points}

用户已掌握的基础知识不需要重复考，重点考察薄弱环节。"""

_COMPLEX_QUIZ_PROMPT = """生成 {n} 道综合题（含简答/证明/计算），难度 3-5，覆盖以下薄弱知识点：
{weak_points}

题目要有区分度，综合考察多个知识点的关联能力。"""


# ── Generator ──────────────────────────────────────────────────────────────


class QuizGenerator:
    """Generate practice questions via LLM with flash/pro routing."""

    _MAX_RETRIES = 2

    def __init__(self, gateway: LLMGateway | None = None) -> None:
        self._gateway = gateway or llm_gateway

    async def generate(
        self,
        weak_knowledge_points: list[dict],
        subject: str = "",
        count: int = 5,
        difficulty_range: tuple[int, int] = (1, 5),
    ) -> GeneratedQuiz:
        """Generate practice questions targeting weak knowledge points.

        Args:
            weak_knowledge_points: list of {name, mastery_level, error_rate, ...}
            subject: subject name for context
            count: target number of questions (actual may vary)
            difficulty_range: (min, max) difficulty to target

        Returns:
            GeneratedQuiz with questions array
        """
        kp_names = [kp.get("name", str(kp)) for kp in weak_knowledge_points]

        # Determine tier: high difficulty or essay-type → pro
        is_complex = difficulty_range[1] >= 4 or any(
            kp.get("error_rate", 0) > 0.5 for kp in weak_knowledge_points
        )
        tier = self._gateway.route_tier(
            require_depth=is_complex,
            difficulty=difficulty_range[1],
            question_type="essay" if is_complex else "single",
        )

        # Build prompt
        kp_list = "\n".join(f"- {n}" for n in kp_names[:5])

        if is_complex:
            prompt = _COMPLEX_QUIZ_PROMPT.format(
                n=min(count, 5), weak_points=kp_list
            )
        else:
            prompt = _SIMPLE_QUIZ_PROMPT.format(
                n=min(count, 5), weak_points=kp_list
            )

        if subject:
            prompt = f"科目：{subject}\n{prompt}"

        messages = [
            {"role": "system", "content": _QUIZ_SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ]

        # Call LLM with retry for JSON parsing
        questions: list[dict] = []
        token_usage: dict = {}

        for attempt in range(self._MAX_RETRIES + 1):
            result = await self._gateway.chat(tier, messages, temperature=0.5)
            content = result.get("content", "")
            token_usage = result.get("usage", {})

            questions = self._parse_questions(content)
            if questions:
                break
            logger.warning(
                "quiz_generator: JSON parse failed on attempt %d, retrying...",
                attempt + 1,
            )
            # Add hint for next attempt
            messages.append(
                {"role": "user", "content": "请确保输出是严格的 JSON 数组格式。"}
            )

        # Enrich each question with default values
        enriched = []
        for q in questions:
            enriched.append(
                {
                    "type": q.get("type", "single"),
                    "content": q.get("content", ""),
                    "options": q.get("options"),
                    "answer": q.get("answer", {}),
                    "analysis": q.get("analysis", ""),
                    "difficulty": max(1, min(5, q.get("difficulty", 3))),
                    "knowledge_point": q.get("knowledge_point", ""),
                }
            )

        return GeneratedQuiz(
            subject=subject,
            knowledge_points=kp_names,
            questions=enriched,
            token_usage=token_usage,
        )

    # ── JSON parser ────────────────────────────────────────────────────

    @staticmethod
    def _parse_questions(content: str) -> list[dict]:
        """Robust JSON extraction from LLM output (may contain markdown fences)."""
        if not content:
            return []

        # Strip markdown code fences
        text = content.strip()
        if text.startswith("```"):
            lines = text.split("\n")
            # Drop opening fence line
            if lines[0].startswith("```"):
                lines = lines[1:]
            # Drop closing fence line
            if lines and lines[-1].startswith("```"):
                lines = lines[:-1]
            text = "\n".join(lines)

        try:
            parsed = json.loads(text)
        except json.JSONDecodeError:
            # Try to find a JSON array anywhere in the response
            import re

            m = re.search(r"\[\s*\{.*?\}\s*\]", content, re.DOTALL)
            if m:
                try:
                    parsed = json.loads(m.group(0))
                except json.JSONDecodeError:
                    return []
            else:
                return []

        if isinstance(parsed, list):
            return parsed
        if isinstance(parsed, dict):
            return [parsed]
        return []


# ── module-level convenience ──

quiz_generator = QuizGenerator()
