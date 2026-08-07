"""Subjects router — list / create / knowledge-points."""
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db import get_db
from app.db.models import KnowledgePoint, Subject
from app.schemas.subjects import (
    KnowledgePointResponse,
    KnowledgePointTreeResponse,
    SubjectCreate,
    SubjectResponse,
)

router = APIRouter(tags=["subjects"])


@router.get("/subjects", response_model=list[SubjectResponse])
async def list_subjects(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Subject).where(Subject.is_active).order_by(Subject.sort_order)
    )
    subjects = result.scalars().all()
    return [
        SubjectResponse(
            id=str(s.id),
            code=s.code,
            name=s.name,
            description=s.description,
            is_active=s.is_active,
            sort_order=s.sort_order,
            config=s.config,
        )
        for s in subjects
    ]


@router.post("/subjects", response_model=SubjectResponse, status_code=status.HTTP_201_CREATED)
async def create_subject(
    body: SubjectCreate,
    db: AsyncSession = Depends(get_db),
    _user=Depends(get_current_user),
):
    existing = await db.execute(select(Subject).where(Subject.code == body.code))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Subject code already exists")

    subject = Subject(**body.model_dump())
    db.add(subject)
    await db.commit()
    await db.refresh(subject)
    return SubjectResponse(
        id=str(subject.id),
        code=subject.code,
        name=subject.name,
        description=subject.description,
        is_active=subject.is_active,
        sort_order=subject.sort_order,
        config=subject.config,
    )


@router.get(
    "/subjects/{subject_id}/knowledge-points",
    response_model=list[KnowledgePointResponse],
)
async def list_knowledge_points(
    subject_id: str,
    parent_id: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
    _user=Depends(get_current_user),
):
    stmt = select(KnowledgePoint).where(KnowledgePoint.subject_id == subject_id)
    if parent_id is not None:
        stmt = stmt.where(KnowledgePoint.parent_id == parent_id)
    stmt = stmt.order_by(KnowledgePoint.sort_order)
    result = await db.execute(stmt)
    kps = result.scalars().all()
    return [
        KnowledgePointResponse(
            id=str(kp.id),
            subject_id=str(kp.subject_id),
            parent_id=str(kp.parent_id) if kp.parent_id else None,
            name=kp.name,
            content=kp.content,
            level=kp.level,
            sort_order=kp.sort_order,
        )
        for kp in kps
    ]


@router.get(
    "/knowledge-points/tree",
    response_model=list[KnowledgePointTreeResponse],
)
async def knowledge_point_tree(
    subject_id: str = Query(...),
    db: AsyncSession = Depends(get_db),
    _user=Depends(get_current_user),
):
    result = await db.execute(
        select(KnowledgePoint)
        .where(KnowledgePoint.subject_id == subject_id)
        .order_by(KnowledgePoint.sort_order)
    )
    all_kps = result.scalars().all()

    node_map: dict[str, KnowledgePointTreeResponse] = {}
    roots: list[KnowledgePointTreeResponse] = []

    for kp in all_kps:
        node = KnowledgePointTreeResponse(
            id=str(kp.id),
            name=kp.name,
            level=kp.level,
            children=[],
        )
        node_map[str(kp.id)] = node

    for kp in all_kps:
        node = node_map[str(kp.id)]
        if kp.parent_id and str(kp.parent_id) in node_map:
            node_map[str(kp.parent_id)].children.append(node)
        else:
            roots.append(node)

    return roots
