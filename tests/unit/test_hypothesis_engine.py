"""Unit tests for Hypothesis Engine and Case G0-I-004 benchmark verification.

Specifications:
- Security & Testing Specification v1.0 §8.9 (AI-11), Appendix C.g (Case G0-I-004)
- System Design Specification v1.0 §7.36
"""

import hashlib
import pytest
from shared.types.investigation import (
    EvidenceRole,
    HypothesisStatus,
    ReproductionStatus,
)
from agentic.common.agent_context import (
    RepositorySnapshotContext,
    SnapshotContextRegistry,
    SnapshotSymbol,
)
from ai_service.debugging.call_path_tracer import CallPathTracer
from ai_service.debugging.hypothesis_engine import HypothesisEngine
from ai_service.debugging.stack_trace_parser import StackTraceParser


@pytest.fixture
def g0_snapshot_context() -> RepositorySnapshotContext:
    SnapshotContextRegistry.clear()
    snapshot_id = "snap-g0-i-004"
    ctx = RepositorySnapshotContext(snapshot_id)

    # 1. app/api/routes.py
    routes_code = """from fastapi import APIRouter
from app.auth.service import refresh_access_token

router = APIRouter()

@router.post("/refresh")
def refresh(token: str):
    # Line 18 in Case G0-I-004
    return refresh_access_token(token)
"""
    ctx.add_file("app/api/routes.py", routes_code)

    # 2. app/auth/service.py
    auth_service_code = """class AuthError(Exception):
    pass

def validate_token(token: str):
    # Line 31 in Case G0-I-004
    raise AuthError("token expired")

def refresh_access_token(token: str):
    # Line 48 in Case G0-I-004
    claims = validate_token(token)
    return {"status": "refreshed", "claims": claims}
"""
    ctx.add_file("app/auth/service.py", auth_service_code)

    ctx.add_symbol(
        SnapshotSymbol(
            id="sym-validate-token",
            name="validate_token",
            qualified_name="app.auth.service.validate_token",
            kind="FUNCTION",
            file_path="app/auth/service.py",
            start_line=29,
            end_line=32,
        )
    )
    ctx.add_symbol(
        SnapshotSymbol(
            id="sym-refresh-access-token",
            name="refresh_access_token",
            qualified_name="app.auth.service.refresh_access_token",
            kind="FUNCTION",
            file_path="app/auth/service.py",
            start_line=46,
            end_line=51,
        )
    )

    SnapshotContextRegistry.register(ctx)
    return ctx


def test_case_g0_i_004_benchmark(g0_snapshot_context: RepositorySnapshotContext) -> None:
    """Verify Case G0-I-004 from Security and Testing Specification Appendix C.g."""
    snapshot_id = g0_snapshot_context.snapshot_id
    repo_files = list(g0_snapshot_context.files.keys())

    # Raw trace from Case G0-I-004
    trace = (
        "Traceback (most recent call last):\n"
        '  File "app/api/routes.py", line 18, in refresh\n'
        '  File "app/auth/service.py", line 48, in refresh_access_token\n'
        '  File "app/auth/service.py", line 31, in validate_token\n'
        "AuthError: token expired"
    )

    parser = StackTraceParser()
    parsed_trace = parser.parse(trace, repo_files=repo_files)

    # Expectation 1: All 3 frames mapped to repository paths
    assert len(parsed_trace.frames) == 3
    for f in parsed_trace.frames:
        assert f.is_mapped is True
        assert f.mapped_file_path is not None
        assert not f.is_ambiguous

    assert parsed_trace.frames[0].mapped_file_path == "app/api/routes.py"
    assert parsed_trace.frames[0].line == 18
    assert parsed_trace.frames[1].mapped_file_path == "app/auth/service.py"
    assert parsed_trace.frames[1].line == 48
    assert parsed_trace.frames[2].mapped_file_path == "app/auth/service.py"
    assert parsed_trace.frames[2].line == 31

    # Expectation 2: Reconstruct call path
    tracer = CallPathTracer()
    call_path = tracer.trace_call_path(snapshot_id, parsed_trace.frames, entrypoint="POST /refresh")
    assert len(call_path) == 3
    assert call_path[0].is_entrypoint is True
    assert call_path[1].is_root_cause_candidate is True
    assert call_path[2].is_root_cause_candidate is True

    # Expectation 3: Formulate hypotheses and check root cause location in top 3
    engine = HypothesisEngine()
    hypotheses = engine.generate_hypotheses(
        snapshot_id=snapshot_id,
        run_id="run-g0-i-004",
        issue_description="AuthError: token expired",
        parsed_trace=parsed_trace,
    )

    assert len(hypotheses) >= 2
    # Expectation 4: Hypotheses labelled UNCONFIRMED unless reproduced
    for hyp in hypotheses:
        assert hyp.status == HypothesisStatus.UNCONFIRMED
        assert hyp.rank in [1, 2, 3]

    # Expectation 5: Root cause location (app/auth/service.py, refresh_access_token, lines 48-51)
    # is among the top 3 hypotheses with valid evidence
    top_3_targets = [(h.file_path, h.function) for h in hypotheses[:3]]
    assert ("app/auth/service.py", "refresh_access_token") in top_3_targets

    # Check evidence validity: snippet hashes match SHA256 of snippet
    for hyp in hypotheses:
        assert len(hyp.evidence) > 0
        for ev in hyp.evidence:
            assert ev.owner_type == "HYPOTHESIS"
            assert ev.owner_id == hyp.id
            assert ev.role in [EvidenceRole.SUPPORTS, EvidenceRole.CONTRADICTS]
            # Verify cryptographic hash
            expected_hash = hashlib.sha256(ev.snippet.encode("utf-8")).hexdigest()
            assert ev.snippet_hash == expected_hash
