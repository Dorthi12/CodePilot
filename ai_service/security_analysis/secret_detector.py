"""Secret detection and redaction engine enforcing CodePilot AUD-11, SEC-SECRET-01, SEC-MAL-10.

Redacts API keys, credentials, connection strings, JWTs, and sensitive environment variables
from stack traces, diagnostics, and repository content.
Scans source files for leaked credentials, storing only SHA256 fingerprints in secret_findings (Invariant I9).
"""

import hashlib
import re
from typing import Any, Dict, List, Optional, Pattern, Tuple, Union
from uuid import uuid4

from shared.types.agent import FindingOrigin, FindingSeverity, FindingStatus
from shared.types.findings import (
    Finding,
    FindingEvidence,
    compute_finding_fingerprint,
)
from shared.types.security import SecretFindingRecord

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
    # Generic test/secret tokens e.g. sk_test_... or sk_live_...
    ("TEST_SECRET_KEY", re.compile(r"\b(sk_(?:test|live)_[A-Za-z0-9_\-]{16,})\b")),
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


class SecretScanner:
    """Enterprise secret detection scanner enforcing zero-leakage security (SEC-SECRET-01)."""

    def __init__(self) -> None:
        self.patterns = SECRET_PATTERNS

    def scan_file(
        self,
        file_path: str,
        content: str,
        run_id: str,
        snapshot_id: str,
    ) -> Tuple[List[Finding], List[SecretFindingRecord]]:
        """Scan file content for embedded secrets, returning Findings and SecretFindingRecords.

        CRITICAL SECURITY INVARIANT (I9):
        The raw secret value is NEVER stored anywhere in the Finding or SecretFindingRecord.
        Only cryptographic SHA-256 fingerprints are stored.
        Evidence snippet and descriptions are strictly sanitized with redact_secrets.
        """
        findings: List[Finding] = []
        secret_records: List[SecretFindingRecord] = []

        lines = content.splitlines()

        for line_idx, line in enumerate(lines, start=1):
            for secret_type, pattern in self.patterns:
                # Skip multiline private key search in line-by-line mode (handled separately)
                if secret_type == "PRIVATE_KEY":
                    continue

                for match in pattern.finditer(line):
                    # Extract the raw secret capture or full match
                    if secret_type in ("DB_URI_PASSWORD", "KEY_VALUE_SECRET"):
                        raw_secret = match.group(2)
                    elif match.groups():
                        raw_secret = match.group(1)
                    else:
                        raw_secret = match.group(0)

                    if not raw_secret or len(raw_secret.strip()) < 6:
                        continue

                    # Compute secret SHA-256 fingerprint (never store raw secret)
                    secret_hash = hashlib.sha256(raw_secret.encode("utf-8")).hexdigest()

                    # Fully redact the line for evidence snippet
                    redacted_line = redact_secrets(line)
                    rule_id = f"SEC-SECRET-{secret_type.upper()}"

                    # Stable finding fingerprint
                    finding_fp = compute_finding_fingerprint(
                        rule_id=rule_id,
                        file_path=file_path,
                        symbol_or_anchor=f"line:{line_idx}",
                        snippet=redacted_line,
                    )

                    finding_id = str(uuid4())
                    evidence = [
                        FindingEvidence(
                            file_path=file_path,
                            line_start=line_idx,
                            line_end=line_idx,
                            snippet=redacted_line,
                            snippet_hash=hashlib.sha256(redacted_line.encode("utf-8")).hexdigest(),
                            role="SUPPORTS",
                        )
                    ]

                    finding = Finding(
                        id=finding_id,
                        snapshot_id=snapshot_id,
                        analysis_run_id=run_id,
                        fingerprint=finding_fp,
                        origin=FindingOrigin.STATIC_TOOL,
                        category="SECURITY",
                        rule_id=rule_id,
                        tool="secret_scanner",
                        tool_version="1.0.0",
                        severity=FindingSeverity.CRITICAL,
                        confidence=0.98,
                        cwe="CWE-798",
                        owasp="A07:2021-Identification and Authentication Failures",
                        title=f"Hardcoded Credential Detected ({secret_type})",
                        description=(
                            f"Detected hardcoded {secret_type} in {file_path} at line {line_idx}. "
                            f"Secret fingerprint: sha256:{secret_hash[:16]}..."
                        ),
                        remediation=(
                            "Revoke and rotate this credential immediately. Never store plaintext credentials in code. "
                            "Inject secrets using environment variables or a secure KMS / secrets manager (SEC-SECRET-01)."
                        ),
                        file_path=file_path,
                        line_start=line_idx,
                        line_end=line_idx,
                        evidence=evidence,
                        status=FindingStatus.OPEN,
                        metadata={
                            "secret_type": secret_type,
                            "secret_fingerprint": secret_hash,
                        },
                    )
                    findings.append(finding)

                    secret_records.append(
                        SecretFindingRecord(
                            finding_id=finding_id,
                            secret_type=secret_type,
                            fingerprint=secret_hash,
                            file_path=file_path,
                            line=line_idx,
                        )
                    )

        # Handle multiline PRIVATE_KEY pattern across entire content
        pk_pattern = next(p for name, p in self.patterns if name == "PRIVATE_KEY")
        for match in pk_pattern.finditer(content):
            raw_key = match.group(0)
            secret_hash = hashlib.sha256(raw_key.encode("utf-8")).hexdigest()
            # Determine line range
            start_pos = match.start()
            line_start = content.count("\n", 0, start_pos) + 1
            line_end = line_start + raw_key.count("\n")

            rule_id = "SEC-SECRET-PRIVATE_KEY"
            redacted_snippet = "-----BEGIN PRIVATE KEY-----\n[REDACTED]\n-----END PRIVATE KEY-----"
            finding_fp = compute_finding_fingerprint(
                rule_id=rule_id,
                file_path=file_path,
                symbol_or_anchor=f"line:{line_start}",
                snippet=redacted_snippet,
            )

            finding_id = str(uuid4())
            evidence = [
                FindingEvidence(
                    file_path=file_path,
                    line_start=line_start,
                    line_end=line_end,
                    snippet=redacted_snippet,
                    snippet_hash=hashlib.sha256(redacted_snippet.encode("utf-8")).hexdigest(),
                    role="SUPPORTS",
                )
            ]

            finding = Finding(
                id=finding_id,
                snapshot_id=snapshot_id,
                analysis_run_id=run_id,
                fingerprint=finding_fp,
                origin=FindingOrigin.STATIC_TOOL,
                category="SECURITY",
                rule_id=rule_id,
                tool="secret_scanner",
                tool_version="1.0.0",
                severity=FindingSeverity.CRITICAL,
                confidence=1.0,
                cwe="CWE-798",
                owasp="A07:2021-Identification and Authentication Failures",
                title="Embedded Asymmetric Private Key Detected",
                description=(
                    f"Detected embedded private key block in {file_path} at lines {line_start}-{line_end}. "
                    f"Fingerprint: sha256:{secret_hash[:16]}..."
                ),
                remediation=(
                    "Revoke and remove the embedded private key block immediately. Generate new key pairs and "
                    "load cryptographic keys at runtime via HSM, KMS, or workload identity (SEC-SECRET-02)."
                ),
                file_path=file_path,
                line_start=line_start,
                line_end=line_end,
                evidence=evidence,
                status=FindingStatus.OPEN,
                metadata={
                    "secret_type": "PRIVATE_KEY",
                    "secret_fingerprint": secret_hash,
                },
            )
            findings.append(finding)
            secret_records.append(
                SecretFindingRecord(
                    finding_id=finding_id,
                    secret_type="PRIVATE_KEY",
                    fingerprint=secret_hash,
                    file_path=file_path,
                    line=line_start,
                )
            )

        return findings, secret_records
