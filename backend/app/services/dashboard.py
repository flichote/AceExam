"""Dashboard service -- aggregation queries (M3 §11.4/§11.5).

Inline implementation per T15 until T17 delivers. Architecture.md §11.4:
all dashboard stats are real-time derived from study_sessions + user_knowledge_states.
"""

import uuid
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import literal_column

from app.db.models import (
    KnowledgePoint,
    Plan,
    StudySession,
    Subject,
    UserKnowledgeState,
)
from app.services.streak import compute_streak


async def get_dashboard(
    db: AsyncSession,
    user_id: uuid.UUID,
    subject_id: uuid.UUID | None = None,
) -> dict:
    """Build dashboard summary for a user."""
    today = date.today()

    # ── Totals ──
    total_filter = [StudySession.user_id == user_id]
    if subject_id:
        total_filter.append(StudySession.subject_id == subject_id)

    total_result = await db.execute(
        select(
            func.coalesce(func.sum(StudySession.questions_practiced), 0),
            func.coalesce(func.sum(StudySession.correct_count), 0),
        ).where(*total_filter)
    )
    total_row = total_result.one()
    questions_practiced = total_row[0]
    correct_count = total_row[1]
    accuracy = round(correct_count / questions_practiced, 3) if questions_practiced > 0 else 0.0

    # ── Mastery (leaf KPs only, filtered by subject) ──
    mastery_filter = [UserKnowledgeState.user_id == user_id]
    if subject_id:
        mastery_filter.append(UserKnowledgeState.subject_id == subject_id)

    # Total leaf KPs for subject(s)
    leaf_filter = [KnowledgePoint.level == 3]
    if subject_id:
        leaf_filter.append(KnowledgePoint.subject_id == subject_id)

    leaf_total_result = await db.execute(
        select(func.count(KnowledgePoint.id)).where(*leaf_filter)
    )
    leaf_total = leaf_total_result.scalar() or 0

    mastered_result = await db.execute(
        select(func.count(UserKnowledgeState.id))
        .where(
            UserKnowledgeState.status == "mastered",
            *mastery_filter,
        )
    )
    mastered = mastered_result.scalar() or 0
    mastery_pct = round(mastered / leaf_total, 3) if leaf_total > 0 else 0.0

    # ── Streak ──
    streak_filter = [StudySession.user_id == user_id, StudySession.checked_in == True]
    if subject_id:
        streak_filter.append(StudySession.subject_id == subject_id)

    streak_result = await db.execute(
        select(StudySession.session_date)
        .where(*streak_filter)
        .order_by(StudySession.session_date.asc())
    )
    dates = [row[0] for row in streak_result.all()]
    current_streak, longest_streak = compute_streak(dates, today=today)

    # ── Weak points ──
    weak_filter = [
        UserKnowledgeState.user_id == user_id,
        UserKnowledgeState.status.in_(["weak", "consolidating"]),
    ]
    if subject_id:
        weak_filter.append(UserKnowledgeState.subject_id == subject_id)

    weak_result = await db.execute(
        select(
            func.count(UserKnowledgeState.id).filter(UserKnowledgeState.status == "weak"),
            func.count(UserKnowledgeState.id).filter(UserKnowledgeState.status == "consolidating"),
        ).where(*weak_filter)
    )
    weak_row = weak_result.one()
    weak_count = weak_row[0] or 0
    consolidating_count = weak_row[1] or 0

    # ── Per-subject breakdown ──
    per_subject = []
    if not subject_id:
        # Group by subject for all subjects user has sessions for
        ps_result = await db.execute(
            select(
                StudySession.subject_id,
                func.sum(StudySession.questions_practiced),
                func.sum(StudySession.correct_count),
            )
            .where(StudySession.user_id == user_id)
            .group_by(StudySession.subject_id)
        )
        for row in ps_result:
            sid = row[0]
            sq = row[1]
            sc = row[2]
            sa = round(sc / sq, 3) if sq > 0 else 0.0

            subj_result = await db.execute(select(Subject).where(Subject.id == sid))
            subj = subj_result.scalar_one_or_none()
            subj_name = subj.name if subj else "Unknown"

            # Mastery for this subject
            sm_result = await db.execute(
                select(func.count(UserKnowledgeState.id))
                .where(
                    UserKnowledgeState.user_id == user_id,
                    UserKnowledgeState.subject_id == sid,
                    UserKnowledgeState.status == "mastered",
                )
            )
            sm = sm_result.scalar() or 0
            sl_result = await db.execute(
                select(func.count(KnowledgePoint.id))
                .where(KnowledgePoint.subject_id == sid, KnowledgePoint.level == 3)
            )
            sl = sl_result.scalar() or 1
            sm_pct = round(sm / sl, 3) if sl > 0 else 0.0

            per_subject.append({
                "subject_id": str(sid),
                "subject_name": subj_name,
                "questions_practiced": sq,
                "correct_count": sc,
                "accuracy": sa,
                "mastery_pct": sm_pct,
            })

    # ── Exam info ──
    exam_filter = [Plan.user_id == user_id, Plan.status == "active"]
    if subject_id:
        exam_filter.append(Plan.subject_id == subject_id)

    plan_result = await db.execute(
        select(Plan).where(*exam_filter).order_by(Plan.exam_date.nulls_last()).limit(1)
    )
    plan = plan_result.scalar_one_or_none()
    has_active_plan = plan is not None
    days_left = (plan.exam_date - today).days if (plan and plan.exam_date) else None

    return {
        "totals": {
            "questions_practiced": questions_practiced,
            "correct_count": correct_count,
            "accuracy": accuracy,
        },
        "mastery": {
            "leaf_total": leaf_total,
            "mastered": mastered,
            "mastery_pct": mastery_pct,
        },
        "streak": {
            "current": current_streak,
            "longest": longest_streak,
        },
        "weak_points": {
            "weak": weak_count,
            "consolidating": consolidating_count,
        },
        "per_subject": per_subject,
        "exam": {
            "has_active_plan": has_active_plan,
            "days_left": days_left,
        },
    }


