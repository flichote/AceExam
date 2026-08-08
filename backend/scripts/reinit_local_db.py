"""本地开发库重建：应用 0005 迁移后的最新模型（major/is_public/user_subjects）。

本地 SQLite 是开发库，直接 drop_all + create_all + seed 重建（迁移在 PG 上由 alembic 管理）。
"""
import uuid as _uuid_mod

from sqlalchemy import create_engine
from sqlalchemy.dialects.postgresql import UUID as _PgUUID
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.compiler import compiles

@compiles(JSONB, "sqlite")
def _c(t, c, **kw):
    return "JSON"

_orig = _PgUUID.bind_processor


def _shim(self, dialect):
    proc = _orig(self, dialect)
    if proc is None:
        return None

    def process(value):
        if isinstance(value, str):
            try:
                value = _uuid_mod.UUID(value)
            except ValueError:
                pass
        return proc(value)

    return process


_PgUUID.bind_processor = _shim

from app.db.base import Base  # noqa: E402
from app.db import models  # noqa: E402,F401
from app.db.seed import seed  # noqa: E402

url = "sqlite:///./aceexam.db"
engine = create_engine(url)
Base.metadata.drop_all(engine)
Base.metadata.create_all(engine)
print("表结构重建完成（含 major/is_public/user_subjects）")
seed(url, reset=False)
print("seed 完成")

# 验证新字段
import sqlite3  # noqa: E402
conn = sqlite3.connect("aceexam.db")
cur = conn.cursor()
cur.execute("PRAGMA table_info(subjects)")
cols = [r[1] for r in cur.fetchall()]
print("subjects 列含 is_public:", "is_public" in cols)
cur.execute("PRAGMA table_info(users)")
cols2 = [r[1] for r in cur.fetchall()]
print("users 列含 major:", "major" in cols2)
cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='user_subjects'")
print("user_subjects 表存在:", cur.fetchone() is not None)
cur.execute("SELECT code, is_public FROM subjects")
print("科目:", cur.fetchall())
conn.close()
