"""Bug Investigation Workflow (Mastermind Feature 2).

Specifications:
- Master Architecture Specification v2.1 §10 (M2)
- API and Data Specification v1.0 §3.4.13
- Security and Testing Specification v1.0 §8.9 (AI-11), Appendix C.g (Case G0-I-004)
- System Design Specification v1.0 §7.36: Status stays UNCONFIRMED until reproduction/test.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import uuid4

from shared.types.investigation import (
    DiagnosticKind,
    DiagnosticStatus,
    DiagnosticStep,
    Hypothesis,
    HypothesisStatus,
    InvestigationRecord,
    ReproductionStatus,
)
from agentic.common.agent_context import SnapshotContextRegistry
from ai_service.debugging.call_path_tracer import CallPathTracer
from ai_service.debugging.hypothesis_engine import HypothesisEngine
from ai_service.debugging.stack_trace_parser import StackTraceParser
from ai_service.security_analysis.secret_detector import redact_dict, redact_secrets
from backend.app.repositories.investigation_repository import InvestigationRepository
from sandbox.runner.diagnostic_sandbox import DiagnosticSandboxRunner, ExecutionConsentRequiredError


class BugInvestigationWorkflow:
    """End-to-end workflow coordinating stack parsing, call path tracing, hypothesis generation, and sandboxed reproduction."""

    def __init__(
        self,
        repository: Optional[InvestigationRepository] = None,
        parser: Optional[StackTraceParser] = None,
        tracer: Optional[CallPathTracer] = None,
        hypothesis_engine: Optional[HypothesisEngine] = None,
        sandbox_runner: Optional[DiagnosticSandboxRunner] = None,
    ) -> None:
        self.repo = repository or InvestigationRepository.get_instance()
        self.parser = parser or StackTraceParser()
        self.tracer = tracer or CallPathTracer()
        self.engine = hypothesis_engine or HypothesisEngine()
        self.sandbox = sandbox_runner or DiagnosticSandboxRunner()

    def start_investigation(
        self,
        snapshot_id: str,
        issue_description: str,
        stack_trace: Optional[str] = None,
        failing_test: Optional[str] = None,
        entrypoint: Optional[str] = None,
        environment: Optional[Dict[str, Any]] = None,
    ) -> InvestigationRecord:
        """Execute complete bug investigation and root-cause analysis on a snapshot."""
        run_id = str(uuid4())
        started_at = datetime.now(timezone.utc)

        # 1. Secret Redaction (AUD-11)
        redacted_trace = redact_secrets(stack_trace) if stack_trace else ""
        redacted_env = redact_dict(environment) if environment else {}

        # 2. Get Repository Snapshot Files for Suffix Matching
        ctx = SnapshotContextRegistry.get(snapshot_id)
        repo_files = list(ctx.files.keys())

        # 3. Parse Stack Trace & Map Frames
        parsed_trace = self.parser.parse(redacted_trace, repo_files=repo_files)

        # 4. Reconstruct Call Path
        call_path = self.tracer.trace_call_path(
            snapshot_id=snapshot_id,
            frames=parsed_trace.frames,
            entrypoint=entrypoint,
        )

        # 5. Formulate Ranked Hypotheses & Evidence
        hypotheses = self.engine.generate_hypotheses(
            snapshot_id=snapshot_id,
            run_id=run_id,
            issue_description=issue_description,
            parsed_trace=parsed_trace,
            failing_test=failing_test,
            entrypoint=entrypoint,
        )

        # 6. Aggregate All Evidence References
        all_evidence = []
        for hyp in hypotheses:
            all_evidence.extend(hyp.evidence)

        # 7. Formulate Diagnostic Steps & Next Steps
        diagnostics: List[DiagnosticStep] = []
        next_steps: List[str] = []

        if failing_test:
            diag_cmd = f"pytest {failing_test}"
            primary_hyp_id = hypotheses[0].id if hypotheses else None
            diagnostics.append(
                DiagnosticStep(
                    id=str(uuid4()),
                    run_id=run_id,
                    hypothesis_id=primary_hyp_id,
                    kind=DiagnosticKind.SANDBOX_TEST,
                    command_ref=diag_cmd,
                    status=DiagnosticStatus.PENDING_APPROVAL,
                )
            )
            next_steps.append(
                f"Obtain EXECUTE approval to run sandboxed reproduction test '{diag_cmd}'."
            )
        elif parsed_trace.frames:
            deepest = parsed_trace.frames[-1]
            mapped_file = deepest.mapped_file_path or deepest.raw_file_path
            next_steps.append(
                f"Inspect error handling and caller contracts in '{mapped_file}' at line {deepest.line}."
            )

        if hypotheses:
            next_steps.append(
                f"Review Top Hypothesis: {hypotheses[0].summary}"
            )

        # 8. Construct Problem Summary
        err_str = f"{parsed_trace.error_class}: {parsed_trace.error_message}" if parsed_trace.error_class else issue_description
        problem_summary = f"Bug investigation for reported issue: {err_str}"

        # 9. Build and Persist Investigation Record
        record = InvestigationRecord(
            run_id=run_id,
            snapshot_id=snapshot_id,
            issue_description=issue_description,
            stack_trace_raw=stack_trace,
            stack_trace_redacted=redacted_trace,
            parsed_frames=parsed_trace.frames,
            failing_test=failing_test,
            entrypoint=entrypoint,
            environment_redacted=redacted_env,
            reproduction_status=ReproductionStatus.NOT_REPRODUCED,
            hypotheses=hypotheses,
            call_path=call_path,
            evidence=all_evidence,
            diagnostics=diagnostics,
            next_steps=next_steps,
            problem_summary=problem_summary,
            started_at=started_at,
            completed_at=datetime.now(timezone.utc),
        )

        self.repo.save_investigation(record)
        return record

    def execute_diagnostic(
        self,
        run_id: str,
        consent_execute: bool,
        diagnostic_id: Optional[str] = None,
        approver_id: Optional[str] = None,
        simulate_outcome: Optional[str] = None,
    ) -> DiagnosticStep:
        """Execute a diagnostic step with explicit EXECUTE gate verification."""
        inv = self.repo.get_investigation(run_id)
        if not inv:
            raise KeyError(f"Investigation '{run_id}' not found.")

        # Find diagnostic step
        step: Optional[DiagnosticStep] = None
        if diagnostic_id:
            for d in inv.diagnostics:
                if d.id == diagnostic_id:
                    step = d
                    break
            if not step:
                raise KeyError(f"Diagnostic step '{diagnostic_id}' not found in investigation '{run_id}'.")
        elif inv.diagnostics:
            step = inv.diagnostics[0]
        else:
            # Create ad-hoc diagnostic if test is specified in investigation
            cmd = f"pytest {inv.failing_test}" if inv.failing_test else "pytest tests/"
            step = DiagnosticStep(
                id=str(uuid4()),
                run_id=run_id,
                kind=DiagnosticKind.SANDBOX_TEST,
                command_ref=cmd,
                status=DiagnosticStatus.PENDING_APPROVAL,
            )
            inv.diagnostics.append(step)

        # Run via Sandbox Runner (enforces consent gate)
        test_results = self.sandbox.execute_diagnostic(
            diagnostic=step,
            consent_execute=consent_execute,
            approver_id=approver_id,
            simulate_outcome=simulate_outcome,
        )

        # Update Investigation State based on outcome
        if test_results.get("reproduced"):
            inv.reproduction_status = ReproductionStatus.REPRODUCED
            # Upgrade primary hypothesis status to REPRODUCED / SUPPORTED
            if step.hypothesis_id:
                self.repo.update_hypothesis_status(run_id, step.hypothesis_id, HypothesisStatus.REPRODUCED)
            elif inv.hypotheses:
                inv.hypotheses[0].status = HypothesisStatus.REPRODUCED
        elif test_results.get("exit_code") == 0:
            inv.reproduction_status = ReproductionStatus.NOT_REPRODUCED
            if step.hypothesis_id:
                self.repo.update_hypothesis_status(run_id, step.hypothesis_id, HypothesisStatus.REFUTED)
            elif inv.hypotheses:
                inv.hypotheses[0].status = HypothesisStatus.REFUTED
        else:
            inv.reproduction_status = ReproductionStatus.INCONCLUSIVE

        self.repo.save_investigation(inv)
        return step
