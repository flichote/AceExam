"""API 层测试 — 题库：列表筛选 / 详情 / 创建 / 提交判定 / 幂等性。

验收点（flows.md 流程1）：
- 列表按 subject_id 过滤，支持 knowledge_point_id / difficulty 筛选与分页
- 提交正确 → correct=True；错误 → 错题入库（wrong_answer_id 非空）
- 幂等性：同一题重复提交错误，不产生重复错题记录
"""
import uuid

import pytest

from tests.conftest import _rand, _auth_headers, _register_user


async def _mk_question_payload(subject_id: str, kp_id: str | None = None) -> dict:
    return {
        "type": "single",
        "content": f"测试题目 {_rand('q')}",
        "options": {"A": "选项A", "B": "选项B", "C": "选项C", "D": "选项D"},
        "answer": {"correct": "B"},
        "analysis": "解析内容",
        "difficulty": 2,
        "source": "self_built",
        "knowledge_point_id": kp_id,
    }


class TestQuestionList:
    async def test_list_requires_auth(self, client):
        resp = await client.get("/api/v1/questions", params={"subject_id": str(uuid.uuid4())})
        assert resp.status_code == 401

    async def test_list_empty(self, client, registered_user, seed_subject):
        _, _, _, headers = registered_user
        resp = await client.get(
            "/api/v1/questions",
            params={"subject_id": seed_subject["id"]},
            headers=headers,
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["items"] == []
        assert body["total"] == 0

    async def test_list_filters_by_difficulty(self, client, registered_user, seed_question):
        _, _, _, headers = registered_user
        sid = seed_question["subject_id"]
        # difficulty=2 命中
        r2 = await client.get(
            "/api/v1/questions",
            params={"subject_id": sid, "difficulty": 2},
            headers=headers,
        )
        assert r2.status_code == 200
        assert r2.json()["total"] >= 1
        # difficulty=5 不命中
        r5 = await client.get(
            "/api/v1/questions",
            params={"subject_id": sid, "difficulty": 5},
            headers=headers,
        )
        assert r5.json()["total"] == 0

    async def test_list_filters_by_kp(self, client, registered_user, seed_question):
        _, _, _, headers = registered_user
        r = await client.get(
            "/api/v1/questions",
            params={"subject_id": seed_question["subject_id"], "knowledge_point_id": seed_question["knowledge_point_id"]},
            headers=headers,
        )
        assert r.status_code == 200
        assert r.json()["total"] >= 1
        # 不存在的 kp → 0
        r2 = await client.get(
            "/api/v1/questions",
            params={"subject_id": seed_question["subject_id"], "knowledge_point_id": str(uuid.uuid4())},
            headers=headers,
        )
        assert r2.json()["total"] == 0

    async def test_list_pagination(self, client, registered_user, seed_subject, seed_kp):
        _, _, _, headers = registered_user
        sid = seed_subject["id"]
        # 插入 3 题
        for i in range(3):
            payload = await _mk_question_payload(sid, seed_kp["id"])
            await client.post(
                "/api/v1/questions",
                params={"subject_id": sid},
                json=payload,
                headers=headers,
            )
        r = await client.get(
            "/api/v1/questions",
            params={"subject_id": sid, "page": 1, "page_size": 2},
            headers=headers,
        )
        body = r.json()
        assert body["total"] == 3
        assert len(body["items"]) == 2
        assert body["page"] == 1


class TestQuestionGet:
    async def test_get_question_detail(self, client, registered_user, seed_question):
        _, _, _, headers = registered_user
        resp = await client.get(
            f"/api/v1/questions/{seed_question['id']}", headers=headers
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == seed_question["id"]
        # 列表/详情响应不泄露答案
        assert "answer" not in data
        assert "analysis" not in data

    async def test_get_question_not_found(self, client, registered_user):
        _, _, _, headers = registered_user
        resp = await client.get(
            f"/api/v1/questions/{uuid.uuid4()}", headers=headers
        )
        assert resp.status_code == 404


class TestQuestionCreate:
    async def test_create_requires_auth(self, client):
        resp = await client.post(
            "/api/v1/questions",
            params={"subject_id": str(uuid.uuid4())},
            json=await _mk_question_payload(str(uuid.uuid4())),
        )
        assert resp.status_code == 401

    async def test_create_question(self, client, registered_user, seed_subject, seed_kp):
        _, _, _, headers = registered_user
        payload = await _mk_question_payload(seed_subject["id"], seed_kp["id"])
        resp = await client.post(
            "/api/v1/questions",
            params={"subject_id": seed_subject["id"]},
            json=payload,
            headers=headers,
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["content"] == payload["content"]
        assert data["type"] == "single"


class TestQuestionSubmit:
    async def test_submit_correct(self, client, registered_user, seed_question):
        _, _, _, headers = registered_user
        resp = await client.post(
            f"/api/v1/questions/{seed_question['id']}/submit",
            json={"answer": {"correct": "A"}},
            headers=headers,
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["correct"] is True
        assert body["wrong_answer_id"] is None

    async def test_submit_wrong_creates_wrong_answer(self, client, registered_user, seed_question):
        _, _, _, headers = registered_user
        resp = await client.post(
            f"/api/v1/questions/{seed_question['id']}/submit",
            json={"answer": {"correct": "C"}},
            headers=headers,
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["correct"] is False
        assert body["wrong_answer_id"] is not None

        # 错题本应出现记录
        wa_resp = await client.get("/api/v1/wrong-answers", headers=headers)
        assert wa_resp.status_code == 200
        assert len(wa_resp.json()) == 1

    async def test_submit_wrong_idempotent(self, client, registered_user, seed_question):
        """幂等性：同一用户对同一题重复提交错误，只产生一条错题记录。"""
        _, _, _, headers = registered_user
        body = {"answer": {"correct": "C"}}
        r1 = await client.post(
            f"/api/v1/questions/{seed_question['id']}/submit",
            json=body,
            headers=headers,
        )
        r2 = await client.post(
            f"/api/v1/questions/{seed_question['id']}/submit",
            json=body,
            headers=headers,
        )
        assert r1.status_code == 200 and r2.status_code == 200
        assert r1.json()["wrong_answer_id"] == r2.json()["wrong_answer_id"]
        wa_resp = await client.get("/api/v1/wrong-answers", headers=headers)
        assert len(wa_resp.json()) == 1

    async def test_submit_question_not_found(self, client, registered_user):
        _, _, _, headers = registered_user
        resp = await client.post(
            f"/api/v1/questions/{uuid.uuid4()}/submit",
            json={"answer": {"correct": "A"}},
            headers=headers,
        )
        assert resp.status_code == 404
