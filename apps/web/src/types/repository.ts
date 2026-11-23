export interface Repository {
  id: string;
  owner_user_id: string;
  provider: string;
  provider_repo_id: string;
  owner: string;
  name: string;
  full_name: string;
  canonical_url: string;
  visibility: 'PUBLIC' | 'PRIVATE' | 'INTERNAL';
  default_branch: string;
  tracked_branch: string;
  description: string | null;
  language: string | null;
  stargazers_count: number;
  forks_count: number;
  open_issues_count: number;
  size_kb: number;
  status: string;
  analysis_status: 'NOT_ANALYZED' | 'ANALYZING' | 'READY' | 'FAILED';
  created_at: string;
  updated_at: string;
}

export interface GitHubRepoPickerItem {
  id: number;
  name: string;
  full_name: string;
  owner: string;
  owner_avatar_url: string | null;
  html_url: string;
  description: string | null;
  private: boolean;
  visibility: string;
  language: string | null;
  default_branch: string;
  stargazers_count: number;
  forks_count: number;
  updated_at: string;
  is_imported: boolean;
}

export interface GitHubRepoListResponse {
  repositories: GitHubRepoPickerItem[];
  page: number;
  per_page: number;
  has_more: boolean;
}

export interface RepositoryImportRequest {
  url: string;
  branch?: string;
}

export interface RepositoryImportEvent {
  id: string;
  user_id: string;
  repository_id: string | null;
  provider: string;
  provider_repo_id: string | null;
  repo_name: string;
  source_url: string;
  status: 'SUCCEEDED' | 'FAILED' | 'IN_PROGRESS';
  error_message: string | null;
  created_at: string;
}


export type RetrievalMethod = 'GIT_CLONE' | 'ZIP_DOWNLOAD';

export type JobStage = 
  | 'VALIDATING' 
  | 'CLONING' 
  | 'SCANNING' 
  | 'PARSING' 
  | 'CHUNKING' 
  | 'STORING' 
  | 'COMPLETED' 
  | 'FAILED';

export type JobStatus = 'QUEUED' | 'RUNNING' | 'SUCCEEDED' | 'FAILED' | 'CANCELLED';

export interface RepositoryCloneRequest {
  branch?: string;
  retrieval_method?: RetrievalMethod;
}

export interface IngestionJob {
  id: string;
  repository_id: string;
  user_id: string;
  job_type: string;
  status: JobStatus;
  stage: JobStage;
  retrieval_method: RetrievalMethod;
  progress: number | null;
  progress_message: string | null;
  branch: string;
  commit_sha: string | null;
  bytes_downloaded: number;
  total_bytes: number | null;
  files_discovered: number;
  files_processed: number;
  files_skipped: number;
  files_failed: number;
  error_code: string | null;
  error_message: string | null;
  retryable: boolean;
  cancel_requested: boolean;
  workspace_path: string | null;
  started_at: string | null;
  ended_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface SnapshotResponse {
  id: string;
  repository_id: string;
  commit_sha: string;
  branch: string;
  status: string;
  total_files: number;
  total_lines: number;
  metadata_json: {
    languages?: Record<string, number>;
    parsed_at?: string;
    total_symbols?: number;
    total_chunks?: number;
    [key: string]: any;
  };
  created_at: string;
}

export interface FileTreeItem {
  name: string;
  path: string;
  type: 'file' | 'directory';
  language: string | null;
  size_bytes: number;
  line_count: number;
  summary: string | null;
  symbol_count: number;
}

export interface FileTreeResponse {
  current_path: string;
  entries: FileTreeItem[];
  snapshot: SnapshotResponse | null;
}

export interface SymbolResponse {
  id: string;
  file_id: string;
  name: string;
  qualified_name: string;
  kind: 'FUNCTION' | 'CLASS' | 'METHOD' | 'INTERFACE' | 'VARIABLE' | string;
  scope: string | null;
  start_line: number;
  end_line: number;
  start_column: number;
  end_column: number;
  signature: string | null;
  docstring: string | null;
}

export interface ImportResponse {
  id: string;
  source_module: string;
  imported_symbol: string | null;
  alias: string | null;
  line_number: number;
}

export interface CodeChunkResponse {
  id: string;
  chunk_type: string;
  start_line: number;
  end_line: number;
  token_count: number;
  content: string;
  content_hash: string;
}

export interface FileDetailResponse {
  id: string;
  snapshot_id: string;
  path: string;
  filename: string;
  extension: string | null;
  language: string | null;
  content_hash: string;
  size_bytes: number;
  line_count: number;
  summary: string | null;
  content: string | null;
  symbols: SymbolResponse[];
  imports: ImportResponse[];
  chunks: CodeChunkResponse[];
}

export interface FileSummaryItem {
  id: string;
  snapshot_id: string;
  path: string;
  filename: string;
  extension: string | null;
  language: string | null;
  size_bytes: number;
  line_count: number;
  summary: string | null;
  function_count: number;
  class_count: number;
  symbol_count: number;
}

export interface RepositoryOverviewResponse {
  repository_id: string;
  total_files: number;
  total_lines: number;
  total_symbols: number;
  total_chunks: number;
  languages: Record<string, number>;
  latest_snapshot: SnapshotResponse | null;
  commit_sha: string | null;
  branch: string | null;
  last_analyzed_at: string | null;
}

export interface FileSummaryResponse {
  file_id: string;
  path: string;
  filename: string;
  language?: string | null;
  summary: string;
  cached: boolean;
  content_hash: string;
}
