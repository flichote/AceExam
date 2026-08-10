"""M3.5 TTS API 验收测试 — POST /chat/explain/{session_id}/tts + GET /tts/audio/{hash}.mp3。

验收点（docs/api.md §12.1/§12.2）：
- 会员鉴权：免费用户 403；未登录 401
- 会话归属：不存在/非本人 session → 404
- 无 assistant 讲解内容 → 404 EXPLANATION_NOT_FOUND（含 LaTeX 被剥光后为空）
- voice 白名单校验：非法 → 422
- mock edge-tts 生成音频：200 + session_id/audio_url/voice/text_preview/cache_hit
- 磁盘缓存幂等：第二次调用 cache_hit=true，不重复合成
- 上游失败（edge-tts 异常）→ 502 TTS_UNAVAILABLE
- 音频流：GET /tts/audio/{hash}.mp3 → 200 audio/mpeg；文件不存在 → 404

Run: cd backend && PYTHONPATH="" .venv/Scripts/python.exe -m pytest tests/test_m35_tts_api.py -v --tb=short -p no:warnings
"""
import uuid
from pathlib import Path

import pytest
from httpx import AsyncClient
from sqlalchemy import select

import edge_tts  # 仅用于 mock Communicate.stream（不发起真实网络请求）
from app.db.models import ChatSession, User
from tests.conftest import _rand

pytestmark = pytest.mark.anyio


async def _register(client, username: str | None = None, password: str = "pass123456") -> tuple[str, str]:
    username = username or _rand("user")
    resp = await client.post(
        "/api/v1/auth/register",
        json={"username": username, "password": password},
    )
    assert resp.status_code == 201, resp.text
    return username, resp.json()["access_token"]


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


async def _user_id(db, username: str) -> uuid.UUID:
    res = await db.execute(select(User).where(User.username == username))
    return res.scalar_one().id


async def _seed_session(db, user_id: uuid.UUID, messages: list[dict] | None = None) -> ChatSession:
    """直接入库一个 ChatSession（默认带一条 assistant 讲解消息）。"""
    session = ChatSession(
        user_id=user_id,
        session_key=_rand("sess"),
        messages=messages or [
            {
                "role": "user",
                "content": "请讲解这道极限题",
            },
            {
                "role": "assistant",
                "content": "第一步，我们先理解题意：题干给出极限式 $\\lim_{x \\to 0} \\frac{\\sin x}{x}$，"
                "我们需要求其值。第二步，应用重要极限公式可得结果为 1。",
            },
        ],
    )
    db.add(session)
    await db.commit()
    await db.refresh(session)
    return session


@pytest.fixture
async def member_user_id(client, db_session, member_user):
    """提升为会员的用户 id（member_user 复用 conftest fixture）。"""
    return await _user_id(db_session, member_user[0])


@pytest.fixture
def tts_cache_dir(tmp_path, monkeypatch):
    """把 chat 模块的 TTS 磁盘缓存目录指向临时目录，避免污染仓库 backend/media/tts。"""
    import app.api.v1.chat as chat_mod

    cache_dir = tmp_path / "tts"
    monkeypatch.setattr(chat_mod, "_TTS_CACHE_DIR", cache_dir)
    return cache_dir


def _fake_edge_stream(self):
    """替代 edge_tts.Communicate.stream 的假异步生成器（返回音频字节）。"""
    async def _gen():
        yield {"type": "audio", "data": b"\xff\xfb\x90\x00" * 200}
        yield {"type": "WordBoundary", "offset": 0, "duration": 10}

    return _gen()


# ═══════════════════════════════════════════════════════════════════════
# 1. 鉴权边界
# ═══════════════════════════════════════════════════════════════════════

