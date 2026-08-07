"""RAG Engine — retrieval-augmented generation pipeline.

Orchestrates:
  1. Retrieve relevant chunks from pgvector
  2. Assemble context with citation metadata
  3. Call LLM (flash/pro, routed by question depth) to generate an explanation
  4. Return structured response with inline citation markers

Hard rule (per PRD): if no chunks pass the similarity threshold, mark "uncovered"
and forbid the LLM from fabricating answers outside the textbook.
"""

import logging
import uuid
from dataclasses import dataclass, field

from sqlalchemy.ext.asyncio import AsyncSession

from app.services.llm_gateway import LLMGateway, llm_gateway
from app.services.rag.embedder import embedder
from app.services.rag.retriever import RetrievedChunk, retriever

logger = logging.getLogger(__name__)

# ── Output structures ──────────────────────────────────────────────────────


@dataclass
class Citation:
    """A source citation referencing a textbook passage."""

    source: str  # document name
    chapter: str | None = None
    section: str | None = None
    page: str | None = None
    snippet: str = ""  # relevant excerpt from the chunk
    chunk_id: str = ""


@dataclass
class ExplanationStep:
    """One step in the explanation chain."""

    step_number: int
    content: str
    citations: list[Citation] = field(default_factory=list)


@dataclass
class RagResponse:
    """Full RAG explanation result."""

    question: str
    steps: list[ExplanationStep] = field(default_factory=list)
    conclusion: str = ""
    citations: list[Citation] = field(default_factory=list)
    uncovered: bool = False  # True when textbook didn't cover the question
    model_used: str = ""
    token_usage: dict = field(default_factory=dict)


# ── Prompt template ────────────────────────────────────────────────────────

_RAG_SYSTEM_PROMPT = """你是一个大学课程 AI 助教，叫 AceExam。你的回答必须严格基于下面提供的教材片段。
规则：
1. 用连续的步骤讲解，每一步都要引用教材原文（标注 [来源: 章节/页码]）。
2. 如果教材片段无法回答用户的问题，你必须明确说"教材未覆盖此问题"，不要编造。
3. 最后给出一个简洁的结论总结。
4. 用中文回答，公式用 LaTeX 表达。"""

_UNCOVERED_SYSTEM_PROMPT = """你是一个大学课程 AI 助教，叫 AceExam。
用户问了一个问题，但在教材中找不到相关内容。
你必须礼貌地告诉用户：这个问题在已上传的教材中未覆盖，建议查阅其他资料或向老师请教。
不要尝试猜测或编造答案。用中文回答。"""


def _build_context(chunks: list[RetrievedChunk]) -> str:
    """Assemble retrieved chunks into a context block for the LLM prompt."""
    parts: list[str] = []
    for i, c in enumerate(chunks, 1):
        source_label = c.source
        if c.chapter:
            source_label += f" / {c.chapter}"
        if c.section:
            source_label += f" / {c.section}"
        if c.page:
            source_label += f" / p.{c.page}"

        parts.append(
            f"[片段 {i}] 来源: {source_label}\n"
            f"内容:\n{c.chunk_text}\n"
        )
    return "\n---\n".join(parts)


def _extract_citations(chunks: list[RetrievedChunk]) -> list[Citation]:
    """Build citation list from retrieved chunks."""
    return [
        Citation(
            source=c.source,
            chapter=c.chapter,
            section=c.section,
            page=c.page,
            snippet=c.chunk_text[:200] + ("..." if len(c.chunk_text) > 200 else ""),
            chunk_id=str(c.id),
        )
        for c in chunks
    ]


# ── Engine ─────────────────────────────────────────────────────────────────


