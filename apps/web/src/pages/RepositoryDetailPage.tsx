import React, { useEffect, useState, useCallback } from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';
import { Navbar } from '../components/Navbar';
import { repositoryService } from '../services/repositoryService';
import { RepositoryProcessingStatus } from '../components/RepositoryProcessingStatus';
import { CodebaseExplorer } from '../components/CodebaseExplorer';
import { FileSummariesView } from '../components/FileSummariesView';
import {
  Repository,
  RepositoryOverviewResponse
} from '../types/repository';
import {
  FolderGit2,
  GitBranch,
  Globe,
  Lock,
  ExternalLink,
  Calendar,
  Layers,
  Code2,
  FileText,
  ChevronRight,
  ArrowLeft,
  Loader2,
  AlertCircle,
  Database,
  Hash
} from 'lucide-react';

type TabType = 'overview' | 'explorer' | 'summaries';

export const RepositoryDetailPage: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();

  const [activeTab, setActiveTab] = useState<TabType>('overview');
  const [repository, setRepository] = useState<Repository | null>(null);
  const [overview, setOverview] = useState<RepositoryOverviewResponse | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  // Selected file to open directly in Code Explorer (e.g. from File Summaries)
  const [selectedFileForExplorer, setSelectedFileForExplorer] = useState<string | undefined>(undefined);

  const fetchRepoData = useCallback(async () => {
    if (!id) return;
    try {
      const [repoData, overviewData] = await Promise.all([
        repositoryService.getRepository(id),
        repositoryService.getOverview(id).catch(() => null)
      ]);
      setRepository(repoData);
      setOverview(overviewData);
    } catch (err: any) {
      setError(err.response?.data?.error?.message || 'Repository not found or access denied.');
    } finally {
      setLoading(false);
    }
  }, [id]);

  useEffect(() => {
    fetchRepoData();
  }, [fetchRepoData]);

  const handleOpenFileInExplorer = (filePath: string) => {
    setSelectedFileForExplorer(filePath);
    setActiveTab('explorer');
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-surface-darkest text-slate-100 flex flex-col">
        <Navbar />
        <div className="flex-1 flex flex-col items-center justify-center space-y-3">
          <Loader2 className="w-8 h-8 animate-spin text-brand-400" />
          <span className="text-sm text-slate-400 font-mono">Loading repository data...</span>
        </div>
      </div>
    );
  }

  if (error || !repository) {
    return (
      <div className="min-h-screen bg-surface-darkest text-slate-100 flex flex-col">
        <Navbar />
        <div className="flex-1 max-w-2xl mx-auto w-full px-4 py-16 flex flex-col items-center justify-center text-center space-y-4">
          <div className="w-12 h-12 rounded-2xl bg-rose-950/40 border border-rose-800/60 flex items-center justify-center text-rose-400">
            <AlertCircle className="w-6 h-6" />
          </div>
          <h2 className="text-xl font-bold text-slate-100">Unable to Load Repository</h2>
          <p className="text-sm text-slate-400 max-w-md">{error || 'The requested repository could not be found.'}</p>
          <button
            onClick={() => navigate('/dashboard')}
            className="px-4 py-2 rounded-xl bg-surface-dark border border-surface-border hover:border-brand-500/50 text-slate-200 text-xs font-semibold flex items-center space-x-2 transition-colors cursor-pointer"
          >
            <ArrowLeft className="w-3.5 h-3.5" />
            <span>Return to Dashboard</span>
          </button>
        </div>
      </div>
    );
  }

  const isPrivate = repository.visibility === 'PRIVATE';

  const lastAnalyzed = overview?.last_analyzed_at
    ? new Date(overview.last_analyzed_at).toLocaleString('en-US', {
        month: 'short',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit'
      })
    : null;

  return (
    <div className="min-h-screen bg-surface-darkest text-slate-100 flex flex-col">
      <Navbar />

      <main className="flex-1 max-w-7xl mx-auto w-full px-4 sm:px-6 lg:px-8 py-6 space-y-6">
        {/* Breadcrumb Navigation */}
        <div className="flex items-center space-x-2 text-xs font-mono text-slate-400">
          <Link to="/dashboard" className="hover:text-brand-300 transition-colors flex items-center space-x-1">
            <span>Dashboard</span>
          </Link>
          <ChevronRight className="w-3 h-3 text-slate-600" />
          <span className="text-slate-500">{repository.owner}</span>
          <ChevronRight className="w-3 h-3 text-slate-600" />
          <span className="text-brand-300 font-semibold">{repository.name}</span>
        </div>

        {/* Repository Header Card */}
        <div className="bg-surface-darker/90 border border-surface-border/70 rounded-2xl p-6 shadow-xl relative overflow-hidden">
          <div className="absolute top-0 right-0 w-96 h-96 bg-brand-500/5 rounded-full blur-3xl pointer-events-none" />

          <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-6 relative">
            {/* Title & Info */}
            <div className="space-y-3">
              <div className="flex items-center space-x-3">
                <div className="w-11 h-11 rounded-2xl bg-surface-dark border border-surface-border flex items-center justify-center text-brand-400 shadow-md">
                  <FolderGit2 className="w-5 h-5" />
                </div>
                <div>
                  <div className="flex items-center space-x-2.5">
                    <h1 className="text-xl sm:text-2xl font-bold text-slate-100">
                      {repository.name}
                    </h1>
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
                  </div>
                  <p className="text-xs text-slate-400 font-mono mt-0.5">
                    {repository.owner}
                  </p>
                </div>
              </div>

              {repository.description && (
                <p className="text-xs text-slate-300 max-w-2xl leading-relaxed">
                  {repository.description}
                </p>
              )}

              {/* Badges row */}
              <div className="flex flex-wrap items-center gap-x-4 gap-y-2 text-xs text-slate-400 font-mono pt-1">
                <div className="flex items-center space-x-1.5" title="Tracked branch">
                  <GitBranch className="w-3.5 h-3.5 text-brand-400" />
                  <span>{overview?.branch || repository.tracked_branch || repository.default_branch}</span>
                </div>

                {overview?.commit_sha && (
                  <div className="flex items-center space-x-1 px-2 py-0.5 rounded-lg bg-surface-dark border border-surface-border/50 text-slate-300">
                    <Hash className="w-3 h-3 text-slate-500" />
                    <span className="font-mono text-[11px]">{overview.commit_sha.substring(0, 7)}</span>
                  </div>
                )}

                {repository.language && (
                  <div className="flex items-center space-x-1.5">
                    <span className="w-2 h-2 rounded-full bg-brand-400" />
                    <span>{repository.language}</span>
                  </div>
                )}

                {lastAnalyzed && (
                  <div className="flex items-center space-x-1.5 text-slate-500">
                    <Calendar className="w-3.5 h-3.5" />
                    <span>Analyzed {lastAnalyzed}</span>
                  </div>
                )}

                <a
                  href={repository.canonical_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="flex items-center space-x-1 text-slate-400 hover:text-brand-300 transition-colors"
                >
                  <span>GitHub</span>
                  <ExternalLink className="w-3 h-3" />
                </a>
              </div>
            </div>

            {/* Quick Stats Grid */}
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
              <div className="bg-surface-dark/70 border border-surface-border/50 rounded-xl p-3 min-w-[100px] text-center">
                <div className="text-[10px] font-mono uppercase text-slate-400 font-medium">Files</div>
                <div className="text-lg font-bold font-mono text-slate-100 mt-0.5">
                  {(overview?.total_files || 0).toLocaleString()}
                </div>
              </div>

              <div className="bg-surface-dark/70 border border-surface-border/50 rounded-xl p-3 min-w-[100px] text-center">
                <div className="text-[10px] font-mono uppercase text-slate-400 font-medium">Lines</div>
                <div className="text-lg font-bold font-mono text-brand-300 mt-0.5">
                  {(overview?.total_lines || 0).toLocaleString()}
                </div>
              </div>

              <div className="bg-surface-dark/70 border border-surface-border/50 rounded-xl p-3 min-w-[100px] text-center">
                <div className="text-[10px] font-mono uppercase text-slate-400 font-medium">Symbols</div>
                <div className="text-lg font-bold font-mono text-purple-300 mt-0.5">
                  {(overview?.total_symbols || 0).toLocaleString()}
                </div>
              </div>

              <div className="bg-surface-dark/70 border border-surface-border/50 rounded-xl p-3 min-w-[100px] text-center">
                <div className="text-[10px] font-mono uppercase text-slate-400 font-medium">Chunks</div>
                <div className="text-lg font-bold font-mono text-emerald-300 mt-0.5">
                  {(overview?.total_chunks || 0).toLocaleString()}
                </div>
              </div>
            </div>
          </div>

          {/* Navigation Tabs Header */}
          <div className="flex items-center space-x-2 border-t border-surface-border/50 mt-6 pt-4">
            <button
              onClick={() => setActiveTab('overview')}
              className={`px-4 py-2 rounded-xl text-xs font-semibold flex items-center space-x-2 cursor-pointer transition-all ${
                activeTab === 'overview'
                  ? 'bg-brand-500 text-surface-darkest font-bold shadow-md shadow-brand-500/20'
                  : 'text-slate-400 hover:text-slate-200 hover:bg-surface-dark'
              }`}
            >
              <Layers className="w-3.5 h-3.5" />
              <span>Overview</span>
            </button>

            <button
              onClick={() => setActiveTab('explorer')}
              className={`px-4 py-2 rounded-xl text-xs font-semibold flex items-center space-x-2 cursor-pointer transition-all ${
                activeTab === 'explorer'
                  ? 'bg-brand-500 text-surface-darkest font-bold shadow-md shadow-brand-500/20'
                  : 'text-slate-400 hover:text-slate-200 hover:bg-surface-dark'
              }`}
            >
              <Code2 className="w-3.5 h-3.5" />
              <span>Code Explorer</span>
              {overview?.total_files ? (
                <span className={`text-[10px] font-mono px-1.5 py-0.2 rounded-full ${
                  activeTab === 'explorer' ? 'bg-surface-darkest/20 text-surface-darkest' : 'bg-surface-dark text-slate-400'
                }`}>
                  {overview.total_files}
                </span>
              ) : null}
            </button>

            <button
              onClick={() => setActiveTab('summaries')}
              className={`px-4 py-2 rounded-xl text-xs font-semibold flex items-center space-x-2 cursor-pointer transition-all ${
                activeTab === 'summaries'
                  ? 'bg-brand-500 text-surface-darkest font-bold shadow-md shadow-brand-500/20'
                  : 'text-slate-400 hover:text-slate-200 hover:bg-surface-dark'
              }`}
            >
              <FileText className="w-3.5 h-3.5" />
              <span>File Summaries</span>
            </button>
          </div>
        </div>

        {/* Tab 1: Overview */}
        {activeTab === 'overview' && (
          <div className="space-y-6">
            {/* Real-time Processing Pipeline Card */}
            <RepositoryProcessingStatus
              repository={repository}
              onRefreshRepo={fetchRepoData}
              onExploreClick={() => setActiveTab('explorer')}
            />

            {/* Language Breakdown & Architecture Card */}
            {overview && Object.keys(overview.languages).length > 0 && (
              <div className="bg-surface-darker/90 border border-surface-border/70 rounded-2xl p-6 shadow-xl space-y-4">
                <div className="flex items-center justify-between pb-3 border-b border-surface-border/50">
                  <h3 className="text-sm font-semibold text-slate-200 flex items-center space-x-2">
                    <Database className="w-4 h-4 text-brand-400" />
                    <span>Language Distribution</span>
                  </h3>
                  <span className="text-xs text-slate-400 font-mono">
                    {Object.keys(overview.languages).length} detected languages
                  </span>
                </div>

                {/* Progress bar across languages */}
                <div className="w-full h-3 bg-surface-dark rounded-full overflow-hidden flex border border-surface-border/50">
                  {Object.entries(overview.languages).map(([lang, count], i) => {
                    const total = Object.values(overview.languages).reduce((a, b) => a + b, 0);
                    const pct = total > 0 ? (count / total) * 100 : 0;
                    const colors = [
                      'bg-blue-500',
                      'bg-sky-400',
                      'bg-amber-400',
                      'bg-purple-500',
                      'bg-emerald-400',
                      'bg-pink-400',
                      'bg-orange-400'
                    ];
                    return (
                      <div
                        key={lang}
                        style={{ width: `${pct}%` }}
                        className={`${colors[i % colors.length]} transition-all`}
                        title={`${lang}: ${count} files (${pct.toFixed(1)}%)`}
                      />
                    );
                  })}
                </div>

                {/* Legend Chips */}
                <div className="flex flex-wrap gap-2.5 pt-1">
                  {Object.entries(overview.languages).map(([lang, count], i) => {
                    const total = Object.values(overview.languages).reduce((a, b) => a + b, 0);
                    const pct = total > 0 ? ((count / total) * 100).toFixed(1) : 0;
                    const dotColors = [
                      'bg-blue-400',
                      'bg-sky-400',
                      'bg-amber-400',
                      'bg-purple-400',
                      'bg-emerald-400',
                      'bg-pink-400',
                      'bg-orange-400'
                    ];
                    return (
                      <div
                        key={lang}
                        className="flex items-center space-x-2 bg-surface-dark/70 border border-surface-border/40 px-3 py-1.5 rounded-xl text-xs font-mono"
                      >
                        <span className={`w-2 h-2 rounded-full ${dotColors[i % dotColors.length]}`} />
                        <span className="text-slate-200 capitalize font-medium">{lang}</span>
                        <span className="text-slate-500">
                          {count} ({pct}%)
                        </span>
                      </div>
                    );
                  })}
                </div>
              </div>
            )}
          </div>
        )}

        {/* Tab 2: Code Explorer */}
        {activeTab === 'explorer' && (
          <CodebaseExplorer
            repositoryId={repository.id}
            initialFilePath={selectedFileForExplorer}
            onFileSelect={path => setSelectedFileForExplorer(path)}
          />
        )}

        {/* Tab 3: File Summaries */}
        {activeTab === 'summaries' && (
          <FileSummariesView
            repositoryId={repository.id}
            onSelectFile={handleOpenFileInExplorer}
          />
        )}
      </main>
    </div>
  );
};
