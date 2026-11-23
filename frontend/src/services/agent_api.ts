import axios from 'axios';
import {
  AgentRunCreateRequest,
  AgentRunResponse,
  MultiAgentReport,
} from '../types/agent';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api/v1';

export const agentApi = {
  async createRun(data: AgentRunCreateRequest): Promise<AgentRunResponse> {
    const res = await axios.post<AgentRunResponse>(`${API_BASE_URL}/agents/analysis-runs`, data);
    return res.data;
  },

  async getRun(runId: string): Promise<AgentRunResponse> {
    const res = await axios.get<AgentRunResponse>(`${API_BASE_URL}/agents/analysis-runs/${runId}`);
    return res.data;
  },

  async approveRun(runId: string, scope = 'PLAN', comment?: string): Promise<AgentRunResponse> {
    const res = await axios.post<AgentRunResponse>(
      `${API_BASE_URL}/agents/analysis-runs/${runId}/approve`,
      { scope, comment }
    );
    return res.data;
  },

  async cancelRun(runId: string): Promise<AgentRunResponse> {
    const res = await axios.post<AgentRunResponse>(`${API_BASE_URL}/agents/analysis-runs/${runId}/cancel`);
    return res.data;
  },

  async getReport(runId: string): Promise<MultiAgentReport> {
    const res = await axios.get<MultiAgentReport>(`${API_BASE_URL}/agents/analysis-runs/${runId}/report`);
    return res.data;
  },

  subscribeEvents(runId: string, onEvent: (event: any) => void): () => void {
    const eventSource = new EventSource(`${API_BASE_URL}/agents/analysis-runs/${runId}/events`);
    eventSource.onmessage = (e) => {
      try {
        const data = JSON.parse(e.data);
        onEvent(data);
      } catch (err) {
        console.error('Failed to parse SSE event data', err);
      }
    };
    eventSource.onerror = () => {
      eventSource.close();
    };
    return () => eventSource.close();
  },
};