class TestTTSSAuth:
    async def test_tts_requires_login(self, client: AsyncClient):
        """未登录 → 401。"""
        resp = await client.post(
            f"/api/v1/chat/explain/{uuid.uuid4()}/tts",
            json={"voice": "zh-CN-XiaoxiaoNeural"},
        )
        assert resp.status_code == 401, resp.text

    async def test_tts_free_user_forbidden(
        self, client: AsyncClient, db_session, registered_user
    ):
        """免费用户（非会员）→ 403（TTS 为会员功能，§12.1 免费 403）。"""
        _, _, _, headers = registered_user
        resp = await client.post(
            f"/api/v1/chat/explain/{uuid.uuid4()}/tts",
            json={"voice": "zh-CN-XiaoxiaoNeural"},
            headers=headers,
        )
        assert resp.status_code == 403, resp.text


# ═══════════════════════════════════════════════════════════════════════
# 2. 参数校验与会话归属
# ═══════════════════════════════════════════════════════════════════════

class TestTTSValidation:
    async def test_tts_invalid_voice_422(
        self, client: AsyncClient, db_session, member_user_id, member_user
    ):
        """voice 不在白名单 → 422。"""
        _, _, _, headers = member_user
        resp = await client.post(
            f"/api/v1/chat/explain/{uuid.uuid4()}/tts",
            json={"voice": "en-US-AriaNeural"},
            headers=headers,
        )
        assert resp.status_code == 422, resp.text

    async def test_tts_session_not_found(
        self, client: AsyncClient, db_session, member_user_id, member_user
    ):
        """不存在的 session → 404。"""
        _, _, _, headers = member_user
        resp = await client.post(
            f"/api/v1/chat/explain/{uuid.uuid4()}/tts",
            json={"voice": "zh-CN-XiaoxiaoNeural"},
            headers=headers,
        )
        assert resp.status_code == 404, resp.text

    async def test_tts_other_users_session_404(
        self, client: AsyncClient, db_session, member_user_id, member_user
    ):
        """非本人的 session → 404（归属校验）。"""
        # 另一个用户建 session
        other_uid = uuid.uuid4()
        from app.core.security import hash_password

        db_session.add(User(
            id=other_uid,
            username=_rand("other"),
            password_hash=hash_password("pass123456"),
            role="student",
            is_member=True,
        ))
        await db_session.flush()
        session = await _seed_session(db_session, other_uid)

        _, _, _, headers = member_user
        resp = await client.post(
            f"/api/v1/chat/explain/{session.id}/tts",
            json={"voice": "zh-CN-XiaoxiaoNeural"},
            headers=headers,
        )
        assert resp.status_code == 404, resp.text

    async def test_tts_no_assistant_message_404(
        self, client: AsyncClient, db_session, member_user_id, member_user
    ):
        """session 存在但无 assistant 讲解 → 404。"""
        session = await _seed_session(
            db_session,
            member_user_id,
            messages=[{"role": "user", "content": "请讲解"}],
        )
        _, _, _, headers = member_user
        resp = await client.post(
            f"/api/v1/chat/explain/{session.id}/tts",
            json={"voice": "zh-CN-XiaoxiaoNeural"},
            headers=headers,
        )
        assert resp.status_code == 404, resp.text

    async def test_tts_empty_assistant_content_404(
        self, client: AsyncClient, db_session, member_user_id, member_user
    ):
        """assistant 消息内容为空白 → 404。"""
        session = await _seed_session(
            db_session,
            member_user_id,
            messages=[
                {"role": "assistant", "content": "   \n  "},
            ],
        )
        _, _, _, headers = member_user
        resp = await client.post(
            f"/api/v1/chat/explain/{session.id}/tts",
            json={"voice": "zh-CN-XiaoxiaoNeural"},
            headers=headers,
        )
        assert resp.status_code == 404, resp.text

    @pytest.mark.xfail(reason="D-23 display math 未被 _clean_text_for_tts 清洗", strict=False)
    async def test_tts_display_math_not_stripped(
        self, client: AsyncClient, db_session, member_user_id, member_user, tts_cache_dir, monkeypatch
    ):
        """D-23 固化：$$...$$ 展示公式不被 _clean_text_for_tts 剥光，LaTeX 命令会进 TTS。

        契约（tts_service.preprocess_text 语义）要求 display math 同样被清洗；
        当前 chat.py _clean_text_for_tts 仅处理 inline $...$，$$...$$ 残留。
        修复后应返回 404（清洗后为空），此用例自动转 XPASS。
        """
        session = await _seed_session(
            db_session,
            member_user_id,
            messages=[
                {"role": "assistant", "content": "$$\\lim_{x \\to 0} \\frac{\\sin x}{x} = 1$$"},
            ],
        )
        _, _, _, headers = member_user

        monkeypatch.setattr(edge_tts.Communicate, "stream", _fake_edge_stream)
        resp = await client.post(
            f"/api/v1/chat/explain/{session.id}/tts",
            json={"voice": "zh-CN-XiaoxiaoNeural"},
            headers=headers,
        )
        assert resp.status_code == 404, resp.text


