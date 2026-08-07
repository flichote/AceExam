"""M3 考前突击验收测试 — POST /subjects/{id}/sprint/activate + GET /subjects/{id}/sprint/questions。

验收点（docs/design/flows.md / architecture.md §11.2/§11.3）：
- 手动激活：会员 200 + created=True + exam_date/days_left 来自计划；重复激活幂等 created=False
- 自动激活：计划考试 ≤7 天时 GET questions 自动激活（DB auto_activated=True）；>7 天不激活 → 403
- 题单生成：高频考点（heat≥20 且 avg_acc<0.75）题 + 个人未掌握错题，去重、限量、快照稳定

Run: cd backend && PYTHONPATH="" .venv/Scripts/python.exe -m pytest tests/test_m3_sprint.py -v --tb=short -p no:warnings
"""
import uuid
from datetime import date, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.db.models import (
    KnowledgePoint,
    Plan,
    Question,
    SprintSession,
    StudySession,
    Subject,
    User,
    UserKnowledgeState,
    WrongAnswer,
)
from tests.conftest import _rand

pytestmark = pytest.mark.anyio


def _d(offset: int) -> date:
    return date.today() + timedelta(days=offset)


async def _user_id(db, username: str) -> uuid.UUID:
    res = await db.execute(select(User).where(User.username == username))
    return res.scalar_one().id


async def _seed_kp(db, subject_id: str, name: str, level: int = 3) -> KnowledgePoint:
    kp = KnowledgePoint(subject_id=uuid.UUID(subject_id), name=name, content="", level=level)
    db.add(kp)
    await db.commit()
    await db.refresh(kp)
    return kp


async def _seed_question(db, subject_id: str, kp_id, source: str = "self_built") -> str:
    q = Question(
        subject_id=uuid.UUID(subject_id), knowledge_point_id=kp_id, type="single",
        content=f"题-{_rand('q')}",
        options=[{"key": "A", "text": "1"}, {"key": "B", "text": "2"}],
        answer="B", analysis="", difficulty=3, source=source, status="active",
    )
    db.add(q)
    await db.commit()
    await db.refresh(q)
    return str(q.id)


async def _set_heat_state(db, user_id, kp_id, subject_id: str, correct: int, wrong: int):
    """写入练习状态用于高频考点热度（heat=correct+wrong，跨用户累计）。"""
    db.add(UserKnowledgeState(
        user_id=user_id, knowledge_point_id=kp_id, subject_id=uuid.UUID(subject_id),
        status="weak" if correct / max(correct + wrong, 1) < 0.4 else "consolidating",
        correct_count=correct, wrong_count=wrong, streak=0,
    ))
    await db.commit()


async def _seed_wrong(db, user_id, question_id: str, subject_id: str, mastered: bool = False) -> None:
    db.add(WrongAnswer(
        user_id=user_id, question_id=uuid.UUID(question_id), subject_id=uuid.UUID(subject_id),
        wrong_answer={"value": "A"}, wrong_reason="测试", mastered=mastered,
    ))
    await db.commit()


async def _seed_plan(db, user_id, subject_id: str, exam_date: date) -> None:
    db.add(Plan(
        user_id=user_id, subject_id=uuid.UUID(subject_id), title="期末计划",
        exam_date=exam_date, status="active", config={},
    ))
    await db.commit()


async def _active_sprint(db, user_id, subject_id: str) -> SprintSession | None:
    res = await db.execute(
        select(SprintSession).where(
            SprintSession.user_id == user_id,
            SprintSession.subject_id == uuid.UUID(subject_id),
            SprintSession.status == "active",
        )
    )
    return res.scalar_one_or_none()


# ═══════════════════════════════════════════════════════════════════════
# 1. 手动激活
# ═══════════════════════════════════════════════════════════════════════

