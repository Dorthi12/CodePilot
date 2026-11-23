import React, { useState, useEffect } from 'react';
import {
  AgentRole,
  AgentRunResponse,
  MultiAgentReport,
} from '../../../types/agent';
import { agentApi } from '../../../services/agent_api';
import { ApprovalDialog } from './ApprovalDialog';
import { TaskTimeline } from './TaskTimeline';
import { ConsolidatedReportView } from './ConsolidatedReportView';
import {
  Bot,
  Play,
  StopCircle,
  FileText,
  Clock,
  CheckCircle,
  AlertCircle,
  Sparkles,
} from 'lucide-react';

export const AgentPanel: React.FC = () => {
  const [snapshotId, setSnapshotId] = useState('snap-prod-main');
  const [selectedAgents, setSelectedAgents] = useState<AgentRole[]>([
    'ARCHITECTURE',
    'SECURITY',
    'CODE_QUALITY',
    'PERFORMANCE',
  ]);
  const [requireApproval, setRequireApproval] = useState(false);
  const [tokenBudget, setTokenBudget] = useState(50000);

  const [activeRun, setActiveRun] = useState<AgentRunResponse | null>(null);
  const [report, setReport] = useState<MultiAgentReport | null>(null);
  const [activeTab, setActiveTab] = useState<'timeline' | 'report'>('timeline');
  const [isLaunching, setIsLaunching] = useState(false);
  const [isApproving, setIsApproving] = useState(false);
  const [showApprovalDialog, setShowApprovalDialog] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  // Poll or listen for updates
  useEffect(() => {
    if (!activeRun) return;

    if (activeRun.status === 'WAITING_APPROVAL') {
      setShowApprovalDialog(true);
    } else {
      setShowApprovalDialog(false);
    }

    if (activeRun.status === 'COMPLETED') {
      agentApi
        .getReport(activeRun.run_id)
        .then((rep) => {
          setReport(rep);
          setActiveTab('report');
        })
        .catch((err) => console.error('Failed to load report', err));
    }

    // Subscribe to SSE events
    if (activeRun.status === 'RUNNING' || activeRun.status === 'WAITING_APPROVAL') {
      const unsubscribe = agentApi.subscribeEvents(activeRun.run_id, (event) => {
        if (event.type === 'run_state_changed' || event.type === 'run_completed') {
          agentApi.getRun(activeRun.run_id).then(setActiveRun).catch(console.error);
        }
      });
      return () => unsubscribe();
    }
  }, [activeRun?.status, activeRun?.run_id]);

  const toggleAgent = (role: AgentRole) => {
    if (selectedAgents.includes(role)) {
      if (selectedAgents.length > 1) {
        setSelectedAgents(selectedAgents.filter((r) => r !== role));
      }
    } else {
      setSelectedAgents([...selectedAgents, role]);
    }
  };

  const handleLaunchRun = async () => {
    setIsLaunching(true);
    setErrorMsg(null);
    setReport(null);
    setActiveTab('timeline');

    try {
      const run = await agentApi.createRun({
        snapshot_id: snapshotId,
        agents: selectedAgents,
        require_plan_approval: requireApproval,
        token_budget: tokenBudget,
      });
      setActiveRun(run);
    } catch (err: any) {
      setErrorMsg(err.response?.data?.detail || err.message || 'Failed to start run');
    } finally {
      setIsLaunching(false);
    }
  };

  const handleApprove = async (comment: string) => {
    if (!activeRun) return;
    setIsApproving(true);
    try {
      const updated = await agentApi.approveRun(activeRun.run_id, 'PLAN', comment);
      setActiveRun(updated);
      setShowApprovalDialog(false);
    } catch (err: any) {
      setErrorMsg(err.response?.data?.detail || 'Failed to approve plan');
    } finally {
      setIsApproving(false);
    }
  };

  const handleCancel = async () => {
    if (!activeRun) return;
    try {
      const updated = await agentApi.cancelRun(activeRun.run_id);
      setActiveRun(updated);
      setShowApprovalDialog(false);
    } catch (err: any) {
      setErrorMsg(err.response?.data?.detail || 'Failed to cancel run');
    }
  };

  return (
    <div className="flex h-full flex-col bg-slate-950 p-6 text-slate-100">
      {/* Header */}
      <div className="mb-6 flex flex-col md:flex-row md:items-center justify-between border-b border-slate-800 pb-5 gap-4">
        <div>
          <div className="flex items-center space-x-2.5">
            <div className="rounded-lg bg-indigo-600/20 p-2 text-indigo-400">
              <Bot className="h-6 w-6" />
            </div>
            <div>
              <h1 className="text-xl font-bold tracking-tight">Multi-Agent Code Analysis (M1)</h1>
              <p className="text-xs text-slate-400">
                Coordinated autonomous specialist agents analyzing architecture, security, quality & performance
              </p>
            </div>
          </div>
        </div>

        {activeRun && (
          <div className="flex items-center space-x-3">
            <span
              className={`rounded-full border px-3 py-1 text-xs font-semibold ${
                activeRun.status === 'COMPLETED'
                  ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/30'
                  : activeRun.status === 'WAITING_APPROVAL'
                  ? 'bg-amber-500/10 text-amber-400 border-amber-500/30'
                  : activeRun.status === 'RUNNING'
                  ? 'bg-indigo-500/10 text-indigo-400 border-indigo-500/30 animate-pulse'
                  : 'bg-slate-800 text-slate-400 border-slate-700'
              }`}
            >
              Status: {activeRun.status}
            </span>

            {activeRun.status === 'RUNNING' && (
              <button
                onClick={handleCancel}
                className="flex items-center space-x-1.5 rounded-lg border border-rose-800 bg-rose-950/40 px-3 py-1.5 text-xs font-medium text-rose-300 hover:bg-rose-900/60"
              >
                <StopCircle className="h-4 w-4" />
                <span>Cancel</span>
              </button>
            )}
          </div>
        )}
      </div>

      {errorMsg && (
        <div className="mb-6 flex items-center space-x-2 rounded-xl border border-rose-500/20 bg-rose-950/30 p-3.5 text-xs text-rose-300">
          <AlertCircle className="h-4 w-4 shrink-0 text-rose-400" />
          <span>{errorMsg}</span>
        </div>
      )}

      {/* Main Grid: Control Panel + Results */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 flex-1 overflow-hidden">
        {/* Left Column: Configuration & Agent Select */}
        <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-5 space-y-5 h-fit">
          <h2 className="text-sm font-semibold text-slate-200 uppercase tracking-wider flex items-center space-x-2">
            <Sparkles className="h-4 w-4 text-indigo-400" />
            <span>Run Configuration</span>
          </h2>

          <div>
            <label className="block text-xs font-medium text-slate-400 mb-1">Pinned Snapshot ID</label>
            <input
              type="text"
              value={snapshotId}
              onChange={(e) => setSnapshotId(e.target.value)}
              className="w-full rounded-lg border border-slate-700 bg-slate-800 px-3 py-2 text-xs text-slate-200 focus:outline-none focus:border-indigo-500 font-mono"
            />
          </div>

          <div>
            <label className="block text-xs font-medium text-slate-400 mb-2">Specialist Agents</label>
            <div className="space-y-2">
              {(['ARCHITECTURE', 'SECURITY', 'CODE_QUALITY', 'PERFORMANCE'] as AgentRole[]).map((role) => {
                const isSelected = selectedAgents.includes(role);
                return (
                  <div
                    key={role}
                    onClick={() => toggleAgent(role)}
                    className={`flex items-center justify-between rounded-lg border p-2.5 cursor-pointer text-xs transition ${
                      isSelected
                        ? 'border-indigo-500/50 bg-indigo-950/30 text-indigo-200'
                        : 'border-slate-800 bg-slate-800/40 text-slate-400 hover:border-slate-700'
                    }`}
                  >
                    <span className="font-medium">{role.replace('_', ' ')} Agent</span>
                    <input
                      type="checkbox"
                      checked={isSelected}
                      readOnly
                      className="rounded border-slate-700 bg-slate-800 text-indigo-600 focus:ring-0"
                    />
                  </div>
                );
              })}
            </div>
          </div>

          <div className="border-t border-slate-800/80 pt-4 space-y-3">
            <div className="flex items-center justify-between">
              <div>
                <label className="text-xs font-medium text-slate-300 block">Require Human Plan Approval</label>
                <p className="text-[11px] text-slate-500">Pause in WAITING_APPROVAL before execution</p>
              </div>
              <input
                type="checkbox"
                checked={requireApproval}
                onChange={(e) => setRequireApproval(e.target.checked)}
                className="rounded border-slate-700 bg-slate-800 text-indigo-600 focus:ring-0 h-4 w-4"
              />
            </div>

            <div>
              <div className="flex justify-between text-xs text-slate-400 mb-1">
                <span>Token Budget</span>
                <span className="font-mono text-slate-200">{tokenBudget.toLocaleString()}</span>
              </div>
              <input
                type="range"
                min={10000}
                max={100000}
                step={5000}
                value={tokenBudget}
                onChange={(e) => setTokenBudget(Number(e.target.value))}
                className="w-full accent-indigo-500"
              />
            </div>
          </div>

          <button
            onClick={handleLaunchRun}
            disabled={isLaunching || activeRun?.status === 'RUNNING'}
            className="w-full flex items-center justify-center space-x-2 rounded-xl bg-indigo-600 py-2.5 text-xs font-semibold text-white hover:bg-indigo-500 transition shadow-lg shadow-indigo-600/30 disabled:opacity-50"
          >
            <Play className="h-4 w-4" />
            <span>{isLaunching ? 'Preparing Plan...' : 'Launch Multi-Agent Analysis'}</span>
          </button>
        </div>

        {/* Right Column: Execution View & Reports */}
        <div className="lg:col-span-2 flex flex-col space-y-4">
          {activeRun && (
            <div className="flex items-center space-x-2 border-b border-slate-800 pb-2">
              <button
                onClick={() => setActiveTab('timeline')}
                className={`flex items-center space-x-2 rounded-lg px-3 py-1.5 text-xs font-medium transition ${
                  activeTab === 'timeline'
                    ? 'bg-slate-800 text-slate-100 shadow'
                    : 'text-slate-400 hover:text-slate-200'
                }`}
              >
                <Clock className="h-3.5 w-3.5" />
                <span>Task Timeline ({activeRun.tasks?.length ?? 0})</span>
              </button>

              <button
                onClick={() => setActiveTab('report')}
                disabled={!report}
                className={`flex items-center space-x-2 rounded-lg px-3 py-1.5 text-xs font-medium transition ${
                  activeTab === 'report'
                    ? 'bg-slate-800 text-slate-100 shadow'
                    : 'text-slate-400 hover:text-slate-200 disabled:opacity-40'
                }`}
              >
                <FileText className="h-3.5 w-3.5" />
                <span>Consolidated Report {report ? `(${report.total_findings})` : ''}</span>
              </button>
            </div>
          )}

          <div className="flex-1 overflow-y-auto pr-1">
            {!activeRun ? (
              <div className="flex h-96 flex-col items-center justify-center rounded-xl border border-dashed border-slate-800 bg-slate-900/30 text-center text-slate-400 p-8">
                <Bot className="h-10 w-10 text-slate-600 mb-3" />
                <h3 className="text-sm font-semibold text-slate-300">No Active Analysis Run</h3>
                <p className="mt-1 text-xs text-slate-500 max-w-sm">
                  Select your specialist agents on the left and click "Launch Multi-Agent Analysis" to begin.
                </p>
              </div>
            ) : activeTab === 'timeline' ? (
              <TaskTimeline tasks={activeRun.tasks} />
            ) : report ? (
              <ConsolidatedReportView report={report} />
            ) : (
              <div className="p-8 text-center text-slate-400">Loading consolidated report...</div>
            )}
          </div>
        </div>
      </div>

      {/* Approval Gate Dialog */}
      {activeRun?.plan && (
        <ApprovalDialog
          isOpen={showApprovalDialog}
          plan={activeRun.plan}
          onApprove={handleApprove}
          onCancel={handleCancel}
          isSubmitting={isApproving}
        />
      )}
    </div>
  );
};
