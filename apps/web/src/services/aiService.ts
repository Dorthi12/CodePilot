import { api } from './api';
import {
  SearchResponse,
  ExplanationResponse,
  ProjectSummaryResponse,
  RepositoryFilesResponse,
  FileContentResponse,
} from '../types/ai';

export interface SearchParams {
  query: string;
  filters?: {
    kinds?: string[];
    languages?: string[];
    path_prefix?: string;
  };
  top_k?: number;
}

export interface ExplainParams {
  code?: string;
  file_path?: string;
  start_line?: number;
  end_line?: number;
  symbol_id?: string;
  question?: string;
  explanation_style?: 'beginner' | 'technical' | 'deep';
}

export const aiService = {
  async searchRepository(repoId: string, params: SearchParams): Promise<SearchResponse> {
    const response = await api.post<SearchResponse>(`/repositories/${repoId}/ai/search`, {
      query: params.query,
      filters: params.filters,
      top_k: params.top_k || 20,
    });
    return response.data;
  },

  async explainCode(repoId: string, params: ExplainParams): Promise<ExplanationResponse> {
    const response = await api.post<ExplanationResponse>(`/repositories/${repoId}/ai/explain`, {
      code: params.code,
      file_path: params.file_path,
      start_line: params.start_line,
      end_line: params.end_line,
      symbol_id: params.symbol_id,
      question: params.question,
      explanation_style: params.explanation_style || 'technical',
    });
    return response.data;
  },

  async getRepositorySummary(repoId: string): Promise<ProjectSummaryResponse> {
    const response = await api.get<ProjectSummaryResponse>(`/repositories/${repoId}/analysis/summary`);
    return response.data;
  },

  async getRepositoryFiles(repoId: string): Promise<RepositoryFilesResponse> {
    const response = await api.get<RepositoryFilesResponse>(`/repositories/${repoId}/ai/files`);
    return response.data;
  },

  async getFileContent(repoId: string, path: string): Promise<FileContentResponse> {
    const response = await api.get<FileContentResponse>(`/repositories/${repoId}/file-content`, {
      params: { path },
    });
    return response.data;
  },
};
