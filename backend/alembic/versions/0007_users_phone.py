"""M6 表结构增量：users.phone（手机号，找回密码用）

落地内容：
1. users.phone：String(20) 可空（注册可选填；找回密码按手机号定位账号）。
2. ix_users_phone：普通索引（找回密码按 phone 查询；手机号非强制唯一，
   一个手机号可绑定多个账号时取最近注册者）。
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0007_users_phone"
down_revision: Union[str, None] = "0006_course_alias_level"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("phone", sa.String(20), nullable=True),
    )
    op.create_index("ix_users_phone", "users", ["phone"])


def downgrade() -> None:
    op.drop_index("ix_users_phone", table_name="users")
    op.drop_column("users", "phone")
