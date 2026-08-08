"""SQLAlchemy 2.x ORM models — AceExam M1 全部表 + M2 增量表（ep-db 交付，供 alembic env + seed 使用）。

表结构事实来源：docs/database.md（ep-arch 评审后锁定；M2 增量见 §8）。
本模块与 backend/app/models/models.py（ep-backend 骨架）同用 app.db.base.Base；
若两模块被同一进程同时 import 会出现表名重复注册，FastAPI 侧请以本模块为准或合并。
"""
import uuid
from datetime import date, datetime, timezone

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint("role IN ('student','admin')", name="ck_users_role"),
        UniqueConstraint("username", name="uq_users_username"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    username: Mapped[str] = mapped_column(String(50), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(20), nullable=False, default="student")
    is_member: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    member_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    class_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("classes.id", use_alter=True), nullable=True, index=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow)


class Subject(Base):
    __tablename__ = "subjects"
    __table_args__ = (UniqueConstraint("code", name="uq_subjects_code"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    code: Mapped[str] = mapped_column(String(50), nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    config: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow)


class KnowledgePoint(Base):
    __tablename__ = "knowledge_points"
    __table_args__ = (
        CheckConstraint("level BETWEEN 1 AND 3", name="ck_kp_level"),
        UniqueConstraint("subject_id", "parent_id", "name", name="uq_kp_subject_parent_name"),
        Index("ix_kp_subject_parent", "subject_id", "parent_id"),
        Index("ix_kp_subject_level", "subject_id", "level"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    subject_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("subjects.id"), nullable=False)
    parent_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("knowledge_points.id"), nullable=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    content: Mapped[str | None] = mapped_column(Text, nullable=True)
    level: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=1)  # 1=章 2=节 3=知识点
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow)


class Question(Base):
    __tablename__ = "questions"
    __table_args__ = (
        CheckConstraint("difficulty BETWEEN 1 AND 5", name="ck_questions_difficulty"),
        CheckConstraint(
            "source IN ('textbook','past_exam','self_built','ugc')", name="ck_questions_source"
        ),
        CheckConstraint("status IN ('draft','pending','active','rejected','archived')", name="ck_questions_status"),
        Index("ix_questions_subject_kp_diff", "subject_id", "knowledge_point_id", "difficulty"),
        Index("ix_questions_subject_status", "subject_id", "status"),
        Index("ix_questions_status_created", "status", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    subject_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("subjects.id"), nullable=False)
    knowledge_point_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("knowledge_points.id"), nullable=False)
    type: Mapped[str] = mapped_column(String(20), nullable=False)  # single/multi/blank/essay/...
    content: Mapped[str] = mapped_column(Text, nullable=False)
    options: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    answer: Mapped[dict | str | list] = mapped_column(JSONB, nullable=False)
    analysis: Mapped[str | None] = mapped_column(Text, nullable=True)
    difficulty: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=3)
    source: Mapped[str] = mapped_column(String(20), nullable=False, default="self_built")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")
    submitted_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    reviewed_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    reject_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow)


class QuestionEmbedding(Base):
    __tablename__ = "question_embeddings"
    __table_args__ = (
        UniqueConstraint("question_id", "model", name="uq_qemb_question_model"),
        Index("ix_qemb_subject", "subject_id"),
        Index(
            "ix_qemb_embedding_hnsw",
            "embedding",
            postgresql_using="hnsw",
            postgresql_with={"m": 16, "ef_construction": 64},
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    question_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("questions.id"), nullable=False)
    subject_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("subjects.id"), nullable=False)
    embedding: Mapped[list[float]] = mapped_column(Vector(1024), nullable=False)
    model: Mapped[str] = mapped_column(String(100), nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)


class DocumentChunk(Base):
    __tablename__ = "document_chunks"
    __table_args__ = (
        UniqueConstraint("subject_id", "content_hash", name="uq_doc_subject_hash"),
        Index("ix_doc_subject", "subject_id"),
        Index(
            "ix_doc_embedding_hnsw",
            "embedding",
            postgresql_using="hnsw",
            postgresql_with={"m": 16, "ef_construction": 64},
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    subject_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("subjects.id"), nullable=False)
    source: Mapped[str] = mapped_column(String(200), nullable=False)
    chapter: Mapped[str | None] = mapped_column(String(100), nullable=True)
    section: Mapped[str | None] = mapped_column(String(100), nullable=True)
    page: Mapped[str | None] = mapped_column(String(20), nullable=True)
    chunk_text: Mapped[str] = mapped_column(Text, nullable=False)
    embedding: Mapped[list[float] | None] = mapped_column(Vector(1024), nullable=True)
    meta: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)


