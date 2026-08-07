"""initial schema: AceExam M1 全部表 + 索引 + pgvector

Revision ID: 0001_initial
Revises:
Create Date: 2026-08-07

表结构事实来源：docs/database.md（ep-arch 评审后锁定）。
主键 UUID + gen_random_uuid()（PG13+ 内置）；向量列 VECTOR(1024) + HNSW(vector_cosine_ops)。
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import VECTOR
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _uuid_pk() -> sa.Column:
    return sa.Column(
        "id",
        postgresql.UUID(as_uuid=True),
        primary_key=True,
        server_default=sa.text("gen_random_uuid()"),
    )


def _timestamps() -> list[sa.Column]:
    return [
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    ]


def upgrade() -> None:
    # --- pgvector 扩展（幂等） ---
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    # --- users ---
    op.create_table(
        "users",
        _uuid_pk(),
        sa.Column("username", sa.String(50), nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("role", sa.String(20), nullable=False, server_default="student"),
        sa.Column("is_member", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("member_expires_at", sa.DateTime(timezone=True), nullable=True),
        *_timestamps(),
        sa.CheckConstraint("role IN ('student','admin')", name="ck_users_role"),
        sa.UniqueConstraint("username", name="uq_users_username"),
    )

    # --- subjects ---
    op.create_table(
        "subjects",
        _uuid_pk(),
        sa.Column("code", sa.String(50), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("config", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default=sa.text("0")),
        *_timestamps(),
        sa.UniqueConstraint("code", name="uq_subjects_code"),
    )

    # --- knowledge_points（树） ---
    op.create_table(
        "knowledge_points",
        _uuid_pk(),
        sa.Column("subject_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("subjects.id"), nullable=False),
        sa.Column("parent_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("knowledge_points.id"), nullable=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("content", sa.Text(), nullable=True),
        sa.Column("level", sa.SmallInteger(), nullable=False, server_default=sa.text("1")),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default=sa.text("0")),
        *_timestamps(),
        sa.CheckConstraint("level BETWEEN 1 AND 3", name="ck_kp_level"),
        sa.UniqueConstraint("subject_id", "parent_id", "name", name="uq_kp_subject_parent_name"),
    )
    op.create_index("ix_kp_subject_parent", "knowledge_points", ["subject_id", "parent_id"])
    op.create_index("ix_kp_subject_level", "knowledge_points", ["subject_id", "level"])

    # --- questions ---
    op.create_table(
        "questions",
        _uuid_pk(),
        sa.Column("subject_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("subjects.id"), nullable=False),
        sa.Column(
            "knowledge_point_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("knowledge_points.id"),
            nullable=False,
        ),
        sa.Column("type", sa.String(20), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("options", postgresql.JSONB(), nullable=True),
        sa.Column("answer", postgresql.JSONB(), nullable=False),
        sa.Column("analysis", sa.Text(), nullable=True),
        sa.Column("difficulty", sa.SmallInteger(), nullable=False, server_default=sa.text("3")),
        sa.Column("source", sa.String(20), nullable=False, server_default="self_built"),
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
        *_timestamps(),
        sa.CheckConstraint("difficulty BETWEEN 1 AND 5", name="ck_questions_difficulty"),
        sa.CheckConstraint("source IN ('textbook','past_exam','self_built','ugc')", name="ck_questions_source"),
        sa.CheckConstraint("status IN ('draft','active','archived')", name="ck_questions_status"),
    )
    op.create_index("ix_questions_subject_kp_diff", "questions", ["subject_id", "knowledge_point_id", "difficulty"])
    op.create_index("ix_questions_subject_status", "questions", ["subject_id", "status"])

    # --- question_embeddings（向量表） ---
    op.create_table(
        "question_embeddings",
        _uuid_pk(),
        sa.Column("question_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("questions.id"), nullable=False),
        sa.Column("subject_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("subjects.id"), nullable=False),
        sa.Column("embedding", VECTOR(1024), nullable=False),
        sa.Column("model", sa.String(100), nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("question_id", "model", name="uq_qemb_question_model"),
    )
    op.create_index("ix_qemb_subject", "question_embeddings", ["subject_id"])
    op.create_index(
        "ix_qemb_embedding_hnsw",
        "question_embeddings",
        ["embedding"],
        postgresql_using="hnsw",
        postgresql_with={"m": 16, "ef_construction": 64},
        postgresql_ops={"embedding": "vector_cosine_ops"},
    )

    # --- document_chunks（教材向量库 RAG） ---
    op.create_table(
        "document_chunks",
        _uuid_pk(),
        sa.Column("subject_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("subjects.id"), nullable=False),
        sa.Column("source", sa.String(200), nullable=False),
        sa.Column("chapter", sa.String(100), nullable=True),
        sa.Column("section", sa.String(100), nullable=True),
        sa.Column("page", sa.String(20), nullable=True),
        sa.Column("chunk_text", sa.Text(), nullable=False),
        sa.Column("embedding", VECTOR(1024), nullable=True),
        sa.Column("meta", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("subject_id", "content_hash", name="uq_doc_subject_hash"),
    )
    op.create_index("ix_doc_subject", "document_chunks", ["subject_id"])
    op.create_index(
        "ix_doc_embedding_hnsw",
        "document_chunks",
        ["embedding"],
        postgresql_using="hnsw",
        postgresql_with={"m": 16, "ef_construction": 64},
        postgresql_ops={"embedding": "vector_cosine_ops"},
    )

    # --- wrong_answers ---
    op.create_table(
        "wrong_answers",
        _uuid_pk(),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("question_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("questions.id"), nullable=False),
        sa.Column("subject_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("subjects.id"), nullable=False),
        sa.Column("wrong_answer", postgresql.JSONB(), nullable=True),
        sa.Column("wrong_reason", sa.Text(), nullable=True),
        sa.Column("review_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("mastered", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        *_timestamps(),
        sa.UniqueConstraint("user_id", "question_id", name="uq_wrong_user_question"),
    )
    op.create_index("ix_wrong_user_subject_mastered", "wrong_answers", ["user_id", "subject_id", "mastered"])

    # --- user_knowledge_states（自适应选题核心） ---
    op.create_table(
        "user_knowledge_states",
        _uuid_pk(),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column(
            "knowledge_point_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("knowledge_points.id"),
            nullable=False,
        ),
        sa.Column("subject_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("subjects.id"), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="untouched"),
        sa.Column("correct_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("wrong_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("last_practiced_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.CheckConstraint(
            "status IN ('untouched','consolidating','mastered','weak')", name="ck_ukstate_status"
        ),
        sa.UniqueConstraint("user_id", "knowledge_point_id", name="uq_ukstate_user_kp"),
    )
    # 自适应选题复合索引：按用户+科目+状态捞知识点
    op.create_index("ix_ukstate_user_subject_status", "user_knowledge_states", ["user_id", "subject_id", "status"])
    op.create_index("ix_ukstate_user_subject_upd", "user_knowledge_states", ["user_id", "subject_id", "updated_at"])

    # --- plans（备考计划） ---
    op.create_table(
        "plans",
        _uuid_pk(),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("subject_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("subjects.id"), nullable=False),
        sa.Column("title", sa.String(200), nullable=True),
        sa.Column("exam_date", sa.Date(), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
        sa.Column("config", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        *_timestamps(),
        sa.CheckConstraint("status IN ('active','completed','cancelled')", name="ck_plans_status"),
    )
    op.create_index("ix_plans_user_subject_status", "plans", ["user_id", "subject_id", "status"])

    # --- study_sessions（学习记录/打卡） ---
    op.create_table(
        "study_sessions",
        _uuid_pk(),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("subject_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("subjects.id"), nullable=False),
        sa.Column("plan_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("plans.id"), nullable=True),
        sa.Column("session_date", sa.Date(), nullable=False),
        sa.Column("questions_practiced", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("correct_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("checked_in", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        *_timestamps(),
        sa.UniqueConstraint("user_id", "session_date", name="uq_session_user_date"),
    )
    op.create_index("ix_session_user_subject_date", "study_sessions", ["user_id", "subject_id", "session_date"])

    # --- ai_explanations（讲解缓存） ---
    op.create_table(
        "ai_explanations",
        _uuid_pk(),
        sa.Column("question_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("questions.id"), nullable=False),
        sa.Column("model", sa.String(20), nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("explanation", postgresql.JSONB(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("question_id", "model", "content_hash", name="uq_expl_question_model_hash"),
    )

    # --- chat_sessions（追问会话） ---
    op.create_table(
        "chat_sessions",
        _uuid_pk(),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("question_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("questions.id"), nullable=True),
        sa.Column("session_key", sa.String(64), nullable=False),
        sa.Column("messages", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        *_timestamps(),
        sa.UniqueConstraint("session_key", name="uq_chat_session_key"),
    )

    # --- token_usage（LLM 计量） ---
    op.create_table(
        "token_usage",
        _uuid_pk(),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("model", sa.String(20), nullable=False),
        sa.Column("scene", sa.String(30), nullable=False),
        sa.Column("prompt_tokens", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("completion_tokens", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("cost_est", sa.Numeric(10, 6), nullable=False, server_default=sa.text("0")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_token_usage_created", "token_usage", ["created_at"])


def downgrade() -> None:
    # 逆序 drop（先子后父）
    op.drop_index("ix_token_usage_created", table_name="token_usage")
    op.drop_table("token_usage")
    op.drop_table("chat_sessions")
    op.drop_table("ai_explanations")
    op.drop_index("ix_session_user_subject_date", table_name="study_sessions")
    op.drop_table("study_sessions")
    op.drop_index("ix_plans_user_subject_status", table_name="plans")
    op.drop_table("plans")
    op.drop_index("ix_ukstate_user_subject_upd", table_name="user_knowledge_states")
    op.drop_index("ix_ukstate_user_subject_status", table_name="user_knowledge_states")
    op.drop_table("user_knowledge_states")
    op.drop_index("ix_wrong_user_subject_mastered", table_name="wrong_answers")
    op.drop_table("wrong_answers")
    op.drop_index("ix_doc_embedding_hnsw", table_name="document_chunks")
    op.drop_index("ix_doc_subject", table_name="document_chunks")
    op.drop_table("document_chunks")
    op.drop_index("ix_qemb_embedding_hnsw", table_name="question_embeddings")
    op.drop_index("ix_qemb_subject", table_name="question_embeddings")
    op.drop_table("question_embeddings")
    op.drop_index("ix_questions_subject_status", table_name="questions")
    op.drop_index("ix_questions_subject_kp_diff", table_name="questions")
    op.drop_table("questions")
    op.drop_index("ix_kp_subject_level", table_name="knowledge_points")
    op.drop_index("ix_kp_subject_parent", table_name="knowledge_points")
    op.drop_table("knowledge_points")
    op.drop_table("subjects")
    op.drop_table("users")
    # 扩展不 drop（可能被其他库使用；如需彻底清理手动执行 DROP EXTENSION vector）
