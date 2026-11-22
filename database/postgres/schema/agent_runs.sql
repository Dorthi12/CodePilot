-- CodePilot PostgreSQL Schema: Mastermind Feature M2 (AI Bug Investigation) & Agent Runs
-- Version: 1.0 (Audited against Master Architecture Spec v2.1 §6.6, §10 and API Spec §4.6)

-- 1. Investigations Table
CREATE TABLE IF NOT EXISTS investigations (
    run_id UUID PRIMARY KEY REFERENCES analysis_runs(id) ON DELETE CASCADE,
    snapshot_id VARCHAR(255) NOT NULL,
    issue_description TEXT NOT NULL,
    stack_trace_redacted TEXT,
    parsed_frames JSONB DEFAULT '[]'::jsonb,
    failing_test VARCHAR(500),
    entrypoint VARCHAR(500),
    reproduction_status VARCHAR(50) NOT NULL DEFAULT 'NOT_REPRODUCED',
    environment_redacted JSONB DEFAULT '{}'::jsonb,
    problem_summary TEXT,
    next_steps JSONB DEFAULT '[]'::jsonb,
    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_investigations_snapshot ON investigations(snapshot_id);
CREATE INDEX IF NOT EXISTS idx_investigations_repro_status ON investigations(reproduction_status);

-- 2. Hypotheses Table
CREATE TABLE IF NOT EXISTS hypotheses (
    id UUID PRIMARY KEY,
    run_id UUID NOT NULL REFERENCES analysis_runs(id) ON DELETE CASCADE,
    rank INT NOT NULL,
    summary TEXT NOT NULL,
    confidence NUMERIC(3, 2) NOT NULL DEFAULT 0.80,
    status VARCHAR(50) NOT NULL DEFAULT 'UNCONFIRMED', -- UNCONFIRMED, SUPPORTED, REPRODUCED, REFUTED
    file_path VARCHAR(1024),
    function VARCHAR(255),
    line_start INT,
    line_end INT,
    rationale TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT chk_hypothesis_status CHECK (status IN ('UNCONFIRMED', 'SUPPORTED', 'REPRODUCED', 'REFUTED'))
);

CREATE INDEX IF NOT EXISTS idx_hypotheses_run ON hypotheses(run_id);
CREATE INDEX IF NOT EXISTS idx_hypotheses_status ON hypotheses(status);

-- 3. Diagnostic Steps Table
CREATE TABLE IF NOT EXISTS diagnostic_steps (
    id UUID PRIMARY KEY,
    run_id UUID NOT NULL REFERENCES analysis_runs(id) ON DELETE CASCADE,
    hypothesis_id UUID REFERENCES hypotheses(id) ON DELETE SET NULL,
    kind VARCHAR(50) NOT NULL, -- SANDBOX_TEST, STATIC_CHECK, CALL_GRAPH_INSPECTION, LOG_ANALYSIS
    command_ref TEXT NOT NULL,
    status VARCHAR(50) NOT NULL DEFAULT 'PENDING_APPROVAL', -- PENDING_APPROVAL, APPROVED, RUNNING, COMPLETED, FAILED, REJECTED
    result_ref VARCHAR(255),
    approved_by VARCHAR(255),
    limits JSONB DEFAULT '{"timeout_seconds": 60, "max_memory_mb": 2048, "network": "NONE"}'::jsonb,
    test_results JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_diagnostic_steps_run ON diagnostic_steps(run_id);
CREATE INDEX IF NOT EXISTS idx_diagnostic_steps_status ON diagnostic_steps(status);

-- 4. Test Runs & Results Tables (Used by M2 and M5 for isolated sandbox tracking)
CREATE TABLE IF NOT EXISTS test_runs (
    id UUID PRIMARY KEY,
    run_id UUID NOT NULL REFERENCES analysis_runs(id) ON DELETE CASCADE,
    sandbox_image VARCHAR(255) NOT NULL DEFAULT 'codepilot/sandbox:latest',
    status VARCHAR(50) NOT NULL DEFAULT 'PENDING',
    started_at TIMESTAMPTZ,
    ended_at TIMESTAMPTZ,
    limits JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS test_results (
    id UUID PRIMARY KEY,
    test_run_id UUID NOT NULL REFERENCES test_runs(id) ON DELETE CASCADE,
    test_name VARCHAR(500) NOT NULL,
    status VARCHAR(50) NOT NULL, -- PASSED, FAILED, SKIPPED, ERROR
    duration_ms NUMERIC(10, 2) NOT NULL DEFAULT 0.0,
    failure_ref TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_test_results_run ON test_results(test_run_id);
