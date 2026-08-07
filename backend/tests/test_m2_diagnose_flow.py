"""M2 摸底诊断端到端验收测试 — 自测 → 提交 → 报告 JSON schema 校验。

验收点（docs/design/flows.md 流程3 / PRD）：
- 自测题覆盖主要章节（coverage）
- 薄弱 Top5 与自测表现一致（可解释）
- 报告 JSON schema：weak_top5 含 rank/knowledge_point_id/name/accuracy/practice_count/status/suggestion
- 幂等：重复提交返回既有报告

已知缺陷（详见 docs/qa/test-report.md M2 节）：
- D-10 [P2] 题库 options 为 dict 格式时 /diagnose/self-test 500（xfail 固化契约）
- D-11 [P2] weak_top5 排序反转：order_by 布尔 ASC → weak 排最后（xfail 固化契约）
"""
import uuid

import pytest
from sqlalchemy import select

from app.db.models import KnowledgePoint, Question, Subject
from tests.conftest import _rand


async def _seed_diag_bank(db, n_kps: int = 3) -> dict:
    """subject + n 个叶子知识点 + n 道单选（生产格式：options=list, answer="A"）。"""
    subj = Subject(code=_rand("diag"), name="诊断测试科目", description="", config={})
    db.add(subj)
    await db.flush()
    kp_ids, q_ids, kp_names = [], [], []
    for i in range(n_kps):
        kp = KnowledgePoint(subject_id=subj.id, name=f"诊断知识点{i}", content="", level=3)
        db.add(kp)
        await db.flush()
        kp_ids.append(str(kp.id))
        kp_names.append(kp.name)
        q = Question(
            subject_id=subj.id,
            knowledge_point_id=kp.id,
            type="single",
            content=f"诊断题{i}：$\\lim_{{x\\to0}}\\frac{{\\sin x}}{{x}}$ = ?",
            options=[{"key": "A", "text": "$1$"}, {"key": "B", "text": "$0$"}],
            answer="A",
            analysis="重要极限",
            difficulty=2,
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
        "kp_names": kp_names,
        "q_ids": q_ids,
    }


