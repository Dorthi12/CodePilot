"""
Feature 2: AI Code Explanation Package.
Exposes models and explanation orchestrator.
"""

from AIservices.features.code_explanation.explanation_engine import explain_code
from AIservices.features.code_explanation.models import (
    CitationItem,
    ExplanationRequest,
    ExplanationResponse,
    ExplanationStyle,
    RelatedSymbolContext,
)

__all__ = [
    "explain_code",
    "ExplanationRequest",
    "ExplanationResponse",
    "ExplanationStyle",
    "CitationItem",
    "RelatedSymbolContext",
]
