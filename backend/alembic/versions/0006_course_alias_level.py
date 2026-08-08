"""M5 表结构增量：course_aliases 新表 + subjects.level + user_subjects.template_subject_id

架构 §14.2 / §14.5；database.md §12。落地内容：
1. course_aliases（同课多名归一）：alias → template_subject_id，
   source（seed/ai/manual）+ is_verified（D20），UNIQUE(alias)，ix_course_aliases_template。
2. subjects.level：public/major/school 课程分层（NOT NULL DEFAULT 'public' + CHECK），
   ix_subjects_level (level, is_active)（分层列表/广场过滤）。
3. user_subjects.template_subject_id：校本课程实例 → 模板课程外键
   （NULL=未归一独立实例），ix_user_subjects_template (user_id, template_subject_id)。
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0006_course_alias_level"
down_revision: Union[str, None] = "0005_user_major_plaza"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. subjects.level（NOT NULL DEFAULT 'public'，CHECK public/major/school）
    op.add_column(
        "subjects",
        sa.Column("level", sa.String(20), nullable=False, server_default="public"),
    )
    op.create_check_constraint(
        "ck_subjects_level", "subjects", "level IN ('public','major','school')"
    )
    op.create_index("ix_subjects_level", "subjects", ["level", "is_active"])

    # 2. course_aliases 新表（同课多名归一，架构 §14.2 / D20）
    op.create_table(
        "course_aliases",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("alias", sa.String(100), nullable=False),
        sa.Column(
            "template_subject_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("subjects.id"),
            nullable=False,
        ),
        sa.Column("source", sa.String(20), nullable=False, server_default="seed"),
        sa.Column("is_verified", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("source IN ('seed','ai','manual')", name="ck_course_aliases_source"),
        sa.UniqueConstraint("alias", name="uq_course_aliases_alias"),
    )
    op.create_index("ix_course_aliases_template", "course_aliases", ["template_subject_id"])

    # 3. user_subjects.template_subject_id（NULL=未归一独立实例）
    op.add_column(
        "user_subjects",
        sa.Column(
            "template_subject_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("subjects.id"),
            nullable=True,
        ),
    )
    op.create_index(
        "ix_user_subjects_template", "user_subjects", ["user_id", "template_subject_id"]
    )


def downgrade() -> None:
    # 3. user_subjects.template_subject_id 回滚
    op.drop_index("ix_user_subjects_template", table_name="user_subjects")
    op.drop_column("user_subjects", "template_subject_id")

    # 2. course_aliases 回滚
    op.drop_index("ix_course_aliases_template", table_name="course_aliases")
    op.drop_table("course_aliases")

    # 1. subjects.level 回滚
    op.drop_index("ix_subjects_level", table_name="subjects")
    op.drop_constraint("ck_subjects_level", "subjects", type_="check")
    op.drop_column("subjects", "level")
