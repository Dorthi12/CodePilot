import React, { useEffect, useState, useCallback } from 'react';
import {
  Download,
  CheckCircle2,
  AlertCircle,
  Loader2,
  RefreshCw,
  Ban,
  FileCode,
  FileCheck,
  FileX,
  Files,
  Sparkles,
  Terminal,
  ArrowRight
} from 'lucide-react';
import { Repository, IngestionJob, JobStage, RetrievalMethod } from '../types/repository';
import { repositoryService } from '../services/repositoryService';

interface RepositoryProcessingStatusProps {
  repository: Repository;
  onRefreshRepo?: () => void;
  onExploreClick?: () => void;
}

interface StageStep {
  key: JobStage | 'SAVING';
  label: string;
  description: string;
}

const PIPELINE_STAGES: StageStep[] = [
  { key: 'VALIDATING', label: 'Validating', description: 'Checking repository permissions and URL' },
  { key: 'CLONING', label: 'Cloning', description: 'Cloning repository workspace' },
  { key: 'SCANNING', label: 'Scanning', description: 'Discovering source files and workspace tree' },
  { key: 'PARSING', label: 'Parsing Code', description: 'Tree-sitter AST extraction (Python, JS, TS)' },
  { key: 'CHUNKING', label: 'Generating Chunks', description: 'Creating semantic code chunks and summaries' },
  { key: 'COMPLETED', label: 'Completed', description: 'Snapshot persisted and ready to explore' },
];

