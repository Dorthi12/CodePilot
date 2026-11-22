"""Deterministic Bug and Security Flaw Detector using AST analysis and pattern matching."""

import ast
import re
from typing import Any, Dict, List, Optional, Set

from shared.types.agent import FindingOrigin, FindingSeverity
from shared.types.findings import Finding
from agentic.common.agent_context import RepositorySnapshotContext
from ai_service.code_analysis.finding_classifier import FindingClassifier


class ASTBugVisitor(ast.NodeVisitor):
    """AST Visitor detecting deterministic bugs in Python code."""

    def __init__(self, file_path: str, lines: List[str]) -> None:
        self.file_path = file_path
        self.lines = lines
        self.findings: List[Dict[str, Any]] = []

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._check_mutable_defaults(node)
        self.generic_visit(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self._check_mutable_defaults(node)
        self.generic_visit(node)

    def generic_visit(self, node: ast.AST) -> None:
        for attr in ("body", "orelse", "finalbody"):
            stmt_list = getattr(node, attr, None)
            if isinstance(stmt_list, list) and stmt_list and isinstance(stmt_list[0], ast.stmt):
                self._check_unreachable_code(stmt_list)
        super().generic_visit(node)

    def _check_mutable_defaults(self, node: Any) -> None:
        """Rule BUG-MUTABLE-DEFAULT: Detect mutable default arguments."""
        args = node.args
        all_defaults = list(args.defaults) + [d for d in getattr(args, "kw_defaults", []) if d is not None]
        for default in all_defaults:
            if isinstance(default, (ast.List, ast.Dict, ast.Set)):
                lineno = getattr(default, "lineno", node.lineno)
                snippet = self.lines[lineno - 1].strip() if lineno <= len(self.lines) else ""
                self.findings.append({
                    "rule_id": "BUG-MUTABLE-DEFAULT",
                    "title": f"Mutable default argument in function '{node.name}'",
                    "line_start": lineno,
                    "line_end": lineno,
                    "severity": FindingSeverity.HIGH,
                    "description": f"Function '{node.name}' uses a mutable default argument. Defaults are instantiated once at module load, persisting mutated state across invocations.",
                    "remediation": "Use None as the default value and initialize the mutable object inside the function body.",
                    "snippet": snippet,
                })
            elif isinstance(default, ast.Call) and isinstance(default.func, ast.Name):
                if default.func.id in ("list", "dict", "set"):
                    lineno = getattr(default, "lineno", node.lineno)
                    snippet = self.lines[lineno - 1].strip() if lineno <= len(self.lines) else ""
                    self.findings.append({
                        "rule_id": "BUG-MUTABLE-DEFAULT",
                        "title": f"Mutable default argument via {default.func.id}() in '{node.name}'",
                        "line_start": lineno,
                        "line_end": lineno,
                        "severity": FindingSeverity.HIGH,
                        "description": f"Function '{node.name}' initializes default argument using mutable factory {default.func.id}().",
                        "remediation": "Use None as default and initialize within the function body.",
                        "snippet": snippet,
                    })

    def _check_unreachable_code(self, body: List[ast.stmt]) -> None:
        """Rule BUG-UNREACHABLE-CODE: Detect statements after return, raise, break, continue."""
        for i, stmt in enumerate(body[:-1]):
            if isinstance(stmt, (ast.Return, ast.Raise, ast.Break, ast.Continue)):
                next_stmt = body[i + 1]
                lineno = getattr(next_stmt, "lineno", stmt.lineno + 1)
                snippet = self.lines[lineno - 1].strip() if lineno <= len(self.lines) else ""
                self.findings.append({
                    "rule_id": "BUG-UNREACHABLE-CODE",
                    "title": "Unreachable code statement following terminal jump",
                    "line_start": lineno,
                    "line_end": getattr(next_stmt, "end_lineno", lineno),
                    "severity": FindingSeverity.LOW,
                    "description": "Statements immediately following a return, raise, break, or continue cannot be executed.",
                    "remediation": "Remove the redundant dead statements or fix the control flow.",
                    "snippet": snippet,
                })
                break

    def visit_Try(self, node: ast.Try) -> None:
        """Rule BUG-BARE-EXCEPT: Detect bare except: clause."""
        for handler in node.handlers:
            if handler.type is None:
                lineno = handler.lineno
                snippet = self.lines[lineno - 1].strip() if lineno <= len(self.lines) else ""
                self.findings.append({
                    "rule_id": "BUG-BARE-EXCEPT",
                    "title": "Bare 'except:' clause catches BaseException",
                    "line_start": lineno,
                    "line_end": lineno,
                    "severity": FindingSeverity.MEDIUM,
                    "description": "A bare 'except:' catches all exceptions, including KeyboardInterrupt and SystemExit, masking fatal errors and complicating debugging.",
                    "remediation": "Specify explicit exception types to catch, e.g., 'except Exception:' or domain-specific exceptions.",
                    "snippet": snippet,
                })
        self.generic_visit(node)

    def visit_Assign(self, node: ast.Assign) -> None:
        """Rule BUG-RESOURCE-LEAK: Detect open() call assigned without context manager."""
        if isinstance(node.value, ast.Call):
            func = node.value.func
            if (isinstance(func, ast.Name) and func.id == "open") or (isinstance(func, ast.Attribute) and func.attr == "open"):
                lineno = node.lineno
                snippet = self.lines[lineno - 1].strip() if lineno <= len(self.lines) else ""
                self.findings.append({
                    "rule_id": "BUG-RESOURCE-LEAK",
                    "title": "Potential file descriptor resource leak: open() without 'with' statement",
                    "line_start": lineno,
                    "line_end": node.lineno,
                    "severity": FindingSeverity.MEDIUM,
                    "description": "Opening files directly with open() rather than a 'with' context manager risks unclosed file descriptors on error.",
                    "remediation": "Use 'with open(...) as f:' context manager to ensure safe resource cleanup.",
                    "snippet": snippet,
                })
        self.generic_visit(node)

    def visit_Assert(self, node: ast.Assert) -> None:
        """Rule BUG-ASSERT-PROD: Assert used in non-test production code."""
        if "test" not in self.file_path.lower():
            lineno = node.lineno
            snippet = self.lines[lineno - 1].strip() if lineno <= len(self.lines) else ""
            self.findings.append({
                "rule_id": "BUG-ASSERT-PROD",
                "title": "Use of 'assert' in production logic",
                "line_start": lineno,
                "line_end": node.lineno,
                "severity": FindingSeverity.LOW,
                "description": "Python assert statements are stripped when run with python -O optimization flags, invalidating validation.",
                "remediation": "Raise explicit exceptions (ValueError, TypeError) instead of relying on assert in production code.",
                "snippet": snippet,
            })
        self.generic_visit(node)


class BugDetector:
    """Detects deterministic bugs, security injection flaws, and exposed credentials."""

    SECRET_PATTERNS = [
        (r"""(?i)(?:api_key|apikey|secret_key|app_secret|password)\s*=\s*['"][a-zA-Z0-9_\-]{16,}['"]""", "SEC-SECRET-001", "Hardcoded credential or API secret"),
        (r"""ghp_[a-zA-Z0-9]{36}""", "SEC-SECRET-002", "GitHub Personal Access Token"),
        (r"""ey[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}""", "SEC-SECRET-003", "Hardcoded JWT Token"),
    ]

    INJECTION_PATTERNS = [
        (r"""(?:f['"].*(?:SELECT|INSERT|UPDATE|DELETE).*(?:\{|%s)|execute(?:_query)?\s*\(.*f['"])""", "SEC-SQLI-001", "Potential SQL injection via formatted query string"),
        (r"""\b(?:eval|exec)\s*\(""", "SEC-CODEI-001", "Execution of dynamic code via unsafe eval() or exec()"),
    ]

    def analyze(
        self,
        context: RepositorySnapshotContext,
        analysis_run_id: str,
        target_files: Optional[Set[str]] = None,
    ) -> List[Finding]:
        """Execute deterministic bug and security checks across snapshot files."""
        findings: List[Finding] = []
        files_to_scan = [
            f for path, f in context.files.items()
            if target_files is None or path in target_files
        ]

        for file_obj in files_to_scan:
            lines = file_obj.content.splitlines()

            # 1. AST-based Bug Analysis (Python)
            if file_obj.language == "python" or file_obj.path.endswith(".py"):
                try:
                    tree = ast.parse(file_obj.content)
                    visitor = ASTBugVisitor(file_obj.path, lines)
                    visitor.visit(tree)

                    for raw in visitor.findings:
                        findings.append(
                            FindingClassifier.create_normalized_finding(
                                snapshot_id=context.snapshot_id,
                                analysis_run_id=analysis_run_id,
                                rule_id=raw["rule_id"],
                                title=raw["title"],
                                file_path=file_obj.path,
                                line_start=raw["line_start"],
                                line_end=raw["line_end"],
                                origin=FindingOrigin.STATIC_TOOL,
                                category="BUG",
                                severity=raw["severity"],
                                tool="codepilot_ast",
                                description=raw["description"],
                                remediation=raw["remediation"],
                                snippet=raw["snippet"],
                            )
                        )
                except SyntaxError:
                    pass

            # 2. Secret Scanning (Redacted snippets, SEC-PI compliant)
            for pattern, rule_id, desc in self.SECRET_PATTERNS:
                for idx, line in enumerate(lines, start=1):
                    match = re.search(pattern, line)
                    if match:
                        # Redact the secret in evidence snippet
                        matched_text = match.group(0)
                        redacted_line = line.replace(matched_text, "[REDACTED_SECRET]")
                        findings.append(
                            FindingClassifier.create_normalized_finding(
                                snapshot_id=context.snapshot_id,
                                analysis_run_id=analysis_run_id,
                                rule_id=rule_id,
                                title=desc,
                                file_path=file_obj.path,
                                line_start=idx,
                                line_end=idx,
                                origin=FindingOrigin.STATIC_TOOL,
                                category="SECURITY",
                                severity=FindingSeverity.CRITICAL,
                                tool="codepilot_secrets",
                                description=f"Exposed secret or sensitive token pattern identified at {file_obj.path}:{idx}.",
                                remediation="Store secrets in environment variables or an enterprise secrets manager (KMS / HashiCorp Vault).",
                                snippet=redacted_line.strip()[:100],
                            )
                        )

            # 3. Injection Flaws (SQL injection, unsafe eval)
            for pattern, rule_id, desc in self.INJECTION_PATTERNS:
                for idx, line in enumerate(lines, start=1):
                    if re.search(pattern, line):
                        findings.append(
                            FindingClassifier.create_normalized_finding(
                                snapshot_id=context.snapshot_id,
                                analysis_run_id=analysis_run_id,
                                rule_id=rule_id,
                                title=desc,
                                file_path=file_obj.path,
                                line_start=idx,
                                line_end=idx,
                                origin=FindingOrigin.STATIC_TOOL,
                                category="SECURITY",
                                severity=FindingSeverity.HIGH,
                                tool="codepilot_sast",
                                description=f"Potential injection risk detected at line {idx}: {desc}",
                                remediation="Use parameterized queries or sanitized safe parsers.",
                                snippet=line.strip()[:100],
                            )
                        )

        return findings
