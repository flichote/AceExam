"""T33 M5 验收测试：课程归一对齐 + UGC 审核流（T29/T30/T31/T32 交付后验收）。

对照 docs/api.md §14（14.1~14.5）+ docs/architecture.md §14（D19~D22）：
  1. course_aliases 表结构：alias UNIQUE、template FK、source/is_verified 默认值、source CHECK
  2. GET /courses/aliases：q 过滤（ILIKE）、is_verified 优先、limit 限制、template 过滤、401
  3. POST /courses/match：
       - 别名精确命中 → strategy=alias、confidence=1.0、单候选、source=alias
       - 未命中 → AI（mock LLM）→ strategy=ai、matched 由 top confidence 决定（D21：≥0.60）
       - 阈值边界：0.85 / 0.60 / 0.59；候选按 confidence 降序（D-33 xfail 固化）
       - 归一化：去学期/年份/括号/空白
  4. POST /me/courses：
       - template_subject_id 非空 → 映射模板（template_subject_id 写入）
       - 已存在同名 level='school' 行 → 复用（subject_id=校本行, template_subject_id=模板）
       - template_subject_id 为空 → 手动建 school 实例（level='school', template NULL, code school_<hash>）
       - 幂等 409 ALREADY_EXISTS；模板不存在/不活跃 404
       - 命中沉淀 alias（D-34 xfail：当前仅 seed 写入，API 未沉淀）
  5. POST /ugc/upload：
       - 规则预检：content≥15、answer 与 options 匹配、content_hash 去重 409 DUPLICATE
       - AI 初审 pass → pending（默认 subject 配置）
       - config.ugc_ai_auto_approve=true 且 pass 且 confidence≥0.9 → active（D22 自动放行）
       - AI flag（无答案）→ pending + reject_reason "[AI:flag] ..."（D22：AI 只预筛不终审）
       - skip_ai_review → ai_review=None
       - subject_id 解析：school 实例 → 按 user_subjects.template_subject_id 解析为模板课程
  6. GET /ugc/status：仅当前用户投稿、status 过滤、ai_review 前缀反解、admin reject 后 rejected
"""
from __future__ import annotations

import uuid

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.db.models import (
    CourseAlias,
    KnowledgePoint,
    Question,
    Subject,
    User,
    UserSubject,
)
from app.api.v1 import courses as courses_api
from tests.conftest import _rand


def _headers(reg_user) -> dict:
    return reg_user[3]


async def _seed_template(db_session, *, code: str | None = None, name: str = "高等数学", level: str = "public",
                   config: dict | None = None, is_active: bool = True) -> Subject:
    """直插一个模板课程（level 默认 public），返回 ORM 对象（已 flush，id 可用）。"""
    subj = Subject(
        code=code or _rand("tpl"),
        name=name,
        description="T33 测试模板课程",
        config=config or {},
        level=level,
        is_active=is_active,
        is_public=(level == "public"),
    )
    db_session.add(subj)
    await db_session.flush()
    return subj


async def _seed_alias(db_session, alias: str, template_id, *, source: str = "seed", is_verified: bool = True) -> CourseAlias:
    """直插一条课程别名，返回 ORM 对象。"""
    ca = CourseAlias(
        alias=alias,
        template_subject_id=template_id,
        source=source,
        is_verified=is_verified,
    )
    db_session.add(ca)
    return ca


async def _seed_kp(db_session, subject_id, name: str | None = None) -> KnowledgePoint:
    kp = KnowledgePoint(
        subject_id=subject_id,
        name=name or f"知识点-{_rand('kp')}",
        content="T33 测试知识点",
        level=1,
    )
    db_session.add(kp)
    await db_session.flush()
    return kp


async def _user_id(db_session, username: str) -> str:
    res = await db_session.execute(select(User).where(User.username == username))
    return str(res.scalar_one().id)


# ═══════════════════════════════════════════════════════════════════════
# 1. course_aliases 表结构（DB 层）
# ═══════════════════════════════════════════════════════════════════════


