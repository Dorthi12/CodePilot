"""Mastermind Feature 7: Pull Request Review API endpoints (092–096).

Specifications:
- Master Architecture Specification v2.1 §10 (M7), §11.3 (Endpoints 092–096)
- API and Data Specification v1.0 §3.3 (092–096), §3.4.15
- Security and Testing Specification v1.0 §7.3.10, §7.9, §8.9 (AI-16)
"""

from typing import List, Optional
from fastapi import APIRouter, HTTPException, Query, Response, status

from backend.app.modules.pull_requests.review_manager import PullRequestReviewManager
from backend.app.schemas.pull_requests import (
    CommentEditRequest,
    PublishReviewRequest,
    PublishReviewResponse,
    PullRequestItem,
    PullRequestListResponse,
    ReviewCommentResponse,
    ReviewRunCreateRequest,
    ReviewRunResponse,
)

router = APIRouter(tags=["Pull Request Reviews (M7)"])
review_manager = PullRequestReviewManager.get_instance()


@router.get(
    "/repositories/{repository_id}/pull-requests",
    response_model=PullRequestListResponse,
    summary="092: List/sync pull requests for repository",
)
def list_pull_requests(
    repository_id: str,
    state: Optional[str] = Query(None, description="Filter by state: OPEN, CLOSED, MERGED"),
):
    """Retrieve list of pull requests for a given repository (Role: VIEWER)."""
    prs = review_manager.list_pull_requests(repository_id=repository_id, state=state)
    items = [
        PullRequestItem(
            id=pr.id,
            repository_id=pr.repository_id,
            number=pr.number,
            title=pr.title,
            author_login=pr.author_login,
            base_ref=pr.base_ref,
            head_ref=pr.head_ref,
            head_repo_full_name=pr.head_repo_full_name,
            base_sha=pr.base_sha,
            head_sha=pr.head_sha,
            base_snapshot_id=pr.base_snapshot_id,
            head_snapshot_id=pr.head_snapshot_id,
            state=pr.state,
            is_fork=pr.is_fork,
            draft=pr.draft,
            last_synced_at=pr.last_synced_at,
            latest_review_run_id=pr.latest_review_run_id,
        )
        for pr in prs
    ]
    return PullRequestListResponse(
        repository_id=repository_id,
        pull_requests=items,
        total=len(items),
    )


@router.post(
    "/pull-requests/{pull_request_id}/review-runs",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=ReviewRunResponse,
    summary="093: Start a PR review run pinned to base/head SHAs",
)
def create_review_run(
    pull_request_id: str,
    request: ReviewRunCreateRequest,
):
    """Start an AI PR review run pinned to base_sha and head_sha (Role: ADMIN).

    Returns 409 PR_HEAD_CHANGED if head SHA has changed (force-push).
    """
    try:
        run_dict = review_manager.start_review_run(
            pull_request_id=pull_request_id,
            base_sha=request.base_sha,
            head_sha=request.head_sha,
            review_profile=request.review_profile,
            unified_diff=request.unified_diff,
            base_snapshot_id=request.base_snapshot_id,
            head_snapshot_id=request.head_snapshot_id,
        )
        return run_dict
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except ValueError as e:
        detail = str(e)
        if "PR_HEAD_CHANGED" in detail:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="PR_HEAD_CHANGED: The pull request head SHA has changed. Please refresh and review latest commits.",
            ) from e
        raise HTTPException(status_code=422, detail=detail) from e


@router.get(
    "/pull-requests/{pull_request_id}/reviews/{run_id}",
    response_model=ReviewRunResponse,
    summary="094: Draft review: summary, comments, impact",
)
def get_review_draft(
    pull_request_id: str,
    run_id: str,
):
    """Retrieve draft review report: executive summary, inline comments, blast radius, tests to run (Role: VIEWER)."""
    try:
        return review_manager.get_review_draft(pull_request_id=pull_request_id, run_id=run_id)
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


@router.patch(
    "/pull-requests/{pull_request_id}/reviews/{run_id}/comments/{comment_id}",
    response_model=ReviewCommentResponse,
    summary="095: Edit or discard a draft comment before publish",
)
def edit_or_discard_comment(
    pull_request_id: str,
    run_id: str,
    comment_id: str,
    request: CommentEditRequest,
):
    """Edit draft comment text or mark comment DISCARDED before publishing (Role: ADMIN)."""
    try:
        comment = review_manager.edit_or_discard_comment(
            pull_request_id=pull_request_id,
            run_id=run_id,
            comment_id=comment_id,
            body=request.body,
            status=request.status,
        )
        return comment
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e)) from e


@router.post(
    "/pull-requests/{pull_request_id}/reviews/{run_id}/publish",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=PublishReviewResponse,
    summary="096: Publish approved comments to GitHub (Dangerous Operation Gate)",
)
def publish_review(
    pull_request_id: str,
    run_id: str,
    request: PublishReviewRequest = PublishReviewRequest(),
):
    """Publish approved review comments to GitHub under the Dangerous Operation Gate (Role: OWNER).

    Comments marked DISCARDED are omitted. Sets github_comment_id and writes immutable audit record.
    """
    try:
        res = review_manager.publish_review(
            pull_request_id=pull_request_id,
            run_id=run_id,
            publish_approval_id=request.publish_approval_id,
            comment_ids=request.comment_ids,
            actor_role="OWNER",
        )
        return res
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e)) from e
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e)) from e
