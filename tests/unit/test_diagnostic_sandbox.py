"""Unit tests for Diagnostic Sandbox Runner and EXECUTE opt-in security gate.

Specifications:
- Master Architecture Specification v2.1 §13.3, §14.2
- API and Data Specification v1.0 §1.5 Gate: EXECUTE opt-in
- Security & Testing Specification v1.0 IT-11, RT-16
"""

import pytest
from shared.types.investigation import (
    DiagnosticKind,
    DiagnosticStatus,
    DiagnosticStep,
    HypothesisStatus,
    ReproductionStatus,
)
from agentic.workflows.bug_investigation import BugInvestigationWorkflow
from backend.app.repositories.investigation_repository import InvestigationRepository
from sandbox.runner.diagnostic_sandbox import (
    DiagnosticSandboxRunner,
    ExecutionConsentRequiredError,
)


def test_execute_opt_in_gate_blocks_without_consent() -> None:
    runner = DiagnosticSandboxRunner()
    diag = DiagnosticStep(
        run_id="run-1",
        kind=DiagnosticKind.SANDBOX_TEST,
        command_ref="pytest tests/test_auth.py",
        status=DiagnosticStatus.PENDING_APPROVAL,
    )

    # Without explicit consent, must raise ExecutionConsentRequiredError
    with pytest.raises(ExecutionConsentRequiredError) as exc_info:
        runner.execute_diagnostic(diag, consent_execute=False)

    assert "explicit EXECUTE opt-in approval is required" in str(exc_info.value)
    assert diag.status == DiagnosticStatus.REJECTED


def test_execute_opt_in_gate_allows_with_consent() -> None:
    runner = DiagnosticSandboxRunner()
    diag = DiagnosticStep(
        run_id="run-1",
        kind=DiagnosticKind.SANDBOX_TEST,
        command_ref="pytest tests/test_auth.py::test_refresh",
        status=DiagnosticStatus.PENDING_APPROVAL,
    )

    result = runner.execute_diagnostic(
        diag,
        consent_execute=True,
        approver_id="user_maintainer",
        simulate_outcome="REPRODUCED",
    )

    assert diag.status == DiagnosticStatus.COMPLETED
    assert diag.approved_by == "user_maintainer"
    assert result["reproduced"] is True
    assert result["limits_enforced"]["network"] == "NONE"
    assert result["limits_enforced"]["timeout_seconds"] == 60


def test_workflow_diagnostic_execution_updates_hypothesis_status() -> None:
    repo = InvestigationRepository.get_instance()
    repo.clear()
    workflow = BugInvestigationWorkflow(repository=repo)

    # Start an investigation with a failing test
    inv = workflow.start_investigation(
        snapshot_id="snap-test",
        issue_description="Token expiration handling bug",
        failing_test="tests/test_auth.py::test_refresh",
    )

    assert inv.reproduction_status == ReproductionStatus.NOT_REPRODUCED
    assert len(inv.diagnostics) == 1
    diag_step = inv.diagnostics[0]
    assert diag_step.status == DiagnosticStatus.PENDING_APPROVAL
    assert inv.hypotheses[0].status == HypothesisStatus.UNCONFIRMED

    # Execute with consent
    completed_diag = workflow.execute_diagnostic(
        run_id=inv.run_id,
        consent_execute=True,
        diagnostic_id=diag_step.id,
        approver_id="admin_user",
        simulate_outcome="REPRODUCED",
    )

    assert completed_diag.status == DiagnosticStatus.COMPLETED
    updated_inv = repo.get_investigation(inv.run_id)
    assert updated_inv.reproduction_status == ReproductionStatus.REPRODUCED
    assert updated_inv.hypotheses[0].status == HypothesisStatus.REPRODUCED
