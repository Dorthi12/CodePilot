import axios from 'axios';

export interface PatchFile {
  path: string;
  change_type: string;
  additions: number;
  deletions: number;
}

export interface PatchApproval {
  id: string;
  scope: string;
  diff_sha256: string;
  approver_id: string;
  created_at: string;
}

export interface PatchArtifact {
  id: string;
  snapshot_id: string;
  finding_id?: string;
  suggestion_id?: string;
  source_task?: string;
  unified_diff: string;
  diff_sha256: string;
  files: PatchFile[];
  rationale: string;
  status: string;
  validation: Array<{ kind: string; status: string; detail: string }>;
  validation_policy: Record<string, boolean>;
  approvals: PatchApproval[];
  version: number;
  created_at: string;
  rejected_reason?: string;
}

export interface FixCreatePayload {
  snapshot_id: string;
  finding_id?: string;
  suggestion_id?: string;
  task?: string;
  target_files?: string[];
  constraints?: string[];
  validation_policy?: {
    syntax?: boolean;
    lint?: boolean;
    tests?: boolean;
    security?: boolean;
  };
  unified_diff?: string;
}

export interface FixPRPayload {
  publish_approval_id: string;
  branch_name: string;
  title: string;
  body?: string;
}

const apiClient = axios.create({
  baseURL: '/api/v1',
  headers: {
    'Content-Type': 'application/json',
  },
});

export const fixesApi = {
  createFix: async (payload: FixCreatePayload): Promise<PatchArtifact> => {
    const res = await apiClient.post<PatchArtifact>('/fixes', payload);
    return res.data;
  },

  getFix: async (patchId: string): Promise<PatchArtifact> => {
    const res = await apiClient.get<PatchArtifact>(`/fixes/${patchId}`);
    return res.data;
  },

  editFix: async (patchId: string, unifiedDiff: string, rationale?: string): Promise<PatchArtifact> => {
    const res = await apiClient.patch<PatchArtifact>(`/fixes/${patchId}`, {
      unified_diff: unifiedDiff,
      rationale,
    });
    return res.data;
  },

  reviseFix: async (patchId: string, instruction: string): Promise<PatchArtifact> => {
    const res = await apiClient.post<PatchArtifact>(`/fixes/${patchId}/revise`, {
      instruction,
    });
    return res.data;
  },

  validateFix: async (patchId: string, consentExecuteTests: boolean = false): Promise<PatchArtifact> => {
    const res = await apiClient.post<PatchArtifact>(`/fixes/${patchId}/validate`, {
      consent_execute_tests: consentExecuteTests,
    });
    return res.data;
  },

  approveFix: async (patchId: string, diffSha256: string, scope: 'EXPORT' | 'PUBLISH' = 'EXPORT'): Promise<PatchArtifact> => {
    const res = await apiClient.post<PatchArtifact>(`/fixes/${patchId}/approve`, {
      scope,
      diff_sha256: diffSha256,
    });
    return res.data;
  },

  rejectFix: async (patchId: string, reason: string): Promise<PatchArtifact> => {
    const res = await apiClient.post<PatchArtifact>(`/fixes/${patchId}/reject`, {
      reason,
    });
    return res.data;
  },

  exportFix: async (patchId: string): Promise<Blob> => {
    const res = await apiClient.post(`/fixes/${patchId}/export`, {}, {
      responseType: 'blob',
    });
    return res.data;
  },

  createPullRequest: async (patchId: string, payload: FixPRPayload): Promise<any> => {
    const res = await apiClient.post(`/fixes/${patchId}/pull-request`, payload);
    return res.data;
  },
};
