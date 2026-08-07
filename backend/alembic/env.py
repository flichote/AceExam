"""Alembic 迁移环境（AceExam M1，ep-db 交付）。

- 目标元数据：backend/app/db/models.py 的 Base.metadata（全部 M1 表）
- 数据库连接：优先 DATABASE_URL 环境变量，其次 alembic.ini 的 sqlalchemy.url
"""
import os
import sys
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

# 确保 backend/ 在 sys.path，使 `from app.db import models` 可导入
BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from app.db.base import Base  # noqa: E402
from app.db import models  # noqa: E402,F401  # 注册全部表到 Base.metadata

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# DATABASE_URL 环境变量优先（.env 不入库）
database_url = os.environ.get("DATABASE_URL")
if database_url:
    config.set_main_option("sqlalchemy.url", database_url)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """离线模式：只生成 SQL 不连库（--sql）。"""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url or "postgresql://",  # 仅用于渲染方言；--sql 模式不真正连接
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """在线模式：连接数据库执行迁移。"""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
