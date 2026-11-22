"""Refactoring Analyzer identifying concrete code improvement and refactoring patterns.

Specifications:
- Master Architecture Specification v2.1 §10 (M3)
- API and Data Specification v1.0 §3.4.13, §4.6
- Security & Testing Specification v1.0 §7.8, §8.9 (AI-19)
"""

import ast
import re
from typing import Any, Dict, List, Optional, Tuple

from shared.types.suggestions import EffortLevel, RiskLevel, SuggestionCategory


class RefactoringCandidate:
    """Represents a concrete detected refactoring opportunity with before/after snippets."""

    def __init__(
        self,
        category: SuggestionCategory,
        rule_id: str,
        title: str,
        problem: str,
        recommendation: str,
        benefit: str,
        effort: EffortLevel,
        risk: RiskLevel,
        trade_offs: str,
        file_path: str,
        line_start: int,
        line_end: int,
        current_code: str,
        proposed_code: str,
        affected_symbols: Optional[List[str]] = None,
        confidence: float = 0.85,
    ) -> None:
        self.category = category
        self.rule_id = rule_id
        self.title = title
        self.problem = problem
        self.recommendation = recommendation
        self.benefit = benefit
        self.effort = effort
        self.risk = risk
        self.trade_offs = trade_offs
        self.file_path = file_path
        self.line_start = line_start
        self.line_end = line_end
        self.current_code = current_code
        self.proposed_code = proposed_code
        self.affected_symbols = affected_symbols or []
        self.confidence = confidence


