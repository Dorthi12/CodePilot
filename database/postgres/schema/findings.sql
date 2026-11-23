-- CodePilot PostgreSQL Schema: Feature A3 (Bug and Code Smell Detection) & Shared Findings
-- Version: 1.0 (Audited against Master Architecture Spec v2.1 §6.5, §6.6 and API Spec §4.6)

-- 1. Analysis Runs Table (Unified run model across quality, security, and agent analysis)
CREATE TABLE IF NOT EXISTS analysis_runs (
    id UUID PRIMARY KEY,
    snapshot_id VARCHAR(255) NOT NULL,
    run_type VARCHAR(50) NOT NULL DEFAULT 'QUALITY', -- QUALITY, SECURITY, AGENT_ANALYSIS, etc.
    status VARCHAR(50) NOT NULL DEFAULT 'CREATED',   -- CREATED, RUNNING, COMPLETED, PARTIAL, FAILED, CANCELLED
    job_id UUID,
    parent_run_id UUID REFERENCES analysis_runs(id) ON DELETE SET NULL,
    config JSONB DEFAULT '{}'::jsonb,
    model_and_tool_versions JSONB DEFAULT '{}'::jsonb,
    cost_estimate NUMERIC(10, 4) DEFAULT 0.0,
    created_by VARCHAR(255) DEFAULT 'system',
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_analysis_runs_snapshot ON analysis_runs(snapshot_id);
CREATE INDEX IF NOT EXISTS idx_analysis_runs_type_status ON analysis_runs(run_type, status);

-- 2. Rule Metadata Table
CREATE TABLE IF NOT EXISTS rule_metadata (
    rule_id VARCHAR(100) PRIMARY KEY,
    tool VARCHAR(100) NOT NULL,
    pack VARCHAR(100) NOT NULL DEFAULT 'default',
    category VARCHAR(50) NOT NULL,
    default_severity VARCHAR(20) NOT NULL,
    cwe VARCHAR(50),
    owasp VARCHAR(50),
    title VARCHAR(255) NOT NULL,
    description TEXT,
    remediation TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_rule_metadata_tool_pack ON rule_metadata(tool, pack);
CREATE INDEX IF NOT EXISTS idx_rule_metadata_category ON rule_metadata(category);

-- 3. Findings Table (Canonical single resource for all quality and security findings)
CREATE TABLE IF NOT EXISTS findings (
    id UUID PRIMARY KEY,
    snapshot_id VARCHAR(255) NOT NULL,
    analysis_run_id UUID NOT NULL REFERENCES analysis_runs(id) ON DELETE CASCADE,
    fingerprint VARCHAR(64) NOT NULL,
    origin VARCHAR(30) NOT NULL, -- STATIC_TOOL, GRAPH_RULE, AI_HYPOTHESIS, CONFIRMED
    category VARCHAR(50) NOT NULL, -- CODE_QUALITY, BUG, SECURITY, PERFORMANCE, ARCHITECTURE
    rule_id VARCHAR(100) NOT NULL,
    tool VARCHAR(100) NOT NULL,
    tool_version VARCHAR(50) NOT NULL DEFAULT '1.0.0',
    severity VARCHAR(20) NOT NULL, -- CRITICAL, HIGH, MEDIUM, LOW, INFO
    confidence NUMERIC(3, 2) NOT NULL DEFAULT 0.80,
    cwe VARCHAR(50),
    owasp VARCHAR(50),
    title VARCHAR(500) NOT NULL,
    description TEXT,
    remediation TEXT,
    file_path VARCHAR(1024) NOT NULL,
    line_start INT NOT NULL,
    line_end INT NOT NULL,
    symbol_id VARCHAR(255),
    evidence JSONB DEFAULT '[]'::jsonb,
    status VARCHAR(30) NOT NULL DEFAULT 'OPEN', -- OPEN, ACKNOWLEDGED, FALSE_POSITIVE, ACCEPTED_RISK, FIXED
    version INT NOT NULL DEFAULT 1,
    status_reason TEXT,
    status_updated_by VARCHAR(255),
    status_updated_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_findings_snapshot_fingerprint ON findings(snapshot_id, fingerprint);
CREATE INDEX IF NOT EXISTS idx_findings_snapshot_category ON findings(snapshot_id, category);
CREATE INDEX IF NOT EXISTS idx_findings_status ON findings(status);
CREATE INDEX IF NOT EXISTS idx_findings_origin ON findings(origin);

-- 4. Suppressions Table (Repository-scoped: survives snapshot retirement)
CREATE TABLE IF NOT EXISTS suppressions (
    id UUID PRIMARY KEY,
    repository_id VARCHAR(255) NOT NULL,
    fingerprint VARCHAR(64),
    rule_id VARCHAR(100),
    path_glob VARCHAR(500),
    reason TEXT NOT NULL,
    created_by VARCHAR(255) NOT NULL,
    expires_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT chk_suppression_target CHECK (fingerprint IS NOT NULL OR (rule_id IS NOT NULL AND path_glob IS NOT NULL))
);

CREATE INDEX IF NOT EXISTS idx_suppressions_repo_fingerprint ON suppressions(repository_id, fingerprint);
CREATE INDEX IF NOT EXISTS idx_suppressions_repo_rule ON suppressions(repository_id, rule_id);

-- 5. Tool Execution Logs Table (Records coverage, status, and redacted stderr)
CREATE TABLE IF NOT EXISTS tool_execution_logs (
    id UUID PRIMARY KEY,
    run_id UUID NOT NULL REFERENCES analysis_runs(id) ON DELETE CASCADE,
    tool VARCHAR(100) NOT NULL,
    tool_version VARCHAR(50) NOT NULL,
    status VARCHAR(50) NOT NULL, -- SUCCESS, PARTIAL, FAILED, TIMEOUT, SKIPPED
    duration_ms NUMERIC(10, 2) NOT NULL DEFAULT 0.0,
    coverage JSONB DEFAULT '{}'::jsonb, -- files_scanned, rules_run, etc.
    stderr_redacted TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_tool_logs_run_id ON tool_execution_logs(run_id);

-- 6. Evidence References Table (Polymorphic linking for citations and supporting evidence)
CREATE TABLE IF NOT EXISTS evidence_refs (
    id UUID PRIMARY KEY,
    owner_type VARCHAR(50) NOT NULL, -- FINDING, HYPOTHESIS, SUGGESTION, COMMENT
    owner_id UUID NOT NULL,
    source_ref_id VARCHAR(255),
    file_path VARCHAR(1024) NOT NULL,
    line_start INT NOT NULL,
    line_end INT NOT NULL,
    snippet TEXT NOT NULL,
    snippet_hash VARCHAR(64),
    role VARCHAR(20) NOT NULL DEFAULT 'SUPPORTS', -- SUPPORTS, CONTRADICTS
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT chk_owner_type CHECK (owner_type IN ('FINDING', 'HYPOTHESIS', 'SUGGESTION', 'COMMENT')),
    CONSTRAINT chk_role CHECK (role IN ('SUPPORTS', 'CONTRADICTS'))
);

CREATE INDEX IF NOT EXISTS idx_evidence_refs_owner ON evidence_refs(owner_type, owner_id);
