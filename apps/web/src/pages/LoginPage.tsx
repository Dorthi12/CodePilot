import React, { useEffect, useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { Github, Shield, Terminal, ArrowRight, AlertTriangle } from 'lucide-react';

export const LoginPage: React.FC = () => {
  const { isAuthenticated, loginWithGitHub, isLoading } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();

  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  // If already authenticated, redirect to dashboard
  useEffect(() => {
    if (isAuthenticated) {
      navigate('/dashboard', { replace: true });
    }
  }, [isAuthenticated, navigate]);

  // Check URL search parameters for OAuth callback error messages
  useEffect(() => {
    const params = new URLSearchParams(location.search);
    const error = params.get('error');
    const desc = params.get('error_description');

    if (error) {
      if (error === 'access_denied') {
        setErrorMessage('GitHub authorization was canceled by the user.');
      } else if (error === 'invalid_state') {
        setErrorMessage('OAuth security session expired or is invalid. Please try again.');
      } else if (desc) {
        setErrorMessage(desc);
      } else {
        setErrorMessage(`Authentication failed (${error}).`);
      }
    }
  }, [location]);

  return (
    <div className="min-h-screen bg-surface-darkest flex flex-col justify-between relative overflow-hidden">
      {/* Background glowing effects */}
      <div className="absolute top-0 left-1/2 -translate-x-1/2 w-[800px] h-[450px] bg-brand-500/10 rounded-full blur-[140px] pointer-events-none -z-10"></div>
      <div className="absolute bottom-0 right-1/4 w-[500px] h-[300px] bg-indigo-500/5 rounded-full blur-[120px] pointer-events-none -z-10"></div>

      {/* Decorative Grid Pattern */}
      <div className="absolute inset-0 bg-[linear-gradient(to_right,#1e293b08_1px,transparent_1px),linear-gradient(to_bottom,#1e293b08_1px,transparent_1px)] bg-[size:40px_40px] pointer-events-none -z-10"></div>

      {/* Top Header */}
      <header className="px-6 py-6 max-w-7xl mx-auto w-full flex items-center justify-between">
        <div className="flex items-center space-x-3">
          <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-brand-400 to-brand-600 flex items-center justify-center shadow-lg shadow-brand-500/25">
            <span className="font-mono text-surface-darkest font-extrabold text-lg tracking-tighter">CP</span>
          </div>
          <span className="font-bold text-slate-100 text-xl tracking-tight">CodePilot</span>
        </div>

        <div className="flex items-center space-x-2 text-xs font-mono text-slate-400 bg-surface-dark/40 border border-surface-border/60 rounded-full px-3 py-1">
          <span className="w-2 h-2 rounded-full bg-brand-400"></span>
          <span>SYSTEM DESIGN v1.1 COMPLIANT</span>
        </div>
      </header>

      {/* Main Content Area */}
      <main className="flex-1 flex items-center justify-center px-4 sm:px-6 lg:px-8 py-12">
        <div className="max-w-md w-full space-y-8 bg-surface-darker/90 border border-surface-border/80 backdrop-blur-xl p-8 sm:p-10 rounded-3xl shadow-2xl relative">
          
          {/* Emblem & Athena Title */}
          <div className="text-center space-y-3">
            <div className="inline-flex items-center space-x-2 px-3 py-1 rounded-full bg-brand-950/80 border border-brand-800 text-brand-300 text-xs font-mono font-medium tracking-wide">
              <span>THE KNOWLEDGE OF ATHENA</span>
            </div>

            <h1 className="text-3xl font-extrabold text-slate-100 tracking-tight sm:text-4xl">
              CodePilot
            </h1>

            <p className="text-sm text-slate-400 max-w-sm mx-auto leading-relaxed">
              Understand, explore and debug your codebase intelligently.
            </p>
          </div>

          {/* Error Banner */}
          {errorMessage && (
            <div className="p-4 rounded-xl bg-rose-950/40 border border-rose-800/80 text-rose-300 text-xs flex items-start space-x-3">
              <AlertTriangle className="w-5 h-5 flex-shrink-0 text-rose-400 mt-0.5" />
              <div className="flex-1">
                <p className="font-medium">Authentication Notice</p>
                <p className="text-rose-200/80 mt-0.5">{errorMessage}</p>
              </div>
            </div>
          )}

          {/* Authentication Actions */}
          <div className="space-y-4 pt-2">
            <button
              onClick={loginWithGitHub}
              disabled={isLoading}
              className="w-full flex items-center justify-center space-x-3 py-3.5 px-5 rounded-xl text-sm font-semibold text-white bg-slate-900 hover:bg-slate-800 active:scale-[0.99] border border-slate-700 hover:border-slate-600 shadow-lg shadow-black/40 transition-all duration-200 group disabled:opacity-60 cursor-pointer"
            >
              <Github className="w-5 h-5 text-slate-200 group-hover:text-white transition-colors" />
              <span>Continue with GitHub</span>
              <ArrowRight className="w-4 h-4 text-slate-400 group-hover:translate-x-1 group-hover:text-brand-300 transition-all" />
            </button>

            <div className="text-center">
              <span className="text-[11px] text-slate-400">
                Authorized via scoped GitHub App • Zero password storage
              </span>
            </div>
          </div>

          {/* Feature Highlights Grid */}
          <div className="pt-6 border-t border-surface-border/50 grid grid-cols-2 gap-3 text-left">
            <div className="p-3 rounded-xl bg-surface-dark/40 border border-surface-border/40">
              <Shield className="w-4 h-4 text-brand-400 mb-1.5" />
              <h4 className="text-xs font-semibold text-slate-200">Secure Sessions</h4>
              <p className="text-[11px] text-slate-400 mt-0.5">HttpOnly, SameSite Lax, Redis-backed sessions.</p>
            </div>
            <div className="p-3 rounded-xl bg-surface-dark/40 border border-surface-border/40">
              <Terminal className="w-4 h-4 text-brand-400 mb-1.5" />
              <h4 className="text-xs font-semibold text-slate-200">Developer First</h4>
              <p className="text-[11px] text-slate-400 mt-0.5">Strict token isolation & encryption at rest.</p>
            </div>
          </div>

        </div>
      </main>

      {/* Footer */}
      <footer className="py-6 px-4 text-center text-xs text-slate-400 border-t border-surface-border/30">
        <p>CodePilot &copy; 2026. Built with FastAPI, PostgreSQL, Redis, and React.</p>
      </footer>
    </div>
  );
};
