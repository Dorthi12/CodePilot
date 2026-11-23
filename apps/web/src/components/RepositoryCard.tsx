import React, { useState } from 'react';
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
  Search,
  BookOpen,
  Layers
} from 'lucide-react';

interface RepositoryCardProps {
  repository: Repository;
  onAnalyze: (repoId: string) => Promise<void>;
  onOpenSearch?: (repository: Repository) => void;
  onOpenExplain?: (repository: Repository) => void;
  onOpenExplorer?: (repository: Repository) => void;
}

export const RepositoryCard: React.FC<RepositoryCardProps> = ({
  repository,
  onAnalyze,
  onOpenSearch,
  onOpenExplain,
  onOpenExplorer,
}) => {
  const [isAnalyzing, setIsAnalyzing] = useState(false);

  const handleAnalyzeClick = async () => {
    setIsAnalyzing(true);
    try {
      await onAnalyze(repository.id);
    } finally {
      setIsAnalyzing(false);
    }
  };

  const isPrivate = repository.visibility === 'PRIVATE';
  const isReady = repository.analysis_status === 'READY';

  return (
    <div className="bg-surface-darker/90 border border-surface-border/70 hover:border-brand-500/50 rounded-2xl p-5 shadow-lg transition-all duration-200 flex flex-col justify-between group">
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
              className="p-1.5 rounded-lg text-slate-400 hover:text-slate-200 hover:bg-surface-dark transition-colors"
              title="Open on GitHub"
            >
              <ExternalLink className="w-3.5 h-3.5" />
            </a>
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
      <div className="flex items-center justify-between border-t border-surface-border/50 pt-3 gap-2 flex-wrap">
        <div>
          {isReady ? (
            <span className="inline-flex items-center space-x-1 text-[11px] font-medium text-emerald-400">
              <CheckCircle2 className="w-3.5 h-3.5" />
              <span>Analyzed & Ready</span>
            </span>
          ) : (
            <span className="text-[11px] font-medium text-slate-400">
              Ready for Athena
            </span>
          )}
        </div>

        <div className="flex items-center space-x-1.5">
          {isReady && onOpenExplorer && (
            <button
              onClick={() => onOpenExplorer(repository)}
              className="px-2.5 py-1.5 rounded-xl text-xs font-semibold flex items-center space-x-1 bg-brand-500/10 hover:bg-brand-500/20 text-brand-300 border border-brand-500/30 transition-all cursor-pointer"
              title="Explore Codebase & Project Summary"
            >
              <Layers className="w-3.5 h-3.5 text-brand-400" />
              <span>Explore Code</span>
            </button>
          )}

          {isReady && onOpenSearch && (
            <button
              onClick={() => onOpenSearch(repository)}
              className="px-2.5 py-1.5 rounded-xl text-xs font-semibold flex items-center space-x-1 bg-surface-dark hover:bg-surface-border/60 text-slate-200 border border-surface-border transition-all cursor-pointer"
              title="Search code symbols"
            >
              <Search className="w-3.5 h-3.5 text-brand-400" />
              <span>Search</span>
            </button>
          )}

          {isReady && onOpenExplain && (
            <button
              onClick={() => onOpenExplain(repository)}
              className="px-2.5 py-1.5 rounded-xl text-xs font-semibold flex items-center space-x-1 bg-surface-dark hover:bg-surface-border/60 text-slate-200 border border-surface-border transition-all cursor-pointer"
              title="Explain code with AI"
            >
              <BookOpen className="w-3.5 h-3.5 text-brand-400" />
              <span>Explain</span>
            </button>
          )}

          <button
            onClick={handleAnalyzeClick}
            disabled={isAnalyzing}
            className={`px-3 py-1.5 rounded-xl text-xs font-semibold flex items-center space-x-1.5 transition-all cursor-pointer ${
              isReady
                ? 'bg-brand-500/10 hover:bg-brand-500/20 text-brand-300 border border-brand-500/30'
                : 'bg-brand-500 hover:bg-brand-400 text-surface-darkest font-bold shadow-md shadow-brand-500/20'
            } disabled:opacity-50`}
          >
            {isAnalyzing ? (
              <>
                <Loader2 className="w-3.5 h-3.5 animate-spin" />
                <span>Queuing...</span>
              </>
            ) : (
              <>
                <Sparkles className="w-3.5 h-3.5" />
                <span>{isReady ? 'Re-Analyze' : 'Analyze Repository'}</span>
              </>
            )}
          </button>
        </div>
      </div>
    </div>
  );
};
