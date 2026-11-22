"""Code Improvement Workflow (Mastermind Feature 3).

Specifications:
- Master Architecture Specification v2.1 §10 (M3)
- API and Data Specification v1.0 §3.4.13, §4.6
- Security and Testing Specification v1.0 §7.2, §7.3, §7.8, §8.9 (AI-19)
- Invariants I1, I5, I8
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import uuid4

from shared.types.suggestions import (
    ImprovementRunReport,
    SuggestionCategory,
    SuggestionRecord,
)
from agentic.common.agent_context import SnapshotContextRegistry
from ai_service.improvements.improvement_reporter import ImprovementReporter
from ai_service.improvements.recommendation_ranker import RecommendationRanker
from ai_service.improvements.suggestion_engine import SuggestionEngine
from backend.app.repositories.findings_repository import FindingsRepository
from backend.app.repositories.improvement_repository import ImprovementRepository


class CodeImprovementWorkflow:
    """Coordinates end-to-end code analysis, refactoring detection, ranking, and persistence."""

    def __init__(
        self,
        repository: Optional[ImprovementRepository] = None,
        findings_repo: Optional[FindingsRepository] = None,
        engine: Optional[SuggestionEngine] = None,
        ranker: Optional[RecommendationRanker] = None,
        reporter: Optional[ImprovementReporter] = None,
    ) -> None:
        self.repo = repository or ImprovementRepository.get_instance()
        self.findings_repo = findings_repo or FindingsRepository.get_instance()
        self.engine = engine or SuggestionEngine()
        self.ranker = ranker or RecommendationRanker()
        self.reporter = reporter or ImprovementReporter()

    def run_improvement_analysis(
        self,
        snapshot_id: str,
        scope_paths: Optional[List[str]] = None,
        categories: Optional[List[SuggestionCategory]] = None,
        constraints: Optional[List[str]] = None,
        repository_id: Optional[str] = None,
    ) -> ImprovementRunReport:
        """Execute end-to-end code improvement analysis on a snapshot."""
        run_id = str(uuid4())
        started_at = datetime.now(timezone.utc)

        # 1. Verify snapshot context exists
        if not SnapshotContextRegistry.contains(snapshot_id):
            raise KeyError(f"Snapshot '{snapshot_id}' not found in registry.")

        snapshot_ctx = SnapshotContextRegistry.get(snapshot_id)

        # 2. Retrieve active suppressions for repository if provided
        active_suppressions = []
        if repository_id:
            active_suppressions = self.findings_repo.list_suppressions(repository_id)

        # 3. Generate raw suggestions with cryptographic evidence and injection defenses
        raw_suggestions = self.engine.generate_suggestions(
            snapshot_ctx=snapshot_ctx,
            run_id=run_id,
            target_paths=scope_paths,
            categories=categories,
            suppressions=active_suppressions,
            constraints=constraints,
        )

        # 4. Rank by priority score and deduplicate
        ranked_suggestions = self.ranker.rank_and_deduplicate(raw_suggestions)

        # 5. Build consolidated report
        completed_at = datetime.now(timezone.utc)
        report = self.reporter.build_report(
            run_id=run_id,
            snapshot_id=snapshot_id,
            suggestions=ranked_suggestions,
            started_at=started_at,
            completed_at=completed_at,
            status="COMPLETED",
        )

        # 6. Persist to repository
        self.repo.save_report(report)

        return report
