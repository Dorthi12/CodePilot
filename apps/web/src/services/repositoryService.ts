import { api } from './api';
import { APIResponse } from './authService';
import {
  Repository,
  GitHubRepoListResponse,
  RepositoryImportRequest,
  RepositoryImportEvent
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

  async searchRepository(
    id: string,
    query: string,
    topK = 20
  ): Promise<Record<string, unknown>> {
    const response = await api.post<Record<string, unknown>>(
      `/repositories/${id}/ai/search`,
      { query, top_k: topK }
    );
    return response.data;
  },

  async explainRepositoryCode(
    id: string,
    payload: Record<string, unknown>
  ): Promise<Record<string, unknown>> {
    const response = await api.post<Record<string, unknown>>(
      `/repositories/${id}/ai/explain`,
      payload
    );
    return response.data;
  }
};
