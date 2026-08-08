"""Sprint service -- activation + question list generation (M3 §11.2/§11.3).

Inline implementation per T15 until T17 delivers. See architecture.md §11.2.
- High-frequency KP identification: rule-based from user_knowledge_states
- Question selection: high_freq KPs + personal wrong answers, deduped
- Activation: idempotent (returns existing if active), auto-activates when days_left ≤ 7
"""

import uuid
from datetime import date, datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import (
    KnowledgePoint,
    Plan,
    Question,
    SprintSession,
    UserKnowledgeState,
    WrongAnswer,
)


async def activate_sprint(
    db: AsyncSession,
    subject_id: uuid.UUID,
    user_id: uuid.UUID,
) -> tuple[dict, bool]:
    """Activate a sprint session. Idempotent: returns existing if active.

    Returns: (sprint_dict, created_bool)
    """
    # Check existing active session
    existing = await db.execute(
        select(SprintSession).where(
            SprintSession.user_id == user_id,
            SprintSession.subject_id == subject_id,
            SprintSession.status == "active",
        )
    )
    active = existing.scalar_one_or_none()

    # Check if exam date has passed → expire old and create new
    today = date.today()
    if active and active.expires_at and active.expires_at < today:
        active.status = "expired"
        await db.commit()
        active = None

    if active:
        return _sprint_to_dict(active), False

    # Look up active plan for exam_date
    plan_result = await db.execute(
        select(Plan).where(
            Plan.user_id == user_id,
            Plan.subject_id == subject_id,
            Plan.status == "active",
        ).order_by(Plan.exam_date.nulls_last()).limit(1)
    )
    plan = plan_result.scalar_one_or_none()

    exam_date = plan.exam_date if plan and plan.exam_date else None
    days_left = (exam_date - today).days if exam_date else None

    sprint = SprintSession(
        user_id=user_id,
        subject_id=subject_id,
        status="active",
        auto_activated=False,
        expires_at=exam_date,
    )
    db.add(sprint)
    await db.commit()
    await db.refresh(sprint)

    return {
        "id": str(sprint.id),
        "subject_id": str(sprint.subject_id),
        "status": sprint.status,
        "activated_at": sprint.activated_at,
        "auto_activated": sprint.auto_activated,
        "exam_date": exam_date.isoformat() if exam_date else None,
        "days_left": days_left,
        "expires_at": exam_date.isoformat() if exam_date else None,
    }, True


def _sprint_to_dict(s: SprintSession) -> dict:
    today = date.today()
    days_left = (s.expires_at - today).days if s.expires_at else None
    return {
        "id": str(s.id),
        "subject_id": str(s.subject_id),
        "status": s.status,
        "activated_at": s.activated_at,
        "auto_activated": s.auto_activated,
        "exam_date": s.expires_at.isoformat() if s.expires_at else None,
        "days_left": days_left,
        "expires_at": s.expires_at.isoformat() if s.expires_at else None,
    }


async def get_or_auto_activate_sprint(
    db: AsyncSession,
    subject_id: uuid.UUID,
    user_id: uuid.UUID,
) -> SprintSession | None:
    """Get active sprint session or auto-activate if days_left ≤ 7."""
    existing = await db.execute(
        select(SprintSession).where(
            SprintSession.user_id == user_id,
            SprintSession.subject_id == subject_id,
            SprintSession.status == "active",
        )
    )
    active = existing.scalar_one_or_none()

    today = date.today()
    if active and active.expires_at and active.expires_at < today:
        active.status = "expired"
        await db.commit()
        active = None

    if active:
        return active

    # Check plan for auto-activation
    plan_result = await db.execute(
        select(Plan).where(
            Plan.user_id == user_id,
            Plan.subject_id == subject_id,
            Plan.status == "active",
        )
    )
    plan = plan_result.scalar_one_or_none()

    if plan and plan.exam_date:
        days_left = (plan.exam_date - today).days
        if days_left <= 7:
            sprint = SprintSession(
                user_id=user_id,
                subject_id=subject_id,
                status="active",
                auto_activated=True,
                expires_at=plan.exam_date,
            )
            db.add(sprint)
            await db.commit()
            await db.refresh(sprint)
            return sprint

    return None