class WrongAnswer(Base):
    __tablename__ = "wrong_answers"
    __table_args__ = (
        UniqueConstraint("user_id", "question_id", name="uq_wrong_user_question"),
        Index("ix_wrong_user_subject_mastered", "user_id", "subject_id", "mastered"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    question_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("questions.id"), nullable=False)
    subject_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("subjects.id"), nullable=False)
    wrong_answer: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    wrong_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    review_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    mastered: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow)


class UserKnowledgeState(Base):
    __tablename__ = "user_knowledge_states"
    __table_args__ = (
        CheckConstraint(
            "status IN ('untouched','consolidating','mastered','weak')",
            name="ck_ukstate_status",
        ),
        UniqueConstraint("user_id", "knowledge_point_id", name="uq_ukstate_user_kp"),
        Index("ix_ukstate_user_subject_status", "user_id", "subject_id", "status"),
        Index("ix_ukstate_user_subject_upd", "user_id", "subject_id", "updated_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    knowledge_point_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("knowledge_points.id"), nullable=False)
    subject_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("subjects.id"), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="untouched")
    correct_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    wrong_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    streak: Mapped[int] = mapped_column(Integer, nullable=False, default=0)  # M2：连续正确次数（答对+1，答错归 0；≥3 → mastered）
    last_practiced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow)


class Plan(Base):
    __tablename__ = "plans"
    __table_args__ = (
        CheckConstraint("status IN ('active','completed','cancelled')", name="ck_plans_status"),
        Index("ix_plans_user_subject_status", "user_id", "subject_id", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    subject_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("subjects.id"), nullable=False)
    title: Mapped[str | None] = mapped_column(String(200), nullable=True)
    exam_date: Mapped[datetime | None] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")
    config: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow)


class StudySession(Base):
    __tablename__ = "study_sessions"
    __table_args__ = (
        UniqueConstraint("user_id", "session_date", name="uq_session_user_date"),
        Index("ix_session_user_subject_date", "user_id", "subject_id", "session_date"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    subject_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("subjects.id"), nullable=False)
    plan_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("plans.id"), nullable=True)
    session_date: Mapped[datetime] = mapped_column(Date, nullable=False)
    questions_practiced: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    correct_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    checked_in: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    checked_in_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)  # M2：打卡时间（api.md §8.3）
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow)


class AIExplanation(Base):
    __tablename__ = "ai_explanations"
    __table_args__ = (
        UniqueConstraint("question_id", "model", "content_hash", name="uq_expl_question_model_hash"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    question_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("questions.id"), nullable=False)
    model: Mapped[str] = mapped_column(String(20), nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    explanation: Mapped[dict] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)


class SprintSession(Base):
    """考前突击会话（M3 新表，架构 §11.7-1 / §11.2）。

    生命周期：active（突击中）→ completed（用户手动结束）/ expired（考试日已过）。
    question_snapshot 为题单快照（items 题 id + tag 列表，防重复组卷/题目下线漂移，
    重复请求返回同一份题单，api.md §11.3）。
    """

    __tablename__ = "sprint_sessions"
    __table_args__ = (
        CheckConstraint(
            "status IN ('active','completed','expired')", name="ck_sprint_status"
        ),
        Index("ix_sprint_user_subject_status", "user_id", "subject_id", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    subject_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("subjects.id"), nullable=False)
    activated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    auto_activated: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")
    expires_at: Mapped[date | None] = mapped_column(Date, nullable=True)  # 考试日（关联计划 exam_date 快照）
    question_snapshot: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)  # [{"id","tag"}] 题单快照
    high_freq_kps: Mapped[list | None] = mapped_column(JSONB, nullable=True)  # 高频考点 top-N 快照
    stats: Mapped[dict | None] = mapped_column(JSONB, nullable=True)  # 完成统计（做题数/正确数/正确率）
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow)


class ChatSession(Base):
    __tablename__ = "chat_sessions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    question_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("questions.id"), nullable=True)
    session_key: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    messages: Mapped[list[dict]] = mapped_column(JSONB, nullable=False, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow)


