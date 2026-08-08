"""Subjects router — list / create / knowledge-points / plaza."""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db import get_db
from app.db.models import KnowledgePoint, Question, Subject, User, UserSubject
from app.schemas.subjects import (
    KnowledgePointResponse,
    KnowledgePointTreeResponse,
    SubjectCreate,
    SubjectResponse,
)
from app.schemas.me import PlazaListResponse, PlazaSubject

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
            is_public=s.is_public,
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
        is_public=subject.is_public,
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


# ── M4 课程广场 ──


async def _get_optional_user(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> Optional[User]:
    """可选的用户认证：有 token 则返回用户，无则返回 None（不抛 401）。"""
    from app.core.security import decode_access_token
    from jose import JWTError

    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return None

    token = auth_header[7:]  # strip "Bearer "
    if not token:
        return None

    try:
        payload = decode_access_token(token)
        user_id: str = payload.get("sub", "")
    except JWTError:
        return None

    result = await db.execute(select(User).where(User.id == user_id))
    return result.scalar_one_or_none()


@router.get("/subjects/plaza", response_model=PlazaListResponse)
async def list_plaza(
    db: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(_get_optional_user),
):
    """GET /subjects/plaza：课程广场（api.md §13.4）。

    游客白名单：未登录可看列表，joined 恒 false。
    """
    # 查询公共课程（is_public=True AND is_active=True）
    result = await db.execute(
        select(Subject)
        .where(Subject.is_public == True, Subject.is_active == True)
        .order_by(Subject.sort_order, Subject.name)
    )
    subjects = result.scalars().all()

    # 查询当前用户已加入的课程（登录态才有意义）
    joined_ids: set[str] = set()
    if current_user is not None:
        us_result = await db.execute(
            select(UserSubject.subject_id).where(UserSubject.user_id == current_user.id)
        )
        joined_ids = {str(row[0]) for row in us_result.all()}

    # 批量查询每门课的题目数
    q_counts: dict[str, int] = {}
    if subjects:
        subject_ids = [s.id for s in subjects]
        qc_result = await db.execute(
            select(
                Question.subject_id,
                func.count(),
            )
            .where(
                Question.subject_id.in_(subject_ids),
                Question.status == "active",
            )
            .group_by(Question.subject_id)
        )
        q_counts = {str(row[0]): int(row[1]) for row in qc_result.all()}

    items = [
        PlazaSubject(
            id=str(s.id),
            code=s.code,
            name=s.name,
            description=s.description,
            is_public=s.is_public,
            is_active=s.is_active,
            joined=(str(s.id) in joined_ids),
            question_count=q_counts.get(str(s.id), 0),
        )
        for s in subjects
    ]

    return PlazaListResponse(items=items, total=len(items))
