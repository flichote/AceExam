"""Knowledge graph schemas (M3 §11.1)."""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class GraphNode(BaseModel):
    """Tree node for knowledge graph visualization (ECharts series-tree ready)."""
    id: str
    name: str
    level: int
    status: str  # mastered / weak / consolidating / untouched
    question_count: int = 0
    practice_count: int | None = None  # leaf only
    accuracy: float | None = None  # leaf only, 0..1
    children: list[GraphNode] = []


class GraphStats(BaseModel):
    total_nodes: int
    leaf_count: int
    mastered_count: int
    weak_count: int
    consolidating_count: int
    untouched_count: int


class KnowledgeGraphResponse(BaseModel):
    subject_id: str
    subject_name: str
    generated_at: datetime
    root: GraphNode | None = None
    stats: GraphStats
