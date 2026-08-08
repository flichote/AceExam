"""M3.5 API 验收测试 — TTS / UGC / 班级 / 分享卡 / 班级排行榜。

验收点（docs/api.md §12）：
- UGC 投稿：content≥15 字预检、answer-type 校验、重复检测、幂等
- Admin 审核：role=admin 鉴权、approve/reject、已审禁止重审
- 班级：建班 invite_code 生成、加入班级、GET /me/class
- 分享卡：聚合数据非空、全零用户返回 0 值
- 排行榜 scope=class：班级过滤、未加入 422

Run: cd backend && PYTHONPATH="" .venv/Scripts/python.exe -m pytest tests/test_m35_api.py -v --tb=short -p no:warnings
"""
import uuid
from datetime import date, datetime, timezone, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.db.models import (
    Class,
    KnowledgePoint,
    Plan,
    Question,
    StudySession,
    Subject,
    User,
    UserKnowledgeState,
)
from tests.conftest import _rand

pytestmark = pytest.mark.anyio


def _d(offset: int) -> date:
    return date.today() + timedelta(days=offset)


async def _register(client, username: str | None = None, password: str = "pass123456") -> tuple[str, str]:
    username = username or _rand("user")
    resp = await client.post(
        "/api/v1/auth/register",
        json={"username": username, "password": password},
    )
    assert resp.status_code == 201, resp.text
    return username, resp.json()["access_token"]


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


async def _user_id(db, username: str) -> uuid.UUID:
    res = await db.execute(select(User).where(User.username == username))
    u = res.scalar_one()
    return u.id


async def _seed_subject(db, name: str = "高数") -> dict:
    s = Subject(code=_rand("subj"), name=name, description="", config={})
    db.add(s)
    await db.commit()
    await db.refresh(s)
    return {"id": str(s.id), "name": s.name}


async def _seed_kp(db, subj_id: str, name: str = "洛必达") -> dict:
    kp = KnowledgePoint(subject_id=uuid.UUID(subj_id), name=name, content="", level=3)
    db.add(kp)
    await db.commit()
    await db.refresh(kp)
    return {"id": str(kp.id), "name": kp.name}


async def _make_admin(db, username: str):
    res = await db.execute(select(User).where(User.username == username))
    u = res.scalar_one()
    u.role = "admin"
    await db.commit()


# ═══════════════════════════════════════════════════════════════════════
# 1. UGC 题目提交
# ═══════════════════════════════════════════════════════════════════════

class TestUGCSubmit:
    async def test_submit_ugc_question_creates_pending(
        self, client: AsyncClient, db_session, registered_user
    ):
        """提交 UGC 题 → 201 + status=pending。"""
        subj = await _seed_subject(db_session)
        kp = await _seed_kp(db_session, subj["id"])
        username, _, _, headers = registered_user

        resp = await client.post(
            "/api/v1/questions/ugc",
            json={
                "subject_id": subj["id"],
                "knowledge_point_id": kp["id"],
                "type": "single",
                "content": "这是一个至少十五个字的测试题干内容用于UGC投稿",
                "options": [{"key": "A", "text": "正确"}, {"key": "B", "text": "错误"}],
                "answer": "A",
                "analysis": "因为所以科学道理",
            },
            headers=headers,
        )
        assert resp.status_code == 201, resp.text
        data = resp.json()
        assert data["status"] == "pending"
        assert data["duplicated"] is False
        assert "question_id" in data

        # 验证库中状态
        qid = uuid.UUID(data["question_id"])
        res = await db_session.execute(select(Question).where(Question.id == qid))
        q = res.scalar_one()
        assert q.status == "pending"
        assert q.source == "ugc"

    async def test_submit_ugc_content_too_short(
        self, client: AsyncClient, db_session, registered_user
    ):
        """题干 <15 字 → 422。"""
        subj = await _seed_subject(db_session)
        kp = await _seed_kp(db_session, subj["id"])
        _, _, _, headers = registered_user

        resp = await client.post(
            "/api/v1/questions/ugc",
            json={
                "subject_id": subj["id"],
                "knowledge_point_id": kp["id"],
                "type": "single",
                "content": "太短",
                "options": [{"key": "A", "text": "A"}],
                "answer": "A",
            },
            headers=headers,
        )
        assert resp.status_code == 422, resp.text

    async def test_submit_ugc_duplicate_content(
        self, client: AsyncClient, db_session, registered_user
    ):
        """重复题干 → 409 DUPLICATE。"""
        subj = await _seed_subject(db_session)
        kp = await _seed_kp(db_session, subj["id"])
        username, _, _, headers = registered_user

        content = "这是一个至少十五个字的测试题干内容用于重复检测测试"
        # 第一投
        r1 = await client.post(
            "/api/v1/questions/ugc",
            json={
                "subject_id": subj["id"],
                "knowledge_point_id": kp["id"],
                "type": "single",
                "content": content,
                "options": [{"key": "A", "text": "A"}],
                "answer": "A",
            },
            headers=headers,
        )
        assert r1.status_code == 201

        # 第二投（同内容）
        r2 = await client.post(
            "/api/v1/questions/ugc",
            json={
                "subject_id": subj["id"],
                "knowledge_point_id": kp["id"],
                "type": "single",
                "content": content,
                "options": [{"key": "A", "text": "A"}],
                "answer": "A",
            },
            headers=headers,
        )
        assert r2.status_code == 409, r2.text


