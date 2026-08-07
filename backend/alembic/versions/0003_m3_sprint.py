"""M3 增量迁移：考前突击会话 sprint_sessions

Revision ID: 0003_m3_sprint
Revises: 0002_m2_diagnosis_checkin_ocr
Create Date: 2026-08-08

表结构事实来源：docs/architecture.md §11.7（M3 表增量约定，决策锁定 D4）+ docs/database.md §9（M3 增量，随本迁移同步更新）。
变更清单：
  1. 新表 sprint_sessions（考前突击会话：激活时间 / 题单快照 / 高频考点快照 / 完成统计）

M3 决策确认（architecture.md §11.3/§11.5/§11.6/§11.7，均无新表）：
  - 打卡连胜：无新表无新字段（study_sessions 的 UNIQUE(user_id, session_date) + checked_in 已支撑，
    判定只需按日期的 checked_in=true 序列，§11.3）
  - 排行榜：无新表（纯查询方案，实时聚合 study_sessions GROUP BY；预留 leaderboard_snapshots 草案不建，§11.5）
  - 挂科预警：无新表（实时推导瞬态视图；预留 risk_alerts 草案不建，§11.6）
  - 高频考点识别：无新表（从 user_knowledge_states 实时聚合，§11.2）

sprint_sessions.question_snapshot 快照语义（api.md §11.3）：
  重复请求返回同一份题单（sprint_id 稳定），防重复组卷 / 题目下线漂移；
  存 items 题 id + tag（high_freq / wrong_review），返回时 join questions 取实时内容。
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0003_m3_sprint"
down_revision: Union[str, None] = "0002_m2_diagnosis_checkin_ocr"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── 1. sprint_sessions（考前突击会话，M3 唯一新表，架构 §11.7-1）──
    op.create_table(
        "sprint_sessions",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id"),
            nullable=False,
        ),
        sa.Column(
            "subject_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("subjects.id"),
            nullable=False,
        ),
        # 激活时间（自动激活 = 首次访问题单时创建；手动激活 = POST /sprint/activate）
        sa.Column(
            "activated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        # 自动（考前 7 天触发）/ 手动
        sa.Column(
            "auto_activated",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column(
            "status",
            sa.String(20),
            nullable=False,
            server_default="active",
        ),
        # 考试日（关联计划 exam_date 快照；无 active 计划时为 NULL）
        sa.Column("expires_at", sa.Date(), nullable=True),
        # 题单快照 [{"id": "<question_id>", "tag": "high_freq"|"wrong_review"}]，防重复组卷/题目下线漂移
        sa.Column(
            "question_snapshot",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        # 高频考点 top-N 快照 [{"id","name","heat","avg_accuracy","has_past_exam"}]（展示"本卷覆盖高频考点"）
        sa.Column("high_freq_kps", postgresql.JSONB(), nullable=True),
        # 完成统计 {"questions_practiced","correct_count","accuracy"}（可选）
        sa.Column("stats", postgresql.JSONB(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.CheckConstraint(
            "status IN ('active','completed','expired')", name="ck_sprint_status"
        ),
    )
    # 同一时刻每用户每科目至多一个 active（T15 先查后建 + 幂等，不建部分唯一索引，简单为先）
    op.create_index(
        "ix_sprint_user_subject_status",
        "sprint_sessions",
        ["user_id", "subject_id", "status"],
    )


def downgrade() -> None:
    op.drop_index("ix_sprint_user_subject_status", table_name="sprint_sessions")
    op.drop_table("sprint_sessions")
