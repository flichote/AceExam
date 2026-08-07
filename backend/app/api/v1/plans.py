"""Plans router -- create + active + checkin (M2).

Design: daily tasks derived real-time, not pre-stored (architecture.md section 10.5).
"""
import uuid
from datetime import date, datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_member, get_current_user
from app.db import get_db
from app.db.models import (
    Plan,
    StudySession,
    User,
    UserKnowledgeState,
)
from app.schemas.plans import (
    ActivePlanResponse,
    CheckinResponse,
    PlanCreate,
    PlanCreateResponse,
    PlanDetail,
    TodayTask,
    UpcomingTask,
    WeakKPItem,
)
from app.services.plan_service import (
    derive_today_task,
    get_or_create_session,
)

router = APIRouter(prefix="/plans", tags=["plans"])


@router.post("", response_model=PlanCreateResponse, status_code=201)
async def create_plan(
    body: PlanCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_member),
):
    # Check no existing active plan for same subject
    existing = await db.execute(
        select(Plan).where(
            Plan.user_id == user.id,
            Plan.subject_id == uuid.UUID(body.subject_id),
            Plan.status == "active",
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=409,
            detail="Active plan already exists for this subject. Complete or cancel it first.",
        )

    # Validate exam date
    if body.exam_date <= date.today():
        raise HTTPException(status_code=422, detail="Exam date must be in the future")

    # Create plan
    plan = Plan(
        user_id=user.id,
        subject_id=uuid.UUID(body.subject_id),
        title=body.title,
        exam_date=body.exam_date,
        status="active",
        config={"daily_question_target": body.daily_question_target},
    )
    db.add(plan)
    await db.commit()
    await db.refresh(plan)

    # Fetch weak KPs
    state_result = await db.execute(
        select(UserKnowledgeState).where(
            UserKnowledgeState.user_id == user.id,
            UserKnowledgeState.subject_id == uuid.UUID(body.subject_id),
            UserKnowledgeState.status.in_(["weak", "consolidating"]),
        ).order_by(UserKnowledgeState.correct_count.asc()).limit(5)
    )
    states = state_result.scalars().all()

    from app.db.models import KnowledgePoint
    weak_kps = []
    for s in states:
        kp_result = await db.execute(
            select(KnowledgePoint).where(KnowledgePoint.id == s.knowledge_point_id)
        )
        kp = kp_result.scalar_one_or_none()
        total = s.correct_count + s.wrong_count
        accuracy = s.correct_count / total if total > 0 else 0.0
        weak_kps.append({
            "id": str(s.knowledge_point_id),
            "name": kp.name if kp else "Unknown",
            "status": s.status,
            "accuracy": round(accuracy, 2),
        })

    # Derive today's task
    today = date.today()
    session = await get_or_create_session(db, user.id, uuid.UUID(body.subject_id), today, plan.id)
    today_task_data = derive_today_task(plan, today, weak_kps, session)

    days_left = (body.exam_date - today).days
    plan_detail = PlanDetail(
        id=str(plan.id),
        subject_id=str(plan.subject_id),
        title=plan.title or "Study Plan",
        exam_date=body.exam_date,
        days_left=days_left,
        status=plan.status,
        daily_question_target=body.daily_question_target,
    )

    return PlanCreateResponse(
        plan=plan_detail,
        weak_kps=[WeakKPItem(**wk) for wk in weak_kps],
        today_task=TodayTask(**today_task_data),
    )


@router.get("/active", response_model=ActivePlanResponse)
async def get_active_plan(
    subject_id: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    # Find active plan
    stmt = select(Plan).where(
        Plan.user_id == user.id,
        Plan.status == "active",
    )
    if subject_id:
        stmt = stmt.where(Plan.subject_id == uuid.UUID(subject_id))
    stmt = stmt.order_by(Plan.created_at.desc()).limit(1)

    result = await db.execute(stmt)
    plan = result.scalar_one_or_none()

    if not plan:
        return ActivePlanResponse(plan=None, today_task=None, upcoming=[])

    today = date.today()
    days_left = (plan.exam_date - today).days if plan.exam_date else 30

    # Weak KPs
    state_result = await db.execute(
        select(UserKnowledgeState).where(
            UserKnowledgeState.user_id == user.id,
            UserKnowledgeState.subject_id == plan.subject_id,
            UserKnowledgeState.status.in_(["weak", "consolidating"]),
        ).order_by(UserKnowledgeState.correct_count.asc()).limit(5)
    )
    states = state_result.scalars().all()

    from app.db.models import KnowledgePoint
    weak_kps = []
    for s in states:
        kp_result = await db.execute(
            select(KnowledgePoint).where(KnowledgePoint.id == s.knowledge_point_id)
        )
        kp = kp_result.scalar_one_or_none()
        total = s.correct_count + s.wrong_count
        accuracy = s.correct_count / total if total > 0 else 0.0
        weak_kps.append({
            "id": str(s.knowledge_point_id),
            "name": kp.name if kp else "Unknown",
            "status": s.status,
            "accuracy": round(accuracy, 2),
        })

    # Today's session
    session = await get_or_create_session(db, user.id, plan.subject_id, today, plan.id)
    today_task_data = derive_today_task(plan, today, weak_kps, session)

    # Upcoming 3 days
    upcoming = []
    for delta in range(1, 4):
        future_date = today.replace(day=today.day + delta) if today.day + delta <= 28 else today
        d = (plan.exam_date - future_date).days if plan.exam_date else 30
        phase = "daily" if d > 14 else ("intensify" if d >= 7 else "sprint")
        upcoming.append({
            "date": future_date,
            "target_questions": (plan.config or {}).get("daily_question_target", 10),
            "focus_kps": [],
            "type": f"{phase}_practice",
        })

    plan_detail = PlanDetail(
        id=str(plan.id),
        subject_id=str(plan.subject_id),
        title=plan.title or "Study Plan",
        exam_date=plan.exam_date,
        days_left=days_left,
        status=plan.status,
        daily_question_target=(plan.config or {}).get("daily_question_target", 10),
    )

    return ActivePlanResponse(
        plan=plan_detail,
        today_task=TodayTask(**today_task_data),
        upcoming=[UpcomingTask(**u) for u in upcoming],
    )


@router.post("/{plan_id}/checkin", response_model=CheckinResponse)
async def checkin(
    plan_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    # Validate plan
    result = await db.execute(
        select(Plan).where(Plan.id == plan_id, Plan.user_id == user.id)
    )
    plan = result.scalar_one_or_none()
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")
    if plan.status != "active":
        raise HTTPException(status_code=409, detail="Plan is not active")

    today = date.today()
    session = await get_or_create_session(db, user.id, plan.subject_id, today, plan.id)

    if session.checked_in:
        return CheckinResponse(
            checked_in=True,
            already_checked_in=True,
            session={
                "session_date": str(session.session_date),
                "questions_practiced": session.questions_practiced,
                "correct_count": session.correct_count,
                "checked_in": True,
                "checked_in_at": session.checked_in_at.isoformat() if session.checked_in_at else None,
            },
        )

    # Optimistic lock: UPDATE ... WHERE checked_in=false
    now = datetime.now(timezone.utc)
    stmt = (
        update(StudySession)
        .where(
            StudySession.id == session.id,
            StudySession.checked_in == False,
        )
        .values(checked_in=True, checked_in_at=now)
    )
    result = await db.execute(stmt)
    await db.commit()

    if result.rowcount == 0:
        # Already checked in (race condition)
        refreshed = await db.execute(select(StudySession).where(StudySession.id == session.id))
        s = refreshed.scalar_one()
        return CheckinResponse(
            checked_in=True,
            already_checked_in=True,
            session={
                "session_date": str(s.session_date),
                "questions_practiced": s.questions_practiced,
                "correct_count": s.correct_count,
                "checked_in": True,
                "checked_in_at": s.checked_in_at.isoformat() if s.checked_in_at else None,
            },
        )

    refreshed = await db.execute(select(StudySession).where(StudySession.id == session.id))
    s = refreshed.scalar_one()

    return CheckinResponse(
        checked_in=True,
        already_checked_in=False,
        session={
            "session_date": str(s.session_date),
            "questions_practiced": s.questions_practiced,
            "correct_count": s.correct_count,
            "checked_in": True,
            "checked_in_at": s.checked_in_at.isoformat(),
        },
    )
