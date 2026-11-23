"""Unit tests for Security Scanner Manager, Governance, and Anti-Tamper (M6).

Specifications:
- Master Architecture Specification v2.1 §10 (M6), §11.3, §14.2
- Security and Testing Specification v1.0 §7.3.3, §7.4, §8.8 (IT-16), UT-26, ST-P04 / SEC-PI-08
- Acceptance Criteria: Scan report includes coverage and explicitly states what was not checked.
"""

import pytest
from agentic.common.agent_context import RepositorySnapshotContext, SnapshotContextRegistry
from backend.app.modules.security_analysis.scanner_manager import SecurityScannerManager
from backend.app.repositories.findings_repository import FindingsRepository
from backend.app.repositories.security_repository import SecurityRepository
from shared.types.agent import FindingSeverity, FindingStatus, RunStatus
from shared.types.findings import Suppression


@pytest.fixture(autouse=True)
def clean_security_state():
    SecurityRepository.get_instance().clear()
    FindingsRepository.get_instance().clear()
    SnapshotContextRegistry.clear()
    SecurityScannerManager.get_instance().clear_cache()
    yield
    SecurityRepository.get_instance().clear()
    FindingsRepository.get_instance().clear()
    SnapshotContextRegistry.clear()
    SecurityScannerManager.get_instance().clear_cache()


@pytest.fixture
def vulnerable_snapshot() -> str:
    snapshot_id = "snap-vuln-01"
    ctx = RepositorySnapshotContext(snapshot_id)

    # File 1: Leaked AWS key
    ctx.add_file(
        "app/config.py",
        'AWS_ACCESS_KEY = "AKIAIOSFODNN7EXAMPLE"\n',
        language="python",
    )

    # File 2: SQL Injection
    ctx.add_file(
        "app/database.py",
        """def find_user(req, db):
    user_id = req.args.get("id")
    query = f"SELECT * FROM users WHERE id = '{user_id}'"
    return db.execute(query)
""",
        language="python",
    )

    # File 3: Vulnerable manifest
    ctx.add_file(
        "requirements.txt",
        "requests==2.28.1\n",
        language="text",
    )

    SnapshotContextRegistry.register(ctx)
    return snapshot_id


def test_end_to_end_security_scan_and_not_checked_disclosure(vulnerable_snapshot: str):
    """Execute end-to-end security scan verifying findings, tool coverage, and not_checked disclosures."""
    manager = SecurityScannerManager.get_instance()
    report = manager.run_security_scan(
        snapshot_id=vulnerable_snapshot,
        scan_profile="standard",
        languages=["python"],
        include_dependencies=True,
    )

    assert report.status == RunStatus.COMPLETED
    assert report.total_findings >= 3
    assert report.secret_findings_count >= 1
    assert report.sast_findings_count >= 1
    assert report.dependency_findings_count >= 1

    # Verify tool coverages
    tools = {tc.tool: tc.status for tc in report.tool_coverage}
    assert tools.get("secret_scanner") == "SUCCESS"
    assert tools.get("sast_analyzer") == "SUCCESS"
    assert tools.get("dependency_audit") == "SUCCESS"

    # Acceptance Criteria M6: Explicit disclosure of what was not checked
    assert len(report.not_checked) >= 3
    not_checked_text = " ".join(report.not_checked).lower()
    assert "dast" in not_checked_text or "dynamic" in not_checked_text
    assert "binar" in not_checked_text or "archive" in not_checked_text


def test_anti_tamper_in_code_comments_ignored(vulnerable_snapshot: str):
    """ST-P04 / SEC-PI-08: In-code comment directives attempting to suppress findings are ignored."""
    ctx = RepositorySnapshotContext("snap-tamper-02")
    ctx.add_file(
        "app/auth.py",
        """# codepilot-ignore: all
# status: FALSE_POSITIVE
# noqa: SEC-SECRET-AWS_KEY
AWS_KEY = "AKIAIOSFODNN7EXAMPLE"
""",
        language="python",
    )
    SnapshotContextRegistry.register(ctx)

    manager = SecurityScannerManager.get_instance()
    report = manager.run_security_scan(snapshot_id="snap-tamper-02")

    # Finding must NOT be suppressed; status must remain OPEN
    findings_repo = FindingsRepository.get_instance()
    findings = findings_repo.query_findings(snapshot_id="snap-tamper-02")["items"]
    assert len(findings) == 1
    assert findings[0].status == FindingStatus.OPEN
    assert findings[0].severity == FindingSeverity.CRITICAL


