"""Unit tests for Built-in Graph/Metric Rule Pack in CodeSmellDetector (Feature A3)."""

import pytest
from agentic.common.agent_context import (
    GraphEdge,
    RepositorySnapshotContext,
    SnapshotFile,
    SnapshotSymbol,
)
from ai_service.code_analysis.code_smell_detector import CodeSmellDetector, RulePackConfig


def test_long_function_and_complexity():
    ctx = RepositorySnapshotContext("snap-smell-1")

    # Python function with 60 lines and many branches (complexity >= 10)
    func_lines = ["def complex_routine(a, b):"]
    for i in range(12):
        func_lines.append(f"    if a == {i}:")
        func_lines.append(f"        print({i})")
    for i in range(35):
        func_lines.append(f"    x_{i} = {i}")
    func_lines.append("    return a + b")

    content = "\n".join(func_lines)
    ctx.add_file("app/heavy.py", content, language="python")

    detector = CodeSmellDetector(RulePackConfig(max_function_lines=40, max_cyclomatic_complexity=8))
    findings = detector.analyze(ctx, analysis_run_id="run-1")

    rule_ids = [f.rule_id for f in findings]
    assert "QUAL-LEN-001" in rule_ids
    assert "QUAL-COMPLEX-001" in rule_ids

    len_finding = next(f for f in findings if f.rule_id == "QUAL-LEN-001")
    assert len_finding.origin.value == "GRAPH_RULE"
    assert len_finding.file_path == "app/heavy.py"

    complex_finding = next(f for f in findings if f.rule_id == "QUAL-COMPLEX-001")
    assert complex_finding.severity.value in ("HIGH", "MEDIUM")


def test_too_many_parameters_and_deep_nesting():
    ctx = RepositorySnapshotContext("snap-smell-2")

    content = """def deeply_nested_func(p1, p2, p3, p4, p5, p6, p7):
    if p1:
        while p2:
            for x in p3:
                if p4:
                    if p5:
                        return x
    return None
"""
    ctx.add_file("app/nested.py", content, language="python")

    detector = CodeSmellDetector(RulePackConfig(max_parameters=5, max_nesting_depth=4))
    findings = detector.analyze(ctx, analysis_run_id="run-2")

    rule_ids = [f.rule_id for f in findings]
    assert "QUAL-PARAM-001" in rule_ids
    assert "QUAL-NEST-001" in rule_ids


def test_oversized_file_and_class():
    ctx = RepositorySnapshotContext("snap-smell-3")

    # File with 55 lines when max is 40
    lines = [f"# line {i}" for i in range(60)]
    ctx.add_file("app/oversized.py", "\n".join(lines), language="python")

    # Class with 30 lines when max is 20
    class_code = """class MonsterClass:
    def __init__(self):
        self.val = 0
""" + "\n".join([f"    def method_{i}(self):\n        pass" for i in range(15)])
    ctx.add_file("app/monster.py", class_code, language="python")

    detector = CodeSmellDetector(RulePackConfig(max_file_lines=40, max_class_lines=20))
    findings = detector.analyze(ctx, analysis_run_id="run-3")

    size_findings = [f for f in findings if f.rule_id == "QUAL-SIZE-001"]
    assert len(size_findings) >= 2


def test_todo_and_fixme_detection():
    ctx = RepositorySnapshotContext("snap-smell-4")
    content = """# TODO: Refactor this database connection pool
def connect():
    # FIXME: Handle SSL certificate validation error
    pass
"""
    ctx.add_file("app/db.py", content, language="python")

    detector = CodeSmellDetector()
    findings = detector.analyze(ctx, analysis_run_id="run-4")

    todo_findings = [f for f in findings if f.rule_id == "QUAL-TODO-001"]
    assert len(todo_findings) == 2
    assert any("TODO" in f.title for f in todo_findings)
    assert any("FIXME" in f.title for f in todo_findings)


