"""Plan service -- rule engine for daily task derivation + checkin (M2).

Design: daily tasks are NOT stored in a new table; they are derived real-time
from plans + user_knowledge_states + study_sessions (architecture.md section 10.5).
"""
import uuid
from datetime import date, datetime, timezone

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Plan, StudySession, UserKnowledgeState


def days_left_phase(days: int) -> str:
    """Determine study phase based on days until exam."""
    if days > 14:
        return "daily"
    elif days >= 7:
        return "intensify"
    else:
        return "sprint"


def derive_today_task(
    plan: Plan,
    today: date,
    weak_kps: list[dict],
    session: StudySession | None,
) -> dict:
    """Derive today's task from plan config and current weak points."""
    days_left = (plan.exam_date - today).days if plan.exam_date else 30
    phase = days_left_phase(days_left)

    target = (plan.config or {}).get("daily_question_target", 10)
    focus_kps = []
    for wk in weak_kps[:3]:
        focus_kps.append({
            "id": wk["id"],
            "name": wk["name"],
            "reason": f"weak, accuracy {wk.get('accuracy', 0):.0%}",
        })

    phase_reasons = {
        "daily": f"{days_left} days left, focus on weak points",
        "intensify": f"{days_left} days left, mix weak practice + review",
        "sprint": f"{days_left} days left, focus on wrong-answer review",
    }

    done = {
        "questions_practiced": session.questions_practiced if session else 0,
        "correct_count": session.correct_count if session else 0,
        "checked_in": session.checked_in if session else False,
    }

    return {
        "date": today,
        "target_questions": target,
        "focus_kps": focus_kps,
        "type": f"{phase}_practice",
        "reason": phase_reasons.get(phase, ""),
        "done": done,
    }


async def get_or_create_session(
    db: AsyncSession,
    user_id: uuid.UUID,
    subject_id: uuid.UUID,
    session_date: date,
    plan_id: uuid.UUID | None = None,
) -> StudySession:
    """Get or create a study session for the given date."""
    from sqlalchemy.dialects.postgresql import insert as pg_insert

    stmt = pg_insert(StudySession).values(
        user_id=user_id,
        subject_id=subject_id,
        plan_id=plan_id,
        session_date=session_date,
    ).on_conflict_do_nothing(
        index_elements=["user_id", "session_date"],
    )
    await db.execute(stmt)
    await db.commit()

    result = await db.execute(
        select(StudySession).where(
            StudySession.user_id == user_id,
            StudySession.session_date == session_date,
        )
    )
    return result.scalar_one()


async def increment_session_stats(
    db: AsyncSession,
    user_id: uuid.UUID,
    subject_id: uuid.UUID,
    session_date: date,
    correct: bool = False,
    plan_id: uuid.UUID | None = None,
) -> StudySession:
    """Increment today's study session stats (questions_practiced, and optionally correct_count)."""
    session = await get_or_create_session(db, user_id, subject_id, session_date, plan_id)

    update_vals = {
        "questions_practiced": StudySession.questions_practiced + 1,
    }
    if correct:
        update_vals["correct_count"] = StudySession.correct_count + 1

    stmt = update(StudySession).where(
        StudySession.id == session.id,
    ).values(**update_vals)
    await db.execute(stmt)
    await db.commit()

    # Refresh
    result = await db.execute(select(StudySession).where(StudySession.id == session.id))
    return result.scalar_one()


async def apply_answer(
    db: AsyncSession,
    user_id: uuid.UUID,
    knowledge_point_id: uuid.UUID,
    subject_id: uuid.UUID,
    correct: bool,
) -> UserKnowledgeState:
    """Apply answer result to user knowledge state.

    Updates streak + status per state machine:
    - Correct: streak += 1, if streak >= 3 -> mastered
    - Wrong: streak = 0, recalculate status
    """
    from sqlalchemy.dialects.postgresql import insert as pg_insert

    now = datetime.now(timezone.utc)

    # Get current state first
    result = await db.execute(
        select(UserKnowledgeState).where(
            UserKnowledgeState.user_id == user_id,
            UserKnowledgeState.knowledge_point_id == knowledge_point_id,
        )
    )
    state = result.scalar_one_or_none()

    if state is None:
        # Insert new state
        state = UserKnowledgeState(
            user_id=user_id,
            knowledge_point_id=knowledge_point_id,
            subject_id=subject_id,
            status="untouched",
            correct_count=0,
            wrong_count=0,
            streak=0,
        )
        db.add(state)
        await db.flush()

    # Update counts
    if correct:
        new_correct = state.correct_count + 1
        new_wrong = state.wrong_count
        new_streak = state.streak + 1
    else:
        new_correct = state.correct_count
        new_wrong = state.wrong_count + 1
        new_streak = 0

    # Determine status
    total = new_correct + new_wrong
    if total == 0:
        new_status = "untouched"
    elif new_streak >= 3:
        new_status = "mastered"
    else:
        accuracy = new_correct / total if total > 0 else 0.0
        if accuracy < 0.4:
            new_status = "weak"
        elif accuracy < 0.7:
            new_status = "consolidating"
        else:
            new_status = "consolidating"  # >70% but not yet 3-streak

    # Upsert
    stmt = pg_insert(UserKnowledgeState).values(
        user_id=user_id,
        knowledge_point_id=knowledge_point_id,
        subject_id=subject_id,
        status=new_status,
        correct_count=new_correct,
        wrong_count=new_wrong,
        streak=new_streak,
        last_practiced_at=now,
        updated_at=now,
    ).on_conflict_do_update(
        index_elements=["user_id", "knowledge_point_id"],
        set_={
            "status": new_status,
            "correct_count": new_correct,
            "wrong_count": new_wrong,
            "streak": new_streak,
            "last_practiced_at": now,
            "updated_at": now,
        },
    )
    await db.execute(stmt)
    await db.commit()

    # Re-fetch
    result = await db.execute(
        select(UserKnowledgeState).where(
            UserKnowledgeState.user_id == user_id,
            UserKnowledgeState.knowledge_point_id == knowledge_point_id,
        )
    )
    return result.scalar_one()
