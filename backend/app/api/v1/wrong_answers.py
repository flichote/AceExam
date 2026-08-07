"""Wrong Answers router — list / delete / mark mastered."""
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db import get_db
from app.db.models import Question, User, WrongAnswer
from app.schemas.wrong_answers import WrongAnswerCreate, WrongAnswerResponse

router = APIRouter(prefix="/wrong-answers", tags=["wrong-answers"])


@router.get("", response_model=list[WrongAnswerResponse])
async def list_wrong_answers(
    subject_id: str | None = Query(None),
    status_filter: str | None = Query(None, alias="status"),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    stmt = select(WrongAnswer).where(WrongAnswer.user_id == user.id)
    if subject_id:
        stmt = stmt.where(WrongAnswer.subject_id == uuid.UUID(subject_id))
    if status_filter == "active":
        stmt = stmt.where(WrongAnswer.mastered == False)  # noqa: E712
    elif status_filter == "mastered":
        stmt = stmt.where(WrongAnswer.mastered == True)  # noqa: E712
    stmt = stmt.order_by(WrongAnswer.created_at.desc())

    result = await db.execute(stmt)
    wa_list = result.scalars().all()

    responses: list[WrongAnswerResponse] = []
    for wa in wa_list:
        q_result = await db.execute(select(Question).where(Question.id == wa.question_id))
        question = q_result.scalar_one_or_none()
        responses.append(
            WrongAnswerResponse(
                id=str(wa.id),
                question_id=str(wa.question_id),
                subject_id=str(wa.subject_id),
                wrong_answer=str(wa.wrong_answer) if wa.wrong_answer else None,
                wrong_reason=wa.wrong_reason,
                review_count=wa.review_count,
                mastered=wa.mastered,
                created_at=wa.created_at,
                question_content=question.content[:200] if question else None,
                knowledge_point_name=None,
            )
        )
    return responses


@router.post("", response_model=WrongAnswerResponse, status_code=status.HTTP_201_CREATED)
async def create_wrong_answer(
    body: WrongAnswerCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    existing = await db.execute(
        select(WrongAnswer).where(
            WrongAnswer.user_id == user.id,
            WrongAnswer.question_id == uuid.UUID(body.question_id),
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Already in wrong-answer book")

    wa = WrongAnswer(
        user_id=user.id,
        question_id=uuid.UUID(body.question_id),
        subject_id=uuid.UUID(body.subject_id),
        wrong_reason=body.wrong_reason,
    )
    db.add(wa)
    await db.commit()
    await db.refresh(wa)
    return WrongAnswerResponse(
        id=str(wa.id),
        question_id=str(wa.question_id),
        subject_id=str(wa.subject_id),
        wrong_answer=None,
        wrong_reason=wa.wrong_reason,
        review_count=wa.review_count,
        mastered=wa.mastered,
        created_at=wa.created_at,
        question_content=None,
        knowledge_point_name=None,
    )


@router.delete("/{wa_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_wrong_answer(
    wa_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(WrongAnswer).where(WrongAnswer.id == uuid.UUID(wa_id), WrongAnswer.user_id == user.id)
    )
    wa = result.scalar_one_or_none()
    if not wa:
        raise HTTPException(status_code=404, detail="Wrong answer record not found")
    await db.delete(wa)
    await db.commit()


@router.post("/{wa_id}/mastered", response_model=WrongAnswerResponse)
async def mark_mastered(
    wa_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(WrongAnswer).where(WrongAnswer.id == uuid.UUID(wa_id), WrongAnswer.user_id == user.id)
    )
    wa = result.scalar_one_or_none()
    if not wa:
        raise HTTPException(status_code=404, detail="Wrong answer record not found")
    wa.mastered = True
    await db.commit()
    await db.refresh(wa)
    return WrongAnswerResponse(
        id=str(wa.id),
        question_id=str(wa.question_id),
        subject_id=str(wa.subject_id),
        wrong_answer=str(wa.wrong_answer) if wa.wrong_answer else None,
        wrong_reason=wa.wrong_reason,
        review_count=wa.review_count,
        mastered=wa.mastered,
        created_at=wa.created_at,
        question_content=None,
        knowledge_point_name=None,
    )
