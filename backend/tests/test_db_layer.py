"""数据库层测试 — 独立测试库建表 / 种子 / 清理 / 知识点状态机约束 / 幂等性。

验收点：
- conftest 用独立测试库（SQLite test_aceexam.db 或 TEST_DATABASE_URL 指定 PG）
- 建表成功：核心业务表存在
- 种子数据可查询
- 测试后清理：reset_db drop_all 后表不存在
- 知识点状态机：status 枚举（untouched/consolidating/mastered/weak）由 CheckConstraint 强制
- 幂等性：唯一约束防重复（用户、科目 code）
"""
import uuid

import pytest
from sqlalchemy import inspect, select, text

from app.db.base import Base
from app.db.models import (
    AIExplanation,
    ChatSession,
    DocumentChunk,
    KnowledgePoint,
    Plan,
    Question,
    QuestionEmbedding,
    StudySession,
    Subject,
    TokenUsage,
    User,
    UserKnowledgeState,
    WrongAnswer,
)
from app.core.security import hash_password


async def _table_names(engine) -> set[str]:
    """AsyncEngine 上跑 inspect（SQLAlchemy 不支持直接 inspect(AsyncEngine)）。"""

    def _get(conn):
        return set(inspect(conn).get_table_names())

    async with engine.connect() as conn:
        return await conn.run_sync(_get)


class TestSchemaCreated:
    async def test_all_tables_created(self, db_session):
        """建表：M1 全部业务表都应存在。"""
        tables = await _table_names(db_session.bind)
        expected = {
            "users",
            "subjects",
            "knowledge_points",
            "questions",
            "question_embeddings",
            "document_chunks",
            "wrong_answers",
            "user_knowledge_states",
            "plans",
            "study_sessions",
            "ai_explanations",
            "chat_sessions",
            "token_usage",
        }
        missing = expected - tables
        assert not missing, f"缺少表: {missing}"

    async def test_users_unique_username(self, db_session):
        """幂等性（DB 层）：username 唯一约束。"""
        u1 = User(username="dup_user", password_hash=hash_password("x123456"))
        db_session.add(u1)
        await db_session.commit()

        u2 = User(username="dup_user", password_hash=hash_password("y123456"))
        db_session.add(u2)
        with pytest.raises(Exception) as exc:
            await db_session.commit()
        assert "unique" in str(exc.value).lower() or "integrity" in str(exc.value).lower()

    async def test_subject_code_unique(self, db_session):
        s1 = Subject(code="dup_subj", name="A")
        db_session.add(s1)
        await db_session.commit()
        s2 = Subject(code="dup_subj", name="B")
        db_session.add(s2)
        with pytest.raises(Exception) as exc:
            await db_session.commit()
        assert "unique" in str(exc.value).lower() or "integrity" in str(exc.value).lower()


class TestSeed:
    async def test_seed_subject_visible(self, db_session, seed_subject):
        result = await db_session.execute(
            select(Subject).where(Subject.id == uuid.UUID(seed_subject["id"]))
        )
        subject = result.scalar_one()
        assert subject.name == "高等数学(测试)"

    async def test_seed_kp_linked_to_subject(self, db_session, seed_kp):
        result = await db_session.execute(
            select(KnowledgePoint).where(KnowledgePoint.id == uuid.UUID(seed_kp["id"]))
        )
        kp = result.scalar_one()
        assert str(kp.subject_id) == seed_kp["subject_id"]

    async def test_seed_question_with_answer(self, db_session, seed_question):
        result = await db_session.execute(
            select(Question).where(Question.id == uuid.UUID(seed_question["id"]))
        )
        q = result.scalar_one()
        assert q.answer == {"correct": "A"}


class TestCleanup:
    async def test_reset_db_cleans_tables(self, db_session, seed_subject, test_engine):
        """测试后 reset_db 清理：下一个用例的 db_session 是全新 schema。"""
        # 本用例内能看到种子
        result = await db_session.execute(select(Subject))
        assert len(result.scalars().all()) >= 1
        # 手动 drop_all 验证清理路径
        async with test_engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
        tables = await _table_names(test_engine)
        assert "subjects" not in tables


class TestKnowledgeStateMachine:
    """知识点状态机约束：status ∈ (untouched, consolidating, mastered, weak)。"""

    async def test_valid_statuses_accepted(self, db_session, seed_kp):
        u = User(username="state_user", password_hash=hash_password("pass123456"))
        db_session.add(u)
        await db_session.commit()
        for status in ("untouched", "consolidating", "mastered", "weak"):
            st = UserKnowledgeState(
                user_id=u.id,
                knowledge_point_id=uuid.UUID(seed_kp["id"]),
                subject_id=uuid.UUID(seed_kp["subject_id"]),
                status=status,
            )
            db_session.add(st)
            await db_session.commit()
            await db_session.delete(st)
            await db_session.commit()

    async def test_invalid_status_rejected(self, db_session, seed_kp):
        u = User(username="state_user2", password_hash=hash_password("pass123456"))
        db_session.add(u)
        await db_session.commit()
        st = UserKnowledgeState(
            user_id=u.id,
            knowledge_point_id=uuid.UUID(seed_kp["id"]),
            subject_id=uuid.UUID(seed_kp["subject_id"]),
            status="unknown_status",
        )
        db_session.add(st)
        with pytest.raises(Exception):
            await db_session.commit()
        await db_session.rollback()

    async def test_state_unique_per_user_kp(self, db_session, seed_kp):
        """幂等性：user+knowledge_point 唯一。"""
        u = User(username="state_user3", password_hash=hash_password("pass123456"))
        db_session.add(u)
        await db_session.commit()
        await db_session.refresh(u)
        uid = u.id  # rollback 后属性会过期，先保存主键
        kpid = uuid.UUID(seed_kp["id"])
        subj_id = uuid.UUID(seed_kp["subject_id"])
        for _ in range(2):
            st = UserKnowledgeState(
                user_id=uid,
                knowledge_point_id=kpid,
                subject_id=subj_id,
                status="mastered",
            )
            db_session.add(st)
            try:
                await db_session.commit()
            except Exception:
                await db_session.rollback()
        # 唯一约束 → 只有 1 条
        result = await db_session.execute(
            select(UserKnowledgeState).where(
                UserKnowledgeState.user_id == uid,
                UserKnowledgeState.knowledge_point_id == kpid,
            )
        )
        assert len(result.scalars().all()) == 1


class TestWrongAnswerIdempotentDb:
    async def test_unique_user_question(self, db_session, seed_question):
        """幂等性：错题本 user+question 唯一（DB 约束兜底）。"""
        u = User(username="wa_user", password_hash=hash_password("pass123456"))
        db_session.add(u)
        await db_session.commit()
        await db_session.refresh(u)
        uid = u.id
        qid = uuid.UUID(seed_question["id"])
        sid = uuid.UUID(seed_question["subject_id"])
        for _ in range(2):
            wa = WrongAnswer(
                user_id=uid,
                question_id=qid,
                subject_id=sid,
            )
            db_session.add(wa)
            try:
                await db_session.commit()
            except Exception:
                await db_session.rollback()
        result = await db_session.execute(
            select(WrongAnswer).where(
                WrongAnswer.user_id == uid,
                WrongAnswer.question_id == qid,
            )
        )
        assert len(result.scalars().all()) == 1