async def get_dashboard_trend(
    db: AsyncSession,
    user_id: uuid.UUID,
    days: int = 30,
    subject_id: uuid.UUID | None = None,
    granularity: str = "day",
) -> dict:
    """Build time-series trend data."""
    end_date = date.today()
    start_date = end_date - timedelta(days=days - 1)

    # ── Study session bucketing ──
    base_filter = [
        StudySession.user_id == user_id,
        StudySession.session_date >= start_date,
        StudySession.session_date <= end_date,
    ]
    if subject_id:
        base_filter.append(StudySession.subject_id == subject_id)

    # Check if we're on PostgreSQL (supports date_trunc)
    is_pg = db.bind and db.bind.dialect.name == "postgresql"

    if is_pg:
        trunc_map = {"day": "day", "week": "week", "month": "month"}
        pg_trunc = trunc_map.get(granularity, "day")
        bucket_result = await db.execute(
            select(
                func.date_trunc(pg_trunc, StudySession.session_date).label("bucket"),
                func.coalesce(func.sum(StudySession.questions_practiced), 0).label("qp"),
                func.coalesce(func.sum(StudySession.correct_count), 0).label("cc"),
            )
            .where(*base_filter)
            .group_by(literal_column("bucket"))
            .order_by(literal_column("bucket"))
        )
        bucket_rows = {}
        for row in bucket_result.all():
            key = row[0] if isinstance(row[0], date) else row[0].date()
            bucket_rows[key] = (row[1], row[2])
    else:
        # SQLite fallback: fetch all rows and bucket in Python
        raw_result = await db.execute(
            select(
                StudySession.session_date,
                StudySession.questions_practiced,
                StudySession.correct_count,
            ).where(*base_filter).order_by(StudySession.session_date)
        )
        from collections import defaultdict
        raw_buckets: dict[date, tuple[int, int]] = defaultdict(lambda: (0, 0))
        for row in raw_result.all():
            d = row[0]
            bucket_key = d
            if granularity == "week":
                bucket_key = d - timedelta(days=d.weekday())
            elif granularity == "month":
                bucket_key = d.replace(day=1)
            qp, cc = raw_buckets[bucket_key]
            raw_buckets[bucket_key] = (qp + (row[1] or 0), cc + (row[2] or 0))
        bucket_rows = dict(raw_buckets)

    # ── Mastery as-of approximation ──
    mastery_filter = [
        UserKnowledgeState.user_id == user_id,
        UserKnowledgeState.status == "mastered",
    ]
    if subject_id:
        mastery_filter.append(UserKnowledgeState.subject_id == subject_id)

    # Get total leaf KP count for mastery_pct baseline
    leaf_filter = [KnowledgePoint.level == 3]
    if subject_id:
        leaf_filter.append(KnowledgePoint.subject_id == subject_id)
    leaf_total_result = await db.execute(
        select(func.count(KnowledgePoint.id)).where(*leaf_filter)
    )
    leaf_total = leaf_total_result.scalar() or 1

    # Build trend items
    items = []
    current = start_date
    while current <= end_date:
        bucket_key = current
        if granularity == "week":
            bucket_key = current - timedelta(days=current.weekday())
        elif granularity == "month":
            bucket_key = current.replace(day=1)

        qp, cc = bucket_rows.get(bucket_key, (0, 0))
        acc = round(cc / qp, 3) if qp > 0 else None

        # As-of mastery: count mastered points with updated_at <= bucket_end
        bucket_end = current
        if granularity == "week":
            bucket_end = bucket_key + timedelta(days=6)
        elif granularity == "month":
            next_month = bucket_key.replace(day=28) + timedelta(days=4)
            bucket_end = next_month - timedelta(days=next_month.day)

        mastered_kp_result = await db.execute(
            select(func.count(UserKnowledgeState.id))
            .where(
                *mastery_filter,
                UserKnowledgeState.updated_at <= datetime.combine(bucket_end, datetime.max.time(), tzinfo=timezone.utc),
            )
        )
        mastered_kp_count = mastered_kp_result.scalar() or 0

        items.append({
            "bucket_start": bucket_key.isoformat(),
            "questions_practiced": qp,
            "correct_count": cc,
            "accuracy": acc,
            "mastered_kp_count": mastered_kp_count,
            "mastery_pct": round(mastered_kp_count / leaf_total, 3) if leaf_total > 0 else 0.0,
        })

        if granularity == "day":
            current += timedelta(days=1)
        elif granularity == "week":
            current += timedelta(days=7)
        else:
            next_month = current.replace(day=28) + timedelta(days=4)
            current = next_month - timedelta(days=next_month.day - 1)

    return {
        "granularity": granularity,
        "items": items,
    }
