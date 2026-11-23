import React from 'react';
import { Navigate, useLocation } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';

interface ProtectedRouteProps {
  children: React.ReactNode;
}

export const ProtectedRoute: React.FC<ProtectedRouteProps> = ({ children }) => {
  const { isAuthenticated, isLoading } = useAuth();
  const location = useLocation();

  if (isLoading) {
    return (
      <div className="min-h-screen bg-surface-darkest flex flex-col items-center justify-center p-6 text-slate-300">
        <div className="relative mb-6">
          <div className="w-16 h-16 rounded-2xl bg-brand-500/10 border border-brand-500/30 flex items-center justify-center animate-pulse">
            <div className="w-8 h-8 rounded-xl bg-brand-500/30 flex items-center justify-center">
              <span className="font-mono text-brand-400 font-bold text-lg">CP</span>
            </div>
          </div>
          <div className="absolute -inset-1 rounded-2xl bg-brand-400/20 blur-sm -z-10 animate-pulse"></div>
        </div>
        <div className="flex items-center space-x-3 text-slate-400">
          <svg className="animate-spin h-5 w-5 text-brand-400" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z"></path>
          </svg>
          <span className="text-sm font-medium tracking-wide">Authenticating with Athena Session...</span>
        </div>
      </div>
    );
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" state={{ from: location }} replace />;
  }

  return <>{children}</>;
};
