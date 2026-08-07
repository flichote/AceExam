"""Shared test fixtures — AceExam M1 三层测试门禁 conftest。

设计要点：
1. 独立测试库：默认 SQLite 文件 `test_aceexam.db`（backend/ 目录，已被 .gitignore 覆盖）；
   设置环境变量 TEST_DATABASE_URL 可切换到 PG 测试库（如
   postgresql+asyncpg://postgres:postgres@localhost:5432/test_aceexam）。
2. 每个用到 DB 的测试自动 drop_all → create_all → 种子数据，测试后清理（互不污染）。
3. FastAPI get_db 依赖被覆盖为测试会话工厂；上游 LLM / OCR / 向量库一律不真调（见各测试文件）。
4. 运行方式（PYTHONPATH 必须清空，避免宿主 hermes venv 污染）：
   cd backend && PYTHONPATH= .venv/Scripts/python.exe -m pytest
"""
import os
import uuid
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.ext.compiler import compiles

# ── SQLite 兼容：postgresql.JSONB → JSON（模型层使用 JSONB，SQLite 无原生 JSONB）──
@compiles(JSONB, "sqlite")
def _compile_jsonb_sqlite(type_, compiler, **kw):  # pragma: no cover
    return "JSON"


# ── SQLite 兼容：postgresql.UUID(as_uuid=True) 的 bind processor ──
# 生产库 asyncpg 会把 JWT 里的字符串 UUID 自动转成 uuid.UUID；SQLite 驱动没有这个行为，
# 直接 bind str 会报 "'str' object has no attribute 'hex'"。这里是测试专用 shim，
# 让 SQLite 与 asyncpg 行为对齐（仅在本测试进程生效，不影响业务代码）。
import uuid as _uuid_mod  # noqa: E402

from sqlalchemy.dialects.postgresql import UUID as _PgUUID  # noqa: E402

_orig_uuid_bind = _PgUUID.bind_processor


def _sqlite_uuid_bind_processor(self, dialect):
    """包装 postgresql.UUID.bind_processor：str 先转 uuid.UUID 再走原逻辑。"""
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


# 必须在创建引擎前导入模型，让所有表注册到 Base.metadata
from app.db.base import Base  # noqa: E402
from app.db.models import (  # noqa: E402,F401
    KnowledgePoint,
    Question,
    Subject,
    User,
)
from app.core.security import hash_password  # noqa: E402
from app.db import get_db  # noqa: E402
from app.main import app  # noqa: E402

TEST_DATABASE_URL = os.getenv(
    "TEST_DATABASE_URL", "sqlite+aiosqlite:///./test_aceexam.db"
)
SQLITE_FILE = Path("test_aceexam.db")


# ═══════════════════════════════════════════════════════════════════════
# 引擎 / 会话
# ═══════════════════════════════════════════════════════════════════════


@pytest.fixture(scope="session")
async def test_engine():
    """Session 级测试引擎（SQLite 文件或 TEST_DATABASE_URL 指定的 PG）。"""
    engine = create_async_engine(TEST_DATABASE_URL)
    yield engine
    await engine.dispose()
    # 清理 SQLite 文件
    if TEST_DATABASE_URL.startswith("sqlite") and SQLITE_FILE.exists():
        SQLITE_FILE.unlink(missing_ok=True)


@pytest.fixture
async def reset_db(test_engine):
    """每个用例前重建 schema（建表），用例结束后 drop（清理）。"""
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest.fixture
async def db_session(test_engine, reset_db):
    """直接操作测试库的会话（DB 层测试用）。"""
    factory = async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        yield session


# ═══════════════════════════════════════════════════════════════════════
# API 客户端
# ═══════════════════════════════════════════════════════════════════════


@pytest.fixture
async def client(test_engine, reset_db):
    """FastAPI TestClient（httpx ASGITransport），get_db 覆盖为测试库会话。"""
    factory = async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)

    async def _override_get_db():
        async with factory() as session:
            yield session

    app.dependency_overrides[get_db] = _override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.pop(get_db, None)


# ═══════════════════════════════════════════════════════════════════════
# 种子 & 辅助
# ═══════════════════════════════════════════════════════════════════════


def _rand(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:8]}"


async def _register_user(client, username: str | None = None, password: str = "pass123456"):
    """注册一个用户，返回 (username, password, token)。"""
    username = username or _rand("user")
    resp = await client.post(
        "/api/v1/auth/register",
        json={"username": username, "password": password},
    )
    assert resp.status_code == 201, resp.text
    token = resp.json()["access_token"]
    return username, password, token


async def _auth_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
async def registered_user(client):
    """注册并返回 (username, password, token, headers)。"""
    username, password, token = await _register_user(client)
    return username, password, token, await _auth_headers(token)


@pytest.fixture
async def member_user(client, db_session, registered_user):
    """把 registered_user 提升为会员（chat 需要 get_current_member）。

    registered_user 与 db_session 共享同一测试引擎；先注册（API），再直插库提升会员。
    """
    from sqlalchemy import select

    username, password, token, headers = registered_user
    result = await db_session.execute(select(User).where(User.username == username))
    user = result.scalar_one()
    user.is_member = True
    await db_session.commit()
    return username, password, token, headers


@pytest.fixture
async def seed_subject(db_session) -> dict:
    """直接入库一个科目，返回 dict(id/code/name)。"""
    code = _rand("math")
    subject = Subject(
        code=code,
        name="高等数学(测试)",
        description="M1 测试种子科目",
        config={"formula_enabled": True},
    )
    db_session.add(subject)
    await db_session.commit()
    await db_session.refresh(subject)
    return {
        "id": str(subject.id),
        "code": subject.code,
        "name": subject.name,
    }


@pytest.fixture
async def seed_kp(db_session, seed_subject) -> dict:
    """直接入库一个知识点，返回 dict。"""
    kp = KnowledgePoint(
        subject_id=uuid.UUID(seed_subject["id"]),
        name="函数与极限(测试)",
        content="测试知识点内容",
        level=1,
    )
    db_session.add(kp)
    await db_session.commit()
    await db_session.refresh(kp)
    return {
        "id": str(kp.id),
        "subject_id": seed_subject["id"],
        "name": kp.name,
    }


@pytest.fixture
async def seed_question(db_session, seed_subject, seed_kp) -> dict:
    """直接入库一道单选题（answer 为 dict，与 SubmitAnswerRequest 兼容）。"""
    q = Question(
        subject_id=uuid.UUID(seed_subject["id"]),
        knowledge_point_id=uuid.UUID(seed_kp["id"]),
        type="single",
        content="函数 $f(x)=x^2$ 在 $x=0$ 处的导数为（　　）。",
        options={"A": "0", "B": "1", "C": "2", "D": "x"},
        answer={"correct": "A"},
        analysis="导数定义：$f'(0)=\\lim_{h\\to 0}\\frac{h^2}{h}=0$。",
        difficulty=2,
        source="self_built",
        status="active",
    )
    db_session.add(q)
    await db_session.commit()
    await db_session.refresh(q)
    return {
        "id": str(q.id),
        "subject_id": seed_subject["id"],
        "knowledge_point_id": seed_kp["id"],
        "answer": {"correct": "A"},
    }
