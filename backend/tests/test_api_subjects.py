"""API 层测试 — 科目：列表 / 创建 / 重复 code / 知识点查询 / 401。"""
import pytest

from tests.conftest import _rand, _auth_headers


class TestSubjectsList:
    async def test_list_subjects_empty(self, client):
        resp = await client.get("/api/v1/subjects")
        assert resp.status_code == 200
        assert resp.json() == []

    async def test_list_subjects_after_seed(self, client, seed_subject):
        resp = await client.get("/api/v1/subjects")
        assert resp.status_code == 200
        items = resp.json()
        assert len(items) == 1
        assert items[0]["code"] == seed_subject["code"]
        assert items[0]["is_active"] is True

    async def test_list_subjects_public_no_auth(self, client):
        """列表接口公开（无需登录）——按产品设定科目列表对游客可见。"""
        resp = await client.get("/api/v1/subjects")
        assert resp.status_code == 200


class TestSubjectCreate:
    async def test_create_subject_requires_auth(self, client):
        resp = await client.post(
            "/api/v1/subjects",
            json={"code": _rand("s"), "name": "科目", "description": "d"},
        )
        assert resp.status_code == 401

    async def test_create_subject_success(self, client, registered_user):
        _, _, _, headers = registered_user
        code = _rand("math")
        resp = await client.post(
            "/api/v1/subjects",
            json={"code": code, "name": "高等数学", "description": "微积分", "config": {"formula_enabled": True}},
            headers=headers,
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["code"] == code
        assert data["name"] == "高等数学"
        assert data["is_active"] is True

    async def test_create_subject_duplicate_code_409(self, client, registered_user):
        _, _, _, headers = registered_user
        code = _rand("dup")
        payload = {"code": code, "name": "同名科目", "description": None}
        r1 = await client.post("/api/v1/subjects", json=payload, headers=headers)
        assert r1.status_code == 201
        r2 = await client.post("/api/v1/subjects", json=payload, headers=headers)
        assert r2.status_code == 409

    async def test_create_subject_missing_fields_422(self, client, registered_user):
        _, _, _, headers = registered_user
        resp = await client.post("/api/v1/subjects", json={"code": "x"}, headers=headers)
        assert resp.status_code == 422


class TestKnowledgePoints:
    async def test_list_knowledge_points_requires_auth(self, client):
        resp = await client.get("/api/v1/subjects/00000000-0000-0000-0000-000000000000/knowledge-points")
        assert resp.status_code == 401

    async def test_list_knowledge_points_empty(self, client, registered_user, seed_subject):
        _, _, _, headers = registered_user
        resp = await client.get(
            f"/api/v1/subjects/{seed_subject['id']}/knowledge-points",
            headers=headers,
        )
        assert resp.status_code == 200
        assert resp.json() == []

    async def test_list_knowledge_points_with_kp(self, client, registered_user, seed_kp):
        _, _, _, headers = registered_user
        resp = await client.get(
            f"/api/v1/subjects/{seed_kp['subject_id']}/knowledge-points",
            headers=headers,
        )
        assert resp.status_code == 200
        items = resp.json()
        assert len(items) == 1
        assert items[0]["name"] == seed_kp["name"]

    async def test_knowledge_point_tree(self, client, registered_user, seed_kp):
        _, _, _, headers = registered_user
        resp = await client.get(
            "/api/v1/knowledge-points/tree",
            params={"subject_id": seed_kp["subject_id"]},
            headers=headers,
        )
        assert resp.status_code == 200
        roots = resp.json()
        assert len(roots) == 1
        assert roots[0]["id"] == seed_kp["id"]
