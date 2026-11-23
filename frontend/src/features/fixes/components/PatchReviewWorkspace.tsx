import { useEffect, useState } from 'react';
import { fixesApi, PatchArtifact } from '../services/fixes_api';

interface PatchReviewWorkspaceProps {
  patchId: string;
}

export const PatchReviewWorkspace: React.FC<PatchReviewWorkspaceProps> = ({ patchId }) => {
  const [patch, setPatch] = useState<PatchArtifact | null>(null);
  const [editedDiff, setEditedDiff] = useState<string>('');
  const [revisionInstruction, setRevisionInstruction] = useState<string>('');
  const [prBranch, setPrBranch] = useState<string>('fix-issue');
  const [prTitle, setPrTitle] = useState<string>('');
  const [prBody, setPrBody] = useState<string>('');
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [actionSuccess, setActionSuccess] = useState<string | null>(null);

  useEffect(() => {
    loadPatch();
  }, [patchId]);

  const loadPatch = async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await fixesApi.getFix(patchId);
      setPatch(data);
      setEditedDiff(data.unified_diff);
      setPrTitle(`Fix: ${data.rationale || 'CodePilot proposal'}`);
    } catch (err: any) {
      setError(err?.response?.data?.detail || err.message || 'Failed to load patch');
    } finally {
      setLoading(false);
    }
  };

  const handleEdit = async () => {
    try {
      setError(null);
      const updated = await fixesApi.editFix(patchId, editedDiff, 'Manual user edit in Monaco workspace');
      setPatch(updated);
      setActionSuccess('Patch diff updated. Approvals and validations have been cleared (Invariant I8).');
    } catch (err: any) {
      setError(err?.response?.data?.detail || err.message || 'Failed to edit patch');
    }
  };

  const handleRevise = async () => {
    if (!revisionInstruction.trim()) return;
    try {
      setError(null);
      const updated = await fixesApi.reviseFix(patchId, revisionInstruction);
      setPatch(updated);
      setEditedDiff(updated.unified_diff);
      setRevisionInstruction('');
      setActionSuccess('Patch revision applied by AI generator.');
    } catch (err: any) {
      setError(err?.response?.data?.detail || err.message || 'Failed to revise patch');
    }
  };

  const handleValidate = async (consentExecute: boolean) => {
    try {
      setError(null);
      const updated = await fixesApi.validateFix(patchId, consentExecute);
      setPatch(updated);
      setActionSuccess(`Validation finished: ${updated.status}`);
    } catch (err: any) {
      setError(err?.response?.data?.detail || err.message || 'Failed to validate patch');
    }
  };

  const handleApprove = async () => {
    if (!patch) return;
    try {
      setError(null);
      const updated = await fixesApi.approveFix(patchId, patch.diff_sha256, 'EXPORT');
      setPatch(updated);
      setActionSuccess('Patch cryptographically approved for EXPORT.');
    } catch (err: any) {
      setError(err?.response?.data?.detail || err.message || 'Failed to approve patch');
    }
  };

  const handleReject = async () => {
    try {
      setError(null);
      const updated = await fixesApi.rejectFix(patchId, 'Rejected by user review');
      setPatch(updated);
      setActionSuccess('Patch rejected.');
    } catch (err: any) {
      setError(err?.response?.data?.detail || err.message || 'Failed to reject patch');
    }
  };

  const handleExport = async () => {
    try {
      setError(null);
      const blob = await fixesApi.exportFix(patchId);
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `codepilot-${patchId.substring(0, 8)}.diff`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      setActionSuccess('Unified diff downloaded with nosniff attachment headers.');
    } catch (err: any) {
      setError(err?.response?.data?.detail || err.message || 'Failed to export patch');
    }
  };

  const handlePublishPR = async () => {
    try {
      setError(null);
      const res = await fixesApi.createPullRequest(patchId, {
        publish_approval_id: `approval-${Date.now()}`,
        branch_name: prBranch,
        title: prTitle,
        body: prBody,
      });
      setActionSuccess(`Pull Request #${res.pull_request_number} published to branch ${res.branch_name}`);
    } catch (err: any) {
      setError(err?.response?.data?.detail || err.message || 'Failed to publish PR');
    }
  };

  if (loading) {
    return <div className="p-6 text-gray-500">Loading patch artifact...</div>;
  }

  if (!patch) {
    return <div className="p-6 text-red-500">{error || 'Patch not found'}</div>;
  }

  return (
    <div className="flex flex-col h-full bg-slate-900 text-slate-100 p-6 space-y-6">
      <div className="flex items-center justify-between border-b border-slate-700 pb-4">
        <div>
          <h1 className="text-xl font-bold flex items-center space-x-3">
            <span>Fix Proposal ({patch.id.substring(0, 8)})</span>
            <span
              className={`px-2.5 py-0.5 rounded text-xs font-semibold ${
                patch.status === 'VALIDATED' || patch.status === 'APPROVED'
                  ? 'bg-emerald-800 text-emerald-200'
                  : patch.status === 'VALIDATION_FAILED' || patch.status === 'REJECTED'
                  ? 'bg-rose-800 text-rose-200'
                  : 'bg-amber-800 text-amber-200'
              }`}
            >
              {patch.status}
            </span>
            <span className="text-xs text-slate-400">v{patch.version}</span>
          </h1>
          <p className="text-xs text-slate-400 mt-1">
            Diff SHA256: <code className="font-mono text-cyan-300">{patch.diff_sha256}</code>
          </p>
        </div>

        <div className="flex items-center space-x-2">
          <button
            onClick={() => handleValidate(false)}
            className="px-3 py-1.5 bg-indigo-600 hover:bg-indigo-500 rounded text-sm font-medium"
          >
            Validate (Static)
          </button>
          <button
            onClick={() => handleValidate(true)}
            className="px-3 py-1.5 bg-blue-600 hover:bg-blue-500 rounded text-sm font-medium"
          >
            Validate + Test (Sandbox)
          </button>
          <button
            onClick={handleApprove}
            disabled={patch.status !== 'VALIDATED'}
            className="px-3 py-1.5 bg-emerald-600 hover:bg-emerald-500 disabled:opacity-40 rounded text-sm font-medium"
          >
            Approve Export
          </button>
          <button
            onClick={handleExport}
            disabled={patch.status !== 'APPROVED'}
            className="px-3 py-1.5 bg-teal-600 hover:bg-teal-500 disabled:opacity-40 rounded text-sm font-medium"
          >
            Export Diff
          </button>
          <button
            onClick={handleReject}
            className="px-3 py-1.5 bg-rose-600 hover:bg-rose-500 rounded text-sm font-medium"
          >
            Reject
          </button>
        </div>
      </div>

      {actionSuccess && (
        <div className="bg-emerald-950 border border-emerald-600 text-emerald-200 text-sm p-3 rounded">
          {actionSuccess}
        </div>
      )}

      {error && (
        <div className="bg-rose-950 border border-rose-600 text-rose-200 text-sm p-3 rounded">
          {error}
        </div>
      )}

      <div className="grid grid-cols-3 gap-6 flex-1">
        {/* Monaco/Diff editor */}
        <div className="col-span-2 flex flex-col space-y-3">
          <div className="flex items-center justify-between text-sm font-medium text-slate-300">
            <span>Unified Diff Preview & Review</span>
            <button
              onClick={handleEdit}
              className="text-xs bg-slate-700 hover:bg-slate-600 px-2 py-1 rounded text-cyan-300"
            >
              Apply Edit (Invariant I8)
            </button>
          </div>
          <textarea
            value={editedDiff}
            onChange={(e) => setEditedDiff(e.target.value)}
            className="w-full flex-1 font-mono text-xs bg-slate-950 border border-slate-700 p-3 rounded text-slate-200 resize-none focus:outline-none focus:border-cyan-500"
            rows={18}
          />

          <div className="bg-slate-800 p-3 rounded border border-slate-700">
            <span className="text-xs font-semibold text-slate-400 uppercase">AI Revision Instruction</span>
            <div className="flex space-x-2 mt-1">
              <input
                type="text"
                placeholder="e.g. Ensure type annotations are added and comments follow docstring rules"
                value={revisionInstruction}
                onChange={(e) => setRevisionInstruction(e.target.value)}
                className="flex-1 text-xs bg-slate-900 border border-slate-700 p-2 rounded text-slate-200"
              />
              <button
                onClick={handleRevise}
                className="px-3 py-1.5 bg-purple-600 hover:bg-purple-500 text-xs font-medium rounded"
              >
                Revise Patch
              </button>
            </div>
          </div>
        </div>

        {/* Validation and PR Publishing Panel */}
        <div className="flex flex-col space-y-6">
          <div className="bg-slate-800 border border-slate-700 rounded p-4">
            <h2 className="text-sm font-bold text-slate-200 mb-3">Validation Results</h2>
            {patch.validation && patch.validation.length > 0 ? (
              <ul className="space-y-2 text-xs">
                {patch.validation.map((v, i) => (
                  <li key={i} className="flex flex-col p-2 bg-slate-900 rounded border border-slate-700">
                    <div className="flex justify-between font-semibold">
                      <span>{v.kind}</span>
                      <span
                        className={
                          v.status === 'PASSED'
                            ? 'text-emerald-400'
                            : v.status === 'FAILED'
                            ? 'text-rose-400'
                            : 'text-amber-400'
                        }
                      >
                        {v.status}
                      </span>
                    </div>
                    <span className="text-slate-400 text-[11px] mt-1">{v.detail}</span>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="text-xs text-slate-500 italic">No validation runs recorded. Click validate to run checks.</p>
            )}
          </div>

          <div className="bg-slate-800 border border-slate-700 rounded p-4 space-y-3">
            <h2 className="text-sm font-bold text-slate-200">GitHub Pull Request (D3 Gate)</h2>
            <div className="space-y-2 text-xs">
              <div>
                <label className="text-slate-400 block mb-1">Branch Name</label>
                <div className="flex items-center space-x-1">
                  <span className="text-slate-500">codepilot/</span>
                  <input
                    type="text"
                    value={prBranch}
                    onChange={(e) => setPrBranch(e.target.value)}
                    className="flex-1 bg-slate-900 border border-slate-700 p-1.5 rounded text-slate-200"
                  />
                </div>
              </div>
              <div>
                <label className="text-slate-400 block mb-1">Title</label>
                <input
                  type="text"
                  value={prTitle}
                  onChange={(e) => setPrTitle(e.target.value)}
                  className="w-full bg-slate-900 border border-slate-700 p-1.5 rounded text-slate-200"
                />
              </div>
              <div>
                <label className="text-slate-400 block mb-1">Description</label>
                <textarea
                  value={prBody}
                  onChange={(e) => setPrBody(e.target.value)}
                  className="w-full bg-slate-900 border border-slate-700 p-1.5 rounded text-slate-200 text-xs"
                  rows={3}
                />
              </div>
              <button
                onClick={handlePublishPR}
                disabled={patch.status !== 'APPROVED'}
                className="w-full py-2 bg-blue-600 hover:bg-blue-500 disabled:opacity-40 rounded text-xs font-semibold text-white mt-2"
              >
                Publish Pull Request
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
