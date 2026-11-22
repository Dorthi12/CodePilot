# CodePilot Agent & Debugging API

## AI Bug Investigation Endpoints (M2)

Prefix: `/api/v1`

### 1. `POST /debug/investigations` (070)
- **Role:** ADMIN
- **Mode:** Asynchronous / Synchronous (Class: HEAVY)
- **Description:** Start an AI bug investigation from an issue description, raw stack trace, or failing test.

#### Request Body
```json
{
  "snapshot_id": "uuid-or-slug",
  "issue_description": "Token refresh fails unexpectedly for expired tokens",
  "stack_trace": "Traceback (most recent call last):\n  File \"app/api/routes.py\", line 18...",
  "failing_test": "tests/test_auth.py::test_refresh",
  "entrypoint": "POST /refresh",
  "environment": {
    "python": "3.12"
  }
}
```

#### Response (201 Created)
```json
{
  "investigation_id": "uuid",
  "run_id": "uuid",
  "snapshot_id": "uuid",
  "problem_summary": "Bug investigation for reported issue...",
  "root_causes": [
    {
      "id": "uuid",
      "rank": 1,
      "summary": "Unhandled AuthError in 'refresh_access_token' (app/auth/service.py:48)",
      "confidence": 0.88,
      "status": "UNCONFIRMED",
      "file_path": "app/auth/service.py",
      "function": "refresh_access_token",
      "line_start": 48,
      "line_end": 51,
      "rationale": "AuthError raised by validate_token is not caught or translated for the API layer."
    }
  ],
  "call_path": [
    {
      "order": 1,
      "file_path": "app/api/routes.py",
      "line": 18,
      "function": "refresh",
      "snippet": "return refresh_access_token(token)",
      "is_root_cause_candidate": false,
      "is_entrypoint": true
    }
  ],
  "evidence": [
    {
      "id": "uuid",
      "owner_type": "HYPOTHESIS",
      "owner_id": "uuid",
      "file_path": "app/auth/service.py",
      "line_start": 48,
      "line_end": 51,
      "snippet": "claims = validate_token(token)\nreturn claims",
      "snippet_hash": "sha256...",
      "role": "SUPPORTS"
    }
  ],
  "reproduction_status": "NOT_REPRODUCED",
  "diagnostics": [
    {
      "id": "uuid",
      "kind": "SANDBOX_TEST",
      "command_ref": "pytest tests/test_auth.py::test_refresh",
      "status": "PENDING_APPROVAL"
    }
  ],
  "next_steps": [
    "Obtain EXECUTE approval to run sandboxed reproduction test 'pytest tests/test_auth.py::test_refresh'."
  ],
  "stack_trace_redacted": "Traceback...",
  "started_at": "2026-11-22T18:00:00Z",
  "completed_at": "2026-11-22T18:00:01Z"
}
```

---

### 2. `GET /debug/investigations/{id}` (071)
- **Role:** VIEWER
- **Mode:** Synchronous (Class: READ)
- **Description:** Retrieve the full investigation report by run/investigation ID.

---

### 3. `POST /debug/investigations/{id}/diagnostics` (072)
- **Role:** ADMIN
- **Mode:** Asynchronous (Class: HEAVY)
- **Description:** Request an approved diagnostic (e.g. running an approved test in the disposable sandbox).
- **Security Gate:** Requires explicit `consent: {"execute": true}` opt-in approval. Without consent, returns `403 Forbidden`.

#### Request Body
```json
{
  "diagnostic_id": "uuid",
  "consent": {
    "execute": true,
    "approver_id": "user_admin"
  }
}
```

#### Response (200 OK)
```json
{
  "diagnostic_id": "uuid",
  "run_id": "uuid",
  "status": "COMPLETED",
  "reproduction_status": "REPRODUCED",
  "test_results": {
    "test_run_id": "uuid",
    "command": "pytest tests/test_auth.py::test_refresh",
    "exit_code": 1,
    "reproduced": true,
    "duration_ms": 350.0
  },
  "message": "Diagnostic executed successfully in sandbox"
}
```
