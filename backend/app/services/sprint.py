"""Sprint service -- activation + question list generation (M3 §11.2/§11.3).

Inline implementation per T15 until T17 delivers. See architecture.md §11.2.
- High-frequency KP identification: rule-based from user_knowledge_states
- Question selection: high_freq KPs + personal wrong answers, deduped
- Activation: idempotent (returns existing if active), auto-activates when days_left ≤ 7
"""

import uuid
from datetime import date, datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import (
    KnowledgePoint,
    Plan,
    Question,
    SprintSession,
    UserKnowledgeState,
    WrongAnswer,
)


async def activate_sprint(
    db: AsyncSession,
    subject_id: uuid.UUID,
    user_id: uuid.UUID,
) -> tuple[dict, bool]:
    """Activate a sprint session. Idempotent: returns existing if active.

    Returns: (sprint_dict, created_bool)
    """
    # Check existing active session
    existing = await db.execute(
        select(SprintSession).where(
            SprintSession.user_id == user_id,
            SprintSession.subject_id == subject_id,
            SprintSession.status == "active",
        )
    )
    active = existing.scalar_one_or_none()

    # Check if exam date has passed → expire old and create new
    today = date.today()
    if active and active.expires_at and active.expires_at < today:
        active.status = "expired"
        await db.commit()
        active = None

    if active:
        return _sprint_to_dict(active), False

    # Look up active plan for exam_date
    plan_result = await db.execute(
        select(Plan).where(
            Plan.user_id == user_id,
            Plan.subject_id == subject_id,
            Plan.status == "active",
        ).order_by(Plan.exam_date.nulls_last()).limit(1)
    )
    plan = plan_result.scalar_one_or_none()

    exam_date = plan.exam_date if plan and plan.exam_date else None
    days_left = (exam_date - today).days if exam_date else None

    sprint = SprintSession(
        user_id=user_id,
        subject_id=subject_id,
        status="active",
        auto_activated=False,
        expires_at=exam_date,
    )
    db.add(sprint)
    await db.commit()
    await db.refresh(sprint)

    return {
        "id": str(sprint.id),
        "subject_id": str(sprint.subject_id),
        "status": sprint.status,
        "activated_at": sprint.activated_at,
        "auto_activated": sprint.auto_activated,
        "exam_date": exam_date.isoformat() if exam_date else None,
        "days_left": days_left,
        "expires_at": exam_date.isoformat() if exam_date else None,
    }, True


def _sprint_to_dict(s: SprintSession) -> dict:
    today = date.today()
    days_left = (s.expires_at - today).days if s.expires_at else None
    return {
        "id": str(s.id),
        "subject_id": str(s.subject_id),
        "status": s.status,
        "activated_at": s.activated_at,
        "auto_activated": s.auto_activated,
        "exam_date": s.expires_at.isoformat() if s.expires_at else None,
        "days_left": days_left,
        "expires_at": s.expires_at.isoformat() if s.expires_at else None,
    }


async def get_or_auto_activate_sprint(
    db: AsyncSession,
    subject_id: uuid.UUID,
    user_id: uuid.UUID,
) -> SprintSession | None:
    """Get active sprint session or auto-activate if days_left ≤ 7."""
    existing = await db.execute(
        select(SprintSession).where(
            SprintSession.user_id == user_id,
            SprintSession.subject_id == subject_id,
            SprintSession.status == "active",
        )
    )
    active = existing.scalar_one_or_none()

    today = date.today()
    if active and active.expires_at and active.expires_at < today:
        active.status = "expired"
        await db.commit()
        active = None

    if active:
        return active

    # Check plan for auto-activation
    plan_result = await db.execute(
        select(Plan).where(
            Plan.user_id == user_id,
            Plan.subject_id == subject_id,
            Plan.status == "active",
        )
    )
    plan = plan_result.scalar_one_or_none()

    if plan and plan.exam_date:
        days_left = (plan.exam_date - today).days
        if days_left <= 7:
            sprint = SprintSession(
                user_id=user_id,
                subject_id=subject_id,
                status="active",
                auto_activated=True,
                expires_at=plan.exam_date,
            )
            db.add(sprint)
            await db.commit()
            await db.refresh(sprint)
            return sprint

    return None


