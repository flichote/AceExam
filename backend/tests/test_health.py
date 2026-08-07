"""Tests for the /healthz endpoint and app boot.

The health endpoint is the simplest integration test — if this passes,
the FastAPI app is correctly wired and serving.
"""

import pytest


@pytest.mark.anyio
async def test_healthz_returns_200(client):
    """RED → GREEN: /api/v1/healthz returns ok."""
    resp = await client.get("/api/v1/healthz")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert data["service"] == "AceExam"
