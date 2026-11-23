-- CodePilot PostgreSQL Schema: Mastermind Feature 7 (Pull Request Reviews & Webhooks)
-- Version: 1.0 (Audited against Master Architecture Spec v2.1 §6.5, §6.6, §10 M7 and API Spec §4.5, §4.6)

-- 1. Pull Requests Table
CREATE TABLE IF NOT EXISTS pull_requests (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL,
    repository_id UUID NOT NULL,
    number INTEGER NOT NULL,
    title TEXT NOT NULL,
    author_login TEXT NOT NULL,
    base_ref TEXT NOT NULL,
    head_ref TEXT NOT NULL,
    head_repo_full_name TEXT,
    base_sha CHAR(40) NOT NULL,
    head_sha CHAR(40) NOT NULL,
    base_snapshot_id VARCHAR(255),
    head_snapshot_id VARCHAR(255),
    state TEXT NOT NULL CHECK (state IN ('OPEN', 'CLOSED', 'MERGED')),
    is_fork BOOLEAN NOT NULL DEFAULT FALSE,
    draft BOOLEAN NOT NULL DEFAULT FALSE,
    last_synced_at TIMESTAMPTZ,
    latest_review_run_id UUID,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (repository_id, number)
);

CREATE INDEX IF NOT EXISTS idx_pull_requests_repo_state ON pull_requests(repository_id, state);
CREATE INDEX IF NOT EXISTS idx_pull_requests_head_sha ON pull_requests(head_sha);
CREATE INDEX IF NOT EXISTS idx_pull_requests_tenant ON pull_requests(tenant_id);

-- 2. Webhook Deliveries Table (Deduplication and Auditing per API Spec §3.10)
CREATE TABLE IF NOT EXISTS webhook_deliveries (
    delivery_id VARCHAR(100) PRIMARY KEY,              -- X-GitHub-Delivery GUID
    tenant_id UUID,
    event TEXT NOT NULL,
    repository_id UUID,
    received_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    status TEXT NOT NULL DEFAULT 'RECEIVED' CHECK (status IN ('RECEIVED', 'PROCESSED', 'IGNORED', 'FAILED'))
);

CREATE INDEX IF NOT EXISTS idx_webhook_deliveries_status ON webhook_deliveries(status);
CREATE INDEX IF NOT EXISTS idx_webhook_deliveries_received_at ON webhook_deliveries(received_at);

-- 3. PR Files Table (Changed files in diff)
CREATE TABLE IF NOT EXISTS pr_files (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    pull_request_id UUID NOT NULL REFERENCES pull_requests(id) ON DELETE CASCADE,
    path TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('added', 'modified', 'removed', 'renamed')),
    additions INTEGER NOT NULL DEFAULT 0,
    deletions INTEGER NOT NULL DEFAULT 0,
    hunks_ref JSONB DEFAULT '[]'::jsonb
);

CREATE INDEX IF NOT EXISTS idx_pr_files_pr_id ON pr_files(pull_request_id);
CREATE INDEX IF NOT EXISTS idx_pr_files_path ON pr_files(path);

-- 4. Review Comments Table (Inline comments with lifecycle and valid anchor enforcement)
CREATE TABLE IF NOT EXISTS review_comments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    run_id UUID NOT NULL,
    pull_request_id UUID NOT NULL REFERENCES pull_requests(id) ON DELETE CASCADE,
    file_path TEXT NOT NULL,
    side TEXT NOT NULL DEFAULT 'RIGHT' CHECK (side IN ('LEFT', 'RIGHT')),
    line INTEGER NOT NULL,
    finding_id UUID,
    body TEXT NOT NULL,
    severity TEXT NOT NULL DEFAULT 'MEDIUM' CHECK (severity IN ('CRITICAL', 'HIGH', 'MEDIUM', 'LOW', 'INFO')),
    status TEXT NOT NULL DEFAULT 'DRAFT' CHECK (status IN ('DRAFT', 'EDITED', 'DISCARDED', 'PUBLISHED')),
    github_comment_id BIGINT,
    evidence JSONB DEFAULT '[]'::jsonb,
    version INTEGER NOT NULL DEFAULT 1,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_review_comments_run ON review_comments(run_id);
CREATE INDEX IF NOT EXISTS idx_review_comments_pr_status ON review_comments(pull_request_id, status);
CREATE INDEX IF NOT EXISTS idx_review_comments_file_line ON review_comments(file_path, line);

-- 5. Review Runs Table (PR Review analysis runs pinned to base/head SHAs)
CREATE TABLE IF NOT EXISTS pr_review_runs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    pull_request_id UUID NOT NULL REFERENCES pull_requests(id) ON DELETE CASCADE,
    repository_id UUID NOT NULL,
    base_sha CHAR(40) NOT NULL,
    head_sha CHAR(40) NOT NULL,
    review_profile VARCHAR(50) NOT NULL DEFAULT 'standard',
    status VARCHAR(50) NOT NULL DEFAULT 'COMPLETED',
    summary TEXT,
    impacted_modules JSONB DEFAULT '[]'::jsonb,
    tests_to_run JSONB DEFAULT '[]'::jsonb,
    approval_state VARCHAR(50) NOT NULL DEFAULT 'DRAFT',
    stale BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_pr_review_runs_pr ON pr_review_runs(pull_request_id);
CREATE INDEX IF NOT EXISTS idx_pr_review_runs_shas ON pr_review_runs(base_sha, head_sha);

-- 6. Audit Events Table (Tamper-evident log for high-risk operations: SEC-AUD-02, SEC-AUD-10)
CREATE TABLE IF NOT EXISTS pr_audit_events (
    id BIGSERIAL PRIMARY KEY,
    tenant_id UUID,
    actor_id VARCHAR(255) NOT NULL,
    actor_type VARCHAR(50) NOT NULL CHECK (actor_type IN ('USER', 'AGENT', 'SERVICE', 'WEBHOOK', 'OPERATOR', 'SYSTEM')),
    action TEXT NOT NULL,
    resource_type TEXT NOT NULL,
    resource_id TEXT NOT NULL,
    outcome TEXT NOT NULL CHECK (outcome IN ('SUCCESS', 'DENIED', 'FAILURE')),
    reason_code TEXT,
    request_id TEXT,
    trace_id TEXT,
    approval_id TEXT,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_pr_audit_events_resource ON pr_audit_events(resource_type, resource_id);
CREATE INDEX IF NOT EXISTS idx_pr_audit_events_action ON pr_audit_events(action);
