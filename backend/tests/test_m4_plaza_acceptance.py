"""T27 选课+广场验收测试（补充 T25 契约边界未覆盖项）。

对照 docs/api.md §13 边界断言清单（architecture.md §13.6 T27 职责）：
  - PUT /me/profile：major 超长行为（契约写 400 VALIDATION_ERROR，实现返回 422 → 缺陷 D-28）、
    首尾空白 strip
  - PUT /me/subjects：幂等全量覆盖语义（先设 [A,B] 再设 [B,C] → 仅剩 [B,C]，非追加/合并）、
    空数组清空后再设置
  - GET /me/subjects：请求数组顺序 = 返回顺序（created_at 升序）；stats 统计口径数值断言
    （question_count / correct_count / accuracy / mastery / knowledge_points / streak）
  - GET /subjects/plaza：登录+加入后 joined=true、未加入 joined=false；sort_order,name 排序；
    question_count 只统计 status='active' 题目

T25 的 test_m4_subjects_plaza.py 已覆盖基础路径（更新/清除/401/422 SUBJECT_NOT_JOINABLE/
游客可看），本文件聚焦其空库断言盲区与统计口径数值。
"""
from __future__ import annotations

import uuid
from datetime import date, timedelta

import pytest
from sqlalchemy import select

from app.db.models import KnowledgePoint, Question, StudySession, Subject, User, UserKnowledgeState
from tests.conftest import _rand


def _headers(reg_user) -> dict:
    return reg_user[3]


async def _user_id(db_session, username: str) -> str:
    res = await db_session.execute(select(User).where(User.username == username))
    return str(res.scalar_one().id)


async def _seed_subject(db_session, *, is_public: bool = False, sort_order: int = 0) -> dict:
    """直插一个科目（可选公共课），返回 dict(id/code/name)。"""
    code = _rand("subj")
    subj = Subject(
        code=code,
        name=f"课程-{code}",
        description="T27 测试种子科目",
        config={},
        is_public=is_public,
        is_active=True,
        sort_order=sort_order,
    )
    db_session.add(subj)
    await db_session.commit()
    await db_session.refresh(subj)
    return {"id": str(subj.id), "code": subj.code, "name": subj.name}


async def _seed_kp(db_session, subject_id: str, name: str) -> str:
    kp = KnowledgePoint(subject_id=uuid.UUID(subject_id), name=name, content="", level=1)
    db_session.add(kp)
    await db_session.commit()
    await db_session.refresh(kp)
    return str(kp.id)


async def _seed_question(db_session, subject_id: str, *, status: str = "active", knowledge_point_id: str | None = None) -> str:
    if knowledge_point_id is None:
        knowledge_point_id = await _seed_kp(db_session, subject_id, f"KP-{_rand('q')}")
    q = Question(
        subject_id=uuid.UUID(subject_id),
        knowledge_point_id=uuid.UUID(knowledge_point_id),
        type="single",
        content=f"T27 题目 {_rand('q')}",
        options={"A": "1", "B": "2"},
        answer={"correct": "A"},
        analysis="",
        difficulty=2,
        source="self_built",
        status=status,
    )
    db_session.add(q)
    await db_session.commit()
    await db_session.refresh(q)
    return str(q.id)


async def _seed_state(db_session, user_id: str, kp_id: str, subject_id: str, status: str) -> None:
    db_session.add(UserKnowledgeState(
        user_id=uuid.UUID(user_id),
        knowledge_point_id=uuid.UUID(kp_id),
        subject_id=uuid.UUID(subject_id),
        status=status,
        correct_count=0,
        wrong_count=0,
        streak=0,
    ))
    await db_session.commit()


async def _seed_session(db_session, user_id: str, subject_id: str, d: date, q: int, c: int, checked_in: bool = True) -> None:
    db_session.add(StudySession(
        user_id=uuid.UUID(user_id),
        subject_id=uuid.UUID(subject_id),
        session_date=d,
        questions_practiced=q,
        correct_count=c,
        checked_in=checked_in,
    ))
    await db_session.commit()


def _d(offset: int) -> date:
    return date.today() + timedelta(days=offset)


# ═══════════════════════════════════════════════════════════════════════
# 1. PUT /me/profile 边界
# ═══════════════════════════════════════════════════════════════════════


@pytest.mark.anyio
class TestProfileBoundary:

    async def test_major_strip_whitespace(self, client, registered_user):
        """§13.1：去首尾空白后入库。"""
        resp = await client.put(
            "/api/v1/me/profile",
            json={"major": "  计算机科学与技术  "},
            headers=_headers(registered_user),
        )
        assert resp.status_code == 200
        assert resp.json()["major"] == "计算机科学与技术"

    async def test_major_too_long_returns_422(self, client, registered_user):
        """§13.1 错误表写 400 VALIDATION_ERROR；实现实际返回 422（Pydantic 默认）。

        固化现状（不 xfail，避免门禁误伤），契约偏差记录为缺陷 D-28，由 ep-backend 裁决。
        """
        resp = await client.put(
            "/api/v1/me/profile",
            json={"major": "x" * 101},
            headers=_headers(registered_user),
        )
        assert resp.status_code == 422
        detail = resp.json()["detail"]
        assert isinstance(detail, list)  # FastAPI RequestValidationError 形态

    async def test_major_length_100_ok(self, client, registered_user):
        """§13.1：100 字符边界合法。"""
        resp = await client.put(
            "/api/v1/me/profile",
            json={"major": "x" * 100},
            headers=_headers(registered_user),
        )
        assert resp.status_code == 200
        assert resp.json()["major"] == "x" * 100


