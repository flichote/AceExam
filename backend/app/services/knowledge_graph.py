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


# ═══════════════════════════════════════════════════════════════════════════
# AI-enhanced functions (T17)
# ═══════════════════════════════════════════════════════════════════════════

import json
import logging

from app.services.llm_gateway import llm_gateway

logger = logging.getLogger(__name__)


async def ai_enhance_graph_nodes(
    nodes: list[dict],
) -> list[dict]:
    """Use LLM (flash) to enhance graph nodes with study notes and recommended order.

    Args:
        nodes: list of graph node dicts with {id, name, level, status, accuracy,
               practice_count, children}

    Returns:
        Same nodes with added study_note and recommended_order fields
    """
    if not nodes:
        return []

    # Only send leaf nodes (level==3) to LLM for efficiency
    leaf_nodes = [n for n in nodes if n.get("level") == 3]
    if not leaf_nodes:
        # No leaf nodes: add basic defaults
        for node in nodes:
            node["study_note"] = ""
            node["recommended_order"] = 99
        return nodes

    system_prompt = (
        "你是一位大学课程知识图谱分析师。请根据知识点的掌握状态，"
        "为每个知识点生成简短学习备注和推荐学习顺序。\n"
        "输出 JSON 格式：\n"
        '{{"enhanced_nodes": [{{"id": "节点ID", "study_note": "学习建议（15字以内）", '
        '"recommended_order": 学习优先级（1最高）}}]}}\n'
        "weak 状态优先、consolidating 次之、mastered 最后、untouched 可穿插。"
    )

    nodes_text = json.dumps(leaf_nodes, ensure_ascii=False, indent=2)
    user_prompt = (
        f"以下是一个学生知识点的掌握状态（json）。请为每个节点添加学习备注和推荐顺序：\n\n"
        f"{nodes_text}\n\n"
        f"请以 JSON 格式输出增强结果。"
    )

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]

    try:
        result = await llm_gateway.chat(
            tier="flash",
            messages=messages,
            temperature=0.4,
        )
        content = result.get("content", "")
        parsed = json.loads(content)
        enhanced = parsed.get("enhanced_nodes", [])

        # Build lookup by id
        enhance_map: dict[str, dict] = {}
        for en in enhanced:
            enhance_map[en.get("id", "")] = en

        # Merge back into original nodes
        for node in nodes:
            nid = node.get("id", "")
            en = enhance_map.get(nid, {})
            node["study_note"] = en.get("study_note", _default_note(node.get("status", "")))
            node["recommended_order"] = en.get("recommended_order", 99)

        # Sort by recommended_order for top-level convenience
        nodes.sort(key=lambda n: n.get("recommended_order", 99))
        return nodes
    except (json.JSONDecodeError, KeyError, Exception) as e:
        logger.warning("ai_enhance_graph_nodes LLM failed: %s, falling back to rules", e)
        return _rule_based_enhance_nodes(nodes)


def _default_note(status: str) -> str:
    """Default study note based on status."""
    notes = {
        "weak": "需重点突破",
        "consolidating": "继续巩固",
        "mastered": "已掌握",
        "untouched": "尽快开始",
    }
    return notes.get(status, "")


def _rule_based_enhance_nodes(nodes: list[dict]) -> list[dict]:
    """Rule-based fallback: add notes and order based on status."""
    status_order = {"weak": 1, "consolidating": 2, "untouched": 3, "mastered": 4}
    for node in nodes:
        status = node.get("status", "untouched")
        node["study_note"] = _default_note(status)
        node["recommended_order"] = status_order.get(status, 99)
    nodes.sort(key=lambda n: n.get("recommended_order", 99))
    return nodes


async def ai_summarize_graph_status(
    stats: dict,
) -> dict:
    """Use LLM (pro) to generate an overall summary of knowledge graph status.

    Args:
        stats: {total_nodes, mastered_count, weak_count, consolidating_count,
               untouched_count}

    Returns:
        {summary, mastery_rate, risk_areas, recommendation}
    """
    total = stats.get("total_nodes", 0)
    if total == 0:
        return {
            "summary": "暂无知识点数据",
            "mastery_rate": 0.0,
            "risk_areas": [],
            "recommendation": "请先添加知识点",
        }

    mastery_rate = stats.get("mastered_count", 0) / total

    system_prompt = (
        "你是一位大学课程学习分析师。请根据知识图谱统计数据，"
        "生成总体学习状况摘要和建议。\n"
        "输出 JSON 格式：\n"
        '{{"summary": "总体摘要（50-100字）", '
        '"mastery_rate": 掌握率(0-1), '
        '"risk_areas": ["高风险领域1", "高风险领域2"], '
        '"recommendation": "综合建议（50-100字）"}}\n'
    )

    stats_text = json.dumps(stats, ensure_ascii=False)
    user_prompt = (
        f"以下是知识图谱统计数据（json）：\n\n"
        f"{stats_text}\n\n"
        f"请以 JSON 格式输出学习状况分析和建议。"
    )

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]

    try:
        result = await llm_gateway.chat(
            tier="pro",
            messages=messages,
            temperature=0.4,
        )
        content = result.get("content", "")
        parsed = json.loads(content)
        return {
            "summary": parsed.get("summary", _rule_summary(stats)),
            "mastery_rate": parsed.get("mastery_rate", round(mastery_rate, 2)),
            "risk_areas": parsed.get("risk_areas", []),
            "recommendation": parsed.get("recommendation", _rule_recommendation(stats)),
        }
    except (json.JSONDecodeError, KeyError, Exception) as e:
        logger.warning("ai_summarize_graph_status LLM failed: %s", e)
        return {
            "summary": _rule_summary(stats),
            "mastery_rate": round(mastery_rate, 2),
            "risk_areas": [],
            "recommendation": _rule_recommendation(stats),
        }


def _rule_summary(stats: dict) -> str:
    total = stats.get("total_nodes", 0)
    mastered = stats.get("mastered_count", 0)
    weak = stats.get("weak_count", 0)
    untouched = stats.get("untouched_count", 0)
    rate = int(mastered / max(total, 1) * 100)
    return (
        f"已掌握{rate}%知识点（{mastered}/{total}），"
        f"{weak}个薄弱需重点突破，"
        f"{untouched}个未接触需尽快启动"
    )


def _rule_recommendation(stats: dict) -> str:
    weak = stats.get("weak_count", 0)
    untouched = stats.get("untouched_count", 0)
    consolidating = stats.get("consolidating_count", 0)
    if weak > 0:
        return f"优先处理{weak}个薄弱知识点，每天安排2-3个知识点的专项练习"
    elif consolidating > 0:
        return f"继续巩固{consolidating}个待巩固知识点，进行综合练习"
    elif untouched > 0:
        return f"尽快启动{untouched}个未接触知识点的学习"
    else:
        return "进行全真模拟考试，查漏补缺"
