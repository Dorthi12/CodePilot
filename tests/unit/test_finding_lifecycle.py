"""Unit tests for Finding Lifecycle, Stable Fingerprints, Carry-Forward, and Suppressions (UT-26)."""

import pytest
from agentic.common.agent_context import RepositorySnapshotContext, SnapshotContextRegistry
from backend.app.modules.code_analysis.engine import CodeQualityEngine
from backend.app.repositories.findings_repository import FindingsRepository
from shared.types.agent import FindingStatus
from shared.types.findings import Suppression, compute_finding_fingerprint


@pytest.fixture(autouse=True)
def clean_repo():
    repo = FindingsRepository.get_instance()
    repo.clear()
    SnapshotContextRegistry.clear()
    yield
    repo.clear()
    SnapshotContextRegistry.clear()


def test_stable_fingerprint_generation():
    fp1 = compute_finding_fingerprint(
        rule_id="BUG-MUTABLE-DEFAULT",
        file_path="app/db/service.py",
        symbol_or_anchor="connect",
        snippet="def connect(items=[]):",
    )
    fp2 = compute_finding_fingerprint(
        rule_id="bug-mutable-default",
        file_path="app\\db\\service.py",
        symbol_or_anchor="connect",
        snippet="def connect(items=[]):",
    )
    # Different case and path separator must produce identical fingerprint
    assert fp1 == fp2
    assert len(fp1) == 64


def test_finding_carry_forward_across_snapshots():
    """UT-26: Same fingerprint across snapshots; status carried forward."""
    repo = FindingsRepository.get_instance()
    engine = CodeQualityEngine(repository=repo)

    # 1. Snapshot 1 with a mutable default argument
    code = "def query(filter_list=[]):\n    pass\n"
    ctx1 = RepositorySnapshotContext("snap-v1")
    ctx1.add_file("app/query.py", code, language="python")
    SnapshotContextRegistry.register(ctx1)

    run1 = engine.run_code_quality_analysis(snapshot_id="snap-v1", repository_id="repo-123")
    assert run1.status.value == "COMPLETED"

    findings1 = repo.query_findings(snapshot_id="snap-v1")["items"]
    assert len(findings1) == 1
    finding1 = findings1[0]
    assert finding1.status == FindingStatus.OPEN

    # 2. User acknowledges the finding in Snapshot 1
    repo.update_finding_status(
        finding_id=finding1.id,
        new_status=FindingStatus.ACKNOWLEDGED,
        reason="Acknowledged during sprint planning; fix scheduled for next release.",
        user="tech_lead",
    )

    # 3. New commit creates Snapshot 2 with the same file
    ctx2 = RepositorySnapshotContext("snap-v2")
    ctx2.add_file("app/query.py", code, language="python")
    SnapshotContextRegistry.register(ctx2)

    # Run analysis on Snapshot 2
    run2 = engine.run_code_quality_analysis(snapshot_id="snap-v2", repository_id="repo-123")
    assert run2.status.value == "COMPLETED"

    findings2 = repo.query_findings(snapshot_id="snap-v2")["items"]
    assert len(findings2) == 1
    finding2 = findings2[0]

    # Verify UT-26: fingerprint matches and status is carried forward!
    assert finding2.fingerprint == finding1.fingerprint
    assert finding2.status == FindingStatus.ACKNOWLEDGED
    assert "sprint planning" in finding2.status_reason


def test_repository_scoped_suppressions():
    """Verify repository-scoped suppressions match by rule_id + path_glob or fingerprint."""
    repo = FindingsRepository.get_instance()
    engine = CodeQualityEngine(repository=repo)

    # Register suppression for repo-xyz on all files in 'legacy/*' for rule BUG-BARE-EXCEPT
    suppression = Suppression(
        repository_id="repo-xyz",
        rule_id="BUG-BARE-EXCEPT",
        path_glob="legacy/*",
        reason="Legacy vendor module exempt from linter rules",
        created_by="security_officer",
    )
    repo.add_suppression(suppression)

    # Snapshot with bare except in legacy/old.py and modern/new.py
    bare_code = "try:\n    do_something()\nexcept:\n    pass\n"
    ctx = RepositorySnapshotContext("snap-supp-1")
    ctx.add_file("legacy/old.py", bare_code, language="python")
    ctx.add_file("modern/new.py", bare_code, language="python")
    SnapshotContextRegistry.register(ctx)

    engine.run_code_quality_analysis(snapshot_id="snap-supp-1", repository_id="repo-xyz")

    findings = repo.query_findings(snapshot_id="snap-supp-1")["items"]
    assert len(findings) == 2

    legacy_finding = next(f for f in findings if f.file_path == "legacy/old.py")
    modern_finding = next(f for f in findings if f.file_path == "modern/new.py")

    # legacy finding must be marked FALSE_POSITIVE / suppressed by policy
    assert legacy_finding.status == FindingStatus.FALSE_POSITIVE
    assert "Suppressed by policy" in legacy_finding.status_reason
    assert legacy_finding.status_updated_by == "security_officer"

    # modern finding must remain OPEN
    assert modern_finding.status == FindingStatus.OPEN