def test_code_clone_detection():
    ctx = RepositorySnapshotContext("snap-smell-5")

    clone_block = """    token = generate_session_token()
    timestamp = get_utc_timestamp()
    record = create_audit_record(token, timestamp)
    validate_permissions(record)
    save_to_database(record)
    notify_listeners(record)"""

    file1 = f"""def process_user_action():
{clone_block}
    return True
"""
    file2 = f"""def process_admin_action():
{clone_block}
    return False
"""
    ctx.add_file("app/user.py", file1, language="python")
    ctx.add_file("app/admin.py", file2, language="python")

    detector = CodeSmellDetector(RulePackConfig(clone_min_lines=6))
    findings = detector.analyze(ctx, analysis_run_id="run-5")

    clone_findings = [f for f in findings if f.rule_id == "QUAL-CLONE-001"]
    assert len(clone_findings) >= 1
    assert "QUAL-CLONE-001" in [f.rule_id for f in clone_findings]


def test_unused_dead_symbols():
    ctx = RepositorySnapshotContext("snap-smell-6")
    ctx.add_file("app/unused.py", "def obsolete_helper():\n    return 42\n", language="python")
    ctx.add_symbol(
        SnapshotSymbol(
            id="sym-dead-1",
            name="obsolete_helper",
            qualified_name="app.unused.obsolete_helper",
            kind="FUNCTION",
            file_path="app/unused.py",
            start_line=1,
            end_line=2,
        )
    )

    detector = CodeSmellDetector()
    findings = detector.analyze(ctx, analysis_run_id="run-6")

    dead_findings = [f for f in findings if f.rule_id == "QUAL-DEAD-001"]
    assert len(dead_findings) == 1
    assert "obsolete_helper" in dead_findings[0].title


def test_circular_dependencies():
    ctx = RepositorySnapshotContext("snap-smell-7")
    ctx.add_file("app/service_a.py", "import app.service_b\n", language="python")
    ctx.add_file("app/service_b.py", "import app.service_a\n", language="python")

    ctx.add_edge(source="app/service_a.py", target="app/service_b.py", relationship="IMPORTS")
    ctx.add_edge(source="app/service_b.py", target="app/service_a.py", relationship="IMPORTS")

    detector = CodeSmellDetector()
    findings = detector.analyze(ctx, analysis_run_id="run-7")

    cycle_findings = [f for f in findings if f.rule_id == "ARCH-CYCLE-001"]
    assert len(cycle_findings) >= 1
    assert cycle_findings[0].category == "ARCHITECTURE"
    assert cycle_findings[0].severity.value == "HIGH"


def test_god_module_detection():
    ctx = RepositorySnapshotContext("snap-smell-8")
    ctx.add_file("app/god_core.py", "# central core\n", language="python")

    # 5 incoming imports and 5 outgoing imports
    for i in range(5):
        client = f"app/client_{i}.py"
        ctx.add_file(client, "pass\n")
        ctx.add_edge(source=client, target="app/god_core.py", relationship="IMPORTS")

    for i in range(5):
        dep = f"app/dep_{i}.py"
        ctx.add_file(dep, "pass\n")
        ctx.add_edge(source="app/god_core.py", target=dep, relationship="IMPORTS")

    detector = CodeSmellDetector(RulePackConfig(god_module_fan_in=5, god_module_fan_out=5))
    findings = detector.analyze(ctx, analysis_run_id="run-8")

    god_findings = [f for f in findings if f.rule_id == "ARCH-GOD-001"]
    assert len(god_findings) >= 1
    assert "god_core.py" in god_findings[0].title


def test_untested_public_functions():
    ctx = RepositorySnapshotContext("snap-smell-9")
    ctx.add_file("app/api.py", "def public_endpoint():\n    pass\n", language="python")
    ctx.add_symbol(
        SnapshotSymbol(
            id="sym-pub-1",
            name="public_endpoint",
            qualified_name="app.api.public_endpoint",
            kind="FUNCTION",
            file_path="app/api.py",
            start_line=1,
            end_line=2,
        )
    )

    detector = CodeSmellDetector()
    findings = detector.analyze(ctx, analysis_run_id="run-9")

    untested = [f for f in findings if f.rule_id == "QUAL-TEST-001"]
    assert len(untested) == 1
    assert "public_endpoint" in untested[0].title