async def generate_sprint_questions(
    db: AsyncSession,
    sprint: SprintSession,
    count: int = 20,
    mode: str = "review",
) -> dict:
    """Generate sprint question list (high-freq + wrong answers, deduped).

    If sprint already has a snapshot, return it (stable).
    """
    # Return cached snapshot if available
    if sprint.question_snapshot:
        snap = sprint.question_snapshot
        # 快照必须是 dict（{"items": [...], "sprint_id": ...}）才可复用；
        # 旧版本遗留的 list 快照（[{id, tag}, ...]）结构不完整，直接丢弃重新生成。
        if isinstance(snap, dict):
            snap_items = snap.get("items", [])
            # Check if snapshot items still exist
            item_ids = [uuid.UUID(i["id"]) for i in snap_items if isinstance(i, dict) and i.get("id")]
            if not item_ids:
                # 快照为空或结构异常 → 视为无缓存，重新生成
                sprint.question_snapshot = None
            else:
                q_check = await db.execute(
                    select(Question).where(Question.id.in_(item_ids))
                )
                alive_ids = {q.id for q in q_check.scalars().all()}
                if len(alive_ids) >= len(item_ids) * 0.8:  # at least 80% alive → reuse
                    return snap
        else:
            # 旧 list 格式：丢弃，走重新生成（下方统一写 dict）
            sprint.question_snapshot = None

    subject_id = sprint.subject_id
    user_id = sprint.user_id
    today = date.today()
    days_left = (sprint.expires_at - today).days if sprint.expires_at else None

    # 1) High-frequency KPs: heat = total_user_practice_count across all users
    heat_result = await db.execute(
        select(
            UserKnowledgeState.knowledge_point_id,
            func.sum(UserKnowledgeState.correct_count + UserKnowledgeState.wrong_count).label("heat"),
            func.sum(UserKnowledgeState.correct_count).label("total_correct"),
        )
        .join(KnowledgePoint, UserKnowledgeState.knowledge_point_id == KnowledgePoint.id)
        .where(
            KnowledgePoint.subject_id == subject_id,
            KnowledgePoint.level == 3,
        )
        .group_by(UserKnowledgeState.knowledge_point_id)
        .order_by(func.sum(UserKnowledgeState.correct_count + UserKnowledgeState.wrong_count).desc())
        .limit(10)
    )
    high_freq_rows = heat_result.all()

    high_freq_kps = []
    for row in high_freq_rows:
        total_q = row.heat or 0
        if total_q >= 20:  # threshold per architecture §11.2
            kp_result = await db.execute(
                select(KnowledgePoint).where(KnowledgePoint.id == row.knowledge_point_id)
            )
            kp = kp_result.scalar_one_or_none()
            if kp:
                avg_acc = (row.total_correct / total_q) if total_q > 0 else 0.0
                if avg_acc < 0.75:  # only include "difficult" high-freq KPs
                    # Check past_exam questions
                    pe_result = await db.execute(
                        select(func.count(Question.id)).where(
                            Question.knowledge_point_id == kp.id,
                            Question.source == "past_exam",
                            Question.status == "active",
                        )
                    )
                    pe_count = pe_result.scalar() or 0
                    high_freq_kps.append({
                        "id": str(kp.id),
                        "name": kp.name,
                        "heat": total_q,
                        "avg_accuracy": round(avg_acc, 2),
                        "has_past_exam": pe_count > 0,
                    })

    # Fallback: if no high-freq KPs, use KPs with past_exam questions
    if not high_freq_kps:
        pe_kps_result = await db.execute(
            select(Question.knowledge_point_id, func.count(Question.id).label("cnt"))
            .where(
                Question.subject_id == subject_id,
                Question.source == "past_exam",
                Question.status == "active",
            )
            .group_by(Question.knowledge_point_id)
            .order_by(func.count(Question.id).desc())
            .limit(5)
        )
        for row in pe_kps_result:
            kp_result = await db.execute(
                select(KnowledgePoint).where(KnowledgePoint.id == row.knowledge_point_id)
            )
            kp = kp_result.scalar_one_or_none()
            if kp:
                high_freq_kps.append({
                    "id": str(kp.id),
                    "name": kp.name,
                    "heat": row.cnt,
                    "avg_accuracy": 0.5,
                    "has_past_exam": True,
                })

    # 2) Personal wrong answers (unmastered)
    wa_result = await db.execute(
        select(WrongAnswer).where(
            WrongAnswer.user_id == user_id,
            WrongAnswer.subject_id == subject_id,
            WrongAnswer.mastered == False,
        ).order_by(WrongAnswer.created_at.desc()).limit(count)
    )
    wrong_answers = wa_result.scalars().all()

    # 3) Select questions: high-freq KPs first, then wrong answers, deduped
    selected_ids: set[uuid.UUID] = set()
    items: list[dict] = []
    high_freq_count = 0
    wrong_review_count = 0

    # High-freq: up to 3 questions per KP
    hf_slots = max(count - min(len(wrong_answers), count // 3), int(count * 0.7))
    for hf in high_freq_kps:
        if len(items) >= hf_slots:
            break
        kp_id = uuid.UUID(hf["id"])
        q_result = await db.execute(
            select(Question)
            .where(
                Question.knowledge_point_id == kp_id,
                Question.status == "active",
                Question.id.notin_(selected_ids),
            )
            .limit(3)
        )
        for q in q_result.scalars().all():
            if q.id not in selected_ids:
                selected_ids.add(q.id)
                items.append(_question_public(q, tag="high_freq"))
                high_freq_count += 1

    # Wrong answers: up to 2 per KP
    for wa in wrong_answers:
        if len(items) >= count:
            break
        q_result = await db.execute(
            select(Question).where(
                Question.id == wa.question_id,
                Question.status == "active",
                Question.id.notin_(selected_ids),
            )
        )
        q = q_result.scalar_one_or_none()
        if q and q.id not in selected_ids:
            selected_ids.add(q.id)
            items.append(_question_public(q, tag="wrong_review"))
            wrong_review_count += 1

    total = len(items)

    # 4) Build snapshot
    snapshot: dict = {
        "sprint_id": str(sprint.id),
        "status": sprint.status,
        "days_left": days_left,
        "high_freq_kps": high_freq_kps,
        "items": items,
        "summary": {
            "high_freq_questions": high_freq_count,
            "wrong_review_questions": wrong_review_count,
            "deduped": high_freq_count + wrong_review_count - total,
            "total": total,
        },
        "mock": None,
    }

    if mode == "mock":
        snapshot["mock"] = {
            "duration_min": 120,
            "total_score": 100,
            "started_at": None,
        }

    # Save snapshot
    sprint.question_snapshot = snapshot
    await db.commit()

    return snapshot


def _question_public(q: Question, tag: str | None = None) -> dict:
    item = {
        "id": str(q.id),
        "subject_id": str(q.subject_id),
        "knowledge_point_id": str(q.knowledge_point_id),
        "type": q.type,
        "content": q.content,
        "options": q.options,
        "difficulty": q.difficulty,
        "source": q.source,
    }
    if tag:
        item["tag"] = tag
    return item


# ═══════════════════════════════════════════════════════════════════════════
# AI-enhanced functions (T17)
# ═══════════════════════════════════════════════════════════════════════════

import json
import logging

from app.services.llm_gateway import llm_gateway

logger = logging.getLogger(__name__)


async def ai_identify_high_freq_kps(
    stats: list[dict],
) -> list[dict]:
    """Use LLM (pro, JSON mode) to identify high-frequency weak KPs from practice stats.

    Args:
        stats: list of {kp_name, correct, wrong, total_practice}

    Returns:
        list of {kp_name, heat_score, reason, priority}, sorted by priority
    """
    if not stats:
        return []

    system_prompt = (
        "你是一位大学课程备考分析师。请根据学生的做题统计数据，识别高频薄弱考点。\n"
        "高频薄弱考点定义：练习量高（total_practice ≥ 10）但正确率低（< 60%）的知识点。\n"
        "请输出 JSON 格式，包含 high_freq_kps 数组，每个元素有 kp_name、heat_score(0-1)、"
        "reason（一句话分析）、priority（排名，1最高）。\n"
        "按 priority 升序排列。限定最多 5 个考点。"
    )

    stats_text = json.dumps(stats, ensure_ascii=False, indent=2)
    user_prompt = (
        f"以下是一个学生的做题统计数据（json）。请识别高频薄弱考点：\n\n"
        f"{stats_text}\n\n"
        f"请以 JSON 格式输出：{{\"high_freq_kps\": [...]}}"
    )

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]

    try:
        result = await llm_gateway.chat(
            tier="pro",
            messages=messages,
            temperature=0.3,
        )
        content = result.get("content", "")
        parsed = json.loads(content)
        high_freq_kps = parsed.get("high_freq_kps", [])
        # Validate and sort
        for item in high_freq_kps:
            if "kp_name" not in item:
                continue
            item.setdefault("heat_score", 0.5)
            item.setdefault("reason", "")
            item.setdefault("priority", 99)
        high_freq_kps.sort(key=lambda x: x.get("priority", 99))
        return high_freq_kps
    except (json.JSONDecodeError, KeyError, Exception) as e:
        logger.warning("ai_identify_high_freq_kps LLM failed: %s, falling back to rules", e)
        return _rule_based_high_freq_kps(stats)


def _rule_based_high_freq_kps(stats: list[dict]) -> list[dict]:
    """Rule-based fallback: score KPs by (practice_volume × error_rate)."""
    results = []
    for i, s in enumerate(stats):
        total = s.get("total_practice", 0)
        correct = s.get("correct", 0)
        if total <= 0:
            continue
        error_rate = 1 - (correct / total)
        heat_score = min((total / 30) * error_rate, 1.0)
        results.append({
            "kp_name": s.get("kp_name", "unknown"),
            "heat_score": round(heat_score, 2),
            "reason": (
                f"练习{total}次，正确率{int(correct / total * 100)}%，"
                f"{'高频薄弱' if heat_score > 0.5 else '需关注'}"
            ),
            "priority": i + 1,
        })
    results.sort(key=lambda x: x["heat_score"], reverse=True)
    # Re-number priorities
    for idx, r in enumerate(results):
        r["priority"] = idx + 1
    return results[:5]


async def ai_enhance_sprint_plan(
    high_freq_kps: list[dict],
    days_left: int,
    total_questions: int = 20,
) -> dict:
    """Use LLM (pro, JSON mode) to generate a day-by-day sprint study plan.

    Args:
        high_freq_kps: from ai_identify_high_freq_kps or rule-based equivalent
        days_left: days until exam
        total_questions: total questions to allocate

    Returns:
        {plan: [{day, focus, question_count, rationale}], total_questions, strategy}
    """
    if not high_freq_kps or days_left <= 0:
        return {
            "plan": [],
            "total_questions": 0,
            "strategy": "",
        }

    system_prompt = (
        "你是一位大学考前突击教练。请根据高频薄弱考点和剩余天数，制定每日突击计划。\n"
        "输出 JSON 格式：{{\"plan\": [...], \"total_questions\": N, \"strategy\": \"...\"}}\n"
        "plan 数组每个元素：{{\"day\": 整数, \"focus\": \"考点名\", "
        "\"question_count\": 整数, \"rationale\": \"理由\"}}\n"
        "规划天数 = days_left，每日题量递减，优先攻克 priority 最高的考点。"
    )

    kps_text = json.dumps(high_freq_kps, ensure_ascii=False, indent=2)
    user_prompt = (
        f"请为以下高频薄弱考点制定{min(days_left, 7)}天突击计划（共{total_questions}道题）：\n\n"
        f"高频薄弱考点：\n{kps_text}\n\n"
        f"请以 JSON 格式输出计划。"
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
        plan = parsed.get("plan", [])
        # Clamp total questions
        actual_total = sum(d.get("question_count", 0) for d in plan)
        if actual_total > total_questions:
            scale = total_questions / max(actual_total, 1)
            for d in plan:
                d["question_count"] = max(1, int(d.get("question_count", 1) * scale))
        # Ensure required fields
        for d in plan:
            d.setdefault("day", 0)
            d.setdefault("focus", "")
            d.setdefault("rationale", "")
        return {
            "plan": plan,
            "total_questions": total_questions,
            "strategy": parsed.get("strategy", ""),
        }
    except (json.JSONDecodeError, KeyError, Exception) as e:
        logger.warning("ai_enhance_sprint_plan LLM failed: %s, falling back to rules", e)
        return _rule_based_sprint_plan(high_freq_kps, days_left, total_questions)


def _rule_based_sprint_plan(
    high_freq_kps: list[dict], days_left: int, total_questions: int
) -> dict:
    """Rule-based fallback: evenly split questions across days."""
    actual_days = min(days_left, 7)
    if actual_days <= 0:
        return {"plan": [], "total_questions": 0, "strategy": ""}

    per_day = max(1, total_questions // actual_days)
    remainder = total_questions - per_day * actual_days
    plan = []
    for d in range(1, actual_days + 1):
        qc = per_day + (1 if d <= remainder else 0)
        kp_idx = (d - 1) % len(high_freq_kps)
        focus = high_freq_kps[kp_idx]["kp_name"]
        plan.append({
            "day": d,
            "focus": focus,
            "question_count": qc,
            "rationale": f"第{d}天：重点练习{focus}",
        })

    return {
        "plan": plan,
        "total_questions": total_questions,
        "strategy": f"{actual_days}天突击计划，每日{per_day}道题，从高频薄弱考点入手",
    }
