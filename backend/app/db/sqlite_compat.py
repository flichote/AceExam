"""SQLite 运行时兼容 shim（本地开发用）。

模型层使用 postgresql.JSONB / postgresql.UUID(as_uuid=True)，生产走 asyncpg；
本地体验用 SQLite（conda PG 有 0xC0000142 DLL 问题）。本模块在应用启动时
应用与 tests/conftest.py 相同的兼容补丁，让 SQLite 行为对齐 asyncpg。

生产（PostgreSQL）下本模块不产生副作用。
"""
import uuid as _uuid_mod

from sqlalchemy.dialects.postgresql import UUID as _PgUUID
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.compiler import compiles


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


def apply_sqlite_compat() -> None:
    """显式应用兼容补丁（幂等，可重复调用）。"""
    # bind_processor 已在模块导入时替换；此处保留为显式入口，方便理解依赖顺序。
    return None
