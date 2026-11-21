import json
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any, Tuple
import redis.asyncio as aioredis

from src.config import settings
from src.services.crypto_service import crypto_service

logger = logging.getLogger(__name__)


class SessionData:
    def __init__(
        self,
        session_id: str,
        user_id: str,
        github_id: str,
        username: str,
        csrf_token: str,
        created_at: str,
        last_seen: str
    ):
        self.session_id = session_id
        self.user_id = user_id
        self.github_id = github_id
        self.username = username
        self.csrf_token = csrf_token
        self.created_at = created_at
        self.last_seen = last_seen

    def to_dict(self) -> Dict[str, Any]:
        return {
            "session_id": self.session_id,
            "user_id": self.user_id,
            "github_id": self.github_id,
            "username": self.username,
            "csrf_token": self.csrf_token,
            "created_at": self.created_at,
            "last_seen": self.last_seen,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SessionData":
        return cls(
            session_id=data.get("session_id", ""),
            user_id=data["user_id"],
            github_id=data["github_id"],
            username=data["username"],
            csrf_token=data["csrf_token"],
            created_at=data["created_at"],
            last_seen=data.get("last_seen", data["created_at"])
        )


class SessionService:
    def __init__(self, redis: aioredis.Redis):
        self.redis = redis

    def _get_key(self, session_id: str) -> str:
        return f"sess:{session_id}"

    async def create_session(
        self,
        user_id: str,
        github_id: str,
        username: str
    ) -> Tuple[str, str, SessionData]:
        """
        Creates a new server-side session in Redis.
        Returns (session_id, csrf_token, SessionData).
        """
        session_id = crypto_service.generate_random_token(32)
        csrf_token = crypto_service.generate_random_token(32)
        now_iso = datetime.now(timezone.utc).isoformat()

        session_data = SessionData(
            session_id=session_id,
            user_id=str(user_id),
            github_id=str(github_id),
            username=username,
            csrf_token=csrf_token,
            created_at=now_iso,
            last_seen=now_iso
        )

        key = self._get_key(session_id)
        # Store as JSON string with idle timeout
        await self.redis.set(
            key,
            json.dumps(session_data.to_dict()),
            ex=settings.SESSION_IDLE_TIMEOUT_SECONDS
        )

        logger.debug("Created session %s for user %s", session_id[:8], username)
        return session_id, csrf_token, session_data

    async def get_session(self, session_id: str) -> Optional[SessionData]:
        """
        Retrieves and validates a session from Redis.
        Enforces absolute lifetime check and updates idle TTL.
        """
        if not session_id:
            return None

        key = self._get_key(session_id)
        raw_data = await self.redis.get(key)
        if not raw_data:
            return None

        try:
            data = json.loads(raw_data)
            session = SessionData.from_dict(data)

            # Check absolute lifetime (7 days)
            created_at = datetime.fromisoformat(session.created_at)
            now = datetime.now(timezone.utc)
            if now - created_at > timedelta(seconds=settings.SESSION_ABSOLUTE_LIFETIME_SECONDS):
                logger.info("Session %s exceeded absolute lifetime of %s seconds", session_id[:8], settings.SESSION_ABSOLUTE_LIFETIME_SECONDS)
                await self.redis.delete(key)
                return None

            # Touch session: update last_seen and refresh idle expiration
            session.last_seen = now.isoformat()
            remaining_absolute = int((created_at + timedelta(seconds=settings.SESSION_ABSOLUTE_LIFETIME_SECONDS) - now).total_seconds())
            ttl = min(settings.SESSION_IDLE_TIMEOUT_SECONDS, max(remaining_absolute, 1))

            await self.redis.set(key, json.dumps(session.to_dict()), ex=ttl)
            return session
        except Exception as e:
            logger.error("Error deserializing session %s: %s", session_id[:8], e)
            return None

    async def rotate_session(self, old_session_id: str) -> Optional[Tuple[str, str, SessionData]]:
        """
        Rotates session ID while preserving user info (anti-session-fixation).
        """
        old_session = await self.get_session(old_session_id)
        if not old_session:
            return None

        # Delete old session
        await self.delete_session(old_session_id)

        # Create new session for the same user
        return await self.create_session(
            user_id=old_session.user_id,
            github_id=old_session.github_id,
            username=old_session.username
        )

    async def delete_session(self, session_id: str) -> bool:
        """Invalidates a session on logout."""
        if not session_id:
            return False
        key = self._get_key(session_id)
        deleted = await self.redis.delete(key)
        logger.debug("Deleted session %s: %s", session_id[:8], deleted > 0)
        return deleted > 0
