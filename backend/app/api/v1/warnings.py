"""Warnings (挂科预警) router (M3 §11.7)."""
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db import get_db
from app.db.models import Subject, User
from app.schemas.warnings import WarningItem, WarningsResponse
from app.services.warning import get_warnings

router = APIRouter(tags=["warnings"])


@router.get("/me/warnings", response_model=WarningsResponse)
async def warnings(
    subject_id: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if subject_id:
        subj_result = await db.execute(select(Subject).where(Subject.id == subject_id))
        if not subj_result.scalar_one_or_none():
            raise HTTPException(status_code=404, detail="Subject not found")

    data = await get_warnings(
        db=db,
        user_id=user.id,
        subject_id=uuid.UUID(subject_id) if subject_id else None,
    )

    return WarningsResponse(
        overall_risk=data["overall_risk"],
        items=[WarningItem(**item) for item in data["items"]],
        generated_at=data["generated_at"],
    )
