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
