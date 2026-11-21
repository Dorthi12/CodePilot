import json
import logging
from datetime import datetime, timezone
from typing import Optional, Dict, Any, Tuple
import httpx
import redis.asyncio as aioredis

from src.config import settings
from src.services.crypto_service import crypto_service

logger = logging.getLogger(__name__)

GITHUB_OAUTH_AUTHORIZE_URL = "https://github.com/login/oauth/authorize"
GITHUB_OAUTH_ACCESS_TOKEN_URL = "https://github.com/login/oauth/access_token"
GITHUB_API_USER_URL = "https://api.github.com/user"
GITHUB_API_EMAILS_URL = "https://api.github.com/user/emails"


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
        query_string = "&".join(f"{k}={v}" for k, v in params.items())
        auth_url = f"{GITHUB_OAUTH_AUTHORIZE_URL}?{query_string}"

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
            "User-Agent": settings.APP_NAME
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
            "User-Agent": settings.APP_NAME
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
