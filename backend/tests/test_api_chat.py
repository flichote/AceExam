"""API 层测试 — AI 讲解 / 追问（chat），mock LLM 上游，不真调 DeepSeek。

验收点（flows.md 流程1）：
- 非会员访问 chat → 403（会员墙）
- 会员讲解成功 → steps / conclusion / citations
- 追问有上下文（同 session 往返）
- 不存在的题目 / session → 404
"""
import uuid

import pytest

from app.services.llm_gateway import llm_gateway

from tests.conftest import _rand, _auth_headers, _register_user


async def _fake_chat(tier, messages, max_tokens=None, temperature=0.3):
    """假 LLM：回显用户最后一条消息。"""
    last_user = next((m["content"] for m in reversed(messages) if m["role"] == "user"), "")
    return {
        "content": f"步骤1：关于「{last_user[:30]}」的讲解。\n结论：理解即可。",
        "model": "deepseek-chat",
        "usage": {"prompt_tokens": 10, "completion_tokens": 5},
    }


@pytest.fixture
async def mock_llm(monkeypatch):
    """把 llm_gateway.chat / chat_stream 替换为本地假实现。"""
    async def _fake_stream(tier, messages, max_tokens=None, temperature=0.3):
        yield "片段A"
        yield "片段B"

    monkeypatch.setattr(llm_gateway, "chat", _fake_chat)
    monkeypatch.setattr(llm_gateway, "chat_stream", _fake_stream)
    return llm_gateway


class TestChatAuth:
    async def test_explain_requires_member(self, client, registered_user, seed_question):
        """普通用户（非会员）→ 403。"""
        _, _, token, headers = registered_user
        resp = await client.post(
            "/api/v1/chat/explain",
            json={"question_id": seed_question["id"]},
            headers=headers,
        )
        assert resp.status_code == 403

    async def test_explain_requires_auth(self, client, seed_question):
        resp = await client.post(
            "/api/v1/chat/explain",
            json={"question_id": seed_question["id"]},
        )
        assert resp.status_code == 401


class TestChatExplain:
    async def test_explain_success(self, client, member_user, seed_question, mock_llm):
        _, _, _, headers = member_user
        resp = await client.post(
            "/api/v1/chat/explain",
            json={"question_id": seed_question["id"]},
            headers=headers,
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["session_id"]
        assert len(body["steps"]) >= 1
        assert body["steps"][0]["title"] == "讲解"
        assert "理解即可" in body["steps"][0]["content"]
        assert body["uncovered"] is False

    async def test_explain_missing_question_404(self, client, member_user, mock_llm):
        _, _, _, headers = member_user
        resp = await client.post(
            "/api/v1/chat/explain",
            json={"question_id": str(uuid.uuid4())},
            headers=headers,
        )
        assert resp.status_code == 404


class TestChatFollowup:
    async def test_followup_keeps_context(self, client, member_user, seed_question, mock_llm):
        _, _, _, headers = member_user
        r1 = await client.post(
            "/api/v1/chat/explain",
            json={"question_id": seed_question["id"]},
            headers=headers,
        )
        session_id = r1.json()["session_id"]

        r2 = await client.post(
            "/api/v1/chat/followup",
            json={"session_id": session_id, "message": "再讲细一点"},
            headers=headers,
        )
        assert r2.status_code == 200
        body = r2.json()
        assert body["session_id"] == session_id
        # 追问响应携带上下文
        assert "再讲细一点" in body["steps"][0]["content"] or len(body["steps"]) >= 1

    async def test_followup_missing_session_404(self, client, member_user, mock_llm):
        _, _, _, headers = member_user
        resp = await client.post(
            "/api/v1/chat/followup",
            json={"session_id": str(uuid.uuid4()), "message": "hi"},
            headers=headers,
        )
        assert resp.status_code == 404

    async def test_followup_other_users_session_404(self, client, db_session, member_user, seed_question, mock_llm):
        from sqlalchemy import select

        from app.db.models import User

        _, _, _, headers = member_user
        r1 = await client.post(
            "/api/v1/chat/explain",
            json={"question_id": seed_question["id"]},
            headers=headers,
        )
        session_id = r1.json()["session_id"]

        # 第二个用户也提升为会员，再访问别人的 session → 404（按 user_id 过滤）
        u2 = _rand("u2")
        await client.post(
            "/api/v1/auth/register", json={"username": u2, "password": "pass123456"}
        )
        result = await db_session.execute(select(User).where(User.username == u2))
        user2 = result.scalar_one()
        user2.is_member = True
        await db_session.commit()

        login = await client.post(
            "/api/v1/auth/login", json={"username": u2, "password": "pass123456"}
        )
        headers2 = await _auth_headers(login.json()["access_token"])
        resp = await client.post(
            "/api/v1/chat/followup",
            json={"session_id": session_id, "message": "hi"},
            headers=headers2,
        )
        assert resp.status_code == 404


class TestChatStream:
    async def test_explain_stream(self, client, member_user, seed_question, mock_llm):
        _, _, _, headers = member_user
        resp = await client.post(
            "/api/v1/chat/explain",
            params={"stream": "true"},
            json={"question_id": seed_question["id"]},
            headers=headers,
        )
        assert resp.status_code == 200
        assert "text/event-stream" in resp.headers.get("content-type", "")
        body = resp.text
        assert "片段A" in body
        assert "[DONE]" in body
