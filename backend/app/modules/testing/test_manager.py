"""Test Manager: Orchestrates the end-to-end lifecycle of Mastermind Feature 5 (Unit Test Generation).

Specifications:
- Master Architecture Specification v2.1 §10 (M5), §14.2, §14.3
- API and Data Specification v1.0 §3.3 (Endpoints 085-088), §3.4.14
- Security & Testing Specification v1.0 §7.3.3, §8.9 (AI-15)
- Patch Core Integration: Hands off exported test suite to M4 Patch pipeline
"""

import difflib
from datetime import datetime, timezone
import posixpath
from typing import Any, Dict, List, Optional, Tuple
from uuid import uuid4

from agentic.common.agent_context import (
    RepositorySnapshotContext,
    SnapshotContextRegistry,
)
from ai_service.generation.test_generator import TestGenerator
from backend.app.modules.patching.patch_manager import PatchManager, inspect_diff, sha256_diff
from backend.app.modules.testing.coverage_analyzer import CoverageAnalyzer
from backend.app.modules.testing.test_discovery import TestDiscoveryService
from backend.app.modules.testing.test_execution import ExecutionConsentRequiredError, SandboxTestRunner
from backend.app.repositories.test_repository import TestRepository
from shared.types.patch import PatchArtifact
from shared.types.testing import (
    CoverageReportRecord,
    TestArtifact,
    TestArtifactStatus,
    TestGenerationRunRecord,
    TestResultRecord,
    TestRunRecord,
    TestRunStatus,
)


