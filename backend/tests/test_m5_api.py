"""Tests for M5 课程归一对齐 + UGC 审核流 API endpoints.

Covers:
  - GET /courses/aliases (alias lookup)
  - POST /courses/match (course matching)
  - POST /me/courses (add course instance) + GET /me/courses (list)
  - POST /ugc/upload (UGC with AI review) + GET /ugc/status
"""
import uuid

import pytest

from tests.conftest import _rand


def _headers(reg_user) -> dict:
    return reg_user[3]


# ═══════════════════════════════════════════════════════════════════════
# GET /courses/aliases
# ═══════════════════════════════════════════════════════════════════════


class TestCoursesAliases:

    async def test_requires_auth(self, client):
        resp = await client.get("/api/v1/courses/aliases")
        assert resp.status_code == 401

    async def test_empty_returns_empty(self, client, registered_user):
        """No aliases seeded → returns empty list."""
        resp = await client.get(
            "/api/v1/courses/aliases",
            headers=_headers(registered_user),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["items"] == []
        assert data["total"] == 0

    async def test_with_query_parameter(self, client, registered_user):
        """Query with q= should not error even with empty DB."""
        resp = await client.get(
            "/api/v1/courses/aliases?q=高数&limit=5",
            headers=_headers(registered_user),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 0


# ═══════════════════════════════════════════════════════════════════════
# POST /courses/match
# ═══════════════════════════════════════════════════════════════════════


class TestCoursesMatch:

    async def test_requires_auth(self, client):
        resp = await client.post("/api/v1/courses/match", json={"name": "高等数学"})
        assert resp.status_code == 401

    async def test_match_uses_mock(self, client, registered_user):
        """Mock returns candidates for known course names."""
        resp = await client.post(
            "/api/v1/courses/match",
            json={"name": "高等数学", "limit": 5},
            headers=_headers(registered_user),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "matched" in data
        assert "candidates" in data
        assert "strategy" in data

    async def test_unknown_course_no_match(self, client, registered_user):
        """Unknown course name → no match."""
        resp = await client.post(
            "/api/v1/courses/match",
            json={"name": "量子力学进阶", "limit": 5},
            headers=_headers(registered_user),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["matched"] is False
        assert data["candidates"] == []

    async def test_name_too_long(self, client, registered_user):
        resp = await client.post(
            "/api/v1/courses/match",
            json={"name": "x" * 101, "limit": 5},
            headers=_headers(registered_user),
        )
        assert resp.status_code == 422

    async def test_name_empty(self, client, registered_user):
        resp = await client.post(
            "/api/v1/courses/match",
            json={"name": "", "limit": 5},
            headers=_headers(registered_user),
        )
        assert resp.status_code == 422


# ═══════════════════════════════════════════════════════════════════════
# POST /me/courses + GET /me/courses
# ═══════════════════════════════════════════════════════════════════════


class TestMeCourses:

    async def test_requires_auth(self, client):
        resp = await client.post("/api/v1/me/courses", json={"name": "高等数学"})
        assert resp.status_code == 401

    async def test_add_school_course_no_template(self, client, registered_user):
        """Add a school course without template → level='school' instance created."""
        resp = await client.post(
            "/api/v1/me/courses",
            json={"name": "清华·高数A", "school": "清华大学"},
            headers=_headers(registered_user),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["subject"]["name"] == "清华·高数A"
        assert data["matched"] is False
        assert data["user_subject"]["subject_id"] is not None
        assert data["user_subject"]["template_subject_id"] is None

    async def test_add_duplicate_school_course(self, client, registered_user):
        """Duplicate school course → 409 ALREADY_EXISTS."""
        headers = _headers(registered_user)
        # First add
        resp1 = await client.post(
            "/api/v1/me/courses",
            json={"name": "清华·高数A"},
            headers=headers,
        )
        assert resp1.status_code == 200

        # Second add same
        resp2 = await client.post(
            "/api/v1/me/courses",
            json={"name": "清华·高数A"},
            headers=headers,
        )
        assert resp2.status_code == 409

    async def test_add_template_course_not_found(self, client, registered_user):
        """Template subject_id that doesn't exist → 404."""
        resp = await client.post(
            "/api/v1/me/courses",
            json={"name": "高等数学", "template_subject_id": str(uuid.uuid4())},
            headers=_headers(registered_user),
        )
        assert resp.status_code == 404

    async def test_list_my_courses_empty(self, client, registered_user):
        """GET /me/courses with no courses → empty list."""
        resp = await client.get(
            "/api/v1/me/courses",
            headers=_headers(registered_user),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["items"] == []
        assert data["total"] == 0

    async def test_list_my_courses_after_add(self, client, registered_user):
        """After adding, list shows the course."""
        headers = _headers(registered_user)
        # Add
        await client.post(
            "/api/v1/me/courses",
            json={"name": "清华·高数A"},
            headers=headers,
        )
        # List
        resp = await client.get("/api/v1/me/courses", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["items"]) == 1
        assert data["items"][0]["subject"]["name"] == "清华·高数A"


# ═══════════════════════════════════════════════════════════════════════
# POST /ugc/upload + GET /ugc/status
# ═══════════════════════════════════════════════════════════════════════


class TestUGCUpload:

    async def test_requires_auth(self, client):
        resp = await client.post("/api/v1/ugc/upload", json={})
        assert resp.status_code == 401

    async def test_upload_with_short_content(self, client, registered_user, seed_subject, seed_kp):
        """Content < 15 chars → 422."""
        resp = await client.post(
            "/api/v1/ugc/upload",
            json={
                "subject_id": seed_subject["id"],
                "knowledge_point_id": seed_kp["id"],
                "type": "single",
                "content": "short",
            },
            headers=_headers(registered_user),
        )
        assert resp.status_code == 422

    async def test_upload_success_pending(self, client, registered_user, seed_subject, seed_kp):
        """Valid UGC upload → 201 with status=pending and AI review."""
        resp = await client.post(
            "/api/v1/ugc/upload",
            json={
                "subject_id": seed_subject["id"],
                "knowledge_point_id": seed_kp["id"],
                "type": "single",
                "content": "求函数 f(x)=x^3 在 x=1 处的导数是多少？",
                "options": [
                    {"key": "A", "text": "1"},
                    {"key": "B", "text": "2"},
                    {"key": "C", "text": "3"},
                    {"key": "D", "text": "0"},
                ],
                "answer": "C",
            },
            headers=_headers(registered_user),
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["status"] in ("pending", "active")
        assert data["question_id"] is not None
        assert data["duplicated"] is False

    async def test_upload_subject_not_found(self, client, registered_user, seed_kp):
        """Non-existent subject → 404."""
        resp = await client.post(
            "/api/v1/ugc/upload",
            json={
                "subject_id": str(uuid.uuid4()),
                "knowledge_point_id": seed_kp["id"],
                "type": "single",
                "content": "求函数 f(x)=x^3 在 x=1 处的导数是多少？",
                "options": [
                    {"key": "A", "text": "1"},
                    {"key": "B", "text": "2"},
                    {"key": "C", "text": "3"},
                    {"key": "D", "text": "0"},
                ],
                "answer": "C",
            },
            headers=_headers(registered_user),
        )
        assert resp.status_code == 404

    async def test_upload_kp_not_found(self, client, registered_user, seed_subject):
        """Non-existent knowledge point → 404."""
        resp = await client.post(
            "/api/v1/ugc/upload",
            json={
                "subject_id": seed_subject["id"],
                "knowledge_point_id": str(uuid.uuid4()),
                "type": "single",
                "content": "求函数 f(x)=x^3 在 x=1 处的导数是多少？",
                "options": [
                    {"key": "A", "text": "1"},
                    {"key": "B", "text": "2"},
                    {"key": "C", "text": "3"},
                    {"key": "D", "text": "0"},
                ],
                "answer": "C",
            },
            headers=_headers(registered_user),
        )
        assert resp.status_code == 404

    async def test_upload_with_skip_ai_review(self, client, registered_user, seed_subject, seed_kp):
        """skip_ai_review=True → AI review skipped."""
        resp = await client.post(
            "/api/v1/ugc/upload",
            json={
                "subject_id": seed_subject["id"],
                "knowledge_point_id": seed_kp["id"],
                "type": "single",
                "content": "求函数 f(x)=x^3 在 x=1 处的导数是多少？",
                "options": [
                    {"key": "A", "text": "1"},
                    {"key": "B", "text": "2"},
                    {"key": "C", "text": "3"},
                    {"key": "D", "text": "0"},
                ],
                "answer": "C",
                "skip_ai_review": True,
            },
            headers=_headers(registered_user),
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["ai_review"] is None


class TestUGCStatus:

    async def test_requires_auth(self, client):
        resp = await client.get("/api/v1/ugc/status")
        assert resp.status_code == 401

    async def test_empty_status(self, client, registered_user):
        """No uploads yet → empty list."""
        resp = await client.get(
            "/api/v1/ugc/status",
            headers=_headers(registered_user),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["items"] == []
        assert data["total"] == 0
        assert data["page"] == 1
        assert data["page_size"] == 20

    async def test_status_after_upload(self, client, registered_user, seed_subject, seed_kp):
        """After upload, status endpoint shows the question."""
        headers = _headers(registered_user)

        # Upload
        await client.post(
            "/api/v1/ugc/upload",
            json={
                "subject_id": seed_subject["id"],
                "knowledge_point_id": seed_kp["id"],
                "type": "single",
                "content": "求函数 f(x)=x^3 在 x=1 处的导数是多少？",
                "options": [
                    {"key": "A", "text": "1"},
                    {"key": "B", "text": "2"},
                    {"key": "C", "text": "3"},
                    {"key": "D", "text": "0"},
                ],
                "answer": "C",
            },
            headers=headers,
        )

        # Check status
        resp = await client.get("/api/v1/ugc/status", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["items"]) == 1
        assert data["items"][0]["type"] == "single"
        assert "导数" in data["items"][0]["content"]

    async def test_status_filter(self, client, registered_user, seed_subject, seed_kp):
        """Status filter works."""
        headers = _headers(registered_user)

        # Upload
        await client.post(
            "/api/v1/ugc/upload",
            json={
                "subject_id": seed_subject["id"],
                "knowledge_point_id": seed_kp["id"],
                "type": "single",
                "content": "求函数 f(x)=x^3 在 x=1 处的导数是多少？",
                "options": [
                    {"key": "A", "text": "1"},
                    {"key": "B", "text": "2"},
                    {"key": "C", "text": "3"},
                    {"key": "D", "text": "0"},
                ],
                "answer": "C",
            },
            headers=headers,
        )

        # Filter by pending
        resp = await client.get("/api/v1/ugc/status?status=pending", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 1

        # Filter by rejected → should be empty
        resp = await client.get("/api/v1/ugc/status?status=rejected", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 0
