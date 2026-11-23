"""Test Reporter: Generates structured and markdown reports for synthesized test suites and execution results.

Specifications:
- Master Architecture Specification v2.1 §10 (M5: Output contract)
- API and Data Specification v1.0 §3.4.14
- Security & Testing Specification v1.0 §8.9 (AI-15)
"""

from typing import Any, Dict, List, Optional
from shared.types.testing import (
    CoverageReportRecord,
    TestArtifact,
    TestCaseRecord,
    TestGenerationRunRecord,
    TestResultRecord,
    TestRunRecord,
)


class TestReporter:
    """Produces detailed summary metrics and reports for unit test generation and execution."""

    @staticmethod
    def generate_markdown_summary(record: TestGenerationRunRecord) -> str:
        """Create a Markdown summary detailing test coverage, cases, and sandbox execution status."""
        lines: List[str] = [
            f"# Test Generation Report: `{record.target_file_path}`",
            "",
            f"- **Run ID:** `{record.run_id}`",
            f"- **Framework:** `{record.framework}`",
            f"- **Test Type:** `{record.test_type}`",
            f"- **Artifact Path:** `{record.test_artifact.file_path if record.test_artifact else 'N/A'}`",
            f"- **Validation Status:** `{record.test_artifact.validation_status.value if record.test_artifact else 'PENDING'}`",
            "",
            "## Synthesized Test Cases",
            "",
            "| Test Case | Type | Target Symbol | Expected Outcome |",
            "|---|---|---|---|",
        ]

        for tc in record.test_cases:
            lines.append(f"| `{tc.name}` | {tc.test_type.value} | `{tc.target_symbol or 'file'}` | {tc.expected_behavior} |")

        lines.append("")

        if record.assumptions:
            lines.append("## Explicit Assumptions")
            lines.append("")
            for asm in record.assumptions:
                lines.append(f"- {asm}")
            lines.append("")

        if record.vacuous_assertions_detected:
            lines.append("## Quality Warnings (Vacuous Assertions)")
            lines.append("")
            for w in record.vacuous_assertions_detected:
                lines.append(f"- ⚠️ {w}")
            lines.append("")

        if record.test_run:
            lines.append("## Sandbox Execution Results")
            lines.append("")
            lines.append(f"- **Status:** `{record.test_run.status.value}`")
            lines.append(f"- **Exit Code:** `{record.test_run.exit_code}`")
            lines.append(f"- **Duration:** `{record.test_run.duration_ms:.2f} ms`")
            lines.append(f"- **Risk Level:** `{record.test_run.risk_level}`")
            lines.append("")

        if record.coverage:
            lines.append("## Coverage Delta")
            lines.append("")
            b_pct = record.coverage.before.get("coverage_percent", 0.0)
            a_pct = record.coverage.after.get("coverage_percent", 0.0)
            d_pct = record.coverage.delta.get("delta_percent", 0.0)
            lines.append(f"- **Baseline Coverage:** {b_pct:.1f}%")
            lines.append(f"- **Post-Generation Coverage:** {a_pct:.1f}%")
            lines.append(f"- **Coverage Delta:** `+{d_pct:.1f}%` ({record.coverage.delta.get('status', 'IMPROVED')})")
            lines.append(f"- **Newly Covered Lines:** {record.coverage.delta.get('newly_covered_lines', [])}")
            lines.append("")

        return "\n".join(lines)
