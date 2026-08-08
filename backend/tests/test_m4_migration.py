"""T27 迁移可执行性验证 — M4 0005_user_major_plaza（含全链 0001→0005）。

任务要求（T27 body）：数据迁移可执行 —— alembic upgrade head --sql 或等效。

方法：subprocess 调用 backend/.venv 的 python -m alembic upgrade head --sql（离线模式，
不连接数据库，仅生成 SQL 渲染方言）。断言：
  1. 退出码 0（迁移链脚本无语法/引用错误，0001→0005 全部可渲染）；
  2. 输出包含 0005 的关键 DDL：users.major、subjects.is_public、user_subjects 建表 + 索引。

注意：离线模式由 alembic/env.py 的 run_migrations_offline 驱动，DATABASE_URL 未设置时
以 "postgresql://" 渲染方言（--sql 不真正连接，无需真实 PG）。
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

BACKEND_DIR = Path(__file__).resolve().parents[1]  # backend/
PYTHON_BIN = BACKEND_DIR / ".venv" / "Scripts" / "python.exe"


def _run_alembic_sql() -> subprocess.CompletedProcess:
    """在 backend/ 目录跑 alembic upgrade head --sql（离线）。"""
    env = os.environ.copy()
    env.pop("PYTHONPATH", None)  # 清空宿主 venv 污染
    env.pop("DATABASE_URL", None)  # 保持离线渲染方言
    return subprocess.run(
        [str(PYTHON_BIN), "-m", "alembic", "upgrade", "head", "--sql"],
        cwd=str(BACKEND_DIR),
        capture_output=True,
        text=True,
        timeout=120,
        env=env,
    )


@pytest.mark.anyio
class TestMigrationChainExecutable:
    """0001→0005 全链离线 SQL 可生成（迁移脚本无阻断性错误）。"""

    async def test_upgrade_head_sql_exit_zero(self):
        if not PYTHON_BIN.exists():
            pytest.skip("backend/.venv 不存在，跳过迁移验证")
        proc = _run_alembic_sql()
        assert proc.returncode == 0, (
            f"alembic upgrade head --sql 失败 rc={proc.returncode}\n"
            f"STDOUT: {proc.stdout[-2000:]}\nSTDERR: {proc.stderr[-2000:]}"
        )

    async def test_sql_contains_0005_ddl(self):
        """0005 关键 DDL 出现在渲染结果中。"""
        if not PYTHON_BIN.exists():
            pytest.skip("backend/.venv 不存在，跳过迁移验证")
        proc = _run_alembic_sql()
        assert proc.returncode == 0
        sql = proc.stdout
        # 1. users.major 列
        assert "ADD COLUMN major VARCHAR(100)" in sql or "ADD COLUMN major" in sql
        # 2. subjects.is_public 列
        assert "ADD COLUMN is_public" in sql
        # 3. user_subjects 表 + 唯一约束 + 索引
        assert "CREATE TABLE user_subjects" in sql
        assert "ix_us_user_id" in sql
        assert "ix_us_subject_id" in sql

    async def test_migration_metadata_0005_chain(self):
        """0005 迁移链头尾正确（down_revision=0004_m35_classes_ugc）。"""
        mig_file = BACKEND_DIR / "alembic" / "versions" / "0005_user_major_plaza.py"
        if not mig_file.exists():
            pytest.skip("0005 迁移文件不存在")
        text = mig_file.read_text(encoding="utf-8")
        assert 'revision: str = "0005_user_major_plaza"' in text
        assert 'down_revision: Union[str, None] = "0004_m35_classes_ugc"' in text
        # 升级/回滚函数存在
        assert "def upgrade()" in text
        assert "def downgrade()" in text
