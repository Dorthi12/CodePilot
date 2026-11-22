"""Pydantic v2 schemas for Mastermind Feature 7 (Pull Request Reviews & Webhooks).

Specifications:
- Master Architecture Specification v2.1 §10 (M7), §11.3 (Endpoints 091–096)
- API and Data Specification v1.0 §3.3, §3.4.15, §3.10
- Security and Testing Specification v1.0 §7.3.10, §7.9
"""

from datetime import datetime
from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, Field

from shared.types.agent import FindingSeverity
from shared.types.findings import FindingEvidence
from shared.types.pull_requests import PRState, ReviewCommentStatus


class WebhookReceiptResponse(BaseModel):
    """Response returned upon receiving a webhook (fast 202/200 response)."""
    status: str = "ACCEPTED"
    delivery_id: str
    event: str
    action: Optional[str] = None
    processed: bool = True
    message: str = "Webhook delivery accepted."


class PullRequestItem(BaseModel):
    """PR summary item for listing and sync."""
    id: str
    repository_id: str
    number: int
    title: str
    author_login: str
    base_ref: str
    head_ref: str
    head_repo_full_name: Optional[str] = None
    base_sha: str
    head_sha: str
    base_snapshot_id: Optional[str] = None
    head_snapshot_id: Optional[str] = None
    state: PRState = PRState.OPEN
    is_fork: bool = False
    draft: bool = False
    last_synced_at: Optional[datetime] = None
    latest_review_run_id: Optional[str] = None


class PullRequestListResponse(BaseModel):
    """Response for GET /repositories/{id}/pull-requests."""
    repository_id: str
    pull_requests: List[PullRequestItem] = Field(default_factory=list)
    total: int = 0


class ReviewRunCreateRequest(BaseModel):
    """Request body for POST /pull-requests/{id}/review-runs (Endpoint 093)."""
    base_sha: str = Field(min_length=7, max_length=40, description="Base commit SHA")
    head_sha: str = Field(min_length=7, max_length=40, description="Head commit SHA")
    review_profile: str = Field(default="standard", description="Review profile: standard, security, strict")
    unified_diff: Optional[str] = Field(default=None, max_length=2_000_000, description="Optional explicit unified diff")
    base_snapshot_id: Optional[str] = None
    head_snapshot_id: Optional[str] = None


class ReviewCommentResponse(BaseModel):
    """Comment item in a review draft."""
    id: str
    run_id: str
    pull_request_id: str
    file_path: str
    side: str = "RIGHT"
    line: int
    finding_id: Optional[str] = None
    body: str
    severity: FindingSeverity = FindingSeverity.MEDIUM
    status: ReviewCommentStatus = ReviewCommentStatus.DRAFT
    github_comment_id: Optional[int] = None
    evidence: List[FindingEvidence] = Field(default_factory=list)
    version: int = 1
    created_at: datetime
    updated_at: datetime


class ReviewRunResponse(BaseModel):
    """Response for GET /pull-requests/{id}/reviews/{run_id} and review creation."""
    run_id: str
    pull_request_id: str
    repository_id: str
    base_sha: str
    head_sha: str
    review_profile: str
    status: str
    summary: str
    impacted_modules: List[str] = Field(default_factory=list)
    tests_to_run: List[str] = Field(default_factory=list)
    comments: List[ReviewCommentResponse] = Field(default_factory=list)
    approval_state: str = "DRAFT"
    stale: bool = False
    created_at: datetime
    completed_at: Optional[datetime] = None


class CommentEditRequest(BaseModel):
    """Request body for PATCH /pull-requests/{id}/reviews/{run_id}/comments/{comment_id} (Endpoint 095)."""
    body: Optional[str] = Field(default=None, min_length=1, max_length=8000, description="Updated comment text")
    status: Optional[Literal["EDITED", "DISCARDED"]] = Field(
        default=None, description="Set to EDITED or DISCARDED"
    )


class PublishReviewRequest(BaseModel):
    """Request body for POST /pull-requests/{id}/reviews/{run_id}/publish (Endpoint 096)."""
    publish_approval_id: Optional[str] = Field(
        default=None, description="Explicit approval ID from approval gate"
    )
    comment_ids: Optional[List[str]] = Field(
        default=None, description="Subset of comment IDs to publish; if omitted, all active non-discarded comments are published"
    )


class PublishReviewResponse(BaseModel):
    """Response returned upon publishing review comments."""
    run_id: str
    pull_request_id: str
    status: str = "PUBLISHED"
    published_count: int
    published_comment_ids: List[str] = Field(default_factory=list)
    github_comment_ids: List[int] = Field(default_factory=list)
    audit_event_id: str
    published_at: str