class TestCourseAliasesTable:
    """architecture.md §14.2 / database.md §12：alias UNIQUE、template FK、默认值、CHECK。"""

    async def test_columns_exist(self, db_session):
        cols = {c.name for c in CourseAlias.__table__.columns}
        assert {"id", "alias", "template_subject_id", "source", "is_verified",
                "created_at", "updated_at"} <= cols

    async def test_alias_unique_constraint(self, db_session):
        subj = await _seed_template(db_session)
        await db_session.flush()
        await _seed_alias(db_session, "高等数学a", subj.id)
        await db_session.commit()
        # 同 alias 再插一条 → UNIQUE 冲突
        db_session.add(CourseAlias(alias="高等数学a", template_subject_id=subj.id, source="ai", is_verified=False))
        with pytest.raises(IntegrityError):
            await db_session.commit()
        await db_session.rollback()

    async def test_template_fk_declared(self, db_session):
        """template_subject_id 必须声明 FK → subjects.id（SQLite 测试库不强制 FK，做元数据级断言）。"""
        fks = CourseAlias.__table__.c.template_subject_id.foreign_keys
        assert len(fks) == 1
        fk = next(iter(fks))
        assert fk.column.table.name == "subjects"

    async def test_defaults_source_seed_and_is_verified_false(self, db_session):
        subj = await _seed_template(db_session)
        await db_session.flush()
        db_session.add(CourseAlias(alias="高数", template_subject_id=subj.id))
        await db_session.commit()
        row = (await db_session.execute(
            select(CourseAlias).where(CourseAlias.alias == "高数")
        )).scalar_one()
        assert row.source == "seed"
        assert row.is_verified is False

    async def test_source_check_constraint(self, db_session):
        subj = await _seed_template(db_session)
        await db_session.flush()
        db_session.add(CourseAlias(alias="非法来源", template_subject_id=subj.id, source="hacker"))
        with pytest.raises(IntegrityError):
            await db_session.commit()
        await db_session.rollback()

    async def test_multiple_aliases_same_template_allowed(self, db_session):
        """不同 alias 可指向同一模板（多对一），只有 alias 本身唯一。"""
        subj = await _seed_template(db_session)
        await db_session.flush()
        await _seed_alias(db_session, "高等数学a", subj.id)
        await _seed_alias(db_session, "高数上", subj.id)
        await db_session.commit()
        rows = (await db_session.execute(select(CourseAlias))).scalars().all()
        assert len(rows) == 2


# ═══════════════════════════════════════════════════════════════════════
# 2. POST /courses/match —— 别名精确命中（14.2）
# ═══════════════════════════════════════════════════════════════════════


