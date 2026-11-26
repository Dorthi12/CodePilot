import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Repository } from '../types/repository';
import { 
  GitBranch, 
  Star, 
  GitFork, 
  Lock, 
  Globe, 
  ExternalLink, 
  Sparkles, 
  CheckCircle2, 
  Loader2,
  FolderGit2,
  Trash2,
  X,
  ShieldCheck
} from 'lucide-react';

interface RepositoryCardProps {
  repository: Repository;
  onAnalyze: (repoId: string) => Promise<void>;
  onDelete?: (repoId: string) => Promise<void>;
}

export const RepositoryCard: React.FC<RepositoryCardProps> = ({ repository, onAnalyze, onDelete }) => {
  const navigate = useNavigate();
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [isDeleteModalOpen, setIsDeleteModalOpen] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);
  const [deleteError, setDeleteError] = useState<string | null>(null);

  const handleCardClick = (e: React.MouseEvent) => {
    // Prevent triggering if clicked on external link or action button
    if ((e.target as HTMLElement).closest('a, button')) return;
    navigate(`/repositories/${repository.id}`);
  };

  const handleDeleteClick = (e: React.MouseEvent) => {
    e.stopPropagation();
    setDeleteError(null);
    setIsDeleteModalOpen(true);
  };

  const handleConfirmDelete = async () => {
    if (!onDelete) return;
    setIsDeleting(true);
    setDeleteError(null);
    try {
      await onDelete(repository.id);
      setIsDeleteModalOpen(false);
    } catch (err: any) {
      setDeleteError(err.response?.data?.error?.message || 'Failed to delete repository.');
    } finally {
      setIsDeleting(false);
    }
  };

  const handleActionClick = async (e: React.MouseEvent) => {
    e.stopPropagation();
    if (repository.analysis_status === 'READY') {
      navigate(`/repositories/${repository.id}`);
    } else {
      setIsAnalyzing(true);
      try {
        await onAnalyze(repository.id);
      } finally {
        setIsAnalyzing(false);
      }
    }
  };

  const isPrivate = repository.visibility === 'PRIVATE';
  const isReady = repository.analysis_status === 'READY';

  return (
    <div 
      onClick={handleCardClick}
      className="bg-surface-darker/90 border border-surface-border/70 hover:border-brand-500/50 rounded-2xl p-5 shadow-lg hover:shadow-xl transition-all duration-200 flex flex-col justify-between group cursor-pointer"
    >
      <div>
        {/* Header: Name, Visibility Badge, GitHub Link */}
        <div className="flex items-start justify-between gap-3 mb-2.5">
          <div className="flex items-center space-x-2.5 min-w-0">
            <div className="w-9 h-9 rounded-xl bg-surface-dark border border-surface-border flex items-center justify-center flex-shrink-0 text-brand-400 group-hover:text-brand-300">
              <FolderGit2 className="w-4 h-4" />
            </div>
            <div className="min-w-0">
              <h3 className="text-sm font-semibold text-slate-100 truncate group-hover:text-brand-300 transition-colors">
                {repository.name}
              </h3>
              <p className="text-[11px] font-mono text-slate-400 truncate">
                {repository.owner}
              </p>
            </div>
          </div>

          <div className="flex items-center space-x-1.5 flex-shrink-0">
            <span
              className={`inline-flex items-center space-x-1 text-[10px] font-medium font-mono px-2 py-0.5 rounded-full border ${
                isPrivate
                  ? 'bg-amber-950/60 text-amber-300 border-amber-800/60'
                  : 'bg-emerald-950/60 text-emerald-300 border-emerald-800/60'
              }`}
            >
              {isPrivate ? <Lock className="w-2.5 h-2.5" /> : <Globe className="w-2.5 h-2.5" />}
              <span>{repository.visibility}</span>
            </span>

            <a
              href={repository.canonical_url}
              target="_blank"
              rel="noopener noreferrer"
              onClick={e => e.stopPropagation()}
              className="p-1.5 rounded-lg text-slate-400 hover:text-slate-200 hover:bg-surface-dark transition-colors"
              title="Open on GitHub"
            >
              <ExternalLink className="w-3.5 h-3.5" />
            </a>

            {onDelete && (
              <button
                type="button"
                onClick={handleDeleteClick}
                className="p-1.5 rounded-lg text-slate-500 hover:text-rose-400 hover:bg-rose-500/10 transition-colors cursor-pointer"
                title="Delete repository from CodePilot"
              >
                <Trash2 className="w-3.5 h-3.5" />
              </button>
            )}
          </div>
        </div>

        {/* Description */}
        <p className="text-xs text-slate-400 line-clamp-2 min-h-[2rem] mb-4 leading-relaxed">
          {repository.description || 'No description provided by repository owner.'}
        </p>

        {/* Metadata stats */}
        <div className="flex items-center flex-wrap gap-x-4 gap-y-1.5 text-[11px] text-slate-400 border-t border-surface-border/40 pt-3 mb-4">
          {repository.language && (
            <div className="flex items-center space-x-1.5">
              <span className="w-2 h-2 rounded-full bg-brand-400"></span>
              <span className="font-medium text-slate-300">{repository.language}</span>
            </div>
          )}

          <div className="flex items-center space-x-1 text-slate-400" title="Tracked Branch">
            <GitBranch className="w-3 h-3 text-slate-400" />
            <span className="font-mono text-[10px]">{repository.tracked_branch}</span>
          </div>

          <div className="flex items-center space-x-1 text-slate-400" title="Stars">
            <Star className="w-3 h-3 text-amber-400/80" />
            <span>{repository.stargazers_count.toLocaleString()}</span>
          </div>

          <div className="flex items-center space-x-1 text-slate-400" title="Forks">
            <GitFork className="w-3 h-3 text-slate-400" />
            <span>{repository.forks_count.toLocaleString()}</span>
          </div>
        </div>
      </div>

      {/* Footer: Analysis Status and Action Button */}
      <div className="flex items-center justify-between border-t border-surface-border/50 pt-3">
        <div>
          {isReady ? (
            <span className="inline-flex items-center space-x-1 text-[11px] font-medium text-emerald-400">
              <CheckCircle2 className="w-3.5 h-3.5" />
              <span>Workspace Ready</span>
            </span>
          ) : repository.analysis_status === 'ANALYZING' ? (
            <span className="inline-flex items-center space-x-1 text-[11px] font-medium text-brand-400">
              <Loader2 className="w-3.5 h-3.5 animate-spin" />
              <span>Ingesting...</span>
            </span>
          ) : (
            <span className="text-[11px] font-medium text-slate-400">
              Ready to Ingest
            </span>
          )}
        </div>

        <button
          onClick={handleActionClick}
          disabled={isAnalyzing}
          className={`px-3 py-1.5 rounded-xl text-xs font-semibold flex items-center space-x-1.5 transition-all cursor-pointer ${
            isReady
              ? 'bg-brand-500 hover:bg-brand-400 text-surface-darkest font-bold shadow-md shadow-brand-500/20'
              : 'bg-brand-500 hover:bg-brand-400 text-surface-darkest font-bold shadow-md shadow-brand-500/20'
          } disabled:opacity-50`}
        >
          {isAnalyzing ? (
            <>
              <Loader2 className="w-3.5 h-3.5 animate-spin" />
              <span>Opening...</span>
            </>
          ) : isReady ? (
            <>
              <Sparkles className="w-3.5 h-3.5" />
              <span>Explore Codebase</span>
            </>
          ) : (
            <>
              <Sparkles className="w-3.5 h-3.5" />
              <span>Start Ingestion</span>
            </>
          )}
        </button>
      </div>

      {/* Delete Confirmation Modal */}
      {isDeleteModalOpen && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm animate-in fade-in duration-200"
          onClick={e => e.stopPropagation()}
        >
          <div className="bg-surface-darker border border-surface-border rounded-3xl w-full max-w-md shadow-2xl overflow-hidden p-6 space-y-4">
            <div className="flex items-start justify-between">
              <div className="flex items-center space-x-3">
                <div className="w-10 h-10 rounded-2xl bg-rose-500/10 border border-rose-500/30 flex items-center justify-center text-rose-400 flex-shrink-0">
                  <Trash2 className="w-5 h-5" />
                </div>
                <div>
                  <h3 className="text-sm font-semibold text-slate-100">
                    Delete from CodePilot
                  </h3>
                  <p className="text-xs font-mono text-slate-400 mt-0.5">
                    {repository.owner}/{repository.name}
                  </p>
                </div>
              </div>

              <button
                type="button"
                onClick={() => setIsDeleteModalOpen(false)}
                disabled={isDeleting}
                className="p-1.5 rounded-xl text-slate-400 hover:text-slate-200 hover:bg-surface-dark transition-colors cursor-pointer"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <div className="space-y-3 text-xs text-slate-300 leading-relaxed">
              <p>
                Are you sure you want to delete this repository from CodePilot?
              </p>
              <div className="bg-surface-dark/80 rounded-xl p-3 border border-surface-border/60 space-y-1.5 text-[11px] text-slate-400 font-mono">
                <div className="text-slate-300 font-semibold mb-1">This will permanently delete:</div>
                <div>• Local cloned workspace directory and source files</div>
                <div>• AST symbols, code chunks, and imports</div>
                <div>• On-demand summaries and analysis snapshots</div>
              </div>

              <div className="flex items-start space-x-2 bg-emerald-950/30 border border-emerald-800/40 rounded-xl p-3 text-[11px] text-emerald-300">
                <ShieldCheck className="w-4 h-4 text-emerald-400 flex-shrink-0 mt-0.5" />
                <span>
                  <strong>GitHub Protected:</strong> This action will <strong>never</strong> delete or modify the original repository on GitHub.
                </span>
              </div>

              {deleteError && (
                <div className="p-2.5 rounded-xl bg-rose-950/40 border border-rose-800/60 text-xs text-rose-300">
                  {deleteError}
                </div>
              )}
            </div>

            <div className="flex items-center justify-end space-x-3 pt-2 border-t border-surface-border/50">
              <button
                type="button"
                onClick={() => setIsDeleteModalOpen(false)}
                disabled={isDeleting}
                className="px-4 py-2 rounded-xl text-xs font-semibold bg-surface-dark hover:bg-surface-border text-slate-300 transition-colors cursor-pointer disabled:opacity-50"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={handleConfirmDelete}
                disabled={isDeleting}
                className="px-4 py-2 rounded-xl text-xs font-bold bg-rose-600 hover:bg-rose-500 text-white flex items-center space-x-1.5 transition-colors cursor-pointer shadow-lg shadow-rose-600/20 disabled:opacity-50"
              >
                {isDeleting ? (
                  <>
                    <Loader2 className="w-3.5 h-3.5 animate-spin" />
                    <span>Deleting...</span>
                  </>
                ) : (
                  <>
                    <Trash2 className="w-3.5 h-3.5" />
                    <span>Delete Repository</span>
                  </>
                )}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