export const RepositoryProcessingStatus: React.FC<RepositoryProcessingStatusProps> = ({
  repository,
  onRefreshRepo,
  onExploreClick
}) => {
  const [job, setJob] = useState<IngestionJob | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [actionLoading, setActionLoading] = useState<boolean>(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [selectedMethod] = useState<RetrievalMethod>('GIT_CLONE');
  const [selectedBranch] = useState<string>(
    repository.tracked_branch || repository.default_branch || 'main'
  );

  const fetchStatus = useCallback(async () => {
    try {
      const latestJob = await repositoryService.getCloneStatus(repository.id);
      setJob(latestJob);
    } catch (err) {
      console.error('Failed to fetch job status', err);
    } finally {
      setLoading(false);
    }
  }, [repository.id]);

  useEffect(() => {
    fetchStatus();

    // Auto-refresh while job is active
    let interval: ReturnType<typeof setInterval> | null = null;
    interval = setInterval(() => {
      if (job?.status === 'QUEUED' || job?.status === 'RUNNING' || repository.analysis_status === 'ANALYZING') {
        fetchStatus();
        onRefreshRepo?.();
      }
    }, 1500);

    return () => {
      if (interval) clearInterval(interval);
    };
  }, [fetchStatus, job?.status, repository.analysis_status, onRefreshRepo]);

  const handleStartClone = async () => {
    setActionLoading(true);
    setErrorMsg(null);
    try {
      const newJob = await repositoryService.cloneRepository(repository.id, {
        branch: selectedBranch,
        retrieval_method: selectedMethod
      });
      setJob(newJob);
      onRefreshRepo?.();
    } catch (err: any) {
      const msg = err.response?.data?.error?.message || err.message || 'Failed to start ingestion.';
      setErrorMsg(msg);
    } finally {
      setActionLoading(false);
    }
  };

  const handleReanalyze = async () => {
    setActionLoading(true);
    setErrorMsg(null);
    try {
      await repositoryService.triggerAnalysis(repository.id);
      await fetchStatus();
      onRefreshRepo?.();
    } catch (err: any) {
      const msg = err.response?.data?.error?.message || err.message || 'Failed to trigger analysis.';
      setErrorMsg(msg);
    } finally {
      setActionLoading(false);
    }
  };

  const handleCancel = async () => {
    if (!job) return;
    setActionLoading(true);
    try {
      const updated = await repositoryService.cancelJob(job.id);
      setJob(updated);
      onRefreshRepo?.();
    } catch (err: any) {
      setErrorMsg('Failed to cancel job.');
    } finally {
      setActionLoading(false);
    }
  };

  const handleRetry = async () => {
    if (!job) return;
    setActionLoading(true);
    setErrorMsg(null);
    try {
      const retried = await repositoryService.retryJob(job.id);
      setJob(retried);
      onRefreshRepo?.();
    } catch (err: any) {
      setErrorMsg('Failed to retry job.');
    } finally {
      setActionLoading(false);
    }
  };

  const isRunning = job?.status === 'RUNNING' || job?.status === 'QUEUED';
  const isSucceeded = job?.status === 'SUCCEEDED' || repository.analysis_status === 'READY';
  const isFailed = job?.status === 'FAILED';
  const isCancelled = job?.status === 'CANCELLED';

  // Helper to determine stage status
  const getStageStatus = (stageKey: string): 'completed' | 'active' | 'pending' | 'failed' => {
    if (!job) {
      return isSucceeded ? 'completed' : 'pending';
    }
    if (isFailed && job.stage === stageKey) return 'failed';
    if (isSucceeded) return 'completed';

    const stageOrder = ['VALIDATING', 'CLONING', 'SCANNING', 'PARSING', 'CHUNKING', 'COMPLETED'];
    const currentIdx = stageOrder.indexOf(job.stage);
    const stepIdx = stageOrder.indexOf(stageKey);

    if (currentIdx === -1) return 'pending';
    if (stepIdx < currentIdx) return 'completed';
    if (stepIdx === currentIdx) return isRunning ? 'active' : 'completed';
    return 'pending';
  };

  if (loading) {
    return (
      <div className="bg-surface-darker/90 border border-surface-border/70 rounded-2xl p-6 flex items-center justify-center min-h-[220px]">
        <div className="flex flex-col items-center space-y-3 text-slate-400">
          <Loader2 className="w-6 h-6 animate-spin text-brand-400" />
          <span className="text-sm font-medium">Checking repository status...</span>
        </div>
      </div>
    );
  }

  return (
    <div className="bg-surface-darker/90 border border-surface-border/70 rounded-2xl p-6 shadow-xl space-y-6">
      {/* Header Row */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-4 border-b border-surface-border/50">
        <div>
          <div className="flex items-center space-x-2.5">
            <h3 className="text-base font-semibold text-slate-100">Repository Processing Pipeline</h3>
            {isRunning && (
              <span className="inline-flex items-center space-x-1.5 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-brand-500/10 text-brand-400 border border-brand-500/30">
                <Loader2 className="w-3 h-3 animate-spin" />
                <span>Processing</span>
              </span>
            )}
            {isSucceeded && (
              <span className="inline-flex items-center space-x-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-emerald-500/10 text-emerald-400 border border-emerald-500/30">
                <CheckCircle2 className="w-3 h-3" />
                <span>Ready</span>
              </span>
            )}
            {isFailed && (
              <span className="inline-flex items-center space-x-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-rose-500/10 text-rose-400 border border-rose-500/30">
                <AlertCircle className="w-3 h-3" />
                <span>Failed</span>
              </span>
            )}
          </div>
          <p className="text-xs text-slate-400 mt-1">
            {job?.progress_message || (isSucceeded ? 'Repository is parsed, chunked, and ready for exploration.' : 'Initiate cloning and AST ingestion to analyze the codebase.')}
          </p>
        </div>

        {/* Action Buttons */}
        <div className="flex items-center space-x-3 flex-shrink-0">
          {isRunning && (
            <button
              onClick={handleCancel}
              disabled={actionLoading || job?.cancel_requested}
              className="px-3 py-1.5 rounded-xl border border-rose-500/40 text-rose-300 hover:bg-rose-500/10 text-xs font-semibold flex items-center space-x-1.5 transition-colors cursor-pointer disabled:opacity-50"
            >
              <Ban className="w-3.5 h-3.5" />
              <span>{job?.cancel_requested ? 'Cancelling...' : 'Cancel'}</span>
            </button>
          )}

          {(isFailed || isCancelled) && (
            <button
              onClick={handleRetry}
              disabled={actionLoading}
              className="px-3.5 py-1.5 rounded-xl bg-brand-500 hover:bg-brand-400 text-surface-darkest text-xs font-bold flex items-center space-x-1.5 transition-colors cursor-pointer disabled:opacity-50 shadow-md shadow-brand-500/20"
            >
              <RefreshCw className={`w-3.5 h-3.5 ${actionLoading ? 'animate-spin' : ''}`} />
              <span>Retry Job</span>
            </button>
          )}

          {!job && !isSucceeded && (
            <button
              onClick={handleStartClone}
              disabled={actionLoading}
              className="px-4 py-2 rounded-xl bg-brand-500 hover:bg-brand-400 text-surface-darkest text-xs font-bold flex items-center space-x-1.5 transition-colors cursor-pointer disabled:opacity-50 shadow-lg shadow-brand-500/20"
            >
              {actionLoading ? (
                <>
                  <Loader2 className="w-3.5 h-3.5 animate-spin" />
                  <span>Starting...</span>
                </>
              ) : (
                <>
                  <Download className="w-3.5 h-3.5" />
                  <span>Start Ingestion</span>
                </>
              )}
            </button>
          )}

          {isSucceeded && (
            <>
              <button
                onClick={handleReanalyze}
                disabled={actionLoading}
                className="px-3 py-1.5 rounded-xl border border-surface-border hover:border-brand-500/40 text-slate-300 hover:text-slate-100 text-xs font-medium flex items-center space-x-1.5 transition-colors cursor-pointer"
                title="Re-run AST parsing on the cloned workspace"
              >
                <RefreshCw className={`w-3 h-3 ${actionLoading ? 'animate-spin' : ''}`} />
                <span>Re-analyze</span>
              </button>

              {onExploreClick && (
                <button
                  onClick={onExploreClick}
                  className="px-4 py-2 rounded-xl bg-brand-500 hover:bg-brand-400 text-surface-darkest text-xs font-bold flex items-center space-x-2 transition-all cursor-pointer shadow-lg shadow-brand-500/25 hover:shadow-brand-500/40 transform hover:-translate-y-0.5"
                >
                  <Sparkles className="w-3.5 h-3.5" />
                  <span>Explore Codebase</span>
                  <ArrowRight className="w-3.5 h-3.5" />
                </button>
              )}
            </>
          )}
        </div>
      </div>

      {/* Pipeline Stage Tracker */}
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3">
        {PIPELINE_STAGES.map((step, idx) => {
          const status = getStageStatus(step.key);
          return (
            <div
              key={step.key}
              className={`rounded-xl p-3 border transition-all ${
                status === 'completed'
                  ? 'bg-emerald-950/20 border-emerald-800/40 text-emerald-300'
                  : status === 'active'
                  ? 'bg-brand-950/40 border-brand-500/50 text-brand-300 shadow-md shadow-brand-500/10'
                  : status === 'failed'
                  ? 'bg-rose-950/30 border-rose-800/50 text-rose-300'
                  : 'bg-surface-dark/50 border-surface-border/40 text-slate-500'
              }`}
            >
              <div className="flex items-center justify-between mb-1.5">
                <span className="text-[10px] font-mono uppercase tracking-wider font-semibold opacity-70">
                  Step 0{idx + 1}
                </span>
                {status === 'completed' && <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />}
                {status === 'active' && <Loader2 className="w-3.5 h-3.5 text-brand-400 animate-spin" />}
                {status === 'failed' && <AlertCircle className="w-3.5 h-3.5 text-rose-400" />}
              </div>
              <div className="text-xs font-semibold text-slate-200 truncate">{step.label}</div>
              <div className="text-[10px] text-slate-400 line-clamp-2 mt-0.5 leading-snug">
                {step.description}
              </div>
            </div>
          );
        })}
      </div>

      {/* Progress Bar (when running) */}
      {isRunning && (
        <div className="space-y-1.5">
          <div className="flex items-center justify-between text-xs">
            <span className="text-slate-400 flex items-center space-x-1.5">
              <Terminal className="w-3.5 h-3.5 text-brand-400" />
              <span>{job?.progress_message || 'Processing repository files...'}</span>
            </span>
            <span className="font-mono text-brand-400 font-semibold">
              {job?.progress ? `${Math.round(job.progress * 100)}%` : 'In progress'}
            </span>
          </div>
          <div className="w-full h-2 bg-surface-dark rounded-full overflow-hidden border border-surface-border/50">
            <div
              className="h-full bg-gradient-to-r from-brand-600 to-brand-400 transition-all duration-300 rounded-full"
              style={{ width: `${Math.max(5, Math.min(100, (job?.progress || 0.15) * 100))}%` }}
            />
          </div>
        </div>
      )}

      {/* Metrics Row (Discovered, Processed, Skipped, Failed) */}
      {job && (
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 pt-2">
          <div className="bg-surface-dark/60 border border-surface-border/40 rounded-xl p-3 flex items-center space-x-3">
            <div className="p-2 rounded-lg bg-surface-dark border border-surface-border text-slate-400">
              <Files className="w-4 h-4" />
            </div>
            <div>
              <div className="text-[11px] text-slate-400">Discovered</div>
              <div className="text-sm font-semibold text-slate-100 font-mono">
                {job.files_discovered.toLocaleString()}
              </div>
            </div>
          </div>

          <div className="bg-surface-dark/60 border border-surface-border/40 rounded-xl p-3 flex items-center space-x-3">
            <div className="p-2 rounded-lg bg-emerald-950/40 border border-emerald-800/40 text-emerald-400">
              <FileCheck className="w-4 h-4" />
            </div>
            <div>
              <div className="text-[11px] text-slate-400">Processed</div>
              <div className="text-sm font-semibold text-emerald-300 font-mono">
                {job.files_processed.toLocaleString()}
              </div>
            </div>
          </div>

          <div className="bg-surface-dark/60 border border-surface-border/40 rounded-xl p-3 flex items-center space-x-3">
            <div className="p-2 rounded-lg bg-slate-900 border border-surface-border text-slate-500">
              <FileCode className="w-4 h-4" />
            </div>
            <div>
              <div className="text-[11px] text-slate-400">Skipped (Binary/Vendor)</div>
              <div className="text-sm font-semibold text-slate-400 font-mono">
                {job.files_skipped.toLocaleString()}
              </div>
            </div>
          </div>

          <div className="bg-surface-dark/60 border border-surface-border/40 rounded-xl p-3 flex items-center space-x-3">
            <div className="p-2 rounded-lg bg-rose-950/40 border border-rose-800/40 text-rose-400">
              <FileX className="w-4 h-4" />
            </div>
            <div>
              <div className="text-[11px] text-slate-400">Failed</div>
              <div className="text-sm font-semibold text-rose-300 font-mono">
                {job.files_failed.toLocaleString()}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Error Message */}
      {(errorMsg || job?.error_message) && (
        <div className="bg-rose-950/40 border border-rose-800/60 rounded-xl p-4 flex items-start space-x-3 text-xs">
          <AlertCircle className="w-4 h-4 text-rose-400 flex-shrink-0 mt-0.5" />
          <div>
            <div className="font-semibold text-rose-200">Processing Error</div>
            <div className="text-rose-300 mt-0.5 leading-relaxed">
              {errorMsg || job?.error_message}
            </div>
            {job?.error_code && (
              <div className="text-[10px] font-mono text-rose-400/80 mt-1">
                Error Code: {job.error_code}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
};
