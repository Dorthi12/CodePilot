import os
from typing import List, Optional
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    ENVIRONMENT: str = Field(default="development", description="Environment mode: development, testing, production")
    APP_NAME: str = "CodePilot — The Knowledge of Athena"
    APP_BASE_URL: str = "http://localhost:8000"
    FRONTEND_BASE_URL: str = "http://localhost:5173"
    CORS_ALLOWED_ORIGINS: List[str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ]

    # Database
    DATABASE_URL: str = Field(
        default="postgresql+asyncpg://postgres:postgres@localhost:5432/codepilot",
        description="Async PostgreSQL connection string"
    )
    DATABASE_URL_SYNC: str = Field(
        default="postgresql://postgres:postgres@localhost:5432/codepilot",
        description="Synchronous PostgreSQL connection string for Alembic"
    )

    # Redis
    REDIS_URL: str = Field(
        default="redis://localhost:6379/0",
        description="Redis URL for session and cache"
    )

    # GitHub OAuth
    GITHUB_CLIENT_ID: str = Field(default="", description="GitHub OAuth App Client ID")
    GITHUB_CLIENT_SECRET: str = Field(default="", description="GitHub OAuth App Client Secret")
    GITHUB_REDIRECT_URI: str = Field(
        default="http://localhost:8000/api/v1/integrations/github/callback",
        description="GitHub OAuth redirect URI"
    )
    GITHUB_SCOPES: str = "read:user,user:email,repo"
    AI_SERVICES_URL: str = "http://ai:8001"
    # AI_SERVICES_URL: str = "http://127.0.0.1:8001"

    # Security & Encryption
    SESSION_SECRET: str = Field(
        default="codepilot-dev-session-secret-key-32-bytes-minimum-length-req",
        description="Secret key used for signing session or state tokens"
    )
    TOKEN_ENCRYPTION_KEY: str = Field(
        default="codepilot-dev-token-encryption-key-32-chars-long!",
        description="32-byte secret key used for AES-GCM / Fernet token encryption"
    )

    # Session & Cookie settings
    SESSION_COOKIE_NAME: str = "cp_session"
    CSRF_COOKIE_NAME: str = "cp_csrf"
    SESSION_IDLE_TIMEOUT_SECONDS: int = 12 * 3600  # 12 hours
    SESSION_ABSOLUTE_LIFETIME_SECONDS: int = 7 * 86400  # 7 days
    COOKIE_SECURE: bool = False
    COOKIE_SAMESITE: str = "lax"
    COOKIE_DOMAIN: Optional[str] = None

    # Workspace & Repository Cloning
    WORKSPACE_BASE_DIR: str = Field(
        default=os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "workspaces")),
        description="Base directory for cloned repository workspaces"
    )
    MAX_REPO_SIZE_KB: int = Field(default=500 * 1024, description="Maximum allowed repository size in KB (500 MB)")
    MAX_WORKSPACE_DISK_USAGE_MB: int = Field(default=1000, description="Maximum disk quota per cloned workspace in MB (1 GB)")
    CLONE_TIMEOUT_SECONDS: int = Field(default=300, description="Maximum timeout for clone operations in seconds (5 minutes)")

    # Optional AI / LLM Provider
    GEMINI_API_KEY: Optional[str] = Field(
        default=None,
        description="Optional Google Gemini API key for AI code explanation (falls back to offline StaticAnalysisProvider if unset)"
    )

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )


settings = Settings()
