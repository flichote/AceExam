"""Smoke test for M2 five-module APIs via test fixtures.

Run: cd backend && PYTHONPATH="" .venv/Scripts/python.exe -m pytest tests/test_m2_smoke.py -v --tb=short -p no:warnings
"""
import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.anyio


@pytest.mark.asyncio
async def test_m2_health(client: AsyncClient):
    resp = await client.get("/api/v1/healthz")
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_m2_plans_active_empty(client: AsyncClient, registered_user):
    """GET /plans/active returns null when no active plan exists."""
    _, _, _, headers = registered_user
    resp = await client.get("/api/v1/plans/active", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["plan"] is None
    assert data["today_task"] is None


@pytest.mark.asyncio
async def test_m2_diagnose_self_test(client: AsyncClient, registered_user, seed_kp):
    """POST /diagnose/self-test creates a report."""
    _, _, _, headers = registered_user
    resp = await client.post("/api/v1/diagnose/self-test", headers=headers, json={
        "subject_id": seed_kp["subject_id"],
        "count": 5,
        "include_weak": True,
    })
    assert resp.status_code == 201
    data = resp.json()
    assert "report_id" in data
    assert data["status"] == "in_progress"


@pytest.mark.asyncio
async def test_m2_chat_explain_non_member(client: AsyncClient, registered_user):
    """POST /chat/explain requires membership -> 403 for free user."""
    _, _, _, headers = registered_user
    resp = await client.post("/api/v1/chat/explain", headers=headers, json={
        "question_id": "550e8400-e29b-41d4-a716-446655440000",
    })
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_m2_diagnose_report_404(client: AsyncClient, registered_user):
    """GET /diagnose/self-test/{id} returns 404 for nonexistent report."""
    _, _, _, headers = registered_user
    resp = await client.get("/api/v1/diagnose/self-test/550e8400-e29b-41d4-a716-446655440999", headers=headers)
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_m2_ocr_poll_404(client: AsyncClient, registered_user):
    """GET /ocr/upload/{id} returns 404 for nonexistent upload."""
    _, _, _, headers = registered_user
    resp = await client.get("/api/v1/ocr/upload/550e8400-e29b-41d4-a716-446655440999", headers=headers)
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_m2_submit_answer_404(client: AsyncClient, registered_user):
    """POST /questions/{id}/answers returns 404 for nonexistent question."""
    _, _, _, headers = registered_user
    resp = await client.post("/api/v1/questions/550e8400-e29b-41d4-a716-446655440999/answers", headers=headers, json={
        "answer": "C", "time_spent_seconds": 30,
    })
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_m2_submit_answer_correct(client: AsyncClient, registered_user, seed_subject, seed_kp, seed_question):
    """POST /questions/{id}/answers returns correct result and updates knowledge state."""
    _, _, _, headers = registered_user
    resp = await client.post(
        f"/api/v1/questions/{seed_question['id']}/answers",
        headers=headers,
        json={"answer": seed_question["answer"], "time_spent_seconds": 30},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "correct" in data
    assert "knowledge_state" in data
    ks = data["knowledge_state"]
    assert "status" in ks
    assert "streak" in ks


@pytest.mark.asyncio
async def test_m2_plans_create_non_member(client: AsyncClient, registered_user, seed_subject):
    """POST /plans requires membership -> 403 for free user."""
    _, _, _, headers = registered_user
    resp = await client.post("/api/v1/plans", headers=headers, json={
        "subject_id": seed_subject["id"],
        "exam_date": "2026-08-28",
        "daily_question_target": 10,
        "title": "Test Plan",
    })
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_m2_plans_create_and_checkin(client: AsyncClient, member_user, seed_subject):
    """POST /plans and POST /plans/{id}/checkin for member user."""
    _, _, _, headers = member_user
    # Create plan
    resp = await client.post("/api/v1/plans", headers=headers, json={
        "subject_id": seed_subject["id"],
        "exam_date": "2026-08-28",
        "daily_question_target": 10,
        "title": "SMOKE PLAN",
    })
    assert resp.status_code == 201
    data = resp.json()
    assert "plan" in data
    assert data["plan"]["status"] == "active"
    plan_id = data["plan"]["id"]

    # Check active plan
    resp = await client.get("/api/v1/plans/active", headers=headers, params={"subject_id": seed_subject["id"]})
    assert resp.status_code == 200
    active = resp.json()
    assert active["plan"] is not None
    assert active["today_task"] is not None

    # Checkin
    resp = await client.post(f"/api/v1/plans/{plan_id}/checkin", headers=headers, json={})
    assert resp.status_code == 200
    cdata = resp.json()
    assert cdata["checked_in"] is True

    # Double checkin (idempotent)
    resp = await client.post(f"/api/v1/plans/{plan_id}/checkin", headers=headers, json={})
    assert resp.status_code == 200
    cdata = resp.json()
    assert cdata["already_checked_in"] is True
