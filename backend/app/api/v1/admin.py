"""Admin router — UGC 审核 (M3.5 §12.4/§12.5)."""
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db import get_db
from app.db.models import Question, User, KnowledgePoint, Subject
from app.schemas.ugc import (
    UGCQuestionItem,
    UGCReviewRequest,
    UGCReviewResponse,
    UGCSubmittedBy,
)

router = APIRouter(prefix="/admin", tags=["admin"])


async def _require_admin(user: User = Depends(get_current_user)) -> User:
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    return user


@router.get("/questions/ugc")
async def list_ugc_questions(
    status: str = Query("pending", pattern="^(pending|active|rejected)$"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(_require_admin),
):
    base = select(Question).where(Question.source == "ugc", Question.status == status)
    count_stmt = select(func.count()).select_from(base.subquery())
    total_res = await db.execute(count_stmt)
    total = total_res.scalar()

    query = base.order_by(Question.created_at.asc()).offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(query)
    questions = result.scalars().all()

    items = []
    for q in questions:
        # Resolve subject & kp names
        subj_res = await db.execute(select(Subject.name).where(Subject.id == q.subject_id))
        subj_name = subj_res.scalar_one_or_none() or ""
        kp_res = await db.execute(select(KnowledgePoint.name).where(KnowledgePoint.id == q.knowledge_point_id))
        kp_name = kp_res.scalar_one_or_none() or ""

        submitted_by = None
        if q.submitted_by:
            u_res = await db.execute(select(User.id, User.username).where(User.id == q.submitted_by))
            u_row = u_res.first()
            if u_row:
                submitted_by = UGCSubmittedBy(user_id=str(u_row[0]), username=u_row[1])

        items.append(UGCQuestionItem(
            question_id=str(q.id),
            subject_id=str(q.subject_id),
            subject_name=subj_name,
            knowledge_point_id=str(q.knowledge_point_id),
            knowledge_point_name=kp_name,
            type=q.type,
            content=q.content,
            options=q.options,
            answer=q.answer,
            analysis=q.analysis,
            submitted_by=submitted_by,
            status=q.status,
            created_at=q.created_at,
            reject_reason=q.reject_reason,
        ))

    return {"items": items, "page": page, "page_size": page_size, "total": total}


@router.post("/questions/{question_id}/review", response_model=UGCReviewResponse)
async def review_ugc_question(
    question_id: str,
    body: UGCReviewRequest,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(_require_admin),
):
    result = await db.execute(select(Question).where(Question.id == question_id))
    question = result.scalar_one_or_none()
    if not question:
        raise HTTPException(status_code=404, detail="Question not found")
    if question.source != "ugc":
        raise HTTPException(status_code=422, detail="Not a UGC question")
    if question.status != "pending":
        raise HTTPException(status_code=409, detail="Already reviewed")

    if body.action == "reject" and not body.reject_reason:
        raise HTTPException(status_code=422, detail="reject_reason is required when rejecting")

    now = datetime.now(timezone.utc)
    if body.action == "approve":
        question.status = "active"
    else:
        question.status = "rejected"
        question.reject_reason = body.reject_reason

    question.reviewed_by = admin.id
    question.reviewed_at = now
    await db.commit()

    return UGCReviewResponse(
        question_id=str(question.id),
        status=question.status,
        reviewed_at=now,
    )
