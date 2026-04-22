import uuid
from collections.abc import AsyncGenerator

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import StaticPool, event
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.api.v1.auth import _get_audit_session_factory
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
TestingSession = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


@event.listens_for(engine.sync_engine, "connect")
def _set_sqlite_compat(dbapi_conn, _connection_record):
    from datetime import UTC, datetime

    dbapi_conn.create_function("gen_random_uuid", 0, lambda: str(uuid.uuid4()))
    dbapi_conn.create_function("now", 0, lambda: datetime.now(UTC).isoformat())


class FakeRedis:
    def __init__(self):
        self._store: dict[str, str] = {}
        self._counters: dict[str, int] = {}

    async def setex(self, key: str, ttl: int, value: str) -> None:
        self._store[key] = value

    async def exists(self, key: str) -> int:
        return 1 if key in self._store or key in self._counters else 0

    async def incr(self, key: str) -> int:
        self._counters[key] = self._counters.get(key, 0) + 1
        return self._counters[key]

    async def expire(self, key: str, ttl: int) -> bool:
        return key in self._counters or key in self._store

    async def ttl(self, key: str) -> int:
        if key in self._counters or key in self._store:
            return 60
        return -2

    async def flushall(self) -> None:
        self._store.clear()
        self._counters.clear()

    async def aclose(self) -> None:
        pass


_fake_redis = FakeRedis()


async def _override_get_db() -> AsyncGenerator[AsyncSession, None]:
    async with TestingSession() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def _override_get_redis() -> AsyncGenerator[FakeRedis, None]:
    yield _fake_redis


def _override_audit_session_factory():
    return TestingSession


app.dependency_overrides[get_db] = _override_get_db
app.dependency_overrides[get_redis] = _override_get_redis
app.dependency_overrides[_get_audit_session_factory] = _override_audit_session_factory


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
    async with TestingSession() as session:
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


async def _create_tenant_with_owner(
    name: str, slug: str, owner_email: str, owner_password: str = "SecurePass123"
) -> dict:
    async with TestingSession() as session:
        tenant = Tenant(id=uuid.uuid4(), name=name, slug=slug)
        session.add(tenant)
        await session.flush()

        owner = User(
            id=uuid.uuid4(),
            tenant_id=tenant.id,
            email=owner_email,
            hashed_password=hash_password(owner_password),
            full_name=f"Owner {name}",
            role=Role.OWNER,
        )
        session.add(owner)
        await session.flush()
        tenant.owner_id = owner.id
        await session.commit()

        return {
            "tenant_id": str(tenant.id),
            "owner_id": str(owner.id),
            "owner_email": owner_email,
            "owner_password": owner_password,
            "slug": slug,
        }


async def _create_user_in_tenant(
    tenant_id: str, email: str, role: Role, password: str = "SecurePass123"
) -> dict:
    async with TestingSession() as session:
        user = User(
            id=uuid.uuid4(),
            tenant_id=uuid.UUID(tenant_id),
            email=email,
            hashed_password=hash_password(password),
            full_name=f"{role.value} {email}",
            role=role,
        )
        session.add(user)
        await session.commit()
        return {"user_id": str(user.id), "email": email, "password": password}


async def _login(client: AsyncClient, email: str, password: str) -> AsyncClient:
    resp = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    )
    assert resp.status_code == 200, f"login failed: {resp.text}"
    return client


@pytest.fixture
async def tenant_a() -> dict:
    return await _create_tenant_with_owner("Studio A", "studio-a", "owner_a@example.com")


@pytest.fixture
async def tenant_b() -> dict:
    return await _create_tenant_with_owner("Studio B", "studio-b", "owner_b@example.com")


@pytest.fixture
async def owner_client_a(tenant_a: dict) -> AsyncGenerator[AsyncClient, None]:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        await _login(ac, tenant_a["owner_email"], tenant_a["owner_password"])
        yield ac


@pytest.fixture
async def owner_client_b(tenant_b: dict) -> AsyncGenerator[AsyncClient, None]:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        await _login(ac, tenant_b["owner_email"], tenant_b["owner_password"])
        yield ac


@pytest.fixture
async def model_client_a(tenant_a: dict) -> AsyncGenerator[AsyncClient, None]:
    model = await _create_user_in_tenant(tenant_a["tenant_id"], "model_a@example.com", Role.MODEL)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        await _login(ac, model["email"], model["password"])
        yield ac


@pytest.fixture
async def monitor_client_a(tenant_a: dict) -> AsyncGenerator[AsyncClient, None]:
    monitor = await _create_user_in_tenant(
        tenant_a["tenant_id"], "monitor_a@example.com", Role.MONITOR
    )
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        await _login(ac, monitor["email"], monitor["password"])
        yield ac


@pytest.fixture
async def inactive_tenant_user() -> dict:
    async with TestingSession() as session:
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
