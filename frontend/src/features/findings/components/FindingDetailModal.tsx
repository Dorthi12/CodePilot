import React, { useEffect, useState } from 'react';
import {
  Finding,
  FindingOrigin,
  FindingSeverity,
  FindingStatus,
} from '../../../types/findings';
import { findingsApi } from '../services/findings_api';
import {
  AlertTriangle,
  Bug,
  CheckCircle2,
  Clock,
  Code2,
  ExternalLink,
  Info,
  Shield,
  ShieldAlert,
  Sparkles,
  X,
} from 'lucide-react';

interface FindingDetailModalProps {
  finding: Finding | null;
  onClose: () => void;
  onStatusUpdated: (updated: Finding) => void;
}

export const FindingDetailModal: React.FC<FindingDetailModalProps> = ({
  finding,
  onClose,
  onStatusUpdated,
}) => {
  const [selectedStatus, setSelectedStatus] = useState<FindingStatus>(
    finding?.status || 'OPEN'
  );
  const [reason, setReason] = useState<string>('');
  const [isUpdating, setIsUpdating] = useState<boolean>(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  useEffect(() => {
    setSelectedStatus(finding?.status || 'OPEN');
    setReason('');
    setErrorMsg(null);
  }, [finding?.id, finding?.status]);

  if (!finding) return null;

  const getOriginBadge = (origin: FindingOrigin) => {
    switch (origin) {
      case 'STATIC_TOOL':
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-semibold bg-blue-500/10 text-blue-400 border border-blue-500/20">
            <Code2 className="w-3.5 h-3.5" /> Static Tool
          </span>
        );
      case 'GRAPH_RULE':
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-semibold bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
            <CheckCircle2 className="w-3.5 h-3.5" /> Graph Metric Rule
          </span>
        );
      case 'AI_HYPOTHESIS':
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-semibold bg-purple-500/10 text-purple-400 border border-purple-500/20">
            <Sparkles className="w-3.5 h-3.5" /> AI Hypothesis (Unconfirmed)
          </span>
        );
      case 'CONFIRMED':
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-semibold bg-rose-500/10 text-rose-400 border border-rose-500/20">
            <ShieldAlert className="w-3.5 h-3.5" /> Confirmed Defect
          </span>
        );
    }
  };

  const getSeverityBadge = (severity: FindingSeverity) => {
    const colors: Record<FindingSeverity, string> = {
      CRITICAL: 'bg-rose-500/20 text-rose-300 border-rose-500/40',
      HIGH: 'bg-orange-500/20 text-orange-300 border-orange-500/40',
      MEDIUM: 'bg-amber-500/20 text-amber-300 border-amber-500/40',
      LOW: 'bg-sky-500/20 text-sky-300 border-sky-500/40',
      INFO: 'bg-slate-500/20 text-slate-300 border-slate-500/40',
    };
    return (
      <span
        className={`px-2.5 py-0.5 rounded text-xs font-bold border uppercase tracking-wider ${colors[severity]}`}
      >
        {severity}
      </span>
    );
  };

  const handleUpdateStatus = async () => {
    if (['FALSE_POSITIVE', 'ACCEPTED_RISK'].includes(selectedStatus) && !reason.trim()) {
      setErrorMsg('A justification reason is required for false-positive and accepted-risk decisions.');
      return;
    }

    setIsUpdating(true);
    setErrorMsg(null);
    try {
      const updated = await findingsApi.updateFinding(finding.id, {
        status: selectedStatus,
        reason: reason.trim() || undefined,
      });
      onStatusUpdated(updated);
      onClose();
    } catch (err: any) {
      setErrorMsg(
        err.response?.data?.detail || err.message || 'Failed to update finding status.'
      );
    } finally {
      setIsUpdating(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm animate-in fade-in duration-150">
      <div className="bg-slate-900 border border-slate-800 rounded-xl max-w-3xl w-full max-h-[90vh] flex flex-col shadow-2xl overflow-hidden">
        {/* Header */}
        <div className="flex items-start justify-between p-6 border-b border-slate-800">
          <div className="space-y-2">
            <div className="flex items-center gap-2.5 flex-wrap">
              {getSeverityBadge(finding.severity)}
              {getOriginBadge(finding.origin)}
              <span className="px-2 py-0.5 rounded text-xs font-mono bg-slate-800 text-slate-300 border border-slate-700">
                {finding.rule_id}
              </span>
              {finding.cwe && (
                <span className="px-2 py-0.5 rounded text-xs font-mono bg-indigo-950 text-indigo-300 border border-indigo-800">
                  {finding.cwe}
                </span>
              )}
              {finding.owasp && (
                <span className="px-2 py-0.5 rounded text-xs font-mono bg-violet-950 text-violet-300 border border-violet-800">
                  {finding.owasp}
                </span>
              )}
            </div>
            <h2 className="text-xl font-bold text-slate-100">{finding.title}</h2>
            <div className="flex items-center gap-2 text-xs text-slate-400 font-mono">
              <span>{finding.file_path}</span>
              <span>•</span>
              <span>Lines {finding.line_start}–{finding.line_end}</span>
              <span>•</span>
              <span>Tool: {finding.tool} ({finding.tool_version})</span>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-1 rounded-lg text-slate-400 hover:text-slate-100 hover:bg-slate-800 transition"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Content Body */}
        <div className="flex-1 overflow-y-auto p-6 space-y-6">
          {/* Description */}
          {finding.description && (
            <div className="space-y-1">
              <h4 className="text-xs font-semibold uppercase tracking-wider text-slate-400">
                Analysis Details
              </h4>
              <p className="text-sm text-slate-300 leading-relaxed bg-slate-950/50 p-3 rounded-lg border border-slate-800/80">
                {finding.description}
              </p>
            </div>
          )}

          {/* Remediation */}
          {finding.remediation && (
            <div className="space-y-1">
              <h4 className="text-xs font-semibold uppercase tracking-wider text-emerald-400 flex items-center gap-1.5">
                <CheckCircle2 className="w-4 h-4" /> Recommended Remediation
              </h4>
              <p className="text-sm text-emerald-300/90 bg-emerald-950/20 border border-emerald-900/30 p-3 rounded-lg">
                {finding.remediation}
              </p>
            </div>
          )}

          {/* Evidence Snippet */}
          {finding.evidence && finding.evidence.length > 0 && (
            <div className="space-y-2">
              <h4 className="text-xs font-semibold uppercase tracking-wider text-slate-400 flex items-center justify-between">
                <span>Code Evidence (Lines {finding.line_start}–{finding.line_end})</span>
                <span className="text-[10px] text-slate-500 font-mono">
                  {finding.evidence[0].role}
                </span>
              </h4>
              <div className="bg-slate-950 border border-slate-800 rounded-lg p-3 font-mono text-xs overflow-x-auto text-slate-300">
                <pre>{finding.evidence[0].snippet}</pre>
              </div>
            </div>
          )}

          {/* Audit trail */}
          {finding.status_reason && (
            <div className="space-y-1 bg-slate-800/40 p-3 rounded-lg border border-slate-700/50 text-xs">
              <div className="font-semibold text-slate-300 flex items-center gap-1.5">
                <Clock className="w-3.5 h-3.5 text-slate-400" /> Status Update History
              </div>
              <p className="text-slate-300 mt-1">{finding.status_reason}</p>
              <div className="text-[10px] text-slate-400 mt-0.5">
                Updated by: {finding.status_updated_by || 'Unknown'} •{' '}
                {finding.status_updated_at ? new Date(finding.status_updated_at).toLocaleString() : ''}
              </div>
            </div>
          )}

          {/* Triage / Status Update Form */}
          <div className="pt-4 border-t border-slate-800 space-y-3">
            <h4 className="text-xs font-semibold uppercase tracking-wider text-slate-300">
              Triage Finding Status
            </h4>
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
              {(['OPEN', 'ACKNOWLEDGED', 'FALSE_POSITIVE', 'ACCEPTED_RISK'] as FindingStatus[]).map(
                (st) => (
                  <button
                    key={st}
                    type="button"
                    onClick={() => setSelectedStatus(st)}
                    className={`px-3 py-2 rounded-lg text-xs font-semibold border transition text-center ${
                      selectedStatus === st
                        ? 'bg-blue-600 text-white border-blue-500 shadow-md'
                        : 'bg-slate-800 text-slate-300 border-slate-700 hover:bg-slate-700'
                    }`}
                  >
                    {st.replace('_', ' ')}
                  </button>
                )
              )}
            </div>

            {['FALSE_POSITIVE', 'ACCEPTED_RISK'].includes(selectedStatus) && (
              <div className="space-y-1 pt-1">
                <label className="text-xs font-medium text-amber-400 flex items-center gap-1">
                  <AlertTriangle className="w-3.5 h-3.5" /> Justification Reason (Required)
                </label>
                <textarea
                  value={reason}
                  onChange={(e) => setReason(e.target.value)}
                  placeholder="Explain why this finding is safe or validated upstream..."
                  className="w-full h-20 px-3 py-2 bg-slate-950 border border-slate-700 rounded-lg text-xs text-slate-200 placeholder-slate-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
                />
              </div>
            )}

            {errorMsg && (
              <div className="p-2.5 rounded-lg bg-rose-500/10 border border-rose-500/30 text-rose-400 text-xs">
                {errorMsg}
              </div>
            )}
          </div>
        </div>

        {/* Footer */}
        <div className="flex items-center justify-end gap-3 p-4 border-t border-slate-800 bg-slate-900/50">
          <button
            onClick={onClose}
            className="px-4 py-2 text-xs font-medium text-slate-300 hover:text-white transition"
          >
            Cancel
          </button>
          <button
            onClick={handleUpdateStatus}
            disabled={isUpdating}
            className="px-4 py-2 text-xs font-semibold bg-blue-600 hover:bg-blue-500 disabled:opacity-50 text-white rounded-lg transition shadow"
          >
            {isUpdating ? 'Updating...' : 'Save Triage Status'}
          </button>
        </div>
      </div>
    </div>
  );
};
