import { api } from './api';
import { User, GitHubStatus } from '../types/auth';

export interface APIResponse<T> {
  data: T;
  request_id?: string;
  trace_id?: string;
}

export const authService = {
  async getMe(): Promise<User> {
    const response = await api.get<APIResponse<User>>('/auth/me');
    return response.data.data;
  },

  async logout(): Promise<void> {
    await api.post('/auth/logout');
  },

  async getGitHubStatus(): Promise<GitHubStatus> {
    const response = await api.get<APIResponse<GitHubStatus>>('/integrations/github/status');
    return response.data.data;
  },

  async disconnectGitHub(): Promise<void> {
    await api.delete('/integrations/github');
  },

  initiateGitHubLogin(): void {
    const apiBase = import.meta.env.VITE_API_URL || '/api/v1';
    window.location.href = `${apiBase}/integrations/github/start`;
  },
};
