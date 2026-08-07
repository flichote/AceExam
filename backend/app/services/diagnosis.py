"""Weakness diagnosis engine — analyze answer records to produce a weakness map.

Workflow:
  1. Collect recent wrong answers + UserKnowledgeState records
  2. Send to LLM with structured prompt
  3. Parse LLM output into a weakness map JSON

The weakness map feeds into the adaptive quiz generator and study plan.
"""

import json
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime

from app.services.llm_gateway import LLMGateway, llm_gateway

logger = logging.getLogger(__name__)

# ── Output structures ──────────────────────────────────────────────────────


@dataclass
class WeaknessItem:
    """A single weak point entry."""

    knowledge_point_id: str = ""
    knowledge_point_name: str = ""
    mastery_level: float = 0.0  # estimated 0-1, lower = weaker
    error_rate: float = 0.0  # wrong / total for this KP
    common_mistake_pattern: str = ""  # e.g. "符号错误", "概念混淆"
    suggested_focus: str = ""  # what to study next


@dataclass
class WeaknessMap:
    """Complete weakness analysis for a user + subject."""

    user_id: str = ""
    subject_id: str = ""
    subject_name: str = ""
    generated_at: str = ""
    overall_mastery: float = 0.0  # 0-1 aggregated
    weak_points: list[WeaknessItem] = field(default_factory=list)
    strengths: list[str] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)
    raw_analysis: str = ""
    token_usage: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "user_id": self.user_id,
            "subject_id": self.subject_id,
            "subject_name": self.subject_name,
            "generated_at": self.generated_at,
            "overall_mastery": self.overall_mastery,
            "weak_points": [
                {
                    "knowledge_point_id": w.knowledge_point_id,
                    "knowledge_point_name": w.knowledge_point_name,
                    "mastery_level": w.mastery_level,
                    "error_rate": w.error_rate,
                    "common_mistake_pattern": w.common_mistake_pattern,
                    "suggested_focus": w.suggested_focus,
                }
                for w in self.weak_points
            ],
            "strengths": self.strengths,
            "recommendations": self.recommendations,
        }


# ── Prompt template ────────────────────────────────────────────────────────

_DIAGNOSIS_SYSTEM_PROMPT = """你是 AceExam 学习诊断专家。根据用户的做题记录，分析薄弱知识点并输出诊断地图。

输出必须是严格的 JSON，格式如下：
{
  "overall_mastery": 0.65,
  "weak_points": [
    {
      "knowledge_point_name": "拉格朗日中值定理",
      "mastery_level": 0.3,
      "error_rate": 0.75,
      "common_mistake_pattern": "混淆中值定理的适用条件",
      "suggested_focus": "重新理解定理的假设条件，练习判断题目适用哪个中值定理"
    }
  ],
  "strengths": ["极限计算", "连续函数性质"],
  "recommendations": [
    "优先复习拉格朗日中值定理，这是后续积分中值定理的基础",
    "考试前集中练习中值定理的综合应用题"
  ]
}

要求：
- 不给建议时不要编造 — 只基于数据说话
- mastery_level ∈ [0, 1]，0 表示完全不会，1 表示完全掌握
- 推荐清单按优先级降序排列
- 用中文输出"""


# ── Engine ─────────────────────────────────────────────────────────────────


