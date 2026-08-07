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
