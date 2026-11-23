"""Unit tests for Code Quality Engine optimization, caching, and partial tool failure (IT-16)."""

from unittest.mock import patch
import pytest
from agentic.common.agent_context import RepositorySnapshotContext, SnapshotContextRegistry
from backend.app.modules.code_analysis.engine import CodeQualityEngine
from backend.app.repositories.findings_repository import FindingsRepository
from shared.types.agent import FindingSeverity


@pytest.fixture(autouse=True)
def clean_repo():
    repo = FindingsRepository.get_instance()
    repo.clear()
    SnapshotContextRegistry.clear()
    yield
    repo.clear()
    SnapshotContextRegistry.clear()


def test_incremental_content_hash_caching():
    """Verify that unchanged files hit cache and skip recomputation."""
    repo = FindingsRepository.get_instance()
    engine = CodeQualityEngine(repository=repo)

    code = "def sample(x=[]):\n    pass\n"
    ctx = RepositorySnapshotContext("snap-cache-1")
    ctx.add_file("app/cached.py", code, language="python")
    SnapshotContextRegistry.register(ctx)

    # First run computes and caches
    run1 = engine.run_code_quality_analysis(snapshot_id="snap-cache-1")
    assert run1.total_findings == 1

    # Second run on same snapshot or same content should hit cache
    with patch("ai_service.code_analysis.bug_detector.BugDetector.analyze") as mock_bug_analyze:
        run2 = engine.run_code_quality_analysis(snapshot_id="snap-cache-1")
        # BugDetector.analyze should NOT have been called because cached content was reused!
        mock_bug_analyze.assert_not_called()
        assert run2.total_findings == 1


def test_it_16_partial_tool_failure_returns_coverage_and_partial_status():
    """IT-16: Tool failure produces partial results with tool_coverage."""
    repo = FindingsRepository.get_instance()
    engine = CodeQualityEngine(repository=repo)

    code = """def long_func():
""" + "\n".join([f"    a_{i} = {i}" for i in range(55)]) + "\n    return 1\n"

    ctx = RepositorySnapshotContext("snap-fail-1")
    ctx.add_file("app/long.py", code, language="python")
    SnapshotContextRegistry.register(ctx)

    # Simulate BugDetector throwing an unexpected crash/exception
    with patch("ai_service.code_analysis.bug_detector.BugDetector.analyze", side_effect=RuntimeError("Subprocess parser crash")):
        run = engine.run_code_quality_analysis(snapshot_id="snap-fail-1")

        # Run status should be PARTIAL
        assert run.status.value == "PARTIAL"
        assert len(run.warnings) >= 1
        assert "Subprocess parser crash" in run.warnings[0]

        # Tool coverage must record both tools
        tools = {tc.tool: tc for tc in run.tool_coverage}
        assert "bug_detector" in tools
        assert tools["bug_detector"].status == "FAILED"
        assert "Subprocess parser crash" in tools["bug_detector"].error

        assert "code_smell_detector" in tools
        assert tools["code_smell_detector"].status == "SUCCESS"

        # CodeSmellDetector findings should still be present!
        assert run.total_findings >= 1


def test_scope_paths_filtering():
    """Verify scope.paths filters files analyzed."""
    repo = FindingsRepository.get_instance()
    engine = CodeQualityEngine(repository=repo)

    ctx = RepositorySnapshotContext("snap-scope-1")
    ctx.add_file("app/models/user.py", "def a(x=[]):\n    pass\n", language="python")
    ctx.add_file("vendor/external.py", "def b(y=[]):\n    pass\n", language="python")
    SnapshotContextRegistry.register(ctx)

    run = engine.run_code_quality_analysis(snapshot_id="snap-scope-1", paths=["app/**"])
    assert run.total_findings == 1
    finding = repo.query_findings(snapshot_id="snap-scope-1")["items"][0]
    assert finding.file_path == "app/models/user.py"


def test_severity_threshold_filtering():
    """Verify severity threshold excludes findings below threshold."""
    repo = FindingsRepository.get_instance()
    engine = CodeQualityEngine(repository=repo)

    # File with TODO (INFO) and mutable default (HIGH)
    code = """# TODO: pending work
def test_func(x=[]):
    pass
"""
    ctx = RepositorySnapshotContext("snap-sev-1")
    ctx.add_file("app/test_sev.py", code, language="python")
    SnapshotContextRegistry.register(ctx)

    # When threshold is HIGH, INFO is filtered out
    run = engine.run_code_quality_analysis(snapshot_id="snap-sev-1", severity_threshold=FindingSeverity.HIGH)
    findings = repo.query_findings(snapshot_id="snap-sev-1")["items"]
    assert len(findings) == 1
    assert findings[0].severity == FindingSeverity.HIGH
