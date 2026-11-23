import axios from 'axios';
import {
  AnalysisRunResponse,
  CodeQualityRequest,
  CodeQualityResponse,
  Finding,
  FindingPatchRequest,
  FindingsListResponse,
  Suppression,
} from '../../../types/findings';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api/v1';

export const findingsApi = {
  async startQualityRun(data: CodeQualityRequest): Promise<CodeQualityResponse> {
    const res = await axios.post<CodeQualityResponse>(`${API_BASE_URL}/analysis/code-quality`, data);
    return res.data;
  },

  async getAnalysisRun(runId: string): Promise<AnalysisRunResponse> {
    const res = await axios.get<AnalysisRunResponse>(`${API_BASE_URL}/analysis-runs/${runId}`);
    return res.data;
  },

  async listFindings(params: {
    snapshot_id?: string;
    category?: string;
    severity?: string;
    status?: string;
    origin?: string;
    file_path?: string;
    rule_id?: string;
    limit?: number;
    offset?: number;
  }): Promise<FindingsListResponse> {
    const res = await axios.get<FindingsListResponse>(`${API_BASE_URL}/findings`, {
      params: { limit: 500, ...params },
    });
    return res.data;
  },

  async getFinding(id: string): Promise<Finding> {
    const res = await axios.get<Finding>(`${API_BASE_URL}/findings/${id}`);
    return res.data;
  },

  async updateFinding(id: string, patch: FindingPatchRequest): Promise<Finding> {
    const res = await axios.patch<Finding>(`${API_BASE_URL}/findings/${id}`, patch);
    return res.data;
  },

  async createSuppression(suppression: {
    repository_id: string;
    fingerprint?: string;
    rule_id?: string;
    path_glob?: string;
    reason: string;
    expires_at?: string;
  }): Promise<Suppression> {
    const res = await axios.post<Suppression>(`${API_BASE_URL}/suppressions`, suppression);
    return res.data;
  },

  async listSuppressions(repositoryId: string): Promise<Suppression[]> {
    const res = await axios.get<Suppression[]>(`${API_BASE_URL}/suppressions`, {
      params: { repository_id: repositoryId },
    });
    return res.data;
  },
};
