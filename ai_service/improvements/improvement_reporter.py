"""Improvement Reporter summarizing and aggregating improvement suggestion runs.

Specifications:
- Master Architecture Specification v2.1 §10 (M3)
- API and Data Specification v1.0 §3.4.13, §4.6
"""

from collections import Counter
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from shared.types.suggestions import ImprovementRunReport, SuggestionRecord


class ImprovementReporter:
    """Consolidates suggestions into a comprehensive, grouped report with hotspot metrics."""

    def build_report(
        self,
        run_id: str,
        snapshot_id: str,
        suggestions: List[SuggestionRecord],
        started_at: datetime,
        completed_at: Optional[datetime] = None,
        status: str = "COMPLETED",
    ) -> ImprovementRunReport:
        """Construct structured ImprovementRunReport with category, effort, risk, and hotspot breakdowns."""
        comp_time = completed_at or datetime.now(timezone.utc)

        # Count by category
        cat_counter = Counter(s.category.value for s in suggestions)
        # Count by status
        status_counter = Counter(s.status.value for s in suggestions)
        # Count by effort
        effort_counter = Counter(s.effort.value for s in suggestions)
        # Count by risk
        risk_counter = Counter(s.risk.value for s in suggestions)

        # Identify hotspot files
        file_counter: Counter = Counter()
        for s in suggestions:
            for f in s.affected_files:
                file_counter[f] += 1

        hotspots = [
            {"file_path": path, "suggestion_count": count}
            for path, count in file_counter.most_common(10)
        ]

        return ImprovementRunReport(
            run_id=run_id,
            snapshot_id=snapshot_id,
            status=status,
            total_suggestions=len(suggestions),
            counts_by_category=dict(cat_counter),
            counts_by_status=dict(status_counter),
            counts_by_effort=dict(effort_counter),
            counts_by_risk=dict(risk_counter),
            hotspot_files=hotspots,
            suggestions=suggestions,
            started_at=started_at,
            completed_at=comp_time,
        )

    def generate_markdown_summary(self, report: ImprovementRunReport) -> str:
        """Produce human-readable markdown summary for dashboard or CLI export."""
        lines = [
            f"# Code Improvement Report (Run: {report.run_id[:8]})",
            f"**Snapshot:** `{report.snapshot_id}` | **Status:** `{report.status}` | **Total Suggestions:** {report.total_suggestions}",
            "",
            "## Summary by Category",
        ]
        for cat, cnt in report.counts_by_category.items():
            lines.append(f"- **{cat}:** {cnt}")

        lines.extend(["", "## Top Hotspots"])
        for h in report.hotspot_files:
            lines.append(f"- `{h['file_path']}`: {h['suggestion_count']} suggestions")

        lines.extend(["", "## Prioritized Suggestions"])
        for idx, s in enumerate(report.suggestions[:10], 1):
            lines.append(
                f"{idx}. **[{s.category.value}] {s.title}** (Priority: {s.priority_score:.1f}, Effort: {s.effort.value}, Risk: {s.risk.value})\n"
                f"   - *Problem:* {s.problem}\n"
                f"   - *Recommendation:* {s.recommendation}\n"
                f"   - *Benefit:* {s.benefit}"
            )

        return "\n".join(lines)
