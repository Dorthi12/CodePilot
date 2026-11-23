"""Unit tests for secret detection and redaction engine (AUD-11)."""

import pytest
from ai_service.security_analysis.secret_detector import (
    redact_dict,
    redact_secrets,
)


def test_redact_api_keys() -> None:
    text = (
        "Error using OpenAI key sk-abcdef12345678901234567890 and "
        "GitHub token ghp_123456789012345678901234567890123456 and "
        "AWS key AKIAIOSFODNN7EXAMPLE."
    )
    redacted = redact_secrets(text)
    assert "sk-abcdef" not in redacted
    assert "ghp_1234" not in redacted
    assert "AKIAIOSF" not in redacted
    assert "[REDACTED]" in redacted


def test_redact_jwt_and_bearer_token() -> None:
    jwt = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4ifQ.SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c"
    bearer = f"Bearer {jwt}"
    text = f"Authorization header: {bearer}"

    redacted = redact_secrets(text)
    assert jwt not in redacted
    assert "Bearer [REDACTED]" in redacted or "[REDACTED]" in redacted


def test_redact_database_uri_password() -> None:
    uri = "postgres://admin:SuperSecretPass123!@db.internal.net:5432/production"
    text = f"Connection failed to: {uri}"

    redacted = redact_secrets(text)
    assert "SuperSecretPass123!" not in redacted
    assert redacted == "Connection failed to: postgres://admin:[REDACTED]@db.internal.net:5432/production"


def test_redact_private_key() -> None:
    private_key = (
        "-----BEGIN RSA PRIVATE KEY-----\n"
        "MIIEowIBAAKCAQEA04rQ3m9V...\n"
        "-----END RSA PRIVATE KEY-----"
    )
    text = f"Loaded private key:\n{private_key}\nStarting server."
    redacted = redact_secrets(text)
    assert "MIIEow" not in redacted
    assert "[REDACTED]" in redacted
    assert "Starting server." in redacted


def test_redact_dict_recursive() -> None:
    env = {
        "ENV": "production",
        "DATABASE_URL": "postgres://user:p4ssword@localhost/db",
        "API_KEY": "sk-1234567890abcdef1234567890",
        "nested": {
            "SECRET_TOKEN": "shhh_secret",
            "normal_field": "visible_value",
        },
        "list_data": [
            "normal item",
            "password=my_secret_password",
        ],
    }

    cleaned = redact_dict(env)
    assert cleaned["ENV"] == "production"
    assert cleaned["DATABASE_URL"] == "[REDACTED]"
    assert cleaned["API_KEY"] == "[REDACTED]"
    assert cleaned["nested"]["SECRET_TOKEN"] == "[REDACTED]"
    assert cleaned["nested"]["normal_field"] == "visible_value"
    assert "my_secret_password" not in str(cleaned["list_data"])


def test_empty_and_none_text() -> None:
    assert redact_secrets(None) == ""
    assert redact_secrets("") == ""
    assert redact_dict(None) == {}
    assert redact_dict({}) == {}