class TestManager:
    """Singleton service coordinating test discovery, synthesis, execution, coverage, and patch export."""

    __test__ = False
    _instance: Optional["TestManager"] = None

    def __init__(self, repo: Optional[TestRepository] = None, patch_mgr: Optional[PatchManager] = None) -> None:
        self.repo = repo or TestRepository.get_instance()
        self.patch_mgr = patch_mgr or PatchManager.instance()
        self.sandbox_runner = SandboxTestRunner()

    @classmethod
    def instance(cls) -> "TestManager":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def generate_tests(
        self,
        snapshot_id: str,
        target_file: Optional[str] = None,
        symbol_id: Optional[str] = None,
        framework: str = "pytest",
        test_type: str = "unit",
        target_edge_cases: Optional[List[str]] = None,
        existing_test_paths: Optional[List[str]] = None,
    ) -> TestGenerationRunRecord:
        """Execute test generation workflow for a targeted file or symbol.

        Args:
            snapshot_id: Repository snapshot identifier.
            target_file: Relative path of the file to test.
            symbol_id: Symbol identifier to test (if file not explicitly specified).
            framework: Target test framework (default pytest).
            test_type: Suite type (unit, edge_case, regression).
            target_edge_cases: Explicit edge cases to include.
            existing_test_paths: Search directories for conventions.

        Returns:
            Fully populated TestGenerationRunRecord.
        """
        if not SnapshotContextRegistry.contains(snapshot_id):
            raise ValueError(f"Snapshot '{snapshot_id}' not found in registry.")

        ctx = SnapshotContextRegistry.get(snapshot_id)

        # Resolve target file and symbol
        target_symbol_name: Optional[str] = None
        resolved_file = target_file

        if symbol_id:
            matching_sym = next((s for s in ctx.symbols if s.id == symbol_id), None)
            if matching_sym:
                target_symbol_name = matching_sym.name
                resolved_file = matching_sym.file_path

        if not resolved_file:
            # Fallback to the first non-test file in snapshot
            non_tests = [p for p in ctx.files.keys() if "test" not in p]
            if non_tests:
                resolved_file = non_tests[0]
            elif ctx.files:
                resolved_file = list(ctx.files.keys())[0]
            else:
                raise ValueError(f"No source files available in snapshot '{snapshot_id}'.")

        norm_file = posixpath.normpath(resolved_file.replace("\\", "/")).lstrip("/")
        if norm_file not in ctx.files:
            raise ValueError(f"Target file '{norm_file}' does not exist in snapshot '{snapshot_id}'.")

        # 1. Discover conventions and existing test framework
        discovery = TestDiscoveryService.discover_tests(
            snapshot_id=snapshot_id,
            target_file=norm_file,
            explicit_framework=framework,
            search_paths=existing_test_paths,
        )

        # 2. Synthesize test code, test cases, fixtures, assumptions
        test_code, test_cases, fixtures, assumptions, vacuous = TestGenerator.generate_test_suite(
            snapshot_id=snapshot_id,
            target_file=norm_file,
            target_symbol_name=target_symbol_name,
            framework=discovery.framework,
            test_type=test_type,
            target_edge_cases=target_edge_cases,
            existing_test_paths=existing_test_paths,
        )

        run_id = str(uuid4())
        test_artifact_path = discovery.suggested_test_path

        # 3. Create TestArtifact
        artifact = TestArtifact(
            id=str(uuid4()),
            analysis_run_id=run_id,
            snapshot_id=snapshot_id,
            file_path=test_artifact_path,
            content=test_code,
            framework=discovery.framework,
            validation_status=TestArtifactStatus.PENDING,
        )

        # 4. Formulate record and persist
        run_record = TestGenerationRunRecord(
            run_id=run_id,
            snapshot_id=snapshot_id,
            status="COMPLETED",
            target={"file_path": norm_file, "symbol_id": symbol_id},
            target_symbol_name=target_symbol_name,
            target_file_path=norm_file,
            framework=discovery.framework,
            test_type=test_type,
            target_edge_cases=target_edge_cases or [],
            existing_test_paths=existing_test_paths or ["tests/"],
            test_artifact=artifact,
            test_cases=test_cases,
            fixtures=fixtures,
            assumptions=assumptions,
            vacuous_assertions_detected=vacuous,
            created_at=datetime.now(timezone.utc),
            completed_at=datetime.now(timezone.utc),
        )

        self.repo.save_run(run_record)
        return run_record

    def execute_tests(
        self,
        run_id: str,
        consent_execute: bool,
        install_scripts: bool = False,
        approver_id: Optional[str] = None,
        simulate_outcome: Optional[str] = None,
    ) -> TestGenerationRunRecord:
        """Run candidate tests in isolated sandbox, enforcing EXECUTE opt-in gate and two-phase install rules.

        Args:
            run_id: Target test generation run ID.
            consent_execute: User boolean consent.
            install_scripts: If True, marks run HIGH_RISK.
            approver_id: User authorizing execution.
            simulate_outcome: Optional override ('PASSED', 'FAILED', 'ERROR').

        Returns:
            Updated TestGenerationRunRecord with execution results and coverage report.
        """
        record = self.repo.get_run(run_id)
        if not record:
            raise KeyError(f"Test generation run '{run_id}' not found.")

        if not record.test_artifact:
            raise ValueError(f"No test artifact exists for run '{run_id}'.")

        # 1. Execute tests in sandbox
        test_run, test_results = self.sandbox_runner.execute_test_suite(
            run_id=run_id,
            test_artifact=record.test_artifact,
            test_cases=record.test_cases,
            consent_execute=consent_execute,
            install_scripts=install_scripts,
            approver_id=approver_id,
            simulate_outcome=simulate_outcome,
        )

        record.test_run = test_run
        record.test_results = test_results

        # 2. Compute coverage delta
        ctx = SnapshotContextRegistry.get(record.snapshot_id)
        target_f = ctx.get_file(record.target_file_path)
        target_code = target_f.content if target_f else ""

        coverage = CoverageAnalyzer.calculate_coverage_delta(
            test_run_id=test_run.id,
            target_file=record.target_file_path,
            target_code=target_code,
            test_code=record.test_artifact.content,
            tool=f"{record.framework}-cov",
        )
        record.coverage = coverage

        # 3. Update artifact validation status based on test execution
        if test_run.status == TestRunStatus.PASSED:
            record.test_artifact.validation_status = TestArtifactStatus.VALIDATED
        else:
            record.test_artifact.validation_status = TestArtifactStatus.FAILED

        self.repo.save_run(record)
        return record

    def export_patch(self, run_id: str, target_path: Optional[str] = None) -> Tuple[PatchArtifact, str]:
        """Export generated test suite as a unified diff patch integrated into M4 Patch Core.

        Args:
            run_id: Target test run ID.
            target_path: Optional destination file path override.

        Returns:
            Tuple of (PatchArtifact, unified_diff_text).
        """
        record = self.repo.get_run(run_id)
        if not record or not record.test_artifact:
            raise KeyError(f"Test generation run '{run_id}' or artifact not found.")

        dest_path = target_path or record.test_artifact.file_path
        norm_dest = posixpath.normpath(dest_path.replace("\\", "/")).lstrip("/")

        # Construct unified diff creating the new test file
        new_lines = record.test_artifact.content.splitlines(keepends=True)
        orig_lines: List[str] = []

        # Check if file already exists in snapshot (e.g. appending or overwriting)
        ctx = SnapshotContextRegistry.get(record.snapshot_id)
        existing = ctx.get_file(norm_dest)
        if existing:
            orig_lines = existing.content.splitlines(keepends=True)

        diff_chunks = list(
            difflib.unified_diff(
                orig_lines,
                new_lines,
                fromfile=f"a/{norm_dest}",
                tofile=f"b/{norm_dest}",
            )
        )
        unified_diff = "".join(diff_chunks)
        if not unified_diff:
            # Fallback unified diff representation for new file addition
            header = f"--- /dev/null\n+++ b/{norm_dest}\n@@ -0,0 +1,{len(new_lines)} @@\n"
            unified_diff = header + "".join(f"+{line}" if not line.startswith("+") else line for line in new_lines)

        diff_hash = sha256_diff(unified_diff)
        files = inspect_diff(unified_diff)

        # Register in Patch Core (M4) in DRAFT status
        patch = self.patch_mgr.create(
            PatchArtifact(
                snapshot_id=record.snapshot_id,
                source_task=f"Unit test generation for {record.target_file_path}",
                unified_diff=unified_diff,
                diff_sha256=diff_hash,
                files=files,
                rationale=f"Generated unit test suite for {record.target_file_path} covering happy path and edge cases.",
                validation_policy={"syntax": True, "lint": True, "tests": True, "security": True},
            )
        )

        record.patch_id = patch.id
        self.repo.save_run(record)

        return patch, unified_diff
