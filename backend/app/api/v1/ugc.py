"""UGC router — M5 UGC 投稿 + AI 初审 + 审核状态查询 (api.md §14.5~§14.6)."""
import hashlib
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db import get_db
from app.db.models import KnowledgePoint, Question, Subject, User, UserSubject
from app.schemas.ugc import (
    AIReviewResult,
    UGCUploadRequest,
    UGCUploadResponse,
    UgcStatusItem,
    UgcStatusListResponse,
)

router = APIRouter(tags=["ugc"])


# ── AI 初审 mock（T31 ugc_review 接口占位）──


async def _call_ugc_review(
    content: str,
    type_: str,
    answer: str | list[str] | None,
    options: list[dict] | None,
    knowledge_point_id: uuid.UUID | None,
) -> AIReviewResult:
    """调用 T31 ugc_review 服务（M5 接口占位，mock 实现）。

    T31 就绪后替换为真实 HTTP 调用。返回契约：
    {\"verdict\": \"pass\"|\"flag\", \"confidence\": 0~1, \"reasons\": [...]}
    """
    reasons: list[str] = []

    # Mock checks
    if len(content.strip()) >= 15:
        reasons.append("题干完整")
    if answer is not None:
        reasons.append("答案自算一致")
    if knowledge_point_id is not None:
        reasons.append("知识点归属正确")

    # Simple mock: all content ≥15 chars passes
    if len(content.strip()) < 15:
        return AIReviewResult(verdict="flag", confidence=0.3, reasons=["题干过短"])
    if not answer:
        return AIReviewResult(verdict="flag", confidence=0.4, reasons=["无答案"])

    return AIReviewResult(verdict="pass", confidence=0.9, reasons=reasons)


# ── AI 初审结果 → reject_reason 前缀编码 ──

def _encode_ai_review_prefix(result: AIReviewResult | None) -> str | None:
    """将 AI 初审结果编码为 reject_reason 前缀（MVP 约定，api.md §14.6 备注）。"""
    if result is None:
        return None
    if result.verdict == "flag":
        return f"[AI:flag] {'; '.join(result.reasons)}" if result.reasons else "[AI:flag]"
    return None


def _parse_ai_review_from_reject_reason(reject_reason: str | None, status: str) -> AIReviewResult | None:
    """从 reject_reason 前缀反向解析 AI 初审结果。"""
    if not reject_reason:
        if status == "active":
            return AIReviewResult(verdict="pass", confidence=0.9, reasons=["自动通过"])
        return None

    if reject_reason.startswith("[AI:flag]"):
        reason_text = reject_reason[len("[AI:flag]"):].strip()
        reasons = [r.strip() for r in reason_text.split(";") if r.strip()]
        return AIReviewResult(verdict="flag", confidence=0.5, reasons=reasons)

    return None


# ── 14.5 POST /ugc/upload ──


