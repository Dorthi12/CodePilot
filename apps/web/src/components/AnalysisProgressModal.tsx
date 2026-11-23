import React from 'react';
import {
  Loader2,
  CheckCircle2,
  AlertCircle,
  Sparkles
} from 'lucide-react';
import { Repository } from '../types/repository';

export interface AnalysisStage {
  id: string;
  label: string;
  description: string;
  status: 'pending' | 'in_progress' | 'completed' | 'failed';
  icon: React.ComponentType<{ className?: string }>;
}

interface AnalysisProgressModalProps {
  repository: Repository;
  isOpen: boolean;
  stages: AnalysisStage[];
  error?: string | null;
  onClose?: () => void;
  onViewResults?: () => void;
  isComplete: boolean;
}

export const AnalysisProgressModal: React.FC<AnalysisProgressModalProps> = ({
  repository,
  isOpen,
  stages,
  error,
  onClose,
  onViewResults,
  isComplete,
}) => {
  if (!isOpen) return null;

  const completedCount = stages.filter((s) => s.status === 'completed').length;
  const progressPercent = Math.round((completedCount / stages.length) * 100);

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-md animate-in fade-in duration-200">
      <div className="bg-surface-darker border border-surface-border rounded-3xl w-full max-w-2xl overflow-hidden shadow-2xl flex flex-col">
        {/* Header */}
        <div className="px-6 py-5 border-b border-surface-border/60 flex items-center justify-between">
          <div className="flex items-center space-x-3">
            <div className="w-10 h-10 rounded-2xl bg-brand-500/10 border border-brand-500/20 flex items-center justify-center text-brand-400">
              <Sparkles className="w-5 h-5 animate-pulse" />
            </div>
            <div>
              <h2 className="text-sm font-semibold text-slate-100 flex items-center gap-2">
                <span>Codebase Intelligence Analysis</span>
                {isComplete && (
                  <span className="px-2 py-0.5 rounded-full text-[10px] font-mono bg-emerald-950/80 text-emerald-300 border border-emerald-800">
                    COMPLETE
                  </span>
                )}
              </h2>
              <p className="text-xs text-slate-400 font-mono">
                {repository.owner}/{repository.name} ({repository.tracked_branch})
              </p>
            </div>
          </div>
          {onClose && (
            <button
              onClick={onClose}
              disabled={!isComplete && !error}
              className="text-slate-400 hover:text-slate-200 text-sm px-2.5 py-1 rounded-xl hover:bg-surface-dark transition-colors disabled:opacity-20 cursor-pointer"
            >
              ✕
            </button>
          )}
        </div>

        {/* Progress Bar */}
        <div className="px-6 pt-5 pb-2">
          <div className="flex items-center justify-between text-xs font-mono mb-2">
            <span className="text-slate-400">Overall Pipeline Progress</span>
            <span className="text-brand-300 font-bold">{progressPercent}%</span>
          </div>
          <div className="w-full h-2 bg-surface-dark rounded-full overflow-hidden border border-surface-border/60">
            <div
              className="h-full bg-gradient-to-r from-brand-500 to-emerald-400 transition-all duration-500 rounded-full"
              style={{ width: `${progressPercent}%` }}
            />
          </div>
        </div>

        {/* Stages list */}
        <div className="px-6 py-4 space-y-3 max-h-[50vh] overflow-y-auto">
          {stages.map((stage, idx) => {
            const Icon = stage.icon;
            const isDone = stage.status === 'completed';
            const isRunning = stage.status === 'in_progress';
            const isFailed = stage.status === 'failed';

            return (
              <div
                key={stage.id}
                className={`flex items-start space-x-3.5 p-3.5 rounded-2xl border transition-all ${
                  isRunning
                    ? 'bg-brand-950/20 border-brand-500/40 shadow-sm shadow-brand-500/10'
                    : isDone
                    ? 'bg-surface-dark/40 border-surface-border/50'
                    : isFailed
                    ? 'bg-rose-950/30 border-rose-800/60'
                    : 'bg-surface-dark/10 border-surface-border/30 opacity-60'
                }`}
              >
                <div
                  className={`w-8 h-8 rounded-xl flex items-center justify-center flex-shrink-0 mt-0.5 border ${
                    isDone
                      ? 'bg-emerald-950/60 border-emerald-800 text-emerald-400'
                      : isRunning
                      ? 'bg-brand-500/20 border-brand-400 text-brand-300'
                      : isFailed
                      ? 'bg-rose-950/60 border-rose-800 text-rose-400'
                      : 'bg-surface-dark border-surface-border text-slate-500'
                  }`}
                >
                  {isDone ? (
                    <CheckCircle2 className="w-4 h-4 text-emerald-400" />
                  ) : isRunning ? (
                    <Loader2 className="w-4 h-4 animate-spin text-brand-400" />
                  ) : isFailed ? (
                    <AlertCircle className="w-4 h-4 text-rose-400" />
                  ) : (
                    <Icon className="w-4 h-4" />
                  )}
                </div>

                <div className="min-w-0 flex-1">
                  <div className="flex items-center justify-between">
                    <span
                      className={`text-xs font-semibold ${
                        isRunning
                          ? 'text-brand-300 font-bold'
                          : isDone
                          ? 'text-slate-200'
                          : isFailed
                          ? 'text-rose-300'
                          : 'text-slate-400'
                      }`}
                    >
                      {idx + 1}. {stage.label}
                    </span>
                    <span className="text-[10px] font-mono uppercase tracking-wider text-slate-400">
                      {stage.status.replace('_', ' ')}
                    </span>
                  </div>
                  <p className="text-[11px] text-slate-400 mt-0.5 leading-relaxed">
                    {stage.description}
                  </p>
                </div>
              </div>
            );
          })}
        </div>

        {/* Error notice if failed */}
        {error && (
          <div className="mx-6 mb-4 p-4 rounded-2xl bg-rose-950/60 border border-rose-800 text-xs text-rose-200 flex items-start space-x-3">
            <AlertCircle className="w-4 h-4 text-rose-400 flex-shrink-0 mt-0.5" />
            <div>
              <div className="font-semibold text-rose-100">Analysis Error</div>
              <div className="mt-1">{error}</div>
            </div>
          </div>
        )}

        {/* Footer actions */}
        <div className="px-6 py-4 border-t border-surface-border/60 bg-surface-dark/30 flex items-center justify-between">
          <div className="text-xs text-slate-400 font-mono">
            {isComplete
              ? '✨ Codebase indexing and architectural analysis ready.'
              : error
              ? '❌ Analysis process halted.'
              : '⚡ Analyzing repository symbols and syntax...'}
          </div>

          <div className="flex items-center space-x-3">
            {error && onClose && (
              <button
                onClick={onClose}
                className="px-4 py-2 rounded-xl text-xs font-semibold bg-surface-dark hover:bg-surface-border text-slate-200 border border-surface-border transition-colors cursor-pointer"
              >
                Dismiss
              </button>
            )}

            {isComplete && onViewResults && (
              <button
                onClick={onViewResults}
                className="px-5 py-2 rounded-xl text-xs font-bold bg-brand-500 hover:bg-brand-400 text-surface-darkest flex items-center space-x-2 transition-all cursor-pointer shadow-lg shadow-brand-500/20"
              >
                <span>Explore Codebase & Summary</span>
                <Sparkles className="w-3.5 h-3.5" />
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};
