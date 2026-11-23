"""Unit tests for AST Bug and Security Detector (Feature A3)."""

import pytest
from agentic.common.agent_context import RepositorySnapshotContext
from ai_service.code_analysis.bug_detector import BugDetector


def test_mutable_default_arguments():
    ctx = RepositorySnapshotContext("snap-bug-1")
    code = """def append_item(val, items=[]):
    items.append(val)
    return items

def set_config(key, mapping=dict()):
    mapping[key] = True
    return mapping
"""
    ctx.add_file("app/mutable.py", code, language="python")

    detector = BugDetector()
    findings = detector.analyze(ctx, analysis_run_id="run-b1")

    rule_ids = [f.rule_id for f in findings]
    assert rule_ids.count("BUG-MUTABLE-DEFAULT") == 2
    f1 = findings[0]
    assert f1.origin.value == "STATIC_TOOL"
    assert f1.severity.value == "HIGH"
    assert f1.cwe == "CWE-665"


def test_bare_except_detection():
    ctx = RepositorySnapshotContext("snap-bug-2")
    code = """def risky_task():
    try:
        dangerous_operation()
    except:
        pass
"""
    ctx.add_file("app/except.py", code, language="python")

    detector = BugDetector()
    findings = detector.analyze(ctx, analysis_run_id="run-b2")

    bare_findings = [f for f in findings if f.rule_id == "BUG-BARE-EXCEPT"]
    assert len(bare_findings) == 1
    assert bare_findings[0].severity.value == "MEDIUM"


def test_unreachable_code_detection():
    ctx = RepositorySnapshotContext("snap-bug-3")
    code = """def jump_helper(x):
    if x > 10:
        return x
        print("This will never execute")
    return 0
"""
    ctx.add_file("app/jump.py", code, language="python")

    detector = BugDetector()
    findings = detector.analyze(ctx, analysis_run_id="run-b3")

    dead = [f for f in findings if f.rule_id == "BUG-UNREACHABLE-CODE"]
    assert len(dead) == 1
    assert dead[0].line_start == 4


def test_resource_leak_open_without_with():
    ctx = RepositorySnapshotContext("snap-bug-4")
    code = """def read_data():
    f = open("data.txt", "r")
    data = f.read()
    return data
"""
    ctx.add_file("app/leak.py", code, language="python")

    detector = BugDetector()
    findings = detector.analyze(ctx, analysis_run_id="run-b4")

    leaks = [f for f in findings if f.rule_id == "BUG-RESOURCE-LEAK"]
    assert len(leaks) == 1
    assert leaks[0].cwe == "CWE-775"


def test_assert_used_in_production():
    ctx = RepositorySnapshotContext("snap-bug-5")
    code = """def validate_user(user_id):
    assert user_id > 0, "Invalid ID"
    return user_id
"""
    ctx.add_file("app/service.py", code, language="python")

    detector = BugDetector()
    findings = detector.analyze(ctx, analysis_run_id="run-b5")

    asserts = [f for f in findings if f.rule_id == "BUG-ASSERT-PROD"]
    assert len(asserts) == 1


def test_secret_scanning_redaction():
    ctx = RepositorySnapshotContext("snap-bug-6")
    code = """API_KEY = 'sk_live_1234567890abcdef123456'
GITHUB_TOKEN = 'ghp_ABCDEFGHIJKLMNOPQRSTUVWXYZ1234567890'
"""
    ctx.add_file("app/config.py", code, language="python")

    detector = BugDetector()
    findings = detector.analyze(ctx, analysis_run_id="run-b6")

    secret_findings = [f for f in findings if f.category == "SECURITY"]
    assert len(secret_findings) == 2
    for sf in secret_findings:
        assert sf.severity.value == "CRITICAL"
        assert sf.evidence
        # Verify secret was REDACTED in the evidence snippet (SEC-PI rule)
        for ev in sf.evidence:
            assert "sk_live_" not in ev.snippet
            assert "ghp_ABC" not in ev.snippet
            assert "[REDACTED_SECRET]" in ev.snippet


def test_sql_and_code_injection_detection():
    ctx = RepositorySnapshotContext("snap-bug-7")
    code = """def query_user(username, raw_code):
    query = f"SELECT * FROM users WHERE name = '{username}'"
    eval(raw_code)
"""
    ctx.add_file("app/db_inject.py", code, language="python")

    detector = BugDetector()
    findings = detector.analyze(ctx, analysis_run_id="run-b7")

    rule_ids = [f.rule_id for f in findings]
    assert "SEC-SQLI-001" in rule_ids
    assert "SEC-CODEI-001" in rule_ids