@router.post("/ugc/upload", response_model=UGCUploadResponse, status_code=status.HTTP_201_CREATED)
async def upload_ugc(
    body: UGCUploadRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """UGC 投稿 → 规则预检 → AI 初审 → pending（api.md §14.5）。"""

    # ── 规则预检 ──
    # content ≥ 15 字
    if len(body.content.strip()) < 15:
        raise HTTPException(status_code=422, detail="Content must be at least 15 characters")

    # type/answer/options 结构校验
    if body.type in ("single", "multi") and body.options:
        option_keys = {opt["key"] for opt in body.options if isinstance(opt, dict)}
        if body.type == "single":
            if not isinstance(body.answer, str) or body.answer not in option_keys:
                raise HTTPException(
                    status_code=422,
                    detail="Answer must match one of the option keys",
                )
        elif body.type == "multi":
            answers = body.answer if isinstance(body.answer, list) else [body.answer]
            if not all(a in option_keys for a in answers):
                raise HTTPException(
                    status_code=422,
                    detail="All answers must match option keys",
                )

    # ── 去重（content_hash）──
    content_hash = hashlib.sha256(body.content.strip().encode()).hexdigest()
    dup_result = await db.execute(
        select(Question).where(
            Question.subject_id == body.subject_id,
            Question.status.in_(["pending", "active"]),
        )
    )
    for q in dup_result.scalars().all():
        q_hash = hashlib.sha256(q.content.strip().encode()).hexdigest()
        if q_hash == content_hash:
            raise HTTPException(
                status_code=409,
                detail={
                    "code": "DUPLICATE",
                    "message": "Similar question already exists",
                    "detail": {"question_id": str(q.id)},
                },
            )

    # ── 验证 subject_id / knowledge_point_id ──
    subj_result = await db.execute(
        select(Subject).where(Subject.id == body.subject_id, Subject.is_active == True)
    )
    subject = subj_result.scalar_one_or_none()
    if not subject:
        raise HTTPException(status_code=404, detail="Subject not found")

    kp_result = await db.execute(
        select(KnowledgePoint).where(KnowledgePoint.id == body.knowledge_point_id)
    )
    kp = kp_result.scalar_one_or_none()
    if not kp:
        raise HTTPException(status_code=404, detail="Knowledge point not found")

    # ── subject_id 解析（通过 user_subjects.template_subject_id 或 subjects 自身）──
    # 题目挂模板课程（跨校共享）
    resolved_subject_id = body.subject_id
    if subject.level == "school":
        # 校本课程 → 查找 template_subject_id
        us_result = await db.execute(
            select(UserSubject.template_subject_id).where(
                UserSubject.user_id == user.id,
                UserSubject.subject_id == body.subject_id,
            )
        )
        us_row = us_result.one_or_none()
        if us_row and us_row[0]:
            resolved_subject_id = us_row[0]

    # ── AI 初审 ──
    ai_review_result: AIReviewResult | None = None
    if not body.skip_ai_review:
        ai_review_result = await _call_ugc_review(
            content=body.content,
            type_=body.type,
            answer=body.answer,
            options=body.options,
            knowledge_point_id=body.knowledge_point_id,
        )

    # ── 决策：active vs pending ──
    auto_approve = False
    if ai_review_result and ai_review_result.verdict == "pass" and ai_review_result.confidence >= 0.9:
        # 检查 subjects.config.ugc_ai_auto_approve
        subject_config = subject.config or {}
        if subject_config.get("ugc_ai_auto_approve") is True:
            auto_approve = True

    question_status = "active" if auto_approve else "pending"
    reject_reason = _encode_ai_review_prefix(ai_review_result) if not auto_approve else None

    # ── 落库 ──
    question = Question(
        subject_id=resolved_subject_id,
        knowledge_point_id=body.knowledge_point_id,
        type=body.type,
        content=body.content.strip(),
        options=[opt if isinstance(opt, dict) else opt for opt in (body.options or [])],
        answer=body.answer,
        analysis=body.analysis,
        difficulty=3,
        source="ugc",
        status=question_status,
        submitted_by=user.id,
        reject_reason=reject_reason,
    )
    db.add(question)
    await db.commit()
    await db.refresh(question)

    return UGCUploadResponse(
        question_id=str(question.id),
        status=question_status,
        duplicated=False,
        ai_review=ai_review_result,
    )


# ── 14.6 GET /ugc/status ──


@router.get("/ugc/status", response_model=UgcStatusListResponse)
async def list_ugc_status(
    status_filter: str | None = Query(default=None, alias="status", description="pending | active | rejected"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """投稿审核状态查询 — 仅返回当前用户投稿（api.md §14.6）。"""
    # 查询
    stmt = (
        select(Question, Subject.name, KnowledgePoint.name)
        .join(Subject, Question.subject_id == Subject.id)
        .join(KnowledgePoint, Question.knowledge_point_id == KnowledgePoint.id)
        .where(Question.submitted_by == user.id, Question.source == "ugc")
    )

    if status_filter:
        stmt = stmt.where(Question.status == status_filter)

    stmt = stmt.order_by(Question.created_at.desc())

    # 总数
    count_stmt = select(func.count()).select_from(Question).where(
        Question.submitted_by == user.id, Question.source == "ugc"
    )
    if status_filter:
        count_stmt = count_stmt.where(Question.status == status_filter)
    count_result = await db.execute(count_stmt)
    total = count_result.scalar() or 0

    # 分页
    offset = (page - 1) * page_size
    stmt = stmt.offset(offset).limit(page_size)

    result = await db.execute(stmt)
    rows = result.all()

    items: list[UgcStatusItem] = []
    for q, subj_name, kp_name in rows:
        # content 截断 50 字
        content_truncated = q.content[:50] + "…" if len(q.content) > 50 else q.content

        ai_review = _parse_ai_review_from_reject_reason(q.reject_reason, q.status)

        items.append(
            UgcStatusItem(
                question_id=str(q.id),
                subject_id=str(q.subject_id),
                subject_name=subj_name,
                knowledge_point_id=str(q.knowledge_point_id),
                knowledge_point_name=kp_name,
                type=q.type,
                content=content_truncated,
                status=q.status,
                reject_reason=q.reject_reason if not q.reject_reason or not q.reject_reason.startswith("[AI:") else None,
                ai_review=ai_review,
                submitted_at=q.created_at,
                reviewed_at=q.reviewed_at,
            )
        )

    return UgcStatusListResponse(
        items=items,
        page=page,
        page_size=page_size,
        total=total,
    )
