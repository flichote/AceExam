"""Courses router — M5 课程归一对齐 API (api.md §14.1~§14.4)."""
import re
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db import get_db
from app.db.models import CourseAlias, Subject, User, UserSubject
from app.schemas.courses import (
    CourseAliasItem,
    CourseAliasListResponse,
    CourseCreateRequest,
    CourseMatchCandidate,
    CourseMatchRequest,
    CourseMatchResponse,
    UserCourseListResponse,
    UserCourseResponse,
    UserCourseSubjectBrief,
    UserCourseUserSubject,
)

router = APIRouter(tags=["courses"])


# ── 归一化辅助 ──

_NORMALIZE_RE = re.compile(r"[\(（].*?[\)）]|\s|\d{4}春?|学期")
_WHITESPACE_RE = re.compile(r"\s+")


def _normalize_course_name(name: str) -> str:
    """归一化课程名：去括号内容、去学期/年份、去空白、小写。"""
    cleaned = _NORMALIZE_RE.sub("", name)
    cleaned = _WHITESPACE_RE.sub("", cleaned)
    return cleaned.strip().lower()


# ── AI 匹配 mock（T31 接口占位）──

_MOCK_COURSE_MATCHER: dict[str, list[dict]] = {
    "高等数学a": [
        {"template_subject_id": "mock-gaoshu-uuid", "name": "高等数学", "code": "math_gaoshu", "confidence": 0.92, "reason": "别名精确命中：高等数学A"},
    ],
    "高等数学": [
        {"template_subject_id": "mock-gaoshu-uuid", "name": "高等数学", "code": "math_gaoshu", "confidence": 0.88, "reason": "语义匹配：高等数学"},
    ],
    "线性代数": [
        {"template_subject_id": "mock-xiandai-uuid", "name": "线性代数", "code": "math_xiandai", "confidence": 0.85, "reason": "语义匹配：线性代数"},
    ],
    "概率论": [
        {"template_subject_id": "mock-gailv-uuid", "name": "概率论与数理统计", "code": "math_gailv", "confidence": 0.80, "reason": "语义匹配：概率论与数理统计"},
    ],
}


async def _call_course_matcher(name: str, limit: int) -> list[dict]:
    """调用 T31 course_matcher 服务（M5 接口占位，mock 实现）。

    T31 就绪后替换为真实 HTTP 调用。返回契约：
    [{"template_subject_id", "confidence", "reason", "name", "code"}, ...]
    """
    normalized = _normalize_course_name(name)
    candidates = _MOCK_COURSE_MATCHER.get(normalized, [])
    return candidates[:limit]


# ── 14.1 GET /courses/aliases ──


@router.get("/courses/aliases", response_model=CourseAliasListResponse)
async def list_course_aliases(
    q: str | None = Query(default=None, description="别名前缀/包含匹配"),
    limit: int = Query(default=10, ge=1, le=20),
    template_subject_id: str | None = Query(default=None, description="按模板课程过滤"),
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    """查询课程别名，供录入时联想（api.md §14.1）。"""
    stmt = select(CourseAlias, Subject.name, Subject.code).join(
        Subject, CourseAlias.template_subject_id == Subject.id
    )

    if template_subject_id:
        try:
            tid = uuid.UUID(template_subject_id)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid template_subject_id")
        stmt = stmt.where(CourseAlias.template_subject_id == tid)

    if q:
        stmt = stmt.where(CourseAlias.alias.ilike(f"%{q}%"))
        stmt = stmt.order_by(CourseAlias.is_verified.desc(), CourseAlias.alias)
    else:
        stmt = stmt.where(CourseAlias.is_verified == True)
        stmt = stmt.order_by(CourseAlias.alias)

    stmt = stmt.limit(limit)

    result = await db.execute(stmt)
    rows = result.all()

    items = [
        CourseAliasItem(
            alias=ca.alias,
            template_subject_id=str(ca.template_subject_id),
            template_name=name,
            template_code=code,
            source=ca.source,
            is_verified=ca.is_verified,
        )
        for ca, name, code in rows
    ]

    # Count total matching
    count_stmt = select(func.count()).select_from(CourseAlias)
    if template_subject_id:
        count_stmt = count_stmt.where(CourseAlias.template_subject_id == tid)
    if q:
        count_stmt = count_stmt.where(CourseAlias.alias.ilike(f"%{q}%"))
    else:
        count_stmt = count_stmt.where(CourseAlias.is_verified == True)
    count_result = await db.execute(count_stmt)
    total = count_result.scalar() or 0

    return CourseAliasListResponse(items=items, total=total)


# ── 14.2 POST /courses/match ──


@router.post("/courses/match", response_model=CourseMatchResponse)
async def match_course(
    body: CourseMatchRequest,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    """校本课程名 → 匹配模板课程（api.md §14.2）。"""
    # Step 1: 归一化
    normalized = _normalize_course_name(body.name)

    # Step 2: 精确别名命中
    alias_result = await db.execute(
        select(CourseAlias, Subject.name, Subject.code)
        .join(Subject, CourseAlias.template_subject_id == Subject.id)
        .where(CourseAlias.is_verified == True)
    )
    alias_rows = alias_result.all()

    for ca, subj_name, subj_code in alias_rows:
        if _normalize_course_name(ca.alias) == normalized:
            candidates = [
                CourseMatchCandidate(
                    template_subject_id=str(ca.template_subject_id),
                    name=subj_name,
                    code=subj_code,
                    confidence=1.0,
                    reason=f"别名精确命中：{ca.alias}",
                    source="alias",
                )
            ]
            return CourseMatchResponse(
                matched=True,
                candidates=candidates,
                strategy="alias",
            )

    # Step 3: AI 语义匹配（T31 course_matcher mock）
    ai_candidates = await _call_course_matcher(body.name, body.limit)

    if not ai_candidates:
        return CourseMatchResponse(
            matched=False,
            candidates=[],
            strategy="ai",
        )

    # Step 4: 解析 AI 结果 → 查询对应的 Subject
    matched_candidates: list[CourseMatchCandidate] = []
    for ac in ai_candidates:
        tid = ac.get("template_subject_id", "")
        confidence = float(ac.get("confidence", 0))
        reason = ac.get("reason", "")

        # 查询模板课程信息
        if tid:
            try:
                tid_uuid = uuid.UUID(tid)
            except ValueError:
                # mock / non-UUID id — use values from AI response directly
                matched_candidates.append(
                    CourseMatchCandidate(
                        template_subject_id=tid,
                        name=ac.get("name", ""),
                        code=ac.get("code", ""),
                        confidence=confidence,
                        reason=reason,
                        source="ai",
                    )
                )
                continue

            subj_result = await db.execute(
                select(Subject.name, Subject.code).where(Subject.id == tid_uuid)
            )
            subj_row = subj_result.one_or_none()
            if subj_row:
                matched_candidates.append(
                    CourseMatchCandidate(
                        template_subject_id=tid,
                        name=subj_row[0],
                        code=subj_row[1],
                        confidence=confidence,
                        reason=reason,
                        source="ai",
                    )
                )

    # D21 阈值决策
    if not matched_candidates:
        return CourseMatchResponse(matched=False, candidates=[], strategy="ai")

    top_confidence = matched_candidates[0].confidence if matched_candidates else 0
    matched = top_confidence >= 0.60

    return CourseMatchResponse(
        matched=matched,
        candidates=matched_candidates,
        strategy="ai",
    )
