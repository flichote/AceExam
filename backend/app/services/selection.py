"""Adaptive question selection -- MVP rule-based scorer (M2).

This is T9's inline implementation per architecture.md section 10.1 formula.
When T10 delivers selection.py, replace this file with the real implementation.
"""
import math
import random
import uuid
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import KnowledgePoint, Question, UserKnowledgeState


def _is_postgres(db: AsyncSession) -> bool:
    """当前会话方言是否为 PostgreSQL（用于 SQLite 本地开发的语法降级）。"""
    return db.bind and db.bind.dialect.name == "postgresql"


def status_factor(status: str) -> float:
    """Map knowledge state status to selection priority weight."""
    return {
        "weak": 1.0,
        "consolidating": 0.6,
        "untouched": 0.35,
        "mastered": 0.05,
    }.get(status, 0.35)


def error_factor(correct_count: int, wrong_count: int) -> float:
    """Laplace-smoothed error rate (0..1)."""
    return (wrong_count + 1) / (correct_count + wrong_count + 2)


def recency_factor(kp: UserKnowledgeState) -> float:
    """Days since last practice, capped at 7 days. Never practiced = 7 days (max)."""
    if kp.last_practiced_at is None:
        return 1.0
    days = (datetime.now(timezone.utc) - kp.last_practiced_at).days
    return min(days, 7) / 7.0


def difficulty_factor(q_difficulty: int, target_difficulty: int) -> float:
    """Proximity to target difficulty (0..1)."""
    return max(0.0, 1.0 - abs(q_difficulty - target_difficulty) / 4.0)


def compute_score(
    kp: UserKnowledgeState,
    weights: dict[str, float] | None = None,
    target_difficulty: int = 3,
    question_difficulty: int = 3,
) -> float:
    """Compute selection score for a knowledge point.

    Default weights (50, 35, 10, 5) per architecture.md section 10.1.
    """
    w = weights or {"status": 50, "error": 35, "recency": 10, "difficulty": 5}
    return (
        w.get("status", 50) * status_factor(kp.status)
        + w.get("error", 35) * error_factor(kp.correct_count, kp.wrong_count)
        + w.get("recency", 10) * recency_factor(kp)
        + w.get("difficulty", 5) * difficulty_factor(question_difficulty, target_difficulty)
    )


