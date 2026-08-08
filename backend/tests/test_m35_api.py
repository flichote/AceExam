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

from app.db.models import Class, KnowledgePoint, Question, StudySession, Subject, User
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
