"""Knowledge graph router (M3 §11.1)."""
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db import get_db
from app.db.models import Subject, User
from app.schemas.graph import GraphStats, KnowledgeGraphResponse
from app.services.knowledge_graph import build_knowledge_graph

router = APIRouter(tags=["knowledge-graph"])


@router.get(
    "/subjects/{subject_id}/knowledge-graph",
    response_model=KnowledgeGraphResponse,
)
async def get_knowledge_graph(
    subject_id: str,
    include_questions: bool = Query(True),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    # Validate subject exists
    subj_result = await db.execute(select(Subject).where(Subject.id == subject_id))
    subject = subj_result.scalar_one_or_none()
    if not subject:
        raise HTTPException(status_code=404, detail="Subject not found")

    graph_data = await build_knowledge_graph(
        db=db,
        subject_id=uuid.UUID(subject_id),
        user_id=user.id,
        include_questions=include_questions,
    )

    if graph_data is None:
        raise HTTPException(status_code=404, detail="No knowledge points found for this subject")

    return KnowledgeGraphResponse(
        subject_id=graph_data["subject_id"],
        subject_name=subject.name,
        generated_at=graph_data["generated_at"],
        root=graph_data["root"],
        stats=GraphStats(**graph_data["stats"]),
    )
