"""M2 AI 讲解端到端验收测试 — /chat/explain + /chat/followup（mock 上游 LLM）。

验收点（docs/design/flows.md 流程1 / PRD）：
- AI 讲解引用教材片段（citation 命中路径透传 citations）
- 无引用命中 → uncovered=true（教材未覆盖提示，禁止编造）
- 追问有上下文（session messages 累积）

实现说明：chat API 未接入 RagEngine（缺陷 D-4 遗留），RAG 结果经由 LLM 返回
JSON 透传；本文件以 mock llm_gateway 返回 citations/uncovered 两种载荷验证
API 契约层。不真调 DeepSeek。
"""
import json
import uuid

import pytest

from app.db.models import Question
from app.services.llm_gateway import llm_gateway
from tests.conftest import _rand


def _llm_echo(payload, records=None):
    """构造假 LLM：返回指定 JSON 载荷（或纯文本），可选记录调用消息。"""

    async def _fake(tier, messages, max_tokens=None, temperature=0.3):
        if records is not None:
            records.append({"tier": tier, "messages": list(messages)})
        if isinstance(payload, str):
            content = payload
        else:
            content = json.dumps(payload, ensure_ascii=False)
        return {
            "content": content,
            "model": "deepseek-chat",
            "usage": {"prompt_tokens": 10, "completion_tokens": 5},
        }

    return _fake


@pytest.fixture
async def mock_llm(monkeypatch):
    """把 llm_gateway.chat 替换为假实现；测试内再用 monkeypatch 换 payload。"""
    calls = []

    async def _fake(tier, messages, max_tokens=None, temperature=0.3):
        calls.append({"tier": tier, "messages": list(messages)})
        return {
            "content": json.dumps({"steps": [{"title": "步骤1", "content": "默认讲解"}]}),
            "model": "deepseek-chat",
            "usage": {"prompt_tokens": 10, "completion_tokens": 5},
        }

    monkeypatch.setattr(llm_gateway, "chat", _fake)
    return calls


# ═══════════════════════════════════════════════════════════════════════════
# /chat/explain：mock RAG 检索两条路径
# ═══════════════════════════════════════════════════════════════════════════


