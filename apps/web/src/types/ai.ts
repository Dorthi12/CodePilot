export type ExplanationStyle = 'beginner' | 'technical' | 'deep';

export interface RepoIndexRequest {
  snapshot_id?: string;
  force?: boolean;
}

export interface RepoIndexResponse {
  repo_id: string;
  snapshot_id: string;
  symbol_count: number;
  file_count: number;
  warnings: string[];
  cached: boolean;
  message: string;
}

export interface CodeSearchFilters {
  kinds?: string[];
  languages?: string[];
  path_prefix?: string;
}

export interface CodeSearchRequest {
  query: string;
  snapshot_id?: string;
  filters?: CodeSearchFilters;
  top_k?: number;
}

export interface CodeSearchResultItem {
  source_id: string;
  repo_id: string;
  snapshot_id: string;
  file_path: string;
  language: string;
  kind: string;
  name: string;
  qualified_name: string;
  start_line: number;
  end_line: number;
  snippet: string;
  score: number;
  match_type: string;
  signature: string | null;
}

export interface CodeSearchResponse {
  repo_id: string;
  snapshot_id: string;
  query: string;
  total: number;
  results: CodeSearchResultItem[];
  warnings: string[];
}

export interface CodeExplainRequest {
  snapshot_id?: string;
  code?: string;
  file_path?: string;
  start_line?: number;
  end_line?: number;
  symbol_id?: string;
  question?: string;
  explanation_style: ExplanationStyle;
}

export interface CitationItem {
  source_id: string;
  file_path: string;
  start_line: number;
  end_line: number;
  symbol_name: string | null;
  snippet: string;
}

export interface RelatedSymbolContext {
  name: string;
  kind: string;
  file_path: string;
  start_line: number;
  end_line: number;
  snippet: string;
  relevance_reason: string;
}

export interface CodeExplainResponse {
  repo_id: string;
  snapshot_id: string;
  file_path: string | null;
  language: string;
  selected_code: string;
  question: string | null;
  explanation_style: string;
  overview: string;
  step_by_step: string[];
  inputs: string | null;
  outputs: string | null;
  important_symbols: string[];
  side_effects: string[];
  edge_cases: string[];
  related_symbols: RelatedSymbolContext[];
  citations: CitationItem[];
  limitations: string[];
  raw_explanation: string;
}
