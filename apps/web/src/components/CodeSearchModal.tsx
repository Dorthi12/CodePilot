import React, { useState } from 'react';
import { Search, Filter, Code2, AlertCircle, Loader2, Sparkles } from 'lucide-react';
import { aiService } from '../services/aiService';
import { SearchResultItem } from '../types/ai';
import { Repository } from '../types/repository';

interface CodeSearchModalProps {
  repository: Repository;
  onClose: () => void;
  onSelectForExplanation: (snippet: string, filePath: string, startLine: number, endLine: number) => void;
}

export const CodeSearchModal: React.FC<CodeSearchModalProps> = ({
  repository,
  onClose,
  onSelectForExplanation,
}) => {
  const [query, setQuery] = useState('');
  const [selectedKind, setSelectedKind] = useState<string>('ALL');
  const [results, setResults] = useState<SearchResultItem[]>([]);
  const [total, setTotal] = useState<number | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSearch = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!query.trim()) return;

    setIsLoading(true);
    setError(null);

    try {
      const filters: { kinds?: string[] } = {};
      if (selectedKind !== 'ALL') {
        filters.kinds = [selectedKind];
      }

      const res = await aiService.searchRepository(repository.id, {
        query: query.trim(),
        filters: Object.keys(filters).length ? filters : undefined,
        top_k: 30,
      });

      setResults(res.results || []);
      setTotal(res.total);
    } catch (err: unknown) {
      let msg = 'Failed to execute code search.';
      if (err && typeof err === 'object' && 'response' in err) {
        const axErr = err as { response?: { data?: { error?: { message?: string } } } };
        msg = axErr.response?.data?.error?.message || msg;
      }
      setError(msg);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/75 backdrop-blur-sm animate-in fade-in duration-200">
      <div className="bg-surface-darker border border-surface-border rounded-2xl w-full max-w-4xl max-h-[90vh] flex flex-col shadow-2xl overflow-hidden">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-surface-border/60">
          <div className="flex items-center space-x-2.5">
            <div className="w-8 h-8 rounded-lg bg-brand-500/10 border border-brand-500/20 flex items-center justify-center text-brand-400">
              <Code2 className="w-4 h-4" />
            </div>
            <div>
              <h2 className="text-sm font-semibold text-slate-100">Code Search</h2>
              <p className="text-xs text-slate-400">
                {repository.owner}/{repository.name} ({repository.tracked_branch})
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="text-slate-400 hover:text-slate-200 text-sm px-2.5 py-1 rounded-lg hover:bg-surface-dark transition-colors"
          >
            ✕
          </button>
        </div>

        {/* Search Bar & Filters */}
        <form onSubmit={handleSearch} className="p-6 border-b border-surface-border/40 space-y-4">
          <div className="flex items-center gap-3">
            <div className="relative flex-1">
              <Search className="w-4 h-4 absolute left-3.5 top-1/2 -translate-y-1/2 text-slate-400" />
              <input
                type="text"
                placeholder="Search functions, classes, methods, variables..."
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                className="w-full bg-surface-dark border border-surface-border/80 focus:border-brand-500 rounded-xl pl-10 pr-4 py-2.5 text-xs text-slate-100 placeholder-slate-500 focus:outline-none"
                autoFocus
              />
            </div>
            <button
              type="submit"
              disabled={isLoading || !query.trim()}
              className="px-5 py-2.5 bg-brand-500 hover:bg-brand-400 disabled:opacity-50 text-surface-darkest text-xs font-semibold rounded-xl flex items-center space-x-1.5 transition-colors cursor-pointer"
            >
              {isLoading ? (
                <>
                  <Loader2 className="w-3.5 h-3.5 animate-spin" />
                  <span>Searching...</span>
                </>
              ) : (
                <>
                  <Search className="w-3.5 h-3.5" />
                  <span>Search</span>
                </>
              )}
            </button>
          </div>

          <div className="flex items-center space-x-2 text-xs">
            <Filter className="w-3.5 h-3.5 text-slate-500" />
            <span className="text-slate-400 font-medium">Filter by Kind:</span>
            {['ALL', 'FUNCTION', 'CLASS', 'METHOD', 'VARIABLE', 'IMPORT'].map((kind) => (
              <button
                key={kind}
                type="button"
                onClick={() => setSelectedKind(kind)}
                className={`px-2.5 py-1 rounded-lg text-[11px] font-mono transition-colors ${
                  selectedKind === kind
                    ? 'bg-brand-500/20 text-brand-300 border border-brand-500/40'
                    : 'text-slate-400 hover:text-slate-200 hover:bg-surface-dark'
                }`}
              >
                {kind}
              </button>
            ))}
          </div>
        </form>

        {/* Results Body */}
        <div className="flex-1 overflow-y-auto p-6 space-y-4">
          {error && (
            <div className="p-4 rounded-xl bg-rose-950/40 border border-rose-800 text-rose-200 text-xs flex items-center space-x-2">
              <AlertCircle className="w-4 h-4 flex-shrink-0" />
              <span>{error}</span>
            </div>
          )}

          {total !== null && !error && (
            <div className="text-xs text-slate-400 font-mono">
              Found {total} matching symbol{total === 1 ? '' : 's'}
            </div>
          )}

          {results.length === 0 && total === 0 && !isLoading && (
            <div className="text-center py-12 text-slate-500 text-xs">
              No matching code symbols found for "{query}".
            </div>
          )}

          {results.map((res) => (
            <div
              key={res.source_id}
              className="bg-surface-dark/60 border border-surface-border/60 hover:border-brand-500/40 rounded-xl p-4 transition-all space-y-2 group"
            >
              <div className="flex items-start justify-between gap-2">
                <div className="min-w-0">
                  <div className="flex items-center space-x-2">
                    <span className="text-[10px] font-mono font-bold px-1.5 py-0.5 rounded bg-brand-500/10 text-brand-300 border border-brand-500/20">
                      {res.kind}
                    </span>
                    <span className="text-xs font-semibold text-slate-100 font-mono truncate">
                      {res.name}
                    </span>
                    <span className="text-[10px] text-slate-500 font-mono">
                      (match: {res.match_type}, score: {res.score})
                    </span>
                  </div>
                  <div className="text-[11px] font-mono text-slate-400 truncate mt-1">
                    {res.file_path}:{res.start_line}-{res.end_line}
                  </div>
                </div>

                <button
                  onClick={() => {
                    onSelectForExplanation(res.snippet, res.file_path, res.start_line, res.end_line);
                  }}
                  className="px-2.5 py-1.5 rounded-lg bg-surface-dark hover:bg-brand-500/20 text-slate-300 hover:text-brand-300 border border-surface-border text-[11px] font-semibold flex items-center space-x-1 transition-colors flex-shrink-0 cursor-pointer"
                  title="Explain this symbol with AI"
                >
                  <Sparkles className="w-3 h-3 text-brand-400" />
                  <span>Explain Code</span>
                </button>
              </div>

              {res.snippet && (
                <pre className="p-3 bg-surface-darkest rounded-lg text-[11px] font-mono text-slate-300 overflow-x-auto max-h-48 border border-surface-border/40">
                  <code>{res.snippet}</code>
                </pre>
              )}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};
