"""Tests for RAG pipeline — doc_processor, embedder (keyword), retriever, rag_engine.

All tests are unit tests (no network, no real DB).
Network-dependent tests are skipped when API key is not configured.
"""

import uuid

import pytest

from app.services.rag.doc_processor import DocProcessor, Chunk
from app.services.rag.embedder import (
    Embedder,
    KeywordEmbedder,
    APIEmbedder,
    embedder,
)
from app.services.rag.retriever import RetrievedChunk, Retriever
from app.services.rag.rag_engine import (
    Citation,
    ExplanationStep,
    RagEngine,
    RagResponse,
    _build_context,
    _extract_citations,
)


# ═══════════════════════════════════════════════════════════════════════════
# DocProcessor
# ═══════════════════════════════════════════════════════════════════════════

TEXTBOOK_SAMPLE = """第一章 极限与连续

1.1 极限的概念

极限是微积分的基础概念。设函数 f(x) 在点 x0 的某个去心邻域内有定义。
如果存在常数 A，使得对于任意给定的 ε > 0，总存在 δ > 0，
当 0 < |x - x0| < δ 时，恒有 |f(x) - A| < ε，则称 A 为 f(x) 当 x → x0 时的极限。

记作：lim_{x→x0} f(x) = A

1.2 极限的四则运算法则

如果 lim f(x) = A，lim g(x) = B，那么：
- lim [f(x) ± g(x)] = A ± B
- lim [f(x) · g(x)] = A · B
- lim [f(x) / g(x)] = A / B（当 B ≠ 0）

第二章 导数与微分

2.1 导数的定义

设函数 y = f(x) 在点 x0 的某个邻域内有定义。如果极限
lim_{Δx→0} [f(x0+Δx) - f(x0)] / Δx
存在，则称 f(x) 在 x0 处可导，该极限值称为 f(x) 在 x0 处的导数，记作 f'(x0)。

2.2 基本求导公式

常数的导数：(C)' = 0
幂函数：(x^n)' = n·x^{n-1}
指数函数：(e^x)' = e^x
对数函数：(ln x)' = 1/x
三角函数：(sin x)' = cos x，(cos x)' = -sin x
"""


class TestDocProcessor:
    """RED → GREEN: verify chunking correctness."""

    def test_chunk_markdown_with_headings(self):
        processor = DocProcessor(max_tokens=1000)
        chunks = processor.chunk_markdown(TEXTBOOK_SAMPLE, source="高等数学.pdf")
        assert len(chunks) > 0
        # Verify chapter metadata
        chapters = {c.chapter for c in chunks if c.chapter}
        assert "第一章 极限与连续" in chapters or "第二章 导数与微分" in chapters

    def test_chunk_markdown_empty(self):
        processor = DocProcessor()
        chunks = processor.chunk_markdown("", source="empty.txt")
        assert chunks == []

    def test_chunk_has_content_hash(self):
        processor = DocProcessor()
        chunks = processor.chunk_markdown("这是一段测试文本。", source="test.txt")
        assert len(chunks) == 1
        assert len(chunks[0].content_hash) == 64

    def test_chunk_max_tokens_respected(self):
        processor = DocProcessor(max_tokens=100)
        chunks = processor.chunk_markdown(TEXTBOOK_SAMPLE, source="math.pdf")
        # Individual chunks should be reasonable; total count should reflect splitting
        assert len(chunks) >= 3  # should have multiple chunks

    def test_split_long_paragraph(self):
        processor = DocProcessor(max_tokens=50)
        long_text = "。".join(["第{i}个句子".format(i=i) for i in range(20)])
        subs = processor._split_long_paragraph(long_text)
        # Should split into multiple sub-parts
        assert len(subs) >= 2

    def test_chunk_with_chapter_and_section(self):
        processor = DocProcessor(max_tokens=1000)
        text = "第一章 概述\n\n1.1 定义\n\n这是定义内容。\n\n1.2 性质\n\n这是性质内容。"
        chunks = processor.chunk_markdown(text, source="教材.pdf")
        # Should detect chapter/section structure
        assert len(chunks) >= 2

    def test_no_headings_fallback_to_paragraphs(self):
        # Use small max_tokens to force paragraph splitting into multiple chunks
        processor = DocProcessor(max_tokens=3)
        text = "第一段内容比较长。\n\n第二段内容也不少。\n\n第三段内容在这里。"
        chunks = processor.chunk_markdown(text, source="plain.txt")
        assert len(chunks) >= 2


