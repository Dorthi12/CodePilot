import React, { useState } from 'react';
import { GitHubRepoPickerItem } from '../types/repository';
import { 
  GitBranch, 
  Star, 
  GitFork, 
  Lock, 
  Globe, 
  ExternalLink, 
  Plus, 
  Check, 
  Loader2,
  FolderGit2
} from 'lucide-react';

interface GitHubRepoPickerCardProps {
  repo: GitHubRepoPickerItem;
  onImport: (repoUrl: string) => Promise<void>;
}

export const GitHubRepoPickerCard: React.FC<GitHubRepoPickerCardProps> = ({ repo, onImport }) => {
  const [isImporting, setIsImporting] = useState(false);

  const handleImport = async () => {
    if (repo.is_imported || isImporting) return;
    setIsImporting(true);
    try {
      await onImport(repo.html_url);
    } finally {
      setIsImporting(false);
    }
  };

  return (
    <div className="bg-surface-darker/70 border border-surface-border/60 hover:border-surface-border rounded-2xl p-4.5 transition-all duration-150 flex flex-col justify-between">
      <div>
        <div className="flex items-start justify-between gap-3 mb-2">
          <div className="flex items-center space-x-2.5 min-w-0">
            <div className="w-8 h-8 rounded-xl bg-surface-dark border border-surface-border flex items-center justify-center flex-shrink-0 text-slate-400">
              <FolderGit2 className="w-4 h-4" />
            </div>
            <div className="min-w-0">
              <h4 className="text-sm font-semibold text-slate-200 truncate">
                {repo.name}
              </h4>
              <p className="text-[11px] font-mono text-slate-400 truncate">
                {repo.owner}
              </p>
            </div>
          </div>

          <div className="flex items-center space-x-1.5 flex-shrink-0">
            <span
              className={`inline-flex items-center space-x-1 text-[10px] font-medium font-mono px-2 py-0.5 rounded-full border ${
                repo.private
                  ? 'bg-amber-950/50 text-amber-300 border-amber-800/50'
                  : 'bg-emerald-950/50 text-emerald-300 border-emerald-800/50'
              }`}
            >
              {repo.private ? <Lock className="w-2.5 h-2.5" /> : <Globe className="w-2.5 h-2.5" />}
              <span>{repo.visibility}</span>
            </span>

            <a
              href={repo.html_url}
              target="_blank"
              rel="noopener noreferrer"
              className="p-1 text-slate-400 hover:text-slate-200 transition-colors"
              title="Open on GitHub"
            >
              <ExternalLink className="w-3.5 h-3.5" />
            </a>
          </div>
        </div>

        <p className="text-xs text-slate-400 line-clamp-2 min-h-[2rem] mb-3 leading-relaxed">
          {repo.description || 'No description provided.'}
        </p>

        <div className="flex items-center flex-wrap gap-x-3.5 gap-y-1 text-[11px] text-slate-400 border-t border-surface-border/30 pt-2.5 mb-3">
          {repo.language && (
            <div className="flex items-center space-x-1">
              <span className="w-1.5 h-1.5 rounded-full bg-brand-400"></span>
              <span className="text-slate-300">{repo.language}</span>
            </div>
          )}

          <div className="flex items-center space-x-1 text-slate-400">
            <GitBranch className="w-3 h-3 text-slate-400" />
            <span className="font-mono text-[10px]">{repo.default_branch}</span>
          </div>

          <div className="flex items-center space-x-1 text-slate-400">
            <Star className="w-3 h-3 text-amber-400/80" />
            <span>{repo.stargazers_count.toLocaleString()}</span>
          </div>

          <div className="flex items-center space-x-1 text-slate-400">
            <GitFork className="w-3 h-3 text-slate-400" />
            <span>{repo.forks_count.toLocaleString()}</span>
          </div>
        </div>
      </div>

      <div className="pt-2 border-t border-surface-border/40 flex justify-end">
        {repo.is_imported ? (
          <span className="inline-flex items-center space-x-1.5 px-3 py-1.5 rounded-xl text-xs font-semibold bg-emerald-950/40 text-emerald-400 border border-emerald-800/50">
            <Check className="w-3.5 h-3.5" />
            <span>Imported to CodePilot</span>
          </span>
        ) : (
          <button
            onClick={handleImport}
            disabled={isImporting}
            className="inline-flex items-center space-x-1.5 px-3.5 py-1.5 rounded-xl text-xs font-semibold text-slate-100 bg-surface-dark hover:bg-brand-500 hover:text-surface-darkest border border-surface-border hover:border-brand-400 transition-all cursor-pointer disabled:opacity-50"
          >
            {isImporting ? (
              <>
                <Loader2 className="w-3.5 h-3.5 animate-spin" />
                <span>Starting Ingestion...</span>
              </>
            ) : (
              <>
                <Plus className="w-3.5 h-3.5" />
                <span>Start Ingestion</span>
              </>
            )}
          </button>
        )}
      </div>
    </div>
  );
};
