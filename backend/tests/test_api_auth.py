"""API 层测试 — 认证：注册 / 登录 / 重复用户名 / /me / 401。

验收点（docs/design/flows.md 流程1 前置）：
- 注册成功返回 201 + access_token
- 重复用户名返回 409
- 登录成功返回 200 + token
- 密码错误返回 401
- 带 token 访问 /me 返回用户信息
- 未带 token 访问受保护端点返回 401
"""
import pytest

from tests.conftest import _rand, _register_user, _auth_headers


# ═══════════════════════════════════════════════════════════════════════
# 注册
# ═══════════════════════════════════════════════════════════════════════


class TestRegister:
    async def test_register_returns_token(self, client):
        resp = await client.post(
            "/api/v1/auth/register",
            json={"username": _rand("u"), "password": "pass123456"},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"

    async def test_register_duplicate_username_conflict(self, client):
        username = _rand("dup")
        await client.post(
            "/api/v1/auth/register",
            json={"username": username, "password": "pass123456"},
        )
        # 重复注册同一用户名 → 409
        resp2 = await client.post(
            "/api/v1/auth/register",
            json={"username": username, "password": "other123456"},
        )
        assert resp2.status_code == 409

    async def test_register_short_password_rejected(self, client):
        resp = await client.post(
            "/api/v1/auth/register",
            json={"username": _rand("u"), "password": "123"},
        )
        assert resp.status_code == 422

    async def test_register_short_username_rejected(self, client):
        resp = await client.post(
            "/api/v1/auth/register",
            json={"username": "a", "password": "pass123456"},
        )
        assert resp.status_code == 422


# ═══════════════════════════════════════════════════════════════════════
# 登录
# ═══════════════════════════════════════════════════════════════════════


class TestLogin:
    async def test_login_success(self, client):
        username, password, _ = await _register_user(client)
        resp = await client.post(
            "/api/v1/auth/login",
            json={"username": username, "password": password},
        )
        assert resp.status_code == 200
        assert "access_token" in resp.json()

    async def test_login_wrong_password_401(self, client):
        username, _, _ = await _register_user(client)
        resp = await client.post(
            "/api/v1/auth/login",
            json={"username": username, "password": "wrong-pass"},
        )
        assert resp.status_code == 401

    async def test_login_unknown_user_401(self, client):
        resp = await client.post(
            "/api/v1/auth/login",
            json={"username": _rand("nobody"), "password": "pass123456"},
        )
        assert resp.status_code == 401


# ═══════════════════════════════════════════════════════════════════════
# /me 与鉴权
# ═══════════════════════════════════════════════════════════════════════


class TestMe:
    async def test_me_with_token(self, client):
        username, _, token = await _register_user(client)
        resp = await client.get(
            "/api/v1/auth/me", headers=await _auth_headers(token)
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["username"] == username
        assert data["is_active"] is True

    async def test_me_without_token_401(self, client):
        resp = await client.get("/api/v1/auth/me")
        assert resp.status_code == 401

    async def test_me_with_invalid_token_401(self, client):
        resp = await client.get(
            "/api/v1/auth/me", headers=await _auth_headers("not-a-jwt")
        )
        assert resp.status_code == 401

    async def test_register_login_me_flow(self, client):
        """注册 → 登录 → 带 token 访问 /me 全链路。"""
        username, password, token1 = await _register_user(client)
        resp_login = await client.post(
            "/api/v1/auth/login",
            json={"username": username, "password": password},
        )
        assert resp_login.status_code == 200
        token2 = resp_login.json()["access_token"]
        resp_me = await client.get(
            "/api/v1/auth/me", headers=await _auth_headers(token2)
        )
        assert resp_me.status_code == 200
        assert resp_me.json()["username"] == username
        # 两个 token 指向同一用户
        resp_me1 = await client.get(
            "/api/v1/auth/me", headers=await _auth_headers(token1)
        )
        assert resp_me1.json()["id"] == resp_me.json()["id"]
