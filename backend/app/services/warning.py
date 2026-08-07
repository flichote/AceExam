"""Warning service -- risk rules + suggestion generation (M3 §11.6).

Inline implementation per T15 until T17 delivers. Architecture.md §11.6:
risk level = base(weak_count × days_left) + trend adjust ±1, clamped [low, high].
Suggestions are simple rule-generated (T17 will replace with LLM flash).
"""

import uuid
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import (
    KnowledgePoint,
    Plan,
    StudySession,
    UserKnowledgeState,
)


async def get_warnings(
    db: AsyncSession,
    user_id: uuid.UUID,
    subject_id: uuid.UUID | None = None,
) -> dict:
    """Generate warnings for user's active plans."""
    today = date.today()

    # Find active plans
    plan_filter = [Plan.user_id == user_id, Plan.status == "active"]
    if subject_id:
        plan_filter.append(Plan.subject_id == subject_id)

    plan_result = await db.execute(
        select(Plan).where(*plan_filter)
    )
    plans = plan_result.scalars().all()

    if not plans:
        return {"overall_risk": None, "items": [], "generated_at": datetime.now(timezone.utc)}

    all_items: list[dict] = []
    overall_levels: list[str] = []

    for plan in plans:
        if not plan.exam_date:
            continue

        days_left = (plan.exam_date - today).days
        if days_left <= 0:
            continue

        sid = plan.subject_id

        # Get weak/consolidating KPs
        state_result = await db.execute(
            select(UserKnowledgeState, KnowledgePoint.name)
            .join(KnowledgePoint, UserKnowledgeState.knowledge_point_id == KnowledgePoint.id)
            .where(
                UserKnowledgeState.user_id == user_id,
                UserKnowledgeState.subject_id == sid,
                UserKnowledgeState.status.in_(["weak", "consolidating"]),
            )
            .order_by(UserKnowledgeState.correct_count.asc())
        )
        weak_rows = state_result.all()

        if not weak_rows:
            overall_levels.append("low")
            continue

        # Recent 7-day activity
        week_ago = today - timedelta(days=7)
        activity_result = await db.execute(
            select(
                func.coalesce(func.sum(StudySession.questions_practiced), 0),
                func.coalesce(func.sum(StudySession.correct_count), 0),
                func.coalesce(func.count(StudySession.id), 0),
            )
            .where(
                StudySession.user_id == user_id,
                StudySession.subject_id == sid,
                StudySession.session_date >= week_ago,
                StudySession.session_date <= today,
            )
        )
        activity_row = activity_result.one()
        week_questions = activity_row[0] or 0
        week_correct = activity_row[1] or 0
        week_active_days = activity_row[2] or 0

        # Trend modifiers
        trend_adjust = 0
        if week_active_days <= 4:  # 3+ inactive days
            trend_adjust = +1  # worsening
        if week_questions >= 70 and week_correct / max(week_questions, 1) >= 0.8:
            trend_adjust = -1  # improving

        # Calculate risk per KP
        for state, kp_name in weak_rows:
            total = state.correct_count + state.wrong_count
            accuracy = round(state.correct_count / total, 3) if total > 0 else 0.0

            risk = _compute_risk(accuracy, total, days_left, trend_adjust)

            # Build reasons
            reasons = []
            if accuracy < 0.4:
                reasons.append(f"正确率仅 {int(accuracy * 100)}%（练习 {total} 次）")
            elif accuracy < 0.6:
                reasons.append(f"正确率偏低 {int(accuracy * 100)}%（练习 {total} 次）")
            else:
                reasons.append(f"仍需巩固（正确率 {int(accuracy * 100)}%，练习 {total} 次）")

            reasons.append(f"距考试仅 {days_left} 天")

            if week_active_days <= 4:
                reasons.append(f"近 7 天仅做题 {week_active_days} 天")

            # Simple suggestion
            suggestion = (
                f"每天 2 道{kp_name}相关练习，重点回顾教材对应章节；"
                f"优先做真题题型"
            )

            all_items.append({
                "knowledge_point_id": str(state.knowledge_point_id),
                "knowledge_point_name": kp_name,
                "risk_level": risk,
                "reasons": reasons,
                "suggestion": suggestion,
                "days_left": days_left,
                "accuracy": accuracy,
                "practice_count": total,
            })

            overall_levels.append(risk)

    # Overall risk = max of all item risks
    risk_rank = {"high": 3, "medium": 2, "low": 1}
    overall = max(overall_levels, key=lambda r: risk_rank.get(r, 0)) if overall_levels else None

    # Sort by risk level desc
    all_items.sort(key=lambda x: risk_rank.get(x["risk_level"], 0), reverse=True)

    return {
        "overall_risk": overall,
        "items": all_items,
        "generated_at": datetime.now(timezone.utc),
    }


