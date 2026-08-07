"""Knowledge graph service -- tree assembly + status aggregation (M3 §11.1).

Inline implementation per T15 until T17 delivers. See architecture.md §11.1 for
design: three-level tree (chapter→section→knowledge point) with status from
user_knowledge_states, aggregated bottom-up (worst-child-wins).
"""

import uuid
from collections import defaultdict

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import KnowledgePoint, Question, UserKnowledgeState


async def build_knowledge_graph(
    db: AsyncSession,
    subject_id: uuid.UUID,
    user_id: uuid.UUID,
    include_questions: bool = True,
) -> dict:
    """Build the knowledge tree for a subject.

    Returns:
        dict with keys: subject_id, subject_name, generated_at, roots, stats
    """
    from datetime import datetime, timezone

    # 1) Fetch all knowledge points for the subject
    kp_result = await db.execute(
        select(KnowledgePoint)
        .where(KnowledgePoint.subject_id == subject_id)
        .order_by(KnowledgePoint.sort_order)
    )
    all_kps = list(kp_result.scalars().all())

    if not all_kps:
        return None

    # 2) Fetch user knowledge states
    kp_ids = [k.id for k in all_kps]
    state_result = await db.execute(
        select(UserKnowledgeState).where(
            UserKnowledgeState.user_id == user_id,
            UserKnowledgeState.knowledge_point_id.in_(kp_ids),
        )
    )
    states: dict[uuid.UUID, UserKnowledgeState] = {
        s.knowledge_point_id: s for s in state_result.scalars().all()
    }

    # 3) Question counts per KP (if requested)
    question_counts: dict[uuid.UUID, int] = {}
    if include_questions:
        q_result = await db.execute(
            select(
                Question.knowledge_point_id,
                func.count(Question.id).label("cnt"),
            )
            .where(
                Question.subject_id == subject_id,
                Question.status == "active",
            )
            .group_by(Question.knowledge_point_id)
        )
        for row in q_result:
            question_counts[row.knowledge_point_id] = row.cnt

    # 4) Build node map
    nodes: dict[uuid.UUID, dict] = {}
    for kp in all_kps:
        state = states.get(kp.id)
        status = state.status if state else "untouched"
        qc = question_counts.get(kp.id, 0)

        node = {
            "id": str(kp.id),
            "name": kp.name,
            "level": kp.level,
            "status": status,
            "question_count": qc,
            "children": [],
        }

        if kp.level == 3 and state is not None and include_questions:
            total = state.correct_count + state.wrong_count
            node["practice_count"] = total
            node["accuracy"] = round(state.correct_count / total, 3) if total > 0 else None

        nodes[kp.id] = node

    # 5) Build tree: link children to parents
    roots: list[dict] = []
    for kp in all_kps:
        node = nodes[kp.id]
        if kp.parent_id and kp.parent_id in nodes:
            nodes[kp.parent_id]["children"].append(node)
        else:
            roots.append(node)

    # 6) Aggregate parent statuses bottom-up (post-order DFS)
    def aggregate_status(n: dict) -> str:
        children = n.get("children", [])
        if not children:
            return n["status"]

        child_statuses = [aggregate_status(c) for c in children]

        # Sum question counts
        n["question_count"] = sum(c.get("question_count", 0) for c in children)

        if any(s == "weak" for s in child_statuses):
            status = "weak"
        elif any(s == "consolidating" for s in child_statuses):
            status = "consolidating"
        elif all(s == "mastered" for s in child_statuses):
            status = "mastered"
        else:
            status = "untouched"

        n["status"] = status
        return status

    for root in roots:
        aggregate_status(root)

    # 7) Stats
    leaf_count = sum(1 for k in all_kps if k.level == 3)
    all_statuses = [nodes[k.id]["status"] for k in all_kps]

    # Only count leaf nodes for mastery/weak stats
    leaf_statuses = [nodes[k.id]["status"] for k in all_kps if k.level == 3]

    stats = {
        "total_nodes": len(all_kps),
        "leaf_count": leaf_count,
        "mastered_count": leaf_statuses.count("mastered"),
        "weak_count": leaf_statuses.count("weak"),
        "consolidating_count": leaf_statuses.count("consolidating"),
        "untouched_count": leaf_statuses.count("untouched"),
    }

    # Wrap single root if there's only one
    root = roots[0] if len(roots) == 1 else None

    return {
        "subject_id": str(subject_id),
        "subject_name": "",
        "generated_at": datetime.now(timezone.utc),
        "root": root,
        "stats": stats,
    }
