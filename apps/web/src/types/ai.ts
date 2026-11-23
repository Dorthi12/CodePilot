export interface SearchResultItem {
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
  signature?: string | null;
}

export interface SearchResponse {
  repo_id: string;
  snapshot_id: string;
  query: string;
  total: number;
  results: SearchResultItem[];
  warnings: string[];
}

export interface CitationItem {
  source_id: string;
  file_path: string;
  start_line: number;
  end_line: number;
  symbol_name?: string | null;
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

export interface ExplanationResponse {
  repo_id: string;
  snapshot_id: string;
  file_path?: string | null;
  language: string;
  selected_code: string;
  question?: string | null;
  explanation_style: string;
  overview: string;
  step_by_step: string[];
  inputs?: string | null;
  outputs?: string | null;
  important_symbols: string[];
  side_effects: string[];
  edge_cases: string[];
  related_symbols: RelatedSymbolContext[];
  citations: CitationItem[];
  limitations: string[];
  raw_explanation: string;
}

export interface TechnologyInfo {
  name: string;
  category: string;
  confidence: string;
}

export interface ModuleInfo {
  name: string;
  path: string;
  file_count: number;
  symbol_count: number;
  description: string;
}

export interface ComponentInfo {
  name: string;
  kind: string;
  file_path: string;
  start_line: number;
  end_line: number;
  signature?: string | null;
}

export interface ProjectSummaryResponse {
  repo_id: string;
  snapshot_id: string;
  project_overview: string;
  project_purpose: string;
  technologies: TechnologyInfo[];
  modules: ModuleInfo[];
  components: ComponentInfo[];
  architecture_overview: string;
  file_count: number;
  symbol_count: number;
  languages: Record<string, number>;
  breakdown_by_kind: Record<string, number>;
}

export interface FileTreeNode {
  name: string;
  path: string;
  type: 'file' | 'directory';
  size?: number | null;
  line_count?: number | null;
  children?: FileTreeNode[] | null;
}

export interface RepositoryFilesResponse {
  repo_id: string;
  snapshot_id: string;
  file_count: number;
  files: Array<{
    path: string;
    size: number;
    line_count: number;
  }>;
  tree: FileTreeNode[];
}

export interface FileContentResponse {
  repo_id: string;
  snapshot_id: string;
  path: string;
  content: string;
  line_count: number;
  symbols: Array<{
    symbol_id: string;
    name: string;
    kind: string;
    start_line: number;
    end_line: number;
    signature?: string | null;
  }>;
}