class TestExplainRagPaths:
    async def test_citation_hit_path(self, client, member_user, seed_question, monkeypatch):
        """RAG 有引用命中：LLM 返回 citations → 响应透传 citations。"""
        payload = {
            "steps": [
                {"title": "步骤1", "content": "先看定义"},
                {"title": "步骤2", "content": "代入公式"},
            ],
            "conclusion": "导数为 0",
            "citations": [
                {"source": "高等数学教材", "chapter": "第二章 导数", "page": "45",
                 "text": "导数定义 $f'(x_0)=\\lim\\dots$"}
            ],
            "uncovered": False,
        }
        monkeypatch.setattr(llm_gateway, "chat", _llm_echo(payload))
        _, _, _, headers = member_user
        resp = await client.post(
            "/api/v1/chat/explain",
            json={"question_id": seed_question["id"]},
            headers=headers,
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["session_id"]
        assert len(body["steps"]) == 2
        assert body["steps"][0]["title"] == "步骤1"
        assert body["conclusion"] == "导数为 0"
        assert len(body["citations"]) == 1
        assert body["citations"][0]["source"] == "高等数学教材"
        assert body["uncovered"] is False
        assert body["model"] == "flash"  # difficulty=2 → flash

    async def test_no_hit_uncovered_fallback(self, client, member_user, seed_question, monkeypatch):
        """RAG 无命中：uncovered=true，citations 为空 → 前端提示教材未覆盖。"""
        payload = {
            "steps": [{"title": "说明", "content": "该知识点教材未覆盖"}],
            "conclusion": None,
            "citations": [],
            "uncovered": True,
        }
        monkeypatch.setattr(llm_gateway, "chat", _llm_echo(payload))
        _, _, _, headers = member_user
        resp = await client.post(
            "/api/v1/chat/explain",
            json={"question_id": seed_question["id"]},
            headers=headers,
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["uncovered"] is True
        assert body["citations"] == []

    async def test_non_json_fallback(self, client, member_user, seed_question, monkeypatch):
        """LLM 返回非 JSON 文本 → 兜底单步讲解，不 500。"""
        monkeypatch.setattr(llm_gateway, "chat", _llm_echo("直接给出一段讲解文字"))
        _, _, _, headers = member_user
        resp = await client.post(
            "/api/v1/chat/explain",
            json={"question_id": seed_question["id"]},
            headers=headers,
        )
        assert resp.status_code == 200
        body = resp.json()
        assert len(body["steps"]) == 1
        assert body["steps"][0]["content"] == "直接给出一段讲解文字"
        assert body["citations"] == []
        assert body["uncovered"] is False

    async def test_difficulty5_routes_pro(self, client, db_session, member_user, monkeypatch):
        """难度 >=4 走 pro 模型（route_tier 集成）。"""
        from app.db.models import KnowledgePoint, Subject
        subj = Subject(code=_rand("math"), name="高数pro", description="", config={})
        db_session.add(subj)
        await db_session.flush()
        kp = KnowledgePoint(subject_id=subj.id, name="难题知识点", content="", level=3)
        db_session.add(kp)
        await db_session.flush()
        q = Question(
            subject_id=subj.id, knowledge_point_id=kp.id, type="proof",
            content="证明：$\\lim_{x\\to0}\\frac{\\sin x}{x}=1$",
            options=None, answer="证明略", analysis="", difficulty=5,
            source="self_built", status="active",
        )
        db_session.add(q)
        await db_session.commit()
        await db_session.refresh(q)
        records = []
        monkeypatch.setattr(llm_gateway, "chat", _llm_echo("证明过程", records))
        _, _, _, headers = member_user
        resp = await client.post(
            "/api/v1/chat/explain",
            json={"question_id": str(q.id)},
            headers=headers,
        )
        assert resp.status_code == 200
        assert resp.json()["model"] == "pro"
        assert records and records[0]["tier"] == "pro"

    async def test_explain_404_unknown_question(self, client, member_user, mock_llm):
        _, _, _, headers = member_user
        resp = await client.post(
            "/api/v1/chat/explain",
            json={"question_id": str(uuid.uuid4())},
            headers=headers,
        )
        assert resp.status_code == 404

    async def test_explain_requires_member(self, client, registered_user, seed_question):
        _, _, _, headers = registered_user
        resp = await client.post(
            "/api/v1/chat/explain",
            json={"question_id": seed_question["id"]},
            headers=headers,
        )
        assert resp.status_code == 403


# ═══════════════════════════════════════════════════════════════════════════
# /chat/followup：上下文保持
# ═══════════════════════════════════════════════════════════════════════════


class TestFollowupContext:
    async def test_followup_keeps_context(self, client, member_user, seed_question, monkeypatch):
        """追问请求携带历史消息（assistant 上一条回答可见）。"""
        records = []
        monkeypatch.setattr(
            llm_gateway, "chat",
            _llm_echo({
                "steps": [{"title": "步骤1", "content": "首答内容"}],
                "conclusion": "结论A", "citations": [], "uncovered": False,
            }, records),
        )
        _, _, _, headers = member_user
        r1 = await client.post(
            "/api/v1/chat/explain",
            json={"question_id": seed_question["id"]},
            headers=headers,
        )
        assert r1.status_code == 200
        session_id = r1.json()["session_id"]

        # 追问：第二次调用携带上下文
        r2 = await client.post(
            "/api/v1/chat/followup",
            json={"session_id": session_id, "message": "再详细讲一下求导步骤"},
            headers=headers,
        )
        assert r2.status_code == 200, r2.text
        body = r2.json()
        assert body["session_id"] == session_id
        assert body["steps"][0]["title"] == "Follow-up answer"

        # 断言假 LLM 收到的 followup 消息包含上一轮 assistant 回答 + 新追问
        followup_call = records[-1]
        msgs = followup_call["messages"]
        assert msgs[-1] == {"role": "user", "content": "再详细讲一下求导步骤"}
        assert any(m["role"] == "assistant" and "首答内容" in m["content"] for m in msgs), (
            "followup 未携带历史 assistant 消息 → 上下文丢失"
        )

    async def test_followup_404_unknown_session(self, client, member_user, mock_llm):
        _, _, _, headers = member_user
        resp = await client.post(
            "/api/v1/chat/followup",
            json={"session_id": str(uuid.uuid4()), "message": "hi"},
            headers=headers,
        )
        assert resp.status_code == 404

    async def test_followup_cross_user_404_v2(self, client, db_session, seed_question, monkeypatch):
        """他人 session 不可追问（数据隔离）—— 直接建两个会员用户。"""
        from sqlalchemy import select
        from app.db.models import User
        from tests.conftest import _register_user
        monkeypatch.setattr(llm_gateway, "chat", _llm_echo({"steps": [], "citations": []}))
        # 用户 A（会员）
        uname_a, _, token_a = await _register_user(client, _rand("user_a"))
        res = await db_session.execute(select(User).where(User.username == uname_a))
        ua = res.scalar_one()
        ua.is_member = True
        # 用户 B（会员）
        uname_b, _, token_b = await _register_user(client, _rand("user_b"))
        res = await db_session.execute(select(User).where(User.username == uname_b))
        ub = res.scalar_one()
        ub.is_member = True
        await db_session.commit()

        headers_a = {"Authorization": f"Bearer {token_a}"}
        headers_b = {"Authorization": f"Bearer {token_b}"}
        r1 = await client.post(
            "/api/v1/chat/explain",
            json={"question_id": seed_question["id"]},
            headers=headers_a,
        )
        assert r1.status_code == 200
        session_id = r1.json()["session_id"]
        r2 = await client.post(
            "/api/v1/chat/followup",
            json={"session_id": session_id, "message": "偷看"},
            headers=headers_b,
        )
        assert r2.status_code == 404


# ═══════════════════════════════════════════════════════════════════════════
# SSE 流式
# ═══════════════════════════════════════════════════════════════════════════


class TestChatSse:
    async def test_explain_stream(self, client, member_user, seed_question, monkeypatch):
        async def _fake_stream(tier, messages, max_tokens=None, temperature=0.3):
            yield "片段1"
            yield "片段2"

        monkeypatch.setattr(llm_gateway, "chat_stream", _fake_stream)
        _, _, _, headers = member_user
        resp = await client.post(
            "/api/v1/chat/explain?stream=true",
            json={"question_id": seed_question["id"]},
            headers=headers,
        )
        assert resp.status_code == 200
        assert "text/event-stream" in resp.headers.get("content-type", "")
        body = resp.text
        assert '"type": "delta"' in body
        assert '"type": "done"' in body
        assert "Understanding the question" in body  # 首步事件（ASCII 明文）

    async def test_followup_stream(self, client, member_user, seed_question, monkeypatch):
        async def _fake_stream(tier, messages, max_tokens=None, temperature=0.3):
            yield "追答片段"

        # explain 走非流式 chat；followup 走流式 chat_stream，两者都要 mock
        monkeypatch.setattr(
            llm_gateway, "chat",
            _llm_echo({"steps": [{"title": "步骤1", "content": "首答"}], "citations": []}),
        )
        monkeypatch.setattr(llm_gateway, "chat_stream", _fake_stream)
        _, _, _, headers = member_user
        r1 = await client.post(
            "/api/v1/chat/explain",
            json={"question_id": seed_question["id"]},
            headers=headers,
        )
        session_id = r1.json()["session_id"]
        resp = await client.post(
            "/api/v1/chat/followup?stream=true",
            json={"session_id": session_id, "message": "追问"},
            headers=headers,
        )
        assert resp.status_code == 200
        assert "text/event-stream" in resp.headers.get("content-type", "")
        assert '"type": "delta"' in resp.text
        assert '"type": "done"' in resp.text
