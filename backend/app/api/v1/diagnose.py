"""Diagnose router -- self-test initiation + report submission (M2).

Design: ranking by rule engine, suggestion text by LLM (architecture.md section 10.4).
"""
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db import get_db
from app.db.models import (
    DiagnosisReport,
    KnowledgePoint,
    Question,
    User,
    UserKnowledgeState,
    WrongAnswer,
)
from app.schemas.diagnose import (
    ChapterCoverage,
    NotStartedItem,
    ReportRequest,
    ReportResponse,
    SelfTestRequest,
    SelfTestResponse,
    SelfTestStatusResponse,
    StrengthItem,
    WeakTopItem,
)
from app.services.plan_service import apply_answer, increment_session_stats
from app.services.selection import select_self_test_questions

router = APIRouter(prefix="/diagnose", tags=["diagnose"])


@router.post("/self-test", response_model=SelfTestResponse, status_code=201)
async def start_self_test(
    body: SelfTestRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    # Select self-test questions (stratified sampling)
    questions = await select_self_test_questions(
        db=db,
        subject_id=uuid.UUID(body.subject_id),
        user_id=user.id,
        count=body.count,
        include_weak=body.include_weak,
    )

    # Build coverage info: group questions by chapter
    chapter_map: dict[str, dict] = {}
    for q in questions:
        kp_result = await db.execute(
            select(KnowledgePoint).where(KnowledgePoint.id == q.knowledge_point_id)
        )
        kp = kp_result.scalar_one_or_none()
        chapter_name = kp.name if kp else f"KP {q.knowledge_point_id}"
        # Find parent chapter (level=1)
        chap_result = await db.execute(
            select(KnowledgePoint).where(
                KnowledgePoint.subject_id == uuid.UUID(body.subject_id),
                KnowledgePoint.level == 1,
            ).limit(1)
        )
        chapter = chap_result.scalar_one_or_none()
        chap_id = str(chapter.id) if chapter else str(q.knowledge_point_id)
        chap_name = chapter.name if chapter else chapter_name

        if chap_id not in chapter_map:
            chapter_map[chap_id] = {"chapter_id": chap_id, "chapter_name": chap_name, "questions": 0}
        chapter_map[chap_id]["questions"] += 1

    coverage = [ChapterCoverage(**v) for v in chapter_map.values()]

    # Create diagnosis report
    report = DiagnosisReport(
        user_id=user.id,
        subject_id=uuid.UUID(body.subject_id),
        status="in_progress",
        questions=[
            {
                "id": str(q.id),
                "knowledge_point_id": str(q.knowledge_point_id),
                "type": q.type,
                "content": q.content,
                "options": q.options,
                "difficulty": q.difficulty,
            }
            for q in questions
        ],
    )
    db.add(report)
    await db.commit()
    await db.refresh(report)

    return SelfTestResponse(
        report_id=str(report.id),
        subject_id=body.subject_id,
        status="in_progress",
        questions=report.questions or [],
        coverage=coverage,
    )


@router.get("/self-test/{report_id}", response_model=SelfTestStatusResponse)
async def get_self_test(
    report_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(DiagnosisReport).where(
            DiagnosisReport.id == report_id,
            DiagnosisReport.user_id == user.id,
        )
    )
    report = result.scalar_one_or_none()
    if not report:
        raise HTTPException(status_code=404, detail="Diagnosis report not found")

    return SelfTestStatusResponse(
        report_id=str(report.id),
        subject_id=str(report.subject_id),
        status=report.status,
        questions=report.questions,
        weak_top5=report.weak_top5,
    )


@router.post("/report", response_model=ReportResponse)
async def submit_report(
    body: ReportRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    # Validate report exists
    result = await db.execute(
        select(DiagnosisReport).where(
            DiagnosisReport.id == body.report_id,
            DiagnosisReport.user_id == user.id,
        )
    )
    report = result.scalar_one_or_none()
    if not report:
        raise HTTPException(status_code=404, detail="Diagnosis report not found")
    if report.status == "completed":
        return ReportResponse(
            report_id=str(report.id),
            status="completed",
            summary="Report already submitted.",
            weak_top5=report.weak_top5 or [],
            strengths=[],
            not_started=[],
            suggested_next_steps=[],
        )

    # Grade each answer
    answers_map = {a.question_id: a.answer for a in body.answers}
    correct_count = 0
    total_count = len(body.answers)

    for ans in body.answers:
        q_result = await db.execute(select(Question).where(Question.id == ans.question_id))
        q = q_result.scalar_one_or_none()
        if not q:
            continue
        is_correct = ans.answer == q.answer

        # Update knowledge state
        await apply_answer(
            db=db,
            user_id=user.id,
            knowledge_point_id=q.knowledge_point_id,
            subject_id=report.subject_id,
            correct=is_correct,
        )

        if is_correct:
            correct_count += 1
        else:
            # Add to wrong answers
            existing_wa = await db.execute(
                select(WrongAnswer).where(
                    WrongAnswer.user_id == user.id,
                    WrongAnswer.question_id == q.id,
                )
            )
            wa = existing_wa.scalar_one_or_none()
            if wa is None:
                wa = WrongAnswer(
                    user_id=user.id,
                    question_id=q.id,
                    subject_id=report.subject_id,
                )
                db.add(wa)

    await db.commit()

    # Increment study session
    today = datetime.now(timezone.utc).date()
    await increment_session_stats(
        db=db, user_id=user.id, subject_id=report.subject_id, session_date=today,
        correct=correct_count > 0,
    )

    # --- Rule layer: compute weak_top5 from user_knowledge_states ---
    state_result = await db.execute(
        select(UserKnowledgeState).where(
            UserKnowledgeState.user_id == user.id,
            UserKnowledgeState.subject_id == report.subject_id,
        ).order_by(
            UserKnowledgeState.status == "weak",
            UserKnowledgeState.status == "consolidating",
        )
    )
    states = state_result.scalars().all()

    weak_top5: list[WeakTopItem] = []
    strengths: list[StrengthItem] = []
    not_started: list[NotStartedItem] = []

    rank = 1
    for state in states:
        total = state.correct_count + state.wrong_count
        accuracy = state.correct_count / total if total > 0 else 0.0

        if state.status in ("weak", "consolidating") and rank <= 5:
            kp_result = await db.execute(
                select(KnowledgePoint).where(KnowledgePoint.id == state.knowledge_point_id)
            )
            kp = kp_result.scalar_one_or_none()
            weak_top5.append(WeakTopItem(
                rank=rank,
                knowledge_point_id=str(state.knowledge_point_id),
                knowledge_point_name=kp.name if kp else "Unknown",
                level=kp.level if kp else 3,
                accuracy=round(accuracy, 2),
                practice_count=total,
                status=state.status,
                suggestion=f"Focus on {kp.name if kp else 'this topic'} with daily practice.",
            ))
            rank += 1
        elif accuracy >= 0.8 and total > 0:
            kp_result = await db.execute(
                select(KnowledgePoint).where(KnowledgePoint.id == state.knowledge_point_id)
            )
            kp = kp_result.scalar_one_or_none()
            strengths.append(StrengthItem(
                knowledge_point_name=kp.name if kp else "Unknown",
                accuracy=round(accuracy, 2),
            ))

    # Not started: find leaf KPs with no state record
    leaf_result = await db.execute(
        select(KnowledgePoint).where(
            KnowledgePoint.subject_id == report.subject_id,
            KnowledgePoint.level == 3,
        ).limit(20)
    )
    leaves = leaf_result.scalars().all()
    state_kp_ids = {s.knowledge_point_id for s in states}
    for leaf in leaves:
        if leaf.id not in state_kp_ids:
            not_started.append(NotStartedItem(
                knowledge_point_name=leaf.name,
                level=leaf.level,
            ))
            if len(not_started) >= 5:
                break

    # --- LLM layer: generate summary and suggestions (mock for now) ---
    summary_text = (
        f"Overall: {correct_count}/{total_count} correct. "
        f"{'Strong performance' if correct_count/total_count >= 0.7 else 'Needs improvement'}"
    )
    suggested_next_steps = [
        "Complete today's plan tasks for weak points",
        "Review the top weak knowledge points on weekends",
    ]

    # Save to report
    report.status = "completed"
    report.answers = [a.model_dump() for a in body.answers]
    report.weak_top5 = [w.model_dump() for w in weak_top5]
    report.report_text = summary_text
    await db.commit()

    return ReportResponse(
        report_id=str(report.id),
        status="completed",
        summary=summary_text,
        weak_top5=weak_top5,
        strengths=strengths,
        not_started=not_started,
        suggested_next_steps=suggested_next_steps,
    )
