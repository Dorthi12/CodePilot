"""Unit and integration tests for Mastermind Feature 5 (Unit Test Generation).

Specifications:
- Master Architecture Specification v2.1 §10 (M5), §11.3, §14.2, §14.3
- API and Data Specification v1.0 §3.3 (Endpoints 085, 086, 087, 088), §3.4.14, §4.6
- Security & Testing Specification v1.0 §7.3.3 (SEC-API-05), §8.9 (AI-15), IT-11, RT-16
- Invariants I1 (Pinned snapshot context), I5 (Verifiable evidence), I8 (Patch tracking)
"""

import ast
import pytest
from fastapi.testclient import TestClient

from agentic.common.agent_context import (
    RepositorySnapshotContext,
    SnapshotContextRegistry,
    SnapshotSymbol,
)
from ai_service.generation.test_generator import TestGenerator, VacuousAssertionChecker
from backend.app.main import app
from backend.app.modules.patching.patch_manager import PatchManager
from backend.app.modules.testing.coverage_analyzer import CoverageAnalyzer
from backend.app.modules.testing.test_discovery import TestDiscoveryService
from backend.app.modules.testing.test_execution import ExecutionConsentRequiredError, SandboxTestRunner
from backend.app.modules.testing.test_manager import TestManager
from backend.app.repositories.findings_repository import FindingsRepository
from backend.app.repositories.test_repository import TestRepository
from shared.types.testing import (
    TestArtifactStatus,
    TestRunStatus,
)

client = TestClient(app)


@pytest.fixture(autouse=True)
def clean_test_state():
    """Reset all repositories and snapshot context before and after each test."""
    TestRepository.get_instance().clear()
    FindingsRepository.get_instance().clear()
    PatchManager.instance().clear()
    SnapshotContextRegistry.clear()
    yield
    TestRepository.get_instance().clear()
    FindingsRepository.get_instance().clear()
    PatchManager.instance().clear()
    SnapshotContextRegistry.clear()


@pytest.fixture
def sample_snapshot() -> str:
    """Setup a rich test snapshot containing source code and existing test conventions."""
    snapshot_id = "snap-test-gen-01"
    ctx = RepositorySnapshotContext(snapshot_id)

    # 1. Source file: Auth and Token Service
    ctx.add_file(
        "app/services/auth_service.py",
        """class AuthenticationError(Exception):
    pass

class TokenService:
    def __init__(self, secret_key: str = "default_secret"):
        self.secret_key = secret_key

    def generate_token(self, user_id: str, role: str = "viewer") -> dict:
        if not user_id:
            raise AuthenticationError("user_id cannot be empty")
        return {"token": f"jwt_{user_id}_{role}", "role": role}

    def validate_token(self, token: str) -> bool:
        if not token:
            return False
        return token.startswith("jwt_")

def calculate_checksum(data: str) -> int:
    if not data:
        return 0
    return sum(ord(c) for c in data)
""",
    )

    # 2. Existing test file for discovery conventions
    ctx.add_file(
        "tests/test_existing.py",
        """import pytest

def test_placeholder():
    assert True
""",
    )

    # Register symbols
    ctx.add_symbol(
        SnapshotSymbol(
            id="sym-auth-01",
            name="generate_token",
            qualified_name="app.services.auth_service.TokenService.generate_token",
            kind="FUNCTION",
            file_path="app/services/auth_service.py",
            start_line=8,
            end_line=11,
        )
    )

    SnapshotContextRegistry.register(ctx)
    return snapshot_id


# ==============================================================================
# 1. Test Discovery & TESTS Graph Mapping
# ==============================================================================


def test_test_discovery_mapping(sample_snapshot: str):
    """Verify TestDiscoveryService discovers existing test suites and maps TESTS edges."""
    discovery = TestDiscoveryService.discover_tests(
        snapshot_id=sample_snapshot,
        target_file="app/services/auth_service.py",
    )
    assert discovery.framework == "pytest"
    assert len(discovery.existing_test_files) >= 1
    assert "tests/test_existing.py" in discovery.existing_test_files
    assert discovery.suggested_test_path == "tests/test_auth_service.py"
    assert len(discovery.mapped_tests_edges) >= 1


# ==============================================================================
# 2. AST Test Synthesis & Vacuous Assertion Prevention (Master §14.3)
# ==============================================================================


def test_test_generator_synthesizes_valid_ast(sample_snapshot: str):
    """Verify TestGenerator produces syntactically valid code covering happy paths, edge cases, and exceptions."""
    test_code, test_cases, fixtures, assumptions, vacuous = TestGenerator.generate_test_suite(
        snapshot_id=sample_snapshot,
        target_file="app/services/auth_service.py",
        framework="pytest",
        target_edge_cases=["empty user_id", "none input"],
    )

    # Must be valid Python syntax
    parsed_ast = ast.parse(test_code)
    assert parsed_ast is not None

    # Verify synthesized test cases
    case_names = [tc.name for tc in test_cases]
    assert any("happy_path" in name for name in case_names)
    assert any("edge_cases" in name for name in case_names)
    assert any("raises" in name for name in case_names)

    # Verify no vacuous assertions generated
    assert len(vacuous) == 0


