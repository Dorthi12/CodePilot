# CodePilot Pull Request & Repository API (Mastermind Feature 7)

## Pull Request Review Endpoints (M7)

Prefix: `/api/v1`

### 1. `POST /github/webhooks` (091)
- **Role:** Unauthenticated (HMAC-SHA256 signature verification)
- **Mode:** Synchronous (Class: WEBHOOK)
- **Headers:**
  - `X-GitHub-Event`: Event name (`pull_request`, `push`, etc.)
  - `X-GitHub-Delivery`: Unique GUID deduplication key
  - `X-Hub-Signature-256`: `sha256=` + HMAC hex digest of raw request body
- **Description:** Ingests inbound GitHub events with constant-time verification, dual-secret rotation support, and replay deduplication.

---

### 2. `GET /repositories/{id}/pull-requests` (092)
- **Role:** VIEWER
- **Mode:** Synchronous (Class: GH)
- **Description:** List or sync pull requests for a given repository.
- **Query Parameters:**
  - `state` (optional): Filter by `OPEN`, `CLOSED`, `MERGED`.

---

### 3. `POST /pull-requests/{id}/review-runs` (093)
- **Role:** ADMIN
- **Mode:** Asynchronous / Synchronous (Class: HEAVY)
- **Description:** Start an AI PR review run pinned to base/head SHAs.
- **Request Body:**
```json
{
  "base_sha": "0123456789abcdef0123456789abcdef01234567",
  "head_sha": "89abcdef0123456789abcdef0123456789abcdef",
  "review_profile": "standard",
  "unified_diff": "--- a/app/service.py\n+++ b/app/service.py..."
}
```
- **Error Codes:**
  - `409 Conflict`: `PR_HEAD_CHANGED` if head commit has moved due to a force-push.

---

### 4. `GET /pull-requests/{id}/reviews/{run_id}` (094)
- **Role:** VIEWER
- **Mode:** Synchronous (Class: READ)
- **Description:** Retrieve draft review summary, inline comments, blast radius (impacted modules), and recommended tests.

---

### 5. `PATCH /pull-requests/{id}/reviews/{run_id}/comments/{comment_id}` (095)
- **Role:** ADMIN
- **Mode:** Synchronous (Class: WRITE)
- **Description:** Edit draft comment body or discard a draft comment before publication.
- **Request Body:**
```json
{
  "body": "Revised comment text",
  "status": "EDITED"
}
```

---

### 6. `POST /pull-requests/{id}/reviews/{run_id}/publish` (096)
- **Role:** OWNER (Dangerous Operation Register Gate)
- **Mode:** Asynchronous (Class: HEAVY)
- **Description:** Publish approved comments to GitHub. Discarded comments are skipped. Emits an immutable audit log record.
- **Request Body:**
```json
{
  "publish_approval_id": "uuid-or-token",
  "comment_ids": ["uuid-comment-1", "uuid-comment-2"]
}
```
