"""LLM Gateway — unified DeepSeek flash/pro via httpx with routing, retry, streaming, metering.

This is the ONLY place in the backend that talks to DeepSeek.
Key reads from environment only.  Supports flash/pro tier switching,
SSE streaming, timeout/error wrapping, and pro→flash fallback.
"""
import json
import logging
from typing import AsyncGenerator, Literal

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

ModelTier = Literal["flash", "pro"]


class LLMError(Exception):
    """Wrapped LLM call error."""


class LLMGateway:
    """Singleton gateway for all LLM calls."""

    _instance: "LLMGateway | None" = None

    def __init__(self) -> None:
        self._client: httpx.AsyncClient | None = None

    @classmethod
    def get_instance(cls) -> "LLMGateway":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @property
    def client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=settings.DEEPSEEK_BASE_URL,
                headers={
                    "Authorization": f"Bearer {settings.DEEPSEEK_API_KEY}",
                    "Content-Type": "application/json",
                },
                timeout=httpx.Timeout(settings.LLM_REQUEST_TIMEOUT),
            )
        return self._client

    # ── routing ────────────────────────────────────────────────────────

    def _model_name(self, tier: ModelTier) -> str:
        return settings.LLM_PRO_MODEL if tier == "pro" else settings.LLM_FLASH_MODEL

    def _max_tokens(self, tier: ModelTier) -> int:
        return settings.LLM_PRO_MAX_TOKENS if tier == "pro" else settings.LLM_FLASH_MAX_TOKENS

    def route_tier(
        self,
        require_depth: bool = False,
        difficulty: int = 0,
        question_type: str = "",
    ) -> ModelTier:
        """Route pro when quality matters, flash otherwise."""
        if require_depth:
            return "pro"
        if difficulty >= 4:
            return "pro"
        if question_type in ("essay", "proof", "writing", "reading"):
            return "pro"
        return "flash"

    # ── non-streaming ──────────────────────────────────────────────────

    async def chat(
        self,
        tier: ModelTier,
        messages: list[dict[str, str]],
        max_tokens: int | None = None,
        temperature: float = 0.3,
    ) -> dict:
        """Non-streaming chat → {content, model, usage}."""
        model = self._model_name(tier)
        tokens = max_tokens or self._max_tokens(tier)
        url = "/v1/chat/completions"
        payload: dict = {
            "model": model,
            "messages": messages,
            "max_tokens": tokens,
            "temperature": temperature,
            "stream": False,
        }

        try:
            resp = await self.client.post(url, json=payload)
            resp.raise_for_status()
            data = resp.json()
        except httpx.HTTPStatusError as exc:
            logger.warning("LLM call HTTP %s for tier=%s", exc.response.status_code, tier)
            if tier == "pro":
                logger.info("Falling back from pro → flash")
                return await self.chat("flash", messages, max_tokens, temperature)
            raise LLMError(f"DeepSeek HTTP {exc.response.status_code}: {exc.response.text[:200]}") from exc
        except httpx.RequestError as exc:
            logger.warning("LLM call network error for tier=%s: %s", tier, exc)
            if tier == "pro":
                logger.info("Falling back from pro → flash")
                return await self.chat("flash", messages, max_tokens, temperature)
            raise LLMError(f"DeepSeek unreachable: {exc}") from exc

        choice = data["choices"][0]
        usage = data.get("usage", {})
        return {
            "content": choice["message"]["content"],
            "model": data.get("model", model),
            "usage": {
                "prompt_tokens": usage.get("prompt_tokens", 0),
                "completion_tokens": usage.get("completion_tokens", 0),
            },
        }

    # ── streaming (SSE) ────────────────────────────────────────────────

    async def chat_stream(
        self,
        tier: ModelTier,
        messages: list[dict[str, str]],
        max_tokens: int | None = None,
        temperature: float = 0.3,
    ) -> AsyncGenerator[str, None]:
        """Streaming chat — yields content delta strings via SSE."""
        model = self._model_name(tier)
        tokens = max_tokens or self._max_tokens(tier)
        url = "/v1/chat/completions"
        payload: dict = {
            "model": model,
            "messages": messages,
            "max_tokens": tokens,
            "temperature": temperature,
            "stream": True,
        }

        try:
            async with self.client.stream("POST", url, json=payload) as resp:
                resp.raise_for_status()
                async for line in resp.aiter_lines():
                    if not line or not line.startswith("data: "):
                        continue
                    data_str = line[6:]
                    if data_str == "[DONE]":
                        break
                    try:
                        chunk = json.loads(data_str)
                        delta = chunk["choices"][0].get("delta", {})
                        content = delta.get("content", "")
                        if content:
                            yield content
                    except (json.JSONDecodeError, KeyError, IndexError):
                        continue
        except httpx.HTTPStatusError as exc:
            logger.warning("LLM stream HTTP %s for tier=%s", exc.response.status_code, tier)
            if tier == "pro":
                logger.info("Falling back from pro → flash stream")
                async for chunk in self.chat_stream("flash", messages, max_tokens, temperature):
                    yield chunk
                return
            raise LLMError(f"DeepSeek stream HTTP {exc.response.status_code}") from exc
        except httpx.RequestError as exc:
            logger.warning("LLM stream network error for tier=%s: %s", tier, exc)
            if tier == "pro":
                logger.info("Falling back from pro → flash stream")
                async for chunk in self.chat_stream("flash", messages, max_tokens, temperature):
                    yield chunk
                return
            raise LLMError(f"DeepSeek stream unreachable: {exc}") from exc


# Singleton accessor
llm_gateway = LLMGateway.get_instance()
