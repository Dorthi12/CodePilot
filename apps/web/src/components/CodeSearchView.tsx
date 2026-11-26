import React, { useState } from 'react';
import {
  Search,
  Loader2,
  AlertCircle,
  FileCode,
  Filter,
  ArrowUpRight,
  X,
} from 'lucide-react';
import { aiService, extractAIErrorMessage } from '../services/aiService';
import { CodeSearchResultItem, CodeSearchResponse } from '../types/ai';

interface CodeSearchViewProps {
  repositoryId: string;
  onSelectResult: (filePath: string, line: number) => void;
}

const SUPPORTED_LANGUAGES = ['python', 'javascript', 'typescript', 'java', 'go'];
const SYMBOL_KINDS = ['FUNCTION', 'CLASS', 'METHOD', 'INTERFACE', 'VARIABLE', 'IMPORT', 'EXPORT'];

export const CodeSearchView: React.FC<CodeSearchViewProps> = ({
  repositoryId,
  onSelectResult,
}) => {
  const [query, setQuery] = useState('');
  const [language, setLanguage] = useState('');
  const [kind, setKind] = useState('');
  const [pathPrefix, setPathPrefix] = useState('');
  const [topK, setTopK] = useState(20);

  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [response, setResponse] = useState<CodeSearchResponse | null>(null);

  const handleSearch = async (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    const trimmed = query.trim();
    if (!trimmed) {
      setError('Please enter a search query.');
      return;
    }

    setIsLoading(true);
    setError(null);

    try {
      const hasFilters = Boolean(language || kind || pathPrefix.trim());
      const data = await aiService.searchCode(repositoryId, {
        query: trimmed,
        top_k: topK,
        filters: hasFilters
          ? {
              languages: language ? [language] : undefined,
              kinds: kind ? [kind] : undefined,
              path_prefix: pathPrefix.trim() || undefined,
            }
          : undefined,
      });
      setResponse(data);
    } catch (err) {
      setError(extractAIErrorMessage(err, 'Failed to search repository code.'));
    } finally {
      setIsLoading(false);
    }
  };

  const clearFilters = () => {
    setLanguage('');
    setKind('');
    setPathPrefix('');
    setTopK(20);
  };

  const hasActiveFilters = Boolean(language || kind || pathPrefix.trim() || topK !== 20);

  return (
    <div className="space-y-4">
      {/* Search & Filter Controls */}
      <div className="bg-surface-darker/90 border border-surface-border/70 rounded-2xl p-5 shadow-xl space-y-4">
        <form onSubmit={handleSearch} className="flex flex-col sm:flex-row gap-3">
          <div className="relative flex-1">
            <Search className="w-4 h-4 text-slate-500 absolute left-3.5 top-1/2 -translate-y-1/2" />
            <input
              type="text"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Search functions, classes, methods, or keywords (exact, symbol, fuzzy)..."
              className="w-full bg-surface-dark/90 border border-surface-border/70 rounded-xl pl-10 pr-4 py-2.5 text-sm text-slate-100 placeholder-slate-500 focus:outline-none focus:border-brand-500/60"
            />
          </div>
          <button
            type="submit"
            disabled={isLoading || !query.trim()}
            className="px-5 py-2.5 rounded-xl bg-brand-500 hover:bg-brand-400 text-surface-darkest text-sm font-bold flex items-center justify-center space-x-2 transition-colors cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {isLoading ? (
              <>
                <Loader2 className="w-4 h-4 animate-spin" />
                <span>Searching...</span>
              </>
            ) : (
              <>
                <Search className="w-4 h-4" />
                <span>Search Code</span>
              </>
            )}
          </button>
        </form>

        {/* Filters */}
        <div className="flex flex-wrap items-center gap-3 pt-1">
          <div className="flex items-center space-x-1.5 text-xs font-mono text-slate-400">
            <Filter className="w-3.5 h-3.5 text-brand-400" />
            <span>Filters:</span>
          </div>

          <select
            aria-label="Filter by language"
            value={language}
            onChange={(e) => setLanguage(e.target.value)}
            className="bg-surface-dark/90 border border-surface-border/60 rounded-xl px-3 py-1.5 text-xs text-slate-200 focus:outline-none focus:border-brand-500/50"
          >
            <option value="">All Languages</option>
            {SUPPORTED_LANGUAGES.map((lang) => (
              <option key={lang} value={lang}>
                {lang}
              </option>
            ))}
          </select>

          <select
            aria-label="Filter by symbol kind"
            value={kind}
            onChange={(e) => setKind(e.target.value)}
            className="bg-surface-dark/90 border border-surface-border/60 rounded-xl px-3 py-1.5 text-xs text-slate-200 focus:outline-none focus:border-brand-500/50"
          >
            <option value="">All Symbol Kinds</option>
            {SYMBOL_KINDS.map((k) => (
              <option key={k} value={k}>
                {k}
              </option>
            ))}
          </select>

          <input
            type="text"
            value={pathPrefix}
            onChange={(e) => setPathPrefix(e.target.value)}
            placeholder="Path prefix (e.g. src/)"
            className="bg-surface-dark/90 border border-surface-border/60 rounded-xl px-3 py-1.5 text-xs text-slate-200 placeholder-slate-500 focus:outline-none focus:border-brand-500/50 w-44"
          />

          <select
            aria-label="Max results"
            value={topK}
            onChange={(e) => setTopK(Number(e.target.value))}
            className="bg-surface-dark/90 border border-surface-border/60 rounded-xl px-3 py-1.5 text-xs text-slate-200 focus:outline-none focus:border-brand-500/50"
          >
            <option value={10}>Top 10</option>
            <option value={20}>Top 20</option>
            <option value={50}>Top 50</option>
          </select>

          {hasActiveFilters && (
            <button
              type="button"
              onClick={clearFilters}
              className="text-xs text-slate-400 hover:text-slate-200 flex items-center space-x-1 px-2 py-1 rounded-lg hover:bg-surface-dark cursor-pointer"
            >
              <X className="w-3 h-3" />
              <span>Reset</span>
            </button>
          )}
        </div>
      </div>

      {/* Error State */}
      {error && (
        <div className="bg-rose-950/30 border border-rose-800/50 rounded-2xl p-4 flex items-start space-x-3 text-rose-200">
          <AlertCircle className="w-5 h-5 text-rose-400 flex-shrink-0 mt-0.5" />
          <div className="text-sm">{error}</div>
        </div>
      )}

      {/* Results Area */}
      {!isLoading && !error && response === null && (
        <div className="bg-surface-darker/70 border border-surface-border/50 rounded-2xl p-10 text-center space-y-2">
          <Search className="w-8 h-8 text-slate-600 mx-auto" />
          <p className="text-sm font-medium text-slate-300">
            Search symbols and code across the repository
          </p>
          <p className="text-xs text-slate-500 max-w-md mx-auto">
            Supports exact name matches, word-boundary symbol matches, and fuzzy matching across file paths and snippets.
          </p>
        </div>
      )}

      {!isLoading && response && response.results.length === 0 && (
        <div className="bg-surface-darker/70 border border-surface-border/50 rounded-2xl p-10 text-center space-y-2">
          <FileCode className="w-8 h-8 text-slate-600 mx-auto" />
          <p className="text-sm font-medium text-slate-300">
            No results found for &ldquo;{response.query}&rdquo;
          </p>
          <p className="text-xs text-slate-500">
            Try broadening your query or clearing active language/kind/path filters.
          </p>
        </div>
      )}

      {response && response.results.length > 0 && (
        <div className="space-y-3">
          <div className="flex items-center justify-between text-xs font-mono text-slate-400 px-1">
            <span>
              Showing {response.results.length} of {response.total} matches for{' '}
              <span className="text-slate-200">&ldquo;{response.query}&rdquo;</span>
            </span>
          </div>

          {response.results.map((item: CodeSearchResultItem) => (
            <button
              key={item.source_id}
              type="button"
              onClick={() => onSelectResult(item.file_path, item.start_line)}
              className="w-full text-left bg-surface-darker/90 hover:bg-surface-dark/80 border border-surface-border/70 hover:border-brand-500/50 rounded-2xl p-4 transition-colors cursor-pointer group space-y-2.5"
            >
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div className="flex items-center space-x-2 min-w-0">
                  <span className="text-sm font-bold font-mono text-brand-300 group-hover:text-brand-200 truncate">
                    {item.name}
                  </span>
                  <span className="text-[10px] font-mono px-2 py-0.5 rounded-full bg-surface-dark border border-surface-border text-slate-300">
                    {item.kind}
                  </span>
                  <span className="text-[10px] font-mono px-2 py-0.5 rounded-full bg-surface-dark border border-surface-border text-slate-400">
                    {item.language}
                  </span>
                </div>

                <div className="flex items-center space-x-2 text-[11px] font-mono">
                  <span className="px-2 py-0.5 rounded-full bg-brand-500/10 text-brand-300 border border-brand-500/30">
                    {item.match_type} • {Math.round(item.score * 100)}%
                  </span>
                  <ArrowUpRight className="w-3.5 h-3.5 text-slate-500 group-hover:text-brand-400" />
                </div>
              </div>

              <div className="text-xs font-mono text-slate-400 flex items-center space-x-2">
                <span className="truncate">{item.file_path}</span>
                <span className="text-slate-600">•</span>
                <span className="text-slate-300 flex-shrink-0">
                  L{item.start_line}–L{item.end_line}
                </span>
              </div>

              {item.snippet && (
                <pre className="bg-[#080c14] border border-surface-border/50 rounded-xl p-3 text-xs font-mono text-slate-300 overflow-x-auto leading-relaxed">
                  <code>{item.snippet}</code>
                </pre>
              )}
            </button>
          ))}
        </div>
      )}
    </div>
  );
};