class TokenUsage(Base):
    __tablename__ = "token_usage"
    __table_args__ = (Index("ix_token_usage_created", "created_at"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    model: Mapped[str] = mapped_column(String(20), nullable=False)
    scene: Mapped[str] = mapped_column(String(30), nullable=False)
    prompt_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    completion_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    cost_est: Mapped[float] = mapped_column(Numeric(10, 6), nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)


class OcrUpload(Base):
    """OCR 拍照录题上传记录（M2 新表，架构 §10.3 / §10.6-2）。

    生命周期：pending（识别中）→ parsed（识别+结构化完成）/ failed（识别失败）
              → confirmed（POST /questions/from-ocr 确认入库后，回填 question_id）。
    """

    __tablename__ = "ocr_uploads"
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending','parsed','failed','confirmed')", name="ck_ocr_status"
        ),
        Index("ix_ocr_user_status", "user_id", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    subject_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("subjects.id"), nullable=False)
    image_path: Mapped[str] = mapped_column(String(500), nullable=False)  # 原始图片引用（对象存储 key / 本地路径）
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    raw_text: Mapped[str | None] = mapped_column(Text, nullable=True)  # Pix2Text 识别输出（Markdown 含 LaTeX）
    structured: Mapped[dict | None] = mapped_column(JSONB, nullable=True)  # 结构化题目 JSON {type,content,options,answer,analysis,confidence}
    suggested_kps: Mapped[list | None] = mapped_column(JSONB, nullable=True)  # 知识点归属 top-3 [{id,name,score}]
    knowledge_point_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("knowledge_points.id"), nullable=True)  # 用户确认的知识点
    question_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("questions.id"), nullable=True)  # 确认入库后回填
    error: Mapped[str | None] = mapped_column(String(200), nullable=True)  # 错误码（如 OCR_EMPTY）
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow)


class DiagnosisReport(Base):
    """薄弱诊断报告（M2 新表，架构 §10.4 / §10.6-3）。

    两段式：规则层算排名（weak_top5/strengths/not_started），LLM 只生成措辞（report_text）。
    questions 为自测题组快照（题目可后续被改/下线，快照保证报告可解释、与自测表现一致）。
    """

    __tablename__ = "diagnosis_reports"
    __table_args__ = (
        CheckConstraint(
            "status IN ('in_progress','completed')", name="ck_diag_status"
        ),
        Index("ix_diag_user_created", "user_id", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    subject_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("subjects.id"), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="in_progress")
    questions: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)  # 题组快照 [{id,knowledge_point_id,type,content,options,difficulty}]
    answers: Mapped[list | None] = mapped_column(JSONB, nullable=True)  # 作答快照 [{question_id,answer,correct}]
    weak_top5: Mapped[list | None] = mapped_column(JSONB, nullable=True)  # 薄弱 Top5 快照 [{rank,knowledge_point_id,accuracy,practice_count,status,suggestion}]
    report_text: Mapped[str | None] = mapped_column(Text, nullable=True)  # LLM 措辞：summary + suggested_next_steps（JSON 字符串）
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow)


class Class(Base):
    """班级（M3.5 新表，架构 §12.5）。

    成员数通过 COUNT users.class_id 实时推导，不落列。
    """

    __tablename__ = "classes"
    __table_args__ = (
        UniqueConstraint("invite_code", name="uq_classes_invite_code"),
        Index("ix_classes_invite_code", "invite_code"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    invite_code: Mapped[str] = mapped_column(String(6), nullable=False)
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow)


class TextbookUpload(Base):
    """教材/课件上传记录（M2 新表，架构 §10.2 ① / §10.6-4）。

    用户上传教材 → 切块 → embedding 的状态跟踪；chunk_count 暴露处理进度
    （前端可据 status 提示"教材处理中/已就绪"）。
    """

    __tablename__ = "textbook_uploads"
    __table_args__ = (
        CheckConstraint(
            "status IN ('processing','ready','failed')", name="ck_tb_status"
        ),
        Index("ix_tb_user_status", "user_id", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    subject_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("subjects.id"), nullable=False)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)  # 原始文件名
    file_path: Mapped[str] = mapped_column(String(500), nullable=False)  # 存储引用
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="processing")
    chunk_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow)
