"""pgvector-based document chunk retriever.

Uses cosine_distance for similarity search over DocumentChunk embeddings.
Returns top-k chunks with distance scores; filters below a configurable threshold.
"""

import logging
import uuid
from dataclasses import dataclass

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import DocumentChunk
from app.services.rag.embedder import embedder

logger = logging.getLogger(__name__)

# Cosine distance threshold: below this, results are "too far" and discarded.
# Cosine distance ∈ [0, 2]; 0 = identical, 1 = orthogonal, 2 = opposite.
# For semantic search, 0.5-0.7 is a reasonable cutoff; keyword is noisier, so use 0.6.
COSSIM_THRESHOLD_KEYWORD = 0.60
COSSIM_THRESHOLD_SEMANTIC = 0.40


@dataclass
class RetrievedChunk:
    """A retrieved document chunk with metadata and score."""

    id: uuid.UUID
    chunk_text: str
    source: str
    chapter: str | None
    section: str | None
    page: str | None
    score: float  # 1 - cosine_distance (higher = more similar)
    content_hash: str


class Retriever:
    """Search DocumentChunk by query via pgvector cosine_distance."""

    def __init__(
        self,
        top_k: int = 5,
        threshold_keyword: float = COSSIM_THRESHOLD_KEYWORD,
        threshold_semantic: float = COSSIM_THRESHOLD_SEMANTIC,
    ) -> None:
        self.top_k = top_k
        self.threshold_keyword = threshold_keyword
        self.threshold_semantic = threshold_semantic

    @property
    def threshold(self) -> float:
        """Active threshold based on current embedder type."""
        return (
            self.threshold_keyword
            if embedder.is_keyword_fallback
            else self.threshold_semantic
        )

    async def retrieve(
        self,
        db: AsyncSession,
        query: str,
        subject_id: uuid.UUID | None = None,
        top_k: int | None = None,
    ) -> list[RetrievedChunk]:
        """Search chunks by semantic (or keyword) similarity.

        Args:
            db: async database session
            query: natural-language query
            subject_id: optional subject filter
            top_k: override default top-k (default 5)

        Returns:
            list of RetrievedChunk, sorted by descending similarity score
        """
        k = top_k or self.top_k
        embedding = await embedder.embed_query(query)
        threshold = self.threshold

        # Build the pgvector cosine_distance query
        # pgvector: cosine_distance(a, b) = 1 - cos(a, b)
        # We want score = 1 - distance, so higher score = more similar
        cols = [
            DocumentChunk.id,
            DocumentChunk.chunk_text,
            DocumentChunk.source,
            DocumentChunk.chapter,
            DocumentChunk.section,
            DocumentChunk.page,
            DocumentChunk.content_hash,
            (1.0 - DocumentChunk.embedding.cosine_distance(embedding)).label("score"),
        ]

        stmt = select(*cols).where(
            DocumentChunk.embedding.isnot(None),
        )

        if subject_id is not None:
            stmt = stmt.where(DocumentChunk.subject_id == subject_id)

        stmt = (
            stmt.order_by(DocumentChunk.embedding.cosine_distance(embedding))
            .limit(k)
        )

        result = await db.execute(stmt)
        rows = result.all()

        chunks: list[RetrievedChunk] = []
        for row in rows:
            score = float(row.score)
            if score < threshold:
                continue
            chunks.append(
                RetrievedChunk(
                    id=row.id,
                    chunk_text=row.chunk_text,
                    source=row.source,
                    chapter=row.chapter,
                    section=row.section,
                    page=row.page,
                    score=round(score, 4),
                    content_hash=row.content_hash,
                )
            )

        logger.debug(
            "retrieve: query=%r subject=%s top_k=%d → %d results (threshold=%.2f)",
            query[:80],
            subject_id,
            k,
            len(chunks),
            threshold,
        )
        return chunks

    async def search_by_keywords(
        self,
        db: AsyncSession,
        keywords: list[str],
        subject_id: uuid.UUID | None = None,
        limit: int = 10,
    ) -> list[RetrievedChunk]:
        """Full-text keyword search fallback (no embedding required).

        Uses PostgreSQL ILIKE for substring matching.  Slower on large tables
        but works without any embedding model.
        """
        conditions = []
        for kw in keywords:
            pattern = f"%{kw}%"
            conditions.append(DocumentChunk.chunk_text.ilike(pattern))

        stmt = select(DocumentChunk).where(*conditions)
        if subject_id is not None:
            stmt = stmt.where(DocumentChunk.subject_id == subject_id)
        stmt = stmt.limit(limit)

        result = await db.execute(stmt)
        rows = result.scalars().all()

        return [
            RetrievedChunk(
                id=r.id,
                chunk_text=r.chunk_text,
                source=r.source,
                chapter=r.chapter,
                section=r.section,
                page=r.page,
                score=1.0,  # exact keyword match
                content_hash=r.content_hash,
            )
            for r in rows
        ]


# ── module-level convenience ──

retriever = Retriever()
