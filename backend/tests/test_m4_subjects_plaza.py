"""Tests for M4 选课+广场 API endpoints.

Covers:
  - PUT /me/profile (update major)
  - PUT /me/subjects (set semester courses, idempotent)
  - GET /me/subjects (user course list with stats)
  - GET /subjects/plaza (public course plaza with optional auth)
  - Response schema extensions: major in auth/me, is_public in subjects
"""

import uuid

import pytest

from tests.conftest import _rand


# ── helpers ──

def _headers(reg_user) -> dict:
    """Extract auth headers from registered_user fixture."""
    # reg_user = (username, password, token, headers)
    return reg_user[3]


# ── PUT /me/profile ──


@pytest.mark.anyio
class TestMeProfile:

    async def test_update_major_success(self, client, registered_user):
        resp = await client.put(
            "/api/v1/me/profile",
            json={"major": "计算机科学与技术"},
            headers=_headers(registered_user),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["major"] == "计算机科学与技术"
        assert data["username"] is not None

    async def test_update_major_empty(self, client, registered_user):
        """空串视为清除 major."""
        resp = await client.put(
            "/api/v1/me/profile",
            json={"major": ""},
            headers=_headers(registered_user),
        )
        assert resp.status_code == 200
        assert resp.json()["major"] is None

    async def test_update_major_none(self, client, registered_user):
        """None 也表示清除."""
        resp = await client.put(
            "/api/v1/me/profile",
            json={"major": None},
            headers=_headers(registered_user),
        )
        assert resp.status_code == 200
        assert resp.json()["major"] is None

    async def test_update_major_requires_auth(self, client):
        resp = await client.put("/api/v1/me/profile", json={"major": "test"})
        assert resp.status_code == 401


# ── PUT /me/subjects + GET /me/subjects ──


@pytest.mark.anyio
class TestMeSubjects:

    async def test_set_and_get(self, client, registered_user, db_session):
        """设置课程后，GET 返回一致内容."""
        from sqlalchemy import select
        from app.db.models import Subject as _S

        result = await db_session.execute(
            select(_S).where(_S.is_active == True).limit(1)
        )
        subj = result.scalar_one_or_none()
        if not subj:
            pytest.skip("No active subjects available")

        headers = _headers(registered_user)
        resp = await client.put(
            "/api/v1/me/subjects",
            json={"subject_ids": [str(subj.id)]},
            headers=headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        assert len(data["items"]) == 1
        assert data["items"][0]["subject"]["id"] == str(subj.id)
        assert "stats" in data["items"][0]

        # GET 确认
        resp2 = await client.get("/api/v1/me/subjects", headers=headers)
        assert resp2.status_code == 200
        assert resp2.json()["total"] == 1

    async def test_empty_list_clears(self, client, registered_user):
        """空数组表示清空选课."""
        resp = await client.put(
            "/api/v1/me/subjects",
            json={"subject_ids": []},
            headers=_headers(registered_user),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 0

    async def test_idempotent(self, client, registered_user, db_session):
        """重复提交相同数组结果一致."""
        from sqlalchemy import select
        from app.db.models import Subject as _S

        result = await db_session.execute(
            select(_S).where(_S.is_active == True).limit(2)
        )
        subjs = result.scalars().all()
        if len(subjs) < 2:
            pytest.skip("Need at least 2 active subjects")

        ids = [str(s.id) for s in subjs]
        headers = _headers(registered_user)

        resp1 = await client.put(
            "/api/v1/me/subjects", json={"subject_ids": ids}, headers=headers,
        )
        assert resp1.status_code == 200

        resp2 = await client.put(
            "/api/v1/me/subjects", json={"subject_ids": ids}, headers=headers,
        )
        assert resp2.status_code == 200
        assert resp2.json()["total"] == 2

    async def test_dedup(self, client, registered_user, db_session):
        """重复 subject_id 自动去重."""
        from sqlalchemy import select
        from app.db.models import Subject as _S

        result = await db_session.execute(
            select(_S).where(_S.is_active == True).limit(1)
        )
        subj = result.scalar_one_or_none()
        if not subj:
            pytest.skip("No active subject")

        resp = await client.put(
            "/api/v1/me/subjects",
            json={"subject_ids": [str(subj.id), str(subj.id)]},
            headers=_headers(registered_user),
        )
        assert resp.status_code == 200
        assert resp.json()["total"] == 1

    async def test_invalid_subject_id_422(self, client, registered_user):
        """无效 subject_id 返回 422 SUBJECT_NOT_JOINABLE."""
        resp = await client.put(
            "/api/v1/me/subjects",
            json={"subject_ids": [str(uuid.uuid4())]},
            headers=_headers(registered_user),
        )
        assert resp.status_code == 422
        detail = resp.json()["detail"]
        assert detail["code"] == "SUBJECT_NOT_JOINABLE"

    async def test_requires_auth_put(self, client):
        resp = await client.put("/api/v1/me/subjects", json={"subject_ids": []})
        assert resp.status_code == 401

    async def test_requires_auth_get(self, client):
        resp = await client.get("/api/v1/me/subjects")
        assert resp.status_code == 401


# ── GET /subjects/plaza ──


@pytest.mark.anyio
class TestPlaza:

    async def test_no_auth_ok(self, client):
        """未登录可访问，joined 恒 false."""
        resp = await client.get("/api/v1/subjects/plaza")
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data
        assert "total" in data
        for item in data["items"]:
            assert item["joined"] is False
            assert item["is_public"] is True
            assert item["is_active"] is True

    async def test_with_auth(self, client, registered_user):
        """登录后 joined 反映真实状态."""
        resp = await client.get(
            "/api/v1/subjects/plaza",
            headers=_headers(registered_user),
        )
        assert resp.status_code == 200
        for item in resp.json()["items"]:
            assert isinstance(item["joined"], bool)

    async def test_only_public_active(self, client):
        """仅返回 is_public=True 且 is_active=True."""
        resp = await client.get("/api/v1/subjects/plaza")
        assert resp.status_code == 200
        for item in resp.json()["items"]:
            assert item["is_public"] is True
            assert item["is_active"] is True

    async def test_question_count_nonnegative(self, client):
        """question_count >= 0."""
        resp = await client.get("/api/v1/subjects/plaza")
        assert resp.status_code == 200
        for item in resp.json()["items"]:
            assert isinstance(item["question_count"], int)
            assert item["question_count"] >= 0


# ── Response schema checks ──


@pytest.mark.anyio
class TestResponseSchema:

    async def test_auth_me_has_major(self, client, registered_user):
        resp = await client.get("/api/v1/auth/me", headers=_headers(registered_user))
        assert resp.status_code == 200
        data = resp.json()
        assert "major" in data
        assert data["major"] is None  # 新用户默认

    async def test_subjects_has_is_public(self, client):
        resp = await client.get("/api/v1/subjects")
        assert resp.status_code == 200
        items = resp.json()
        if len(items) > 0:
            assert "is_public" in items[0]
