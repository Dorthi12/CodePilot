"""Mastermind Feature 7: GitHub Webhooks endpoint (091).

Specifications:
- Master Architecture Specification v2.1 §10 (M7), §11.3 (Endpoint 091)
- API and Data Specification v1.0 §3.3 (091), §3.10
- Security and Testing Specification v1.0 §7.3.10 (SEC-API-28..31)
"""

from fastapi import APIRouter, Header, HTTPException, Request, Response, status

from backend.app.modules.github.webhook_handler import GitHubWebhookHandler
from backend.app.schemas.pull_requests import WebhookReceiptResponse

router = APIRouter(tags=["GitHub Integration & Webhooks (M7)"])
handler = GitHubWebhookHandler()


@router.post(
    "/github/webhooks",
    status_code=status.HTTP_202_ACCEPTED,
    summary="091: Receive GitHub events (HMAC verified, deduplicated)",
)
async def receive_github_webhook(
    request: Request,
    x_github_event: str = Header(..., alias="X-GitHub-Event"),
    x_github_delivery: str = Header(..., alias="X-GitHub-Delivery"),
    x_hub_signature_256: str = Header(None, alias="X-Hub-Signature-256"),
):
    """Receive and process GitHub webhook deliveries with HMAC-SHA256 verification and replay deduplication."""
    # 1. Read raw body bytes before parsing
    raw_body = await request.body()

    # 2. Invoke webhook handler
    status_code, response_data = handler.handle_webhook(
        delivery_id=x_github_delivery,
        event=x_github_event,
        raw_body=raw_body,
        signature_header=x_hub_signature_256,
    )

    if status_code >= 400:
        error_info = response_data.get("error", {})
        raise HTTPException(
            status_code=status_code,
            detail=error_info.get("message", "Webhook processing failed"),
        )

    return Response(
        content=str(response_data),
        status_code=status_code,
        media_type="application/json",
    )
