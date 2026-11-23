"""Code Smell Detector implementing the Built-in Graph/Metric Rule Pack.

Covers all 11 required rules from Master Spec §9 (A3):
1. Long function
2. High cyclomatic complexity
3. Many parameters
4. Deep nesting
5. Oversized class or file
6. Duplicate code blocks (hash-based clone detection)
7. Unused symbols (no inbound references, excluding entry points)
8. Circular dependencies (direct and multi-hop cycles)
9. God module (high fan-in and fan-out)
10. Public functions with no TESTS edge
11. TODO/FIXME markers
"""

import collections
import hashlib
import re
from typing import Any, Dict, List, Optional, Set, Tuple

from shared.types.agent import FindingOrigin, FindingSeverity
from shared.types.findings import Finding
from agentic.common.agent_context import RepositorySnapshotContext
from ai_service.code_analysis.complexity_analyzer import ComplexityAnalyzer
from ai_service.code_analysis.finding_classifier import FindingClassifier


class RulePackConfig:
    """Configurable thresholds for the Built-in Graph/Metric Rule Pack."""

    def __init__(
        self,
        max_function_lines: int = 50,
        max_cyclomatic_complexity: int = 10,
        max_parameters: int = 5,
        max_nesting_depth: int = 4,
        max_class_lines: int = 300,
        max_file_lines: int = 500,
        clone_min_lines: int = 6,
        god_module_fan_in: int = 5,
        god_module_fan_out: int = 5,
    ) -> None:
        self.max_function_lines = max_function_lines
        self.max_cyclomatic_complexity = max_cyclomatic_complexity
        self.max_parameters = max_parameters
        self.max_nesting_depth = max_nesting_depth
        self.max_class_lines = max_class_lines
        self.max_file_lines = max_file_lines
        self.clone_min_lines = clone_min_lines
        self.god_module_fan_in = god_module_fan_in
        self.god_module_fan_out = god_module_fan_out

    @classmethod
    def get_preset(cls, pack_name: str) -> "RulePackConfig":
        if pack_name == "strict":
            return cls(
                max_function_lines=35,
                max_cyclomatic_complexity=7,
                max_parameters=4,
                max_nesting_depth=3,
                max_class_lines=200,
                max_file_lines=350,
                clone_min_lines=5,
                god_module_fan_in=4,
                god_module_fan_out=4,
            )
        elif pack_name == "lenient":
            return cls(
                max_function_lines=80,
                max_cyclomatic_complexity=15,
                max_parameters=7,
                max_nesting_depth=6,
                max_class_lines=500,
                max_file_lines=800,
                clone_min_lines=8,
                god_module_fan_in=8,
                god_module_fan_out=8,
            )
        elif pack_name == "default":
            return cls()
        raise ValueError(f"Unknown code quality rule pack: {pack_name}")


