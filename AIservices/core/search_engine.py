"""
Backward-compatibility proxy.
Feature 1: Basic Code Search is now organized under AIservices.features.code_search.
"""

from AIservices.features.code_search.search_engine import (
    search,
    _score,
    _score_exact,
    _score_symbol,
    _score_fuzzy,
    _apply_filters,
)

__all__ = ["search", "_score", "_score_exact", "_score_symbol", "_score_fuzzy", "_apply_filters"]
