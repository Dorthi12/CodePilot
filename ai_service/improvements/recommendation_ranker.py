"""Recommendation Ranker for prioritizing and deduplicating improvement suggestions.

Specifications:
- Master Architecture Specification v2.1 §10 (M3)
- API and Data Specification v1.0 §3.4.13, §4.6
- Security and Testing Specification v1.0 §8.9 (AI-19)
"""

from typing import List, Set
from shared.types.suggestions import EffortLevel, RiskLevel, SuggestionCategory, SuggestionRecord


class RecommendationRanker:
    """Computes multidimensional impact/effort/risk priority scores and deduplicates recommendations."""

    # Category impact weights
    CATEGORY_WEIGHTS = {
        SuggestionCategory.ARCHITECTURE: 5.0,
        SuggestionCategory.PERFORMANCE: 4.5,
        SuggestionCategory.CODE_QUALITY: 4.0,
        SuggestionCategory.MAINTAINABILITY: 3.5,
        SuggestionCategory.READABILITY: 2.5,
    }

    # Effort penalty weights
    EFFORT_WEIGHTS = {
        EffortLevel.LOW: 1.0,
        EffortLevel.MEDIUM: 1.6,
        EffortLevel.HIGH: 2.8,
    }

    # Risk penalty weights
    RISK_WEIGHTS = {
        RiskLevel.LOW: 1.0,
        RiskLevel.MEDIUM: 1.5,
        RiskLevel.HIGH: 2.5,
    }

    @classmethod
    def calculate_priority_score(
        cls,
        category: SuggestionCategory,
        confidence: float,
        effort: EffortLevel,
        risk: RiskLevel,
    ) -> float:
        """Calculate weighted priority score balancing impact and confidence against effort and risk."""
        impact = cls.CATEGORY_WEIGHTS.get(category, 3.0)
        effort_w = cls.EFFORT_WEIGHTS.get(effort, 1.5)
        risk_w = cls.RISK_WEIGHTS.get(risk, 1.5)

        # Scale by 10 for clean user-facing scores (e.g. 5.0 to 50.0)
        raw_score = (impact * confidence) / (effort_w * risk_w) * 10.0
        return round(raw_score, 2)

    def rank_and_deduplicate(self, suggestions: List[SuggestionRecord]) -> List[SuggestionRecord]:
        """Rank suggestions in descending order of priority score and deduplicate redundant spans."""
        # Compute and assign priority scores
        for s in suggestions:
            s.priority_score = self.calculate_priority_score(
                category=s.category,
                confidence=s.confidence,
                effort=s.effort,
                risk=s.risk,
            )

        # Sort descending by priority score, then confidence
        sorted_suggestions = sorted(
            suggestions,
            key=lambda item: (item.priority_score, item.confidence),
            reverse=True,
        )

        # Deduplicate based on fingerprint or file + line overlap + rule
        seen_fingerprints: Set[str] = set()
        seen_spans: Set[str] = set()
        deduped: List[SuggestionRecord] = []

        for s in sorted_suggestions:
            if s.fingerprint in seen_fingerprints:
                continue

            # Check file + line span overlap
            file_key = s.affected_files[0] if s.affected_files else ""
            line_start = s.evidence[0].line_start if s.evidence else 0
            span_key = f"{file_key}:{line_start}:{s.rule_id}"

            if span_key in seen_spans:
                continue

            seen_fingerprints.add(s.fingerprint)
            seen_spans.add(span_key)
            deduped.append(s)

        return deduped
