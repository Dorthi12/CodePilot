import pytest
from datetime import datetime, timezone, timedelta
import json
from src.services.session_service import SessionService
from src.config import settings


@pytest.mark.asyncio
async def test_session_lifecycle(test_redis):
    """Verifies creation, retrieval, and deletion of a server-side session."""
    session_service = SessionService(test_redis)

    # 1. Create session
    session_id, csrf_token, session_data = await session_service.create_session(
        user_id="user-123-uuid",
        github_id="gh-999",
        username="testuser"
    )

    assert session_id is not None
    assert len(session_id) > 20
    assert csrf_token is not None
    assert session_data.username == "testuser"

    # 2. Retrieve session
    retrieved = await session_service.get_session(session_id)
    assert retrieved is not None
    assert retrieved.user_id == "user-123-uuid"
    assert retrieved.github_id == "gh-999"
    assert retrieved.username == "testuser"
    assert retrieved.csrf_token == csrf_token

    # 3. Check TTL in Redis
    ttl = await test_redis.ttl(f"sess:{session_id}")
    assert 0 < ttl <= settings.SESSION_IDLE_TIMEOUT_SECONDS

    # 4. Delete session
    deleted = await session_service.delete_session(session_id)
    assert deleted is True

    # 5. Verify gone
    retrieved_after = await session_service.get_session(session_id)
    assert retrieved_after is None


@pytest.mark.asyncio
async def test_session_absolute_lifetime_expiration(test_redis):
    """Sessions older than 7 days should be considered expired even if idle TTL was refreshed."""
    session_service = SessionService(test_redis)

    session_id, _, _ = await session_service.create_session(
        user_id="user-456-uuid",
        github_id="gh-888",
        username="olduser"
    )

    # Manually backdate created_at in Redis to 8 days ago
    key = f"sess:{session_id}"
    raw = await test_redis.get(key)
    data = json.loads(raw)
    eight_days_ago = (datetime.now(timezone.utc) - timedelta(days=8)).isoformat()
    data["created_at"] = eight_days_ago
    await test_redis.set(key, json.dumps(data), ex=3600)

    # Now get_session should detect absolute expiration and return None
    retrieved = await session_service.get_session(session_id)
    assert retrieved is None

    # Key should be deleted from Redis
    assert await test_redis.get(key) is None


@pytest.mark.asyncio
async def test_session_rotation(test_redis):
    """Session rotation generates a new session_id while keeping user data, and revokes old session."""
    session_service = SessionService(test_redis)

    old_session_id, old_csrf, _ = await session_service.create_session(
        user_id="user-789-uuid",
        github_id="gh-777",
        username="rotateuser"
    )

    rotated = await session_service.rotate_session(old_session_id)
    assert rotated is not None
    new_session_id, new_csrf, new_data = rotated

    assert new_session_id != old_session_id
    assert new_csrf != old_csrf
    assert new_data.username == "rotateuser"

    # Old session must no longer exist
    assert await session_service.get_session(old_session_id) is None
    # New session must be valid
    assert await session_service.get_session(new_session_id) is not None
