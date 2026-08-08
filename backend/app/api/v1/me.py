"""Me router — 班级 + 分享卡 (M3.5 §12.6~§12.8)."""
import secrets
import string
import uuid
from datetime import date, datetime, timezone, timedelta

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, func, and_, case
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db import get_db
from app.db.models import Class, Plan, Question, StudySession, User, UserKnowledgeState
from app.schemas.classroom import (
    ClassCreateRequest,
    ClassInfo,
    ClassRank,
    JoinClassResponse,
    MeClassResponse,
)
from app.schemas.share_card import (
    ShareCardClass,
    ShareCardExam,
    ShareCardMastery,
    ShareCardResponse,
    ShareCardStreak,
    ShareCardTotals,
    ShareCardWeakPoints,
)
from app.services.streak import compute_streak

router = APIRouter(prefix="/me", tags=["me"])


def _generate_invite_code(length: int = 6) -> str:
    alphabet = string.ascii_uppercase + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(length))


# ── 班级 ──

@router.post("/class", response_model=JoinClassResponse)
async def set_class(
    body: ClassCreateRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if bool(body.name) == bool(body.invite_code):
        raise HTTPException(status_code=422, detail="Provide either 'name' or 'invite_code', not both or neither")

    if body.name:
        # 建班
        code = _generate_invite_code()
        cls = Class(name=body.name, invite_code=code, created_by=user.id)
        db.add(cls)
        await db.flush()
        user.class_id = cls.id
        await db.commit()
        await db.refresh(cls)

        member_count = 1
        return JoinClassResponse(
            class_=ClassInfo(
                id=str(cls.id),
                name=cls.name,
                invite_code=cls.invite_code,
                member_count=member_count,
                is_creator=True,
            ),
            joined=True,
        )
    else:
        # 加入班级
        res = await db.execute(select(Class).where(Class.invite_code == body.invite_code))
        cls = res.scalar_one_or_none()
        if not cls:
            raise HTTPException(status_code=404, detail="Class not found")

        user.class_id = cls.id
        await db.commit()

        # Count members
        cnt_res = await db.execute(
            select(func.count()).select_from(User).where(User.class_id == cls.id)
        )
        member_count = cnt_res.scalar() or 0

        return JoinClassResponse(
            class_=ClassInfo(
                id=str(cls.id),
                name=cls.name,
                invite_code=None,  # 加入者不返回
                member_count=member_count,
                is_creator=(cls.created_by == user.id),
            ),
            joined=True,
        )


@router.get("/class", response_model=MeClassResponse)
async def get_my_class(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if not user.class_id:
        return MeClassResponse(class_=None, my_rank=None)

    res = await db.execute(select(Class).where(Class.id == user.class_id))
    cls = res.scalar_one_or_none()
    if not cls:
        return MeClassResponse(class_=None, my_rank=None)

    cnt_res = await db.execute(
        select(func.count()).select_from(User).where(User.class_id == cls.id)
    )
    member_count = cnt_res.scalar() or 0

    # my_rank: aggregate user stats for class members, sort by total_correct DESC
    agg = (
        select(
            StudySession.user_id,
            func.sum(StudySession.correct_count).label("total_correct"),
            func.sum(StudySession.questions_practiced).label("total_q"),
        )
        .where(StudySession.user_id.in_(
            select(User.id).where(User.class_id == cls.id)
        ))
        .group_by(StudySession.user_id)
    )
    agg_res = await db.execute(agg)
    members = list(agg_res.all())
    members.sort(key=lambda x: (x.total_correct or 0), reverse=True)

    my_rank = None
    for i, (uid, tc, tq) in enumerate(members, start=1):
        if uid == user.id:
            my_rank = ClassRank(rank=i, total_correct=tc or 0)
            break

    return MeClassResponse(
        class_=ClassInfo(
            id=str(cls.id),
            name=cls.name,
            invite_code=cls.invite_code if cls.created_by == user.id else None,
            member_count=member_count,
            is_creator=(cls.created_by == user.id),
        ),
        my_rank=my_rank,
    )


# ── 分享卡 ──

@router.get("/share-card", response_model=ShareCardResponse)
async def get_share_card(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    now = datetime.now(timezone.utc)
    today = now.date()
    seven_days_ago = today - timedelta(days=6)

    # Totals: aggregate all study_sessions
    total_res = await db.execute(
        select(
            func.coalesce(func.sum(StudySession.questions_practiced), 0),
            func.coalesce(func.sum(StudySession.correct_count), 0),
        ).where(StudySession.user_id == user.id)
    )
    total_qp, total_correct = total_res.one()
    total_qp = int(total_qp)
    total_correct = int(total_correct)
    total_acc = round(total_correct / total_qp, 3) if total_qp > 0 else 0.0

    # Recent 7d
    recent_res = await db.execute(
        select(
            func.coalesce(func.sum(StudySession.questions_practiced), 0),
            func.coalesce(func.sum(StudySession.correct_count), 0),
        ).where(
            StudySession.user_id == user.id,
            StudySession.session_date >= seven_days_ago,
        )
    )
    r7_qp, r7_correct = recent_res.one()
    r7_qp = int(r7_qp)
    r7_correct = int(r7_correct)
    r7_acc = round(r7_correct / r7_qp, 3) if r7_qp > 0 else 0.0

    # Streak
    streak_res = await db.execute(
        select(StudySession.session_date)
        .where(StudySession.user_id == user.id, StudySession.checked_in == True)
        .order_by(StudySession.session_date.asc())
    )
    streak_dates = [r[0] for r in streak_res.all()]
    current_streak, longest_streak = compute_streak(streak_dates, today=today) if streak_dates else (0, 0)

    # Mastery: from user_knowledge_states
    mastery_res = await db.execute(
        select(
            func.count().label("total"),
            func.sum(
                case((UserKnowledgeState.status == "mastered", 1), else_=0)
            ).label("mastered"),
        ).where(UserKnowledgeState.user_id == user.id)
    )
    m_row = mastery_res.one()
    total_kps = m_row.total or 0
    mastered_kps = m_row.mastered or 0
    overall_pct = round(mastered_kps / total_kps, 3) if total_kps > 0 else 0.0

    # Best subject
    best_subject = None
    from app.db.models import Subject as _Subject
    subj_res = await db.execute(
        select(
            UserKnowledgeState.subject_id,
            func.count().label("total"),
            func.sum(
                case((UserKnowledgeState.status == "mastered", 1), else_=0)
            ).label("mastered"),
        )
        .where(UserKnowledgeState.user_id == user.id)
        .group_by(UserKnowledgeState.subject_id)
        .limit(1)
    )
    # Sort in Python instead of SQL (avoid SQLite ORDER BY expression issues)
    all_subj_rows = list(subj_res.all())
    all_subj_rows.sort(
        key=lambda r: (r.mastered / r.total) if r.total > 0 else 0,
        reverse=True,
    )
    best_row = all_subj_rows[0] if all_subj_rows else None
    if best_row and best_row.total > 0:
        s_res = await db.execute(select(Subject.name).where(Subject.id == best_row.subject_id))
        s_name = s_res.scalar_one_or_none() or ""
        best_pct = round(best_row.mastered / best_row.total, 3)
        best_subject = {"subject_id": str(best_row.subject_id), "subject_name": s_name, "mastery_pct": best_pct}

    # Weak points
    weak_res = await db.execute(
        select(
            func.sum(case((UserKnowledgeState.status == "weak", 1), else_=0)),
            func.sum(case((UserKnowledgeState.status == "consolidating", 1), else_=0)),
        ).where(UserKnowledgeState.user_id == user.id)
    )
    weak_count, consolidating_count = weak_res.one()
    weak_points = ShareCardWeakPoints(
        weak=int(weak_count or 0),
        consolidating=int(consolidating_count or 0),
    )

    # Class
    class_info = None
    if user.class_id:
        c_res = await db.execute(select(Class).where(Class.id == user.class_id))
        cls = c_res.scalar_one_or_none()
        if cls:
            class_info = ShareCardClass(id=str(cls.id), name=cls.name)

    # Exam (closest active plan with exam_date)
    exam_info = None
    plan_res = await db.execute(
        select(Plan).where(
            Plan.user_id == user.id,
            Plan.status == "active",
            Plan.exam_date.isnot(None),
        ).order_by(Plan.exam_date.asc()).limit(1)
    )
    plan = plan_res.scalar_one_or_none()
    if plan and plan.exam_date:
        # Get subject name
        subj_r = await db.execute(select(Subject.name).where(Subject.id == plan.subject_id))
        subj_name = subj_r.scalar_one_or_none() or ""
        days_left = (plan.exam_date - today).days if hasattr(plan.exam_date, '__sub__') else 0
        exam_info = ShareCardExam(subject_name=subj_name, days_left=max(days_left, 0))

    return ShareCardResponse(
        username=user.username,
        generated_at=now,
        share_card_version=1,
        totals=ShareCardTotals(
            questions_practiced=total_qp,
            correct_count=total_correct,
            accuracy=total_acc,
        ),
        recent_7d=ShareCardTotals(
            questions_practiced=r7_qp,
            correct_count=r7_correct,
            accuracy=r7_acc,
        ),
        streak=ShareCardStreak(current=current_streak, longest=longest_streak),
        mastery=ShareCardMastery(overall_pct=overall_pct, best_subject=best_subject),
        weak_points=weak_points,
        class_=class_info,
        exam=exam_info,
    )
