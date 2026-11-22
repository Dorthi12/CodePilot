"""Unit tests for Secret Detection, Redaction, and Fingerprinting (M6).

Specifications:
- Master Architecture Specification v2.1 §6.6, §10 (M6)
- Security and Testing Specification v1.0 §7.4 (SEC-SECRET-01), §7.10 (SEC-MAL-10)
- Invariant I9: No column in secret_findings holds the raw secret value, only the fingerprint.
- UT-13: Redaction library corpus
"""

import hashlib
import pytest
from ai_service.security_analysis.secret_detector import (
    SecretScanner,
    redact_dict,
    redact_secrets,
)
from shared.types.agent import FindingSeverity


@pytest.fixture
def secret_scanner() -> SecretScanner:
    return SecretScanner()


def test_aws_access_key_detection_and_redaction(secret_scanner: SecretScanner):
    """Detect AWS key, verify redacted snippet and hash fingerprint without raw secret leakage."""
    raw_key = "AKIAIOSFODNN7EXAMPLE"
    code = f'AWS_ACCESS_KEY_ID = "{raw_key}"\n'
    findings, records = secret_scanner.scan_file("config/aws.py", code, "run-1", "snap-1")

    assert len(findings) == 1
    assert len(records) == 1

    f = findings[0]
    rec = records[0]

    # Verify severity & rules
    assert f.severity == FindingSeverity.CRITICAL
    assert f.cwe == "CWE-798"
    assert "SEC-SECRET" in f.rule_id

    # Verify raw secret is NOT present anywhere in finding or record
    assert raw_key not in f.title
    assert raw_key not in f.description
    assert raw_key not in f.evidence[0].snippet
    assert "[REDACTED]" in f.evidence[0].snippet

    # Verify record contains only SHA256 fingerprint hash
    expected_hash = hashlib.sha256(raw_key.encode("utf-8")).hexdigest()
    assert rec.fingerprint == expected_hash
    assert rec.secret_type == "AWS_KEY"
    assert rec.line == 1


def test_github_token_detection(secret_scanner: SecretScanner):
    """Detect GitHub token and ensure zero plaintext leakage."""
    raw_token = "ghp_1234567890abcdefghijklmnopqrstuvwxyzAB"
    code = f'github_auth_token = "{raw_token}"\n'
    findings, records = secret_scanner.scan_file("scripts/deploy.py", code, "run-1", "snap-1")

    assert len(findings) >= 1
    assert raw_token not in findings[0].evidence[0].snippet
    assert raw_token not in findings[0].description
    assert records[0].secret_type in ("GITHUB_TOKEN", "KEY_VALUE_SECRET")
    assert records[0].fingerprint == hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


def test_multiline_rsa_private_key_detection(secret_scanner: SecretScanner):
    """Detect multiline RSA private key blocks and redact them completely."""
    raw_key_block = """-----BEGIN RSA PRIVATE KEY-----
MIIEowIBAAKCAQEA0Y1+examplePrivateDataBlockThatMustNeverBeStored
-----END RSA PRIVATE KEY-----"""
    code = f'SERVER_KEY = """{raw_key_block}"""\n'
    findings, records = secret_scanner.scan_file("certs/server.pem", code, "run-1", "snap-1")

    assert len(findings) == 1
    assert len(records) == 1
    f = findings[0]
    rec = records[0]

    assert f.rule_id == "SEC-SECRET-PRIVATE_KEY"
    assert "examplePrivateDataBlock" not in f.evidence[0].snippet
    assert "[REDACTED]" in f.evidence[0].snippet
    assert rec.secret_type == "PRIVATE_KEY"
    assert rec.fingerprint == hashlib.sha256(raw_key_block.encode("utf-8")).hexdigest()


def test_database_uri_password_redacted(secret_scanner: SecretScanner):
    """Database URI passwords are sanitized while keeping scheme and host readable."""
    raw_uri = "postgres://admin_user:super_secret_password_123@db.prod.internal:5432/main"
    code = f'DATABASE_URL = "{raw_uri}"\n'
    findings, records = secret_scanner.scan_file(".env.example", code, "run-1", "snap-1")

    assert len(findings) >= 1
    snippet = findings[0].evidence[0].snippet
    assert "super_secret_password_123" not in snippet
    assert "postgres://admin_user:[REDACTED]@db.prod.internal:5432/main" in snippet


def test_jwt_token_detection(secret_scanner: SecretScanner):
    """Detect JWT tokens in headers or configurations."""
    raw_jwt = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4gRG9lIiwiaWF0IjoxNTE2MjM5MDIyfQ.SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c"
    code = f'auth_header = "Bearer {raw_jwt}"\n'
    findings, records = secret_scanner.scan_file("app/client.py", code, "run-1", "snap-1")

    assert len(findings) >= 1
    assert raw_jwt not in findings[0].evidence[0].snippet


def test_redact_dict_scrubs_sensitive_keys():
    """Verify recursive dictionary secret scrubbing."""
    env_data = {
        "APP_NAME": "CodePilot",
        "DATABASE_URL": "postgresql://usr:secret_pass@localhost:5432/db",
        "API_KEY": "sk-123456789012345678901234567890",
        "CONFIG": {
            "oauth_token": "ghp_xxxxxxxxxxxxxxxxxxxxxxxxxxxx",
            "normal_field": "safe_value",
        },
    }
    cleaned = redact_dict(env_data)
    assert cleaned["APP_NAME"] == "CodePilot"
    assert cleaned["DATABASE_URL"] == "[REDACTED]"
    assert cleaned["API_KEY"] == "[REDACTED]"
    assert cleaned["CONFIG"]["oauth_token"] == "[REDACTED]"
    assert cleaned["CONFIG"]["normal_field"] == "safe_value"
