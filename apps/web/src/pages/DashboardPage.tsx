import React, { useEffect, useState } from 'react';
import { useAuth } from '../context/AuthContext';
import { Navbar } from '../components/Navbar';
import { authService } from '../services/authService';
import { GitHubStatus } from '../types/auth';
import { 
  Github, 
  ShieldCheck, 
  Calendar, 
  Mail, 
  Key, 
  Layers, 
  CheckCircle2, 
  AlertCircle,
  ExternalLink
} from 'lucide-react';

export const DashboardPage: React.FC = () => {
  const { user, logout } = useAuth();
  const [gitHubStatus, setGitHubStatus] = useState<GitHubStatus | null>(null);
  const [statusLoading, setStatusLoading] = useState<boolean>(true);

  useEffect(() => {
    let mounted = true;
    async function loadStatus() {
      try {
        const status = await authService.getGitHubStatus();
        if (mounted) setGitHubStatus(status);
      } catch (err) {
        console.error('Failed to load GitHub status', err);
      } finally {
        if (mounted) setStatusLoading(false);
      }
    }
    loadStatus();
    return () => { mounted = false; };
  }, []);

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
        {/* Welcome Banner */}
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
                  GitHub Profile: <span className="text-brand-300">@{user.username}</span>
                </p>
              </div>
            </div>

            <button
              onClick={logout}
              className="px-4 py-2 rounded-xl text-xs font-semibold text-rose-300 bg-rose-950/30 hover:bg-rose-900/50 border border-rose-800/60 transition-colors shadow-sm"
            >
              Sign Out
            </button>
          </div>
        </div>

        {/* Dashboard Grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          
          {/* Identity & Account Card */}
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

          {/* GitHub Connection Status Card */}
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
                    {gitHubStatus?.scopes || 'read:user, user:email'}
                  </span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-slate-400">Token Storage</span>
                  <span className="text-slate-300">AES-256-GCM Encrypted at rest</span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-slate-400">Session Type</span>
                  <span className="text-slate-300">Server-side (Redis cp_session)</span>
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

        {/* Placeholder for Next Modules (B2-M7) */}
        <div className="border border-dashed border-surface-border rounded-3xl p-8 text-center bg-surface-darker/30 space-y-3">
          <div className="w-12 h-12 rounded-2xl bg-surface-dark border border-surface-border flex items-center justify-center mx-auto text-slate-400">
            <Layers className="w-6 h-6 text-brand-400" />
          </div>
          <h3 className="text-base font-semibold text-slate-200">
            Authentication Phase Complete
          </h3>
          <p className="text-xs text-slate-400 max-w-lg mx-auto leading-relaxed">
            Your identity and session are established. The remaining 20 CodePilot features
            (Repository Ingestion, Codebase Explorer, Knowledge Graph, Hybrid RAG, Multi-Agent Engine) 
            are locked until explicitly requested.
          </p>
        </div>
      </main>
    </div>
  );
};