# ═══════════════════════════════════════════════════════════════════════
# 2. Admin 审核
# ═══════════════════════════════════════════════════════════════════════

class TestAdminReview:
    async def test_admin_approve_ugc(
        self, client: AsyncClient, db_session, registered_user
    ):
        """Admin approve → status=active。"""
        subj = await _seed_subject(db_session)
        kp = await _seed_kp(db_session, subj["id"])
        username, _, _, headers = registered_user

        # 提交 UGC
        resp = await client.post(
            "/api/v1/questions/ugc",
            json={
                "subject_id": subj["id"],
                "knowledge_point_id": kp["id"],
                "type": "single",
                "content": "这是一个至少十五个字的审核测试题干数据内容",
                "options": [{"key": "A", "text": "对"}],
                "answer": "A",
            },
            headers=headers,
        )
        qid = resp.json()["question_id"]

        # 提升为 admin
        await _make_admin(db_session, username)

        # 审核通过
        review_resp = await client.post(
            f"/api/v1/admin/questions/{qid}/review",
            json={"action": "approve"},
            headers=headers,
        )
        assert review_resp.status_code == 200, review_resp.text
        data = review_resp.json()
        assert data["status"] == "active"

    async def test_non_admin_review_rejected(
        self, client: AsyncClient, db_session, registered_user
    ):
        """非 admin 审核 → 403。"""
        subj = await _seed_subject(db_session)
        kp = await _seed_kp(db_session, subj["id"])
        _, _, _, headers = registered_user

        # 先手动插入一条 pending 题
        q = Question(
            subject_id=uuid.UUID(subj["id"]),
            knowledge_point_id=uuid.UUID(kp["id"]),
            type="single",
            content="手动插入的待审核题目用于测试非admin鉴权",
            options=[{"key": "A", "text": "A"}],
            answer="A",
            difficulty=3,
            source="ugc",
            status="pending",
        )
        db_session.add(q)
        await db_session.commit()
        qid = str(q.id)

        resp = await client.post(
            f"/api/v1/admin/questions/{qid}/review",
            json={"action": "approve"},
            headers=headers,
        )
        assert resp.status_code == 403, resp.text

    async def test_admin_review_list(
        self, client: AsyncClient, db_session, registered_user
    ):
        """GET /admin/questions/ugc 返回待审列表。"""
        subj = await _seed_subject(db_session)
        kp = await _seed_kp(db_session, subj["id"])
        username, _, _, headers = registered_user
        await _make_admin(db_session, username)

        # 插入两条 pending
        for i in range(2):
            q = Question(
                subject_id=uuid.UUID(subj["id"]),
                knowledge_point_id=uuid.UUID(kp["id"]),
                type="single",
                content=f"待审核题目 #{i} 用于测试审核列表数据",
                options=[{"key": "A", "text": "A"}],
                answer="A",
                difficulty=3,
                source="ugc",
                status="pending",
            )
            db_session.add(q)
        await db_session.commit()

        resp = await client.get(
            "/api/v1/admin/questions/ugc?status=pending",
            headers=headers,
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["total"] == 2
        assert len(data["items"]) == 2

    async def test_reject_requires_reason(
        self, client: AsyncClient, db_session, registered_user
    ):
        """reject 不传 reject_reason → 422。"""
        subj = await _seed_subject(db_session)
        kp = await _seed_kp(db_session, subj["id"])
        username, _, _, headers = registered_user
        await _make_admin(db_session, username)

        q = Question(
            subject_id=uuid.UUID(subj["id"]),
            knowledge_point_id=uuid.UUID(kp["id"]),
            type="single",
            content="待审核拒绝的题目内容用于测试缺省拒绝原因",
            options=[{"key": "A", "text": "A"}],
            answer="A",
            difficulty=3,
            source="ugc",
            status="pending",
        )
        db_session.add(q)
        await db_session.commit()
        qid = str(q.id)

        resp = await client.post(
            f"/api/v1/admin/questions/{qid}/review",
            json={"action": "reject"},
            headers=headers,
        )
        assert resp.status_code == 422, resp.text

    async def test_admin_reject_sets_status_and_reason(
        self, client: AsyncClient, db_session, registered_user
    ):
        """reject 带原因 → status=rejected + reject_reason 落库。"""
        subj = await _seed_subject(db_session)
        kp = await _seed_kp(db_session, subj["id"])
        username, _, _, headers = registered_user
        await _make_admin(db_session, username)

        # 通过 API 投稿
        r = await client.post(
            "/api/v1/questions/ugc",
            json={
                "subject_id": subj["id"],
                "knowledge_point_id": kp["id"],
                "type": "single",
                "content": "这是一道将被管理员拒绝的投稿题目内容测试",
                "options": [{"key": "A", "text": "A"}],
                "answer": "A",
            },
            headers=headers,
        )
        qid = r.json()["question_id"]

        resp = await client.post(
            f"/api/v1/admin/questions/{qid}/review",
            json={"action": "reject", "reject_reason": "题目不完整，缺少解析"},
            headers=headers,
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["status"] == "rejected"

        # DB 校验
        res = await db_session.execute(select(Question).where(Question.id == uuid.UUID(qid)))
        q = res.scalar_one()
        assert q.status == "rejected"
        assert q.reject_reason == "题目不完整，缺少解析"

    async def test_review_after_reviewed_conflict(
        self, client: AsyncClient, db_session, registered_user
    ):
        """已审（approve 或 reject）后再审 → 409 Already reviewed。"""
        subj = await _seed_subject(db_session)
        kp = await _seed_kp(db_session, subj["id"])
        username, _, _, headers = registered_user
        await _make_admin(db_session, username)

        q = Question(
            subject_id=uuid.UUID(subj["id"]),
            knowledge_point_id=uuid.UUID(kp["id"]),
            type="single",
            content="已经审核过的题目内容用于测试重复审核冲突",
            options=[{"key": "A", "text": "A"}],
            answer="A",
            difficulty=3,
            source="ugc",
            status="active",
        )
        db_session.add(q)
        await db_session.commit()
        qid = str(q.id)

        resp = await client.post(
            f"/api/v1/admin/questions/{qid}/review",
            json={"action": "reject", "reject_reason": "重复审核请求"},
            headers=headers,
        )
        assert resp.status_code == 409, resp.text

    async def test_review_non_ugc_question_422(
        self, client: AsyncClient, db_session, registered_user
    ):
        """非 UGC source 的题目不可走审核 → 422。"""
        subj = await _seed_subject(db_session)
        kp = await _seed_kp(db_session, subj["id"])
        username, _, _, headers = registered_user
        await _make_admin(db_session, username)

        q = Question(
            subject_id=uuid.UUID(subj["id"]),
            knowledge_point_id=uuid.UUID(kp["id"]),
            type="single",
            content="系统自建题目内容用于测试非UGC审核拦截",
            options=[{"key": "A", "text": "A"}],
            answer="A",
            difficulty=3,
            source="self_built",
            status="active",
        )
        db_session.add(q)
        await db_session.commit()
        qid = str(q.id)

        resp = await client.post(
            f"/api/v1/admin/questions/{qid}/review",
            json={"action": "approve"},
            headers=headers,
        )
        assert resp.status_code == 422, resp.text

    async def test_review_missing_question_404(
        self, client: AsyncClient, db_session, registered_user
    ):
        """审核不存在的题目 → 404。"""
        username, _, _, headers = registered_user
        await _make_admin(db_session, username)

        resp = await client.post(
            f"/api/v1/admin/questions/{uuid.uuid4()}/review",
            json={"action": "approve"},
            headers=headers,
        )
        assert resp.status_code == 404, resp.text

    async def test_review_list_requires_admin(
        self, client: AsyncClient, db_session, registered_user
    ):
        """非 admin 访问审核列表 → 403。"""
        _, _, _, headers = registered_user
        resp = await client.get(
            "/api/v1/admin/questions/ugc?status=pending",
            headers=headers,
        )
        assert resp.status_code == 403, resp.text

    async def test_review_list_filters_by_status(
        self, client: AsyncClient, db_session, registered_user
    ):
        """status 过滤：rejected 列表只含 rejected，pending 不混入。"""
        subj = await _seed_subject(db_session)
        kp = await _seed_kp(db_session, subj["id"])
        username, _, _, headers = registered_user
        await _make_admin(db_session, username)

        for i, st in enumerate(["pending", "rejected"]):
            db_session.add(Question(
                subject_id=uuid.UUID(subj["id"]),
                knowledge_point_id=uuid.UUID(kp["id"]),
                type="single",
                content=f"状态过滤题目 #{i} 用于验证列表状态过滤逻辑",
                options=[{"key": "A", "text": "A"}],
                answer="A",
                difficulty=3,
                source="ugc",
                status=st,
            ))
        await db_session.commit()

        resp = await client.get(
            "/api/v1/admin/questions/ugc?status=rejected",
            headers=headers,
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["total"] == 1
        assert all(it["status"] == "rejected" for it in data["items"])


# ═══════════════════════════════════════════════════════════════════════
# 3. 班级
# ═══════════════════════════════════════════════════════════════════════

class TestClassroom:
    async def test_create_class(
        self, client: AsyncClient, db_session, registered_user
    ):
        """建班 → 200 + invite_code 6位。"""
        username, _, _, headers = registered_user

        resp = await client.post(
            "/api/v1/me/class",
            json={"name": "计科2301"},
            headers=headers,
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        cls_info = data["class"]
        assert cls_info["name"] == "计科2301"
        assert len(cls_info["invite_code"]) == 6
        assert cls_info["is_creator"] is True

    async def test_join_class_by_invite(
        self, client: AsyncClient, db_session, registered_user
    ):
        """邀请码加入 → 200 + joined=true。"""
        username_a, _, _, _ = registered_user
        # 用户 A 建班
        uid_a = await _user_id(db_session, username_a)
        cls = Class(name="测试班", invite_code="ABC123", created_by=uid_a)
        db_session.add(cls)
        await db_session.commit()

        # 用户 B 加入
        uname_b, token_b = await _register(client, _rand("joiner"))
        resp = await client.post(
            "/api/v1/me/class",
            json={"invite_code": "ABC123"},
            headers=_auth(token_b),
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["joined"] is True
        assert data["class"]["name"] == "测试班"
        assert data["class"]["invite_code"] is None  # 加入者不返回 invite_code

    async def test_get_my_class(
        self, client: AsyncClient, db_session, registered_user
    ):
        """GET /me/class 返回我的班级。"""
        username, _, _, headers = registered_user
        uid = await _user_id(db_session, username)
        cls = Class(name="计科2301", invite_code="XYZ999", created_by=uid)
        db_session.add(cls)
        await db_session.flush()
        # 将用户加入班级
        user_res = await db_session.execute(select(User).where(User.id == uid))
        u = user_res.scalar_one()
        u.class_id = cls.id
        await db_session.commit()

        resp = await client.get("/api/v1/me/class", headers=headers)
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["class"]["name"] == "计科2301"
        assert data["class"]["member_count"] == 1

    async def test_get_my_class_not_joined(
        self, client: AsyncClient, registered_user
    ):
        """未加入班级 → class=null。"""
        _, _, _, headers = registered_user
        resp = await client.get("/api/v1/me/class", headers=headers)
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["class"] is None
        assert data["my_rank"] is None

    async def test_class_both_name_and_invite_422(
        self, client: AsyncClient, registered_user
    ):
        """name 与 invite_code 同时提供 → 422。"""
        _, _, _, headers = registered_user
        resp = await client.post(
            "/api/v1/me/class",
            json={"name": "计科2301", "invite_code": "ABC123"},
            headers=headers,
        )
        assert resp.status_code == 422, resp.text

    async def test_class_neither_422(
        self, client: AsyncClient, registered_user
    ):
        """name 与 invite_code 都缺省 → 422。"""
        _, _, _, headers = registered_user
        resp = await client.post(
            "/api/v1/me/class",
            json={},
            headers=headers,
        )
        assert resp.status_code == 422, resp.text

    async def test_join_class_invalid_invite_404(
        self, client: AsyncClient, registered_user
    ):
        """无效邀请码 → 404。"""
        _, _, _, headers = registered_user
        resp = await client.post(
            "/api/v1/me/class",
            json={"invite_code": "NOPE99"},
            headers=headers,
        )
        assert resp.status_code == 404, resp.text


# ═══════════════════════════════════════════════════════════════════════
# 4. 分享卡
# ═══════════════════════════════════════════════════════════════════════

class TestShareCard:
    async def test_share_card_returns_aggregated_data(
        self, client: AsyncClient, db_session, registered_user
    ):
        """分享卡返回聚合数据（全零用户也能返回 0 值）。"""
        _, _, _, headers = registered_user

        resp = await client.get("/api/v1/me/share-card", headers=headers)
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["share_card_version"] == 1
        assert data["totals"]["questions_practiced"] == 0
        assert data["totals"]["correct_count"] == 0
        assert data["streak"]["current"] == 0
        assert data["mastery"]["overall_pct"] == 0.0

    async def test_share_card_with_data(
        self, client: AsyncClient, db_session, registered_user
    ):
        """有做题记录时分享卡聚合正确。"""
        username, _, _, headers = registered_user
        subj = await _seed_subject(db_session)
        uid = await _user_id(db_session, username)

        # 插入做题记录
        today = datetime.now(timezone.utc).date()
        db_session.add(StudySession(
            user_id=uid, subject_id=uuid.UUID(subj["id"]),
            session_date=today, questions_practiced=50, correct_count=40,
            checked_in=True,
        ))
        await db_session.commit()

        resp = await client.get("/api/v1/me/share-card", headers=headers)
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["totals"]["questions_practiced"] == 50
        assert data["totals"]["correct_count"] == 40
        assert data["totals"]["accuracy"] == 0.8
        assert data["recent_7d"]["questions_practiced"] == 50

    async def test_share_card_streak_only(
        self, client: AsyncClient, db_session, registered_user
    ):
        """连胜聚合：3 天连续打卡 → current=3, longest=3（不触发 mastery 分支）。"""
        username, _, _, headers = registered_user
        subj = await _seed_subject(db_session, "高数")
        uid = await _user_id(db_session, username)

        # 3 天连续打卡（今天、昨天、前天）→ current=3, longest=3
        for offset in (0, -1, -2):
            db_session.add(StudySession(
                user_id=uid, subject_id=uuid.UUID(subj["id"]),
                session_date=_d(offset), questions_practiced=10, correct_count=8,
                checked_in=True,
            ))
        await db_session.commit()

        resp = await client.get("/api/v1/me/share-card", headers=headers)
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["totals"]["questions_practiced"] == 30
        assert data["totals"]["correct_count"] == 24
        assert data["totals"]["accuracy"] == 0.8
        assert data["streak"]["current"] == 3
        assert data["streak"]["longest"] == 3

    @pytest.mark.xfail(reason="D-26 me.py 未导入 Subject（best_subject 段同样用 Subject 而非 _Subject）", strict=False)
    async def test_share_card_mastery_and_weak(
        self, client: AsyncClient, db_session, registered_user
    ):
        """D-26 固化：掌握度 overall_pct / best_subject / weak_points 聚合正确（200）。

        实际：只要有 UserKnowledgeState 数据，best_subject 段 `select(Subject.name)`
        NameError → 500（me.py line 236 用 Subject，局部 import 的是 _Subject）。
        修复后此用例应 200 且各字段正确。
        """
        username, _, _, headers = registered_user
        subj1 = await _seed_subject(db_session, "高数")
        kp1 = await _seed_kp(db_session, subj1["id"], "洛必达")
        subj2 = await _seed_subject(db_session, "线代")
        kp2 = await _seed_kp(db_session, subj2["id"], "矩阵")
        kp3 = await _seed_kp(db_session, subj2["id"], "特征值")
        uid = await _user_id(db_session, username)

        # user_knowledge_states 有 (user_id, knowledge_point_id) 唯一约束，kp 必须互异
        db_session.add(UserKnowledgeState(
            user_id=uid, knowledge_point_id=uuid.UUID(kp1["id"]),
            subject_id=uuid.UUID(subj1["id"]), status="mastered",
            correct_count=5, wrong_count=1, streak=3,
        ))
        db_session.add(UserKnowledgeState(
            user_id=uid, knowledge_point_id=uuid.UUID(kp2["id"]),
            subject_id=uuid.UUID(subj2["id"]), status="weak",
            correct_count=1, wrong_count=5, streak=0,
        ))
        db_session.add(UserKnowledgeState(
            user_id=uid, knowledge_point_id=uuid.UUID(kp3["id"]),
            subject_id=uuid.UUID(subj2["id"]), status="consolidating",
            correct_count=2, wrong_count=2, streak=1,
        ))
        await db_session.commit()

        resp = await client.get("/api/v1/me/share-card", headers=headers)
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["mastery"]["overall_pct"] == pytest.approx(1 / 3, abs=0.001)
        # best_subject：高数 mastered 1/1=1.0，线代 0/2=0 → 取高数
        assert data["mastery"]["best_subject"]["subject_name"] == "高数"
        assert data["mastery"]["best_subject"]["mastery_pct"] == 1.0
        assert data["weak_points"]["weak"] == 1
        assert data["weak_points"]["consolidating"] == 1

    async def test_share_card_recent_7d_window(
        self, client: AsyncClient, db_session, registered_user
    ):
        """recent_7d 只统计近 7 天；8 天前的记录只进 totals。"""
        username, _, _, headers = registered_user
        subj = await _seed_subject(db_session)
        uid = await _user_id(db_session, username)

        db_session.add(StudySession(
            user_id=uid, subject_id=uuid.UUID(subj["id"]),
            session_date=_d(0), questions_practiced=20, correct_count=10,
            checked_in=True,
        ))
        db_session.add(StudySession(
            user_id=uid, subject_id=uuid.UUID(subj["id"]),
            session_date=_d(-8), questions_practiced=100, correct_count=50,
            checked_in=True,
        ))
        await db_session.commit()

        resp = await client.get("/api/v1/me/share-card", headers=headers)
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["totals"]["questions_practiced"] == 120
        assert data["totals"]["correct_count"] == 60
        assert data["recent_7d"]["questions_practiced"] == 20
        assert data["recent_7d"]["correct_count"] == 10

    async def test_share_card_class_field(
        self, client: AsyncClient, db_session, registered_user
    ):
        """有班级 → class 字段（按实现字段名 class_，见 D-27）；无 plan 时 exam null。"""
        username, _, _, headers = registered_user
        uid = await _user_id(db_session, username)

        cls = Class(name="计科2301", invite_code="CLS002", created_by=uid)
        db_session.add(cls)
        await db_session.flush()
        u = (await db_session.execute(select(User).where(User.id == uid))).scalar_one()
        u.class_id = cls.id
        await db_session.commit()

        resp = await client.get("/api/v1/me/share-card", headers=headers)
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["class_"]["name"] == "计科2301"
        assert data["exam"] is None

        # 无班级/无计划用户 → class_ null + exam null
        uname2, token2 = await _register(client, _rand("noplan"))
        r2 = await client.get(
            "/api/v1/me/share-card", headers=_auth(token2)
        )
        assert r2.status_code == 200, r2.text
        assert r2.json()["exam"] is None
        assert r2.json()["class_"] is None

    @pytest.mark.xfail(reason="D-27 share-card 班级字段名为 class_ 而非契约/前端消费的 class", strict=False)
    async def test_share_card_class_field_contract(
        self, client: AsyncClient, db_session, registered_user
    ):
        """D-27 固化：§12.8 契约与前端 SharePoster.vue 消费 `class` 字段。

        实际：schema ShareCardResponse.class_ 无 alias，序列化输出 `class_`；
        前端 `d.class` 恒 undefined → 海报班级区块永不显示。修复后应为 `class`。
        """
        username, _, _, headers = registered_user
        uid = await _user_id(db_session, username)

        cls = Class(name="计科2301", invite_code="CLS002", created_by=uid)
        db_session.add(cls)
        await db_session.flush()
        u = (await db_session.execute(select(User).where(User.id == uid))).scalar_one()
        u.class_id = cls.id
        await db_session.commit()

        resp = await client.get("/api/v1/me/share-card", headers=headers)
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["class"]["name"] == "计科2301"

    @pytest.mark.xfail(reason="D-26 me.py 未导入 Subject，share-card 含 exam_date 计划时 500", strict=False)
    async def test_share_card_exam_days_left(
        self, client: AsyncClient, db_session, registered_user
    ):
        """D-26 固化：有 active 计划（exam_date 非空）→ exam 倒计时正确（200）。

        实际：me.py line 274 `select(Subject.name)` NameError → 500（模块顶部未导入 Subject，
        仅 best_subject 段局部 import 为 _Subject）。修复后此用例应 200 且 days_left 正确。
        """
        username, _, _, headers = registered_user
        subj = await _seed_subject(db_session, "高数")
        uid = await _user_id(db_session, username)

        db_session.add(Plan(
            user_id=uid, subject_id=uuid.UUID(subj["id"]),
            title="期末冲刺", exam_date=_d(7), status="active",
            config={},
        ))
        await db_session.commit()

        resp = await client.get("/api/v1/me/share-card", headers=headers)
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["exam"]["subject_name"] == "高数"
        assert data["exam"]["days_left"] == 7


# ═══════════════════════════════════════════════════════════════════════
# 5. 排行榜 scope=class
# ═══════════════════════════════════════════════════════════════════════

class TestLeaderboardClassScope:
    async def test_class_scope_not_joined(
        self, client: AsyncClient, registered_user
    ):
        """未加入班级 → 422 CLASS_NOT_JOINED。"""
        _, _, _, headers = registered_user
        resp = await client.get("/api/v1/leaderboard?scope=class", headers=headers)
        assert resp.status_code == 422, resp.text

    async def test_class_scope_returns_class_members(
        self, client: AsyncClient, db_session, registered_user
    ):
        """scope=class 只返回同班成员。"""
        subj = await _seed_subject(db_session)
        # 用户 A 建班
        username_a, _, _, headers = registered_user
        uid_a = await _user_id(db_session, username_a)
        cls = Class(name="计科2301", invite_code="CLS001", created_by=uid_a)
        db_session.add(cls)
        await db_session.flush()

        # A 加入班级
        user_a = await db_session.execute(select(User).where(User.id == uid_a))
        ua = user_a.scalar_one()
        ua.class_id = cls.id

        # B: 直接通过 db_session 创建用户并加入同班（避免 API 调用的 SQLite 锁）
        import uuid as _uuid
        from app.core.security import hash_password
        uid_b = _uuid.uuid4()
        uname_b = _rand("cls_b")
        db_session.add(User(
            id=uid_b,
            username=uname_b,
            password_hash=hash_password("pass123456"),
            role="student",
            class_id=cls.id,
        ))

        # C: 注册但未加入班级
        uid_c = _uuid.uuid4()
        uname_c = _rand("cls_c")
        db_session.add(User(
            id=uid_c,
            username=uname_c,
            password_hash=hash_password("pass123456"),
            role="student",
        ))
        await db_session.commit()

        # A 做题
        db_session.add(StudySession(
            user_id=uid_a, subject_id=uuid.UUID(subj["id"]),
            session_date=_d(-3), questions_practiced=50, correct_count=40,
            checked_in=True,
        ))
        # B 做题
        db_session.add(StudySession(
            user_id=uid_b, subject_id=uuid.UUID(subj["id"]),
            session_date=_d(-3), questions_practiced=40, correct_count=30,
            checked_in=True,
        ))
        # C 做题（不应出现在班榜中）
        db_session.add(StudySession(
            user_id=uid_c, subject_id=uuid.UUID(subj["id"]),
            session_date=_d(-3), questions_practiced=100, correct_count=80,
            checked_in=True,
        ))
        await db_session.commit()

        resp = await client.get("/api/v1/leaderboard?scope=class", headers=headers)
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["scope"] == "class"
        assert data["class_"]["name"] == "计科2301"
        # 只应包含 A 和 B（同班）
        assert data["total"] == 2
        usernames_in_board = {it["username"] for it in data["items"]}
        assert username_a in usernames_in_board
        assert uname_b in usernames_in_board
        assert uname_c not in usernames_in_board

    async def test_class_scope_with_subject_filter(
        self, client: AsyncClient, db_session, registered_user
    ):
        """scope=class + subject_id → 班内且限定科目的聚合。"""
        subj1 = await _seed_subject(db_session, "高数")
        subj2 = await _seed_subject(db_session, "线代")
        username_a, _, _, headers = registered_user
        uid_a = await _user_id(db_session, username_a)
        cls = Class(name="计科2301", invite_code="CLS003", created_by=uid_a)
        db_session.add(cls)
        await db_session.flush()
        ua = (await db_session.execute(select(User).where(User.id == uid_a))).scalar_one()
        ua.class_id = cls.id

        # A：高数 60 题 48 对，线代 200 题 180 对（study_sessions 有 user+date 唯一约束，须错开日期）
        db_session.add(StudySession(
            user_id=uid_a, subject_id=uuid.UUID(subj1["id"]),
            session_date=_d(-3), questions_practiced=60, correct_count=48,
            checked_in=True,
        ))
        db_session.add(StudySession(
            user_id=uid_a, subject_id=uuid.UUID(subj2["id"]),
            session_date=_d(-4), questions_practiced=200, correct_count=180,
            checked_in=True,
        ))
        await db_session.commit()

        resp = await client.get(
            f"/api/v1/leaderboard?scope=class&subject_id={subj1['id']}",
            headers=headers,
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["scope"] == "class"
        assert data["total"] == 1
        item = data["items"][0]
        assert item["username"] == username_a
        assert item["questions_practiced"] == 60  # 只聚合高数
        assert item["total_correct"] == 48
        assert item["accuracy"] == 0.8
