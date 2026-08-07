"""Smoke test for M3 new APIs — knowledge graph, sprint, dashboard, leaderboard, warnings.

Run: cd backend && PYTHONPATH="" .venv/Scripts/python.exe -m pytest tests/test_m3_smoke.py -v --tb=short -p no:warnings
"""
import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.anyio


# ═══════════════════════════════════════════════════════════════════════
# Knowledge Graph
# ═══════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_knowledge_graph_404(client: AsyncClient, registered_user):
    """GET /subjects/{id}/knowledge-graph returns 404 for nonexistent subject."""
    _, _, _, headers = registered_user
    resp = await client.get(
        "/api/v1/subjects/550e8400-e29b-41d4-a716-446655440000/knowledge-graph",
        headers=headers,
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_knowledge_graph_empty(client: AsyncClient, registered_user, seed_subject):
    """GET /subjects/{id}/knowledge-graph returns 404 when no KPs exist."""
    _, _, _, headers = registered_user
    resp = await client.get(
        f"/api/v1/subjects/{seed_subject['id']}/knowledge-graph",
        headers=headers,
    )
    assert resp.status_code == 404  # no KPs → 404


@pytest.mark.asyncio
async def test_knowledge_graph_with_kps(client: AsyncClient, registered_user, seed_subject, seed_kp):
    """GET /subjects/{id}/knowledge-graph returns tree with KPs."""
    _, _, _, headers = registered_user
    resp = await client.get(
        f"/api/v1/subjects/{seed_subject['id']}/knowledge-graph",
        headers=headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["subject_id"] == seed_subject["id"]
    assert "stats" in data
    assert "root" in data


# ═══════════════════════════════════════════════════════════════════════
# Sprint (考前突击) — member only
# ═══════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_sprint_activate_403_for_free_user(client: AsyncClient, registered_user, seed_subject):
    """POST /subjects/{id}/sprint/activate returns 403 for free user."""
    _, _, _, headers = registered_user
    resp = await client.post(
        f"/api/v1/subjects/{seed_subject['id']}/sprint/activate",
        headers=headers, json={},
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_sprint_activate_member(client: AsyncClient, member_user, seed_subject):
    """POST /subjects/{id}/sprint/activate creates sprint for member."""
    _, _, _, headers = member_user
    resp = await client.post(
        f"/api/v1/subjects/{seed_subject['id']}/sprint/activate",
        headers=headers, json={},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["created"] is True
    assert data["sprint"]["status"] == "active"


@pytest.mark.asyncio
async def test_sprint_activate_idempotent(client: AsyncClient, member_user, seed_subject):
    """POST activate twice returns created=false second time."""
    _, _, _, headers = member_user
    resp1 = await client.post(
        f"/api/v1/subjects/{seed_subject['id']}/sprint/activate",
        headers=headers, json={},
    )
    assert resp1.status_code == 200
    assert resp1.json()["created"] is True

    resp2 = await client.post(
        f"/api/v1/subjects/{seed_subject['id']}/sprint/activate",
        headers=headers, json={},
    )
    assert resp2.status_code == 200
    assert resp2.json()["created"] is False


@pytest.mark.asyncio
async def test_sprint_questions_403_free(client: AsyncClient, registered_user, seed_subject):
    """GET sprint/questions returns 403 for free user."""
    _, _, _, headers = registered_user
    resp = await client.get(
        f"/api/v1/subjects/{seed_subject['id']}/sprint/questions",
        headers=headers,
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_sprint_questions_no_active(client: AsyncClient, member_user, seed_subject):
    """GET sprint/questions without activation returns 403."""
    _, _, _, headers = member_user
    resp = await client.get(
        f"/api/v1/subjects/{seed_subject['id']}/sprint/questions",
        headers=headers,
    )
    assert resp.status_code == 403  # no active session + no plan


# ═══════════════════════════════════════════════════════════════════════
# Dashboard
# ═══════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_dashboard_returns_zeros(client: AsyncClient, registered_user):
    """GET /me/dashboard returns zero values for new user."""
    _, _, _, headers = registered_user
    resp = await client.get("/api/v1/me/dashboard", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["totals"]["questions_practiced"] == 0
    assert data["totals"]["correct_count"] == 0
    assert data["streak"]["current"] == 0


@pytest.mark.asyncio
async def test_dashboard_trend(client: AsyncClient, registered_user):
    """GET /me/dashboard/trend returns trend items."""
    _, _, _, headers = registered_user
    resp = await client.get("/api/v1/me/dashboard/trend", headers=headers, params={"days": 7})
    assert resp.status_code == 200
    data = resp.json()
    assert "items" in data
    assert "granularity" in data
    assert data["granularity"] == "day"
    assert len(data["items"]) > 0


@pytest.mark.asyncio
async def test_dashboard_trend_invalid_granularity(client: AsyncClient, registered_user):
    """GET /me/dashboard/trend rejects invalid granularity."""
    _, _, _, headers = registered_user
    resp = await client.get(
        "/api/v1/me/dashboard/trend",
        headers=headers,
        params={"granularity": "hour"},
    )
    assert resp.status_code == 422


# ═══════════════════════════════════════════════════════════════════════
# Leaderboard
# ═══════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_leaderboard_global(client: AsyncClient, registered_user):
    """GET /leaderboard returns global leaderboard."""
    _, _, _, headers = registered_user
    resp = await client.get("/api/v1/leaderboard", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["scope"] == "global"
    assert "items" in data
    assert "me" in data


@pytest.mark.asyncio
async def test_leaderboard_subject_requires_id(client: AsyncClient, registered_user):
    """GET /leaderboard with scope=subject without subject_id → 422."""
    _, _, _, headers = registered_user
    resp = await client.get(
        "/api/v1/leaderboard",
        headers=headers,
        params={"scope": "subject"},
    )
    assert resp.status_code == 422


# ═══════════════════════════════════════════════════════════════════════
# Warnings (挂科预警)
# ═══════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_warnings_no_plan(client: AsyncClient, registered_user):
    """GET /me/warnings returns null overall_risk when no active plan."""
    _, _, _, headers = registered_user
    resp = await client.get("/api/v1/me/warnings", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["overall_risk"] is None
    assert data["items"] == []


@pytest.mark.asyncio
async def test_warnings_404_subject(client: AsyncClient, registered_user):
    """GET /me/warnings with nonexistent subject_id → 404."""
    _, _, _, headers = registered_user
    resp = await client.get(
        "/api/v1/me/warnings",
        headers=headers,
        params={"subject_id": "550e8400-e29b-41d4-a716-446655440000"},
    )
    assert resp.status_code == 404


# ═══════════════════════════════════════════════════════════════════════
# Sprint questions after activation
# ═══════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_sprint_questions_after_activate(client: AsyncClient, member_user, seed_subject):
    """After activation, GET sprint/questions returns question list."""
    _, _, _, headers = member_user
    # Activate
    resp = await client.post(
        f"/api/v1/subjects/{seed_subject['id']}/sprint/activate",
        headers=headers, json={},
    )
    assert resp.status_code == 200

    # Get questions
    resp = await client.get(
        f"/api/v1/subjects/{seed_subject['id']}/sprint/questions",
        headers=headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "sprint_id" in data
    assert "items" in data
    assert "summary" in data


# ═══════════════════════════════════════════════════════════════════════
# Dashboard with subject filter
# ═══════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_dashboard_subject_filter(client: AsyncClient, registered_user, seed_subject):
    """GET /me/dashboard?subject_id= filters by subject."""
    _, _, _, headers = registered_user
    resp = await client.get(
        "/api/v1/me/dashboard",
        headers=headers,
        params={"subject_id": seed_subject["id"]},
    )
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_dashboard_subject_404(client: AsyncClient, registered_user):
    """GET /me/dashboard?subject_id= returns 404 for invalid subject."""
    _, _, _, headers = registered_user
    resp = await client.get(
        "/api/v1/me/dashboard",
        headers=headers,
        params={"subject_id": "550e8400-e29b-41d4-a716-446655440000"},
    )
    assert resp.status_code == 404
