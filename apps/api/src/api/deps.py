import uuid
from typing import Optional
from fastapi import Request, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
import redis.asyncio as aioredis

from src.config import settings
from src.database import get_db
from src.redis_client import get_redis
from src.services.session_service import SessionService, SessionData
from src.services.auth_service import AuthService
from src.services.github_service import GitHubService
from src.services.repository_service import RepositoryService
from src.services.clone_service import CloneService
from src.services.ingestion_service import IngestionService
from src.services.summary_service import SummaryService
from src.services.ai_service import AIServiceBridge
from src.models.user import User


def get_session_service(redis: aioredis.Redis = Depends(get_redis)) -> SessionService:
    return SessionService(redis)


def get_github_service(redis: aioredis.Redis = Depends(get_redis)) -> GitHubService:
    return GitHubService(redis)


def get_auth_service(
    db: AsyncSession = Depends(get_db),
    session_service: SessionService = Depends(get_session_service)
) -> AuthService:
    return AuthService(db, session_service)


def get_repository_service(
    db: AsyncSession = Depends(get_db),
    github_service: GitHubService = Depends(get_github_service),
    auth_service: AuthService = Depends(get_auth_service)
) -> RepositoryService:
    return RepositoryService(db, github_service, auth_service)


def get_clone_service(
    db: AsyncSession = Depends(get_db),
    redis: aioredis.Redis = Depends(get_redis),
    auth_service: AuthService = Depends(get_auth_service),
    github_service: GitHubService = Depends(get_github_service)
) -> CloneService:
    return CloneService(db, redis, auth_service, github_service)


def get_ingestion_service(
    db: AsyncSession = Depends(get_db)
) -> IngestionService:
    return IngestionService(db)


def get_summary_service(
    db: AsyncSession = Depends(get_db)
) -> SummaryService:
    return SummaryService(db)


def get_ai_service(
    db: AsyncSession = Depends(get_db)
) -> AIServiceBridge:
    return AIServiceBridge(db)


async def get_current_session(
    request: Request,
    session_service: SessionService = Depends(get_session_service)
) -> SessionData:
    """
    Extracts and validates the session from the HttpOnly cp_session cookie.
    Raises 401 UNAUTHENTICATED if session is invalid or missing.
    """
    session_id = request.cookies.get(settings.SESSION_COOKIE_NAME)
    if not session_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "code": "UNAUTHENTICATED",
                "message": "Authentication required. No session cookie provided."
            }
        )

    session = await session_service.get_session(session_id)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "code": "UNAUTHENTICATED",
                "message": "Session is invalid, expired, or was logged out."
            }
        )

    return session


async def get_optional_session(
    request: Request,
    session_service: SessionService = Depends(get_session_service)
) -> Optional[SessionData]:
    """Retrieves session if present, otherwise returns None."""
    session_id = request.cookies.get(settings.SESSION_COOKIE_NAME)
    if not session_id:
        return None
    return await session_service.get_session(session_id)


async def get_current_user(
    session: SessionData = Depends(get_current_session),
    auth_service: AuthService = Depends(get_auth_service)
) -> User:
    """
    Resolves the authenticated User from database using current session.
    """
    user_uuid = uuid.UUID(session.user_id)
    user = await auth_service.get_user_by_id(user_uuid)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "code": "UNAUTHENTICATED",
                "message": "Authenticated user record no longer exists."
            }
        )
    return user


async def verify_csrf(
    request: Request,
    session: SessionData = Depends(get_current_session)
) -> None:
    """
    Verifies CSRF token for state-changing requests.
    Validates X-CSRF-Token header against the active session's csrf_token.
    Validates Origin / Referer against allowed origins.
    """
    # 1. Check Origin / Referer
    origin = request.headers.get("origin")
    if origin:
        normalized_origin = origin.rstrip("/")
        allowed = [o.rstrip("/") for o in settings.CORS_ALLOWED_ORIGINS]
        if normalized_origin not in allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "code": "CSRF_FAILED",
                    "message": f"Untrusted origin: {origin}"
                }
            )

    # 2. Check X-CSRF-Token header
    csrf_header = request.headers.get("x-csrf-token")
    if not csrf_header:
        # Check if sent in cookie double-submit as fallback
        csrf_header = request.cookies.get(settings.CSRF_COOKIE_NAME)

    if not csrf_header or csrf_header != session.csrf_token:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": "CSRF_FAILED",
                "message": "Invalid or missing CSRF token."
            }
        )
