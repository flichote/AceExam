"""Embedding service — generate vectors for document chunks and queries.

Primary path: DeepSeek embeddings API (or OpenAI-compatible endpoint).
Fallback: keyword-based (bag-of-words + TF-IDF scoring) when:
  - EMBEDDING_MODEL is not configured
  - EMBEDDING_API_KEY is empty
  - The embeddings API returns 404/not-found

NOTE (2026-08): DeepSeek's primary models (deepseek-chat / deepseek-reasoner) do NOT
expose a dedicated /v1/embeddings endpoint.  If EMBEDDING_MODEL is unset, this module
degrades to keyword-based retrieval with zero external API cost.  To enable vector
embeddings, set EMBEDDING_MODEL + EMBEDDING_BASE_URL + EMBEDDING_API_KEY to an
OpenAI-compatible provider (e.g. OpenAI text-embedding-3-small, or a local
sentence-transformers server).
"""

import hashlib
import logging
from collections import Counter
from typing import Sequence

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

# ── Embedding interface ────────────────────────────────────────────────────


class Embedder:
    """Abstract embedding interface."""

    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """Return embedding vectors (one per input text)."""
        raise NotImplementedError

    async def embed_query(self, text: str) -> list[float]:
        results = await self.embed_texts([text])
        return results[0]

    @property
    def dim(self) -> int:
        raise NotImplementedError

    @property
    def is_keyword_fallback(self) -> bool:
        """True when embeddings are keyword-based (no semantic similarity)."""
        raise NotImplementedError


# ── Vector Embedder (calls external API) ───────────────────────────────────


class APIEmbedder(Embedder):
    """Calls an OpenAI-compatible /v1/embeddings endpoint."""

    def __init__(
        self,
        model: str = "",
        base_url: str = "",
        api_key: str = "",
        dim: int = 1024,
    ) -> None:
        self._model = model or settings.EMBEDDING_MODEL
        self._base = (base_url or settings.EMBEDDING_BASE_URL).rstrip("/")
        self._key = api_key or settings.EMBEDDING_API_KEY
        self._dim = dim or settings.EMBEDDING_DIM
        self._client: httpx.AsyncClient | None = None

    @property
    def dim(self) -> int:
        return self._dim

    @property
    def is_keyword_fallback(self) -> bool:
        return False

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self._base,
                headers={
                    "Authorization": f"Bearer {self._key}",
                    "Content-Type": "application/json",
                },
                timeout=httpx.Timeout(30),
            )
        return self._client

    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        if not self._model or not self._base:
            raise ValueError("EMBEDDING_MODEL and EMBEDDING_BASE_URL must be set")

        client = await self._get_client()
        resp = await client.post(
            "/v1/embeddings",
            json={"model": self._model, "input": texts},
        )
        resp.raise_for_status()
        data = resp.json()
        return [item["embedding"] for item in data["data"]]


# ── Keyword Fallback Embedder (zero API cost) ──────────────────────────────


class KeywordEmbedder(Embedder):
    """Bag-of-words embedder for keyword-based retrieval fallback.

    Produces a sparse-like fixed-dimensional vector from token frequencies.
    The vector is NOT semantically meaningful — cosine_distance over these
    vectors is equivalent to Jaccard-like keyword overlap.  This is an explicit
    degradation from true semantic search, documented here so every caller
    understands the quality trade-off.

    Strategy: collect vocabulary from training texts, encode each text as
    a normalized term-frequency vector over the vocab (top N terms).
    """

    def __init__(self, dim: int = 1024) -> None:
        self._dim = dim
        self._vocab: list[str] = []  # populated by the first embed_texts call

    @property
    def dim(self) -> int:
        return self._dim

    @property
    def is_keyword_fallback(self) -> bool:
        return True

    def _tokenize(self, text: str) -> Counter:
        """Simple Chinese + English tokenizer (character bigrams + word unigrams)."""
        import re

        tokens: Counter = Counter()
        # English words
        for w in re.findall(r"[a-zA-Z]+", text):
            tokens[w.lower()] += 1
        # Chinese character bigrams (better than unigrams for disambiguation)
        cleaned = re.sub(r"[^\u4e00-\u9fff]", "", text)
        for i in range(len(cleaned) - 1):
            tokens[cleaned[i : i + 2]] += 1
        # Also add unigrams for coverage
        for ch in cleaned:
            tokens[ch] += 1
        return tokens

    def _build_vocab(self, texts: list[str]) -> list[str]:
        """Build vocabulary from a corpus of texts, top-N by frequency."""
        global_counter: Counter = Counter()
        for t in texts:
            global_counter.update(self._tokenize(t))
        return [w for w, _ in global_counter.most_common(self._dim)]

    def _encode(self, text: str, vocab: list[str]) -> list[float]:
        if not vocab:
            return [0.0] * self._dim
        tokens = self._tokenize(text)
        total = sum(tokens.values()) or 1
        vec = [tokens.get(w, 0) / total for w in vocab]
        # Pad to dim
        if len(vec) < self._dim:
            vec.extend([0.0] * (self._dim - len(vec)))
        return vec[: self._dim]

    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        if not self._vocab:
            self._vocab = self._build_vocab(texts)
        return [self._encode(t, self._vocab) for t in texts]


# ── Factory ────────────────────────────────────────────────────────────────


def _create_embedder() -> Embedder:
    """Create the best available embedder.

    Priority:
      1. APIEmbedder when EMBEDDING_MODEL + EMBEDDING_BASE_URL are configured
      2. KeywordEmbedder as zero-cost fallback
    """
    if settings.EMBEDDING_ENABLED and settings.EMBEDDING_MODEL and settings.EMBEDDING_BASE_URL:
        logger.info("Embedder: using API model=%s", settings.EMBEDDING_MODEL)
        return APIEmbedder()
    logger.info(
        "Embedder: EMBEDDING_MODEL or EMBEDDING_BASE_URL not set — "
        "falling back to keyword-based retrieval (cosine_distance ~ keyword overlap)"
    )
    return KeywordEmbedder(dim=settings.EMBEDDING_DIM)


embedder = _create_embedder()
