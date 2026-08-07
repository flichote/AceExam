"""RAG explanation engine — document chunking, embedding, retrieval, generation."""

from app.services.rag.doc_processor import Chunk, DocProcessor, processor
from app.services.rag.embedder import Embedder, embedder
from app.services.rag.rag_engine import (
    Citation,
    ExplanationStep,
    RagEngine,
    RagResponse,
    rag_engine,
)
from app.services.rag.retriever import RetrievedChunk, Retriever, retriever

__all__ = [
    # doc_processor
    "Chunk",
    "DocProcessor",
    "processor",
    # embedder
    "Embedder",
    "embedder",
    # retriever
    "RetrievedChunk",
    "Retriever",
    "retriever",
    # rag_engine
    "Citation",
    "ExplanationStep",
    "RagEngine",
    "RagResponse",
    "rag_engine",
]
