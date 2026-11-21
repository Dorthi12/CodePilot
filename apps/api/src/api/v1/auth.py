from fastapi import APIRouter, Depends, Response
from src.config import settings
from src.schemas.common import APIResponse
from src.schemas.user import UserResponse
from src.schemas.auth import MessageResponse
from src.models.user import User
from src.services.session_service import SessionService, SessionData
from src.api.deps import (
    get_current_user,
    get_current_session,
    get_session_service,
    verify_csrf
)

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.get("/me", response_model=APIResponse[UserResponse])
async def get_me(current_user: User = Depends(get_current_user)) -> APIResponse[UserResponse]:
    """
    Returns the currently authenticated user based on the active session.
    """
    return APIResponse(
        data=UserResponse.model_validate(current_user)
    )


@router.post("/logout", response_model=APIResponse[MessageResponse])
async def logout(
    response: Response,
    session: SessionData = Depends(get_current_session),
    session_service: SessionService = Depends(get_session_service),
    _: None = Depends(verify_csrf)
) -> APIResponse[MessageResponse]:
    """
    Ends the current user session, deleting it from Redis and clearing cookies.
    """
    # 1. Delete session from Redis
    await session_service.delete_session(session.session_id)

    # 2. Clear cookies
    response.delete_cookie(
        key=settings.SESSION_COOKIE_NAME,
        path="/",
        domain=settings.COOKIE_DOMAIN,
        httponly=True,
        samesite=settings.COOKIE_SAMESITE,
        secure=settings.COOKIE_SECURE
    )
    response.delete_cookie(
        key=settings.CSRF_COOKIE_NAME,
        path="/",
        domain=settings.COOKIE_DOMAIN,
        httponly=False,
        samesite=settings.COOKIE_SAMESITE,
        secure=settings.COOKIE_SECURE
    )

    return APIResponse(
        data=MessageResponse(message="Successfully logged out")
    )
