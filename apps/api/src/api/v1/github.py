import logging
from typing import Optional
from fastapi import APIRouter, Depends, Query, Request, Response, status
from fastapi.responses import RedirectResponse

from src.config import settings
from src.schemas.common import APIResponse
from src.schemas.auth import (
    GitHubStatusResponse,
    GitHubAuthUrlResponse,
    MessageResponse
)
from src.schemas.repository import GitHubRepoListResponse, GitHubRepoPickerItem
from src.models.user import User
from src.services.github_service import GitHubService, GitHubOAuthError
from src.services.session_service import SessionService
from src.services.auth_service import AuthService
from src.services.crypto_service import crypto_service
from src.services.repository_service import RepositoryService
from src.api.deps import (
    get_github_service,
    get_session_service,
    get_auth_service,
    get_repository_service,
    get_current_user,
    verify_csrf
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/integrations/github", tags=["GitHub Integration"])


@router.get("/start")
async def start_github_oauth(
    request: Request,
    format: Optional[str] = Query(None, description="Set to 'json' to return auth URL as JSON"),
    github_service: GitHubService = Depends(get_github_service)
):
    """
    Initiates GitHub OAuth flow.
    Generates a secure state in Redis and redirects to GitHub, or returns JSON if requested.
    """
    auth_url, state = await github_service.create_authorization_url()

    # If client requests JSON
    accept_header = request.headers.get("accept", "")
    if format == "json" or "application/json" in accept_header:
        return APIResponse(
            data=GitHubAuthUrlResponse(
                authorization_url=auth_url,
                state=state
            )
        )

    # Browser default: 302 redirect directly to GitHub
    return RedirectResponse(url=auth_url, status_code=status.HTTP_302_FOUND)


@router.get("/callback")
async def github_oauth_callback(
    code: Optional[str] = Query(None),
    state: Optional[str] = Query(None),
    error: Optional[str] = Query(None),
    error_description: Optional[str] = Query(None),
    github_service: GitHubService = Depends(get_github_service),
    session_service: SessionService = Depends(get_session_service),
    auth_service: AuthService = Depends(get_auth_service)
):
    """
    Handles OAuth callback from GitHub.
    Validates state, exchanges code for access token, fetches user profile,
    upserts user record, and establishes HttpOnly cp_session.
    """
    login_url = f"{settings.FRONTEND_BASE_URL}/login"
    dashboard_url = f"{settings.FRONTEND_BASE_URL}/dashboard"

    # 1. Check for GitHub error redirect (e.g. user canceled)
    if error:
        logger.warning("GitHub OAuth returned error: %s (%s)", error, error_description)
        return RedirectResponse(
            url=f"{login_url}?error={error}&error_description={error_description or ''}",
            status_code=status.HTTP_302_FOUND
        )

    if not code or not state:
        logger.warning("GitHub OAuth callback missing code or state")
        return RedirectResponse(
            url=f"{login_url}?error=invalid_request&error_description=Missing+code+or+state",
            status_code=status.HTTP_302_FOUND
        )

    # 2. Validate and consume OAuth state (CSRF protection)
    state_valid = await github_service.validate_and_consume_state(state)
    if not state_valid:
        logger.warning("Invalid or expired OAuth state in callback: %s", state)
        return RedirectResponse(
            url=f"{login_url}?error=invalid_state&error_description=OAuth+session+expired+or+invalid",
            status_code=status.HTTP_302_FOUND
        )

    try:
        # 3. Exchange authorization code for access token
        token_data = await github_service.exchange_code_for_token(code)
        access_token = token_data["access_token"]
        scopes = token_data.get("scope")

        # 4. Fetch GitHub user profile and primary verified email
        profile = await github_service.fetch_user_profile(access_token)

        # 5. Create or update User and OAuthConnection in PostgreSQL
        user, is_new = await auth_service.upsert_github_user(
            github_profile=profile,
            access_token=access_token,
            scopes=scopes
        )

        # 6. Establish server-side session in Redis
        session_id, csrf_token, _ = await session_service.create_session(
            user_id=str(user.id),
            github_id=str(user.github_id),
            username=user.username
        )

        # 7. Create redirect response and attach HttpOnly session cookie + CSRF cookie
        redirect_resp = RedirectResponse(url=dashboard_url, status_code=status.HTTP_302_FOUND)

        # Session cookie (HttpOnly)
        redirect_resp.set_cookie(
            key=settings.SESSION_COOKIE_NAME,
            value=session_id,
            max_age=settings.SESSION_IDLE_TIMEOUT_SECONDS,
            path="/",
            domain=settings.COOKIE_DOMAIN,
            httponly=True,
            samesite=settings.COOKIE_SAMESITE,
            secure=settings.COOKIE_SECURE
        )

        # CSRF cookie (accessible to JS for double-submit / header inclusion)
        redirect_resp.set_cookie(
            key=settings.CSRF_COOKIE_NAME,
            value=csrf_token,
            max_age=settings.SESSION_IDLE_TIMEOUT_SECONDS,
            path="/",
            domain=settings.COOKIE_DOMAIN,
            httponly=False,
            samesite=settings.COOKIE_SAMESITE,
            secure=settings.COOKIE_SECURE
        )

        logger.info("Successfully authenticated user %s (is_new=%s)", user.username, is_new)
        return redirect_resp

    except GitHubOAuthError as e:
        logger.error("GitHub OAuth processing error: %s", e.message)
        return RedirectResponse(
            url=f"{login_url}?error={e.code}&error_description={e.message}",
            status_code=status.HTTP_302_FOUND
        )
    except Exception as e:
        logger.exception("Unexpected error during GitHub OAuth callback: %s", e)
        return RedirectResponse(
            url=f"{login_url}?error=internal_error&error_description=Authentication+failed+internally",
            status_code=status.HTTP_302_FOUND
        )


@router.get("/status", response_model=APIResponse[GitHubStatusResponse])
async def get_github_status(
    current_user: User = Depends(get_current_user),
    auth_service: AuthService = Depends(get_auth_service)
) -> APIResponse[GitHubStatusResponse]:
    """
    Checks the status of the current user's GitHub integration.
    """
    conn = await auth_service.get_github_connection(str(current_user.id))
    if not conn:
        return APIResponse(
            data=GitHubStatusResponse(
                connected=False,
                provider="github"
            )
        )

    return APIResponse(
        data=GitHubStatusResponse(
            connected=True,
            provider="github",
            username=current_user.username,
            scopes=conn.scopes,
            connected_at=conn.created_at
        )
    )


@router.delete("", response_model=APIResponse[MessageResponse])
async def disconnect_github(
    current_user: User = Depends(get_current_user),
    auth_service: AuthService = Depends(get_auth_service),
    _: None = Depends(verify_csrf)
) -> APIResponse[MessageResponse]:
    """
    Disconnects and removes the current user's GitHub integration.
    """
    disconnected = await auth_service.disconnect_github(str(current_user.id))
    if not disconnected:
        return APIResponse(
            data=MessageResponse(message="No active GitHub integration found to disconnect")
        )

    return APIResponse(
        data=MessageResponse(message="GitHub integration successfully disconnected")
    )


@router.get("/repositories", response_model=APIResponse[GitHubRepoListResponse])
async def list_user_github_repositories(
    page: int = Query(1, ge=1),
    per_page: int = Query(30, ge=1, le=100),
    search: Optional[str] = Query(None),
    sort: str = Query("updated"),
    current_user: User = Depends(get_current_user),
    auth_service: AuthService = Depends(get_auth_service),
    github_service: GitHubService = Depends(get_github_service),
    repo_service: RepositoryService = Depends(get_repository_service)
) -> APIResponse[GitHubRepoListResponse]:
    """
    Fetches repositories accessible to the current authenticated GitHub user.
    Cross-references with CodePilot database to indicate which repositories are already imported.
    """
    conn = await auth_service.get_github_connection(str(current_user.id))
    if not conn or not conn.encrypted_access_token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "GITHUB_NOT_CONNECTED",
                "message": "GitHub account is not connected. Please connect your GitHub account first."
            }
        )

    try:
        access_token = crypto_service.decrypt_token(conn.encrypted_access_token)
    except Exception as e:
        logger.error("Failed to decrypt access token for user %s: %s", current_user.id, e)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "code": "INVALID_TOKEN",
                "message": "GitHub access token could not be decrypted. Please re-authenticate."
            }
        )

    try:
        raw_repos = await github_service.list_user_repositories(
            access_token=access_token,
            page=page,
            per_page=per_page,
            search=search,
            sort=sort
        )
    except GitHubOAuthError as e:
        status_code = status.HTTP_400_BAD_REQUEST
        if e.code == "GITHUB_UNAUTHORIZED":
            status_code = status.HTTP_401_UNAUTHORIZED
        elif e.code == "RATE_LIMIT_EXCEEDED":
            status_code = status.HTTP_429_TOO_MANY_REQUESTS
        raise HTTPException(
            status_code=status_code,
            detail={"code": e.code, "message": e.message}
        )

    # Get set of already imported provider_repo_ids
    existing_repos = await repo_service.list_repositories(user_id=current_user.id)
    imported_ids = {r.provider_repo_id for r in existing_repos}

    items = []
    for r in raw_repos:
        items.append(
            GitHubRepoPickerItem(
                id=r["id"],
                name=r["name"],
                full_name=r["full_name"],
                owner=r["owner"]["login"],
                owner_avatar_url=r["owner"].get("avatar_url"),
                html_url=r["html_url"],
                description=r.get("description"),
                private=r.get("private", False),
                visibility="private" if r.get("private") else "public",
                language=r.get("language"),
                default_branch=r.get("default_branch") or "main",
                stargazers_count=r.get("stargazers_count", 0),
                forks_count=r.get("forks_count", 0),
                updated_at=r.get("updated_at") or "",
                is_imported=str(r["id"]) in imported_ids
            )
        )

    return APIResponse(
        data=GitHubRepoListResponse(
            repositories=items,
            page=page,
            per_page=per_page,
            has_more=len(raw_repos) == per_page
        )
    )