# ═══════════════════════════════════════════════════════════════════════
# 3. 正常合成（mock edge-tts）
# ═══════════════════════════════════════════════════════════════════════

class TestTTSSynthesize:
    async def test_tts_generates_audio(
        self, client: AsyncClient, db_session, member_user_id, member_user, tts_cache_dir, monkeypatch
    ):
        """mock edge-tts → 200 + audio_url/cache_hit=false。"""
        session = await _seed_session(db_session, member_user_id)
        _, _, _, headers = member_user

        monkeypatch.setattr(edge_tts.Communicate, "stream", _fake_edge_stream)
        resp = await client.post(
            f"/api/v1/chat/explain/{session.id}/tts",
            json={"voice": "zh-CN-XiaoxiaoNeural"},
            headers=headers,
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["session_id"] == str(session.id)
        assert data["voice"] == "zh-CN-XiaoxiaoNeural"
        assert data["cache_hit"] is False
        assert data["audio_url"].startswith("/api/v1/chat/tts/audio/")  # D-24 修复：含 /chat 段
        assert data["audio_url"].endswith(".mp3")
        assert "极限" in data["text_preview"]  # LaTeX 已清洗、中文保留
        # 磁盘缓存已生成
        files = list(tts_cache_dir.glob("*.mp3"))
        assert len(files) == 1
        assert files[0].read_bytes() == b"\xff\xfb\x90\x00" * 200

    async def test_tts_cache_hit_second_call(
        self, client: AsyncClient, db_session, member_user_id, member_user, tts_cache_dir, monkeypatch
    ):
        """同 session 同 voice 二次调用 → cache_hit=true，不再合成。"""
        session = await _seed_session(db_session, member_user_id)
        _, _, _, headers = member_user

        monkeypatch.setattr(edge_tts.Communicate, "stream", _fake_edge_stream)
        r1 = await client.post(
            f"/api/v1/chat/explain/{session.id}/tts",
            json={"voice": "zh-CN-YunxiNeural"},
            headers=headers,
        )
        assert r1.status_code == 200
        assert r1.json()["cache_hit"] is False

        # 第二次调用：缓存命中，即使 mock 被移除也应成功（不触发 edge-tts）
        monkeypatch.delattr(edge_tts.Communicate, "stream")
        r2 = await client.post(
            f"/api/v1/chat/explain/{session.id}/tts",
            json={"voice": "zh-CN-YunxiNeural"},
            headers=headers,
        )
        assert r2.status_code == 200, r2.text
        assert r2.json()["cache_hit"] is True
        assert r2.json()["audio_url"] == r1.json()["audio_url"]

    async def test_tts_default_voice_when_body_omitted(
        self, client: AsyncClient, db_session, member_user_id, member_user, tts_cache_dir, monkeypatch
    ):
        """不传 body（或缺省 voice）→ 默认 Xiaoxiao 音色。"""
        session = await _seed_session(db_session, member_user_id)
        _, _, _, headers = member_user

        monkeypatch.setattr(edge_tts.Communicate, "stream", _fake_edge_stream)
        resp = await client.post(
            f"/api/v1/chat/explain/{session.id}/tts",
            headers=headers,
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["voice"] == "zh-CN-XiaoxiaoNeural"

    async def test_tts_upstream_failure_502(
        self, client: AsyncClient, db_session, member_user_id, member_user, tts_cache_dir, monkeypatch
    ):
        """edge-tts 异常 → 502 TTS_UNAVAILABLE。"""
        session = await _seed_session(db_session, member_user_id)
        _, _, _, headers = member_user

        async def _broken_stream(self):
            raise RuntimeError("edge-tts WebSocket closed")

        monkeypatch.setattr(edge_tts.Communicate, "stream", _broken_stream)
        resp = await client.post(
            f"/api/v1/chat/explain/{session.id}/tts",
            json={"voice": "zh-CN-XiaoxiaoNeural"},
            headers=headers,
        )
        assert resp.status_code == 502, resp.text


# ═══════════════════════════════════════════════════════════════════════
# 4. 音频流下载
# ═══════════════════════════════════════════════════════════════════════

class TestTTSAudioDownload:
    async def test_audio_download_real_route_returns_mp3(
        self, client: AsyncClient, db_session, member_user_id, member_user, tts_cache_dir, monkeypatch
    ):
        """真实路由 GET /api/v1/chat/tts/audio/{hash}.mp3 → 200 audio/mpeg + 字节一致。"""
        session = await _seed_session(db_session, member_user_id)
        _, _, _, headers = member_user

        monkeypatch.setattr(edge_tts.Communicate, "stream", _fake_edge_stream)
        gen = await client.post(
            f"/api/v1/chat/explain/{session.id}/tts",
            json={"voice": "zh-CN-XiaoxiaoNeural"},
            headers=headers,
        )
        assert gen.status_code == 200
        file_hash = gen.json()["audio_url"].rsplit("/", 1)[-1].removesuffix(".mp3")

        # 真实路由（chat router prefix=/chat → /api/v1/chat/tts/audio/...）
        dl = await client.get(f"/api/v1/chat/tts/audio/{file_hash}.mp3", headers=headers)
        assert dl.status_code == 200, dl.text
        assert dl.headers["content-type"] == "audio/mpeg"
        assert dl.content == b"\xff\xfb\x90\x00" * 200

    async def test_audio_url_from_tts_matches_route(
        self, client: AsyncClient, db_session, member_user_id, member_user, tts_cache_dir, monkeypatch
    ):
        """D-24 修复验证：§12.1 响应的 audio_url 应可直接 GET（200）。

        修复：chat.py audio_url 补 /chat 段（/api/v1/chat/tts/audio/...）。
        """
        session = await _seed_session(db_session, member_user_id)
        _, _, _, headers = member_user

        monkeypatch.setattr(edge_tts.Communicate, "stream", _fake_edge_stream)
        gen = await client.post(
            f"/api/v1/chat/explain/{session.id}/tts",
            json={"voice": "zh-CN-XiaoxiaoNeural"},
            headers=headers,
        )
        assert gen.status_code == 200
        audio_url = gen.json()["audio_url"]

        dl = await client.get(audio_url, headers=headers)
        assert dl.status_code == 200, dl.text

    async def test_audio_missing_404(
        self, client: AsyncClient, db_session, member_user_id, member_user, tts_cache_dir
    ):
        """缓存文件不存在 → 404。"""
        _, _, _, headers = member_user
        resp = await client.get(
            "/api/v1/chat/tts/audio/0000000000000000000000000000000000000000000000000000000000000000.mp3",
            headers=headers,
        )
        assert resp.status_code == 404, resp.text

    async def test_audio_download_free_user_forbidden(
        self, client: AsyncClient, db_session, registered_user
    ):
        """免费用户下载音频 → 403（实现按会员鉴权；契约 §12.2 写登录即可，见 D-25）。"""
        _, _, _, headers = registered_user
        resp = await client.get(
            "/api/v1/chat/tts/audio/0000000000000000000000000000000000000000000000000000000000000000.mp3",
            headers=headers,
        )
        assert resp.status_code == 403, resp.text
