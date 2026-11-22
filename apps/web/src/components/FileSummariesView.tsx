import React, { useState, useEffect, useMemo } from 'react';
import {
  FileText,
  Search,
  FileCode,
  ArrowRight,
  Layers,
  Loader2,
  Sparkles
} from 'lucide-react';
import { FileSummaryItem } from '../types/repository';
import { repositoryService } from '../services/repositoryService';

interface FileSummariesViewProps {
  repositoryId: string;
  onSelectFile: (filePath: string) => void;
}

export const FileSummariesView: React.FC<FileSummariesViewProps> = ({
  repositoryId,
  onSelectFile
}) => {
  const [files, setFiles] = useState<FileSummaryItem[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState<string>('');
  const [selectedLanguage, setSelectedLanguage] = useState<string>('ALL');

  useEffect(() => {
    let mounted = true;
    async function loadFiles() {
      setLoading(true);
      setError(null);
      try {
        const fileList = await repositoryService.listRepositoryFiles(repositoryId);
        if (mounted) {
          setFiles(fileList);
        }
      } catch (err: any) {
        if (mounted) {
          setError(err.response?.data?.error?.message || 'Failed to load file summaries.');
        }
      } finally {
        if (mounted) {
          setLoading(false);
        }
      }
    }
    loadFiles();
    return () => { mounted = false; };
  }, [repositoryId]);

  // Extract unique languages
  const availableLanguages = useMemo(() => {
    const langs = new Set<string>();
    files.forEach(f => {
      if (f.language) langs.add(f.language);
    });
    return Array.from(langs).sort();
  }, [files]);

  // Filtered files
  const filteredFiles = useMemo(() => {
    return files.filter(f => {
      const q = searchQuery.toLowerCase().trim();
      const matchesSearch =
        !q ||
        f.filename.toLowerCase().includes(q) ||
        f.path.toLowerCase().includes(q) ||
        (f.summary && f.summary.toLowerCase().includes(q));

      const matchesLang =
        selectedLanguage === 'ALL' ||
        (f.language && f.language.toLowerCase() === selectedLanguage.toLowerCase());

      return matchesSearch && matchesLang;
    });
  }, [files, searchQuery, selectedLanguage]);

  return (
    <div className="space-y-4">
      {/* Search and Language Filter Toolbar */}
      <div className="bg-surface-darker/90 border border-surface-border/70 rounded-2xl p-4 flex flex-col sm:flex-row items-center justify-between gap-3 shadow-lg">
        {/* Search Input */}
        <div className="relative w-full sm:w-96">
          <Search className="w-4 h-4 text-slate-500 absolute left-3 top-1/2 -translate-y-1/2" />
          <input
            type="text"
            value={searchQuery}
            onChange={e => setSearchQuery(e.target.value)}
            placeholder="Search files by path, name or summary keywords..."
            className="w-full bg-surface-dark/90 border border-surface-border/60 rounded-xl pl-9 pr-4 py-2 text-xs text-slate-200 placeholder-slate-500 focus:outline-none focus:border-brand-500/50"
          />
        </div>

        {/* Language Filter Pills */}
        <div className="flex items-center space-x-1.5 overflow-x-auto w-full sm:w-auto pb-1 sm:pb-0">
          <span className="text-[11px] font-mono text-slate-500 mr-1 hidden lg:inline">
            Language:
          </span>
          <button
            onClick={() => setSelectedLanguage('ALL')}
            className={`px-3 py-1 rounded-xl text-xs font-mono font-medium cursor-pointer transition-colors ${
              selectedLanguage === 'ALL'
                ? 'bg-brand-500 text-surface-darkest font-bold'
                : 'bg-surface-dark border border-surface-border text-slate-400 hover:text-slate-200'
            }`}
          >
            All ({files.length})
          </button>
          {availableLanguages.map(lang => (
            <button
              key={lang}
              onClick={() => setSelectedLanguage(lang)}
              className={`px-2.5 py-1 rounded-xl text-xs font-mono font-medium capitalize cursor-pointer transition-colors ${
                selectedLanguage === lang
                  ? 'bg-brand-500 text-surface-darkest font-bold'
                  : 'bg-surface-dark border border-surface-border text-slate-400 hover:text-slate-200'
              }`}
            >
              {lang}
            </button>
          ))}
        </div>
      </div>

      {/* Content Area */}
      {loading ? (
        <div className="bg-surface-darker/90 border border-surface-border/70 rounded-2xl p-12 flex flex-col items-center justify-center text-slate-400 space-y-3">
          <Loader2 className="w-7 h-7 animate-spin text-brand-400" />
          <span className="text-sm font-medium">Aggregating file-level AST summaries...</span>
        </div>
      ) : error ? (
        <div className="bg-surface-darker/90 border border-rose-800/40 rounded-2xl p-8 text-center text-rose-300 space-y-2">
          <FileText className="w-8 h-8 text-rose-400 mx-auto" />
          <p className="text-sm font-medium">{error}</p>
        </div>
      ) : filteredFiles.length === 0 ? (
        <div className="bg-surface-darker/90 border border-surface-border/70 rounded-2xl p-12 text-center text-slate-400 space-y-2">
          <Layers className="w-8 h-8 text-slate-600 mx-auto mb-1" />
          <p className="text-sm font-medium text-slate-300">No matching files found</p>
          <p className="text-xs text-slate-500">Try adjusting your search query or language filter.</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3.5">
          {filteredFiles.map(file => (
            <div
              key={file.id}
              onClick={() => onSelectFile(file.path)}
              className="bg-surface-darker/80 hover:bg-surface-darker border border-surface-border/60 hover:border-brand-500/50 rounded-2xl p-4 transition-all duration-200 cursor-pointer flex flex-col justify-between group shadow-sm hover:shadow-lg"
            >
              <div>
                {/* Header: Path & Language Pill */}
                <div className="flex items-start justify-between gap-2 mb-2">
                  <div className="flex items-center space-x-2.5 min-w-0">
                    <div className="w-8 h-8 rounded-xl bg-surface-dark border border-surface-border flex items-center justify-center flex-shrink-0 text-slate-300 group-hover:text-brand-300">
                      <FileCode className="w-4 h-4" />
                    </div>
                    <div className="min-w-0">
                      <h4 className="text-xs font-semibold text-slate-200 truncate group-hover:text-brand-300 font-mono">
                        {file.filename}
                      </h4>
                      <p className="text-[11px] font-mono text-slate-500 truncate">
                        {file.path}
                      </p>
                    </div>
                  </div>

                  {file.language && (
                    <span className="px-2 py-0.5 rounded-full text-[10px] font-mono uppercase font-semibold bg-brand-500/10 text-brand-300 border border-brand-500/30 flex-shrink-0">
                      {file.language}
                    </span>
                  )}
                </div>

                {/* Summary Text */}
                {file.summary ? (
                  <p className="text-xs text-slate-300 leading-relaxed line-clamp-3 mb-3 bg-surface-dark/40 rounded-xl p-2.5 border border-surface-border/30">
                    {file.summary}
                  </p>
                ) : (
                  <div className="flex items-center space-x-2 text-xs text-slate-500 italic mb-3 bg-surface-dark/20 rounded-xl p-2.5 border border-surface-border/20">
                    <Sparkles className="w-3.5 h-3.5 text-slate-600 flex-shrink-0" />
                    <span>No summary generated yet. Click to view and generate on-demand.</span>
                  </div>
                )}
              </div>

              {/* Stats Footer */}
              <div className="flex items-center justify-between pt-2.5 border-t border-surface-border/40 text-[11px] text-slate-400 font-mono">
                <div className="flex items-center space-x-3">
                  <span>{file.line_count} lines</span>
                  <span>•</span>
                  <span>{(file.size_bytes / 1024).toFixed(1)} KB</span>
                  {file.function_count > 0 && (
                    <>
                      <span>•</span>
                      <span className="text-emerald-400 font-semibold">{file.function_count} fn</span>
                    </>
                  )}
                  {file.class_count > 0 && (
                    <>
                      <span>•</span>
                      <span className="text-purple-400 font-semibold">{file.class_count} cls</span>
                    </>
                  )}
                </div>

                <div className="flex items-center space-x-1 text-brand-400 opacity-0 group-hover:opacity-100 transition-opacity font-semibold">
                  <span>{file.summary ? 'Inspect' : 'Generate'}</span>
                  <ArrowRight className="w-3.5 h-3.5" />
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};
