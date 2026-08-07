"""M2 增量迁移：诊断/打卡/OCR/教材上传

Revision ID: 0002_m2_diagnosis_checkin_ocr
Revises: 0001_initial
Create Date: 2026-08-07

表结构事实来源：docs/architecture.md §10.6（M2 表增量约定）+ docs/database.md §8（M2 增量，随本迁移同步更新）。
变更清单：
  1. user_knowledge_states 增列 streak（连续正确次数，自适应选题状态机，§10.1）
  2. study_sessions 增列 checked_in_at（打卡时间，api.md §8.3 返回字段）
  3. 新表 ocr_uploads（拍照录题上传记录，§10.3 / §10.6-2）
  4. 新表 diagnosis_reports（薄弱诊断报告，§10.4 / §10.6-3）
  5. 新表 textbook_uploads（教材上传→切块→embed 状态跟踪，§10.2 / §10.6-4）

说明：document_chunks.source 在 M1 即为 VARCHAR(200) 无 CHECK 约束，
'user_upload' 值天然可用，无需 DDL 变更（docs/database.md §8.2 记录）。
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0002_m2_diagnosis_checkin_ocr"
down_revision: Union[str, None] = "0001_initial"
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
    # ── 1. user_knowledge_states.streak（M2 状态机：答对+1、答错归0、≥3 → mastered）──
    op.add_column(
        "user_knowledge_states",
        sa.Column("streak", sa.Integer(), nullable=False, server_default=sa.text("0")),
    )

    # ── 2. study_sessions.checked_in_at（打卡时间，api.md §8.3）──
    op.add_column(
        "study_sessions",
        sa.Column("checked_in_at", sa.DateTime(timezone=True), nullable=True),
    )

    # ── 3. ocr_uploads（拍照录题上传记录）──
    op.create_table(
        "ocr_uploads",
        _uuid_pk(),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("subject_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("subjects.id"), nullable=False),
        sa.Column("image_path", sa.String(500), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("raw_text", sa.Text(), nullable=True),
        sa.Column("structured", postgresql.JSONB(), nullable=True),
        sa.Column("suggested_kps", postgresql.JSONB(), nullable=True),
        sa.Column(
            "knowledge_point_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("knowledge_points.id"),
            nullable=True,
        ),
        sa.Column(
            "question_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("questions.id"),
            nullable=True,
        ),
        sa.Column("error", sa.String(200), nullable=True),
        *_timestamps(),
        sa.CheckConstraint(
            "status IN ('pending','parsed','failed','confirmed')", name="ck_ocr_status"
        ),
    )
    op.create_index("ix_ocr_user_status", "ocr_uploads", ["user_id", "status"])

    # ── 4. diagnosis_reports（薄弱诊断报告，题组/作答/薄弱 Top5 快照）──
    op.create_table(
        "diagnosis_reports",
        _uuid_pk(),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("subject_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("subjects.id"), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="in_progress"),
        sa.Column("questions", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("answers", postgresql.JSONB(), nullable=True),
        sa.Column("weak_top5", postgresql.JSONB(), nullable=True),
        sa.Column("report_text", sa.Text(), nullable=True),
        *_timestamps(),
        sa.CheckConstraint(
            "status IN ('in_progress','completed')", name="ck_diag_status"
        ),
    )
    op.create_index("ix_diag_user_created", "diagnosis_reports", ["user_id", "created_at"])

    # ── 5. textbook_uploads（教材上传 → 切块 → embed 状态跟踪）──
    op.create_table(
        "textbook_uploads",
        _uuid_pk(),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("subject_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("subjects.id"), nullable=False),
        sa.Column("filename", sa.String(255), nullable=False),
        sa.Column("file_path", sa.String(500), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="processing"),
        sa.Column("chunk_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("error", sa.String(500), nullable=True),
        *_timestamps(),
        sa.CheckConstraint(
            "status IN ('processing','ready','failed')", name="ck_tb_status"
        ),
    )
    op.create_index("ix_tb_user_status", "textbook_uploads", ["user_id", "status"])


def downgrade() -> None:
    # 逆序 drop（先子后父）
    op.drop_index("ix_tb_user_status", table_name="textbook_uploads")
    op.drop_table("textbook_uploads")

    op.drop_index("ix_diag_user_created", table_name="diagnosis_reports")
    op.drop_table("diagnosis_reports")

    op.drop_index("ix_ocr_user_status", table_name="ocr_uploads")
    op.drop_table("ocr_uploads")

    op.drop_column("study_sessions", "checked_in_at")
    op.drop_column("user_knowledge_states", "streak")
