"""API 层测试 — 错题本：列表 / 创建 / 重复创建 / 删除 / 标记掌握 / 状态过滤。"""
import uuid

import pytest

from tests.conftest import _rand, _auth_headers, _register_user


class TestWrongAnswerList:
    async def test_list_requires_auth(self, client):
        resp = await client.get("/api/v1/wrong-answers")
        assert resp.status_code == 401

    async def test_list_empty(self, client, registered_user):
        _, _, _, headers = registered_user
        resp = await client.get("/api/v1/wrong-answers", headers=headers)
        assert resp.status_code == 200
        assert resp.json() == []

    async def test_list_with_records(self, client, registered_user, seed_question):
        _, _, _, headers = registered_user
        # 先提交错误答案生成错题
        await client.post(
            f"/api/v1/questions/{seed_question['id']}/submit",
            json={"answer": {"correct": "C"}},
            headers=headers,
        )
        resp = await client.get("/api/v1/wrong-answers", headers=headers)
        assert resp.status_code == 200
        items = resp.json()
        assert len(items) == 1
        assert items[0]["question_id"] == seed_question["id"]
        assert items[0]["mastered"] is False
        assert items[0]["question_content"]  # join 出题面内容


class TestWrongAnswerCreate:
    async def test_create_wrong_answer(self, client, registered_user, seed_question):
        _, _, _, headers = registered_user
        resp = await client.post(
            "/api/v1/wrong-answers",
            json={
                "question_id": seed_question["id"],
                "subject_id": seed_question["subject_id"],
                "wrong_reason": "概念混淆",
            },
            headers=headers,
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["question_id"] == seed_question["id"]
        assert data["mastered"] is False

    async def test_create_duplicate_409(self, client, registered_user, seed_question):
        _, _, _, headers = registered_user
        payload = {
            "question_id": seed_question["id"],
            "subject_id": seed_question["subject_id"],
            "wrong_reason": "x",
        }
        r1 = await client.post("/api/v1/wrong-answers", json=payload, headers=headers)
        assert r1.status_code == 201
        r2 = await client.post("/api/v1/wrong-answers", json=payload, headers=headers)
        assert r2.status_code == 409


class TestWrongAnswerDelete:
    async def test_delete_wrong_answer(self, client, registered_user, seed_question):
        _, _, _, headers = registered_user
        created = await client.post(
            "/api/v1/wrong-answers",
            json={"question_id": seed_question["id"], "subject_id": seed_question["subject_id"]},
            headers=headers,
        )
        wa_id = created.json()["id"]
        resp = await client.delete(f"/api/v1/wrong-answers/{wa_id}", headers=headers)
        assert resp.status_code == 204
        # 删除后列表为空
        listing = await client.get("/api/v1/wrong-answers", headers=headers)
        assert listing.json() == []

    async def test_delete_missing_404(self, client, registered_user):
        _, _, _, headers = registered_user
        resp = await client.delete(
            f"/api/v1/wrong-answers/{uuid.uuid4()}", headers=headers
        )
        assert resp.status_code == 404

    async def test_delete_other_users_record_404(self, client, registered_user, seed_question):
        _, _, _, headers = registered_user
        created = await client.post(
            "/api/v1/wrong-answers",
            json={"question_id": seed_question["id"], "subject_id": seed_question["subject_id"]},
            headers=headers,
        )
        wa_id = created.json()["id"]
        # 第二个用户删除别人的记录 → 404（按 user_id 过滤）
        _, _, token2 = await _register_user(client)
        headers2 = await _auth_headers(token2)
        resp = await client.delete(f"/api/v1/wrong-answers/{wa_id}", headers=headers2)
        assert resp.status_code == 404


class TestWrongAnswerMastered:
    async def test_mark_mastered(self, client, registered_user, seed_question):
        _, _, _, headers = registered_user
        created = await client.post(
            "/api/v1/wrong-answers",
            json={"question_id": seed_question["id"], "subject_id": seed_question["subject_id"]},
            headers=headers,
        )
        wa_id = created.json()["id"]
        resp = await client.post(
            f"/api/v1/wrong-answers/{wa_id}/mastered", headers=headers
        )
        assert resp.status_code == 200
        assert resp.json()["mastered"] is True

    async def test_status_filter(self, client, registered_user, seed_question):
        _, _, _, headers = registered_user
        created = await client.post(
            "/api/v1/wrong-answers",
            json={"question_id": seed_question["id"], "subject_id": seed_question["subject_id"]},
            headers=headers,
        )
        wa_id = created.json()["id"]
        await client.post(f"/api/v1/wrong-answers/{wa_id}/mastered", headers=headers)

        active = await client.get(
            "/api/v1/wrong-answers", params={"status": "active"}, headers=headers
        )
        mastered = await client.get(
            "/api/v1/wrong-answers", params={"status": "mastered"}, headers=headers
        )
        assert active.json() == []
        assert len(mastered.json()) == 1
        assert mastered.json()[0]["mastered"] is True

    async def test_mark_mastered_missing_404(self, client, registered_user):
        _, _, _, headers = registered_user
        resp = await client.post(
            f"/api/v1/wrong-answers/{uuid.uuid4()}/mastered", headers=headers
        )
        assert resp.status_code == 404
