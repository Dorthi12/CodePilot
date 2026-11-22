"""Deterministic static analysis and rule-pack tool for multi-agent evaluation."""

import re
from typing import Any, Dict, List, Optional
from shared.types.agent import ToolPermissionLevel
from agentic.common.agent_context import SnapshotContextRegistry
from agentic.tools.base_tool import BaseAgentTool


class StaticAnalysisTool(BaseAgentTool):
    name = "static_analysis"
    permission_level = ToolPermissionLevel.ANALYZE
    description = "Run deterministic static linting, secret detection, and AST heuristics"

    SECRET_PATTERNS = [
        (r"""(?i)(?:api_key|apikey|secret_key|app_secret|password)\s*=\s*['"][a-zA-Z0-9_\-]{16,}['"]""", "SEC-SECRET-001", "Hardcoded credential or API secret"),
        (r"""ghp_[a-zA-Z0-9]{36}""", "SEC-SECRET-002", "GitHub Personal Access Token"),
        (r"""ey[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}""", "SEC-SECRET-003", "Hardcoded JWT Token"),
    ]

    INJECTION_PATTERNS = [
        (r"""execute\s*\(\s*f['"].*SELECT.*\{.*\}""", "SEC-SQLI-001", "Potential SQL injection via f-string interpolation"),
        (r"""eval\s*\(|exec\s*\(""", "SEC-CODEI-001", "Use of unsafe eval() or exec()"),
    ]

    PERF_PATTERNS = [
        (r"""for\s+.*\s+in\s+.*:\s*\n(?:\s+.*\n)*?\s+for\s+.*\s+in\s+.*:""", "PERF-LOOP-001", "Nested loop detected: potential O(N^2) complexity bottleneck"),
    ]

    def execute(
        self,
        snapshot_id: str,
        category: Optional[str] = None,
        file_path: Optional[str] = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        ctx = SnapshotContextRegistry.get(snapshot_id)
        findings: List[Dict[str, Any]] = []

        files_to_scan = [ctx.files[file_path]] if file_path and file_path in ctx.files else ctx.files.values()

        for file_obj in files_to_scan:
            lines = file_obj.content.splitlines()

            # 1. Security Checks (Secret scanning & injection)
            if not category or category.upper() == "SECURITY":
                for pattern, rule_id, desc in self.SECRET_PATTERNS:
                    for idx, line in enumerate(lines, start=1):
                        if re.search(pattern, line):
                            findings.append(
                                {
                                    "category": "SECURITY",
                                    "rule_id": rule_id,
                                    "severity": "CRITICAL" if "SECRET" in rule_id else "HIGH",
                                    "title": desc,
                                    "file_path": file_obj.path,
                                    "line_start": idx,
                                    "line_end": idx,
                                    "snippet": line.strip()[:100],
                                    "cwe": "CWE-798" if "SECRET" in rule_id else "CWE-89",
                                }
                            )

                for pattern, rule_id, desc in self.INJECTION_PATTERNS:
                    for idx, line in enumerate(lines, start=1):
                        if re.search(pattern, line):
                            findings.append(
                                {
                                    "category": "SECURITY",
                                    "rule_id": rule_id,
                                    "severity": "HIGH",
                                    "title": desc,
                                    "file_path": file_obj.path,
                                    "line_start": idx,
                                    "line_end": idx,
                                    "snippet": line.strip()[:100],
                                    "cwe": "CWE-89" if "SQLI" in rule_id else "CWE-94",
                                }
                            )

            # 2. Code Quality Checks (Function length, complexity)
            if not category or category.upper() == "CODE_QUALITY":
                for sym in ctx.symbols:
                    if sym.file_path == file_obj.path and sym.kind in ("FUNCTION", "METHOD"):
                        length = sym.end_line - sym.start_line + 1
                        if length > 50:
                            findings.append(
                                {
                                    "category": "CODE_QUALITY",
                                    "rule_id": "QUAL-LEN-001",
                                    "severity": "MEDIUM",
                                    "title": f"Function '{sym.name}' exceeds recommended length ({length} lines)",
                                    "file_path": file_obj.path,
                                    "line_start": sym.start_line,
                                    "line_end": sym.end_line,
                                    "snippet": lines[sym.start_line - 1].strip() if sym.start_line <= len(lines) else "",
                                }
                            )
                        if sym.complexity >= 10:
                            findings.append(
                                {
                                    "category": "CODE_QUALITY",
                                    "rule_id": "QUAL-COMPLEX-001",
                                    "severity": "HIGH",
                                    "title": f"Function '{sym.name}' has high cyclomatic complexity ({sym.complexity})",
                                    "file_path": file_obj.path,
                                    "line_start": sym.start_line,
                                    "line_end": sym.end_line,
                                    "snippet": lines[sym.start_line - 1].strip() if sym.start_line <= len(lines) else "",
                                }
                            )

            # 3. Performance Checks
            if not category or category.upper() == "PERFORMANCE":
                for pattern, rule_id, desc in self.PERF_PATTERNS:
                    match = re.search(pattern, file_obj.content)
                    if match:
                        start_pos = match.start()
                        line_no = file_obj.content[:start_pos].count("\n") + 1
                        findings.append(
                            {
                                "category": "PERFORMANCE",
                                "rule_id": rule_id,
                                "severity": "MEDIUM",
                                "title": desc,
                                "file_path": file_obj.path,
                                "line_start": line_no,
                                "line_end": min(len(lines), line_no + 5),
                                "snippet": lines[line_no - 1].strip() if line_no <= len(lines) else "",
                            }
                        )

        # 4. Architecture Checks (Circular dependencies from graph edges)
        if not category or category.upper() == "ARCHITECTURE":
            # Detect 2-cycles A -> B and B -> A
            edge_pairs = set()
            for edge in ctx.edges:
                if edge.relationship in ("IMPORTS", "DEPENDS_ON"):
                    edge_pairs.add((edge.source, edge.target))
                    if (edge.target, edge.source) in edge_pairs and edge.source != edge.target:
                        findings.append(
                            {
                                "category": "ARCHITECTURE",
                                "rule_id": "ARCH-CYCLE-001",
                                "severity": "HIGH",
                                "title": f"Circular dependency detected between '{edge.source}' and '{edge.target}'",
                                "file_path": edge.source,
                                "line_start": 1,
                                "line_end": 1,
                                "snippet": f"{edge.source} <-> {edge.target}",
                            }
                        )

        return {
            "snapshot_id": snapshot_id,
            "category": category,
            "total_findings": len(findings),
            "findings": findings,
        }
