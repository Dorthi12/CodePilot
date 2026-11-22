/**
 * TypeScript interfaces for Feature A3 (Bug and Code Smell Detection) and Findings.
 * Audited against Master Architecture Specification v2.1 §9 (A3), §6.5 & API Spec §3.4.10.
 */

export type FindingOrigin = 'STATIC_TOOL' | 'GRAPH_RULE' | 'AI_HYPOTHESIS' | 'CONFIRMED';

export type FindingSeverity = 'CRITICAL' | 'HIGH' | 'MEDIUM' | 'LOW' | 'INFO';

export type FindingStatus = 'OPEN' | 'ACKNOWLEDGED' | 'FALSE_POSITIVE' | 'ACCEPTED_RISK' | 'FIXED';

export interface FindingEvidence {
  id: string;
  source_ref_id?: string;
  file_path: string;
  line_start: number;
  line_end: number;
  snippet: string;
  snippet_hash?: string;
  role: 'SUPPORTS' | 'CONTRADICTS';
}

export interface Finding {
  id: string;
  snapshot_id: string;
  analysis_run_id: string;
  fingerprint: string;
  origin: FindingOrigin;
  category: string;
  rule_id: string;
  tool: string;
  tool_version: string;
  severity: FindingSeverity;
  confidence: number;
  cwe?: string;
  owasp?: string;
  title: string;
  description: string;
  remediation?: string;
  file_path: string;
  line_start: number;
  line_end: number;
  symbol_id?: string;
  evidence: FindingEvidence[];
  status: FindingStatus;
  version: number;
  status_reason?: string;
  status_updated_by?: string;
  status_updated_at?: string;
  created_at: string;
  metadata?: Record<string, any>;
}

export interface ToolCoverage {
  tool: string;
  version: string;
  status: 'SUCCESS' | 'PARTIAL' | 'FAILED' | 'TIMEOUT' | 'SKIPPED';
  duration_ms: number;
  files_scanned: number;
  rules_run: number;
  findings_count: number;
  error?: string;
}

export interface AnalysisRunResponse {
  run_id: string;
  snapshot_id: string;
  run_type: string;
  status: string;
  tool_coverage: ToolCoverage[];
  counts_by_severity: Record<string, number>;
  counts_by_origin: Record<string, number>;
  total_findings: number;
  warnings: string[];
  started_at: string;
  completed_at?: string;
}

export interface CodeQualityRequest {
  snapshot_id: string;
  scope?: {
    paths?: string[];
    changed_files?: string[];
    changed_files_only?: boolean;
  };
  rule_pack?: string;
  severity_threshold?: FindingSeverity;
  repository_id?: string;
}

export interface CodeQualityResponse {
  run_id: string;
  job_id: string;
  status: string;
  snapshot_id: string;
  message: string;
}

export interface FindingsListResponse {
  items: Finding[];
  total: number;
  limit: number;
  offset: number;
  counts_by_severity: Record<string, number>;
  counts_by_origin: Record<string, number>;
}

export interface FindingPatchRequest {
  status: FindingStatus;
  reason?: string;
}

export interface Suppression {
  id: string;
  repository_id: string;
  fingerprint?: string;
  rule_id?: string;
  path_glob?: string;
  reason: string;
  created_by: string;
  expires_at?: string;
  created_at: string;
}
