import uuid
from collections.abc import AsyncGenerator

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import StaticPool, event
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.security import hash_password
from app.database import get_db
from app.main import app
from app.models.base import Base
from app.models.tenant import Tenant
from app.models.user import Role, User
from app.redis import get_redis

TEST_DB_URL = "sqlite+aiosqlite:///:memory:"

engine = create_async_engine(
    TEST_DB_URL,
    echo=False,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
test_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


@event.listens_for(engine.sync_engine, "connect")
def _set_sqlite_compat(dbapi_conn, _connection_record):
    from datetime import UTC, datetime

    dbapi_conn.create_function("gen_random_uuid", 0, lambda: str(uuid.uuid4()))
    dbapi_conn.create_function("now", 0, lambda: datetime.now(UTC).isoformat())


class FakeRedis:
    def __init__(self):
        self._store: dict[str, str] = {}

    async def setex(self, key: str, ttl: int, value: str) -> None:
        self._store[key] = value

    async def exists(self, key: str) -> int:
        return 1 if key in self._store else 0

    async def flushall(self) -> None:
        self._store.clear()

    async def aclose(self) -> None:
        pass


_fake_redis = FakeRedis()


async def _override_get_db() -> AsyncGenerator[AsyncSession, None]:
    async with test_session() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def _override_get_redis() -> AsyncGenerator[FakeRedis, None]:
    yield _fake_redis


app.dependency_overrides[get_db] = _override_get_db
app.dependency_overrides[get_redis] = _override_get_redis


@pytest.fixture(autouse=True)
async def _setup_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await _fake_redis.flushall()


@pytest.fixture
async def client() -> AsyncGenerator[AsyncClient, None]:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.fixture
async def seed_tenant_and_owner() -> dict:
    async with test_session() as session:
        tenant = Tenant(
            id=uuid.uuid4(),
            name="Test Studio",
            slug="test-studio",
        )
        session.add(tenant)
        await session.flush()

        owner = User(
            id=uuid.uuid4(),
            tenant_id=tenant.id,
            email="owner@test.com",
            hashed_password=hash_password("SecurePass123"),
            full_name="Test Owner",
            role=Role.OWNER,
        )
        session.add(owner)
        await session.flush()

        tenant.owner_id = owner.id
        await session.commit()

        return {
            "tenant_id": str(tenant.id),
            "user_id": str(owner.id),
            "email": "owner@test.com",
            "password": "SecurePass123",
        }


@pytest.fixture
async def inactive_tenant_user() -> dict:
    async with test_session() as session:
        tenant = Tenant(
            id=uuid.uuid4(),
            name="Suspended Studio",
            slug="suspended-studio",
            is_active=False,
        )
        session.add(tenant)
        await session.flush()

        user = User(
            id=uuid.uuid4(),
            tenant_id=tenant.id,
            email="suspended@test.com",
            hashed_password=hash_password("SecurePass123"),
            full_name="Suspended User",
            role=Role.OWNER,
        )
        session.add(user)
        await session.commit()

        return {"email": "suspended@test.com", "password": "SecurePass123"}
