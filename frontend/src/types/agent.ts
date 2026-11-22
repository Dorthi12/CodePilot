export type AgentRole =
  | 'ORCHESTRATOR'
  | 'ARCHITECTURE'
  | 'SECURITY'
  | 'CODE_QUALITY'
  | 'PERFORMANCE'
  | 'TESTING'
  | 'REVIEW';

export type RunStatus =
  | 'CREATED'
  | 'PLANNING'
  | 'WAITING_APPROVAL'
  | 'RUNNING'
  | 'VERIFYING'
  | 'COMPLETED'
  | 'PARTIAL'
  | 'FAILED'
  | 'CANCELLED';

export type TaskStatus = 'PENDING' | 'RUNNING' | 'COMPLETED' | 'FAILED' | 'CANCELLED';

export type FindingSeverity = 'CRITICAL' | 'HIGH' | 'MEDIUM' | 'LOW' | 'INFO';

export interface FindingEvidence {
  source_ref_id?: string;
  file_path: string;
  line_start: number;
  line_end: number;
  snippet: string;
  snippet_hash?: string;
  role: string;
}

export interface Finding {
  id: string;
  snapshot_id: string;
  analysis_run_id: string;
  fingerprint: string;
  origin: string;
  category: string;
  rule_id: string;
  tool: string;
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
  status: string;
  agent_role?: string;
}

export interface ToolCall {
  id: string;
  tool: string;
  permission_level: string;
  input: Record<string, any>;
  output?: Record<string, any>;
  status: string;
  policy_decision: string;
  duration_ms: number;
}

export interface AgentTask {
  id: string;
  run_id: string;
  agent_role: AgentRole;
  status: TaskStatus;
  tokens: number;
  findings: Finding[];
  tool_calls: ToolCall[];
  error_message?: string;
  started_at?: string;
  ended_at?: string;
}

export interface AnalysisPlanStep {
  step_id: string;
  agent_role: AgentRole;
  title: string;
  description: string;
  permission_level: string;
  requires_approval: boolean;
  estimated_tokens: number;
}

export interface AnalysisPlan {
  plan_id: string;
  title: string;
  steps: AnalysisPlanStep[];
  requires_human_approval: boolean;
  approval_reason?: string;
  estimated_total_tokens: number;
  estimated_cost_usd: number;
  approved_by?: string;
  approved_at?: string;
}

export interface ConsensusFinding {
  fingerprint: string;
  category: string;
  title: string;
  severity: FindingSeverity;
  file_path: string;
  line_start: number;
  line_end: number;
  supporting_agents: AgentRole[];
  consensus_confidence: number;
  synthesized_remediation: string;
}

export interface DisagreementItem {
  topic: string;
  file_path: string;
  affected_symbol?: string;
  agents_involved: AgentRole[];
  positions: Record<string, string>;
  conflicting_aspect: string;
  trade_off_analysis: string;
}

export interface MultiAgentReport {
  run_id: string;
  snapshot_id: string;
  total_findings: number;
  findings_by_severity: Record<string, number>;
  findings_by_category: Record<string, number>;
  consensus_findings: ConsensusFinding[];
  disagreements: DisagreementItem[];
  all_findings: Finding[];
  verification_summary: {
    total_checks: number;
    passed_checks: number;
    validity_percentage: number;
  };
  agent_summaries: Record<string, string>;
  execution_metrics: {
    total_tasks: number;
    total_tokens: number;
    total_tool_calls: number;
  };
  created_at: string;
}

export interface AgentRunResponse {
  run_id: string;
  snapshot_id: string;
  status: RunStatus;
  plan?: AnalysisPlan;
  tasks: AgentTask[];
  total_findings: number;
  created_at: string;
  started_at?: string;
  completed_at?: string;
  error_message?: string;
}

export interface AgentRunCreateRequest {
  snapshot_id: string;
  repository_id?: string;
  scope?: string;
  target_paths?: string[];
  agents: AgentRole[];
  require_plan_approval: boolean;
  token_budget?: number;
}
