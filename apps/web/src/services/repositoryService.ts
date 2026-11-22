import { api } from './api';
import { APIResponse } from './authService';
import {
  Repository,
  GitHubRepoListResponse,
  RepositoryImportRequest,
  RepositoryImportEvent,
  RepositoryCloneRequest,
  IngestionJob,
  RepositoryOverviewResponse,
  FileTreeResponse,
  FileDetailResponse,
  FileSummaryItem,
  SymbolResponse,
  FileSummaryResponse
} from '../types/repository';

export const repositoryService = {
  async listRepositories(search?: string, visibility?: string): Promise<Repository[]> {
    const params: Record<string, string> = {};
    if (search) params.search = search;
    if (visibility) params.visibility = visibility;

    const response = await api.get<APIResponse<Repository[]>>('/repositories', { params });
    return response.data.data;
  },

  async importRepository(payload: RepositoryImportRequest): Promise<Repository> {
    const response = await api.post<APIResponse<Repository>>('/repositories/import', payload);
    return response.data.data;
  },

  async getRepository(id: string): Promise<Repository> {
    const response = await api.get<APIResponse<Repository>>(`/repositories/${id}`);
    return response.data.data;
  },

  async listImports(limit = 20): Promise<RepositoryImportEvent[]> {
    const response = await api.get<APIResponse<RepositoryImportEvent[]>>('/repositories/imports', {
      params: { limit }
    });
    return response.data.data;
  },

  async listUserGitHubRepositories(
    page = 1,
    perPage = 30,
    search?: string
  ): Promise<GitHubRepoListResponse> {
    const params: Record<string, string | number> = {
      page,
      per_page: perPage
    };
    if (search) params.search = search;

    const response = await api.get<APIResponse<GitHubRepoListResponse>>(
      '/integrations/github/repositories',
      { params }
    );
    return response.data.data;
  },

  async triggerAnalysis(id: string): Promise<Repository> {
    const response = await api.post<APIResponse<Repository>>(`/repositories/${id}/analyze`);
    return response.data.data;
  },

  async cloneRepository(id: string, payload: RepositoryCloneRequest): Promise<IngestionJob> {
    const response = await api.post<APIResponse<IngestionJob>>(`/repositories/${id}/clone`, payload);
    return response.data.data;
  },

  async getCloneStatus(id: string): Promise<IngestionJob | null> {
    const response = await api.get<APIResponse<IngestionJob | null>>(`/repositories/${id}/clone/status`);
    return response.data.data;
  },

  async getJob(jobId: string): Promise<IngestionJob> {
    const response = await api.get<APIResponse<IngestionJob>>(`/jobs/${jobId}`);
    return response.data.data;
  },

  async cancelJob(jobId: string): Promise<IngestionJob> {
    const response = await api.post<APIResponse<IngestionJob>>(`/jobs/${jobId}/cancel`);
    return response.data.data;
  },

  async retryJob(jobId: string): Promise<IngestionJob> {
    const response = await api.post<APIResponse<IngestionJob>>(`/jobs/${jobId}/retry`);
    return response.data.data;
  },

  async getOverview(id: string): Promise<RepositoryOverviewResponse> {
    const response = await api.get<APIResponse<RepositoryOverviewResponse>>(`/repositories/${id}/overview`);
    return response.data.data;
  },

  async getFileTree(id: string, path = '', snapshotId?: string): Promise<FileTreeResponse> {
    const params: Record<string, string> = {};
    if (path) params.path = path;
    if (snapshotId) params.snapshot_id = snapshotId;

    const response = await api.get<APIResponse<FileTreeResponse>>(`/repositories/${id}/tree`, { params });
    return response.data.data;
  },

  async getFileDetail(id: string, path: string, snapshotId?: string): Promise<FileDetailResponse> {
    const params: Record<string, string> = { path };
    if (snapshotId) params.snapshot_id = snapshotId;

    const response = await api.get<APIResponse<FileDetailResponse>>(`/repositories/${id}/file`, { params });
    return response.data.data;
  },

  async getFileDetailById(id: string, fileId: string): Promise<FileDetailResponse> {
    const response = await api.get<APIResponse<FileDetailResponse>>(`/repositories/${id}/files/${fileId}`);
    return response.data.data;
  },

  async listRepositoryFiles(
    id: string,
    search?: string,
    language?: string,
    snapshotId?: string
  ): Promise<FileSummaryItem[]> {
    const params: Record<string, string> = {};
    if (search) params.search = search;
    if (language) params.language = language;
    if (snapshotId) params.snapshot_id = snapshotId;

    const response = await api.get<APIResponse<FileSummaryItem[]>>(`/repositories/${id}/files`, { params });
    return response.data.data;
  },

  async listSymbols(
    id: string,
    query?: string,
    kind?: string,
    limit = 50
  ): Promise<SymbolResponse[]> {
    const params: Record<string, string | number> = { limit };
    if (query) params.q = query;
    if (kind) params.kind = kind;

    const response = await api.get<APIResponse<SymbolResponse[]>>(`/repositories/${id}/symbols`, { params });
    return response.data.data;
  },

  async generateFileSummary(
    id: string,
    fileId: string,
    options?: { force?: boolean }
  ): Promise<FileSummaryResponse> {
    const params: Record<string, boolean> = {};
    if (options?.force) params.force = true;

    const response = await api.post<APIResponse<FileSummaryResponse>>(
      `/repositories/${id}/files/${fileId}/summary`,
      null,
      { params }
    );
    return response.data.data;
  },

  async generateFileSummaryByPath(
    id: string,
    filePath: string,
    options?: { force?: boolean }
  ): Promise<FileSummaryResponse> {
    const response = await api.post<APIResponse<FileSummaryResponse>>(
      `/repositories/${id}/files/summary`,
      { file_path: filePath, force: options?.force ?? false }
    );
    return response.data.data;
  }
};
