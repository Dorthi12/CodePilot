"""
Data models for Feature 2: AI Code Explanation.
Conforms to the CodePilot Architecture Specification v2.1 (§8 B6, §3.4.7).
"""

from __future__ import annotations

from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field


class ExplanationStyle(str, Enum):
    BEGINNER = "beginner"
    TECHNICAL = "technical"
    DEEP = "deep"


class CitationItem(BaseModel):
    """Reference citation used to locate and verify the explained code."""
    source_id: str = Field(description="Stable anchor reference ID")
    file_path: str
    start_line: int = Field(ge=1)
    end_line: int = Field(ge=1)
    symbol_name: Optional[str] = None
    snippet: str


class RelatedSymbolContext(BaseModel):
    """Related symbol definition retrieved from repository context via Feature 1."""
    name: str
    kind: str
    file_path: str
    start_line: int
    end_line: int
    snippet: str
    relevance_reason: str


class ExplanationRequest(BaseModel):
    """
    Payload for requesting an AI code explanation.
    Can accept raw code, or file_path + line range, or symbol_id.
    """
    repo_id: str = Field(description="Repository identifier")
    snapshot_id: str = Field(description="Snapshot commit SHA or UUID")
    code: Optional[str] = Field(default=None, description="Explicit selected code snippet")
    file_path: Optional[str] = Field(default=None, description="Path to file in repository")
    start_line: Optional[int] = Field(default=None, ge=1, description="1-based start line")
    end_line: Optional[int] = Field(default=None, ge=1, description="1-based end line")
    symbol_id: Optional[str] = Field(default=None, description="Optional symbol ID anchor")
    question: Optional[str] = Field(
        default=None,
        description="Optional specific question (e.g., 'What does this function do?', 'Are there potential bugs?')"
    )
    explanation_style: ExplanationStyle = Field(
        default=ExplanationStyle.TECHNICAL,
        description="Depth and target audience: beginner | technical | deep"
    )


class ExplanationResponse(BaseModel):
    """
    Structured response containing grounded explanation and context citations.
    """
    repo_id: str
    snapshot_id: str
    file_path: Optional[str] = None
    language: str
    selected_code: str
    question: Optional[str] = None
    explanation_style: str

    # Structured explanation components
    overview: str = Field(description="High-level purpose and summary of the code")
    step_by_step: list[str] = Field(default_factory=list, description="Logical or line-by-line breakdown")
    inputs: Optional[str] = Field(default=None, description="Description of inputs/parameters")
    outputs: Optional[str] = Field(default=None, description="Description of return values and output")
    important_symbols: list[str] = Field(default_factory=list, description="Key variables, functions, or types")
    side_effects: list[str] = Field(default_factory=list, description="State mutations, I/O, or side effects")
    edge_cases: list[str] = Field(default_factory=list, description="Potential boundary conditions or bug vectors")

    # Context and citations (integrated with Feature 1)
    related_symbols: list[RelatedSymbolContext] = Field(
        default_factory=list,
        description="Cross-file or related definitions retrieved from repository index"
    )
    citations: list[CitationItem] = Field(
        default_factory=list,
        description="Citations pointing back to exact file paths and lines"
    )
    limitations: list[str] = Field(
        default_factory=list,
        description="Missing context or unresolvable external references"
    )

    # Formatted markdown presentation
    raw_explanation: str = Field(description="Complete readable markdown explanation")
