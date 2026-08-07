"""Sprint (考前突击) router (M3 §11.2/§11.3)."""
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_member, get_current_user
from app.db import get_db
from app.db.models import Subject, User
from app.schemas.sprint import (
    SprintActivateResponse,
    SprintQuestionsResponse,
    SprintSummary,
)
from app.services.sprint import (
    activate_sprint,
    generate_sprint_questions,
    get_or_auto_activate_sprint,
)

router = APIRouter(tags=["sprint"])


@router.post(
    "/subjects/{subject_id}/sprint/activate",
    response_model=SprintActivateResponse,
)
async def activate(
    subject_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_member),
):
    """Activate sprint mode for a subject. Members only."""
    # Validate subject
    subj_result = await db.execute(select(Subject).where(Subject.id == subject_id))
    if not subj_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Subject not found")

    sprint_data, created = await activate_sprint(
        db=db,
        subject_id=uuid.UUID(subject_id),
        user_id=user.id,
    )

    return SprintActivateResponse(sprint=sprint_data, created=created)


@router.get(
    "/subjects/{subject_id}/sprint/questions",
    response_model=SprintQuestionsResponse,
)
async def get_sprint_questions(
    subject_id: str,
    mode: str = Query("review", pattern="^(review|mock)$"),
    count: int = Query(20, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_member),
):
    """Get sprint question list. Auto-activates if days_left ≤ 7. Members only."""
    # Validate subject
    subj_result = await db.execute(select(Subject).where(Subject.id == subject_id))
    if not subj_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Subject not found")

    # Get or auto-activate
    sprint = await get_or_auto_activate_sprint(
        db=db,
        subject_id=uuid.UUID(subject_id),
        user_id=user.id,
    )

    if not sprint:
        raise HTTPException(
            status_code=403,
            detail="No active sprint session. Activate one first at POST /sprint/activate, or create a study plan with an exam within 7 days.",
        )

    # Generate question list
    snapshot = await generate_sprint_questions(
        db=db,
        sprint=sprint,
        count=count,
        mode=mode,
    )

    return SprintQuestionsResponse(
        sprint_id=snapshot["sprint_id"],
        status=snapshot["status"],
        days_left=snapshot.get("days_left"),
        high_freq_kps=snapshot["high_freq_kps"],
        items=snapshot["items"],
        summary=SprintSummary(**snapshot["summary"]),
        mock=snapshot.get("mock"),
    )
