import asyncio
import os
import sys

# Add apps/api to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pytest
import pytest_asyncio
import fakeredis.aioredis
from typing import AsyncGenerator
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

# Force testing configuration
os.environ["ENVIRONMENT"] = "testing"
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///:memory:"
os.environ["REDIS_URL"] = "redis://localhost:6379/15"
os.environ["GITHUB_CLIENT_ID"] = "test-github-client-id"
os.environ["GITHUB_CLIENT_SECRET"] = "test-github-client-secret"
os.environ["SESSION_SECRET"] = "test-session-secret-key-at-least-32-bytes-long"
os.environ["TOKEN_ENCRYPTION_KEY"] = "test-token-encryption-key-32-chars!"

from src.config import settings
from src.database import Base, get_db
from src.redis_client import get_redis
from src.main import app
from src.models.user import User
from src.models.oauth_connection import OAuthConnection
from src.services.crypto_service import crypto_service
from src.services.session_service import SessionService


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="function")
async def test_redis():
    """Provides a clean in-memory FakeRedis instance for each test."""
    fake_r = fakeredis.aioredis.FakeRedis(decode_responses=True)
    yield fake_r
    await fake_r.flushall()
    await fake_r.aclose()


@pytest_asyncio.fixture(scope="function")
async def test_db():
    """Provides an isolated SQLite in-memory database with created tables."""
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        echo=False,
        future=True,
        connect_args={"check_same_thread": False}
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(
        bind=engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False
    )

    async with session_factory() as session:
        yield session

    await engine.dispose()


@pytest_asyncio.fixture(scope="function")
async def client(test_db: AsyncSession, test_redis: fakeredis.aioredis.FakeRedis) -> AsyncGenerator[AsyncClient, None]:
    """Provides an authenticated AsyncClient with mocked db and redis dependencies."""
    async def override_get_db():
        yield test_db

    async def override_get_redis():
        return test_redis

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_redis] = override_get_redis

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
        yield ac

    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def sample_user(test_db: AsyncSession) -> User:
    """Creates and persists a sample User and OAuthConnection in test DB."""
    user = User(
        github_id="12345678",
        username="athena_dev",
        name="Athena Developer",
        email="athena@example.com",
        avatar_url="https://github.com/images/athena.png"
    )
    test_db.add(user)
    await test_db.flush()

    oauth_conn = OAuthConnection(
        user_id=user.id,
        provider="github",
        provider_user_id="12345678",
        encrypted_access_token=crypto_service.encrypt_token("gho_sample_token_xyz"),
        scopes="read:user,user:email"
    )
    test_db.add(oauth_conn)
    await test_db.commit()
    await test_db.refresh(user)
    return user


@pytest_asyncio.fixture
async def authenticated_session(test_redis: fakeredis.aioredis.FakeRedis, sample_user: User):
    """Establishes a valid session in Redis for sample_user and returns (session_id, csrf_token)."""
    session_service = SessionService(test_redis)
    session_id, csrf_token, session_data = await session_service.create_session(
        user_id=str(sample_user.id),
        github_id=sample_user.github_id,
        username=sample_user.username
    )
    return {
        "session_id": session_id,
        "csrf_token": csrf_token,
        "session_data": session_data,
        "user": sample_user
    }
