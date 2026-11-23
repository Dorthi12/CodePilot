-- CodePilot PostgreSQL Schema: Mastermind Feature M5 (Unit Test Generation)
-- Version: 1.0 (Audited against Master Architecture Spec v2.1 §6.6, §10 and API Spec §4.6)

-- 1. Test Artifacts Table
CREATE TABLE IF NOT EXISTS test_artifacts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL,
    snapshot_id VARCHAR(255) NOT NULL,
    analysis_run_id UUID NOT NULL REFERENCES analysis_runs(id) ON DELETE CASCADE,
    file_path VARCHAR(1024) NOT NULL,
    content TEXT NOT NULL,
    framework VARCHAR(50) NOT NULL DEFAULT 'pytest',
    validation_status VARCHAR(50) NOT NULL DEFAULT 'PENDING', -- PENDING, VALIDATED, FAILED
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT chk_test_artifact_status CHECK (validation_status IN ('PENDING', 'VALIDATED', 'FAILED'))
);

CREATE INDEX IF NOT EXISTS idx_test_artifacts_snapshot ON test_artifacts(snapshot_id);
CREATE INDEX IF NOT EXISTS idx_test_artifacts_run ON test_artifacts(analysis_run_id);
CREATE INDEX IF NOT EXISTS idx_test_artifacts_file_path ON test_artifacts(file_path);

-- 2. Test Runs Table (Isolated Sandbox Executions)
CREATE TABLE IF NOT EXISTS test_runs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL,
    run_id UUID NOT NULL REFERENCES analysis_runs(id) ON DELETE CASCADE,
    sandbox_image VARCHAR(255) NOT NULL,
    status VARCHAR(50) NOT NULL DEFAULT 'PENDING', -- PENDING, RUNNING, PASSED, FAILED, ERROR, HIGH_RISK
    profile TEXT CHECK (profile IN ('S1', 'S2', 'S3')),
    network_mode TEXT NOT NULL DEFAULT 'none' CHECK (network_mode IN ('none', 'proxy_only')),
    risk_level VARCHAR(50) NOT NULL DEFAULT 'STANDARD', -- STANDARD, HIGH_RISK
    limits JSONB NOT NULL DEFAULT '{"timeout_seconds": 60, "max_memory_mb": 2048, "network": "NONE"}'::jsonb,
    command TEXT NOT NULL DEFAULT 'pytest -v',
    exit_code INT,
    stdout_redacted TEXT,
    stderr_redacted TEXT,
    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    ended_at TIMESTAMPTZ,
    duration_ms NUMERIC(10, 2) DEFAULT 0.0,
    CONSTRAINT chk_test_run_status CHECK (status IN ('PENDING', 'RUNNING', 'PASSED', 'FAILED', 'ERROR', 'HIGH_RISK'))
);

CREATE INDEX IF NOT EXISTS idx_test_runs_run ON test_runs(run_id);
CREATE INDEX IF NOT EXISTS idx_test_runs_status ON test_runs(status);

-- 3. Test Results Table (Per-Test Outcome)
CREATE TABLE IF NOT EXISTS test_results (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL,
    test_run_id UUID NOT NULL REFERENCES test_runs(id) ON DELETE CASCADE,
    test_name VARCHAR(500) NOT NULL,
    status VARCHAR(50) NOT NULL DEFAULT 'PASSED', -- PASSED, FAILED, SKIPPED, ERROR
    duration_ms NUMERIC(10, 2) DEFAULT 0.0,
    failure_ref TEXT,
    failure_message TEXT,
    failure_trace_redacted TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT chk_test_result_status CHECK (status IN ('PASSED', 'FAILED', 'SKIPPED', 'ERROR'))
);

CREATE INDEX IF NOT EXISTS idx_test_results_run ON test_results(test_run_id);
CREATE INDEX IF NOT EXISTS idx_test_results_status ON test_results(status);

-- 4. Coverage Reports Table
CREATE TABLE IF NOT EXISTS coverage_reports (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL,
    test_run_id UUID NOT NULL REFERENCES test_runs(id) ON DELETE CASCADE,
    tool VARCHAR(100) NOT NULL DEFAULT 'pytest-cov',
    target_file VARCHAR(1024) NOT NULL,
    before JSONB NOT NULL DEFAULT '{}'::jsonb,
    after JSONB NOT NULL DEFAULT '{}'::jsonb,
    delta JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_coverage_reports_run ON coverage_reports(test_run_id);