async def _start_self_test(client, headers, subject_id: str, count: int = 5) -> dict:
    resp = await client.post(
        "/api/v1/diagnose/self-test",
        headers=headers,
        json={"subject_id": subject_id, "count": count, "include_weak": True},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


# ═══════════════════════════════════════════════════════════════════════════
# 自测发起
# ═══════════════════════════════════════════════════════════════════════════


class TestSelfTest:
    async def test_start_self_test(self, client, db_session, registered_user):
        bank = await _seed_diag_bank(db_session, n_kps=3)
        _, _, _, headers = registered_user
        st = await _start_self_test(client, headers, bank["subject_id"])
        assert st["status"] == "in_progress"
        assert st["report_id"]
        assert len(st["questions"]) >= 1
        # 题目快照不含答案
        for q in st["questions"]:
            assert "answer" not in q
            assert "analysis" not in q
            assert q["knowledge_point_id"]
        # coverage 为章节覆盖列表
        assert isinstance(st["coverage"], list)
        assert len(st["coverage"]) >= 1
        assert "chapter_name" in st["coverage"][0]

    async def test_self_test_count_validation(self, client, db_session, registered_user):
        bank = await _seed_diag_bank(db_session, n_kps=1)
        _, _, _, headers = registered_user
        resp = await client.post(
            "/api/v1/diagnose/self-test",
            headers=headers,
            json={"subject_id": bank["subject_id"], "count": 3, "include_weak": True},
        )
        assert resp.status_code == 422  # count ge=5

    async def test_get_self_test_status(self, client, db_session, registered_user):
        bank = await _seed_diag_bank(db_session, n_kps=2)
        _, _, _, headers = registered_user
        st = await _start_self_test(client, headers, bank["subject_id"])
        resp = await client.get(f"/api/v1/diagnose/self-test/{st['report_id']}", headers=headers)
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "in_progress"
        assert body["questions"] is not None
        assert body["weak_top5"] is None

    async def test_self_test_404(self, client, registered_user):
        _, _, _, headers = registered_user
        resp = await client.get(
            f"/api/v1/diagnose/self-test/{uuid.uuid4()}", headers=headers
        )
        assert resp.status_code == 404

    @pytest.mark.xfail(
        reason="D-10 [P2]: 题库 options 为 dict 格式时 SelfTestQuestionItem.options 校验失败 → 500",
        strict=False,
    )
    async def test_self_test_handles_dict_options_gracefully(self, client, db_session, registered_user):
        """契约：dict 格式 options 的题目（M1 遗留/混库）不应导致 500。

        当前实现 500；应返回 200（后端归一化）或 422（明确拒绝）。
        """
        subj = Subject(code=_rand("diag"), name="混合格式科目", description="", config={})
        db_session.add(subj)
        await db_session.flush()
        kp = KnowledgePoint(subject_id=subj.id, name="遗留格式", content="", level=3)
        db_session.add(kp)
        await db_session.flush()
        q = Question(
            subject_id=subj.id, knowledge_point_id=kp.id, type="single",
            content="dict-options 题目",
            options={"A": "1", "B": "2"},  # M1 遗留 dict 格式
            answer={"correct": "A"},  # M1 遗留 dict 格式
            analysis="", difficulty=2, source="self_built", status="active",
        )
        db_session.add(q)
        await db_session.commit()
        _, _, _, headers = registered_user
        resp = await client.post(
            "/api/v1/diagnose/self-test",
            headers=headers,
            json={"subject_id": str(subj.id), "count": 5, "include_weak": True},
        )
        assert resp.status_code != 500


# ═══════════════════════════════════════════════════════════════════════════
# 提交报告
# ═══════════════════════════════════════════════════════════════════════════


class TestReport:
    async def test_report_schema_and_consistency(self, client, db_session, registered_user):
        """答错 1 题、答对 1 题、答对 3 次（→已掌握）、跳过 1 题 → 报告与表现一致。"""
        bank = await _seed_diag_bank(db_session, n_kps=4)
        _, _, _, headers = registered_user
        st = await _start_self_test(client, headers, bank["subject_id"])
        report_id = st["report_id"]

        resp = await client.post(
            "/api/v1/diagnose/report",
            headers=headers,
            json={
                "report_id": report_id,
                "answers": [
                    {"question_id": bank["q_ids"][0], "answer": "B"},  # 错 → weak
                    {"question_id": bank["q_ids"][1], "answer": "A"},  # 对 ×1 → consolidating
                    {"question_id": bank["q_ids"][2], "answer": "A"},  # 对 ×3 → mastered
                    {"question_id": bank["q_ids"][2], "answer": "A"},
                    {"question_id": bank["q_ids"][2], "answer": "A"},
                    # q3 跳过
                ],
            },
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["status"] == "completed"
        assert isinstance(body["summary"], str) and body["summary"]
        assert isinstance(body["suggested_next_steps"], list) and body["suggested_next_steps"]

        # weak_top5 JSON schema
        assert isinstance(body["weak_top5"], list) and body["weak_top5"]
        for w in body["weak_top5"]:
            assert set(w.keys()) >= {
                "rank", "knowledge_point_id", "knowledge_point_name",
                "accuracy", "practice_count", "status", "suggestion",
            }
            assert 1 <= w["rank"] <= 5
            assert w["status"] in ("untouched", "consolidating", "mastered", "weak")
            assert 0.0 <= w["accuracy"] <= 1.0
            assert isinstance(w["suggestion"], str) and w["suggestion"]

        # 与自测表现一致：答错的 KP0 出现在薄弱（accuracy 0）；已掌握的 KP2 出现在 strengths
        names = {w["knowledge_point_name"]: w for w in body["weak_top5"]}
        assert "诊断知识点0" in names
        assert names["诊断知识点0"]["accuracy"] == 0.0
        assert names["诊断知识点0"]["status"] == "weak"
        strengths_names = [s["knowledge_point_name"] for s in body["strengths"]]
        assert "诊断知识点2" in strengths_names, (
            "连续 3 次正确的知识点应进入 strengths"
        )
        # 跳过的 KP3 → not_started
        not_started_names = [n["knowledge_point_name"] for n in body["not_started"]]
        assert "诊断知识点3" in not_started_names

        # 报告状态持久化：GET 返回 completed + weak_top5
        g = await client.get(f"/api/v1/diagnose/self-test/{report_id}", headers=headers)
        assert g.json()["status"] == "completed"
        assert g.json()["weak_top5"] is not None

    @pytest.mark.xfail(
        reason="D-11 [P2]: weak_top5 排序 order_by(status=='weak') ASC → weak 排最后而非优先",
        strict=False,
    )
    async def test_report_weak_top5_ranks_weakest_first(self, client, db_session, registered_user):
        """契约：薄弱项应排在最前（rank=1 为答错的知识点）。"""
        bank = await _seed_diag_bank(db_session, n_kps=2)
        _, _, _, headers = registered_user
        st = await _start_self_test(client, headers, bank["subject_id"])
        resp = await client.post(
            "/api/v1/diagnose/report",
            headers=headers,
            json={
                "report_id": st["report_id"],
                "answers": [
                    {"question_id": bank["q_ids"][0], "answer": "B"},  # 错 → weak
                    {"question_id": bank["q_ids"][1], "answer": "A"},  # 对 → consolidating
                ],
            },
        )
        body = resp.json()
        assert body["weak_top5"][0]["knowledge_point_name"] == "诊断知识点0", (
            "薄弱项应 rank=1；当前 consolidating 排前 → D-11"
        )

    async def test_report_idempotent(self, client, db_session, registered_user):
        """重复提交同一报告 → 返回既有 completed 报告，不重复写。"""
        bank = await _seed_diag_bank(db_session, n_kps=2)
        _, _, _, headers = registered_user
        st = await _start_self_test(client, headers, bank["subject_id"])
        payload = {
            "report_id": st["report_id"],
            "answers": [{"question_id": bank["q_ids"][0], "answer": "B"}],
        }
        r1 = await client.post("/api/v1/diagnose/report", headers=headers, json=payload)
        assert r1.status_code == 200
        assert r1.json()["status"] == "completed"

        r2 = await client.post("/api/v1/diagnose/report", headers=headers, json=payload)
        assert r2.status_code == 200
        assert r2.json()["status"] == "completed"
        assert "already submitted" in r2.json()["summary"].lower()

    async def test_report_404_unknown(self, client, registered_user):
        _, _, _, headers = registered_user
        resp = await client.post(
            "/api/v1/diagnose/report",
            headers=headers,
            json={"report_id": str(uuid.uuid4()), "answers": []},
        )
        assert resp.status_code == 404

    async def test_report_404_other_user(self, client, db_session, registered_user):
        """不能提交他人报告（数据隔离）。"""
        bank = await _seed_diag_bank(db_session, n_kps=1)
        _, _, _, headers_a = registered_user
        st = await _start_self_test(client, headers_a, bank["subject_id"])
        from tests.conftest import _register_user
        _, _, token_b = await _register_user(client, _rand("user_b"))
        headers_b = {"Authorization": f"Bearer {token_b}"}
        resp = await client.post(
            "/api/v1/diagnose/report",
            headers=headers_b,
            json={"report_id": st["report_id"], "answers": []},
        )
        assert resp.status_code == 404