def _compute_risk(accuracy: float, practice_count: int, days_left: int, trend_adjust: int) -> str:
    """Compute risk level using rule from architecture §11.6."""
    # Base risk from days_left × accuracy
    if days_left <= 7:
        if accuracy < 0.4:
            base = "high"
        elif accuracy < 0.7:
            base = "medium"
        else:
            base = "low"
    elif days_left <= 14:
        if accuracy < 0.3:
            base = "high"
        elif accuracy < 0.6:
            base = "medium"
        else:
            base = "low"
    else:  # > 14 days
        if accuracy < 0.2:
            base = "high"
        elif accuracy < 0.5:
            base = "medium"
        else:
            base = "low"

    # Adjust with trend
    levels = ["low", "medium", "high"]
    base_idx = levels.index(base)
    adjusted_idx = max(0, min(len(levels) - 1, base_idx + trend_adjust))

    return levels[adjusted_idx]


# ═══════════════════════════════════════════════════════════════════════════
# AI-enhanced functions (T17)
# ═══════════════════════════════════════════════════════════════════════════

import json
import logging

from app.services.llm_gateway import llm_gateway

logger = logging.getLogger(__name__)


async def ai_analyze_warning_risk(
    weak_kps: list[dict],
    days_left: int | None,
    trend: dict,
) -> dict:
    """Use LLM (pro, JSON mode) to analyze failure risk with nuanced reasoning.

    Args:
        weak_kps: list of {kp_name, accuracy, practice_count, status}
        days_left: days until exam (None if unknown)
        trend: {active_days_7d, questions_7d, trend_direction}

    Returns:
        {overall_risk, risk_assessments: [{kp_name, risk_level, confidence, reasons}],
         urgency_summary}
    """
    if not weak_kps:
        return {
            "overall_risk": None,
            "risk_assessments": [],
            "urgency_summary": "",
        }

    system_prompt = (
        "你是一位大学课程预警分析师。请根据学生的薄弱知识点、考试倒计时和学习趋势，"
        "评估每个知识点的挂科风险等级（high/medium/low）。\n"
        "输出 JSON 格式：\n"
        '{{"risk_assessments": [{{"kp_name": "...", "risk_level": "high|medium|low", '
        '"confidence": 0.0-1.0, "reasons": ["原因1", "原因2"]}}], '
        '"overall_risk": "high|medium|low", '
        '"urgency_summary": "总体紧急程度描述"}}\n'
        "评估时考虑：正确率越低风险越高、时间越紧迫风险越高、最近学习趋势越差风险越高。"
    )

    kps_text = json.dumps(weak_kps, ensure_ascii=False, indent=2)
    trend_text = json.dumps(trend, ensure_ascii=False)
    days_info = f"距考试 {days_left} 天" if days_left else "考试日期未知"

    user_prompt = (
        f"请评估以下薄弱知识点的挂科风险：\n\n"
        f"薄弱知识点：\n{kps_text}\n\n"
        f"考试倒计时：{days_info}\n"
        f"学习趋势：{trend_text}\n\n"
        f"请以 JSON 格式输出风险评估结果。"
    )

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]

    try:
        result = await llm_gateway.chat(
            tier="pro",
            messages=messages,
            temperature=0.3,
        )
        content = result.get("content", "")
        parsed = json.loads(content)
        assessments = parsed.get("risk_assessments", [])
        for a in assessments:
            a.setdefault("confidence", 0.5)
            a.setdefault("reasons", [])

        # Compute overall as max of items (safety check)
        risk_rank = {"high": 3, "medium": 2, "low": 1}
        levels = [a.get("risk_level", "low") for a in assessments]
        overall = max(levels, key=lambda r: risk_rank.get(r, 0)) if levels else "low"

        return {
            "overall_risk": parsed.get("overall_risk", overall),
            "risk_assessments": assessments,
            "urgency_summary": parsed.get("urgency_summary", ""),
        }
    except (json.JSONDecodeError, KeyError, Exception) as e:
        logger.warning("ai_analyze_warning_risk LLM failed: %s, falling back to rules", e)
        return _rule_based_risk_analysis(weak_kps, days_left, trend)