def test_vacuous_assertion_checker_detects_trivial_asserts():
    """Verify VacuousAssertionChecker flags literal True, False, and tautological asserts."""
    bad_code = """
def test_vacuous():
    assert True
    assert 1 == 1
    x = 10
    assert x == x
"""
    tree = ast.parse(bad_code)
    checker = VacuousAssertionChecker({"test_vacuous"})
    checker.visit(tree)

    assert len(checker.vacuous_issues) >= 3
    assert any("literal True" in issue for issue in checker.vacuous_issues)
    assert any("Tautological" in issue for issue in checker.vacuous_issues)


# ==============================================================================
# 3. Coverage Analyzer & Delta Computation
# ==============================================================================


def test_coverage_analyzer_delta_calculation():
    """Verify CoverageAnalyzer computes before/after/delta metrics and newly covered lines."""
    target_code = """
def process(x: int) -> int:
    if x > 0:
        return x * 2
    else:
        return 0
"""
    test_code = "def test_process_happy_path():\n    assert process(5) == 10\ndef test_process_edge_cases():\n    assert process(0) == 0"
    report = CoverageAnalyzer.calculate_coverage_delta(
        test_run_id="run-test-01",
        target_file="app/process.py",
        target_code=target_code,
        test_code=test_code,
    )

    assert report.before["coverage_percent"] < report.after["coverage_percent"]
    assert report.delta["delta_percent"] > 0
    assert report.delta["status"] == "IMPROVED"
    assert len(report.delta["newly_covered_lines"]) > 0


# ==============================================================================
# 4. REST API Endpoint 085: POST /tests/generate
# ==============================================================================


def test_api_generate_tests_success(sample_snapshot: str):
    """Verify E-085: POST /api/v1/tests/generate synthesizes test cases and returns 201 Created."""
    payload = {
        "snapshot_id": sample_snapshot,
        "target": {"file_path": "app/services/auth_service.py"},
        "framework": "pytest",
        "test_type": "unit",
        "target_edge_cases": ["empty user_id", "malformed token"],
        "existing_test_paths": ["tests/"],
    }
    response = client.post("/api/v1/tests/generate", json=payload)
    assert response.status_code == 201
    data = response.json()

    assert data["run_id"] is not None
    assert data["snapshot_id"] == sample_snapshot
    assert data["status"] == "COMPLETED"
    assert data["target_file_path"] == "app/services/auth_service.py"
    assert data["test_artifact"] is not None
    assert data["test_artifact"]["validation_status"] == "PENDING"
    assert len(data["test_cases"]) >= 2
    assert len(data["assumptions"]) >= 1

    # Verify synced with FindingsRepository analysis_runs
    findings_repo = FindingsRepository.get_instance()
    synced_run = findings_repo.get_analysis_run(data["run_id"])
    assert synced_run is not None
    assert synced_run.run_type == "TEST_GEN"


