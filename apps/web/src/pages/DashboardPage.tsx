import React, { useEffect, useState, useCallback } from 'react';
import { useAuth } from '../context/AuthContext';
import { Navbar } from '../components/Navbar';
import { authService } from '../services/authService';
import { repositoryService } from '../services/repositoryService';
import { RepositoryCard } from '../components/RepositoryCard';
import { GitHubRepoPickerCard } from '../components/GitHubRepoPickerCard';
import { ImportByUrlCard } from '../components/ImportByUrlCard';
import { IngestionProgressModal } from '../components/IngestionProgressModal';
import { GitHubStatus } from '../types/auth';
import { Repository, GitHubRepoPickerItem } from '../types/repository';
import { 
  Github, 
  Search, 
  FolderGit2, 
  Link2, 
  CheckCircle2, 
  AlertCircle,
  Sparkles,
  ChevronLeft,
  ChevronRight,
  ShieldCheck,
  Key,
  Calendar,
  Mail,
  ExternalLink
} from 'lucide-react';

type TabType = 'imported' | 'my-repos' | 'import-url';

export const DashboardPage: React.FC = () => {
  const { user, logout } = useAuth();
  const [gitHubStatus, setGitHubStatus] = useState<GitHubStatus | null>(null);
  const [statusLoading, setStatusLoading] = useState<boolean>(true);

  // Active tab state
  const [activeTab, setActiveTab] = useState<TabType>('imported');

  // Imported repositories state
  const [importedRepos, setImportedRepos] = useState<Repository[]>([]);
  const [reposLoading, setReposLoading] = useState<boolean>(true);
  const [repoSearch, setRepoSearch] = useState<string>('');
  const [visibilityFilter, setVisibilityFilter] = useState<'ALL' | 'PUBLIC' | 'PRIVATE'>('ALL');

  // GitHub account picker state
  const [gitHubRepos, setGitHubRepos] = useState<GitHubRepoPickerItem[]>([]);
  const [selectedRepoForIngestion, setSelectedRepoForIngestion] = useState<Repository | null>(null);
  const [gitHubReposLoading, setGitHubReposLoading] = useState<boolean>(false);
  const [gitHubSearch, setGitHubSearch] = useState<string>('');
  const [gitHubPage, setGitHubPage] = useState<number>(1);
  const [hasMoreGitHub, setHasMoreGitHub] = useState<boolean>(false);

  // Notifications / feedback
  const [toast, setToast] = useState<{ type: 'success' | 'error'; message: string } | null>(null);

  const showToast = (type: 'success' | 'error', message: string) => {
    setToast({ type, message });
    setTimeout(() => {
      setToast(null);
    }, 5000);
  };

  // Load imported repositories
  const fetchImportedRepositories = useCallback(async () => {
    setReposLoading(true);
    try {
      const vis = visibilityFilter === 'ALL' ? undefined : visibilityFilter;
      const repos = await repositoryService.listRepositories(repoSearch || undefined, vis);
      setImportedRepos(repos);
    } catch (err) {
      console.error('Failed to load repositories', err);
    } finally {
      setReposLoading(false);
    }
  }, [repoSearch, visibilityFilter]);

  // Load GitHub account repositories for picker
  const fetchGitHubRepos = useCallback(async (page: number, search?: string) => {
    setGitHubReposLoading(true);
    try {
      const res = await repositoryService.listUserGitHubRepositories(page, 12, search || undefined);
      setGitHubRepos(res.repositories);
      setHasMoreGitHub(res.has_more);
      setGitHubPage(page);
    } catch (err) {
      console.error('Failed to load GitHub user repos', err);
    } finally {
      setGitHubReposLoading(false);
    }
  }, []);

  // Initial load
  useEffect(() => {
    let mounted = true;
    async function loadInitial() {
      try {
        const status = await authService.getGitHubStatus();
        if (mounted) setGitHubStatus(status);
      } catch (err) {
        console.error('Failed to load GitHub status', err);
      } finally {
        if (mounted) setStatusLoading(false);
      }
    }
    loadInitial();
    return () => { mounted = false; };
  }, []);

  // Fetch when tab changes or search/filter changes
  useEffect(() => {
    if (activeTab === 'imported') {
      fetchImportedRepositories();
    } else if (activeTab === 'my-repos') {
      fetchGitHubRepos(1, gitHubSearch);
    }
  }, [activeTab, fetchImportedRepositories, fetchGitHubRepos, gitHubSearch]);

  const handleImportSuccess = async (url: string, branch?: string) => {
    try {
      const repo = await repositoryService.importRepository({ url, branch });
      showToast('success', `Repository '${repo.owner}/${repo.name}' was imported successfully.`);
      setActiveTab('imported');
      await fetchImportedRepositories();
    } catch (err: unknown) {
      let msg = 'Failed to import repository.';
      if (err && typeof err === 'object' && 'response' in err) {
        const axErr = err as { response?: { data?: { error?: { message?: string } } } };
        msg = axErr.response?.data?.error?.message || msg;
      }
      showToast('error', msg);
      throw err;
    }
  };

  const handleAnalyze = async (repoId: string) => {
    const repo = importedRepos.find(r => r.id === repoId);
    if (repo) {
      setSelectedRepoForIngestion(repo);
    }
  };

  const handleDeleteRepository = async (repoId: string) => {
    const repoToDelete = importedRepos.find(r => r.id === repoId);
    const repoName = repoToDelete ? `${repoToDelete.owner}/${repoToDelete.name}` : 'Repository';
    try {
      await repositoryService.deleteRepository(repoId);
      setImportedRepos(prev => prev.filter(r => r.id !== repoId));
      showToast('success', `'${repoName}' was deleted from CodePilot.`);
    } catch (err: unknown) {
      let msg = 'Failed to delete repository.';
      if (err && typeof err === 'object' && 'response' in err) {
        const axErr = err as { response?: { data?: { error?: { message?: string } } } };
        msg = axErr.response?.data?.error?.message || msg;
      }
      showToast('error', msg);
      throw err;
    }
  };

  if (!user) return null;

  const formattedDate = user.created_at
    ? new Date(user.created_at).toLocaleDateString('en-US', {
        month: 'short',
        day: 'numeric',
        year: 'numeric',
      })
    : 'Recently';

  return (
    <div className="min-h-screen bg-surface-darkest flex flex-col">
      <Navbar />

      <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-8">
        
        {/* Toast / Notification Banner */}
        {toast && (
          <div
            className={`p-4 rounded-2xl border text-xs flex items-center justify-between shadow-xl transition-all duration-300 ${
              toast.type === 'success'
                ? 'bg-emerald-950/60 border-emerald-800 text-emerald-200'
                : 'bg-rose-950/60 border-rose-800 text-rose-200'
            }`}
          >
            <div className="flex items-center space-x-2.5">
              {toast.type === 'success' ? (
                <CheckCircle2 className="w-4 h-4 text-emerald-400" />
              ) : (
                <AlertCircle className="w-4 h-4 text-rose-400" />
              )}
              <span className="font-medium">{toast.message}</span>
            </div>
            <button
              onClick={() => setToast(null)}
              className="text-xs opacity-70 hover:opacity-100 font-mono ml-4"
            >
              ✕
            </button>
          </div>
        )}

        {/* Welcome & Session Banner */}
        <div className="bg-surface-darker border border-surface-border/80 rounded-3xl p-6 sm:p-8 relative overflow-hidden shadow-xl">
          <div className="absolute top-0 right-0 w-96 h-96 bg-brand-500/10 rounded-full blur-3xl pointer-events-none -z-0"></div>
          
          <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-6 relative z-10">
            <div className="flex items-center space-x-5">
              {user.avatar_url ? (
                <img
                  src={user.avatar_url}
                  alt={user.username}
                  className="w-16 h-16 rounded-2xl ring-2 ring-brand-500/40 object-cover shadow-lg"
                />
              ) : (
                <div className="w-16 h-16 rounded-2xl bg-surface-dark flex items-center justify-center border border-surface-border">
                  <Github className="w-8 h-8 text-slate-300" />
                </div>
              )}

              <div>
                <div className="flex items-center space-x-3">
                  <h1 className="text-2xl font-bold text-slate-100 tracking-tight">
                    Welcome, {user.name || user.username}
                  </h1>
                  <span className="px-2 py-0.5 rounded-full text-[11px] font-mono font-medium bg-emerald-950/80 text-emerald-300 border border-emerald-800">
                    AUTHENTICATED
                  </span>
                </div>
                <p className="text-sm font-mono text-slate-400 mt-1">
                  GitHub Profile: <span className="text-brand-300">@{user.username}</span> • {importedRepos.length} Repositories Imported
                </p>
              </div>
            </div>

            <button
              onClick={logout}
              className="px-4 py-2 rounded-xl text-xs font-semibold text-rose-300 bg-rose-950/30 hover:bg-rose-900/50 border border-rose-800/60 transition-colors shadow-sm cursor-pointer"
            >
              Sign Out
            </button>
          </div>
        </div>

        {/* Module 2: Repository Integration Section */}
        <div className="space-y-6">
          
          {/* Section Navigation Tabs */}
          <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 border-b border-surface-border/60 pb-3">
            <div className="flex items-center space-x-2 bg-surface-darker/90 p-1.5 rounded-2xl border border-surface-border/70">
              <button
                onClick={() => setActiveTab('imported')}
                className={`flex items-center space-x-2 px-4 py-2 rounded-xl text-xs font-semibold transition-all cursor-pointer ${
                  activeTab === 'imported'
                    ? 'bg-brand-500 text-surface-darkest font-bold shadow-md shadow-brand-500/20'
                    : 'text-slate-400 hover:text-slate-200 hover:bg-surface-dark'
                }`}
              >
                <FolderGit2 className="w-3.5 h-3.5" />
                <span>Imported Workspaces</span>
                <span className={`px-1.5 py-0.2 rounded-full text-[10px] font-mono ${
                  activeTab === 'imported' ? 'bg-surface-darkest/30 text-surface-darkest font-bold' : 'bg-surface-dark text-slate-400'
                }`}>
                  {importedRepos.length}
                </span>
              </button>

              <button
                onClick={() => setActiveTab('my-repos')}
                className={`flex items-center space-x-2 px-4 py-2 rounded-xl text-xs font-semibold transition-all cursor-pointer ${
                  activeTab === 'my-repos'
                    ? 'bg-brand-500 text-surface-darkest font-bold shadow-md shadow-brand-500/20'
                    : 'text-slate-400 hover:text-slate-200 hover:bg-surface-dark'
                }`}
              >
                <Github className="w-3.5 h-3.5" />
                <span>My Repositories</span>
              </button>

              <button
                onClick={() => setActiveTab('import-url')}
                className={`flex items-center space-x-2 px-4 py-2 rounded-xl text-xs font-semibold transition-all cursor-pointer ${
                  activeTab === 'import-url'
                    ? 'bg-brand-500 text-surface-darkest font-bold shadow-md shadow-brand-500/20'
                    : 'text-slate-400 hover:text-slate-200 hover:bg-surface-dark'
                }`}
              >
                <Link2 className="w-3.5 h-3.5" />
                <span>Import by URL</span>
              </button>
            </div>

            {/* Quick action button */}
            {activeTab === 'imported' && (
              <button
                onClick={() => setActiveTab('import-url')}
                className="inline-flex items-center space-x-1.5 px-3.5 py-2 rounded-xl text-xs font-semibold text-brand-300 bg-brand-500/10 hover:bg-brand-500/20 border border-brand-500/30 transition-all cursor-pointer"
              >
                <Sparkles className="w-3.5 h-3.5" />
                <span>Import New Repository</span>
              </button>
            )}
          </div>

          {/* TAB 1: IMPORTED REPOSITORIES */}
          {activeTab === 'imported' && (
            <div className="space-y-6">
              {/* Filter and Search Bar */}
              <div className="flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-3">
                <div className="relative flex-1 max-w-md">
                  <Search className="w-4 h-4 text-slate-400 absolute left-3.5 top-3 pointer-events-none" />
                  <input
                    type="text"
                    value={repoSearch}
                    onChange={(e) => setRepoSearch(e.target.value)}
                    placeholder="Search imported repositories..."
                    className="w-full pl-9 pr-4 py-2 bg-surface-darker/80 border border-surface-border rounded-xl text-xs text-slate-100 placeholder-slate-400 focus:outline-none focus:border-brand-400"
                  />
                </div>

                <div className="flex items-center space-x-1.5 bg-surface-darker/80 border border-surface-border p-1 rounded-xl">
                  {(['ALL', 'PUBLIC', 'PRIVATE'] as const).map((vis) => (
                    <button
                      key={vis}
                      onClick={() => setVisibilityFilter(vis)}
                      className={`px-3 py-1 rounded-lg text-xs font-mono font-medium transition-colors cursor-pointer ${
                        visibilityFilter === vis
                          ? 'bg-surface-dark text-brand-300 font-bold'
                          : 'text-slate-400 hover:text-slate-200'
                      }`}
                    >
                      {vis}
                    </button>
                  ))}
                </div>
              </div>

              {/* Grid or Empty/Loading State */}
              {reposLoading ? (
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
                  {[1, 2, 3].map((n) => (
                    <div key={n} className="bg-surface-darker/60 border border-surface-border/60 rounded-2xl p-5 h-48 animate-pulse"></div>
                  ))}
                </div>
              ) : importedRepos.length > 0 ? (
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
                  {importedRepos.map((repo) => (
                    <RepositoryCard
                      key={repo.id}
                      repository={repo}
                      onAnalyze={handleAnalyze}
                      onDelete={handleDeleteRepository}
                    />
                  ))}
                </div>
              ) : (
                <div className="border border-dashed border-surface-border rounded-3xl p-12 text-center bg-surface-darker/40 space-y-4">
                  <div className="w-12 h-12 rounded-2xl bg-surface-dark border border-surface-border flex items-center justify-center mx-auto text-slate-400">
                    <FolderGit2 className="w-6 h-6 text-brand-400" />
                  </div>
                  <div className="max-w-md mx-auto space-y-1">
                    <h3 className="text-sm font-semibold text-slate-200">
                      No repositories imported yet
                    </h3>
                    <p className="text-xs text-slate-400 leading-relaxed">
                      Select repositories from your GitHub account or import any public repository URL to begin codebase intelligence.
                    </p>
                  </div>
                  <div className="flex items-center justify-center space-x-3 pt-2">
                    <button
                      onClick={() => setActiveTab('my-repos')}
                      className="px-4 py-2 rounded-xl text-xs font-semibold bg-surface-dark hover:bg-surface-border text-slate-200 border border-surface-border transition-colors cursor-pointer"
                    >
                      Browse My Repositories
                    </button>
                    <button
                      onClick={() => setActiveTab('import-url')}
                      className="px-4 py-2 rounded-xl text-xs font-semibold bg-brand-500 hover:bg-brand-400 text-surface-darkest font-bold transition-colors cursor-pointer"
                    >
                      Import by URL
                    </button>
                  </div>
                </div>
              )}
            </div>
          )}

          {/* TAB 2: MY REPOSITORIES (GITHUB PICKER) */}
          {activeTab === 'my-repos' && (
            <div className="space-y-6">
              <div className="flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-3">
                <div className="relative flex-1 max-w-md">
                  <Search className="w-4 h-4 text-slate-400 absolute left-3.5 top-3 pointer-events-none" />
                  <input
                    type="text"
                    value={gitHubSearch}
                    onChange={(e) => setGitHubSearch(e.target.value)}
                    placeholder="Search your GitHub repositories..."
                    className="w-full pl-9 pr-4 py-2 bg-surface-darker/80 border border-surface-border rounded-xl text-xs text-slate-100 placeholder-slate-400 focus:outline-none focus:border-brand-400"
                  />
                </div>

                <div className="flex items-center space-x-2 text-xs text-slate-400">
                  <span>Page {gitHubPage}</span>
                  <div className="flex space-x-1">
                    <button
                      onClick={() => fetchGitHubRepos(Math.max(1, gitHubPage - 1), gitHubSearch)}
                      disabled={gitHubPage === 1 || gitHubReposLoading}
                      className="p-1.5 rounded-lg bg-surface-darker border border-surface-border disabled:opacity-30 hover:bg-surface-dark transition-colors cursor-pointer"
                      title="Previous Page"
                    >
                      <ChevronLeft className="w-4 h-4" />
                    </button>
                    <button
                      onClick={() => fetchGitHubRepos(gitHubPage + 1, gitHubSearch)}
                      disabled={!hasMoreGitHub || gitHubReposLoading}
                      className="p-1.5 rounded-lg bg-surface-darker border border-surface-border disabled:opacity-30 hover:bg-surface-dark transition-colors cursor-pointer"
                      title="Next Page"
                    >
                      <ChevronRight className="w-4 h-4" />
                    </button>
                  </div>
                </div>
              </div>

              {gitHubReposLoading ? (
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
                  {[1, 2, 3, 4, 5, 6].map((n) => (
                    <div key={n} className="bg-surface-darker/60 border border-surface-border/60 rounded-2xl p-5 h-40 animate-pulse"></div>
                  ))}
                </div>
              ) : gitHubRepos.length > 0 ? (
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
                  {gitHubRepos.map((repo) => (
                    <GitHubRepoPickerCard
                      key={repo.id}
                      repo={repo}
                      onImport={(url) => handleImportSuccess(url)}
                    />
                  ))}
                </div>
              ) : (
                <div className="border border-dashed border-surface-border rounded-3xl p-12 text-center bg-surface-darker/40 space-y-3">
                  <Github className="w-8 h-8 text-slate-400 mx-auto" />
                  <h3 className="text-sm font-semibold text-slate-200">
                    No repositories found
                  </h3>
                  <p className="text-xs text-slate-400 max-w-sm mx-auto">
                    No repositories match your search or your GitHub account has no public repositories with the authorized scopes.
                  </p>
                </div>
              )}
            </div>
          )}

          {/* TAB 3: IMPORT BY URL */}
          {activeTab === 'import-url' && (
            <div className="max-w-3xl mx-auto space-y-6">
              <ImportByUrlCard onImport={handleImportSuccess} />
            </div>
          )}

        </div>

        {/* Integration Architecture Summary Card */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <div className="bg-surface-darker border border-surface-border/70 rounded-2xl p-6 shadow-md space-y-4">
            <div className="flex items-center justify-between border-b border-surface-border/60 pb-3">
              <div className="flex items-center space-x-2.5">
                <ShieldCheck className="w-5 h-5 text-brand-400" />
                <h3 className="font-semibold text-slate-200 text-sm">Account & Identity</h3>
              </div>
              <span className="text-xs font-mono text-slate-400">UUIDv4</span>
            </div>

            <dl className="space-y-3 text-xs">
              <div className="flex justify-between py-1">
                <dt className="text-slate-400 flex items-center space-x-2">
                  <Key className="w-3.5 h-3.5" />
                  <span>Internal User ID</span>
                </dt>
                <dd className="font-mono text-slate-300">{user.id}</dd>
              </div>

              <div className="flex justify-between py-1">
                <dt className="text-slate-400 flex items-center space-x-2">
                  <Github className="w-3.5 h-3.5" />
                  <span>GitHub ID</span>
                </dt>
                <dd className="font-mono text-slate-300">{user.github_id}</dd>
              </div>

              <div className="flex justify-between py-1">
                <dt className="text-slate-400 flex items-center space-x-2">
                  <Mail className="w-3.5 h-3.5" />
                  <span>Verified Email</span>
                </dt>
                <dd className="font-mono text-slate-300">{user.email || 'None (Private)'}</dd>
              </div>

              <div className="flex justify-between py-1">
                <dt className="text-slate-400 flex items-center space-x-2">
                  <Calendar className="w-3.5 h-3.5" />
                  <span>First Registered</span>
                </dt>
                <dd className="text-slate-300">{formattedDate}</dd>
              </div>
            </dl>
          </div>

          <div className="bg-surface-darker border border-surface-border/70 rounded-2xl p-6 shadow-md space-y-4">
            <div className="flex items-center justify-between border-b border-surface-border/60 pb-3">
              <div className="flex items-center space-x-2.5">
                <Github className="w-5 h-5 text-brand-400" />
                <h3 className="font-semibold text-slate-200 text-sm">GitHub Integration Status</h3>
              </div>
              {statusLoading ? (
                <span className="text-xs text-slate-400">Verifying...</span>
              ) : gitHubStatus?.connected ? (
                <span className="flex items-center space-x-1 text-emerald-400 text-xs font-medium">
                  <CheckCircle2 className="w-3.5 h-3.5" />
                  <span>Connected</span>
                </span>
              ) : (
                <span className="flex items-center space-x-1 text-amber-400 text-xs font-medium">
                  <AlertCircle className="w-3.5 h-3.5" />
                  <span>Disconnected</span>
                </span>
              )}
            </div>

            <div className="space-y-3 text-xs">
              <div className="p-3 rounded-xl bg-surface-dark/50 border border-surface-border/40 space-y-2">
                <div className="flex items-center justify-between">
                  <span className="text-slate-400">Authorized Scopes</span>
                  <span className="font-mono text-brand-300 bg-brand-950/60 px-2 py-0.5 rounded border border-brand-900">
                    {gitHubStatus?.scopes || 'read:user, user:email, repo'}
                  </span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-slate-400">Token Storage</span>
                  <span className="text-slate-300">AES-256-GCM Encrypted at rest</span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-slate-400">Isolation Mode</span>
                  <span className="text-slate-300">Multi-tenant (User & Repository Scoped)</span>
                </div>
              </div>

              <div className="pt-1">
                <a
                  href={`https://github.com/${user.username}`}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center space-x-1.5 text-xs text-brand-400 hover:text-brand-300 transition-colors"
                >
                  <span>View GitHub Profile</span>
                  <ExternalLink className="w-3 h-3" />
                </a>
              </div>
            </div>
          </div>
        </div>

        {/* Real-time Ingestion Progress Modal */}
        {selectedRepoForIngestion && (
          <IngestionProgressModal
            repository={selectedRepoForIngestion}
            isOpen={Boolean(selectedRepoForIngestion)}
            onClose={() => setSelectedRepoForIngestion(null)}
            onComplete={() => {
              fetchImportedRepositories();
            }}
          />
        )}

      </main>
    </div>
  );
};