def _rule_based_risk_analysis(
    weak_kps: list[dict], days_left: int | None, trend: dict
) -> dict:
    """Rule-based fallback risk analysis."""
    assessments = []
    levels = []

    for kp in weak_kps:
        accuracy = kp.get("accuracy", 0.0)
        dl = days_left if days_left else 999

        if accuracy < 0.3 and dl <= 14:
            risk = "high"
            reasons = [f"正确率仅{int(accuracy*100)}%，非常危险"]
        elif accuracy < 0.5 and dl <= 7:
            risk = "high"
            reasons = [f"正确率{int(accuracy*100)}%，距考试仅{dl}天"]
        elif accuracy < 0.6:
            risk = "medium"
            reasons = [f"正确率{int(accuracy*100)}%，需加强练习"]
        else:
            risk = "low"
            reasons = [f"正确率{int(accuracy*100)}%，持续巩固即可"]

        if dl <= 7:
            reasons.append(f"距考试仅{dl}天，时间紧迫")
        elif dl <= 30:
            reasons.append(f"距考试{dl}天，时间尚可")

        trend_dir = trend.get("trend_direction", "")
        if trend_dir == "declining":
            reasons.append("近期学习趋势下降")
            risk = _escalate_risk(risk, 1)
        elif trend_dir == "improving":
            reasons.append("近期学习趋势向好")

        active_days = trend.get("active_days_7d", 0)
        if active_days <= 2:
            reasons.append(f"近7天仅学习{active_days}天")

        assessments.append({
            "kp_name": kp.get("kp_name", "unknown"),
            "risk_level": risk,
            "confidence": 0.7,
            "reasons": reasons,
        })
        levels.append(risk)

    risk_rank = {"high": 3, "medium": 2, "low": 1}
    overall = max(levels, key=lambda r: risk_rank.get(r, 0)) if levels else None

    return {
        "overall_risk": overall,
        "risk_assessments": assessments,
        "urgency_summary": f"共{len(weak_kps)}个薄弱考点需关注",
    }


def _escalate_risk(current: str, steps: int) -> str:
    levels = ["low", "medium", "high"]
    idx = levels.index(current)
    return levels[min(idx + steps, len(levels) - 1)]


async def ai_generate_warning_suggestion(
    kp_name: str,
    accuracy: float,
    days_left: int | None,
    risk_level: str,
) -> dict:
    """Use LLM (flash) to generate personalized study suggestion for a weak KP.

    Args:
        kp_name: knowledge point name
        accuracy: current accuracy (0-1)
        days_left: days until exam
        risk_level: high/medium/low

    Returns:
        {suggestion, estimated_hours, priority_actions}
    """
    system_prompt = (
        "你是一位大学课程学习教练。请针对学生的薄弱知识点，"
        "提供个性化的学习建议。\n"
        "输出 JSON 格式：\n"
        '{{"suggestion": "详细建议（50-150字）", '
        '"estimated_hours": 建议投入小时数（整数）, '
        '"priority_actions": ["行动1", "行动2", "行动3"]}}\n'
    )

    days_info = f"距考试 {days_left} 天" if days_left else "考试日期未知"

    user_prompt = (
        f"请为以下薄弱知识点生成学习建议：\n\n"
        f"知识点：{kp_name}\n"
        f"当前正确率：{int(accuracy * 100)}%\n"
        f"风险等级：{risk_level}\n"
        f"时间情况：{days_info}\n\n"
        f"请以 JSON 格式输出建议。"
    )

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]

    try:
        result = await llm_gateway.chat(
            tier="flash",
            messages=messages,
            temperature=0.5,
        )
        content = result.get("content", "")
        parsed = json.loads(content)
        return {
            "suggestion": parsed.get("suggestion", _fallback_suggestion(kp_name)),
            "estimated_hours": parsed.get("estimated_hours", 2),
            "priority_actions": parsed.get("priority_actions", []),
        }
    except (json.JSONDecodeError, KeyError, Exception) as e:
        logger.warning("ai_generate_warning_suggestion LLM failed: %s", e)
        return {
            "suggestion": _fallback_suggestion(kp_name),
            "estimated_hours": 3,
            "priority_actions": [
                f"梳理{kp_name}核心概念",
                f"完成{kp_name}相关练习题5道",
                f"总结{kp_name}常见错误类型",
            ],
        }


def _fallback_suggestion(kp_name: str) -> str:
    """Fallback suggestion template."""
    return (
        f"建议重点突破{kp_name}：每天安排2-3道相关练习，"
        f"先回顾教材对应章节的核心概念和公式，"
        f"再逐步增加难度，优先做历年真题中的相关题型。"
        f"完成后务必对照答案分析错误原因，建立错题本。"
    )
