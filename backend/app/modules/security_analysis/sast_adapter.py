"""SAST Adapter coordinating Static Application Security Testing.

Specifications:
- Master Architecture Specification v2.1 §10 (M6), §11.3
- Security and Testing Specification v1.0 §8.8 (IT-16)
"""

import time
from typing import Dict, List, Optional, Tuple
from shared.types.findings import Finding, ToolCoverage, ToolExecutionLog
from ai_service.security_analysis.vulnerability_analyzer import SASTVulnerabilityAnalyzer


class SASTAdapter:
    """Coordinates AST-based static vulnerability scanning and taint tracking."""

    def __init__(self, analyzer: Optional[SASTVulnerabilityAnalyzer] = None) -> None:
        self.analyzer = analyzer or SASTVulnerabilityAnalyzer()

    def run_sast(
        self,
        files: Dict[str, str],
        snapshot_id: str,
        run_id: str,
    ) -> Tuple[List[Finding], ToolCoverage, ToolExecutionLog, List[str]]:
        t0 = time.perf_counter()
        findings: List[Finding] = []
        warnings: List[str] = []
        py_files_scanned = 0

        try:
            for path, content in files.items():
                if path.endswith(".py"):
                    py_files_scanned += 1
                    file_findings, file_warns = self.analyzer.analyze_file(
                        file_path=path,
                        content=content,
                        snapshot_id=snapshot_id,
                        run_id=run_id,
                    )
                    findings.extend(file_findings)
                    warnings.extend(file_warns)

            dur_ms = round((time.perf_counter() - t0) * 1000.0, 2)
            coverage = ToolCoverage(
                tool="sast_analyzer",
                version="1.0.0",
                status="SUCCESS",
                duration_ms=dur_ms,
                files_scanned=py_files_scanned,
                rules_run=10,
                findings_count=len(findings),
            )
            log = ToolExecutionLog(
                run_id=run_id,
                tool="sast_analyzer",
                tool_version="1.0.0",
                status="SUCCESS",
                duration_ms=dur_ms,
                coverage={"files_scanned": py_files_scanned, "python_files": py_files_scanned},
            )
            return findings, coverage, log, warnings

        except Exception as e:
            dur_ms = round((time.perf_counter() - t0) * 1000.0, 2)
            coverage = ToolCoverage(
                tool="sast_analyzer",
                version="1.0.0",
                status="FAILED",
                duration_ms=dur_ms,
                files_scanned=py_files_scanned,
                error=str(e),
            )
            log = ToolExecutionLog(
                run_id=run_id,
                tool="sast_analyzer",
                tool_version="1.0.0",
                status="FAILED",
                duration_ms=dur_ms,
                stderr_redacted=str(e),
            )
            warnings.append(f"SAST tool failure: {str(e)}")
            return findings, coverage, log, warnings
