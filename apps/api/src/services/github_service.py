import json
import logging
import re
from datetime import datetime, timezone
from typing import Optional, Dict, Any, Tuple, List
from urllib.parse import urlencode, urlparse
import httpx
import redis.asyncio as aioredis

from src.config import settings
from src.services.crypto_service import crypto_service

logger = logging.getLogger(__name__)

GITHUB_HTTP_USER_AGENT = "CodePilot/1.0"
GITHUB_OAUTH_AUTHORIZE_URL = "https://github.com/login/oauth/authorize"
GITHUB_OAUTH_ACCESS_TOKEN_URL = "https://github.com/login/oauth/access_token"
GITHUB_API_USER_URL = "https://api.github.com/user"
GITHUB_API_EMAILS_URL = "https://api.github.com/user/emails"
GITHUB_API_REPOS_URL = "https://api.github.com/repos"
GITHUB_API_USER_REPOS_URL = "https://api.github.com/user/repos"

# Strict regex for GitHub username / organization:
# Must start with alphanumeric, 1-39 chars of alphanumeric, hyphens, underscores, dots
GITHUB_OWNER_REGEX = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_.-]{0,38}$")

# Strict regex for GitHub repository name:
# Must start with alphanumeric or underscore, 1-100 chars
GITHUB_REPO_REGEX = re.compile(r"^[a-zA-Z0-9_][a-zA-Z0-9_.-]{0,99}$")


def parse_github_url(url: str) -> Tuple[str, str]:
    """
    Parses and strictly validates a GitHub repository URL or 'owner/repo' identifier.
    Guards against SSRF, directory traversal, malicious schemes, internal hostnames, and arbitrary networks.
    Returns (owner, name).
    """
    if not url or not isinstance(url, str):
        raise GitHubOAuthError("Invalid repository URL provided.", code="INVALID_URL")

    cleaned = url.strip()

    # If an explicit scheme is provided (e.g. http://, https://, ftp://, git://)
    if "://" in cleaned:
        try:
            parsed = urlparse(cleaned)
        except Exception:
            raise GitHubOAuthError("Malformed repository URL.", code="INVALID_URL")

        # Strict scheme validation: only http or https
        if parsed.scheme.lower() not in ("http", "https"):
            raise GitHubOAuthError("Only HTTPS/HTTP GitHub URLs are permitted.", code="INVALID_URL_SCHEME")

        # Strict hostname validation: ONLY github.com or www.github.com
        hostname = (parsed.hostname or "").lower()
        if hostname not in ("github.com", "www.github.com"):
            raise GitHubOAuthError(
                f"Invalid repository host: '{hostname}'. Only repositories hosted on github.com are supported.",
                code="INVALID_URL_HOST"
            )

        path_segments = [seg for seg in parsed.path.strip("/").split("/") if seg]
        if len(path_segments) < 2:
            raise GitHubOAuthError(
                "Repository URL must specify both owner and repository name (e.g. https://github.com/owner/repository).",
                code="INVALID_URL_PATH"
            )

        owner = path_segments[0]
        repo = path_segments[1]
    else:
        # Bare domain prefix or owner/repo format
        if cleaned.startswith("github.com/"):
            cleaned = cleaned[len("github.com/"):]
        elif cleaned.startswith("www.github.com/"):
            cleaned = cleaned[len("www.github.com/"):]

        parts = [p.strip() for p in cleaned.strip("/").split("/") if p.strip()]
        if len(parts) != 2:
            raise GitHubOAuthError(
                "Repository must be specified as 'owner/repository' or a full github.com URL.",
                code="INVALID_URL_PATH"
            )
        owner = parts[0]
        repo = parts[1]

    if repo.endswith(".git"):
        repo = repo[:-4]

    # Validate against GitHub identifier regexes and directory traversal
    if owner in (".", "..") or repo in (".", "..") or not GITHUB_OWNER_REGEX.match(owner) or not GITHUB_REPO_REGEX.match(repo):
        raise GitHubOAuthError(
            f"Invalid repository identifier: '{owner}/{repo}'.",
            code="INVALID_REPOSITORY_IDENTIFIER"
        )

    return owner, repo


class GitHubOAuthError(Exception):
    def __init__(self, message: str, code: str = "GITHUB_OAUTH_ERROR"):
        super().__init__(message)
        self.message = message
        self.code = code


