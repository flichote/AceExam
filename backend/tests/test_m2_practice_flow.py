"""M2 智能刷题端到端验收测试 — 自适应选题 + 知识状态机 + 幂等性。

验收点（docs/design/flows.md 流程1 / PRD）：
- 自适应选题：薄弱知识点优先（architecture.md §10.1 scorer）
- 提交答案 → user_knowledge_states 更新（连续 3 次正确 → mastered；答错 streak 归零）
- 幂等：重复提交错误只产生 1 条错题记录

数据格式约定（database.md §3.3 / seed.py）：
- questions.answer 存纯字符串（single="B"），options 存 [{"key","text"}, ...]
- /answers 请求 answer 信封 {type, value}（api.md §3.3，前端 buildAnswerValue 实际载荷）

已知缺陷（详见 docs/qa/test-report.md M2 节）：
- D-8 [P1] 后端判分整 dict 全等，未按题型解包信封 → 前端实际载荷被判错（xfail 固化契约）
- D-9 [P1] /answers 响应 knowledge_state 滞后一次作答（DB 落库正确，返回对象过期，xfail 固化契约）
"""
import uuid

import pytest
from sqlalchemy import select

from app.db.models import Question, Subject, KnowledgePoint, User, UserKnowledgeState, WrongAnswer
from tests.conftest import _rand


# ═══════════════════════════════════════════════════════════════════════════
# 种子：生产格式题目（options=list / answer=纯字符串）
# ═══════════════════════════════════════════════════════════════════════════


async def _seed_prod_bank(db, n_kps: int = 2) -> dict:
    """创建 subject + n 个叶子知识点 + 每题 1 道单选（答案 "B"）。"""
    subj = Subject(code=_rand("math"), name="高等数学(M2测试)", description="", config={})
    db.add(subj)
    await db.flush()
    kp_ids, q_ids = [], []
    for i in range(n_kps):
        kp = KnowledgePoint(
            subject_id=subj.id, name=f"知识点{i}(M2)", content="测试内容", level=3,
        )
        db.add(kp)
        await db.flush()
        kp_ids.append(str(kp.id))
        q = Question(
            subject_id=subj.id,
            knowledge_point_id=kp.id,
            type="single",
            content=f"题目{i}：$f(x)=x^2$ 的导数为（　　）。",
            options=[
                {"key": "A", "text": "$0$"},
                {"key": "B", "text": "$2x$"},
                {"key": "C", "text": "$x$"},
                {"key": "D", "text": "$x^2$"},
            ],
            answer="B",
            analysis="幂函数求导：$(x^2)'=2x$。",
            difficulty=3,
            source="self_built",
            status="active",
        )
        db.add(q)
        await db.flush()
        q_ids.append(str(q.id))
    await db.commit()
    return {
        "subject_id": str(subj.id),
        "kp_ids": kp_ids,
        "q_ids": q_ids,
    }


async def _user_id(db, username: str) -> uuid.UUID:
    res = await db.execute(select(User).where(User.username == username))
    return res.scalar_one().id


async def _set_state(db, user_id, kp_id, subject_id, status, correct, wrong):
    db.add(UserKnowledgeState(
        user_id=user_id,
        knowledge_point_id=uuid.UUID(kp_id),
        subject_id=uuid.UUID(subject_id),
        status=status,
        correct_count=correct,
        wrong_count=wrong,
        streak=0,
    ))
    await db.commit()


async def _db_state(db, user_id, kp_id):
    res = await db.execute(
        select(UserKnowledgeState).where(
            UserKnowledgeState.user_id == user_id,
            UserKnowledgeState.knowledge_point_id == uuid.UUID(kp_id),
        )
    )
    st = res.scalar_one()
    await db.refresh(st)  # 绕过 identity-map 过期，强制读库
    return st


# ═══════════════════════════════════════════════════════════════════════════
# 1. 自适应选题：薄弱优先
# ═══════════════════════════════════════════════════════════════════════════