def test_api_generate_tests_by_symbol(sample_snapshot: str):
    """Verify E-085: POST /api/v1/tests/generate resolves target by symbol_id."""
    payload = {
        "snapshot_id": sample_snapshot,
        "target": {"symbol_id": "sym-auth-01"},
        "framework": "pytest",
    }
    response = client.post("/api/v1/tests/generate", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["target_symbol_name"] == "generate_token"
    assert any("generate_token" in tc["name"] for tc in data["test_cases"])


def test_api_generate_tests_snapshot_not_found():
    """Verify E-085: Rejects unknown snapshot with 404."""
    payload = {
        "snapshot_id": "snap-non-existent",
        "target": {"file_path": "app/services/auth_service.py"},
    }
    response = client.post("/api/v1/tests/generate", json=payload)
    assert response.status_code == 404


def test_api_generate_tests_missing_target(sample_snapshot: str):
    """Verify E-085: Rejects payload missing both file_path and symbol_id with 422."""
    payload = {
        "snapshot_id": sample_snapshot,
        "target": {},
    }
    response = client.post("/api/v1/tests/generate", json=payload)
    assert response.status_code == 422


# ==============================================================================
# 5. REST API Endpoint 086: GET /tests/{run_id}
# ==============================================================================


def test_api_get_tests_by_run_id(sample_snapshot: str):
    """Verify E-086: GET /api/v1/tests/{run_id} returns full run details."""
    # First generate
    gen_res = client.post(
        "/api/v1/tests/generate",
        json={
            "snapshot_id": sample_snapshot,
            "target": {"file_path": "app/services/auth_service.py"},
        },
    )
    run_id = gen_res.json()["run_id"]

    # Now retrieve
    get_res = client.get(f"/api/v1/tests/{run_id}")
    assert get_res.status_code == 200
    data = get_res.json()
    assert data["run_id"] == run_id
    assert data["snapshot_id"] == sample_snapshot
    assert data["test_artifact"]["file_path"] == "tests/test_auth_service.py"


def test_api_get_tests_not_found():
    """Verify E-086: Returns 404 for unknown run_id."""
    res = client.get("/api/v1/tests/unknown-uuid-1234")
    assert res.status_code == 404


# ==============================================================================
# 6. REST API Endpoint 087: POST /tests/{run_id}/execute (Security Gates)
# ==============================================================================


def test_api_execute_tests_consent_required_gate(sample_snapshot: str):
    """Verify E-087: Sandboxed execution without consent returns 403 EXECUTE_OPT_IN_REQUIRED."""
    gen_res = client.post(
        "/api/v1/tests/generate",
        json={
            "snapshot_id": sample_snapshot,
            "target": {"file_path": "app/services/auth_service.py"},
        },
    )
    run_id = gen_res.json()["run_id"]

    # Attempt execution with consent.execute = False
    exec_res = client.post(
        f"/api/v1/tests/{run_id}/execute",
        json={"consent": {"execute": False}},
    )
    assert exec_res.status_code == 403
    assert "EXECUTE_OPT_IN_REQUIRED" in exec_res.json()["detail"]


def test_api_execute_tests_success_with_coverage(sample_snapshot: str):
    """Verify E-087: Authorized execution runs in sandbox and populates results + coverage."""
    gen_res = client.post(
        "/api/v1/tests/generate",
        json={
            "snapshot_id": sample_snapshot,
            "target": {"file_path": "app/services/auth_service.py"},
        },
    )
    run_id = gen_res.json()["run_id"]

    # Execute with explicit consent
    exec_res = client.post(
        f"/api/v1/tests/{run_id}/execute",
        json={"consent": {"execute": True, "install_scripts": False}},
    )
    assert exec_res.status_code == 200
    data = exec_res.json()

    # Check execution metrics
    assert data["execution"] is not None
    assert data["execution"]["status"] == "PASSED"
    assert data["execution"]["risk_level"] == "STANDARD"
    assert data["execution"]["limits"]["timeout_seconds"] == 60
    assert len(data["test_results"]) >= 2
    assert all(r["status"] == "PASSED" for r in data["test_results"])

    # Check coverage report
    assert data["coverage"] is not None
    assert data["coverage"]["delta"]["delta_percent"] > 0
    assert data["test_artifact"]["validation_status"] == "VALIDATED"


def test_api_execute_tests_two_phase_install_high_risk(sample_snapshot: str):
    """Verify E-087: install_scripts=True triggers HIGH_RISK classification (Master §14.2)."""
    gen_res = client.post(
        "/api/v1/tests/generate",
        json={
            "snapshot_id": sample_snapshot,
            "target": {"file_path": "app/services/auth_service.py"},
        },
    )
    run_id = gen_res.json()["run_id"]

    # Execute with install_scripts=True
    exec_res = client.post(
        f"/api/v1/tests/{run_id}/execute",
        json={"consent": {"execute": True, "install_scripts": True}},
    )
    assert exec_res.status_code == 200
    data = exec_res.json()
    assert data["execution"]["risk_level"] == "HIGH_RISK"
    assert data["execution"]["limits"]["install_scripts"] is True


# ==============================================================================
# 7. REST API Endpoint 088: POST /tests/{run_id}/export (Patch Core Hand-Off)
# ==============================================================================


def test_api_export_test_patch_and_headers(sample_snapshot: str):
    """Verify E-088: Export generates unified diff, diff_sha256, sets headers, and creates Patch Core artifact."""
    gen_res = client.post(
        "/api/v1/tests/generate",
        json={
            "snapshot_id": sample_snapshot,
            "target": {"file_path": "app/services/auth_service.py"},
        },
    )
    run_id = gen_res.json()["run_id"]

    # Export test suite
    export_res = client.post(f"/api/v1/tests/{run_id}/export")
    assert export_res.status_code == 200
    data = export_res.json()

    assert data["run_id"] == run_id
    assert data["patch_id"] is not None
    assert data["diff_sha256"] is not None
    assert len(data["diff_sha256"]) == 64
    assert "+++ b/tests/test_auth_service.py" in data["unified_diff"]
    assert "def test_" in data["unified_diff"]
    assert export_res.headers["Content-Disposition"].startswith("attachment; filename=")
    assert export_res.headers["X-Content-Type-Options"] == "nosniff"

    # Verify registered in Patch Core (M4)
    patch_artifact = PatchManager.instance().get(data["patch_id"])
    assert patch_artifact is not None
    assert patch_artifact.status == "DRAFT"
    assert patch_artifact.diff_sha256 == data["diff_sha256"]
