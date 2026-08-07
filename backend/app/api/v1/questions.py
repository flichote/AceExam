"""Questions router — list / create / submit."""
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db import get_db
from app.db.models import Question, User, WrongAnswer
from app.schemas.questions import (
    QuestionCreate,
    QuestionDetailResponse,
    QuestionResponse,
    SubmitAnswerRequest,
    SubmitAnswerResponse,
)

router = APIRouter(tags=["questions"])


def _question_to_response(q: Question, include_answer: bool = False) -> QuestionResponse | QuestionDetailResponse:
    base = {
        "id": str(q.id),
        "subject_id": str(q.subject_id),
        "knowledge_point_id": str(q.knowledge_point_id) if q.knowledge_point_id else None,
        "type": q.type,
        "content": q.content,
        "options": q.options,
        "difficulty": q.difficulty,
        "source": q.source,
        "created_at": q.created_at,
    }
    if include_answer:
        return QuestionDetailResponse(answer=q.answer, analysis=q.analysis, **base)
    return QuestionResponse(**base)


@router.get("/questions", response_model=dict)
async def list_questions(
    subject_id: str = Query(...),
    knowledge_point_id: str | None = Query(None),
    difficulty: int | None = Query(None, ge=1, le=5),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    _user=Depends(get_current_user),
):
    stmt = select(Question).where(Question.subject_id == subject_id, Question.status == "active")
    if knowledge_point_id:
        stmt = stmt.where(Question.knowledge_point_id == knowledge_point_id)
    if difficulty is not None:
        stmt = stmt.where(Question.difficulty == difficulty)

    count_stmt = select(Question).where(Question.subject_id == subject_id, Question.status == "active")
    if knowledge_point_id:
        count_stmt = count_stmt.where(Question.knowledge_point_id == knowledge_point_id)
    if difficulty is not None:
        count_stmt = count_stmt.where(Question.difficulty == difficulty)

    total_result = await db.execute(count_stmt)
    total = len(total_result.scalars().all())

    stmt = stmt.offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(stmt)
    questions = result.scalars().all()

    return {
        "items": [_question_to_response(q) for q in questions],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.get("/questions/{question_id}", response_model=QuestionResponse)
async def get_question(
    question_id: str,
    db: AsyncSession = Depends(get_db),
    _user=Depends(get_current_user),
):
    result = await db.execute(select(Question).where(Question.id == question_id))
    question = result.scalar_one_or_none()
    if not question:
        raise HTTPException(status_code=404, detail="Question not found")
    return _question_to_response(question, include_answer=False)


@router.post("/questions", response_model=QuestionResponse, status_code=status.HTTP_201_CREATED)
async def create_question(
    body: QuestionCreate,
    subject_id: str = Query(...),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    question = Question(subject_id=uuid.UUID(subject_id), **body.model_dump())
    db.add(question)
    await db.commit()
    await db.refresh(question)
    return _question_to_response(question)


@router.post("/questions/{question_id}/submit", response_model=SubmitAnswerResponse)
async def submit_answer(
    question_id: str,
    body: SubmitAnswerRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = await db.execute(select(Question).where(Question.id == question_id))
    question = result.scalar_one_or_none()
    if not question:
        raise HTTPException(status_code=404, detail="Question not found")

    correct = body.answer == question.answer

    response_data: dict = {
        "correct": correct,
        "correct_answer": question.answer,
        "analysis": question.analysis,
        "wrong_answer_id": None,
    }

    if not correct:
        # Idempotent: check existing via unique constraint
        existing_wa = await db.execute(
            select(WrongAnswer).where(
                WrongAnswer.user_id == user.id,
                WrongAnswer.question_id == uuid.UUID(question_id),
            )
        )
        wa = existing_wa.scalar_one_or_none()
        if wa is None:
            wa = WrongAnswer(
                user_id=user.id,
                question_id=uuid.UUID(question_id),
                subject_id=question.subject_id,
            )
            db.add(wa)
            await db.commit()
            await db.refresh(wa)
        response_data["wrong_answer_id"] = str(wa.id)

    return SubmitAnswerResponse(**response_data)