class GitHubService:
    def __init__(self, redis: aioredis.Redis):
        self.redis = redis

    def _state_key(self, state: str) -> str:
        return f"oauth:state:{state}"

    async def create_authorization_url(self) -> Tuple[str, str]:
        """
        Generates a state, stores it in Redis with 10 min TTL, and returns
        (authorization_url, state).
        """
        state = crypto_service.generate_random_token(32)
        key = self._state_key(state)

        # Store in Redis with 10 min (600s) TTL
        state_data = {
            "created_at": datetime.now(timezone.utc).isoformat()
        }
        await self.redis.set(key, json.dumps(state_data), ex=600)

        # Build GitHub OAuth Authorize URL
        params = {
            "client_id": settings.GITHUB_CLIENT_ID,
            "redirect_uri": settings.GITHUB_REDIRECT_URI,
            "scope": settings.GITHUB_SCOPES,
            "state": state
        }
        auth_url = f"{GITHUB_OAUTH_AUTHORIZE_URL}?{urlencode(params)}"

        return auth_url, state

    async def validate_and_consume_state(self, state: str) -> bool:
        """
        Validates the OAuth state against Redis and deletes it immediately (single use).
        """
        if not state:
            return False

        key = self._state_key(state)
        data = await self.redis.get(key)
        if not data:
            logger.warning("Invalid or expired OAuth state provided: %s", state[:8] if state else "")
            return False

        # Delete immediately so it cannot be reused
        await self.redis.delete(key)
        return True

    async def exchange_code_for_token(self, code: str) -> Dict[str, Any]:
        """
        Exchanges GitHub authorization code for access token.
        """
        if not settings.GITHUB_CLIENT_ID or not settings.GITHUB_CLIENT_SECRET:
            raise GitHubOAuthError(
                "GitHub OAuth client credentials are not configured",
                code="GITHUB_NOT_CONFIGURED"
            )

        payload = {
            "client_id": settings.GITHUB_CLIENT_ID,
            "client_secret": settings.GITHUB_CLIENT_SECRET,
            "code": code,
            "redirect_uri": settings.GITHUB_REDIRECT_URI,
        }
        headers = {
            "Accept": "application/json",
            "User-Agent": GITHUB_HTTP_USER_AGENT
        }

        async with httpx.AsyncClient(timeout=15.0) as client:
            try:
                response = await client.post(GITHUB_OAUTH_ACCESS_TOKEN_URL, json=payload, headers=headers)
                response.raise_for_status()
                token_data = response.json()
            except httpx.HTTPStatusError as e:
                logger.error("GitHub token exchange HTTP error: %s", e.response.text)
                raise GitHubOAuthError("Failed to exchange code with GitHub", code="GITHUB_API_ERROR")
            except Exception as e:
                logger.error("GitHub token exchange network error: %s", e)
                raise GitHubOAuthError("Network error contacting GitHub", code="GITHUB_UNAVAILABLE")

        if "error" in token_data:
            error_desc = token_data.get("error_description", token_data["error"])
            logger.error("GitHub OAuth returned error: %s", error_desc)
            raise GitHubOAuthError(f"GitHub OAuth error: {error_desc}", code="GITHUB_OAUTH_FAILED")

        if "access_token" not in token_data:
            logger.error("GitHub OAuth response missing access_token: %s", token_data)
            raise GitHubOAuthError("Invalid response from GitHub token endpoint", code="GITHUB_INVALID_RESPONSE")

        return token_data

    async def fetch_user_profile(self, access_token: str) -> Dict[str, Any]:
        """
        Fetches the authenticated user profile and primary verified email from GitHub.
        """
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/vnd.github+json",
            "User-Agent": GITHUB_HTTP_USER_AGENT
        }

        async with httpx.AsyncClient(timeout=15.0) as client:
            try:
                user_resp = await client.get(GITHUB_API_USER_URL, headers=headers)
                user_resp.raise_for_status()
                user_data = user_resp.json()
            except Exception as e:
                logger.error("Error fetching GitHub user profile: %s", e)
                raise GitHubOAuthError("Failed to fetch user profile from GitHub", code="GITHUB_USER_FETCH_FAILED")

            email = user_data.get("email")
            # If public email is null, fetch from user emails endpoint
            if not email:
                try:
                    emails_resp = await client.get(GITHUB_API_EMAILS_URL, headers=headers)
                    if emails_resp.status_code == 200:
                        emails_data = emails_resp.json()
                        for entry in emails_data:
                            if entry.get("primary") and entry.get("verified"):
                                email = entry.get("email")
                                break
                        # Fallback to any verified email if primary not flagged
                        if not email and emails_data:
                            for entry in emails_data:
                                if entry.get("verified"):
                                    email = entry.get("email")
                                    break
                except Exception as e:
                    logger.warning("Could not fetch user emails from GitHub: %s", e)

        return {
            "github_id": str(user_data["id"]),
            "username": user_data["login"],
            "name": user_data.get("name") or user_data["login"],
            "email": email,
            "avatar_url": user_data.get("avatar_url"),
        }

    async def get_repository(
        self,
        owner: str,
        name: str,
        access_token: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Fetches repository details from GitHub API: GET /repos/{owner}/{name}.
        Uses authenticated user's access_token if provided (required for private repos).
        Handles rate limits, not found, and permission errors gracefully.
        """
        url = f"{GITHUB_API_REPOS_URL}/{owner}/{name}"
        headers = {
            "Accept": "application/vnd.github+json",
            "User-Agent": GITHUB_HTTP_USER_AGENT
        }
        if access_token:
            headers["Authorization"] = f"Bearer {access_token}"

        async with httpx.AsyncClient(timeout=15.0) as client:
            try:
                response = await client.get(url, headers=headers)
                if response.status_code == 404:
                    raise GitHubOAuthError(
                        f"Repository '{owner}/{name}' was not found on GitHub. If this is a private repository, please ensure your GitHub account has authorized access to it.",
                        code="REPOSITORY_NOT_FOUND"
                    )
                if response.status_code == 401:
                    raise GitHubOAuthError(
                        "Your GitHub authorization token has expired or is invalid. Please sign in again.",
                        code="GITHUB_UNAUTHORIZED"
                    )
                if response.status_code == 403:
                    body_text = response.text.lower()
                    if "rate limit" in body_text:
                        raise GitHubOAuthError(
                            "GitHub API rate limit exceeded. Please wait a few moments and try again.",
                            code="RATE_LIMIT_EXCEEDED"
                        )
                    raise GitHubOAuthError(
                        f"Access to repository '{owner}/{name}' was denied by GitHub.",
                        code="FORBIDDEN"
                    )

                response.raise_for_status()
                data = response.json()
                return data

            except GitHubOAuthError:
                raise
            except httpx.HTTPStatusError as e:
                logger.error("GitHub API error fetching %s/%s: %s", owner, name, e.response.text)
                raise GitHubOAuthError(
                    f"GitHub API returned error ({e.response.status_code}) while fetching repository.",
                    code="GITHUB_API_ERROR"
                )
            except Exception as e:
                logger.error("Network error fetching repository %s/%s: %s", owner, name, e)
                raise GitHubOAuthError(
                    "Network error connecting to GitHub. Please check your internet connection.",
                    code="GITHUB_NETWORK_ERROR"
                )

    async def list_user_repositories(
        self,
        access_token: str,
        page: int = 1,
        per_page: int = 30,
        search: Optional[str] = None,
        sort: str = "updated"
    ) -> List[Dict[str, Any]]:
        """
        Lists repositories accessible to the authenticated user from GitHub API:
        GET /user/repos?per_page={per_page}&page={page}&sort={sort}&affiliation=owner,collaborator,organization_member
        """
        if not access_token:
            raise GitHubOAuthError(
                "GitHub access token is required to list your repositories.",
                code="TOKEN_REQUIRED"
            )

        headers = {
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/vnd.github+json",
            "User-Agent": GITHUB_HTTP_USER_AGENT
        }
        params = {
            "per_page": min(max(per_page, 1), 100),
            "page": max(page, 1),
            "sort": sort,
            "affiliation": "owner,collaborator,organization_member"
        }

        async with httpx.AsyncClient(timeout=15.0) as client:
            try:
                response = await client.get(GITHUB_API_USER_REPOS_URL, headers=headers, params=params)
                if response.status_code == 401:
                    raise GitHubOAuthError(
                        "Your GitHub authorization token has expired or is invalid. Please sign in again.",
                        code="GITHUB_UNAUTHORIZED"
                    )
                if response.status_code == 403:
                    if "rate limit" in response.text.lower():
                        raise GitHubOAuthError(
                            "GitHub API rate limit exceeded. Please wait a few moments and try again.",
                            code="RATE_LIMIT_EXCEEDED"
                        )
                    raise GitHubOAuthError(
                        "Access to GitHub repositories list was denied.",
                        code="FORBIDDEN"
                    )
                response.raise_for_status()
                repos = response.json()

                if search:
                    q = search.lower().strip()
                    repos = [
                        r for r in repos
                        if q in r.get("name", "").lower() or q in r.get("full_name", "").lower() or q in (r.get("description") or "").lower()
                    ]

                return repos

            except GitHubOAuthError:
                raise
            except Exception as e:
                logger.error("Error listing user repositories from GitHub: %s", e)
                raise GitHubOAuthError(
                    "Failed to fetch repositories from GitHub.",
                    code="GITHUB_REPOS_FETCH_FAILED"
                )
