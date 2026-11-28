import React, { useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { 
  X, 
  GitBranch, 
  FolderGit2, 
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
  Sparkles
} from 'lucide-react';
import { Repository, IngestionJob, RetrievalMethod, JobStage } from '../types/repository';
import { repositoryService } from '../services/repositoryService';

interface IngestionProgressModalProps {
  repository: Repository;
  isOpen: boolean;
  autoStart?: boolean;
  onClose: () => void;
  onComplete?: () => void;
}

const STAGES: { key: JobStage; label: string }[] = [
  { key: 'VALIDATING', label: 'Validating' },
  { key: 'CLONING', label: 'Cloning' },
  { key: 'SCANNING', label: 'Scanning' },
  { key: 'PARSING', label: 'Parsing' },
  { key: 'CHUNKING', label: 'Chunking' },
  { key: 'STORING', label: 'Storing' },
  { key: 'COMPLETED', label: 'Completed' },
];

export const IngestionProgressModal: React.FC<IngestionProgressModalProps> = ({
  repository,
  isOpen,
  autoStart = false,
  onClose,
  onComplete
}) => {
  const navigate = useNavigate();
  const [job, setJob] = useState<IngestionJob | null>(null);
  const selectedMethod: RetrievalMethod = 'GIT_CLONE';
  const selectedBranch = repository.tracked_branch || repository.default_branch || 'main';
  const [isLoading, setIsLoading] = useState(false);
  const [isActionLoading, setIsActionLoading] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const autoStartedRef = useRef<string | null>(null);

  // Poll job status
  useEffect(() => {
    if (!isOpen) return;

    let isMounted = true;
    let pollInterval: ReturnType<typeof setInterval> | null = null;

    const fetchStatus = async () => {
      try {
        const latestJob = await repositoryService.getCloneStatus(repository.id);
        if (isMounted) {
          setJob(latestJob);
          if (!latestJob && autoStart && autoStartedRef.current !== repository.id) {
            autoStartedRef.current = repository.id;
            setIsLoading(true);
            try {
              const newJob = await repositoryService.cloneRepository(repository.id, {
                branch: selectedBranch,
                retrieval_method: selectedMethod
              });
              if (isMounted) setJob(newJob);
            } catch (startErr: any) {
              if (isMounted) {
                setErrorMsg(startErr.response?.data?.error?.message || startErr.message || 'Failed to start ingestion.');
              }
            } finally {
              if (isMounted) setIsLoading(false);
            }
          }
          if (latestJob?.status === 'SUCCEEDED' && onComplete) {
            onComplete();
          }
        }
      } catch (err) {
        console.error('Failed to fetch clone status:', err);
      }
    };

    fetchStatus();

    // Poll every 1.2 seconds if job is active
    pollInterval = setInterval(() => {
      if (job?.status === 'QUEUED' || job?.status === 'RUNNING') {
        fetchStatus();
      }
    }, 1200);

    return () => {
      isMounted = false;
      if (pollInterval) clearInterval(pollInterval);
    };
  }, [isOpen, repository.id, job?.status]);

  if (!isOpen) return null;

  const handleStartClone = async () => {
    setIsLoading(true);
    setErrorMsg(null);
    try {
      const newJob = await repositoryService.cloneRepository(repository.id, {
        branch: selectedBranch,
        retrieval_method: selectedMethod
      });
      setJob(newJob);
    } catch (err: any) {
      const msg = err.response?.data?.error?.message || err.message || 'Failed to start cloning.';
      setErrorMsg(msg);
    } finally {
      setIsLoading(false);
    }
  };

  const handleCancel = async () => {
    if (!job) return;
    setIsActionLoading(true);
    try {
      const updated = await repositoryService.cancelJob(job.id);
      setJob(updated);
    } catch (err: any) {
      setErrorMsg(err.response?.data?.error?.message || 'Failed to cancel job.');
    } finally {
      setIsActionLoading(false);
    }
  };

  const handleRetry = async () => {
    if (!job) return;
    setIsActionLoading(true);
    setErrorMsg(null);
    try {
      const updated = await repositoryService.retryJob(job.id);
      setJob(updated);
    } catch (err: any) {
      setErrorMsg(err.response?.data?.error?.message || 'Failed to retry job.');
    } finally {
      setIsActionLoading(false);
    }
  };

  const isRunning = job?.status === 'QUEUED' || job?.status === 'RUNNING';
  const isFailed = job?.status === 'FAILED';
  const isCancelled = job?.status === 'CANCELLED';
  const isCompleted = job?.status === 'SUCCEEDED';
  const isSucceeded = isCompleted || repository.analysis_status === 'READY';

  const formatBytes = (bytes: number) => {
    if (bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return `${(bytes / Math.pow(k, i)).toFixed(1)} ${sizes[i]}`;
  };

  // Find index of current stage in STAGES
  const currentStageIndex = STAGES.findIndex(s => s.key === job?.stage);

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/75 backdrop-blur-sm animate-in fade-in duration-200">
      <div className="bg-surface-darker border border-surface-border rounded-3xl w-full max-w-2xl shadow-2xl overflow-hidden flex flex-col max-h-[90vh]">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-5 border-b border-surface-border/60 bg-surface-dark/40">
          <div className="flex items-center space-x-3 min-w-0">
            <div className="w-10 h-10 rounded-2xl bg-brand-500/10 border border-brand-500/30 flex items-center justify-center text-brand-400 flex-shrink-0">
              <FolderGit2 className="w-5 h-5" />
            </div>
            <div className="min-w-0">
              <h2 className="text-base font-semibold text-slate-100 truncate">
                {repository.owner}/{repository.name}
              </h2>
              <div className="flex items-center space-x-2 text-xs text-slate-400">
                <span className="flex items-center space-x-1">
                  <GitBranch className="w-3 h-3 text-slate-500" />
                  <span className="font-mono">{job?.branch || selectedBranch}</span>
                </span>
                <span>•</span>
                <span className="font-mono text-brand-400/90 text-[11px]">
                  {job?.retrieval_method || selectedMethod}
                </span>
              </div>
            </div>
          </div>

          <button
            onClick={onClose}
            className="p-2 rounded-xl text-slate-400 hover:text-slate-200 hover:bg-surface-border/40 transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Body */}
        <div className="p-6 overflow-y-auto space-y-6">
          {/* Ready-to-ingest summary (auto-detected branch and retrieval method) */}
          {!job && (
            <div className="bg-surface-dark/60 border border-surface-border/60 rounded-2xl p-4 space-y-3">
              <div className="flex items-center justify-between text-xs">
                <span className="text-slate-400">Detected Default Branch</span>
                <span className="font-mono text-slate-200 bg-surface-darkest px-2.5 py-1 rounded-lg border border-surface-border">
                  {selectedBranch}
                </span>
              </div>
              <div className="flex items-center justify-between text-xs">
                <span className="text-slate-400">Retrieval Method</span>
                <span className="font-mono text-brand-300 bg-brand-950/40 px-2.5 py-1 rounded-lg border border-brand-800/40">
                  Automatic ({selectedMethod})
                </span>
              </div>
              <p className="text-[11px] text-slate-400 pt-1 border-t border-surface-border/40">
                Cloning will automatically run AST parsing and Code Intelligence indexing. File summaries are only generated when explicitly requested.
              </p>
            </div>
          )}

          {/* Stepper Stages */}
          {job && (
            <div className="space-y-4">
              <div className="flex items-center justify-between text-xs text-slate-400 px-1">
                <span className="font-semibold text-slate-200">Ingestion Pipeline</span>
                <span className={`font-mono text-[11px] px-2 py-0.5 rounded-full border ${
                  isRunning 
                    ? 'bg-blue-950/60 text-blue-300 border-blue-800/60' 
                    : isCompleted
                    ? 'bg-emerald-950/60 text-emerald-300 border-emerald-800/60'
                    : 'bg-rose-950/60 text-rose-300 border-rose-800/60'
                }`}>
                  {job.status}
                </span>
              </div>

              {/* Progress Steps */}
              <div className="grid grid-cols-7 gap-1.5">
                {STAGES.map((s, idx) => {
                  const isCurrent = s.key === job.stage;
                  const isDone = currentStageIndex > idx || isCompleted;
                  const isFailedStage = isFailed && isCurrent;

                  return (
                    <div key={s.key} className="flex flex-col items-center space-y-1.5">
                      <div
                        className={`w-full h-1.5 rounded-full transition-all ${
                          isFailedStage
                            ? 'bg-rose-500'
                            : isDone
                            ? 'bg-emerald-500'
                            : isCurrent
                            ? 'bg-brand-500 animate-pulse'
                            : 'bg-surface-border/60'
                        }`}
                      />
                      <span className={`text-[10px] font-mono truncate w-full text-center ${
                        isCurrent
                          ? 'text-brand-300 font-bold'
                          : isDone
                          ? 'text-emerald-400/90'
                          : 'text-slate-500'
                      }`}>
                        {s.label}
                      </span>
                    </div>
                  );
                })}
              </div>

              {/* Progress Bar & Message */}
              <div className="bg-surface-darkest/90 border border-surface-border/70 rounded-2xl p-4 space-y-3">
                <div className="flex items-center justify-between text-xs">
                  <div className="flex items-center space-x-2 text-slate-300 min-w-0">
                    {isRunning ? (
                      <Loader2 className="w-4 h-4 text-brand-400 animate-spin flex-shrink-0" />
                    ) : isCompleted ? (
                      <CheckCircle2 className="w-4 h-4 text-emerald-400 flex-shrink-0" />
                    ) : (
                      <AlertCircle className="w-4 h-4 text-rose-400 flex-shrink-0" />
                    )}
                    <span className="truncate font-mono text-[11px] text-slate-300">
                      {job.progress_message || 'Initializing process...'}
                    </span>
                  </div>

                  <span className="font-mono text-xs text-brand-400 font-semibold flex-shrink-0 ml-2">
                    {job.progress !== null ? `${Math.round(job.progress * 100)}%` : isRunning ? 'In Progress' : ''}
                  </span>
                </div>

                {/* Progress bar container */}
                <div className="w-full bg-surface-dark rounded-full h-2 overflow-hidden border border-surface-border/50">
                  {job.progress !== null ? (
                    <div
                      className="bg-brand-500 h-full rounded-full transition-all duration-300"
                      style={{ width: `${Math.round(job.progress * 100)}%` }}
                    />
                  ) : isRunning ? (
                    <div className="bg-gradient-to-r from-brand-600 via-brand-400 to-brand-600 h-full w-full animate-indeterminate rounded-full" />
                  ) : isCompleted ? (
                    <div className="bg-emerald-500 h-full w-full rounded-full" />
                  ) : (
                    <div className="bg-rose-500 h-full w-full rounded-full" />
                  )}
                </div>

                {/* Byte & Sha indicators */}
                <div className="flex items-center justify-between text-[11px] text-slate-400 font-mono pt-1">
                  <span>
                    {job.bytes_downloaded > 0 && (
                      <>
                        Downloaded: {formatBytes(job.bytes_downloaded)}
                        {job.total_bytes && ` / ${formatBytes(job.total_bytes)}`}
                      </>
                    )}
                  </span>
                  <span>
                    {job.commit_sha && `Commit: ${job.commit_sha.substring(0, 7)}`}
                  </span>
                </div>
              </div>

              {/* Statistics Grid */}
              <div className="grid grid-cols-4 gap-3">
                <div className="bg-surface-dark/70 border border-surface-border/60 rounded-2xl p-3 text-center">
                  <div className="flex items-center justify-center space-x-1 text-slate-400 text-[10px] mb-1">
                    <Files className="w-3 h-3" />
                    <span>Discovered</span>
                  </div>
                  <div className="font-mono text-sm font-semibold text-slate-100">
                    {job.files_discovered.toLocaleString()}
                  </div>
                </div>

                <div className="bg-surface-dark/70 border border-surface-border/60 rounded-2xl p-3 text-center">
                  <div className="flex items-center justify-center space-x-1 text-emerald-400/80 text-[10px] mb-1">
                    <FileCode className="w-3 h-3" />
                    <span>Source Files</span>
                  </div>
                  <div className="font-mono text-sm font-semibold text-emerald-300">
                    {job.files_processed.toLocaleString()}
                  </div>
                </div>

                <div className="bg-surface-dark/70 border border-surface-border/60 rounded-2xl p-3 text-center">
                  <div className="flex items-center justify-center space-x-1 text-slate-400 text-[10px] mb-1">
                    <FileCheck className="w-3 h-3" />
                    <span>Skipped</span>
                  </div>
                  <div className="font-mono text-sm font-semibold text-slate-300">
                    {job.files_skipped.toLocaleString()}
                  </div>
                </div>

                <div className="bg-surface-dark/70 border border-surface-border/60 rounded-2xl p-3 text-center">
                  <div className="flex items-center justify-center space-x-1 text-rose-400/80 text-[10px] mb-1">
                    <FileX className="w-3 h-3" />
                    <span>Failed</span>
                  </div>
                  <div className="font-mono text-sm font-semibold text-rose-400">
                    {job.files_failed.toLocaleString()}
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* Error Banner */}
          {(errorMsg || (isFailed && job?.error_message)) && (
            <div className="bg-rose-950/60 border border-rose-800/80 rounded-2xl p-4 flex items-start space-x-3 text-rose-200 text-xs">
              <AlertCircle className="w-4 h-4 text-rose-400 flex-shrink-0 mt-0.5" />
              <div>
                <div className="font-semibold mb-0.5">Operation Error</div>
                <div className="text-rose-300 leading-relaxed">
                  {errorMsg || job?.error_message}
                </div>
              </div>
            </div>
          )}
        </div>

        {/* Footer Actions */}
        <div className="px-6 py-4 border-t border-surface-border/60 bg-surface-dark/40 flex items-center justify-between">
          <div className="text-xs text-slate-500 font-mono">
            {job ? `Job: ${job.id.substring(0, 8)}` : 'Ready to clone'}
          </div>

          <div className="flex items-center space-x-3">
            {isRunning && (
              <button
                onClick={handleCancel}
                disabled={isActionLoading || job?.cancel_requested}
                className="px-3 py-1.5 rounded-xl border border-rose-500/40 text-rose-300 hover:bg-rose-500/10 text-xs font-semibold flex items-center space-x-1.5 transition-colors cursor-pointer disabled:opacity-50"
              >
                <Ban className="w-3.5 h-3.5" />
                <span>{job?.cancel_requested ? 'Cancelling...' : 'Cancel'}</span>
              </button>
            )}

            {(isFailed || isCancelled) && (
              <button
                onClick={handleRetry}
                disabled={isActionLoading}
                className="px-3.5 py-1.5 rounded-xl bg-brand-500 hover:bg-brand-400 text-surface-darkest text-xs font-bold flex items-center space-x-1.5 transition-colors cursor-pointer disabled:opacity-50"
              >
                <RefreshCw className={`w-3.5 h-3.5 ${isActionLoading ? 'animate-spin' : ''}`} />
                <span>Retry</span>
              </button>
            )}

            {isSucceeded && (
              <button
                onClick={() => {
                  onClose();
                  navigate(`/repositories/${repository.id}`);
                }}
                className="px-4 py-2 rounded-xl bg-brand-500 hover:bg-brand-400 text-surface-darkest text-xs font-bold flex items-center space-x-1.5 transition-colors cursor-pointer shadow-md shadow-brand-500/20"
              >
                <Sparkles className="w-3.5 h-3.5" />
                <span>Explore Codebase</span>
              </button>
            )}

            {!job && (
              <button
                onClick={handleStartClone}
                disabled={isLoading}
                className="px-4 py-2 rounded-xl bg-brand-500 hover:bg-brand-400 text-surface-darkest text-xs font-bold flex items-center space-x-1.5 transition-colors cursor-pointer disabled:opacity-50 shadow-md shadow-brand-500/20"
              >
                {isLoading ? (
                  <>
                    <Loader2 className="w-3.5 h-3.5 animate-spin" />
                    <span>Queuing...</span>
                  </>
                ) : (
                  <>
                    <Download className="w-3.5 h-3.5" />
                    <span>Start Ingestion</span>
                  </>
                )}
              </button>
            )}

            <button
              onClick={onClose}
              className="px-3.5 py-1.5 rounded-xl border border-surface-border text-slate-300 hover:bg-surface-border/40 text-xs font-semibold transition-colors cursor-pointer"
            >
              Close
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};