class TestAdaptiveSelection:
    # 注意：GET /subjects/{id}/practice/questions 当前因 ORDER BY `<=>` 运算符
    # （pgvector 专属，integer 列 + SQLite/PG 均不支持）直接 500，见缺陷 D-15。
    # ep-backend 修复前以下集成用例保持 xfail，修复后自动转 XPASS 验证。

    async def test_requires_auth(self, client, seed_subject):
        resp = await client.get(
            f"/api/v1/subjects/{seed_subject['id']}/practice/questions?count=5"
        )
        assert resp.status_code == 401

    @pytest.mark.xfail(reason="D-15 [P1]: ORDER BY difficulty <=> ? 在 SQLite/PG 均语法错误 → 接口 500", strict=False)
    async def test_weak_kp_prioritized(self, client, db_session, registered_user):
        """薄弱知识点在 target_kps 中排第一。"""
        bank = await _seed_prod_bank(db_session, n_kps=2)
        username, _, _, headers = registered_user
        uid = await _user_id(db_session, username)
        await _set_state(db_session, uid, bank["kp_ids"][0], bank["subject_id"],
                         status="weak", correct=1, wrong=8)
        await _set_state(db_session, uid, bank["kp_ids"][1], bank["subject_id"],
                         status="mastered", correct=20, wrong=1)

        resp = await client.get(
            f"/api/v1/subjects/{bank['subject_id']}/practice/questions?count=5",
            headers=headers,
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["items"], "应返回至少 1 道题"
        target = body["strategy"]["target_kps"]
        assert target, "strategy.target_kps 不应为空"
        assert target[0]["id"] == bank["kp_ids"][0], "薄弱知识点应优先"
        assert target[0]["status"] == "weak"
        # 已掌握知识点不应排第一
        assert target[0]["id"] != bank["kp_ids"][1]

    @pytest.mark.xfail(reason="D-15 [P1]: ORDER BY difficulty <=> ? 在 SQLite/PG 均语法错误 → 接口 500", strict=False)
    async def test_untouched_default_priority(self, client, db_session, registered_user):
        """无任何状态时，所有知识点按 untouched 参与选。"""
        bank = await _seed_prod_bank(db_session, n_kps=2)
        _, _, _, headers = registered_user
        resp = await client.get(
            f"/api/v1/subjects/{bank['subject_id']}/practice/questions?count=5",
            headers=headers,
        )
        assert resp.status_code == 200
        body = resp.json()
        assert len(body["items"]) >= 1
        statuses = {t["status"] for t in body["strategy"]["target_kps"]}
        assert statuses <= {"untouched", "consolidating", "weak", "mastered"}

    @pytest.mark.xfail(reason="D-15 [P1]: ORDER BY difficulty <=> ? 在 SQLite/PG 均语法错误 → 接口 500", strict=False)
    async def test_exclude_ids_respected(self, client, db_session, registered_user):
        bank = await _seed_prod_bank(db_session, n_kps=2)
        _, _, _, headers = registered_user
        resp = await client.get(
            f"/api/v1/subjects/{bank['subject_id']}/practice/questions?count=5"
            f"&exclude_ids={bank['q_ids'][0]}",
            headers=headers,
        )
        assert resp.status_code == 200
        ids = [it["id"] for it in resp.json()["items"]]
        assert bank["q_ids"][0] not in ids

    @pytest.mark.xfail(reason="D-15 [P1]: ORDER BY difficulty <=> ? 在 SQLite/PG 均语法错误 → 接口 500", strict=False)
    async def test_count_limit(self, client, db_session, registered_user):
        bank = await _seed_prod_bank(db_session, n_kps=2)
        _, _, _, headers = registered_user
        resp = await client.get(
            f"/api/v1/subjects/{bank['subject_id']}/practice/questions?count=1",
            headers=headers,
        )
        assert resp.status_code == 200
        assert len(resp.json()["items"]) == 1

    async def test_count_bounds_422(self, client, db_session, registered_user):
        bank = await _seed_prod_bank(db_session, n_kps=1)
        _, _, _, headers = registered_user
        for bad in (0, 21):
            resp = await client.get(
                f"/api/v1/subjects/{bank['subject_id']}/practice/questions?count={bad}",
                headers=headers,
            )
            assert resp.status_code == 422

    async def test_no_questions_returns_empty(self, client, db_session, registered_user):
        subj = Subject(code=_rand("math"), name="空科目", description="", config={})
        db_session.add(subj)
        await db_session.commit()
        await db_session.refresh(subj)
        _, _, _, headers = registered_user
        resp = await client.get(
            f"/api/v1/subjects/{subj.id}/practice/questions?count=5",
            headers=headers,
        )
        assert resp.status_code == 200
        assert resp.json()["items"] == []


# ═══════════════════════════════════════════════════════════════════════════
# 2. 提交答案 → 知识状态机
# ═══════════════════════════════════════════════════════════════════════════


class TestKnowledgeStateMachine:
    async def test_three_correct_marks_mastered(self, client, db_session, registered_user):
        """连续 3 次正确 → DB 状态 mastered / streak=3（落库事实）。"""
        bank = await _seed_prod_bank(db_session, n_kps=1)
        username, _, _, headers = registered_user
        uid = await _user_id(db_session, username)
        qid = bank["q_ids"][0]

        for i in range(3):
            resp = await client.post(
                f"/api/v1/questions/{qid}/answers",
                headers=headers,
                json={"answer": "B", "time_spent_seconds": 10},
            )
            assert resp.status_code == 200, resp.text
            assert resp.json()["correct"] is True

        st = await _db_state(db_session, uid, bank["kp_ids"][0])
        assert st.status == "mastered"
        assert st.streak == 3
        assert st.correct_count == 3
        assert st.wrong_count == 0

    async def test_wrong_resets_streak_and_marks_weak(self, client, db_session, registered_user):
        """答错 → streak 归零；正确率 <40% → weak。"""
        bank = await _seed_prod_bank(db_session, n_kps=1)
        username, _, _, headers = registered_user
        uid = await _user_id(db_session, username)
        qid = bank["q_ids"][0]

        # 对 → 错 → 错：1 正确 2 错误，正确率 1/3 ≈ 0.33 < 0.4 → weak
        for ans in ("B", "A", "A"):
            resp = await client.post(
                f"/api/v1/questions/{qid}/answers",
                headers=headers,
                json={"answer": ans, "time_spent_seconds": 10},
            )
            assert resp.status_code == 200

        st = await _db_state(db_session, uid, bank["kp_ids"][0])
        assert st.status == "weak"
        assert st.streak == 0
        assert st.correct_count == 1
        assert st.wrong_count == 2

    async def test_plain_answer_grades_correct(self, client, db_session, registered_user):
        """纯字符串载荷判分正确（当前仅此格式可用，前端信封见 D-8）。"""
        bank = await _seed_prod_bank(db_session, n_kps=1)
        _, _, _, headers = registered_user
        resp = await client.post(
            f"/api/v1/questions/{bank['q_ids'][0]}/answers",
            headers=headers,
            json={"answer": "B", "time_spent_seconds": 10},
        )
        assert resp.status_code == 200
        assert resp.json()["correct"] is True

    @pytest.mark.xfail(reason="D-8 [P1]: /answers 未按题型解包信封 {type,value}，整 dict 全等判分 → 前端实际载荷恒判错", strict=False)
    async def test_envelope_grading_contract(self, client, db_session, registered_user):
        """契约（api.md §3.3）：前端信封 {type:'single', value:'B'} 应判对。

        当前实现整 dict 全等比较 → 恒判错。D-8 [P1] 修复前保持 xfail。
        """
        bank = await _seed_prod_bank(db_session, n_kps=1)
        _, _, _, headers = registered_user
        resp = await client.post(
            f"/api/v1/questions/{bank['q_ids'][0]}/answers",
            headers=headers,
            json={"answer": {"type": "single", "value": "B"}, "time_spent_seconds": 10},
        )
        assert resp.status_code == 200
        assert resp.json()["correct"] is True, (
            "前端实际载荷被判错 → D-8：后端应解包 {type,value} 后与题目 answer 比较"
        )

    @pytest.mark.xfail(reason="D-9 [P1]: apply_answer 返回 identity-map 过期对象，响应 knowledge_state 滞后一次作答", strict=False)
    async def test_response_knowledge_state_reflects_submission(
        self, client, db_session, registered_user
    ):
        """契约：响应 knowledge_state 应反映本次作答后的状态。

        当前返回 identity-map 过期对象（滞后一次）。D-9 [P1] 修复前保持 xfail。
        """
        bank = await _seed_prod_bank(db_session, n_kps=1)
        _, _, _, headers = registered_user
        resp = await client.post(
            f"/api/v1/questions/{bank['q_ids'][0]}/answers",
            headers=headers,
            json={"answer": "B", "time_spent_seconds": 10},
        )
        assert resp.status_code == 200
        ks = resp.json()["knowledge_state"]
        assert ks["correct_count"] == 1, "首次答对应为 correct_count=1（当前滞后为 0 → D-9）"
        assert ks["streak"] == 1

    async def test_wrong_answer_idempotent(self, client, db_session, registered_user):
        """重复提交同一题的错误答案 → 只产生 1 条错题。"""
        bank = await _seed_prod_bank(db_session, n_kps=1)
        username, _, _, headers = registered_user
        uid = await _user_id(db_session, username)
        qid = bank["q_ids"][0]

        r1 = await client.post(
            f"/api/v1/questions/{qid}/answers",
            headers=headers,
            json={"answer": "A", "time_spent_seconds": 10},
        )
        r2 = await client.post(
            f"/api/v1/questions/{qid}/answers",
            headers=headers,
            json={"answer": "A", "time_spent_seconds": 10},
        )
        assert r1.status_code == r2.status_code == 200
        assert r1.json()["correct"] is False
        assert r2.json()["wrong_answer_id"] == r1.json()["wrong_answer_id"]

        res = await db_session.execute(
            select(WrongAnswer).where(
                WrongAnswer.user_id == uid,
                WrongAnswer.question_id == uuid.UUID(qid),
            )
        )
        assert len(res.scalars().all()) == 1, "重复提交不应产生重复错题"

    async def test_answer_404(self, client, registered_user):
        _, _, _, headers = registered_user
        resp = await client.post(
            f"/api/v1/questions/{uuid.uuid4()}/answers",
            headers=headers,
            json={"answer": "B", "time_spent_seconds": 10},
        )
        assert resp.status_code == 404