class DiagnosisEngine:
    """Analyze answer history → weakness map via LLM."""

    _MAX_RETRIES = 2

    def __init__(self, gateway: LLMGateway | None = None) -> None:
        self._gateway = gateway or llm_gateway

    async def diagnose(
        self,
        user_id: uuid.UUID | str,
        subject_id: uuid.UUID | str,
        subject_name: str = "",
        knowledge_states: list[dict] | None = None,
        recent_errors: list[dict] | None = None,
    ) -> WeaknessMap:
        """Run full diagnosis on a user's study history.

        Args:
            user_id: the user
            subject_id: the subject scope
            subject_name: human-readable name
            knowledge_states: list of UserKnowledgeState-like dicts
            recent_errors: list of recent WrongAnswer records

        Returns:
            WeaknessMap with prioritized weak points and recommendations
        """
        # ── 1. Build data summary ──
        data_summary = self._build_summary(knowledge_states, recent_errors)

        if not data_summary:
            # No data → return empty map
            return WeaknessMap(
                user_id=str(user_id),
                subject_id=str(subject_id),
                subject_name=subject_name,
                generated_at=datetime.now().isoformat(),
                overall_mastery=0.5,
                recommendations=["暂无做题记录，建议先完成自测以生成诊断报告。"],
            )

        # ── 2. LLM analysis ──
        user_prompt = (
            f"科目：{subject_name or '未知科目'}\n"
            f"知识点掌握状态与错题记录：\n{data_summary}\n\n"
            f"请分析薄弱知识点，输出 JSON 诊断地图。"
        )
        messages = [
            {"role": "system", "content": _DIAGNOSIS_SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ]

        token_usage: dict = {}
        raw_output = ""

        for attempt in range(self._MAX_RETRIES + 1):
            result = await self._gateway.chat("flash", messages, temperature=0.3)
            raw_output = result.get("content", "")
            token_usage = result.get("usage", {})

            parsed = self._parse_diagnosis(raw_output)
            if parsed:
                return self._build_map(
                    user_id=str(user_id),
                    subject_id=str(subject_id),
                    subject_name=subject_name,
                    parsed=parsed,
                    raw=raw_output,
                    token_usage=token_usage,
                )

            logger.warning(
                "diagnosis: JSON parse failed on attempt %d", attempt + 1
            )
            messages.append(
                {"role": "user", "content": "请确保输出是严格的 JSON 格式。"}
            )

        # Fallback: return raw output as analysis text
        return WeaknessMap(
            user_id=str(user_id),
            subject_id=str(subject_id),
            subject_name=subject_name,
            generated_at=datetime.now().isoformat(),
            raw_analysis=raw_output or "无法解析诊断结果",
            token_usage=token_usage,
        )

    # ── helpers ────────────────────────────────────────────────────────

    @staticmethod
    def _build_summary(
        states: list[dict] | None,
        errors: list[dict] | None,
    ) -> str:
        """Build a text summary of knowledge states and errors."""
        lines: list[str] = []

        if states:
            lines.append("【知识点掌握状态】")
            for s in states:
                name = s.get("knowledge_point_name", s.get("name", "未知"))
                status = s.get("status", "unknown")
                correct = s.get("correct_count", 0)
                wrong = s.get("wrong_count", 0)
                total = correct + wrong
                rate = f"{wrong}/{total} 错误" if total > 0 else "无数据"
                lines.append(f"  - {name}: 状态={status}, {rate}")

        if errors:
            lines.append("【近期错题】")
            for e in errors[:10]:  # cap at 10 to avoid huge prompts
                q_content = e.get("question_content", e.get("content", "?"))[:100]
                wrong_ans = e.get("wrong_answer", "?")
                reason = e.get("wrong_reason", "")
                lines.append(f"  - 题目: {q_content}")
                lines.append(f"    错误答案: {wrong_ans}")
                if reason:
                    lines.append(f"    错误原因: {reason}")

        return "\n".join(lines)

    @staticmethod
    def _parse_diagnosis(content: str) -> dict | None:
        """Parse LLM output into a diagnosis dict."""
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

        try:
            return json.loads(text)
        except json.JSONDecodeError:
            # Try to find JSON object anywhere
            import re

            m = re.search(r"\{.*\}", content, re.DOTALL)
            if m:
                try:
                    return json.loads(m.group(0))
                except json.JSONDecodeError:
                    pass
            return None

    @staticmethod
    def _build_map(
        user_id: str,
        subject_id: str,
        subject_name: str,
        parsed: dict,
        raw: str,
        token_usage: dict,
    ) -> WeaknessMap:
        """Convert parsed JSON into WeaknessMap."""
        weak_points = []
        for wp in parsed.get("weak_points", []):
            weak_points.append(
                WeaknessItem(
                    knowledge_point_name=wp.get("knowledge_point_name", ""),
                    mastery_level=float(wp.get("mastery_level", 0.5)),
                    error_rate=float(wp.get("error_rate", 0.0)),
                    common_mistake_pattern=wp.get("common_mistake_pattern", ""),
                    suggested_focus=wp.get("suggested_focus", ""),
                )
            )

        # Sort weak points: lowest mastery first
        weak_points.sort(key=lambda w: w.mastery_level)

        return WeaknessMap(
            user_id=user_id,
            subject_id=subject_id,
            subject_name=subject_name,
            generated_at=datetime.now().isoformat(),
            overall_mastery=float(parsed.get("overall_mastery", 0.5)),
            weak_points=weak_points,
            strengths=parsed.get("strengths", []),
            recommendations=parsed.get("recommendations", []),
            raw_analysis=raw,
            token_usage=token_usage,
        )


# ── module-level convenience ──

diagnosis_engine = DiagnosisEngine()