async def select_practice_questions(
    db: AsyncSession,
    subject_id: uuid.UUID,
    user_id: uuid.UUID,
    count: int = 10,
    knowledge_point_id: uuid.UUID | None = None,
    exclude_ids: list[str] | None = None,
    difficulty: int | None = None,
) -> tuple[list[Question], list[dict]]:
    """Select adaptive questions for practice session.

    Returns: (questions, strategy_target_kps)
    """
    exclude_uuids = {uuid.UUID(e) for e in (exclude_ids or [])}
    target_diff = difficulty or 3

    # Get all leaf knowledge points for the subject with user states
    kp_query = select(KnowledgePoint).where(
        KnowledgePoint.subject_id == subject_id,
        KnowledgePoint.level == 3,  # leaf nodes only
    )
    kp_result = await db.execute(kp_query)
    kps = kp_result.scalars().all()

    if not kps:
        return [], []

    kp_ids = [k.id for k in kps]

    # Get user knowledge states
    state_query = select(UserKnowledgeState).where(
        UserKnowledgeState.user_id == user_id,
        UserKnowledgeState.knowledge_point_id.in_(kp_ids),
    )
    state_result = await db.execute(state_query)
    states = {s.knowledge_point_id: s for s in state_result.scalars().all()}

    # If filtered by KP, only consider that one
    if knowledge_point_id:
        kps = [k for k in kps if k.id == knowledge_point_id]
        if not kps:
            return [], []

    # Compute scores
    scored = []
    for kp in kps:
        state = states.get(kp.id, UserKnowledgeState(
            user_id=user_id,
            knowledge_point_id=kp.id,
            subject_id=subject_id,
            status="untouched",
            correct_count=0,
            wrong_count=0,
        ))
        score = compute_score(state, target_difficulty=target_diff)
        scored.append((kp, state, score))

    scored.sort(key=lambda x: x[2], reverse=True)

    # Exploration rate epsilon=0.3: 70% from top, 30% random from rest
    epsilon = 0.3
    n_top = max(1, int(len(scored) * (1 - epsilon)))
    top_kps = scored[:n_top]
    rest_kps = scored[n_top:]

    selected_kps = list(top_kps)
    if rest_kps:
        n_random = min(len(rest_kps), max(1, int(len(scored) * epsilon)))
        selected_kps += random.sample(rest_kps, n_random)

    # Strategy metadata for response
    target_kps = []
    for kp, state, score in selected_kps[:5]:
        pct = state.correct_count / max(state.correct_count + state.wrong_count, 1)
        target_kps.append({
            "id": str(kp.id),
            "name": kp.name,
            "level": kp.level,
            "status": state.status,
            "score": round(score, 2),
            "reason": "accuracy {:.0%}, {}".format(pct, "weak priority" if state.status == "weak" else "consolidating" if state.status == "consolidating" else "unpracticed"),
        })

    # Fetch questions for selected KPs
    questions = []
    questions_per_kp = max(1, count // len(selected_kps)) if selected_kps else count

    for kp, state, score in selected_kps:
        q_query = (
            select(Question)
            .where(
                Question.knowledge_point_id == kp.id,
                Question.status == "active",
                Question.id.notin_(exclude_uuids),
            )
            .order_by(
                # PG: `<=>` null-safe 等值比较（difficulty 越接近 target 越优先）
                # SQLite: 不支持 <=>，降级为按难度绝对值距离排序（本地开发等价行为）
                Question.difficulty.op("<=>")(target_diff)  # type: ignore[operator]
                if _is_postgres(db)
                else func.abs(Question.difficulty - target_diff),
            )
            .limit(questions_per_kp + 1)
        )
        q_result = await db.execute(q_query)
        kp_questions = q_result.scalars().all()
        for q in kp_questions:
            if len(questions) < count and q.id not in exclude_uuids:
                questions.append(q)
                exclude_uuids.add(q.id)

    return questions, target_kps


async def select_self_test_questions(
    db: AsyncSession,
    subject_id: uuid.UUID,
    user_id: uuid.UUID,
    count: int = 10,
    include_weak: bool = True,
) -> list[Question]:
    """Select questions for diagnostic self-test.
    Stratified sampling: at least 1 question per chapter, remainder by weakness weight.
    """
    # Get chapters (level=1 KPs)
    chapter_query = select(KnowledgePoint).where(
        KnowledgePoint.subject_id == subject_id,
        KnowledgePoint.level == 1,
    )
    chapter_result = await db.execute(chapter_query)
    chapters = chapter_result.scalars().all()

    selected_questions: list[Question] = []
    selected_ids: set[uuid.UUID] = set()

    # 1 question per chapter
    for chapter in chapters:
        # Get leaf KPs under this chapter
        leaf_query = select(KnowledgePoint).where(
            KnowledgePoint.subject_id == subject_id,
            KnowledgePoint.level == 3,
            KnowledgePoint.name.like(f"{chapter.name}%"),  # approximate chapter match
        ).limit(50)
        leaf_result = await db.execute(leaf_query)
        leaves = leaf_result.scalars().all()

        # Get a question from any leaf under this chapter
        for leaf in leaves:
            q_query = select(Question).where(
                Question.knowledge_point_id == leaf.id,
                Question.status == "active",
            ).limit(1)
            q_result = await db.execute(q_query)
            q = q_result.scalar_one_or_none()
            if q and q.id not in selected_ids:
                selected_questions.append(q)
                selected_ids.add(q.id)
                break

    # Fill remaining with weakness-weighted selection
    remaining = count - len(selected_questions)
    if remaining > 0 and include_weak:
        # Get weak/consolidating KPs
        state_query = select(UserKnowledgeState).where(
            UserKnowledgeState.user_id == user_id,
            UserKnowledgeState.subject_id == subject_id,
            UserKnowledgeState.status.in_(["weak", "consolidating"]),
        ).order_by(UserKnowledgeState.correct_count.asc()).limit(remaining * 2)
        state_result = await db.execute(state_query)
        weak_states = state_result.scalars().all()

        for state in weak_states:
            if len(selected_questions) >= count:
                break
            q_query = select(Question).where(
                Question.knowledge_point_id == state.knowledge_point_id,
                Question.status == "active",
                Question.id.notin_(selected_ids),
            ).limit(1)
            q_result = await db.execute(q_query)
            q = q_result.scalar_one_or_none()
            if q:
                selected_questions.append(q)
                selected_ids.add(q.id)

    # If still short, fill with random active questions
    if len(selected_questions) < count:
        q_query = select(Question).where(
            Question.subject_id == subject_id,
            Question.status == "active",
            Question.id.notin_(selected_ids),
        ).limit(count - len(selected_questions))
        q_result = await db.execute(q_query)
        for q in q_result.scalars().all():
            selected_questions.append(q)

    return selected_questions[:count]
