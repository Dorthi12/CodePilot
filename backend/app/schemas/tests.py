"""Pydantic schemas for Mastermind Feature 5 (Unit Test Generation) API serialization.

Specifications:
- Master Architecture Specification v2.1 §10 (M5), §11.3, §14.2, §14.3
- API and Data Specification v1.0 §3.3 (Endpoints 085, 086, 087, 088), §3.4.14
- Security & Testing Specification v1.0 §7.3.3, §8.9 (AI-15)
"""

from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, model_validator

from shared.types.testing import (
    CoverageReportRecord,
    FixtureMockRecord,
    TestArtifact,
    TestCaseRecord,
    TestResultRecord,
    TestRunRecord,
)


class TestTarget(BaseModel):
    """Specification of the code symbol or file to generate tests for."""
    symbol_id: Optional[str] = Field(default=None, description="UUID of the symbol to test")
    file_path: Optional[str] = Field(default=None, description="Repository-relative file path")

    @model_validator(mode="after")
    def validate_target(self) -> "TestTarget":
        if not self.symbol_id and not self.file_path:
            raise ValueError("Exactly one of 'symbol_id' or 'file_path' must be provided in target.")
        return self


class TestGenerateRequest(BaseModel):
    """Request payload to synthesize unit tests (Endpoint 085)."""
    snapshot_id: str = Field(..., description="Target repository snapshot identifier")
    target: TestTarget = Field(..., description="Target symbol or file")
    framework: str = Field(default="pytest", description="Testing framework (pytest, unittest, jest, vitest, junit, go)")
    test_type: str = Field(default="unit", description="Type of test suite (unit, edge_case, regression, integration)")
    target_edge_cases: List[str] = Field(
        default_factory=list,
        description="Explicit edge cases to test (e.g. empty input, None/null, boundary values)",
    )
    existing_test_paths: List[str] = Field(
        default_factory=lambda: ["tests/"],
        description="Directories or files to inspect for existing test conventions",
    )


class TestConsent(BaseModel):
    """Consent payload enforcing the EXECUTE opt-in security gate and two-phase install rules."""
    execute: bool = Field(..., description="Explicit user authorization granting sandbox code execution")
    install_scripts: bool = Field(
        default=False,
        description="Allow build/install-time scripts in sandbox. If True, run is marked HIGH_RISK (Master §14.2)",
    )
    approver_id: Optional[str] = Field(default=None, description="Approver user ID or token")


class TestExecuteRequest(BaseModel):
    """Request payload to execute candidate tests in the sandbox (Endpoint 087)."""
    consent: TestConsent = Field(..., description="Execution consent and dependency install policies")


class TestExportRequest(BaseModel):
    """Request payload to export candidate tests as a patch (Endpoint 088)."""
    target_path: Optional[str] = Field(
        default=None,
        description="Optional custom destination path for the generated test file",
    )


class TestGenerationReportResponse(BaseModel):
    """Full report returned by test generation and inspection (Endpoints 085, 086, 087)."""
    run_id: str
    snapshot_id: str
    status: str
    target: Dict[str, Any]
    target_symbol_name: Optional[str] = None
    target_file_path: str
    framework: str
    test_type: str
    test_artifact: Optional[TestArtifact] = None
    test_cases: List[TestCaseRecord] = Field(default_factory=list)
    fixtures: List[FixtureMockRecord] = Field(default_factory=list)
    assumptions: List[str] = Field(default_factory=list)
    vacuous_assertions_detected: List[str] = Field(default_factory=list)
    execution: Optional[TestRunRecord] = None
    test_results: List[TestResultRecord] = Field(default_factory=list)
    coverage: Optional[CoverageReportRecord] = None
    patch_id: Optional[str] = None
    created_at: datetime
    completed_at: Optional[datetime] = None
    error: Optional[str] = None


class TestExportResponse(BaseModel):
    """Response payload for exported test patch (Endpoint 088)."""
    run_id: str
    patch_id: str
    snapshot_id: str
    file_path: str
    diff_sha256: str
    unified_diff: str
    status: str = "DRAFT"
    message: str = "Test suite patch exported successfully; ready for M4 review and application."