async def generate_sprint_questions(
    db: AsyncSession,
    sprint: SprintSession,
    count: int = 20,
    mode: str = "review",
) -> dict:
    """Generate sprint question list (high-freq + wrong answers, deduped).

    If sprint already has a snapshot, return it (stable).
    """
    # Return cached snapshot if available
    if sprint.question_snapshot:
        snap = sprint.question_snapshot
        # Check if snapshot items still exist
        item_ids = [uuid.UUID(i["id"]) for i in snap.get("items", [])]
        q_check = await db.execute(
            select(Question).where(Question.id.in_(item_ids))
        )
        alive_ids = {q.id for q in q_check.scalars().all()}
        if len(alive_ids) >= len(item_ids) * 0.8:  # at least 80% alive → reuse
            return snap

    subject_id = sprint.subject_id
    user_id = sprint.user_id
    today = date.today()
    days_left = (sprint.expires_at - today).days if sprint.expires_at else None

    # 1) High-frequency KPs: heat = total_user_practice_count across all users
    heat_result = await db.execute(
        select(
            UserKnowledgeState.knowledge_point_id,
            func.sum(UserKnowledgeState.correct_count + UserKnowledgeState.wrong_count).label("heat"),
            func.sum(UserKnowledgeState.correct_count).label("total_correct"),
        )
        .join(KnowledgePoint, UserKnowledgeState.knowledge_point_id == KnowledgePoint.id)
        .where(
            KnowledgePoint.subject_id == subject_id,
            KnowledgePoint.level == 3,
        )
        .group_by(UserKnowledgeState.knowledge_point_id)
        .order_by(func.sum(UserKnowledgeState.correct_count + UserKnowledgeState.wrong_count).desc())
        .limit(10)
    )
    high_freq_rows = heat_result.all()

    high_freq_kps = []
    for row in high_freq_rows:
        total_q = row.heat or 0
        if total_q >= 20:  # threshold per architecture §11.2
            kp_result = await db.execute(
                select(KnowledgePoint).where(KnowledgePoint.id == row.knowledge_point_id)
            )
            kp = kp_result.scalar_one_or_none()
            if kp:
                avg_acc = (row.total_correct / total_q) if total_q > 0 else 0.0
                if avg_acc < 0.75:  # only include "difficult" high-freq KPs
                    # Check past_exam questions
                    pe_result = await db.execute(
                        select(func.count(Question.id)).where(
                            Question.knowledge_point_id == kp.id,
                            Question.source == "past_exam",
                            Question.status == "active",
                        )
                    )
                    pe_count = pe_result.scalar() or 0
                    high_freq_kps.append({
                        "id": str(kp.id),
                        "name": kp.name,
                        "heat": total_q,
                        "avg_accuracy": round(avg_acc, 2),
                        "has_past_exam": pe_count > 0,
                    })

    # Fallback: if no high-freq KPs, use KPs with past_exam questions
    if not high_freq_kps:
        pe_kps_result = await db.execute(
            select(Question.knowledge_point_id, func.count(Question.id).label("cnt"))
            .where(
                Question.subject_id == subject_id,
                Question.source == "past_exam",
                Question.status == "active",
            )
            .group_by(Question.knowledge_point_id)
            .order_by(func.count(Question.id).desc())
            .limit(5)
        )
        for row in pe_kps_result:
            kp_result = await db.execute(
                select(KnowledgePoint).where(KnowledgePoint.id == row.knowledge_point_id)
            )
            kp = kp_result.scalar_one_or_none()
            if kp:
                high_freq_kps.append({
                    "id": str(kp.id),
                    "name": kp.name,
                    "heat": row.cnt,
                    "avg_accuracy": 0.5,
                    "has_past_exam": True,
                })

    # 2) Personal wrong answers (unmastered)
    wa_result = await db.execute(
        select(WrongAnswer).where(
            WrongAnswer.user_id == user_id,
            WrongAnswer.subject_id == subject_id,
            WrongAnswer.mastered == False,
        ).order_by(WrongAnswer.created_at.desc()).limit(count)
    )
    wrong_answers = wa_result.scalars().all()

    # 3) Select questions: high-freq KPs first, then wrong answers, deduped
    selected_ids: set[uuid.UUID] = set()
    items: list[dict] = []
    high_freq_count = 0
    wrong_review_count = 0

    # High-freq: up to 3 questions per KP
    hf_slots = max(count - min(len(wrong_answers), count // 3), int(count * 0.7))
    for hf in high_freq_kps:
        if len(items) >= hf_slots:
            break
        kp_id = uuid.UUID(hf["id"])
        q_result = await db.execute(
            select(Question)
            .where(
                Question.knowledge_point_id == kp_id,
                Question.status == "active",
                Question.id.notin_(selected_ids),
            )
            .limit(3)
        )
        for q in q_result.scalars().all():
            if q.id not in selected_ids:
                selected_ids.add(q.id)
                items.append(_question_public(q, tag="high_freq"))
                high_freq_count += 1

    # Wrong answers: up to 2 per KP
    for wa in wrong_answers:
        if len(items) >= count:
            break
        q_result = await db.execute(
            select(Question).where(
                Question.id == wa.question_id,
                Question.status == "active",
                Question.id.notin_(selected_ids),
            )
        )
        q = q_result.scalar_one_or_none()
        if q and q.id not in selected_ids:
            selected_ids.add(q.id)
            items.append(_question_public(q, tag="wrong_review"))
            wrong_review_count += 1

    total = len(items)

    # 4) Build snapshot
    snapshot: dict = {
        "sprint_id": str(sprint.id),
        "status": sprint.status,
        "days_left": days_left,
        "high_freq_kps": high_freq_kps,
        "items": items,
        "summary": {
            "high_freq_questions": high_freq_count,
            "wrong_review_questions": wrong_review_count,
            "deduped": high_freq_count + wrong_review_count - total,
            "total": total,
        },
        "mock": None,
    }

    if mode == "mock":
        snapshot["mock"] = {
            "duration_min": 120,
            "total_score": 100,
            "started_at": None,
        }

    # Save snapshot
    sprint.question_snapshot = snapshot
    await db.commit()

    return snapshot


def _question_public(q: Question, tag: str | None = None) -> dict:
    item = {
        "id": str(q.id),
        "subject_id": str(q.subject_id),
        "knowledge_point_id": str(q.knowledge_point_id),
        "type": q.type,
        "content": q.content,
        "options": q.options,
        "difficulty": q.difficulty,
        "source": q.source,
    }
    if tag:
        item["tag"] = tag
    return item
