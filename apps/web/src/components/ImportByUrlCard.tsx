import React, { useState } from 'react';
import { 
  Link2, 
  GitBranch, 
  ShieldCheck, 
  AlertCircle, 
  Loader2, 
  Sparkles,
  ArrowRight
} from 'lucide-react';

interface ImportByUrlCardProps {
  onImport: (url: string, branch?: string) => Promise<void>;
}

export const ImportByUrlCard: React.FC<ImportByUrlCardProps> = ({ onImport }) => {
  const [url, setUrl] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!url.trim()) return;

    setError(null);
    setIsSubmitting(true);
    try {
      await onImport(url.trim());
      setUrl('');
    } catch (err: unknown) {
      if (err && typeof err === 'object' && 'response' in err) {
        const axErr = err as { response?: { data?: { error?: { message?: string } } } };
        setError(axErr.response?.data?.error?.message || 'Failed to import repository.');
      } else {
        setError('Network error or invalid repository URL.');
      }
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleExampleClick = (exampleUrl: string) => {
    setUrl(exampleUrl);
    setError(null);
  };

  return (
    <div className="bg-surface-darker/90 border border-surface-border/80 rounded-3xl p-6 sm:p-8 shadow-xl space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-surface-border/50 pb-5">
        <div>
          <div className="flex items-center space-x-2.5">
            <div className="w-9 h-9 rounded-xl bg-brand-500/10 border border-brand-500/30 flex items-center justify-center text-brand-400">
              <Link2 className="w-5 h-5" />
            </div>
            <h3 className="text-lg font-bold text-slate-100 tracking-tight">
              Import by GitHub URL
            </h3>
          </div>
          <p className="text-xs text-slate-400 mt-1">
            Analyze any public repository or any private repository accessible by your account.
          </p>
        </div>

        <div className="flex items-center space-x-2 text-[11px] font-mono text-emerald-400 bg-emerald-950/40 border border-emerald-800/50 px-3 py-1.5 rounded-xl self-start sm:self-auto">
          <ShieldCheck className="w-3.5 h-3.5" />
          <span>SSRF Protected • Zero Token Exposure</span>
        </div>
      </div>

      {error && (
        <div className="p-4 rounded-2xl bg-rose-950/40 border border-rose-800/80 text-rose-300 text-xs flex items-start space-x-3">
          <AlertCircle className="w-4 h-4 flex-shrink-0 text-rose-400 mt-0.5" />
          <div>
            <p className="font-semibold">Import Issue</p>
            <p className="text-rose-200/80 mt-0.5">{error}</p>
          </div>
        </div>
      )}

      <form onSubmit={handleSubmit} className="space-y-4">
        <div>
          <label className="block text-xs font-semibold text-slate-300 mb-1.5">
            GitHub Repository URL or Identifier
          </label>
          <div className="relative">
            <input
              type="text"
              value={url}
              onChange={(e) => setUrl(e.target.value)}
              placeholder="https://github.com/owner/repository or owner/repo"
              className="w-full px-4 py-3 bg-surface-dark/90 border border-surface-border rounded-xl text-xs text-slate-100 placeholder-slate-500 focus:outline-none focus:border-brand-400 focus:ring-1 focus:ring-brand-400 font-mono transition-colors"
              required
            />
          </div>
          <p className="text-[11px] text-slate-500 mt-1.5 flex items-center space-x-1.5">
            <GitBranch className="w-3 h-3 text-brand-400" />
            <span>Default branch and retrieval method are automatically detected from GitHub.</span>
          </p>
        </div>

        {/* Popular public repo examples */}
        <div className="flex items-center flex-wrap gap-2 pt-1 text-xs text-slate-400">
          <span className="text-[11px] font-mono text-slate-500">Quick suggestions:</span>
          {[
            'pallets/flask',
            'fastapi/fastapi',
            'facebook/react',
            'torvalds/linux',
            'astral-sh/uv'
          ].map((example) => (
            <button
              key={example}
              type="button"
              onClick={() => handleExampleClick(example)}
              className="text-[11px] font-mono px-2.5 py-1 rounded-lg bg-surface-dark hover:bg-surface-border/50 text-slate-300 border border-surface-border/60 transition-colors cursor-pointer"
            >
              {example}
            </button>
          ))}
        </div>

        <div className="pt-2 flex justify-end">
          <button
            type="submit"
            disabled={isSubmitting || !url.trim()}
            className="px-6 py-3 rounded-xl text-xs font-bold text-surface-darkest bg-brand-500 hover:bg-brand-400 active:scale-[0.99] disabled:opacity-50 transition-all flex items-center space-x-2 shadow-lg shadow-brand-500/20 cursor-pointer"
          >
            {isSubmitting ? (
              <>
                <Loader2 className="w-4 h-4 animate-spin" />
                <span>Starting Ingestion...</span>
              </>
            ) : (
              <>
                <Sparkles className="w-4 h-4" />
                <span>Start Ingestion</span>
                <ArrowRight className="w-3.5 h-3.5" />
              </>
            )}
          </button>
        </div>
      </form>
    </div>
  );
};
