"""Secret detection and redaction engine enforcing CodePilot AUD-11.

Redacts API keys, credentials, connection strings, JWTs, and sensitive environment variables
from stack traces and diagnostics before storage or prompting.
"""

import re
from typing import Any, Dict, List, Optional, Pattern, Tuple, Union

# Compiled regular expressions for known secret formats
SECRET_PATTERNS: List[Tuple[str, Pattern[str]]] = [
    # Private Keys (RSA, DSA, EC, OPENSSH, etc.)
    (
        "PRIVATE_KEY",
        re.compile(
            r"-----BEGIN (?:RSA |EC |DSA |OPENSSH )?PRIVATE KEY-----[\s\S]*?-----END (?:RSA |EC |DSA |OPENSSH )?PRIVATE KEY-----",
            re.MULTILINE,
        ),
    ),
    # AWS Access Key IDs
    ("AWS_KEY", re.compile(r"\b((?:AKIA|ASIA|ABIA|ACCA)[0-9A-Z]{16})\b")),
    # GitHub Tokens (Personal, OAuth, User-to-Server, Server-to-Server, Refresh)
    ("GITHUB_TOKEN", re.compile(r"\b(gh[pousr]_[A-Za-z0-9_]{36,255})\b")),
    # OpenAI & Anthropic API Keys
    ("AI_API_KEY", re.compile(r"\b(sk-[a-zA-Z0-9_\-]{20,})\b")),
    # Google API Keys
    ("GOOGLE_API_KEY", re.compile(r"\b(AIza[0-9A-Za-z_\-]{35})\b")),
    # Slack Tokens
    ("SLACK_TOKEN", re.compile(r"\b(xox[baprs]-[0-9]{10,}-[0-9a-zA-Z]{24,})\b")),
    # JSON Web Tokens (JWT)
    (
        "JWT",
        re.compile(
            r"\b(eyJ[A-Za-z0-9_\-]{10,}\.eyJ[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]+)\b"
        ),
    ),
    # Bearer tokens in headers or logs
    ("BEARER_TOKEN", re.compile(r"(?i)\bBearer\s+([A-Za-z0-9_\-\.]{15,})\b")),
    # Database Connection URIs with embedded passwords
    (
        "DB_URI_PASSWORD",
        re.compile(
            r"((?:postgres|postgresql|mysql|mongodb|redis|amqp|mssql)://[^:]+:)([^@\s]+)(@)",
            re.IGNORECASE,
        ),
    ),
    # Generic key-value assignment for secrets (e.g. password="foo", api_key: "bar")
    (
        "KEY_VALUE_SECRET",
        re.compile(
            r"""(?i)\b(api_key|apikey|secret|token|password|passwd|auth_token|access_token|private_key|client_secret)\s*[:=]\s*["']?([^\s,"';\}\]\)\n]{4,})["']?""",
        ),
    ),
]

# Case-insensitive sensitive environment variable keys
SENSITIVE_ENV_KEYS = {
    "password", "secret", "token", "api_key", "apikey", "auth", "credential",
    "private_key", "access_key", "client_secret", "jwt", "bearer", "session_key",
    "github_token", "openai_api_key", "aws_secret_access_key", "database_url",
}


def redact_secrets(text: Optional[str]) -> str:
    """Scrub sensitive credentials, tokens, and secrets from text, replacing them with [REDACTED]."""
    if not text:
        return ""

    redacted = text

    # Handle Database connection string password specifically to keep the URI structure readable
    db_pattern = next(p for name, p in SECRET_PATTERNS if name == "DB_URI_PASSWORD")
    redacted = db_pattern.sub(r"\1[REDACTED]\3", redacted)

    # Handle key-value assignments specifically to keep key name
    kv_pattern = next(p for name, p in SECRET_PATTERNS if name == "KEY_VALUE_SECRET")
    redacted = kv_pattern.sub(r"\1=[REDACTED]", redacted)

    # Handle Bearer token specifically
    bearer_pattern = next(p for name, p in SECRET_PATTERNS if name == "BEARER_TOKEN")
    redacted = bearer_pattern.sub(r"Bearer [REDACTED]", redacted)

    # Handle remaining direct token/key patterns
    for name, pattern in SECRET_PATTERNS:
        if name in ("DB_URI_PASSWORD", "KEY_VALUE_SECRET", "BEARER_TOKEN"):
            continue
        redacted = pattern.sub("[REDACTED]", redacted)

    return redacted


def redact_dict(data: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Recursively scrub secrets from dictionary values and sensitive environment keys."""
    if not data:
        return {}

    result: Dict[str, Any] = {}
    for key, value in data.items():
        k_lower = str(key).lower()
        if any(sensitive in k_lower for sensitive in SENSITIVE_ENV_KEYS):
            result[key] = "[REDACTED]"
        elif isinstance(value, str):
            result[key] = redact_secrets(value)
        elif isinstance(value, dict):
            result[key] = redact_dict(value)
        elif isinstance(value, list):
            result[key] = [
                redact_secrets(v) if isinstance(v, str) else (redact_dict(v) if isinstance(v, dict) else v)
                for v in value
            ]
        else:
            result[key] = value

    return result