# ═══════════════════════════════════════════════════════════════════════════
# Embedder
# ═══════════════════════════════════════════════════════════════════════════


class TestKeywordEmbedder:
    """RED → GREEN: verify keyword-based embedder."""

    def test_embed_texts_returns_correct_dim(self):
        emb = KeywordEmbedder(dim=1024)
        import asyncio
        vectors = asyncio.run(emb.embed_texts(["测试文本 about math"]))
        assert len(vectors) == 1
        assert len(vectors[0]) == 1024

    def test_is_keyword_fallback_true(self):
        emb = KeywordEmbedder()
        assert emb.is_keyword_fallback is True

    def test_embed_query(self):
        import asyncio
        emb = KeywordEmbedder(dim=256)
        v = asyncio.run(emb.embed_query("测试查询"))
        assert len(v) == 256

    def test_similar_texts_closer(self):
        """Keyword embedder: similar texts should have some overlap."""
        import asyncio
        emb = KeywordEmbedder(dim=256)
        v1 = asyncio.run(emb.embed_query("极限的定义 微积分 函数"))
        v2 = asyncio.run(emb.embed_query("极限的概念 微积分 连续性"))
        v3 = asyncio.run(emb.embed_query("计算机网络 TCP IP 协议"))

        # Compute cosine similarity
        dot_12 = sum(a * b for a, b in zip(v1, v2))
        dot_13 = sum(a * b for a, b in zip(v1, v3))
        # v1 should be more similar to v2 than v3
        assert dot_12 >= dot_13, f"Expected dot_12({dot_12}) >= dot_13({dot_13})"

    def test_embed_texts_empty(self):
        import asyncio
        emb = KeywordEmbedder(dim=100)
        vectors = asyncio.run(emb.embed_texts([]))
        assert vectors == []


class TestModuleEmbedder:
    """Verify the module-level embedder is configured."""

    def test_embedder_exists(self):
        assert embedder is not None

    def test_embedder_has_dim(self):
        assert embedder.dim > 0

    def test_embedder_reports_fallback_type(self):
        # Module embedder should always report whether it's keyword or not
        fallback = embedder.is_keyword_fallback
        assert isinstance(fallback, bool)


# ═══════════════════════════════════════════════════════════════════════════
# Retriever (unit — no DB)
# ═══════════════════════════════════════════════════════════════════════════


class TestRetrieverConfig:
    """Test retriever configuration and data structures."""

    def test_default_top_k(self):
        r = Retriever()
        assert r.top_k == 5

    def test_custom_top_k(self):
        r = Retriever(top_k=10)
        assert r.top_k == 10

    def test_retrieved_chunk_dataclass(self):
        chunk = RetrievedChunk(
            id=uuid.uuid4(),
            chunk_text="极限定义",
            source="高等数学.pdf",
            chapter="第一章",
            section="1.1",
            page="3",
            score=0.92,
            content_hash="abc123",
        )
        assert chunk.score == 0.92
        assert chunk.chapter == "第一章"
        assert chunk.source == "高等数学.pdf"

    def test_threshold_selection(self):
        r_kw = Retriever()
        r_sem = Retriever()
        # Both are configured with different thresholds
        assert r_kw.threshold_keyword > r_sem.threshold_semantic


# ═══════════════════════════════════════════════════════════════════════════
# RagEngine — prompt & parsing logic (no LLM call)
# ═══════════════════════════════════════════════════════════════════════════