class CodeSmellDetector:
    """Detects maintainability code smells and structural defects."""

    def __init__(self, config: Optional[RulePackConfig] = None) -> None:
        self.config = config or RulePackConfig()

    def analyze(
        self,
        context: RepositorySnapshotContext,
        analysis_run_id: str,
        target_files: Optional[Set[str]] = None,
    ) -> List[Finding]:
        """Run all built-in smell and graph rules on the repository snapshot."""
        findings: List[Finding] = []
        files_to_scan = [
            f for path, f in context.files.items()
            if target_files is None or path in target_files
        ]

        # 1. Per-file AST Complexity & Metric Checks
        for f in files_to_scan:
            lines = f.content.splitlines()
            loc = len(lines)

            # Rule 5: Oversized file
            if loc > self.config.max_file_lines:
                findings.append(
                    FindingClassifier.create_normalized_finding(
                        snapshot_id=context.snapshot_id,
                        analysis_run_id=analysis_run_id,
                        rule_id="QUAL-SIZE-001",
                        title=f"File exceeds maximum recommended length ({loc} > {self.config.max_file_lines} lines)",
                        file_path=f.path,
                        line_start=1,
                        line_end=min(loc, 10),
                        origin=FindingOrigin.GRAPH_RULE,
                        category="CODE_QUALITY",
                        severity=FindingSeverity.MEDIUM,
                        description=f"File '{f.path}' has {loc} lines, exceeding the recommended limit of {self.config.max_file_lines} lines.",
                        remediation="Decompose this large file into smaller, focused modules according to single responsibility.",
                        snippet=lines[0] if lines else "",
                    )
                )

            # Rule 11: TODO / FIXME markers
            for idx, line in enumerate(lines, start=1):
                match = re.search(r"\b(TODO|FIXME|HACK|XXX)\b\s*[:\-]?(.*)", line, re.IGNORECASE)
                if match:
                    tag = match.group(1).upper()
                    details = match.group(2).strip()[:80]
                    findings.append(
                        FindingClassifier.create_normalized_finding(
                            snapshot_id=context.snapshot_id,
                            analysis_run_id=analysis_run_id,
                            rule_id="QUAL-TODO-001",
                            title=f"Unresolved {tag} marker found: {details or 'pending task'}",
                            file_path=f.path,
                            line_start=idx,
                            line_end=idx,
                            origin=FindingOrigin.STATIC_TOOL,
                            category="CODE_QUALITY",
                            severity=FindingSeverity.INFO,
                            description=f"Encountered temporary debt marker '{tag}' in code: {line.strip()}",
                            remediation=f"Address or convert this {tag} item into a tracked backlog issue.",
                            snippet=line.strip()[:100],
                        )
                    )

            # Analyze Python AST for complexity, parameters, nesting, and classes
            if f.language == "python" or f.path.endswith(".py"):
                ast_metrics = ComplexityAnalyzer.analyze_python_source(f.content)

                # Classes
                for cls_info in ast_metrics["classes"]:
                    c_lines = cls_info["end_line"] - cls_info["start_line"] + 1
                    if c_lines > self.config.max_class_lines:
                        findings.append(
                            FindingClassifier.create_normalized_finding(
                                snapshot_id=context.snapshot_id,
                                analysis_run_id=analysis_run_id,
                                rule_id="QUAL-SIZE-001",
                                title=f"Class '{cls_info['name']}' is oversized ({c_lines} lines)",
                                file_path=f.path,
                                line_start=cls_info["start_line"],
                                line_end=cls_info["end_line"],
                                origin=FindingOrigin.GRAPH_RULE,
                                category="CODE_QUALITY",
                                severity=FindingSeverity.MEDIUM,
                                description=f"Class '{cls_info['name']}' spans {c_lines} lines, exceeding the limit of {self.config.max_class_lines}.",
                                remediation="Extract specialized responsibilities into collaborating classes.",
                                snippet=lines[cls_info["start_line"] - 1].strip() if cls_info["start_line"] <= len(lines) else "",
                            )
                        )

                # Functions
                for fn in ast_metrics["functions"]:
                    # Rule 1: Long Function
                    if fn["line_count"] > self.config.max_function_lines:
                        sev = FindingSeverity.HIGH if fn["line_count"] > self.config.max_function_lines * 2 else FindingSeverity.MEDIUM
                        findings.append(
                            FindingClassifier.create_normalized_finding(
                                snapshot_id=context.snapshot_id,
                                analysis_run_id=analysis_run_id,
                                rule_id="QUAL-LEN-001",
                                title=f"Function '{fn['qualified_name']}' is excessively long ({fn['line_count']} lines)",
                                file_path=f.path,
                                line_start=fn["start_line"],
                                line_end=fn["end_line"],
                                origin=FindingOrigin.GRAPH_RULE,
                                category="CODE_QUALITY",
                                severity=sev,
                                description=f"Function '{fn['qualified_name']}' has {fn['line_count']} lines, exceeding threshold of {self.config.max_function_lines}.",
                                remediation="Decompose into smaller helper functions with distinct sub-tasks.",
                                snippet=lines[fn["start_line"] - 1].strip() if fn["start_line"] <= len(lines) else "",
                            )
                        )

                    # Rule 2: High Cyclomatic Complexity
                    if fn["complexity"] >= self.config.max_cyclomatic_complexity:
                        sev = FindingSeverity.HIGH if fn["complexity"] >= self.config.max_cyclomatic_complexity * 1.5 else FindingSeverity.MEDIUM
                        findings.append(
                            FindingClassifier.create_normalized_finding(
                                snapshot_id=context.snapshot_id,
                                analysis_run_id=analysis_run_id,
                                rule_id="QUAL-COMPLEX-001",
                                title=f"Function '{fn['qualified_name']}' has high cyclomatic complexity ({fn['complexity']})",
                                file_path=f.path,
                                line_start=fn["start_line"],
                                line_end=fn["end_line"],
                                origin=FindingOrigin.GRAPH_RULE,
                                category="CODE_QUALITY",
                                severity=sev,
                                description=f"Cyclomatic complexity of '{fn['qualified_name']}' is {fn['complexity']} (threshold {self.config.max_cyclomatic_complexity}).",
                                remediation="Reduce branching logic, replace nested conditionals with polymorphism, lookup tables, or guard clauses.",
                                snippet=lines[fn["start_line"] - 1].strip() if fn["start_line"] <= len(lines) else "",
                            )
                        )

                    # Rule 3: Many Parameters
                    if fn["param_count"] > self.config.max_parameters:
                        findings.append(
                            FindingClassifier.create_normalized_finding(
                                snapshot_id=context.snapshot_id,
                                analysis_run_id=analysis_run_id,
                                rule_id="QUAL-PARAM-001",
                                title=f"Function '{fn['qualified_name']}' accepts too many parameters ({fn['param_count']} params)",
                                file_path=f.path,
                                line_start=fn["start_line"],
                                line_end=fn["end_line"],
                                origin=FindingOrigin.GRAPH_RULE,
                                category="CODE_QUALITY",
                                severity=FindingSeverity.MEDIUM,
                                description=f"Function '{fn['qualified_name']}' takes {fn['param_count']} parameters (max recommended is {self.config.max_parameters}).",
                                remediation="Introduce parameter objects, configuration dataclasses, or options dictionaries.",
                                snippet=lines[fn["start_line"] - 1].strip() if fn["start_line"] <= len(lines) else "",
                            )
                        )

                    # Rule 4: Deep Nesting
                    if fn["max_nesting"] > self.config.max_nesting_depth:
                        findings.append(
                            FindingClassifier.create_normalized_finding(
                                snapshot_id=context.snapshot_id,
                                analysis_run_id=analysis_run_id,
                                rule_id="QUAL-NEST-001",
                                title=f"Function '{fn['qualified_name']}' has deep control nesting ({fn['max_nesting']} levels)",
                                file_path=f.path,
                                line_start=fn["start_line"],
                                line_end=fn["end_line"],
                                origin=FindingOrigin.GRAPH_RULE,
                                category="CODE_QUALITY",
                                severity=FindingSeverity.MEDIUM,
                                description=f"Deep nesting ({fn['max_nesting']} levels) detected, reducing code readability and testability.",
                                remediation="Use early return guard clauses or extract nested blocks into standalone methods.",
                                snippet=lines[fn["start_line"] - 1].strip() if fn["start_line"] <= len(lines) else "",
                            )
                        )

        # 2. Rule 6: Duplicate Code Blocks (Hash-based clone detection)
        findings.extend(self._detect_code_clones(context, analysis_run_id, target_files))

        # 3. Rule 7: Unused / Dead Symbols
        findings.extend(self._detect_unused_symbols(context, analysis_run_id, target_files))

        # 4. Rule 8: Circular Dependencies
        findings.extend(self._detect_circular_dependencies(context, analysis_run_id, target_files))

        # 5. Rule 9: God Module (High fan-in and fan-out)
        findings.extend(self._detect_god_modules(context, analysis_run_id, target_files))

        # 6. Rule 10: Public functions with no TESTS edge
        findings.extend(self._detect_untested_public_functions(context, analysis_run_id, target_files))

        return findings

    def _detect_code_clones(
        self,
        context: RepositorySnapshotContext,
        analysis_run_id: str,
        target_files: Optional[Set[str]],
    ) -> List[Finding]:
        """Detect duplicate code blocks across files using a sliding window hash approach."""
        findings: List[Finding] = []
        k = self.config.clone_min_lines
        block_hashes: Dict[str, List[Tuple[str, int, int, str]]] = collections.defaultdict(list)

        for path, file_obj in context.files.items():
            lines = file_obj.content.splitlines()
            if len(lines) < k:
                continue

            # Sliding window of k lines
            for i in range(len(lines) - k + 1):
                window = lines[i : i + k]
                # Normalize lines (strip whitespace and skip if mostly blank)
                normalized = [l.strip() for l in window if l.strip()]
                if len(normalized) < k - 1:
                    continue  # skip windows with too many blanks

                window_str = "\n".join(normalized)
                h = hashlib.sha256(window_str.encode("utf-8")).hexdigest()
                block_hashes[h].append((path, i + 1, i + k, window_str))

        # Identify duplicates
        reported_pairs: Set[Tuple[str, str]] = set()
        for h, occurrences in block_hashes.items():
            if len(occurrences) > 1:
                # Group by distinct locations
                first = occurrences[0]
                for second in occurrences[1:]:
                    if first[0] == second[0] and abs(first[1] - second[1]) < k:
                        continue  # Overlapping block in same file

                    pair_key = (f"{first[0]}:{first[1]}", f"{second[0]}:{second[1]}")
                    if pair_key in reported_pairs or (pair_key[1], pair_key[0]) in reported_pairs:
                        continue
                    reported_pairs.add(pair_key)

                    # Only report if at least one file matches target scope
                    if target_files is not None and first[0] not in target_files and second[0] not in target_files:
                        continue

                    snippet = first[3]
                    findings.append(
                        FindingClassifier.create_normalized_finding(
                            snapshot_id=context.snapshot_id,
                            analysis_run_id=analysis_run_id,
                            rule_id="QUAL-CLONE-001",
                            title=f"Duplicate code block ({k}+ identical lines) detected",
                            file_path=first[0],
                            line_start=first[1],
                            line_end=first[2],
                            origin=FindingOrigin.GRAPH_RULE,
                            category="CODE_QUALITY",
                            severity=FindingSeverity.MEDIUM,
                            description=f"Identical code block detected between '{first[0]}:{first[1]}-{first[2]}' and '{second[0]}:{second[1]}-{second[2]}'.",
                            remediation="Extract duplicate logic into a shared helper function or utility module.",
                            snippet=snippet[:100],
                            metadata={"clone_target": f"{second[0]}:{second[1]}-{second[2]}"},
                        )
                    )
        return findings

    def _detect_unused_symbols(
        self,
        context: RepositorySnapshotContext,
        analysis_run_id: str,
        target_files: Optional[Set[str]],
    ) -> List[Finding]:
        """Detect symbols with zero inbound CALLS or REFERENCES edges."""
        findings: List[Finding] = []
        if not context.symbols:
            return findings

        # Inbound references set
        referenced_targets = set()
        for edge in context.edges:
            if edge.relationship in ("CALLS", "REFERENCES", "IMPORTS"):
                referenced_targets.add(edge.target)

        entry_point_names = {"main", "__init__", "app", "handler", "execute", "setUp", "tearDown"}

        for sym in context.symbols:
            if target_files is not None and sym.file_path not in target_files:
                continue
            if sym.kind not in ("FUNCTION", "METHOD", "CLASS"):
                continue

            # Skip common entry points, test functions, and dunder methods
            if (
                sym.name.startswith("__")
                or sym.name.startswith("test_")
                or sym.name in entry_point_names
                or "test" in sym.file_path.lower()
            ):
                continue

            # Check if referenced either by ID or name
            if sym.id not in referenced_targets and sym.name not in referenced_targets and sym.qualified_name not in referenced_targets:
                findings.append(
                    FindingClassifier.create_normalized_finding(
                        snapshot_id=context.snapshot_id,
                        analysis_run_id=analysis_run_id,
                        rule_id="QUAL-DEAD-001",
                        title=f"Unused symbol '{sym.name}' has no inbound calls or references",
                        file_path=sym.file_path,
                        line_start=sym.start_line,
                        line_end=sym.end_line,
                        symbol_id=sym.id,
                        origin=FindingOrigin.GRAPH_RULE,
                        category="CODE_QUALITY",
                        severity=FindingSeverity.LOW,
                        description=f"Symbol '{sym.qualified_name}' is declared but appears to have zero inbound references across the codebase graph.",
                        remediation="Remove dead code if obsolete, or export/invoke it if intended for public use.",
                        snippet=f"def {sym.name}(...)",
                    )
                )
        return findings

    def _detect_circular_dependencies(
        self,
        context: RepositorySnapshotContext,
        analysis_run_id: str,
        target_files: Optional[Set[str]],
    ) -> List[Finding]:
        """Detect circular dependencies in graph edges (direct 2-cycles and multi-hop cycles)."""
        findings: List[Finding] = []
        adj: Dict[str, Set[str]] = collections.defaultdict(set)

        for edge in context.edges:
            if edge.relationship in ("IMPORTS", "DEPENDS_ON"):
                if edge.source != edge.target:
                    adj[edge.source].add(edge.target)

        # 1. Direct 2-cycles A -> B and B -> A
        checked_pairs: Set[Tuple[str, str]] = set()
        for u in list(adj.keys()):
            for v in list(adj[u]):
                if v in adj and u in adj[v]:
                    pair = (min(u, v), max(u, v))
                    if pair not in checked_pairs:
                        checked_pairs.add(pair)
                        if target_files is not None and u not in target_files and v not in target_files:
                            continue
                        findings.append(
                            FindingClassifier.create_normalized_finding(
                                snapshot_id=context.snapshot_id,
                                analysis_run_id=analysis_run_id,
                                rule_id="ARCH-CYCLE-001",
                                title=f"Circular dependency between '{u}' and '{v}'",
                                file_path=u,
                                line_start=1,
                                line_end=1,
                                origin=FindingOrigin.GRAPH_RULE,
                                category="ARCHITECTURE",
                                severity=FindingSeverity.HIGH,
                                description=f"Mutual circular import cycle detected: '{u}' <--> '{v}'. Leads to initialization order bugs and tight coupling.",
                                remediation="Break cycle by extracting shared interfaces or shared dependencies into a separate lower-level module.",
                                snippet=f"{u} <--> {v}",
                                metadata={"cycle_members": [u, v]},
                            )
                        )

        # 2. Tarjan / DFS for 3+ node cycles
        visited: Dict[str, int] = {}  # 0=unvisited, 1=visiting, 2=visited
        path: List[str] = []

        def dfs(node: str) -> None:
            visited[node] = 1
            path.append(node)
            for neighbor in adj.get(node, []):
                if visited.get(neighbor, 0) == 1:
                    # Found cycle
                    cycle_start_idx = path.index(neighbor)
                    cycle_nodes = path[cycle_start_idx:]
                    if len(cycle_nodes) > 2:
                        cycle_key = tuple(sorted(cycle_nodes))
                        if cycle_key not in checked_pairs:
                            checked_pairs.add(cycle_key)  # type: ignore
                            lead_node = cycle_nodes[0]
                            if target_files is None or any(n in target_files for n in cycle_nodes):
                                findings.append(
                                    FindingClassifier.create_normalized_finding(
                                        snapshot_id=context.snapshot_id,
                                        analysis_run_id=analysis_run_id,
                                        rule_id="ARCH-CYCLE-001",
                                        title=f"Multi-node dependency cycle detected: {' -> '.join(cycle_nodes)} -> {neighbor}",
                                        file_path=lead_node,
                                        line_start=1,
                                        line_end=1,
                                        origin=FindingOrigin.GRAPH_RULE,
                                        category="ARCHITECTURE",
                                        severity=FindingSeverity.HIGH,
                                        description=f"Dependency cycle spanning {len(cycle_nodes)} modules: {' -> '.join(cycle_nodes)} -> {neighbor}",
                                        remediation="Refactor the dependency hierarchy to ensure a Directed Acyclic Graph (DAG) architecture.",
                                        snippet=" -> ".join(cycle_nodes),
                                        metadata={"cycle_members": cycle_nodes},
                                    )
                                )
                elif visited.get(neighbor, 0) == 0:
                    dfs(neighbor)
            path.pop()
            visited[node] = 2

        for node in list(adj.keys()):
            if visited.get(node, 0) == 0:
                dfs(node)

        return findings

    def _detect_god_modules(
        self,
        context: RepositorySnapshotContext,
        analysis_run_id: str,
        target_files: Optional[Set[str]],
    ) -> List[Finding]:
        """Detect God Modules with excessive fan-in (dependents) and fan-out (dependencies)."""
        findings: List[Finding] = []
        fan_in: Dict[str, int] = collections.defaultdict(int)
        fan_out: Dict[str, int] = collections.defaultdict(int)

        for edge in context.edges:
            if edge.relationship in ("IMPORTS", "DEPENDS_ON"):
                fan_out[edge.source] += 1
                fan_in[edge.target] += 1

        all_modules = set(fan_in.keys()).union(fan_out.keys())
        for mod in all_modules:
            if target_files is not None and mod not in target_files:
                continue

            fi = fan_in.get(mod, 0)
            fo = fan_out.get(mod, 0)
            if fi >= self.config.god_module_fan_in and fo >= self.config.god_module_fan_out:
                findings.append(
                    FindingClassifier.create_normalized_finding(
                        snapshot_id=context.snapshot_id,
                        analysis_run_id=analysis_run_id,
                        rule_id="ARCH-GOD-001",
                        title=f"God Module detected: '{mod}' has high fan-in ({fi}) and fan-out ({fo})",
                        file_path=mod,
                        line_start=1,
                        line_end=1,
                        origin=FindingOrigin.GRAPH_RULE,
                        category="ARCHITECTURE",
                        severity=FindingSeverity.HIGH,
                        description=f"Module '{mod}' exhibits extreme coupling with fan-in={fi} and fan-out={fo}. It is a central architectural bottleneck.",
                        remediation="Decompose the module into isolated services or use inversion of control (IoC) to reduce dependencies.",
                        snippet=f"Module {mod} (Fan-in: {fi}, Fan-out: {fo})",
                        metadata={"fan_in": fi, "fan_out": fo},
                    )
                )
        return findings

    def _detect_untested_public_functions(
        self,
        context: RepositorySnapshotContext,
        analysis_run_id: str,
        target_files: Optional[Set[str]],
    ) -> List[Finding]:
        """Detect public functions with no inbound TESTS edges."""
        findings: List[Finding] = []
        if not context.symbols:
            return findings

        tested_symbols = set()
        for edge in context.edges:
            if edge.relationship == "TESTS":
                tested_symbols.add(edge.target)

        for sym in context.symbols:
            if target_files is not None and sym.file_path not in target_files:
                continue
            if sym.kind not in ("FUNCTION", "METHOD"):
                continue
            if sym.name.startswith("_") or "test" in sym.file_path.lower():
                continue

            if sym.id not in tested_symbols and sym.name not in tested_symbols and sym.qualified_name not in tested_symbols:
                findings.append(
                    FindingClassifier.create_normalized_finding(
                        snapshot_id=context.snapshot_id,
                        analysis_run_id=analysis_run_id,
                        rule_id="QUAL-TEST-001",
                        title=f"Public function '{sym.qualified_name}' has no unit test coverage",
                        file_path=sym.file_path,
                        line_start=sym.start_line,
                        line_end=sym.end_line,
                        symbol_id=sym.id,
                        origin=FindingOrigin.GRAPH_RULE,
                        category="CODE_QUALITY",
                        severity=FindingSeverity.LOW,
                        description=f"Public routine '{sym.qualified_name}' does not have any corresponding TESTS edge from the test suite.",
                        remediation="Write unit tests covering happy paths and edge cases for this function.",
                        snippet=f"def {sym.name}(...)",
                    )
                )
        return findings