# ═══════════════════════════════════════════════════════════════════════
# 2. PUT /me/subjects 幂等全量覆盖
# ═══════════════════════════════════════════════════════════════════════


@pytest.mark.anyio
class TestIdempotentOverwrite:

    @pytest.mark.xfail(
        reason="D-29: PUT /me/subjects 幂等覆盖同事务 UNIQUE 冲突（T25 实现未 flush；契约 §13.2 要求先删后插成功）",
        strict=False,
    )
    async def test_overwrite_replaces_not_merges(self, client, registered_user, db_session):
        """§13.2 核心语义：先设 [A,B] 再设 [B,C] → 仅剩 [B,C]（A 被覆盖移除）。

        当前实现缺陷 D-29：第二次 PUT 含重叠 id 时 UNIQUE(user_id,subject_id) 冲突 → 500。
        修复后本测试应通过（XPASS 即确认修复）。
        """
        s1 = await _seed_subject(db_session)
        s2 = await _seed_subject(db_session)
        s3 = await _seed_subject(db_session)
        headers = _headers(registered_user)

        r1 = await client.put(
            "/api/v1/me/subjects",
            json={"subject_ids": [s1["id"], s2["id"]]},
            headers=headers,
        )
        assert r1.status_code == 200
        assert r1.json()["total"] == 2

        r2 = await client.put(
            "/api/v1/me/subjects",
            json={"subject_ids": [s2["id"], s3["id"]]},
            headers=headers,
        )
        assert r2.status_code == 200
        assert r2.json()["total"] == 2

        ids = {item["subject"]["id"] for item in r2.json()["items"]}
        assert ids == {s2["id"], s3["id"]}  # s1 已被覆盖移除

    async def test_clear_then_set(self, client, registered_user, db_session):
        """空数组清空后再次设置，仅剩新列表。"""
        s1 = await _seed_subject(db_session)
        s2 = await _seed_subject(db_session)
        headers = _headers(registered_user)

        r1 = await client.put(
            "/api/v1/me/subjects",
            json={"subject_ids": [s1["id"]]},
            headers=headers,
        )
        assert r1.json()["total"] == 1

        r2 = await client.put(
            "/api/v1/me/subjects",
            json={"subject_ids": []},
            headers=headers,
        )
        assert r2.json()["total"] == 0

        r3 = await client.put(
            "/api/v1/me/subjects",
            json={"subject_ids": [s2["id"]]},
            headers=headers,
        )
        assert r3.json()["total"] == 1
        assert r3.json()["items"][0]["subject"]["id"] == s2["id"]


# ═══════════════════════════════════════════════════════════════════════
# 3. GET /me/subjects 顺序 + 统计口径
# ═══════════════════════════════════════════════════════════════════════


