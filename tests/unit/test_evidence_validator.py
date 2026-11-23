"""Unit tests for the Evidence and Citation Validation Engine."""

from shared.types.agent import FindingSeverity, VerificationCheck
from shared.types.findings import Finding, FindingEvidence
from agentic.common.agent_context import RepositorySnapshotContext, SnapshotContextRegistry
from agentic.evaluators.evidence_validator import EvidenceValidator


def test_evidence_validator_valid_finding():
    SnapshotContextRegistry.clear()
    ctx = RepositorySnapshotContext("snap-v1")
    ctx.add_file("app/main.py", "def hello():\n    return 'world'\n", language="python")
    SnapshotContextRegistry.register(ctx)

    validator = EvidenceValidator()
    finding = Finding(
        id="find-1",
        snapshot_id="snap-v1",
        analysis_run_id="run-1",
        fingerprint="fp1",
        category="CODE_QUALITY",
        rule_id="RULE-1",
        tool="test_tool",
        severity=FindingSeverity.LOW,
        title="Valid finding",
        description="Valid description",
        file_path="app/main.py",
        line_start=1,
        line_end=2,
    )

    results = validator.verify_findings("snap-v1", "run-1", [finding])
    assert len(results) == 3
    # Check that schema, duplicate, and citation all passed
    assert all(r.passed for r in results)


def test_evidence_validator_nonexistent_file():
    SnapshotContextRegistry.clear()
    ctx = RepositorySnapshotContext("snap-v1")
    ctx.add_file("app/main.py", "print('hello')", language="python")
    SnapshotContextRegistry.register(ctx)

    validator = EvidenceValidator()
    finding = Finding(
        id="find-1",
        snapshot_id="snap-v1",
        analysis_run_id="run-1",
        fingerprint="fp1",
        category="CODE_QUALITY",
        rule_id="RULE-1",
        tool="test_tool",
        severity=FindingSeverity.LOW,
        title="Hallucinated file",
        description="File does not exist",
        file_path="app/ghost_file.py",
        line_start=1,
        line_end=2,
    )

    results = validator.verify_findings("snap-v1", "run-1", [finding])
    citation_res = next(r for r in results if r.check == VerificationCheck.CITATION)
    assert citation_res.passed is False
    assert "does not exist in snapshot" in citation_res.detail


def test_evidence_validator_line_bounds():
    SnapshotContextRegistry.clear()
    ctx = RepositorySnapshotContext("snap-v1")
    ctx.add_file("app/main.py", "line 1\nline 2\n", language="python")
    SnapshotContextRegistry.register(ctx)

    validator = EvidenceValidator()
    finding = Finding(
        id="find-1",
        snapshot_id="snap-v1",
        analysis_run_id="run-1",
        fingerprint="fp1",
        category="CODE_QUALITY",
        rule_id="RULE-1",
        tool="test_tool",
        severity=FindingSeverity.LOW,
        title="Out of bounds",
        description="Line 99 does not exist",
        file_path="app/main.py",
        line_start=10,
        line_end=99,
    )

    results = validator.verify_findings("snap-v1", "run-1", [finding])
    citation_res = next(r for r in results if r.check == VerificationCheck.CITATION)
    assert citation_res.passed is False
    assert "exceeds file bounds" in citation_res.detail


def test_evidence_validator_duplicate_detection():
    SnapshotContextRegistry.clear()
    ctx = RepositorySnapshotContext("snap-v1")
    ctx.add_file("app/main.py", "line 1\nline 2\n", language="python")
    SnapshotContextRegistry.register(ctx)

    validator = EvidenceValidator()
    finding1 = Finding(
        id="find-1",
        snapshot_id="snap-v1",
        analysis_run_id="run-1",
        fingerprint="fp-dup",
        category="CODE_QUALITY",
        rule_id="RULE-1",
        tool="tool1",
        severity=FindingSeverity.LOW,
        title="Finding 1",
        description="Desc",
        file_path="app/main.py",
        line_start=1,
        line_end=2,
    )
    finding2 = Finding(
        id="find-2",
        snapshot_id="snap-v1",
        analysis_run_id="run-1",
        fingerprint="fp-dup",  # Duplicate fingerprint!
        category="CODE_QUALITY",
        rule_id="RULE-1",
        tool="tool2",
        severity=FindingSeverity.LOW,
        title="Finding 2",
        description="Desc",
        file_path="app/main.py",
        line_start=1,
        line_end=2,
    )

    results = validator.verify_findings("snap-v1", "run-1", [finding1, finding2])
    dup_res = [r for r in results if r.check == VerificationCheck.DUPLICATE]
    assert dup_res[0].passed is True
    assert dup_res[1].passed is False  # Second finding flagged as duplicate
