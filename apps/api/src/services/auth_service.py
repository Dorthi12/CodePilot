import logging
import uuid
from typing import Optional, Tuple, Union
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from src.models.user import User
from src.models.oauth_connection import OAuthConnection
from src.services.crypto_service import crypto_service
from src.services.session_service import SessionService, SessionData

logger = logging.getLogger(__name__)


class AuthService:
    def __init__(self, db: AsyncSession, session_service: SessionService):
        self.db = db
        self.session_service = session_service

    async def get_user_by_id(self, user_id: Union[uuid.UUID, str]) -> Optional[User]:
        uid = uuid.UUID(str(user_id)) if not isinstance(user_id, uuid.UUID) else user_id
        result = await self.db.execute(select(User).where(User.id == uid))
        return result.scalar_one_or_none()

    async def get_user_by_github_id(self, github_id: str) -> Optional[User]:
        result = await self.db.execute(select(User).where(User.github_id == str(github_id)))
        return result.scalar_one_or_none()

    async def upsert_github_user(
        self,
        github_profile: dict,
        access_token: str,
        scopes: Optional[str] = None
    ) -> Tuple[User, bool]:
        """
        Creates or updates a User and their OAuthConnection.
        Returns (User, is_new_user: bool).
        """
        github_id = str(github_profile["github_id"])
        username = github_profile["username"]
        name = github_profile.get("name")
        email = github_profile.get("email")
        avatar_url = github_profile.get("avatar_url")

        # 1. Look up user by github_id
        user = await self.get_user_by_github_id(github_id)
        is_new_user = False

        if user is None:
            # First time registration
            user = User(
                github_id=github_id,
                username=username,
                name=name,
                email=email,
                avatar_url=avatar_url
            )
            self.db.add(user)
            await self.db.flush()  # Populates user.id
            is_new_user = True
            logger.info("Registered new user: %s (github_id: %s)", username, github_id)
        else:
            # Existing user - update profile info
            user.username = username
            user.name = name or user.name
            user.avatar_url = avatar_url or user.avatar_url
            if email:
                user.email = email
            logger.info("Existing user login: %s (id: %s)", username, user.id)

        # 2. Encrypt access token
        encrypted_token = crypto_service.encrypt_token(access_token)

        # 3. Upsert OAuthConnection
        oauth_stmt = select(OAuthConnection).where(
            OAuthConnection.user_id == user.id,
            OAuthConnection.provider == "github"
        )
        oauth_result = await self.db.execute(oauth_stmt)
        oauth_conn = oauth_result.scalar_one_or_none()

        if oauth_conn is None:
            oauth_conn = OAuthConnection(
                user_id=user.id,
                provider="github",
                provider_user_id=github_id,
                encrypted_access_token=encrypted_token,
                scopes=scopes
            )
            self.db.add(oauth_conn)
        else:
            oauth_conn.provider_user_id = github_id
            oauth_conn.encrypted_access_token = encrypted_token
            oauth_conn.scopes = scopes or oauth_conn.scopes

        await self.db.commit()
        await self.db.refresh(user)

        return user, is_new_user

    async def get_github_connection(self, user_id: Union[uuid.UUID, str]) -> Optional[OAuthConnection]:
        uid = uuid.UUID(str(user_id)) if not isinstance(user_id, uuid.UUID) else user_id
        stmt = select(OAuthConnection).where(
            OAuthConnection.user_id == uid,
            OAuthConnection.provider == "github"
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def disconnect_github(self, user_id: Union[uuid.UUID, str]) -> bool:
        """Removes the user's GitHub OAuth connection."""
        conn = await self.get_github_connection(user_id)
        if conn:
            await self.db.delete(conn)
            await self.db.commit()
            return True
        return False
