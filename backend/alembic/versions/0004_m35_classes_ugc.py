"""M3.5 表结构增量：classes 新表 + users.class_id + questions UGC 审核字段

架构 §12.5 / database.md §10。
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0004_m35_classes_ugc"
down_revision: Union[str, None] = "0003_m3_sprint"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. classes 新表
    op.create_table(
        "classes",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("invite_code", sa.String(6), nullable=False),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("invite_code", name="uq_classes_invite_code"),
    )
    op.create_index("ix_classes_invite_code", "classes", ["invite_code"])

    # 2. users.class_id（可空 FK，use_alter 解决循环依赖）
    op.add_column("users", sa.Column("class_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.create_foreign_key(
        "fk_users_class_id", "users", "classes", ["class_id"], ["id"],
        use_alter=True,
    )
    op.create_index("ix_users_class_id", "users", ["class_id"])

    # 3. questions 扩展：status CHECK + 新列 + 新索引
    # 先删除旧 CHECK 约束（SQLite 不支持 ALTER CONSTRAINT，PG 使用以下变通）
    op.execute("ALTER TABLE questions DROP CONSTRAINT IF EXISTS ck_questions_status")
    op.execute(
        "ALTER TABLE questions ADD CONSTRAINT ck_questions_status "
        "CHECK (status IN ('draft','pending','active','rejected','archived'))"
    )

    op.add_column("questions", sa.Column("submitted_by", postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column("questions", sa.Column("reviewed_by", postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column("questions", sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("questions", sa.Column("reject_reason", sa.Text(), nullable=True))

    op.create_foreign_key("fk_questions_submitted_by", "questions", "users", ["submitted_by"], ["id"])
    op.create_foreign_key("fk_questions_reviewed_by", "questions", "users", ["reviewed_by"], ["id"])
    op.create_index("ix_questions_status_created", "questions", ["status", "created_at"])


def downgrade() -> None:
    # questions 回滚
    op.drop_index("ix_questions_status_created", table_name="questions")
    op.drop_constraint("fk_questions_reviewed_by", "questions", type_="foreignkey")
    op.drop_constraint("fk_questions_submitted_by", "questions", type_="foreignkey")
    op.drop_column("questions", "reject_reason")
    op.drop_column("questions", "reviewed_at")
    op.drop_column("questions", "reviewed_by")
    op.drop_column("questions", "submitted_by")

    op.execute("ALTER TABLE questions DROP CONSTRAINT IF EXISTS ck_questions_status")
    op.execute(
        "ALTER TABLE questions ADD CONSTRAINT ck_questions_status "
        "CHECK (status IN ('draft','active','archived'))"
    )

    # users 回滚
    op.drop_index("ix_users_class_id", table_name="users")
    op.drop_constraint("fk_users_class_id", "users", type_="foreignkey")
    op.drop_column("users", "class_id")

    # classes 回滚
    op.drop_index("ix_classes_invite_code", table_name="classes")
    op.drop_table("classes")
