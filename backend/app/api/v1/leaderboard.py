"""Leaderboard router (M3 §11.6)."""
import uuid
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db import get_db
from app.db.models import StudySession, User
from app.schemas.leaderboard import LeaderboardItem, LeaderboardMe, LeaderboardResponse
from app.services.streak import compute_streak

router = APIRouter(tags=["leaderboard"])


_MIN_SAMPLE = 30  # minimum questions to qualify
_MIN_ACCURACY = 0.1  # below this → suspicious, excluded


@router.get("/leaderboard", response_model=LeaderboardResponse)
async def leaderboard(
    scope: str = Query("global", pattern="^(global|subject)$"),
    subject_id: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if scope == "subject" and not subject_id:
        raise HTTPException(status_code=422, detail="subject_id is required when scope=subject")

    sid_filter = [StudySession.subject_id == uuid.UUID(subject_id)] if subject_id else []

    # Aggregate per user
    agg_query = (
        select(
            StudySession.user_id,
            func.sum(StudySession.questions_practiced).label("total_q"),
            func.sum(StudySession.correct_count).label("total_correct"),
        )
        .group_by(StudySession.user_id)
    )
    if sid_filter:
        agg_query = agg_query.where(*sid_filter)

    agg_result = await db.execute(agg_query)
    all_users = list(agg_result.all())

    # Filter: questions_practiced >= 30, accuracy >= 0.1
    qualified = []
    suspicious = set()
    for row in all_users:
        total_q = row.total_q or 0
        total_c = row.total_correct or 0
        if total_q < _MIN_SAMPLE:
            continue
        acc = total_c / total_q if total_q > 0 else 0.0
        if acc < _MIN_ACCURACY:
            suspicious.add(row.user_id)
            continue
        qualified.append((row.user_id, total_q, total_c, acc))

    # Sort: total_correct DESC, accuracy DESC
    qualified.sort(key=lambda x: (x[2], x[3]), reverse=True)

    total = len(qualified)

    # Paginate
    start = (page - 1) * page_size
    page_items = qualified[start:start + page_size]

    # Get usernames and streaks
    user_ids = [uid for uid, _, _, _ in page_items]
    user_map: dict[uuid.UUID, str] = {}
    if user_ids:
        user_result = await db.execute(
            select(User.id, User.username).where(User.id.in_(user_ids))
        )
        for uid, uname in user_result:
            user_map[uid] = uname

    # Build items
    today = date.today()
    items = []
    for rank, (uid, total_q, total_c, acc) in enumerate(page_items, start=start + 1):
        # Get streak for this user
        streak_result = await db.execute(
            select(StudySession.session_date)
            .where(
                StudySession.user_id == uid,
                StudySession.checked_in == True,
            )
            .order_by(StudySession.session_date.asc())
        )
        streak_dates = [r[0] for r in streak_result.all()]
        current_streak, _ = compute_streak(streak_dates, today=today)

        items.append(LeaderboardItem(
            rank=rank,
            user_id=str(uid),
            username=user_map.get(uid, "Unknown"),
            total_correct=total_c,
            questions_practiced=total_q,
            accuracy=round(acc, 3),
            current_streak=current_streak,
        ))

    # Me: current user's rank
    me = None
    me_uid = user.id
    me_qp = 0
    me_correct = 0
    for uid, total_q, total_c, acc in qualified:
        if uid == me_uid:
            me_qp = total_q
            me_correct = total_c
    if me_qp >= _MIN_SAMPLE or me_qp > 0:
        me_acc = me_correct / me_qp if me_qp > 0 else 0.0
        me_rank = None
        if me_qp >= _MIN_SAMPLE and me_acc >= _MIN_ACCURACY and (me_uid not in suspicious):
            me_rank = next(
                (i + 1 for i, (uid, _, _, _) in enumerate(qualified) if uid == me_uid),
                None,
            )
        me = LeaderboardMe(
            rank=me_rank,
            total_correct=me_correct,
            questions_practiced=me_qp,
            accuracy=round(me_acc, 3),
        )

    return LeaderboardResponse(
        scope=scope,
        items=items,
        page=page,
        page_size=page_size,
        total=total,
        me=me,
    )
