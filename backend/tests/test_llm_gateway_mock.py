"""单元层测试 — LLM 网关 mock 上游：超时 / HTTP 错误 / 内容安全拦截 / pro→flash 降级。

用 httpx.MockTransport 模拟 DeepSeek 上游，测试不发起真实网络请求。
验收点：
- 上游 200 → 正常解析 content / model / usage
- 上游 5xx → flash 抛 LLMError；pro 自动降级到 flash 重试
- 上游超时/网络错误 → flash 抛 LLMError；pro 降级
- 内容安全：上游返回敏感内容时网关原样透传（M1 未做拦截 → 见 test-report 缺陷记录）
"""
import json

import httpx
import pytest

from app.services.llm_gateway import LLMGateway, LLMError


def _json_response(payload: dict, status: int = 200) -> httpx.Response:
    return httpx.Response(status, json=payload)


def _ok_payload(content: str = "你好", model: str = "deepseek-chat") -> dict:
    return {
        "id": "chatcmpl-1",
        "object": "chat.completion",
        "model": model,
        "choices": [{"index": 0, "message": {"role": "assistant", "content": content}, "finish_reason": "stop"}],
        "usage": {"prompt_tokens": 12, "completion_tokens": 8, "total_tokens": 20},
    }


@pytest.fixture
def fresh_gateway() -> LLMGateway:
    """每次测试独立 gateway，避免污染单例。"""
    g = LLMGateway()
    return g


@pytest.fixture
def mock_client(fresh_gateway, monkeypatch):
    """把 gateway._client 换成 MockTransport 包装的 AsyncClient。"""

    def _install(handler):
        transport = httpx.MockTransport(handler)
        client = httpx.AsyncClient(
            base_url="https://api.deepseek.com", transport=transport
        )
        monkeypatch.setattr(fresh_gateway, "_client", client)
        return client

    return _install


class TestGatewaySuccess:
    async def test_chat_parses_response(self, fresh_gateway, mock_client):
        def handler(request):
            return _json_response(_ok_payload(content="极限的定义"))

        mock_client(handler)
        result = await fresh_gateway.chat("flash", [{"role": "user", "content": "什么是极限？"}])
        assert result["content"] == "极限的定义"
        assert result["model"] == "deepseek-chat"
        assert result["usage"]["prompt_tokens"] == 12

    async def test_stream_yields_deltas(self, fresh_gateway, mock_client):
        def handler(request):
            stream = (
                "data: " + json.dumps({"choices": [{"delta": {"content": "分"}}]}) + "\n\n"
                "data: " + json.dumps({"choices": [{"delta": {"content": "步"}}]}) + "\n\n"
                "data: [DONE]\n\n"
            )
            return httpx.Response(200, text=stream)

        mock_client(handler)
        chunks = []
        async for c in fresh_gateway.chat_stream("flash", [{"role": "user", "content": "hi"}]):
            chunks.append(c)
        assert chunks == ["分", "步"]


class TestGatewayHTTPError:
    async def test_flash_http_error_raises(self, fresh_gateway, mock_client):
        def handler(request):
            return httpx.Response(500, text="upstream boom")

        mock_client(handler)
        with pytest.raises(LLMError):
            await fresh_gateway.chat("flash", [{"role": "user", "content": "hi"}])

    async def test_pro_falls_back_to_flash(self, fresh_gateway, mock_client):
        """pro 上游 500 → 自动降级 flash，返回 flash 内容。"""
        calls: list[dict] = []

        def handler(request):
            payload = json.loads(request.content)
            calls.append(payload["model"])
            if payload["model"] == "deepseek-reasoner":
                return httpx.Response(500, text="pro down")
            return _json_response(_ok_payload(content="flash 兜底", model="deepseek-chat"))

        mock_client(handler)
        result = await fresh_gateway.chat("pro", [{"role": "user", "content": "hi"}])
        assert result["content"] == "flash 兜底"
        assert result["model"] == "deepseek-chat"
        assert calls == ["deepseek-reasoner", "deepseek-chat"]

    async def test_pro_stream_falls_back(self, fresh_gateway, mock_client):
        calls: list[dict] = []

        def handler(request):
            payload = json.loads(request.content)
            calls.append(payload["model"])
            if payload["model"] == "deepseek-reasoner":
                return httpx.Response(500, text="pro down")
            stream = "data: " + json.dumps({"choices": [{"delta": {"content": "兜底"}}]}) + "\n\n" "data: [DONE]\n\n"
            return httpx.Response(200, text=stream)

        mock_client(handler)
        chunks = []
        async for c in fresh_gateway.chat_stream("pro", [{"role": "user", "content": "hi"}]):
            chunks.append(c)
        assert chunks == ["兜底"]
        assert calls == ["deepseek-reasoner", "deepseek-chat"]


class TestGatewayTimeout:
    async def test_flash_timeout_raises(self, fresh_gateway, mock_client):
        def handler(request):
            raise httpx.ConnectTimeout("connect timeout")

        mock_client(handler)
        with pytest.raises(LLMError):
            await fresh_gateway.chat("flash", [{"role": "user", "content": "hi"}])

    async def test_pro_timeout_falls_back(self, fresh_gateway, mock_client):
        calls: list[dict] = []

        def handler(request):
            payload = json.loads(request.content)
            calls.append(payload["model"])
            if payload["model"] == "deepseek-reasoner":
                raise httpx.ConnectTimeout("timeout")
            return _json_response(_ok_payload(content="ok"))

        mock_client(handler)
        result = await fresh_gateway.chat("pro", [{"role": "user", "content": "hi"}])
        assert result["content"] == "ok"
        assert calls == ["deepseek-reasoner", "deepseek-chat"]

    async def test_flash_stream_timeout_raises(self, fresh_gateway, mock_client):
        def handler(request):
            raise httpx.ReadTimeout("read timeout")

        mock_client(handler)
        with pytest.raises(LLMError):
            async for _ in fresh_gateway.chat_stream("flash", [{"role": "user", "content": "hi"}]):
                pass


class TestContentSafety:
    """内容安全拦截 — M1 现状记录。

    按 PRD/硬性约束，AI 讲解不应输出违规内容。M1 LLM Gateway 直接透传上游内容，
    未做敏感内容拦截（缺陷记录见 docs/qa/test-report.md）。此测试固化当前行为，
    供 M2 拦截层上线后翻转断言。
    """

    async def test_harmful_content_passthrough_current_behavior(self, fresh_gateway, mock_client):
        def handler(request):
            return _json_response(_ok_payload(content="这条内容违反社区规范"))

        mock_client(handler)
        result = await fresh_gateway.chat("flash", [{"role": "user", "content": "x"}])
        # 现状：原样透传（缺陷：无拦截）——标记为已知缺口
        assert result["content"] == "这条内容违反社区规范"

    async def test_gateway_has_no_content_filter_module(self):
        """网关模块内不存在 content_filter / moderation 调用（固话 M1 缺口）。"""
        import inspect

        import app.services.llm_gateway as mod

        src = inspect.getsource(mod)
        assert "moderat" not in src.lower()
        assert "content_filter" not in src
