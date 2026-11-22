"""Domain models and schemas for Mastermind Feature 5 (Unit Test Generation).

Specifications:
- Master Architecture Specification v2.1 §10 (M5), §11.3, §14.2, §14.3
- API and Data Specification v1.0 §3.3 (Endpoints 085, 086, 087, 088), §3.4.14, §4.6
- Security & Testing Specification v1.0 §7.3.3, §8.9 (AI-15), §14.2
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import uuid4
from pydantic import BaseModel, Field


class TestFramework(str, Enum):
    PYTEST = "pytest"
    UNITTEST = "unittest"
    JEST = "jest"
    VITEST = "vitest"
    JUNIT = "junit"
    GO_TEST = "go"


class TestType(str, Enum):
    UNIT = "unit"
    EDGE_CASE = "edge_case"
    REGRESSION = "regression"
    INTEGRATION = "integration"


class TestArtifactStatus(str, Enum):
    __test__ = False
    PENDING = "PENDING"
    VALIDATED = "VALIDATED"
    FAILED = "FAILED"


class TestRunStatus(str, Enum):
    __test__ = False
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    PASSED = "PASSED"
    FAILED = "FAILED"
    ERROR = "ERROR"
    HIGH_RISK = "HIGH_RISK"


class TestResultStatus(str, Enum):
    PASSED = "PASSED"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"
    ERROR = "ERROR"


class TestArtifact(BaseModel):
    """Generated test code artifact matching API Spec §4.6."""
    id: str = Field(default_factory=lambda: str(uuid4()))
    analysis_run_id: str
    snapshot_id: str
    file_path: str
    content: str
    framework: str = "pytest"
    validation_status: TestArtifactStatus = TestArtifactStatus.PENDING
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class TestCaseRecord(BaseModel):
    """Individual test case covered in the generated test file."""
    id: str = Field(default_factory=lambda: str(uuid4()))
    name: str
    description: str
    test_type: TestType = TestType.UNIT
    target_symbol: Optional[str] = None
    edge_case: Optional[str] = None
    expected_behavior: str
    vacuous: bool = False


class FixtureMockRecord(BaseModel):
    """Fixture, mock, or stub synthesized for test isolation."""
    id: str = Field(default_factory=lambda: str(uuid4()))
    name: str
    target_dependency: str
    fixture_type: str = "fixture"  # fixture, mock, stub
    code_snippet: str


class TestRunRecord(BaseModel):
    """Sandbox execution record matching API Spec §4.6."""
    id: str = Field(default_factory=lambda: str(uuid4()))
    run_id: str
    sandbox_image: str = "python:3.12-slim@sha256:pinned"
    status: TestRunStatus = TestRunStatus.PENDING
    profile: str = "S1"  # S1, S2, S3
    network_mode: str = "none"  # none, proxy_only
    risk_level: str = "STANDARD"  # STANDARD, HIGH_RISK
    limits: Dict[str, Any] = Field(
        default_factory=lambda: {
            "timeout_seconds": 60,
            "max_memory_mb": 2048,
            "max_cpus": 2.0,
            "network": "NONE",
            "read_only_root": True,
            "install_scripts": False,
        }
    )
    started_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    ended_at: Optional[datetime] = None
    duration_ms: float = 0.0
    command: str = "pytest -v"
    exit_code: int = 0
    stdout_redacted: str = ""
    stderr_redacted: str = ""


class TestResultRecord(BaseModel):
    """Result of an individual test case execution."""
    id: str = Field(default_factory=lambda: str(uuid4()))
    test_run_id: str
    test_name: str
    status: TestResultStatus = TestResultStatus.PASSED
    duration_ms: float = 0.0
    failure_ref: Optional[str] = None
    failure_message: Optional[str] = None
    failure_trace_redacted: Optional[str] = None


class CoverageReportRecord(BaseModel):
    """Coverage analysis report before and after test execution."""
    id: str = Field(default_factory=lambda: str(uuid4()))
    test_run_id: str
    tool: str = "pytest-cov"
    target_file: str
    before: Dict[str, Any] = Field(
        default_factory=lambda: {
            "total_lines": 0,
            "covered_lines": 0,
            "coverage_percent": 0.0,
            "missing_lines": [],
        }
    )
    after: Dict[str, Any] = Field(
        default_factory=lambda: {
            "total_lines": 0,
            "covered_lines": 0,
            "coverage_percent": 0.0,
            "missing_lines": [],
        }
    )
    delta: Dict[str, Any] = Field(
        default_factory=lambda: {
            "delta_percent": 0.0,
            "newly_covered_lines": [],
            "status": "IMPROVED",
        }
    )


class TestGenerationRunRecord(BaseModel):
    """Complete aggregate record for an M5 Unit Test Generation run."""
    run_id: str = Field(default_factory=lambda: str(uuid4()))
    snapshot_id: str
    status: str = "COMPLETED"  # CREATED, GENERATING, COMPLETED, EXECUTING, EXECUTED, FAILED
    target: Dict[str, Any] = Field(default_factory=dict)
    target_symbol_name: Optional[str] = None
    target_file_path: str
    framework: str = "pytest"
    test_type: str = "unit"
    target_edge_cases: List[str] = Field(default_factory=list)
    existing_test_paths: List[str] = Field(default_factory=list)
    test_artifact: Optional[TestArtifact] = None
    test_cases: List[TestCaseRecord] = Field(default_factory=list)
    fixtures: List[FixtureMockRecord] = Field(default_factory=list)
    assumptions: List[str] = Field(default_factory=list)
    vacuous_assertions_detected: List[str] = Field(default_factory=list)
    test_run: Optional[TestRunRecord] = None
    test_results: List[TestResultRecord] = Field(default_factory=list)
    coverage: Optional[CoverageReportRecord] = None
    patch_id: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    completed_at: Optional[datetime] = None
    error: Optional[str] = None