class TestMatchAliasStrategy:

    async def test_requires_auth(self, client):
        resp = await client.post("/api/v1/courses/match", json={"name": "高等数学"})
        assert resp.status_code == 401

    async def test_verified_alias_exact_hit(self, client, registered_user, db_session):
        """归一化后精确命中 verified 别名 → strategy=alias, confidence=1.0, 单候选。"""
        subj = await _seed_template(db_session, name="高等数学")
        await _seed_alias(db_session, "高等数学a", subj.id, is_verified=True)
        await db_session.commit()

        resp = await client.post(
            "/api/v1/courses/match",
            json={"name": "高等数学A"},
            headers=_headers(registered_user),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["matched"] is True
        assert data["strategy"] == "alias"
        assert len(data["candidates"]) == 1
        c = data["candidates"][0]
        assert c["confidence"] == 1.0
        assert c["source"] == "alias"
        assert c["template_subject_id"] == str(subj.id)
        assert c["name"] == "高等数学"
        assert "精确命中" in c["reason"]

    async def test_normalization_semester_and_parens(self, client, registered_user, db_session):
        """'2026春 高等数学A（上）' 归一化后命中 '高等数学a' 别名。"""
        subj = await _seed_template(db_session, name="高等数学")
        await _seed_alias(db_session, "高等数学a", subj.id, is_verified=True)
        await db_session.commit()

        resp = await client.post(
            "/api/v1/courses/match",
            json={"name": "2026春 高等数学A（上）"},
            headers=_headers(registered_user),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["strategy"] == "alias"
        assert data["candidates"][0]["confidence"] == 1.0

    async def test_unverified_alias_falls_to_ai(self, client, registered_user, db_session):
        """is_verified=False 的别名不用于精确命中 → 走 AI 语义匹配。"""
        subj = await _seed_template(db_session, name="高等数学")
        await _seed_alias(db_session, "高等数学a", subj.id, is_verified=False)
        await db_session.commit()

        resp = await client.post(
            "/api/v1/courses/match",
            json={"name": "高等数学A"},
            headers=_headers(registered_user),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["strategy"] == "ai"  # 非 alias
        assert data["matched"] is True  # mock 命中 0.92

    async def test_name_too_long_422(self, client, registered_user):
        resp = await client.post(
            "/api/v1/courses/match",
            json={"name": "x" * 101},
            headers=_headers(registered_user),
        )
        assert resp.status_code == 422

    async def test_name_empty_422(self, client, registered_user):
        resp = await client.post(
            "/api/v1/courses/match",
            json={"name": ""},
            headers=_headers(registered_user),
        )
        assert resp.status_code == 422


# ═══════════════════════════════════════════════════════════════════════
# 3. POST /courses/match —— AI 语义匹配 + 阈值决策（D21）
# ═══════════════════════════════════════════════════════════════════════


class TestMatchAIStrategy:

    async def test_ai_mock_high_confidence(self, client, registered_user):
        """mock LLM 命中 '高等数学a'（0.92）→ strategy=ai, matched=true。"""
        resp = await client.post(
            "/api/v1/courses/match",
            json={"name": "高等数学A", "limit": 5},
            headers=_headers(registered_user),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["strategy"] == "ai"
        assert data["matched"] is True
        assert len(data["candidates"]) == 1
        c = data["candidates"][0]
        assert c["confidence"] == 0.92
        assert c["source"] == "ai"
        assert c["template_subject_id"] == "mock-gaoshu-uuid"

    async def test_ai_mock_normalized_exact_name(self, client, registered_user):
        """'高等数学'（无后缀）→ mock key '高等数学'（0.88）。"""
        resp = await client.post(
            "/api/v1/courses/match",
            json={"name": "高等数学"},
            headers=_headers(registered_user),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["strategy"] == "ai"
        assert data["candidates"][0]["confidence"] == 0.88

    async def test_ai_mock_mid_confidence(self, client, registered_user):
        """'概率论' → mock 0.80（0.60~0.85 区间）→ matched=true 候选列表。"""
        resp = await client.post(
            "/api/v1/courses/match",
            json={"name": "概率论"},
            headers=_headers(registered_user),
        )
        data = resp.json()
        assert data["strategy"] == "ai"
        assert data["matched"] is True
        assert data["candidates"][0]["confidence"] == 0.80

    async def test_ai_no_candidate_matched_false(self, client, registered_user):
        """未知课程名 → AI 无候选 → matched=false, strategy=ai。"""
        resp = await client.post(
            "/api/v1/courses/match",
            json={"name": "量子力学进阶"},
            headers=_headers(registered_user),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["matched"] is False
        assert data["candidates"] == []
        assert data["strategy"] == "ai"

    # ── 阈值边界（monkeypatch _call_course_matcher 返回指定置信度）──

    async def _post_with_confidence(self, client, headers, monkeypatch, conf: float):
        async def fake_matcher(name: str, limit: int):
            return [{
                "template_subject_id": "mock-tpl-uuid",
                "name": "高等数学",
                "code": "math_gaoshu",
                "confidence": conf,
                "reason": "语义匹配（测试）",
            }]
        monkeypatch.setattr(courses_api, "_call_course_matcher", fake_matcher)
        return await client.post(
            "/api/v1/courses/match",
            json={"name": "某校本课程名"},
            headers=headers,
        )

    async def test_threshold_085_matched(self, client, registered_user, monkeypatch):
        """边界：confidence=0.85（≥0.85 自动采用 top1 档）→ matched=true。"""
        resp = await self._post_with_confidence(client, _headers(registered_user), monkeypatch, 0.85)
        data = resp.json()
        assert data["matched"] is True
        assert data["candidates"][0]["confidence"] == 0.85

    async def test_threshold_060_matched(self, client, registered_user, monkeypatch):
        """边界：confidence=0.60（≥0.60 下界）→ matched=true 候选列表。"""
        resp = await self._post_with_confidence(client, _headers(registered_user), monkeypatch, 0.60)
        data = resp.json()
        assert data["matched"] is True
        assert data["candidates"][0]["confidence"] == 0.60

    async def test_threshold_059_not_matched(self, client, registered_user, monkeypatch):
        """边界：confidence=0.59（<0.60）→ matched=false，引导手动建实例。"""
        resp = await self._post_with_confidence(client, _headers(registered_user), monkeypatch, 0.59)
        data = resp.json()
        assert data["matched"] is False

    @pytest.mark.xfail(
        reason="D-33: POST /courses/match 候选未在 API 层按 confidence 降序（依赖上游服务排序）；契约 api.md §14.2 要求降序返回",
        strict=False,
    )
    async def test_ai_candidates_sorted_desc(self, client, registered_user, monkeypatch):
        """契约：AI 候选按 confidence 降序。当前实现透传上游顺序（本测试注入乱序 → 期望降序）。"""
        async def fake_matcher(name: str, limit: int):
            return [
                {"template_subject_id": "mock-b", "name": "线性代数", "code": "math_xiandai",
                 "confidence": 0.6, "reason": "部分匹配"},
                {"template_subject_id": "mock-a", "name": "高等数学", "code": "math_gaoshu",
                 "confidence": 0.88, "reason": "语义匹配"},
            ]
        monkeypatch.setattr(courses_api, "_call_course_matcher", fake_matcher)
        resp = await client.post(
            "/api/v1/courses/match",
            json={"name": "某校本课程名"},
            headers=_headers(registered_user),
        )
        data = resp.json()
        confs = [c["confidence"] for c in data["candidates"]]
        assert confs == sorted(confs, reverse=True)


# ═══════════════════════════════════════════════════════════════════════
# 4. POST /me/courses —— 映射模板 / 手动建实例 / 幂等（14.3）
# ═══════════════════════════════════════════════════════════════════════


class TestMeCoursesMapping:

    async def test_requires_auth(self, client):
        resp = await client.post("/api/v1/me/courses", json={"name": "高等数学"})
        assert resp.status_code == 401

    async def test_map_to_template_direct(self, client, registered_user, db_session):
        """template_subject_id 非空且无同名 school 行 → subject_id=模板行, template_subject_id=模板。"""
        tpl = await _seed_template(db_session, name="高等数学")
        await db_session.commit()

        resp = await client.post(
            "/api/v1/me/courses",
            json={"name": "清华·高数A", "template_subject_id": str(tpl.id)},
            headers=_headers(registered_user),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["matched"] is True
        assert data["user_subject"]["subject_id"] == str(tpl.id)
        assert data["user_subject"]["template_subject_id"] == str(tpl.id)
        assert data["subject"]["id"] == str(tpl.id)
        assert data["subject"]["level"] == "public"

    async def test_reuse_existing_school_instance(self, client, registered_user, db_session):
        """已存在同名 level='school' 行 → subject_id=校本行, template_subject_id=模板。"""
        tpl = await _seed_template(db_session, name="高等数学")
        school = Subject(
            code=_rand("school_x"), name="清华·高数A", level="school",
            is_active=True, is_public=False,
        )
        db_session.add_all([tpl, school])
        await db_session.commit()

        resp = await client.post(
            "/api/v1/me/courses",
            json={"name": "清华·高数A", "template_subject_id": str(tpl.id)},
            headers=_headers(registered_user),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["matched"] is True
        assert data["subject"]["id"] == str(school.id)
        assert data["subject"]["level"] == "school"
        assert data["user_subject"]["subject_id"] == str(school.id)
        assert data["user_subject"]["template_subject_id"] == str(tpl.id)

    async def test_template_not_found_404(self, client, registered_user):
        resp = await client.post(
            "/api/v1/me/courses",
            json={"name": "高等数学", "template_subject_id": str(uuid.uuid4())},
            headers=_headers(registered_user),
        )
        assert resp.status_code == 404

    async def test_template_inactive_404(self, client, registered_user, db_session):
        tpl = await _seed_template(db_session, is_active=False)
        await db_session.commit()
        resp = await client.post(
            "/api/v1/me/courses",
            json={"name": "高等数学", "template_subject_id": str(tpl.id)},
            headers=_headers(registered_user),
        )
        assert resp.status_code == 404

    async def test_invalid_template_uuid_400(self, client, registered_user):
        resp = await client.post(
            "/api/v1/me/courses",
            json={"name": "高等数学", "template_subject_id": "not-a-uuid"},
            headers=_headers(registered_user),
        )
        assert resp.status_code == 400

    async def test_mapping_duplicate_409(self, client, registered_user, db_session):
        """同用户同 subject_id 已存在 → 409 ALREADY_EXISTS。"""
        tpl = await _seed_template(db_session, name="高等数学")
        await db_session.commit()
        headers = _headers(registered_user)
        resp1 = await client.post(
            "/api/v1/me/courses",
            json={"name": "清华·高数A", "template_subject_id": str(tpl.id)},
            headers=headers,
        )
        assert resp1.status_code == 200
        resp2 = await client.post(
            "/api/v1/me/courses",
            json={"name": "清华·高数A", "template_subject_id": str(tpl.id)},
            headers=headers,
        )
        assert resp2.status_code == 409
        assert resp2.json()["detail"]["code"] == "ALREADY_EXISTS"


class TestMeCoursesSchoolInstance:

    async def test_manual_school_instance(self, client, registered_user):
        """template_subject_id 为空 → 新建 level='school' 行, template NULL, code school_<hash>。"""
        resp = await client.post(
            "/api/v1/me/courses",
            json={"name": "清华·高数A"},
            headers=_headers(registered_user),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["matched"] is False
        assert data["subject"]["level"] == "school"
        assert data["subject"]["is_public"] is False
        assert data["subject"]["code"].startswith("school_")
        assert data["user_subject"]["subject_id"] == data["subject"]["id"]
        assert data["user_subject"]["template_subject_id"] is None

    async def test_manual_duplicate_409(self, client, registered_user):
        headers = _headers(registered_user)
        resp1 = await client.post("/api/v1/me/courses", json={"name": "清华·高数A"}, headers=headers)
        assert resp1.status_code == 200
        resp2 = await client.post("/api/v1/me/courses", json={"name": "清华·高数A"}, headers=headers)
        assert resp2.status_code == 409
        assert resp2.json()["detail"]["code"] == "ALREADY_EXISTS"

    async def test_school_row_shared_between_users(self, client, registered_user, db_session):
        """不同用户录同名校本课 → 复用同一 school 行，仅新增各自 user_subjects。"""
        _, _, _, h1 = registered_user
        # 注册第二个用户
        from tests.conftest import _register_user, _auth_headers
        u2, p2, t2 = await _register_user(client, _rand("user2"))
        h2 = await _auth_headers(t2)

        r1 = await client.post("/api/v1/me/courses", json={"name": "清华·高数A"}, headers=h1)
        assert r1.status_code == 200
        r2 = await client.post("/api/v1/me/courses", json={"name": "清华·高数A"}, headers=h2)
        assert r2.status_code == 200
        # 两个 user_subjects 指向同一 subject
        sid1 = r1.json()["user_subject"]["subject_id"]
        sid2 = r2.json()["user_subject"]["subject_id"]
        assert sid1 == sid2
        rows = (await db_session.execute(
            select(Subject).where(Subject.level == "school", Subject.name == "清华·高数A")
        )).scalars().all()
        assert len(rows) == 1
        assert str(rows[0].id) == sid1
        # 第二个用户可见
        resp = await client.get("/api/v1/me/courses", headers=h2)
        assert resp.status_code == 200
        assert len(resp.json()["items"]) == 1

    async def test_list_my_courses_shows_mapping_and_school(self, client, registered_user, db_session):
        tpl = await _seed_template(db_session, name="高等数学")
        await db_session.commit()
        headers = _headers(registered_user)
        await client.post("/api/v1/me/courses", json={"name": "清华·高数A", "template_subject_id": str(tpl.id)}, headers=headers)
        await client.post("/api/v1/me/courses", json={"name": "清华·线代B"}, headers=headers)

        resp = await client.get("/api/v1/me/courses", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 2
        by_name = {it["subject"]["name"]: it for it in data["items"]}
        assert by_name["高等数学"]["matched"] is True
        assert by_name["高等数学"]["user_subject"]["template_subject_id"] == str(tpl.id)
        assert by_name["清华·线代B"]["matched"] is False
        assert by_name["清华·线代B"]["user_subject"]["template_subject_id"] is None


# ═══════════════════════════════════════════════════════════════════════
# 5. 命中沉淀 alias（架构 §14.2 飞轮闭环）
# ═══════════════════════════════════════════════════════════════════════


class TestAliasPrecipitation:

    @pytest.mark.xfail(
        reason="D-34: M5『命中沉淀 alias』未实现——course_aliases 仅在 seed 写入，AI 匹配命中/用户确认后不沉淀 source='ai' 别名（架构 §14.2『命中即 upsert』飞轮闭环缺失）",
        strict=False,
    )
    async def test_ai_match_precipitates_alias(self, client, registered_user, db_session):
        """匹配命中（AI 语义）后应沉淀一条 source='ai' 别名（幂等 upsert）。"""
        await client.post(
            "/api/v1/courses/match",
            json={"name": "高等数学A"},
            headers=_headers(registered_user),
        )
        rows = (await db_session.execute(select(CourseAlias))).scalars().all()
        assert any(r.source == "ai" for r in rows), "AI 匹配命中后未沉淀 course_aliases(source='ai')"

    @pytest.mark.xfail(
        reason="D-34: M5『命中沉淀 alias』未实现——录入映射模板后不沉淀别名（架构 §14.2 飞轮闭环缺失）",
        strict=False,
    )
    async def test_me_courses_map_precipitates_alias(self, client, registered_user, db_session):
        tpl = await _seed_template(db_session, name="高等数学")
        await db_session.commit()
        resp = await client.post(
            "/api/v1/me/courses",
            json={"name": "清华·高数A", "template_subject_id": str(tpl.id)},
            headers=_headers(registered_user),
        )
        assert resp.status_code == 200
        rows = (await db_session.execute(select(CourseAlias))).scalars().all()
        assert any(r.source == "ai" for r in rows), "录入映射模板后未沉淀 course_aliases(source='ai')"


# ═══════════════════════════════════════════════════════════════════════
# 6. GET /courses/aliases —— 联想查询（14.1）
# ═══════════════════════════════════════════════════════════════════════


class TestCourseAliasesQuery:

    async def test_requires_auth(self, client):
        resp = await client.get("/api/v1/courses/aliases")
        assert resp.status_code == 401

    async def test_no_q_returns_verified_only(self, client, registered_user, db_session):
        tpl = await _seed_template(db_session, name="高等数学")
        await db_session.flush()
        await _seed_alias(db_session, "高等数学a", tpl.id, is_verified=True)
        await _seed_alias(db_session, "高数上", tpl.id, is_verified=True)
        await _seed_alias(db_session, "高数测试未确认", tpl.id, is_verified=False)
        await db_session.commit()

        resp = await client.get("/api/v1/courses/aliases", headers=_headers(registered_user))
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 2
        assert all(it["is_verified"] is True for it in data["items"])
        assert {it["alias"] for it in data["items"]} == {"高等数学a", "高数上"}

    async def test_q_returns_matching_verified_first(self, client, registered_user, db_session):
        tpl = await _seed_template(db_session, name="高等数学")
        await db_session.flush()
        await _seed_alias(db_session, "高数A", tpl.id, is_verified=True)
        await _seed_alias(db_session, "高数", tpl.id, is_verified=True)
        await _seed_alias(db_session, "高数测试未确认", tpl.id, is_verified=False)
        await db_session.commit()

        resp = await client.get("/api/v1/courses/aliases?q=高数", headers=_headers(registered_user))
        assert resp.status_code == 200
        data = resp.json()
        # q 存在时 verified + unverified 都返回，verified 优先
        assert data["total"] == 3
        verified_flags = [it["is_verified"] for it in data["items"]]
        assert verified_flags == sorted(verified_flags, reverse=True)  # verified 在前

    async def test_q_ilike_partial(self, client, registered_user, db_session):
        tpl = await _seed_template(db_session, name="高等数学")
        await db_session.flush()
        await _seed_alias(db_session, "高等数学A", tpl.id, is_verified=True)
        await _seed_alias(db_session, "线性代数A", tpl.id, is_verified=True)
        await db_session.commit()

        # "数A" 是 "线性代数A" 的连续子串，不是 "高等数学A"（数学A 中间隔了 学）
        resp = await client.get("/api/v1/courses/aliases?q=数A", headers=_headers(registered_user))
        data = resp.json()
        assert data["total"] == 1
        assert data["items"][0]["alias"] == "线性代数A"

    async def test_limit_enforced_422(self, client, registered_user):
        resp = await client.get("/api/v1/courses/aliases?limit=21", headers=_headers(registered_user))
        assert resp.status_code == 422

    async def test_limit_honored(self, client, registered_user, db_session):
        tpl = await _seed_template(db_session, name="高等数学")
        await db_session.flush()
        for alias in ("高数A", "高数上", "高数"):
            await _seed_alias(db_session, alias, tpl.id, is_verified=True)
        await db_session.commit()

        resp = await client.get("/api/v1/courses/aliases?limit=2", headers=_headers(registered_user))
        data = resp.json()
        assert len(data["items"]) == 2
        assert data["total"] == 3  # total 反映全量，不随 limit 截断

    async def test_template_filter(self, client, registered_user, db_session):
        tpl1 = await _seed_template(db_session, name="高等数学")
        tpl2 = await _seed_template(db_session, name="线性代数")
        await db_session.flush()
        await _seed_alias(db_session, "高等数学A", tpl1.id, is_verified=True)
        await _seed_alias(db_session, "线性代数A", tpl2.id, is_verified=True)
        await db_session.commit()

        resp = await client.get(
            f"/api/v1/courses/aliases?template_subject_id={tpl1.id}",
            headers=_headers(registered_user),
        )
        data = resp.json()
        assert data["total"] == 1
        assert data["items"][0]["template_subject_id"] == str(tpl1.id)

    async def test_template_filter_invalid_uuid_400(self, client, registered_user):
        resp = await client.get(
            "/api/v1/courses/aliases?template_subject_id=bad-uuid",
            headers=_headers(registered_user),
        )
        assert resp.status_code == 400

    async def test_response_shape(self, client, registered_user, db_session):
        tpl = await _seed_template(db_session, name="高等数学", code="math_gaoshu")
        await db_session.flush()
        await _seed_alias(db_session, "高等数学A", tpl.id, is_verified=True)
        await db_session.commit()

        resp = await client.get("/api/v1/courses/aliases", headers=_headers(registered_user))
        it = resp.json()["items"][0]
        assert set(it.keys()) == {"alias", "template_subject_id", "template_name",
                                  "template_code", "source", "is_verified"}
        assert it["template_name"] == "高等数学"
        assert it["template_code"] == "math_gaoshu"
        assert it["source"] == "seed"
        assert it["is_verified"] is True


# ═══════════════════════════════════════════════════════════════════════
# 7. POST /ugc/upload —— 规则预检 + AI 初审（14.4）
# ═══════════════════════════════════════════════════════════════════════


_UGC_CONTENT = "求函数 f(x)=x^3 在 x=1 处的导数是多少？"
_UGC_OPTIONS = [
    {"key": "A", "text": "1"},
    {"key": "B", "text": "2"},
    {"key": "C", "text": "3"},
    {"key": "D", "text": "0"},
]


def _ugc_body(subject_id: str, kp_id: str, **overrides) -> dict:
    body = {
        "subject_id": subject_id,
        "knowledge_point_id": kp_id,
        "type": "single",
        "content": _UGC_CONTENT,
        "options": _UGC_OPTIONS,
        "answer": "C",
    }
    body.update(overrides)
    return body


class TestUgcUploadReviewFlow:

    async def test_requires_auth(self, client):
        resp = await client.post("/api/v1/ugc/upload", json={})
        assert resp.status_code == 401

    async def test_pass_default_pending(self, client, registered_user, seed_subject, seed_kp):
        """AI 初审 pass（mock confidence=0.9）且 subject 未开自动放行 → status=pending。"""
        resp = await client.post(
            "/api/v1/ugc/upload",
            json=_ugc_body(seed_subject["id"], seed_kp["id"]),
            headers=_headers(registered_user),
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["status"] == "pending"
        assert data["duplicated"] is False
        assert data["ai_review"]["verdict"] == "pass"
        assert data["ai_review"]["confidence"] == 0.9
        assert len(data["ai_review"]["reasons"]) >= 1

    async def test_pass_auto_approve_active(self, client, registered_user, db_session):
        """subjects.config.ugc_ai_auto_approve=true 且 pass 且 confidence≥0.9 → 直接 active（D22 自动放行）。"""
        subj = await _seed_template(db_session, name="高数自动放行", config={"ugc_ai_auto_approve": True})
        await db_session.flush()
        kp = await _seed_kp(db_session, subj.id)
        await db_session.commit()

        resp = await client.post(
            "/api/v1/ugc/upload",
            json=_ugc_body(str(subj.id), str(kp.id)),
            headers=_headers(registered_user),
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["status"] == "active"

        # DB 侧确认 status/reject_reason
        q = (await db_session.execute(
            select(Question).where(Question.id == uuid.UUID(data["question_id"]))
        )).scalar_one()
        assert q.status == "active"
        assert q.reject_reason is None

    async def test_ai_flag_no_answer_pending_with_reason(self, client, registered_user, seed_subject, seed_kp):
        """无答案 → AI flag → status=pending + reject_reason '[AI:flag] 无答案'（D22：AI 只预筛不终审）。"""
        resp = await client.post(
            "/api/v1/ugc/upload",
            json=_ugc_body(seed_subject["id"], seed_kp["id"], options=None, answer=None),
            headers=_headers(registered_user),
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["status"] == "pending"
        assert data["ai_review"]["verdict"] == "flag"
        assert any("无答案" in r for r in data["ai_review"]["reasons"])

    async def test_content_short_422(self, client, registered_user, seed_subject, seed_kp):
        """规则预检：content<15 字 → 422（不落库、不触发 AI）。"""
        resp = await client.post(
            "/api/v1/ugc/upload",
            json=_ugc_body(seed_subject["id"], seed_kp["id"], content="short"),
            headers=_headers(registered_user),
        )
        assert resp.status_code == 422

    async def test_answer_not_in_options_422(self, client, registered_user, seed_subject, seed_kp):
        resp = await client.post(
            "/api/v1/ugc/upload",
            json=_ugc_body(seed_subject["id"], seed_kp["id"], answer="Z"),
            headers=_headers(registered_user),
        )
        assert resp.status_code == 422

    async def test_duplicate_content_409(self, client, registered_user, seed_subject, seed_kp):
        """content_hash 去重：同 subject 同内容二次投稿 → 409 DUPLICATE + 既有 question_id。"""
        headers = _headers(registered_user)
        r1 = await client.post("/api/v1/ugc/upload", json=_ugc_body(seed_subject["id"], seed_kp["id"]), headers=headers)
        assert r1.status_code == 201
        r2 = await client.post("/api/v1/ugc/upload", json=_ugc_body(seed_subject["id"], seed_kp["id"]), headers=headers)
        assert r2.status_code == 409
        detail = r2.json()["detail"]
        assert detail["code"] == "DUPLICATE"
        assert detail["detail"]["question_id"] == r1.json()["question_id"]

    async def test_subject_not_found_404(self, client, registered_user, seed_kp):
        resp = await client.post(
            "/api/v1/ugc/upload",
            json=_ugc_body(str(uuid.uuid4()), seed_kp["id"]),
            headers=_headers(registered_user),
        )
        assert resp.status_code == 404

    async def test_kp_not_found_404(self, client, registered_user, seed_subject):
        resp = await client.post(
            "/api/v1/ugc/upload",
            json=_ugc_body(seed_subject["id"], str(uuid.uuid4())),
            headers=_headers(registered_user),
        )
        assert resp.status_code == 404

    async def test_skip_ai_review(self, client, registered_user, seed_subject, seed_kp):
        resp = await client.post(
            "/api/v1/ugc/upload",
            json=_ugc_body(seed_subject["id"], seed_kp["id"], skip_ai_review=True),
            headers=_headers(registered_user),
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["ai_review"] is None
        assert data["status"] == "pending"

    async def test_school_subject_resolves_to_template(self, client, registered_user, db_session):
        """投稿传 school 实例 id → 按 user_subjects.template_subject_id 解析为模板课程落库。"""
        tpl = await _seed_template(db_session, name="高等数学")
        await db_session.flush()
        kp = await _seed_kp(db_session, tpl.id)
        school = Subject(code=_rand("school_u"), name="清华·高数A", level="school", is_active=True, is_public=False)
        db_session.add(school)
        await db_session.flush()
        uid = await _user_id(db_session, registered_user[0])
        db_session.add(UserSubject(user_id=uuid.UUID(uid), subject_id=school.id, template_subject_id=tpl.id))
        await db_session.commit()

        resp = await client.post(
            "/api/v1/ugc/upload",
            json=_ugc_body(str(school.id), str(kp.id)),
            headers=_headers(registered_user),
        )
        assert resp.status_code == 201
        q = (await db_session.execute(
            select(Question).where(Question.id == uuid.UUID(resp.json()["question_id"]))
        )).scalar_one()
        assert q.subject_id == tpl.id  # 题目挂模板课程
        assert q.source == "ugc"
        assert q.submitted_by == uuid.UUID(uid)


# ═══════════════════════════════════════════════════════════════════════
# 8. GET /ugc/status —— 审核状态查询（14.5）
# ═══════════════════════════════════════════════════════════════════════


class TestUgcStatusQuery:

    async def test_requires_auth(self, client):
        resp = await client.get("/api/v1/ugc/status")
        assert resp.status_code == 401

    async def test_empty(self, client, registered_user):
        resp = await client.get("/api/v1/ugc/status", headers=_headers(registered_user))
        assert resp.status_code == 200
        data = resp.json()
        assert data["items"] == []
        assert data["total"] == 0
        assert data["page"] == 1
        assert data["page_size"] == 20

    async def test_after_upload_ai_review_parsed(self, client, registered_user, seed_subject, seed_kp):
        headers = _headers(registered_user)
        await client.post("/api/v1/ugc/upload", json=_ugc_body(seed_subject["id"], seed_kp["id"]), headers=headers)
        resp = await client.get("/api/v1/ugc/status", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        it = data["items"][0]
        assert it["status"] == "pending"
        assert it["reject_reason"] is None  # [AI: 前缀不直接暴露
        assert it["subject_name"] == seed_subject["name"]
        assert it["type"] == "single"
        assert it["question_id"] is not None

    @pytest.mark.xfail(
        reason="D-36: /ugc/status 对 pass→pending 投稿 ai_review=null（AI 初审 pass 未持久化，契约 api.md §14.5 示例要求透传 verdict=pass+reasons）",
        strict=False,
    )
    async def test_ai_review_passthrough_for_pending_pass(self, client, registered_user, seed_subject, seed_kp):
        """契约 §14.5 示例：pending 投稿应返回 ai_review {verdict: pass, confidence, reasons}。"""
        headers = _headers(registered_user)
        await client.post("/api/v1/ugc/upload", json=_ugc_body(seed_subject["id"], seed_kp["id"]), headers=headers)
        resp = await client.get("/api/v1/ugc/status", headers=headers)
        it = resp.json()["items"][0]
        assert it["ai_review"] is not None
        assert it["ai_review"]["verdict"] == "pass"

    async def test_flag_reason_shown_in_ai_review(self, client, registered_user, seed_subject, seed_kp):
        headers = _headers(registered_user)
        await client.post(
            "/api/v1/ugc/upload",
            json=_ugc_body(seed_subject["id"], seed_kp["id"], options=None, answer=None),
            headers=headers,
        )
        resp = await client.get("/api/v1/ugc/status", headers=headers)
        it = resp.json()["items"][0]
        assert it["ai_review"]["verdict"] == "flag"
        assert any("无答案" in r for r in it["ai_review"]["reasons"])

    async def test_status_filter(self, client, registered_user, seed_subject, seed_kp):
        headers = _headers(registered_user)
        await client.post("/api/v1/ugc/upload", json=_ugc_body(seed_subject["id"], seed_kp["id"]), headers=headers)
        r_pending = await client.get("/api/v1/ugc/status?status=pending", headers=headers)
        assert r_pending.json()["total"] == 1
        r_rejected = await client.get("/api/v1/ugc/status?status=rejected", headers=headers)
        assert r_rejected.json()["total"] == 0

    async def test_only_own_submissions(self, client, registered_user, seed_subject, seed_kp):
        from tests.conftest import _register_user, _auth_headers
        _, _, _, h1 = registered_user
        await client.post("/api/v1/ugc/upload", json=_ugc_body(seed_subject["id"], seed_kp["id"]), headers=h1)

        u2, p2, t2 = await _register_user(client, _rand("user2"))
        h2 = await _auth_headers(t2)
        resp = await client.get("/api/v1/ugc/status", headers=h2)
        assert resp.json()["total"] == 0

    async def test_admin_reject_then_status_rejected(self, client, registered_user, seed_subject, seed_kp, db_session):
        """人工终审 reject（M3.5 状态机）→ /ugc/status 显示 rejected + reject_reason（无 [AI: 前缀）。"""
        headers = _headers(registered_user)
        r = await client.post("/api/v1/ugc/upload", json=_ugc_body(seed_subject["id"], seed_kp["id"]), headers=headers)
        qid = r.json()["question_id"]

        # 提升当前用户为 admin（M3.5 审核流依赖 role=admin）
        username = registered_user[0]
        u = (await db_session.execute(select(User).where(User.username == username))).scalar_one()
        u.role = "admin"
        await db_session.commit()

        rev = await client.post(
            f"/api/v1/admin/questions/{qid}/review",
            json={"action": "reject", "reject_reason": "题干有歧义，请补充"},
            headers=headers,
        )
        assert rev.status_code == 200
        assert rev.json()["status"] == "rejected"

        resp = await client.get("/api/v1/ugc/status?status=rejected", headers=headers)
        data = resp.json()
        assert data["total"] == 1
        it = data["items"][0]
        assert it["status"] == "rejected"
        assert it["reject_reason"] == "题干有歧义，请补充"
        assert it["reviewed_at"] is not None

    async def test_content_truncated_to_50(self, client, registered_user, seed_subject, seed_kp):
        headers = _headers(registered_user)
        long_content = "题干内容" * 30  # 120 字
        await client.post(
            "/api/v1/ugc/upload",
            json=_ugc_body(seed_subject["id"], seed_kp["id"], content=long_content, options=None, answer=None),
            headers=headers,
        )
        resp = await client.get("/api/v1/ugc/status", headers=headers)
        it = resp.json()["items"][0]
        assert len(it["content"]) == 51  # 50 + 省略号
        assert it["content"].endswith("…")
