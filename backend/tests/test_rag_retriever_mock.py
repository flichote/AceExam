"""单元层测试 — RAG 检索（mock 向量库）：retriever 阈值过滤 / rag_engine uncovered 分支。

验收点（flows.md 流程1 / PRD）：
- retrieve：低于相似度阈值的片段被丢弃；subject_id 过滤生效；top_k 生效
- rag_engine.explain：无命中 → uncovered=True（"教材未覆盖"），禁止编造
- rag_engine.explain：有命中 → 组装引用 citations
"""
import importlib
import uuid
from unittest.mock import AsyncMock

import pytest

# 注意：`from app.services.rag import retriever` 会拿到包 __init__ 里 re-export 的
# singleton 实例（retriever = Retriever()），而不是模块对象。这里用 importlib 取真实模块。
retriever_module = importlib.import_module("app.services.rag.retriever")
rag_engine_module = importlib.import_module("app.services.rag.rag_engine")
from app.services.rag.retriever import RetrievedChunk, Retriever  # noqa: E402
from app.services.rag.rag_engine import RagEngine  # noqa: E402


class _StubEmbedder:
    """替身 embedder：固定向量 + keyword fallback 标记。"""

    def __init__(self, is_keyword: bool = True):
        self._is_keyword = is_keyword
        self.dim = 1024

    @property
    def is_keyword_fallback(self) -> bool:
        return self._is_keyword

    async def embed_query(self, text: str) -> list[float]:
        return [0.1, 0.2, 0.3]

    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        return [[0.1, 0.2, 0.3] for _ in texts]


class _StubGateway:
    """替身 LLM 网关：route_tier 是同步方法，chat 返回固定内容（避免 AsyncMock 未 await 警告）。"""

    def __init__(self, content: str = ""):
        self._content = content
        self.tier_calls: list[str] = []

    def route_tier(self, require_depth=False, difficulty=0, question_type=""):
        self.tier_calls.append("pro" if (require_depth or difficulty >= 4) else "flash")
        return "flash"

    async def chat(self, tier, messages, max_tokens=None, temperature=0.3):
        return {
            "content": self._content,
            "model": "deepseek-chat",
            "usage": {"prompt_tokens": 5, "completion_tokens": 3},
        }


class FakeResult:
    def __init__(self, rows):
        self._rows = rows

    def all(self):
        return self._rows


class FakeRow:
    """模拟 db.execute(...).all() 返回的行（属性访问）。"""

    def __init__(self, d):
        self._d = d

    def __getattr__(self, name):
        return self._d[name]


def _fake_row(chunk_id, text, score):
    return {
        "id": uuid.UUID(chunk_id),
        "chunk_text": text,
        "source": "高数.pdf",
        "chapter": "第一章",
        "section": "1.1",
        "page": "3",
        "content_hash": f"hash-{chunk_id[:4]}",
        "score": score,
    }


@pytest.fixture(autouse=True)
def _stub_embedder(monkeypatch):
    """把 retriever 引用的 embedder 换成替身（不真调向量 API）。"""
    monkeypatch.setattr(retriever_module, "embedder", _StubEmbedder())


class TestRetrieverThreshold:
    async def test_drops_below_threshold(self):
        """低于阈值（keyword threshold=0.6）的片段被过滤。"""
        retriever = Retriever(top_k=5)
        db = AsyncMock()
        db.execute.return_value = FakeResult(
            [
                FakeRow(_fake_row("11111111-1111-1111-1111-111111111111", "高相似片段", 0.95)),
                FakeRow(_fake_row("22222222-2222-2222-2222-222222222222", "低相似片段", 0.2)),
            ]
        )
        chunks = await retriever.retrieve(db, "极限是什么？")
        assert len(chunks) == 1
        assert chunks[0].chunk_text == "高相似片段"
        assert chunks[0].score == 0.95

    async def test_all_below_threshold_returns_empty(self):
        retriever = Retriever(top_k=5)
        db = AsyncMock()
        db.execute.return_value = FakeResult(
            [FakeRow(_fake_row("11111111-1111-1111-1111-111111111111", "低分", 0.1))]
        )
        chunks = await retriever.retrieve(db, "无关查询")
        assert chunks == []

    async def test_subject_filter_passed(self):
        retriever = Retriever(top_k=5)
        db = AsyncMock()
        db.execute.return_value = FakeResult(
            [FakeRow(_fake_row("11111111-1111-1111-1111-111111111111", "高分", 0.9))]
        )
        sid = uuid.uuid4()
        await retriever.retrieve(db, "q", subject_id=sid)
        # 确认 SQL 中带 subject 过滤条件（SQLite 下 UUID 渲染为无连字符 hex）
        stmt = db.execute.call_args.args[0]
        compiled = str(stmt.compile(compile_kwargs={"literal_binds": True}))
        assert sid.hex in compiled

    async def test_top_k_limited(self):
        retriever = Retriever(top_k=2)
        db = AsyncMock()
        rows = [
            FakeRow(_fake_row(f"{i:08d}-1111-1111-1111-111111111111", f"片段{i}", 0.8))
            for i in range(1, 6)
        ]
        db.execute.return_value = FakeResult(rows)
        chunks = await retriever.retrieve(db, "q")
        # top_k 在 SQL 层通过 LIMIT 实现（mock 返回全部行，Python 层不再截断）
        stmt = db.execute.call_args.args[0]
        compiled = str(stmt.compile(compile_kwargs={"literal_binds": True}))
        assert "LIMIT 2" in compiled.upper()


class TestRagEngineUncovered:
    async def test_no_chunks_marks_uncovered(self, monkeypatch):
        """无引用命中 → uncovered=True，调用"教材未覆盖"提示分支。"""
        fake_gateway = _StubGateway(content="教材未覆盖此问题，建议查阅其他资料。")
        engine = RagEngine(gateway=fake_gateway)

        # mock rag_engine 模块内的全局 retriever：返回空列表
        fake_retriever = AsyncMock()
        fake_retriever.retrieve.return_value = []
        monkeypatch.setattr(rag_engine_module, "retriever", fake_retriever)

        db = AsyncMock()
        resp = await engine.explain(db, "教材里没有的问题")
        assert resp.uncovered is True
        assert "教材未覆盖" in resp.conclusion
        assert resp.citations == []

    async def test_with_chunks_builds_citations(self, monkeypatch):
        """有引用命中 → 组装 citations，uncovered=False。"""
        fake_gateway = _StubGateway(content="步骤1：定义。\n结论：掌握。")
        engine = RagEngine(gateway=fake_gateway)

        chunk = RetrievedChunk(
            id=uuid.uuid4(),
            chunk_text="极限的定义：ε-δ 语言。",
            source="高数.pdf",
            chapter="第一章",
            section="1.1",
            page="3",
            score=0.95,
            content_hash="h1",
        )
        fake_retriever = AsyncMock()
        fake_retriever.retrieve.return_value = [chunk]
        monkeypatch.setattr(rag_engine_module, "retriever", fake_retriever)

        db = AsyncMock()
        resp = await engine.explain(db, "极限的定义是什么？")
        assert resp.uncovered is False
        assert len(resp.citations) == 1
        assert resp.citations[0].source == "高数.pdf"
        assert resp.citations[0].chapter == "第一章"
        assert len(resp.steps) >= 1
