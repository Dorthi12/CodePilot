import React from 'react';
import { useAuth } from '../context/AuthContext';
import { LogOut, Github } from 'lucide-react';

export const Navbar: React.FC = () => {
  const { user, logout, isLoading } = useAuth();

  return (
    <header className="border-b border-surface-border bg-surface-darker/80 backdrop-blur-md sticky top-0 z-50">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
        {/* Brand */}
        <div className="flex items-center space-x-3">
          <div className="w-9 h-9 rounded-xl bg-gradient-to-br from-brand-400 to-brand-600 flex items-center justify-center shadow-lg shadow-brand-500/20">
            <span className="font-mono text-surface-darkest font-extrabold text-base tracking-tighter">CP</span>
          </div>
          <div>
            <div className="flex items-center space-x-2">
              <span className="font-bold text-slate-100 text-lg tracking-tight">CodePilot</span>
              <span className="px-1.5 py-0.5 rounded text-[10px] font-mono font-medium bg-brand-950 text-brand-300 border border-brand-800">
                ATHENA
              </span>
            </div>
            <p className="text-[11px] text-slate-400 hidden sm:block">The Knowledge of Athena</p>
          </div>
        </div>

        {/* User Info & Actions */}
        {user && (
          <div className="flex items-center space-x-4">
            <div className="flex items-center space-x-3 bg-surface-dark/60 border border-surface-border/60 rounded-full py-1.5 pl-2 pr-4 shadow-sm">
              {user.avatar_url ? (
                <img
                  src={user.avatar_url}
                  alt={user.username}
                  className="w-7 h-7 rounded-full ring-1 ring-brand-500/50 object-cover"
                />
              ) : (
                <div className="w-7 h-7 rounded-full bg-surface-border flex items-center justify-center">
                  <Github className="w-4 h-4 text-slate-400" />
                </div>
              )}
              <div className="text-left hidden sm:block">
                <p className="text-xs font-semibold text-slate-200 leading-tight">
                  {user.name || user.username}
                </p>
                <p className="text-[10px] font-mono text-slate-400 leading-none">
                  @{user.username}
                </p>
              </div>
              <div className="flex items-center text-emerald-400 text-[10px] font-medium space-x-1 pl-1">
                <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse"></span>
                <span className="hidden md:inline">Online</span>
              </div>
            </div>

            <button
              onClick={logout}
              disabled={isLoading}
              className="flex items-center space-x-1.5 px-3 py-1.5 rounded-lg text-xs font-medium text-slate-300 bg-surface-dark hover:bg-rose-950/40 hover:text-rose-300 hover:border-rose-800/60 border border-surface-border transition-colors duration-150 disabled:opacity-50"
              title="Sign Out"
            >
              <LogOut className="w-3.5 h-3.5" />
              <span>Sign Out</span>
            </button>
          </div>
        )}
      </div>
    </header>
  );
};
