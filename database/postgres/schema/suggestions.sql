-- CodePilot PostgreSQL Schema: Mastermind Feature M3 (Code Improvement Suggestions)
-- Version: 1.0 (Audited against Master Architecture Spec v2.1 §6.6, §10 and API Spec §4.6)

-- 1. Suggestions Table
CREATE TABLE IF NOT EXISTS suggestions (
    id UUID PRIMARY KEY,
    run_id UUID NOT NULL REFERENCES analysis_runs(id) ON DELETE CASCADE,
    snapshot_id VARCHAR(255) NOT NULL,
    tenant_id UUID NOT NULL DEFAULT '00000000-0000-0000-0000-000000000000'::uuid,
    category VARCHAR(50) NOT NULL, -- PERFORMANCE, MAINTAINABILITY, READABILITY, ARCHITECTURE, CODE_QUALITY
    rule_id VARCHAR(100) NOT NULL,
    fingerprint VARCHAR(64) NOT NULL,
    title VARCHAR(500) NOT NULL,
    problem TEXT NOT NULL,
    recommendation TEXT NOT NULL,
    current_code TEXT,
    proposed_code TEXT,
    benefit TEXT NOT NULL,
    effort VARCHAR(20) NOT NULL DEFAULT 'LOW', -- LOW, MEDIUM, HIGH
    risk VARCHAR(20) NOT NULL DEFAULT 'LOW',   -- LOW, MEDIUM, HIGH
    trade_offs TEXT,
    affected_symbols JSONB DEFAULT '[]'::jsonb,
    affected_files JSONB DEFAULT '[]'::jsonb,
    status VARCHAR(30) NOT NULL DEFAULT 'NEW', -- NEW, ACCEPTED, DISMISSED
    version INT NOT NULL DEFAULT 1,
    feedback TEXT,
    priority_score NUMERIC(5, 2) NOT NULL DEFAULT 0.0,
    confidence NUMERIC(3, 2) NOT NULL DEFAULT 0.85,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ,
    CONSTRAINT chk_suggestion_category CHECK (category IN ('PERFORMANCE', 'MAINTAINABILITY', 'READABILITY', 'ARCHITECTURE', 'CODE_QUALITY')),
    CONSTRAINT chk_suggestion_status CHECK (status IN ('NEW', 'ACCEPTED', 'DISMISSED')),
    CONSTRAINT chk_suggestion_effort CHECK (effort IN ('LOW', 'MEDIUM', 'HIGH')),
    CONSTRAINT chk_suggestion_risk CHECK (risk IN ('LOW', 'MEDIUM', 'HIGH'))
);

CREATE INDEX IF NOT EXISTS idx_suggestions_run ON suggestions(run_id);
CREATE INDEX IF NOT EXISTS idx_suggestions_snapshot ON suggestions(snapshot_id);
CREATE INDEX IF NOT EXISTS idx_suggestions_category ON suggestions(category);
CREATE INDEX IF NOT EXISTS idx_suggestions_status ON suggestions(status);
CREATE INDEX IF NOT EXISTS idx_suggestions_priority ON suggestions(priority_score DESC);
CREATE INDEX IF NOT EXISTS idx_suggestions_fingerprint ON suggestions(snapshot_id, fingerprint);

-- 2. Polymorphic Evidence References Table (Used by A3, M2, M3, M7)
CREATE TABLE IF NOT EXISTS evidence_refs (
    id UUID PRIMARY KEY,
    owner_type VARCHAR(50) NOT NULL, -- FINDING, HYPOTHESIS, SUGGESTION, COMMENT
    owner_id UUID NOT NULL,
    source_ref_id VARCHAR(255),
    file_path VARCHAR(1024) NOT NULL,
    line_start INT NOT NULL,
    line_end INT NOT NULL,
    snippet TEXT NOT NULL,
    snippet_hash VARCHAR(64) NOT NULL,
    role VARCHAR(20) NOT NULL DEFAULT 'SUPPORTS', -- SUPPORTS, CONTRADICTS
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT chk_evidence_owner_type CHECK (owner_type IN ('FINDING', 'HYPOTHESIS', 'SUGGESTION', 'COMMENT')),
    CONSTRAINT chk_evidence_role CHECK (role IN ('SUPPORTS', 'CONTRADICTS'))
);

CREATE INDEX IF NOT EXISTS idx_evidence_refs_owner ON evidence_refs(owner_type, owner_id);
CREATE INDEX IF NOT EXISTS idx_evidence_refs_file ON evidence_refs(file_path);
