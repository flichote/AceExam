"""Dashboard router (M3 §11.4/§11.5)."""
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db import get_db
from app.db.models import Subject, User
from app.schemas.dashboard import (
    DashboardExam,
    DashboardMastery,
    DashboardResponse,
    DashboardStreak,
    DashboardTotals,
    DashboardTrendResponse,
    DashboardWeakPoints,
    PerSubjectStat,
    TrendItem,
)
from app.services.dashboard import get_dashboard, get_dashboard_trend

router = APIRouter(tags=["dashboard"])


@router.get("/me/dashboard", response_model=DashboardResponse)
async def dashboard(
    subject_id: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if subject_id:
        subj_result = await db.execute(select(Subject).where(Subject.id == subject_id))
        if not subj_result.scalar_one_or_none():
            raise HTTPException(status_code=404, detail="Subject not found")

    data = await get_dashboard(
        db=db,
        user_id=user.id,
        subject_id=uuid.UUID(subject_id) if subject_id else None,
    )

    return DashboardResponse(
        totals=DashboardTotals(**data["totals"]),
        mastery=DashboardMastery(**data["mastery"]),
        streak=DashboardStreak(**data["streak"]),
        weak_points=DashboardWeakPoints(**data["weak_points"]),
        per_subject=[PerSubjectStat(**ps) for ps in data["per_subject"]],
        exam=DashboardExam(**data["exam"]),
    )


@router.get("/me/dashboard/trend", response_model=DashboardTrendResponse)
async def dashboard_trend(
    days: int = Query(30, ge=1, le=180),
    subject_id: str | None = Query(None),
    granularity: str = Query("day", pattern="^(day|week|month)$"),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if subject_id:
        subj_result = await db.execute(select(Subject).where(Subject.id == subject_id))
        if not subj_result.scalar_one_or_none():
            raise HTTPException(status_code=404, detail="Subject not found")

    data = await get_dashboard_trend(
        db=db,
        user_id=user.id,
        days=days,
        subject_id=uuid.UUID(subject_id) if subject_id else None,
        granularity=granularity,
    )

    return DashboardTrendResponse(
        granularity=data["granularity"],
        items=[TrendItem(**item) for item in data["items"]],
    )
