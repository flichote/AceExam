"""M4 表结构增量：users.major + subjects.is_public + user_subjects 新表

架构 §13 / database.md §11。
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0005_user_major_plaza"
down_revision: Union[str, None] = "0004_m35_classes_ugc"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. users.major（可空，自由文本，最长 100）
    op.add_column("users", sa.Column("major", sa.String(100), nullable=True))

    # 2. subjects.is_public（默认 False，课程广场过滤字段）
    op.add_column(
        "subjects",
        sa.Column("is_public", sa.Boolean, nullable=False, server_default=sa.false()),
    )

    # 3. user_subjects 关联表（用户自选课程多对多）
    op.create_table(
        "user_subjects",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("subject_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("subjects.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("user_id", "subject_id", name="uq_us_user_subject"),
    )
    op.create_index("ix_us_user_id", "user_subjects", ["user_id"])
    op.create_index("ix_us_subject_id", "user_subjects", ["subject_id"])


def downgrade() -> None:
    # 3. user_subjects 回滚
    op.drop_index("ix_us_subject_id", table_name="user_subjects")
    op.drop_index("ix_us_user_id", table_name="user_subjects")
    op.drop_table("user_subjects")

    # 2. subjects.is_public 回滚
    op.drop_column("subjects", "is_public")

    # 1. users.major 回滚
    op.drop_column("users", "major")
