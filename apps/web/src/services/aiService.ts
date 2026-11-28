import axios from 'axios';
import { api } from './api';
import { APIResponse } from './authService';
import {
  CodeExplainRequest,
  CodeExplainResponse,
  CodeSearchRequest,
  CodeSearchResponse,
  RepoIndexRequest,
  RepoIndexResponse,
} from '../types/ai';

interface ValidationErrorItem {
  msg?: string;
  loc?: Array<string | number>;
}

interface BackendErrorShape {
  error?: {
    code?: string;
    message?: string;
    details?: {
      errors?: ValidationErrorItem[];
    };
  };
  detail?: string | { code?: string; message?: string };
}

export function extractAIErrorMessage(err: unknown, fallback = 'Request failed. Please try again.'): string {
  if (!axios.isAxiosError(err)) {
    return err instanceof Error ? err.message : fallback;
  }

  const status = err.response?.status;
  const data = err.response?.data as BackendErrorShape | undefined;

  if (status === 401) {
    return 'Your session has expired or you are not authenticated. Please sign in again.';
  }

  if (data?.error?.details?.errors && Array.isArray(data.error.details.errors) && data.error.details.errors.length > 0) {
    const first = data.error.details.errors[0];
    if (first?.msg) return first.msg;
  }

  if (data?.error?.message) {
    return data.error.message;
  }

  if (typeof data?.detail === 'string') {
    return data.detail;
  }
  if (data?.detail && typeof data.detail === 'object' && data.detail.message) {
    return data.detail.message;
  }

  if (status === 404) {
    return 'Repository or completed analysis snapshot was not found.';
  }
  if (status === 422) {
    return 'Invalid request parameters. Please check your input.';
  }
  if (status && status >= 500) {
    return 'Server error occurred while processing the AI request. Please try again.';
  }

  return err.message || fallback;
}

export const aiService = {
  async indexRepository(repositoryId: string, payload: RepoIndexRequest = {}): Promise<RepoIndexResponse> {
    const response = await api.post<APIResponse<RepoIndexResponse>>(
      `/repositories/${repositoryId}/index`,
      payload
    );
    return response.data.data;
  },

  async searchCode(repositoryId: string, payload: CodeSearchRequest): Promise<CodeSearchResponse> {
    const response = await api.post<APIResponse<CodeSearchResponse>>(
      `/repositories/${repositoryId}/search`,
      payload
    );
    return response.data.data;
  },

  async explainCode(repositoryId: string, payload: CodeExplainRequest): Promise<CodeExplainResponse> {
    const response = await api.post<APIResponse<CodeExplainResponse>>(
      `/repositories/${repositoryId}/explain`,
      payload
    );
    return response.data.data;
  },
};
