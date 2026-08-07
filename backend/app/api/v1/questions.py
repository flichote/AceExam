"""Questions router -- list / create / submit + M2 practice/answers/from-ocr."""
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db import get_db
from app.db.models import (
    OcrUpload,
    Question,
    User,
    WrongAnswer,
)
from app.schemas.practice import (
    AnswerRequest,
    AnswerResponse,
    KnowledgeStateSummary,
    OcrConfirmRequest,
    OcrConfirmResponse,
    PracticeQuestionsResponse,
)
from app.schemas.questions import (
    QuestionCreate,
    QuestionDetailResponse,
    QuestionResponse,
    SubmitAnswerRequest,
    SubmitAnswerResponse,
)
from app.services.plan_service import apply_answer, increment_session_stats
from app.services.selection import select_practice_questions

router = APIRouter(tags=["questions"])


def _question_public(q: Question) -> dict:
    """Convert question to public dict (no answer/analysis)."""
    return {
        "id": str(q.id),
        "subject_id": str(q.subject_id),
        "knowledge_point_id": str(q.knowledge_point_id),
        "type": q.type,
        "content": q.content,
        "options": q.options,
        "difficulty": q.difficulty,
        "source": q.source,
        "created_at": q.created_at,
    }


def _question_to_response(q: Question, include_answer: bool = False) -> QuestionResponse | QuestionDetailResponse:
    base = _question_public(q)
    if include_answer:
        return QuestionDetailResponse(answer=q.answer, analysis=q.analysis, **base)
    return QuestionResponse(**base)


# -- M1 endpoints (preserved) --

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


# -- M1 deprecated endpoint (retained for backward compat) --

@router.post("/questions/{question_id}/submit", response_model=SubmitAnswerResponse)
async def submit_answer_deprecated(
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


# -- M2: adaptive practice questions --

@router.get("/subjects/{subject_id}/practice/questions", response_model=PracticeQuestionsResponse)
async def get_practice_questions(
    subject_id: str,
    knowledge_point_id: str | None = Query(None),
    count: int = Query(10, ge=1, le=20),
    exclude_ids: list[str] = Query([]),
    difficulty: int | None = Query(None, ge=1, le=5),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    questions, target_kps = await select_practice_questions(
        db=db,
        subject_id=uuid.UUID(subject_id),
        user_id=user.id,
        count=count,
        knowledge_point_id=uuid.UUID(knowledge_point_id) if knowledge_point_id else None,
        exclude_ids=exclude_ids,
        difficulty=difficulty,
    )

    return PracticeQuestionsResponse(
        items=[
            {
                "id": str(q.id),
                "subject_id": str(q.subject_id),
                "knowledge_point_id": str(q.knowledge_point_id),
                "type": q.type,
                "content": q.content,
                "options": q.options,
                "difficulty": q.difficulty,
                "source": q.source,
                "created_at": q.created_at,
            }
            for q in questions
        ],
        strategy={
            "target_kps": target_kps,
            "weights": {"status": 50, "error": 35, "recency": 10, "difficulty": 5},
        },
        requested_at=datetime.now(timezone.utc),
    )


# -- M2: submit answer with full knowledge state update --

@router.post("/questions/{question_id}/answers", response_model=AnswerResponse)
async def submit_answer(
    question_id: str,
    body: AnswerRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = await db.execute(select(Question).where(Question.id == question_id))
    question = result.scalar_one_or_none()
    if not question:
        raise HTTPException(status_code=404, detail="Question not found")

    # Determine correctness — unwrap {type, value} envelope (D-8 fix)
    user_answer = body.answer
    correct_answer = question.answer

    # Unwrap frontend envelope: {"type": "single", "value": "C"}
    if isinstance(user_answer, dict) and "value" in user_answer:
        user_answer = user_answer["value"]

    # Normalize: some answers may be single-element lists
    if isinstance(correct_answer, list) and len(correct_answer) == 1:
        correct_answer = correct_answer[0]
    if isinstance(user_answer, list) and len(user_answer) == 1:
        user_answer = user_answer[0]

    correct = user_answer == correct_answer

    # Update knowledge state (streak + status machine)
    state = await apply_answer(
        db=db,
        user_id=user.id,
        knowledge_point_id=question.knowledge_point_id,
        subject_id=question.subject_id,
        correct=correct,
    )

    # Increment study session
    today = datetime.now(timezone.utc).date()
    await increment_session_stats(
        db=db,
        user_id=user.id,
        subject_id=question.subject_id,
        session_date=today,
        correct=correct,
    )

    # Wrong answer -> wrong_answers table (idempotent)
    wrong_answer_id: str | None = None
    if not correct:
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
        wrong_answer_id = str(wa.id)

    return AnswerResponse(
        correct=correct,
        correct_answer=correct_answer,
        analysis=question.analysis,
        knowledge_point={"id": str(question.knowledge_point_id), "name": "", "level": 3},
        knowledge_state=KnowledgeStateSummary(
            status=state.status,
            correct_count=state.correct_count,
            wrong_count=state.wrong_count,
            streak=state.streak,
        ),
        wrong_answer_id=wrong_answer_id,
        explanation_available=True,
    )


# -- M2: confirm OCR result and import to question bank --

@router.post("/questions/from-ocr", response_model=OcrConfirmResponse, status_code=status.HTTP_200_OK)
async def confirm_ocr_question(
    body: OcrConfirmRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    # Validate upload exists and belongs to user
    upload_result = await db.execute(
        select(OcrUpload).where(
            OcrUpload.id == body.upload_id,
            OcrUpload.user_id == user.id,
        )
    )
    upload = upload_result.scalar_one_or_none()
    if not upload:
        raise HTTPException(status_code=404, detail="OCR upload not found")

    # Check idempotency: content hash + same user
    import hashlib
    content_str = body.structured.get("content", "")
    content_hash = hashlib.sha256(content_str.encode()).hexdigest()

    existing_q = await db.execute(
        select(Question).where(
            Question.content.like(f"%{content_str[:30]}%"),
            Question.subject_id == uuid.UUID(body.subject_id),
            Question.source == "ugc",
        )
    )
    dup = existing_q.scalar_one_or_none()
    if dup and upload.status == "confirmed" and upload.question_id:
        return OcrConfirmResponse(
            question_id=str(dup.id),
            upload_id=str(upload.id),
            status="confirmed",
            duplicated=True,
        )

    # Create question
    s = body.structured
    question = Question(
        subject_id=uuid.UUID(body.subject_id),
        knowledge_point_id=uuid.UUID(body.knowledge_point_id),
        type=s.get("type", "single"),
        content=s["content"],
        options=s.get("options"),
        answer=s.get("answer") if body.confirm_answer else "",
        analysis=s.get("analysis"),
        difficulty=3,
        source="ugc",
        status="active",
    )
    db.add(question)
    await db.flush()

    # Update OCR upload
    upload.status = "confirmed"
    upload.question_id = question.id
    upload.knowledge_point_id = uuid.UUID(body.knowledge_point_id)

    await db.commit()
    await db.refresh(question)

    return OcrConfirmResponse(
        question_id=str(question.id),
        upload_id=str(upload.id),
        status="confirmed",
        duplicated=False,
    )