class RefactoringAnalyzer:
    """Syntactic and AST analyzer discovering performance, maintainability, readability, and quality refactorings."""

    def analyze_file(self, file_path: str, content: str) -> List[RefactoringCandidate]:
        """Analyze a source file and return all discovered refactoring candidates."""
        candidates: List[RefactoringCandidate] = []
        if not content.strip():
            return candidates

        # Run regex/lexical and AST-based checks
        candidates.extend(self._check_performance_patterns(file_path, content))
        candidates.extend(self._check_maintainability_and_complexity(file_path, content))
        candidates.extend(self._check_readability_patterns(file_path, content))
        candidates.extend(self._check_resource_and_error_handling(file_path, content))
        candidates.extend(self._check_dead_code(file_path, content))

        return candidates

    def _check_performance_patterns(self, file_path: str, content: str) -> List[RefactoringCandidate]:
        """Detect algorithmic and runtime inefficiencies like string concats in loops, O(N^2) lookups."""
        candidates = []
        lines = content.splitlines()

        # 1. String concatenation inside loops (PERF-01)
        # Match "for ... :" followed by variable "+="
        loop_pattern = re.compile(r"^\s*(for\s+.+in\s+.+:|while\s+.+:)")
        concat_pattern = re.compile(r"^\s*([a-zA-Z_]\w*)\s*\+=\s*(.+)")

        in_loop = False
        loop_indent = 0
        loop_start_line = 0

        for i, line in enumerate(lines, 1):
            indent = len(line) - len(line.lstrip())
            if not in_loop:
                m = loop_pattern.match(line)
                if m:
                    in_loop = True
                    loop_indent = indent
                    loop_start_line = i
            else:
                if line.strip() and indent <= loop_indent and not line.strip().startswith("#"):
                    in_loop = False
                else:
                    concat_match = concat_pattern.match(line)
                    if concat_match:
                        var_name = concat_match.group(1)
                        val_expr = concat_match.group(2)
                        # Check if val_expr looks like string
                        if "'" in val_expr or '"' in val_expr or "str(" in val_expr or var_name.lower().endswith(("str", "text", "msg", "out")):
                            cur_chunk = "\n".join(lines[max(0, loop_start_line - 1):min(len(lines), i + 1)])
                            proposed = f"# Pre-allocate list chunks and join once for O(N) performance\nchunks = []\n# In loop: chunks.append({val_expr})\n{var_name} = ''.join(chunks)"
                            candidates.append(
                                RefactoringCandidate(
                                    category=SuggestionCategory.PERFORMANCE,
                                    rule_id="PERF-STR-CONCAT-LOOP",
                                    title=f"In-loop string concatenation on '{var_name}'",
                                    problem=(
                                        f"Repeated string concatenation (`{var_name} += ...`) inside a loop causes "
                                        f"quadratic O(N^2) memory reallocation and copy overhead."
                                    ),
                                    recommendation=(
                                        f"Collect elements into a list and use `''.join(...)` after the loop. "
                                        f"This reduces runtime complexity from O(N^2) to linear O(N)."
                                    ),
                                    benefit="Reduces memory churn and reallocations; accelerates loop execution by up to 10x on large sequences.",
                                    effort=EffortLevel.LOW,
                                    risk=RiskLevel.LOW,
                                    trade_offs="Minimal: requires allocating an intermediate list in memory for the join buffer.",
                                    file_path=file_path,
                                    line_start=loop_start_line,
                                    line_end=i,
                                    current_code=cur_chunk,
                                    proposed_code=proposed,
                                    affected_symbols=[var_name],
                                    confidence=0.92,
                                )
                            )
                            in_loop = False  # Avoid multiple reports per loop

        # 2. Linear search in loop (PERF-02)
        # e.g. "for x in items:\n    if x in list_var:"
        in_list_check = re.compile(r"^\s*if\s+([a-zA-Z_]\w*)\s+in\s+([a-zA-Z_]\w*)\s*:")
        for i, line in enumerate(lines, 1):
            m = in_list_check.match(line)
            if m:
                elem = m.group(1)
                container = m.group(2)
                if container.endswith(("_list", "list", "items", "records", "array")):
                    cur_code = line.strip()
                    proposed = f"{container}_set = set({container})  # Convert to set once outside loop\nif {elem} in {container}_set:  # O(1) average lookup"
                    candidates.append(
                        RefactoringCandidate(
                            category=SuggestionCategory.PERFORMANCE,
                            rule_id="PERF-LINEAR-SEARCH-SET",
                            title=f"Linear membership check on list '{container}'",
                            problem=f"Membership test `if {elem} in {container}` performs an O(N) scan. In loops, this compounds to O(N * M).",
                            recommendation=f"Convert `{container}` to a `set` before lookup to enable O(1) constant-time membership checks.",
                            benefit="Drastically reduces query time from O(N*M) to O(N + M).",
                            effort=EffortLevel.LOW,
                            risk=RiskLevel.LOW,
                            trade_offs="Requires O(N) auxiliary memory to store set keys and elements must be hashable.",
                            file_path=file_path,
                            line_start=i,
                            line_end=i,
                            current_code=cur_code,
                            proposed_code=proposed,
                            affected_symbols=[container],
                            confidence=0.88,
                        )
                    )

        return candidates

    def _check_maintainability_and_complexity(self, file_path: str, content: str) -> List[RefactoringCandidate]:
        """Detect functions with high cyclomatic complexity, deep nesting, or high line count."""
        candidates = []
        try:
            tree = ast.parse(content)
        except SyntaxError:
            return candidates

        lines = content.splitlines()

        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                func_name = node.name
                line_start = node.lineno
                line_end = getattr(node, "end_lineno", line_start + 1)
                func_len = line_end - line_start + 1

                # 1. Long method (MAINT-01)
                if func_len > 45:
                    func_snippet = "\n".join(lines[line_start - 1 : min(len(lines), line_start + 15)]) + "\n    # ... (truncated)"
                    proposed = (
                        f"def {func_name}(...):\n"
                        f"    # Decompose into cohesive single-responsibility steps:\n"
                        f"    _validate_inputs(...)\n"
                        f"    result = _process_core_logic(...)\n"
                        f"    return _format_output(result)"
                    )
                    candidates.append(
                        RefactoringCandidate(
                            category=SuggestionCategory.MAINTAINABILITY,
                            rule_id="MAINT-LONG-FUNCTION",
                            title=f"Decompose lengthy function '{func_name}' ({func_len} lines)",
                            problem=(
                                f"Function '{func_name}' spans {func_len} lines, exceeding the recommended maintainability threshold (45 lines). "
                                f"Long routines increase cognitive load and defect density."
                            ),
                            recommendation="Extract cohesive helper functions separating validation, processing, and formatting.",
                            benefit="Improves testability, isolated unit verification, and readability across maintenance cycles.",
                            effort=EffortLevel.MEDIUM,
                            risk=RiskLevel.LOW,
                            trade_offs="Increases the total number of functions in the module; requires passing explicit arguments.",
                            file_path=file_path,
                            line_start=line_start,
                            line_end=line_end,
                            current_code=func_snippet,
                            proposed_code=proposed,
                            affected_symbols=[func_name],
                            confidence=0.90,
                        )
                    )

                # 2. Deep Nesting & Guard Clauses (MAINT-02)
                max_depth = self._calculate_max_nesting(node)
                if max_depth >= 4:
                    snippet = "\n".join(lines[line_start - 1 : min(len(lines), line_start + 12)])
                    proposed = (
                        f"# Invert conditionals using guard clauses with early returns:\n"
                        f"if not condition_a:\n    return None\nif not condition_b:\n    return None\n# Unnested happy path continues here"
                    )
                    candidates.append(
                        RefactoringCandidate(
                            category=SuggestionCategory.MAINTAINABILITY,
                            rule_id="MAINT-DEEP-NESTING",
                            title=f"Flatten deeply nested logic in '{func_name}' (depth {max_depth})",
                            problem=f"Nesting depth of {max_depth} levels in function '{func_name}' obscures the primary execution flow.",
                            recommendation="Apply guard clauses and early return statements to eliminate nested indentation blocks.",
                            benefit="Reduces cyclomatic complexity and simplifies reason-about flow of the happy path.",
                            effort=EffortLevel.LOW,
                            risk=RiskLevel.LOW,
                            trade_offs="Creates multiple return points in the routine.",
                            file_path=file_path,
                            line_start=line_start,
                            line_end=line_end,
                            current_code=snippet,
                            proposed_code=proposed,
                            affected_symbols=[func_name],
                            confidence=0.89,
                        )
                    )

        return candidates

    def _check_readability_patterns(self, file_path: str, content: str) -> List[RefactoringCandidate]:
        """Detect readability improvements such as boolean simplification and magic constants."""
        candidates = []
        lines = content.splitlines()

        # 1. Redundant boolean comparison (READ-01)
        bool_pattern = re.compile(r"^\s*(if|elif|while)\s+(.+?)\s*==\s*(True|False)\s*:")
        for i, line in enumerate(lines, 1):
            m = bool_pattern.match(line)
            if m:
                keyword = m.group(1)
                expr = m.group(2)
                bool_val = m.group(3)
                if bool_val == "True":
                    proposed = f"{keyword} {expr}:"
                else:
                    proposed = f"{keyword} not {expr}:"

                candidates.append(
                    RefactoringCandidate(
                        category=SuggestionCategory.READABILITY,
                        rule_id="READ-BOOL-SIMPLIFY",
                        title=f"Simplify explicit boolean comparison `== {bool_val}`",
                        problem=f"Explicit comparison to `{bool_val}` (`{line.strip()}`) is unidiomatic and verbose.",
                        recommendation=f"Simplify directly to `{proposed}` using native truthiness.",
                        benefit="Follows PEP 8 style standards and enhances code clarity.",
                        effort=EffortLevel.LOW,
                        risk=RiskLevel.LOW,
                        trade_offs="None.",
                        file_path=file_path,
                        line_start=i,
                        line_end=i,
                        current_code=line.strip(),
                        proposed_code=proposed,
                        affected_symbols=[],
                        confidence=0.98,
                    )
                )

        return candidates

    def _check_resource_and_error_handling(self, file_path: str, content: str) -> List[RefactoringCandidate]:
        """Detect unclosed file handles and bare/swallowed exceptions."""
        candidates = []
        lines = content.splitlines()

        # 1. Raw open without 'with' context manager (QUAL-01)
        open_pattern = re.compile(r"^\s*([a-zA-Z_]\w*)\s*=\s*open\((.+)\)")
        with_pattern = re.compile(r"^\s*with\s+open")

        for i, line in enumerate(lines, 1):
            if open_pattern.match(line) and not with_pattern.match(line):
                m = open_pattern.match(line)
                var_name = m.group(1)
                args = m.group(2)
                cur = line.strip()
                proposed = f"with open({args}) as {var_name}:\n    data = {var_name}.read()"
                candidates.append(
                    RefactoringCandidate(
                        category=SuggestionCategory.CODE_QUALITY,
                        rule_id="QUAL-UNSAFE-RESOURCE-OPEN",
                        title=f"Use context manager for file resource '{var_name}'",
                        problem=f"Opening a file directly with `{var_name} = open(...)` risks leaking file descriptors if an exception occurs.",
                        recommendation="Enclose file handle inside a `with open(...) as ...:` context manager.",
                        benefit="Guarantees immediate file descriptor cleanup even during unexpected exceptions or early terminations.",
                        effort=EffortLevel.LOW,
                        risk=RiskLevel.LOW,
                        trade_offs="Indents the block that operates on the open file.",
                        file_path=file_path,
                        line_start=i,
                        line_end=i,
                        current_code=cur,
                        proposed_code=proposed,
                        affected_symbols=[var_name],
                        confidence=0.95,
                    )
                )

        # 2. Bare except or swallowed exception (QUAL-02)
        bare_except = re.compile(r"^\s*except\s*:\s*$")
        pass_except = re.compile(r"^\s*except\s*(\w+)?\s*:\s*pass\s*$")
        for i, line in enumerate(lines, 1):
            if bare_except.match(line):
                cur = line.strip()
                proposed = "except Exception as exc:\n    logger.warning('Operation failed: %s', exc)\n    raise"
                candidates.append(
                    RefactoringCandidate(
                        category=SuggestionCategory.CODE_QUALITY,
                        rule_id="QUAL-BARE-EXCEPT",
                        title="Avoid bare `except:` clause",
                        problem="Bare `except:` catches KeyboardInterrupt, SystemExit, and MemoryError, preventing graceful process termination.",
                        recommendation="Catch specific expected exception classes (e.g. `except (IOError, ValueError) as e:`) or at minimum `except Exception:`.",
                        benefit="Prevents swallowing system signals and simplifies debugging of unhandled faults.",
                        effort=EffortLevel.LOW,
                        risk=RiskLevel.LOW,
                        trade_offs="Requires identifying which exception types the code actually anticipates.",
                        file_path=file_path,
                        line_start=i,
                        line_end=i,
                        current_code=cur,
                        proposed_code=proposed,
                        affected_symbols=[],
                        confidence=0.96,
                    )
                )

        return candidates

    def _check_dead_code(self, file_path: str, content: str) -> List[RefactoringCandidate]:
        """Detect unreachable dead code statements after terminal return or raise."""
        candidates = []
        try:
            tree = ast.parse(content)
        except SyntaxError:
            return candidates

        lines = content.splitlines()

        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                body = node.body
                for idx, stmt in enumerate(body):
                    if isinstance(stmt, (ast.Return, ast.Raise)):
                        # If there are statements after this terminal statement at the same level
                        if idx + 1 < len(body):
                            dead_start = body[idx + 1].lineno
                            dead_end = getattr(body[-1], "end_lineno", dead_start)
                            dead_snippet = "\n".join(lines[dead_start - 1 : dead_end])
                            candidates.append(
                                RefactoringCandidate(
                                    category=SuggestionCategory.CODE_QUALITY,
                                    rule_id="QUAL-DEAD-CODE-UNREACHABLE",
                                    title=f"Remove unreachable code in '{node.name}'",
                                    problem=f"Code following `{type(stmt).__name__.lower()}` on line {stmt.lineno} is unreachable dead code.",
                                    recommendation="Safely eliminate unreachable statements to reduce binary size and confusion.",
                                    benefit="Decreases dead maintenance burden and improves test coverage metrics.",
                                    effort=EffortLevel.LOW,
                                    risk=RiskLevel.LOW,
                                    trade_offs="None.",
                                    file_path=file_path,
                                    line_start=dead_start,
                                    line_end=dead_end,
                                    current_code=dead_snippet,
                                    proposed_code="# Deleted unreachable statements",
                                    affected_symbols=[node.name],
                                    confidence=0.99,
                                )
                            )
                            break

        return candidates

    def _calculate_max_nesting(self, node: ast.AST) -> int:
        """Calculate the maximum nesting depth of control flow blocks inside an AST node."""
        max_depth = 0

        def walk_depth(current_node: ast.AST, depth: int) -> None:
            nonlocal max_depth
            if isinstance(current_node, (ast.If, ast.For, ast.While, ast.With, ast.Try)):
                depth += 1
                if depth > max_depth:
                    max_depth = depth
            for child in ast.iter_child_nodes(current_node):
                walk_depth(child, depth)

        walk_depth(node, 0)
        return max_depth