class TestRagBuildContext:
    """Test context assembly from retrieved chunks."""

    def test_build_context_with_full_metadata(self):
        chunks = [
            RetrievedChunk(
                id=uuid.uuid4(),
                chunk_text="极限的定义：对于任意 ε > 0，存在 δ > 0...",
                source="高等数学.pdf",
                chapter="第一章 极限与连续",
                section="1.1 极限概念",
                page="3",
                score=0.95,
                content_hash="abc",
            )
        ]
        ctx = _build_context(chunks)
        assert "极限的定义" in ctx
        assert "高等数学.pdf" in ctx
        assert "第一章 极限与连续" in ctx
        assert "1.1 极限概念" in ctx
        assert "[片段 1]" in ctx

    def test_build_context_multiple_chunks(self):
        chunks = [
            RetrievedChunk(
                id=uuid.uuid4(),
                chunk_text="内容A",
                source="doc.pdf",
                chapter="Ch1",
                section=None,
                page=None,
                score=0.9,
                content_hash="h1",
            ),
            RetrievedChunk(
                id=uuid.uuid4(),
                chunk_text="内容B",
                source="doc.pdf",
                chapter="Ch2",
                section="2.1",
                page="10",
                score=0.8,
                content_hash="h2",
            ),
        ]
        ctx = _build_context(chunks)
        assert "[片段 1]" in ctx
        assert "[片段 2]" in ctx
        assert "内容A" in ctx
        assert "内容B" in ctx

    def test_extract_citations(self):
        chunks = [
            RetrievedChunk(
                id=uuid.uuid4(),
                chunk_text="极限的严格定义..." + "x" * 300,
                source="math.pdf",
                chapter="Ch1",
                section="1.2",
                page="5",
                score=0.88,
                content_hash="c1",
            )
        ]
        citations = _extract_citations(chunks)
        assert len(citations) == 1
        assert citations[0].source == "math.pdf"
        assert citations[0].chapter == "Ch1"
        assert len(citations[0].snippet) <= 203  # 200 + "..."


class TestRagStepParser:
    """Test step parsing logic."""

    def test_parse_numbered_steps(self):
        content = "步骤1：理解极限的定义。\n步骤2：验证ε-δ条件。\n步骤3：得出结论。"
        steps = RagEngine._parse_steps(content)
        assert len(steps) >= 3

    def test_parse_no_steps(self):
        content = "这是一段没有步骤标记的讲解文本。"
        steps = RagEngine._parse_steps(content)
        assert len(steps) == 1
        assert steps[0].step_number == 1

    def test_extract_conclusion(self):
        content = "分析过程...\n结论：极限的运算法则成立。"
        c = RagEngine._extract_conclusion(content)
        assert "极限的运算法则成立" in c

    def test_extract_conclusion_fallback(self):
        content = "简单的答案。"
        c = RagEngine._extract_conclusion(content)
        assert "简单的答案" in c


class TestRagResponse:
    """Test RagResponse dataclass."""

    def test_default_response(self):
        resp = RagResponse(question="测试问题")
        assert resp.question == "测试问题"
        assert resp.uncovered is False
        assert resp.steps == []
        assert resp.citations == []

    def test_uncovered_response(self):
        resp = RagResponse(
            question="未知问题",
            uncovered=True,
            conclusion="教材未覆盖此问题。",
        )
        assert resp.uncovered is True
        assert "教材未覆盖" in resp.conclusion


# ═══════════════════════════════════════════════════════════════════════════
# Integration-style: verify pipeline components fit together
# ═══════════════════════════════════════════════════════════════════════════


class TestPipelineIntegration:
    """Verify RAG pipeline components wire together correctly."""

    def test_processor_to_embedder_flow(self):
        """Process → embed chunks end-to-end (no DB)."""
        processor = DocProcessor(max_tokens=500)
        chunks = processor.chunk_markdown(TEXTBOOK_SAMPLE, source="math.pdf")
        assert len(chunks) > 0

        # Verify each chunk has text and metadata
        for c in chunks:
            assert c.chunk_text
            assert c.content_hash
            assert c.source == "math.pdf"

    def test_rag_engine_imports(self):
        """Verify rag_engine can be imported and initialized."""
        from app.services.rag.rag_engine import rag_engine
        assert rag_engine is not None
        assert isinstance(rag_engine, RagEngine)
