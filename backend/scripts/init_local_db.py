"""AceExam 本地开发数据库初始化：建表 + 种子（SQLite）。

复用 tests/conftest.py 的 SQLite 兼容 shim（JSONB→JSON、UUID bind processor），
让本地体验可以直接跑 SQLite 而无需 PostgreSQL。
"""
import uuid as _uuid_mod

from sqlalchemy import create_engine
from sqlalchemy.dialects.postgresql import UUID as _PgUUID
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.compiler import compiles

# ── SQLite 兼容（与 tests/conftest.py 相同）──
@compiles(JSONB, "sqlite")
def _compile_jsonb_sqlite(type_, compiler, **kw):  # pragma: no cover
    return "JSON"


_orig_uuid_bind = _PgUUID.bind_processor


def _sqlite_uuid_bind_processor(self, dialect):
    proc = _orig_uuid_bind(self, dialect)
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


_PgUUID.bind_processor = _sqlite_uuid_bind_processor

# 必须导入模型注册到 Base.metadata
from app.db.base import Base  # noqa: E402
from app.db import models  # noqa: E402,F401
from app.db.seed import seed  # noqa: E402


def main():
    url = "sqlite:///./aceexam.db"
    engine = create_engine(url)
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    print("表结构创建完成")
    seed(url, reset=True)
    print("种子数据完成")


if __name__ == "__main__":
    main()