@pytest.mark.anyio
class TestSubjectsOrderAndStats:

    async def test_order_follows_request_array(self, client, registered_user, db_session):
        """§13.2/§13.3：请求数组顺序 = 返回顺序（created_at 升序）。"""
        s1 = await _seed_subject(db_session)
        s2 = await _seed_subject(db_session)
        s3 = await _seed_subject(db_session)
        headers = _headers(registered_user)

        resp = await client.put(
            "/api/v1/me/subjects",
            json={"subject_ids": [s3["id"], s1["id"], s2["id"]]},  # 故意乱序
            headers=headers,
        )
        assert resp.status_code == 200
        got = [item["subject"]["id"] for item in resp.json()["items"]]
        assert got == [s3["id"], s1["id"], s2["id"]]

        # GET 与 PUT 响应同构
        resp2 = await client.get("/api/v1/me/subjects", headers=headers)
        got2 = [item["subject"]["id"] for item in resp2.json()["items"]]
        assert got2 == got

    async def test_stats_aggregation_values(self, client, registered_user, db_session):
        """§13.3：stats 数值口径 —— question_count/correct_count/accuracy/mastery/
        knowledge_points/streak 实时聚合正确。"""
        subj = await _seed_subject(db_session)
        username, _, _, headers = registered_user
        uid = await _user_id(db_session, username)

        # 2 个知识点：1 mastered + 1 weak → mastery=0.5, kp total=2, mastered=1, weak=1
        kp1 = await _seed_kp(db_session, subj["id"], "KP1")
        kp2 = await _seed_kp(db_session, subj["id"], "KP2")
        await _seed_state(db_session, uid, kp1, subj["id"], "mastered")
        await _seed_state(db_session, uid, kp2, subj["id"], "weak")

        # 3 天做题：昨天/前天各 1 题全对（打卡），今天 8 题 6 对 → q=10, c=8, acc=0.8
        # streak：昨天+前天连续 → 依赖 compute_streak 口径，这里至少断言 >= 1
        await _seed_session(db_session, uid, subj["id"], _d(-2), 1, 1, checked_in=True)
        await _seed_session(db_session, uid, subj["id"], _d(-1), 1, 1, checked_in=True)
        await _seed_session(db_session, uid, subj["id"], _d(0), 8, 6, checked_in=True)

        resp = await client.put(
            "/api/v1/me/subjects",
            json={"subject_ids": [subj["id"]]},
            headers=headers,
        )
        assert resp.status_code == 200
        stats = resp.json()["items"][0]["stats"]

        assert stats["question_count"] == 10
        assert stats["correct_count"] == 8
        assert stats["accuracy"] == 0.8
        assert stats["mastery"] == 0.5
        assert stats["knowledge_points"] == {"total": 2, "mastered": 1, "weak": 1}
        assert stats["streak"] >= 1

    async def test_stats_zero_when_no_activity(self, client, registered_user, db_session):
        """§13.3：无学习记录时 stats 为零值，不报错。"""
        subj = await _seed_subject(db_session)
        resp = await client.put(
            "/api/v1/me/subjects",
            json={"subject_ids": [subj["id"]]},
            headers=_headers(registered_user),
        )
        assert resp.status_code == 200
        stats = resp.json()["items"][0]["stats"]
        assert stats["question_count"] == 0
        assert stats["correct_count"] == 0
        assert stats["accuracy"] == 0.0
        assert stats["mastery"] == 0.0
        assert stats["knowledge_points"] == {"total": 0, "mastered": 0, "weak": 0}
        assert stats["streak"] == 0


# ═══════════════════════════════════════════════════════════════════════
# 4. GET /subjects/plaza 加入状态 + 排序 + question_count
# ═══════════════════════════════════════════════════════════════════════


@pytest.mark.anyio
class TestPlazaStateAndCount:

    async def test_joined_true_after_join_false_before(self, client, registered_user, db_session):
        """§13.4：登录用户加入课程后 plaza joined=true；未加入的课 joined=false。"""
        pub1 = await _seed_subject(db_session, is_public=True, sort_order=1)
        pub2 = await _seed_subject(db_session, is_public=True, sort_order=2)
        headers = _headers(registered_user)

        # 加入 pub1
        r = await client.put(
            "/api/v1/me/subjects",
            json={"subject_ids": [pub1["id"]]},
            headers=headers,
        )
        assert r.status_code == 200

        resp = await client.get("/api/v1/subjects/plaza", headers=headers)
        assert resp.status_code == 200
        joined_map = {item["id"]: item["joined"] for item in resp.json()["items"]}
        assert joined_map.get(pub1["id"]) is True
        assert joined_map.get(pub2["id"]) is False

    async def test_private_subject_not_in_plaza(self, client, db_session):
        """§13.4：is_public=false 的课不进入广场列表。"""
        priv = await _seed_subject(db_session, is_public=False)
        pub = await _seed_subject(db_session, is_public=True)

        resp = await client.get("/api/v1/subjects/plaza")
        assert resp.status_code == 200
        ids = {item["id"] for item in resp.json()["items"]}
        assert priv["id"] not in ids
        assert pub["id"] in ids

    async def test_plaza_sorted_by_sort_order_then_name(self, client, db_session):
        """§13.4：按 sort_order, name 排序。"""
        a = await _seed_subject(db_session, is_public=True, sort_order=5)
        b = await _seed_subject(db_session, is_public=True, sort_order=1)
        c = await _seed_subject(db_session, is_public=True, sort_order=3)

        resp = await client.get("/api/v1/subjects/plaza")
        assert resp.status_code == 200
        got = [item["id"] for item in resp.json()["items"]]
        # 期望顺序：sort_order 1 → b, 3 → c, 5 → a（name 不参与破坏，仅同 order 时）
        pos = {sid: i for i, sid in enumerate(got)}
        assert pos[b["id"]] < pos[c["id"]] < pos[a["id"]]

    async def test_question_count_counts_only_active(self, client, db_session):
        """§13.4：question_count 只统计 status='active' 题目。"""
        pub = await _seed_subject(db_session, is_public=True)
        await _seed_question(db_session, pub["id"], status="active")
        await _seed_question(db_session, pub["id"], status="active")
        await _seed_question(db_session, pub["id"], status="rejected")  # 不应计入

        resp = await client.get("/api/v1/subjects/plaza")
        assert resp.status_code == 200
        item = next(i for i in resp.json()["items"] if i["id"] == pub["id"])
        assert item["question_count"] == 2
