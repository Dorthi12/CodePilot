"""Agentic Workflow for Mastermind Feature 5 (Unit Test Generation).

Specifications:
- Master Architecture Specification v2.1 §10 (M5), §13, §14.2, §14.3
- API and Data Specification v1.0 §3.4.14
- Security & Testing Specification v1.0 §8.9 (AI-15), IT-11, RT-16
"""

from typing import Any, Dict, List, Optional, Tuple

from backend.app.modules.testing.test_manager import TestManager
from backend.app.repositories.test_repository import TestRepository
from shared.types.patch import PatchArtifact
from shared.types.testing import TestGenerationRunRecord


class UnitTestGenerationWorkflow:
    """Agentic workflow coordinating test synthesis, AST validation, execution, and coverage analysis."""

    def __init__(
        self,
        repository: Optional[TestRepository] = None,
        test_manager: Optional[TestManager] = None,
    ) -> None:
        self.repository = repository or TestRepository.get_instance()
        self.test_manager = test_manager or TestManager.instance()

    def run_generation(
        self,
        snapshot_id: str,
        target_file: Optional[str] = None,
        symbol_id: Optional[str] = None,
        framework: str = "pytest",
        test_type: str = "unit",
        target_edge_cases: Optional[List[str]] = None,
        existing_test_paths: Optional[List[str]] = None,
    ) -> TestGenerationRunRecord:
        """Execute test generation workflow for a targeted code file or symbol."""
        return self.test_manager.generate_tests(
            snapshot_id=snapshot_id,
            target_file=target_file,
            symbol_id=symbol_id,
            framework=framework,
            test_type=test_type,
            target_edge_cases=target_edge_cases,
            existing_test_paths=existing_test_paths,
        )

    def execute_suite(
        self,
        run_id: str,
        consent_execute: bool,
        install_scripts: bool = False,
        approver_id: Optional[str] = None,
        simulate_outcome: Optional[str] = None,
    ) -> TestGenerationRunRecord:
        """Run the generated test suite in the isolated sandbox, enforcing the EXECUTE gate."""
        return self.test_manager.execute_tests(
            run_id=run_id,
            consent_execute=consent_execute,
            install_scripts=install_scripts,
            approver_id=approver_id,
            simulate_outcome=simulate_outcome,
        )

    def export_test_patch(
        self,
        run_id: str,
        target_path: Optional[str] = None,
    ) -> Tuple[PatchArtifact, str]:
        """Export candidate test file as unified diff patch integrated with M4 Patch Core."""
        return self.test_manager.export_patch(run_id=run_id, target_path=target_path)