class TestManualActivation:
    async def test_activate_captures_plan_exam_date(
        self, client: AsyncClient, db_session, member_user, seed_subject
    ):
        """激活响应携带计划 exam_date / days_left；created=True。"""
        username, _, _, headers = member_user
        uid = await _user_id(db_session, username)
        exam = _d(10)
        await _seed_plan(db_session, uid, seed_subject["id"], exam)

        resp = await client.post(
            f"/api/v1/subjects/{seed_subject['id']}/sprint/activate", headers=headers, json={},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["created"] is True
        sprint = body["sprint"]
        assert sprint["status"] == "active"
        assert sprint["auto_activated"] is False
        assert sprint["exam_date"] == exam.isoformat()
        assert sprint["days_left"] == 10
        assert sprint["expires_at"] == exam.isoformat()

    async def test_activate_no_plan_days_left_null(
        self, client: AsyncClient, member_user, seed_subject
    ):
        """无计划时激活成功，exam_date/days_left 为 null。"""
        _, _, _, headers = member_user
        resp = await client.post(
            f"/api/v1/subjects/{seed_subject['id']}/sprint/activate", headers=headers, json={},
        )
        assert resp.status_code == 200
        sprint = resp.json()["sprint"]
        assert sprint["exam_date"] is None
        assert sprint["days_left"] is None

    async def test_activate_idempotent_returns_existing(
        self, client: AsyncClient, db_session, member_user, seed_subject
    ):
        """重复激活不产生第二条记录：created=False 且 DB 仅 1 条 active。"""
        username, _, _, headers = member_user
        uid = await _user_id(db_session, username)
        r1 = await client.post(
            f"/api/v1/subjects/{seed_subject['id']}/sprint/activate", headers=headers, json={},
        )
        r2 = await client.post(
            f"/api/v1/subjects/{seed_subject['id']}/sprint/activate", headers=headers, json={},
        )
        assert r1.status_code == r2.status_code == 200
        assert r1.json()["created"] is True
        assert r2.json()["created"] is False
        assert r1.json()["sprint"]["id"] == r2.json()["sprint"]["id"]

        res = await db_session.execute(
            select(SprintSession).where(SprintSession.user_id == uid)
        )
        assert len(res.scalars().all()) == 1, "重复激活只应有一条 sprint 记录"


# ═══════════════════════════════════════════════════════════════════════
# 2. 自动激活（考前 ≤7 天）
# ═══════════════════════════════════════════════════════════════════════

class TestAutoActivation:
    async def test_auto_activate_within_7_days(
        self, client: AsyncClient, db_session, member_user, seed_subject
    ):
        """计划考试日 = 今天+7 → GET questions 自动激活（auto_activated=True）。"""
        username, _, _, headers = member_user
        uid = await _user_id(db_session, username)
        await _seed_plan(db_session, uid, seed_subject["id"], _d(7))

        resp = await client.get(
            f"/api/v1/subjects/{seed_subject['id']}/sprint/questions", headers=headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["days_left"] == 7
        assert data["status"] == "active"

        sprint = await _active_sprint(db_session, uid, seed_subject["id"])
        assert sprint is not None
        assert sprint.auto_activated is True

    async def test_no_auto_activate_beyond_7_days(
        self, client: AsyncClient, db_session, member_user, seed_subject
    ):
        """计划考试日 = 今天+8 → 不自动激活 → 403。"""
        username, _, _, headers = member_user
        uid = await _user_id(db_session, username)
        await _seed_plan(db_session, uid, seed_subject["id"], _d(8))

        resp = await client.get(
            f"/api/v1/subjects/{seed_subject['id']}/sprint/questions", headers=headers,
        )
        assert resp.status_code == 403
        assert await _active_sprint(db_session, uid, seed_subject["id"]) is None

    async def test_manual_activation_then_questions_ok(
        self, client: AsyncClient, db_session, member_user, seed_subject
    ):
        """手动激活（考试 >7 天）后 GET questions 可访问，且不重复建 sprint。"""
        username, _, _, headers = member_user
        uid = await _user_id(db_session, username)
        await _seed_plan(db_session, uid, seed_subject["id"], _d(20))
        r = await client.post(
            f"/api/v1/subjects/{seed_subject['id']}/sprint/activate", headers=headers, json={},
        )
        assert r.status_code == 200
        sprint_id = r.json()["sprint"]["id"]

        resp = await client.get(
            f"/api/v1/subjects/{seed_subject['id']}/sprint/questions", headers=headers,
        )
        assert resp.status_code == 200
        assert resp.json()["sprint_id"] == sprint_id


# ═══════════════════════════════════════════════════════════════════════
# 3. 题单生成：高频考点 + 错题、去重、限量、快照
# ═══════════════════════════════════════════════════════════════════════

class TestQuestionList:
    async def test_high_freq_kp_questions(
        self, client: AsyncClient, db_session, member_user, seed_subject
    ):
        """高频考点（heat≥20 且 avg_acc<0.75）的题进入题单，tag=high_freq。"""
        username, _, _, headers = member_user
        uid = await _user_id(db_session, username)
        kp = await _seed_kp(db_session, seed_subject["id"], "极限与连续")
        q_ids = [await _seed_question(db_session, seed_subject["id"], kp.id) for _ in range(3)]
        await _set_heat_state(db_session, uid, kp.id, seed_subject["id"], correct=5, wrong=20)

        await client.post(
            f"/api/v1/subjects/{seed_subject['id']}/sprint/activate", headers=headers, json={},
        )
        resp = await client.get(
            f"/api/v1/subjects/{seed_subject['id']}/sprint/questions?count=10", headers=headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["high_freq_kps"]) == 1
        hf = data["high_freq_kps"][0]
        assert hf["name"] == "极限与连续"
        assert hf["heat"] == 25
        assert hf["avg_accuracy"] == 0.2
        assert hf["has_past_exam"] is False

        item_ids = [it["id"] for it in data["items"]]
        assert set(item_ids) == set(q_ids)
        assert all(it["tag"] == "high_freq" for it in data["items"])
        assert data["summary"]["high_freq_questions"] == 3
        assert data["summary"]["wrong_review_questions"] == 0
        assert data["summary"]["deduped"] == 0
        assert data["summary"]["total"] == 3

    async def test_low_heat_kp_not_high_freq(
        self, client: AsyncClient, db_session, member_user, seed_subject
    ):
        """heat<20 的考点不进入 high_freq_kps。"""
        username, _, _, headers = member_user
        uid = await _user_id(db_session, username)
        kp = await _seed_kp(db_session, seed_subject["id"], "低热度考点")
        await _seed_question(db_session, seed_subject["id"], kp.id)
        await _set_heat_state(db_session, uid, kp.id, seed_subject["id"], correct=2, wrong=8)  # heat=10 < 20

        await client.post(
            f"/api/v1/subjects/{seed_subject['id']}/sprint/activate", headers=headers, json={},
        )
        resp = await client.get(
            f"/api/v1/subjects/{seed_subject['id']}/sprint/questions?count=10", headers=headers,
        )
        assert resp.status_code == 200
        assert resp.json()["high_freq_kps"] == []

    async def test_wrong_answer_included(
        self, client: AsyncClient, db_session, member_user, seed_subject
    ):
        """个人未掌握错题进入题单，tag=wrong_review。"""
        username, _, _, headers = member_user
        uid = await _user_id(db_session, username)
        kp = await _seed_kp(db_session, seed_subject["id"], "错题考点")
        qid = await _seed_question(db_session, seed_subject["id"], kp.id)
        await _seed_wrong(db_session, uid, qid, seed_subject["id"])

        await client.post(
            f"/api/v1/subjects/{seed_subject['id']}/sprint/activate", headers=headers, json={},
        )
        resp = await client.get(
            f"/api/v1/subjects/{seed_subject['id']}/sprint/questions?count=10", headers=headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["items"]) == 1
        assert data["items"][0]["id"] == qid
        assert data["items"][0]["tag"] == "wrong_review"
        assert data["summary"]["wrong_review_questions"] == 1

    async def test_dedup_high_freq_and_wrong_same_question(
        self, client: AsyncClient, db_session, member_user, seed_subject
    ):
        """同一题既是高频考点题又是错题 → 只出现一次（tag=high_freq）。

        注意：summary.deduped 当前恒为 0（见 D-21），此处不断言该字段。
        """
        username, _, _, headers = member_user
        uid = await _user_id(db_session, username)
        kp = await _seed_kp(db_session, seed_subject["id"], "重叠考点")
        qid = await _seed_question(db_session, seed_subject["id"], kp.id)
        await _set_heat_state(db_session, uid, kp.id, seed_subject["id"], correct=5, wrong=20)  # high-freq
        await _seed_wrong(db_session, uid, qid, seed_subject["id"])  # 同题错题

        await client.post(
            f"/api/v1/subjects/{seed_subject['id']}/sprint/activate", headers=headers, json={},
        )
        resp = await client.get(
            f"/api/v1/subjects/{seed_subject['id']}/sprint/questions?count=10", headers=headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["items"]) == 1
        assert data["items"][0]["id"] == qid
        assert data["items"][0]["tag"] == "high_freq"
        assert data["summary"]["high_freq_questions"] == 1
        assert data["summary"]["wrong_review_questions"] == 0
        assert data["summary"]["total"] == 1

    @pytest.mark.xfail(
        reason="D-21 [P3]: summary.deduped 恒为 0（实现为 high_freq+wrong_review-total，两计数与 total 恒等，未统计被去重的错题数）",
        strict=False,
    )
    async def test_summary_deduped_metric_counts_skipped_wrong(
        self, client: AsyncClient, db_session, member_user, seed_subject
    ):
        """契约：错题被高频考点覆盖时 deduped 应为 1（当前恒为 0）。"""
        username, _, _, headers = member_user
        uid = await _user_id(db_session, username)
        kp = await _seed_kp(db_session, seed_subject["id"], "重叠考点")
        qid = await _seed_question(db_session, seed_subject["id"], kp.id)
        await _set_heat_state(db_session, uid, kp.id, seed_subject["id"], correct=5, wrong=20)
        await _seed_wrong(db_session, uid, qid, seed_subject["id"])

        await client.post(
            f"/api/v1/subjects/{seed_subject['id']}/sprint/activate", headers=headers, json={},
        )
        resp = await client.get(
            f"/api/v1/subjects/{seed_subject['id']}/sprint/questions?count=10", headers=headers,
        )
        data = resp.json()
        assert data["summary"]["deduped"] == 1, "被去重的错题数应反映在 deduped 中 → D-21"

    async def test_high_freq_plus_wrong_combined(
        self, client: AsyncClient, db_session, member_user, seed_subject
    ):
        """高频题 + 独立错题共存：4 题（3 high_freq + 1 wrong_review）。"""
        username, _, _, headers = member_user
        uid = await _user_id(db_session, username)
        kp_hf = await _seed_kp(db_session, seed_subject["id"], "高频考点")
        for _ in range(3):
            await _seed_question(db_session, seed_subject["id"], kp_hf.id)
        await _set_heat_state(db_session, uid, kp_hf.id, seed_subject["id"], correct=5, wrong=20)

        kp_wa = await _seed_kp(db_session, seed_subject["id"], "错题考点")
        q_wa = await _seed_question(db_session, seed_subject["id"], kp_wa.id)
        await _seed_wrong(db_session, uid, q_wa, seed_subject["id"])

        await client.post(
            f"/api/v1/subjects/{seed_subject['id']}/sprint/activate", headers=headers, json={},
        )
        resp = await client.get(
            f"/api/v1/subjects/{seed_subject['id']}/sprint/questions?count=10", headers=headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        tags = {it["id"]: it["tag"] for it in data["items"]}
        assert tags[q_wa] == "wrong_review"
        assert len([t for t in tags.values() if t == "high_freq"]) == 3
        assert data["summary"]["total"] == 4
        assert data["summary"]["deduped"] == 0

    @pytest.mark.xfail(
        reason="D-22 [P2]: 高频阶段按考点一次取 3 题、break 在考点循环顶部 → count=2 时单个考点返回 3 题，超出限量",
        strict=False,
    )
    async def test_count_limit(self, client: AsyncClient, db_session, member_user, seed_subject):
        """契约：count 限量严格生效（count=2 只返回 2 题）。当前单个考点可超出。"""
        username, _, _, headers = member_user
        uid = await _user_id(db_session, username)
        kp1 = await _seed_kp(db_session, seed_subject["id"], "考点A")
        kp2 = await _seed_kp(db_session, seed_subject["id"], "考点B")
        for kp in (kp1, kp2):
            for _ in range(3):
                await _seed_question(db_session, seed_subject["id"], kp.id)
            await _set_heat_state(db_session, uid, kp.id, seed_subject["id"], correct=5, wrong=20)

        await client.post(
            f"/api/v1/subjects/{seed_subject['id']}/sprint/activate", headers=headers, json={},
        )
        resp = await client.get(
            f"/api/v1/subjects/{seed_subject['id']}/sprint/questions?count=2", headers=headers,
        )
        assert resp.status_code == 200
        assert len(resp.json()["items"]) == 2, "count=2 应严格返回 2 题 → D-22"

    async def test_wrong_review_respects_count(
        self, client: AsyncClient, db_session, member_user, seed_subject
    ):
        """错题阶段严格限量：count=3 时 1 高频题 + 2 错题 = 恰好 3 题。"""
        username, _, _, headers = member_user
        uid = await _user_id(db_session, username)
        kp_hf = await _seed_kp(db_session, seed_subject["id"], "高频考点")
        await _seed_question(db_session, seed_subject["id"], kp_hf.id)
        await _set_heat_state(db_session, uid, kp_hf.id, seed_subject["id"], correct=5, wrong=20)

        # 5 个未掌握错题（非高频考点）
        for i in range(5):
            kp_wa = await _seed_kp(db_session, seed_subject["id"], f"错题考点{i}")
            qid = await _seed_question(db_session, seed_subject["id"], kp_wa.id)
            await _seed_wrong(db_session, uid, qid, seed_subject["id"])

        await client.post(
            f"/api/v1/subjects/{seed_subject['id']}/sprint/activate", headers=headers, json={},
        )
        resp = await client.get(
            f"/api/v1/subjects/{seed_subject['id']}/sprint/questions?count=3", headers=headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["items"]) == 3
        assert data["summary"]["wrong_review_questions"] == 2
        assert data["summary"]["total"] == 3

    async def test_snapshot_stable_across_calls(
        self, client: AsyncClient, db_session, member_user, seed_subject
    ):
        """同一 sprint 重复请求返回相同题单快照（防重复组卷）。"""
        username, _, _, headers = member_user
        uid = await _user_id(db_session, username)
        kp = await _seed_kp(db_session, seed_subject["id"], "快照考点")
        for _ in range(3):
            await _seed_question(db_session, seed_subject["id"], kp.id)
        await _set_heat_state(db_session, uid, kp.id, seed_subject["id"], correct=5, wrong=20)

        await client.post(
            f"/api/v1/subjects/{seed_subject['id']}/sprint/activate", headers=headers, json={},
        )
        r1 = await client.get(
            f"/api/v1/subjects/{seed_subject['id']}/sprint/questions?count=10", headers=headers,
        )
        r2 = await client.get(
            f"/api/v1/subjects/{seed_subject['id']}/sprint/questions?count=10", headers=headers,
        )
        assert r1.status_code == r2.status_code == 200
        b1, b2 = r1.json(), r2.json()
        assert b1["sprint_id"] == b2["sprint_id"]
        assert [it["id"] for it in b1["items"]] == [it["id"] for it in b2["items"]]

        # DB 快照落库
        sprint = await _active_sprint(db_session, uid, seed_subject["id"])
        assert sprint.question_snapshot is not None
        assert len(sprint.question_snapshot["items"]) == 3

    async def test_mock_mode_meta(self, client: AsyncClient, db_session, member_user, seed_subject):
        """mode=mock 返回 mock 元信息。"""
        username, _, _, headers = member_user
        uid = await _user_id(db_session, username)
        kp = await _seed_kp(db_session, seed_subject["id"], "模考考点")
        await _seed_question(db_session, seed_subject["id"], kp.id)
        await _set_heat_state(db_session, uid, kp.id, seed_subject["id"], correct=5, wrong=20)

        await client.post(
            f"/api/v1/subjects/{seed_subject['id']}/sprint/activate", headers=headers, json={},
        )
        resp = await client.get(
            f"/api/v1/subjects/{seed_subject['id']}/sprint/questions?mode=mock", headers=headers,
        )
        assert resp.status_code == 200
        mock = resp.json()["mock"]
        assert mock is not None
        assert mock["duration_min"] == 120
        assert mock["total_score"] == 100

    async def test_past_exam_fallback_high_freq(
        self, client: AsyncClient, db_session, member_user, seed_subject
    ):
        """无高频状态时降级：有 past_exam 题的考点进入 high_freq_kps。"""
        _, _, _, headers = member_user
        kp = await _seed_kp(db_session, seed_subject["id"], "真题考点")
        await _seed_question(db_session, seed_subject["id"], kp.id, source="past_exam")

        await client.post(
            f"/api/v1/subjects/{seed_subject['id']}/sprint/activate", headers=headers, json={},
        )
        resp = await client.get(
            f"/api/v1/subjects/{seed_subject['id']}/sprint/questions?count=10", headers=headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["high_freq_kps"]) == 1
        assert data["high_freq_kps"][0]["name"] == "真题考点"
        assert data["high_freq_kps"][0]["has_past_exam"] is True

    async def test_no_questions_empty_items(
        self, client: AsyncClient, db_session, member_user, seed_subject
    ):
        """无任何可选题 → items 为空，summary.total=0。"""
        _, _, _, headers = member_user
        await client.post(
            f"/api/v1/subjects/{seed_subject['id']}/sprint/activate", headers=headers, json={},
        )
        resp = await client.get(
            f"/api/v1/subjects/{seed_subject['id']}/sprint/questions?count=10", headers=headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["items"] == []
        assert data["summary"]["total"] == 0