class RagEngine:
    """RAG explanation pipeline."""

    def __init__(self, gateway: LLMGateway | None = None) -> None:
        self._gateway = gateway or llm_gateway

    async def explain(
        self,
        db: AsyncSession,
        question: str,
        subject_id: uuid.UUID | None = None,
        require_depth: bool = False,
        top_k: int = 5,
    ) -> RagResponse:
        """Run the full RAG pipeline.

        Args:
            db: async DB session
            question: the user's question
            subject_id: optional subject scope
            require_depth: if True, force pro tier
            top_k: number of chunks to retrieve

        Returns:
            RagResponse with steps, citations, and uncovered flag
        """
        # ── 1. Retrieve ──
        chunks = await retriever.retrieve(
            db, question, subject_id=subject_id, top_k=top_k
        )

        # ── 2. Uncovered check ──
        if not chunks:
            logger.info("RAG: no chunks retrieved for question=%r", question[:80])
            return await self._explain_uncovered(question)

        logger.info(
            "RAG: retrieved %d chunks for question=%r (scores: %s)",
            len(chunks),
            question[:80],
            [f"{c.score:.3f}" for c in chunks],
        )

        # ── 3. Build context and prompt ──
        context = _build_context(chunks)
        user_prompt = (
            f"用户问题：{question}\n\n"
            f"教材参考片段：\n{context}\n\n"
            f"请根据以上教材内容，分步骤讲解，并标注引用来源。"
        )
        messages = [
            {"role": "system", "content": _RAG_SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ]

        # ── 4. Route tier and call LLM ──
        tier = self._gateway.route_tier(require_depth=require_depth, difficulty=4)
        result = await self._gateway.chat(tier, messages, temperature=0.3)

        # ── 5. Parse response into steps ──
        content = result.get("content", "")
        steps = self._parse_steps(content)

        citations = _extract_citations(chunks)

        return RagResponse(
            question=question,
            steps=steps,
            conclusion=self._extract_conclusion(content),
            citations=citations,
            uncovered=False,
            model_used=result.get("model", ""),
            token_usage={
                "prompt_tokens": result.get("usage", {}).get("prompt_tokens", 0),
                "completion_tokens": result.get("usage", {}).get("completion_tokens", 0),
            },
        )

    async def _explain_uncovered(self, question: str) -> RagResponse:
        """Handle case where textbook doesn't cover the question."""
        messages = [
            {"role": "system", "content": _UNCOVERED_SYSTEM_PROMPT},
            {"role": "user", "content": f"用户的问题：{question}\n\n教材中未找到相关内容。"},
        ]
        result = await self._gateway.chat("flash", messages, temperature=0.3)

        return RagResponse(
            question=question,
            conclusion=result.get("content", "教材未覆盖此问题，建议查阅其他资料。"),
            uncovered=True,
            model_used=result.get("model", ""),
            token_usage={
                "prompt_tokens": result.get("usage", {}).get("prompt_tokens", 0),
                "completion_tokens": result.get("usage", {}).get("completion_tokens", 0),
            },
        )

    # ── crude step parser (MVP) ─────────────────────────────────────────

    @staticmethod
    def _parse_steps(content: str) -> list[ExplanationStep]:
        """Parse LLM output into numbered steps.  Crude for MVP, can be improved."""
        import re

        # Try to split on numbered patterns like "步骤1" "1." "第一步"
        pattern = re.compile(
            r"(?:步骤\s*\d+|第[一二三四五六七八九十]+步|\d+[\.\、\)])", re.MULTILINE
        )
        parts = pattern.split(content)
        if len(parts) <= 1:
            # No step markers — treat whole content as one step
            return [ExplanationStep(step_number=1, content=content.strip())]

        steps: list[ExplanationStep] = []
        idx = 1
        for part in parts:
            part = part.strip()
            if not part:
                continue
            steps.append(ExplanationStep(step_number=idx, content=part))
            idx += 1
        return steps

    @staticmethod
    def _extract_conclusion(content: str) -> str:
        """Extract the last line or '结论' section as conclusion."""
        import re

        m = re.search(r"(?:结论|总结|综上)[:：]?\s*(.+)$", content, re.MULTILINE)
        if m:
            return m.group(1).strip()
        # Last non-empty line as fallback
        lines = [l.strip() for l in content.split("\n") if l.strip()]
        return lines[-1] if lines else content.strip()


# ── module-level convenience ──

rag_engine = RagEngine()