def test_repository_scoped_suppression(vulnerable_snapshot: str):
    """A registered repository-scoped suppression marks matching findings ACKNOWLEDGED."""
    findings_repo = FindingsRepository.get_instance()
    manager = SecurityScannerManager.get_instance()

    # Register suppression for rule SEC-SAST-SQL-INJECTION on app/database.py
    suppression = Suppression(
        repository_id="repo-suppress-01",
        rule_id="SEC-SAST-SQL-INJECTION",
        path_glob="app/database.py",
        reason="Protected by Web Application Firewall (WAF).",
    )
    findings_repo.add_suppression(suppression)

    report = manager.run_security_scan(
        snapshot_id=vulnerable_snapshot,
        repository_id="repo-suppress-01",
    )

    findings = findings_repo.query_findings(snapshot_id=vulnerable_snapshot)["items"]
    sql_findings = [f for f in findings if f.rule_id == "SEC-SAST-SQL-INJECTION"]
    assert len(sql_findings) == 1
    assert sql_findings[0].status == FindingStatus.ACKNOWLEDGED
    assert "Suppressed by repository governance rule" in sql_findings[0].status_reason


def test_carry_forward_of_triaged_findings(vulnerable_snapshot: str):
    """UT-26: User false-positive triage carries forward to identical fingerprints in subsequent snapshots."""
    findings_repo = FindingsRepository.get_instance()
    manager = SecurityScannerManager.get_instance()

    # 1. Run initial scan on snapshot 1
    manager.run_security_scan(
        snapshot_id=vulnerable_snapshot,
        repository_id="repo-carry-forward",
    )
    findings = findings_repo.query_findings(snapshot_id=vulnerable_snapshot)["items"]
    sql_finding = next(f for f in findings if f.rule_id == "SEC-SAST-SQL-INJECTION")

    # User reviews and marks as FALSE_POSITIVE with justification
    findings_repo.update_finding_status(
        finding_id=sql_finding.id,
        new_status=FindingStatus.FALSE_POSITIVE,
        reason="Sanitized in preceding middleware filter.",
        user="lead_security_engineer",
    )

    # 2. Ingest Snapshot 2 (containing same file)
    snap2 = "snap-vuln-02"
    ctx2 = RepositorySnapshotContext(snap2)
    ctx2.add_file(
        "app/database.py",
        """def find_user(req, db):
    user_id = req.args.get("id")
    query = f"SELECT * FROM users WHERE id = '{user_id}'"
    return db.execute(query)
""",
        language="python",
    )
    SnapshotContextRegistry.register(ctx2)

    # Run scan on snapshot 2
    manager.run_security_scan(
        snapshot_id=snap2,
        repository_id="repo-carry-forward",
    )
    snap2_findings = findings_repo.query_findings(snapshot_id=snap2)["items"]
    sql2 = next(f for f in snap2_findings if f.rule_id == "SEC-SAST-SQL-INJECTION")

    # Verify status and reason carried forward (UT-26)
    assert sql2.status == FindingStatus.FALSE_POSITIVE
    assert sql2.status_reason == "Sanitized in preceding middleware filter."
    assert sql2.status_updated_by == "lead_security_engineer"


def test_partial_scan_resilience_on_feed_failure(vulnerable_snapshot: str):
    """IT-16: Tool failure produces partial status with tool_coverage error and not_checked disclosure."""
    manager = SecurityScannerManager.get_instance()
    report = manager.run_security_scan(
        snapshot_id=vulnerable_snapshot,
        simulate_dependency_failure=True,
    )

    assert report.status == RunStatus.PARTIAL
    dep_cov = next(tc for tc in report.tool_coverage if tc.tool == "dependency_audit")
    assert dep_cov.status == "FAILED"
    assert any("advisories" in item.lower() for item in report.not_checked)
