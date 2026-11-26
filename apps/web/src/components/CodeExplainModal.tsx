import React, { useEffect, useState } from 'react';
import {
  X,
  Sparkles,
  Loader2,
  AlertCircle,
  AlertTriangle,
  BookOpen,
  GitBranch,
  ListChecks,
  ArrowUpRight,
} from 'lucide-react';
import { aiService, extractAIErrorMessage } from '../services/aiService';
import { CodeExplainResponse, ExplanationStyle } from '../types/ai';

interface CodeExplainModalProps {
  isOpen: boolean;
  onClose: () => void;
  repositoryId: string;
  filePath: string;
  totalLines: number;
  initialStartLine?: number;
  initialEndLine?: number;
  symbolName?: string;
  onNavigateToLocation?: (filePath: string, line: number) => void;
}

const PRESET_QUESTIONS = [
  'What does this code do?',
  'Explain this code line by line.',
  'Are there any potential bugs or edge cases?',
];

export const CodeExplainModal: React.FC<CodeExplainModalProps> = ({
  isOpen,
  onClose,
  repositoryId,
  filePath,
  totalLines,
  initialStartLine,
  initialEndLine,
  symbolName,
  onNavigateToLocation,
}) => {
  const [style, setStyle] = useState<ExplanationStyle>('technical');
  const [question, setQuestion] = useState('What does this code do?');
  const [startLine, setStartLine] = useState<string>(
    initialStartLine ? String(initialStartLine) : ''
  );
  const [endLine, setEndLine] = useState<string>(
    initialEndLine ? String(initialEndLine) : ''
  );

  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<CodeExplainResponse | null>(null);

  useEffect(() => {
    if (isOpen) {
      setStartLine(initialStartLine ? String(initialStartLine) : '');
      setEndLine(initialEndLine ? String(initialEndLine) : '');
      setError(null);
      setResult(null);
    }
  }, [isOpen, filePath, initialStartLine, initialEndLine, symbolName]);

  if (!isOpen) return null;

  const handleExplain = async (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    const parsedStart = startLine.trim() ? Number(startLine) : undefined;
    const parsedEnd = endLine.trim() ? Number(endLine) : undefined;

    if (parsedStart !== undefined && (Number.isNaN(parsedStart) || parsedStart < 1)) {
      setError('Start line must be 1 or greater.');
      return;
    }
    if (parsedEnd !== undefined && (Number.isNaN(parsedEnd) || parsedEnd < 1)) {
      setError('End line must be 1 or greater.');
      return;
    }
    if (parsedStart !== undefined && parsedEnd !== undefined && parsedEnd < parsedStart) {
      setError('End line must be greater than or equal to start line.');
      return;
    }

    setIsLoading(true);
    setError(null);

    try {
      const data = await aiService.explainCode(repositoryId, {
        file_path: filePath,
        start_line: parsedStart,
        end_line: parsedEnd,
        question: question.trim() || undefined,
        explanation_style: style,
      });
      setResult(data);
    } catch (err) {
      setError(extractAIErrorMessage(err, 'Failed to generate code explanation.'));
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm"
      onClick={onClose}
    >
      <div
        className="bg-surface-darker border border-surface-border rounded-3xl w-full max-w-3xl max-h-[88vh] shadow-2xl flex flex-col overflow-hidden"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="px-6 py-4 border-b border-surface-border/60 flex items-center justify-between bg-surface-dark/50">
          <div className="min-w-0">
            <div className="flex items-center space-x-2">
              <Sparkles className="w-4 h-4 text-brand-400 flex-shrink-0" />
              <h3 className="text-sm font-bold text-slate-100 truncate">
                AI Code Explanation{symbolName ? ` — ${symbolName}` : ''}
              </h3>
            </div>
            <p className="text-xs font-mono text-slate-400 truncate mt-0.5">
              {filePath} {totalLines > 0 ? `(${totalLines} lines)` : ''}
            </p>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="p-1.5 rounded-xl text-slate-400 hover:text-slate-100 hover:bg-surface-dark cursor-pointer"
            aria-label="Close explanation modal"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Body */}
        <div className="flex-1 overflow-y-auto p-6 space-y-5 custom-scrollbar">
          {/* Request Controls */}
          <form onSubmit={handleExplain} className="space-y-4 bg-surface-dark/40 border border-surface-border/50 rounded-2xl p-4">
            {/* Style + Line Range */}
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div className="flex items-center space-x-1.5">
                <span className="text-xs font-mono text-slate-400 mr-1">Style:</span>
                {(['beginner', 'technical', 'deep'] as ExplanationStyle[]).map((s) => (
                  <button
                    key={s}
                    type="button"
                    onClick={() => setStyle(s)}
                    className={`px-3 py-1 rounded-xl text-xs font-semibold capitalize cursor-pointer transition-colors ${
                      style === s
                        ? 'bg-brand-500 text-surface-darkest'
                        : 'bg-surface-darker text-slate-300 border border-surface-border/60 hover:text-slate-100'
                    }`}
                  >
                    {s}
                  </button>
                ))}
              </div>

              <div className="flex items-center space-x-2 text-xs font-mono">
                <span className="text-slate-400">Lines:</span>
                <input
                  type="number"
                  min={1}
                  max={totalLines || undefined}
                  value={startLine}
                  onChange={(e) => setStartLine(e.target.value)}
                  placeholder="Start"
                  className="w-20 bg-surface-darker border border-surface-border/60 rounded-xl px-2.5 py-1 text-xs text-slate-200 focus:outline-none focus:border-brand-500/50"
                />
                <span className="text-slate-600">–</span>
                <input
                  type="number"
                  min={1}
                  max={totalLines || undefined}
                  value={endLine}
                  onChange={(e) => setEndLine(e.target.value)}
                  placeholder="End"
                  className="w-20 bg-surface-darker border border-surface-border/60 rounded-xl px-2.5 py-1 text-xs text-slate-200 focus:outline-none focus:border-brand-500/50"
                />
              </div>
            </div>

            {/* Question Input */}
            <div className="space-y-2">
              <div className="flex flex-wrap gap-1.5">
                {PRESET_QUESTIONS.map((q) => (
                  <button
                    key={q}
                    type="button"
                    onClick={() => setQuestion(q)}
                    className="text-[11px] px-2.5 py-1 rounded-lg bg-surface-darker border border-surface-border/50 text-slate-400 hover:text-brand-300 hover:border-brand-500/40 cursor-pointer transition-colors"
                  >
                    {q}
                  </button>
                ))}
              </div>
              <div className="flex gap-2">
                <input
                  type="text"
                  value={question}
                  onChange={(e) => setQuestion(e.target.value)}
                  placeholder="Ask a specific question about this code..."
                  className="flex-1 bg-surface-darker border border-surface-border/70 rounded-xl px-3.5 py-2 text-xs text-slate-100 placeholder-slate-500 focus:outline-none focus:border-brand-500/60"
                />
                <button
                  type="submit"
                  disabled={isLoading}
                  className="px-4 py-2 rounded-xl bg-brand-500 hover:bg-brand-400 text-surface-darkest text-xs font-bold flex items-center space-x-1.5 cursor-pointer disabled:opacity-50"
                >
                  {isLoading ? (
                    <>
                      <Loader2 className="w-3.5 h-3.5 animate-spin" />
                      <span>Explaining...</span>
                    </>
                  ) : (
                    <>
                      <Sparkles className="w-3.5 h-3.5" />
                      <span>Explain Code</span>
                    </>
                  )}
                </button>
              </div>
            </div>
          </form>

          {/* Error State */}
          {error && (
            <div className="bg-rose-950/30 border border-rose-800/50 rounded-2xl p-4 flex items-start space-x-3 text-rose-200 text-xs">
              <AlertCircle className="w-4 h-4 text-rose-400 flex-shrink-0 mt-0.5" />
              <span>{error}</span>
            </div>
          )}

          {/* Results */}
          {result && (
            <div className="space-y-4">
              {/* Overview */}
              <div className="bg-surface-dark/40 border border-surface-border/60 rounded-2xl p-4 space-y-2">
                <div className="flex items-center justify-between">
                  <div className="flex items-center space-x-2 text-xs font-mono uppercase text-brand-300 font-semibold">
                    <BookOpen className="w-3.5 h-3.5" />
                    <span>Overview ({result.explanation_style})</span>
                  </div>
                  <span className="text-[10px] font-mono uppercase px-2 py-0.5 rounded-full bg-surface-darker border border-surface-border text-slate-400">
                    {result.language}
                  </span>
                </div>
                <p className="text-sm text-slate-200 leading-relaxed">{result.overview}</p>
              </div>

              {/* Inputs & Outputs */}
              {(result.inputs || result.outputs) && (
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                  {result.inputs && (
                    <div className="bg-surface-dark/40 border border-surface-border/50 rounded-2xl p-3.5 space-y-1">
                      <div className="text-[11px] font-mono uppercase text-slate-400 font-semibold">
                        Inputs / Parameters
                      </div>
                      <p className="text-xs text-slate-300 leading-relaxed">{result.inputs}</p>
                    </div>
                  )}
                  {result.outputs && (
                    <div className="bg-surface-dark/40 border border-surface-border/50 rounded-2xl p-3.5 space-y-1">
                      <div className="text-[11px] font-mono uppercase text-slate-400 font-semibold">
                        Outputs / Return Value
                      </div>
                      <p className="text-xs text-slate-300 leading-relaxed">{result.outputs}</p>
                    </div>
                  )}
                </div>
              )}

              {/* Step-by-Step */}
              {result.step_by_step.length > 0 && (
                <div className="bg-surface-dark/40 border border-surface-border/50 rounded-2xl p-4 space-y-2">
                  <div className="flex items-center space-x-2 text-xs font-mono uppercase text-slate-300 font-semibold">
                    <ListChecks className="w-3.5 h-3.5 text-brand-400" />
                    <span>Step-by-Step Breakdown</span>
                  </div>
                  <ul className="space-y-1.5 text-xs text-slate-300 list-disc list-inside">
                    {result.step_by_step.map((step, i) => (
                      <li key={i} className="leading-relaxed">
                        {step}
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              {/* Edge Cases & Side Effects */}
              {(result.edge_cases.length > 0 || result.side_effects.length > 0) && (
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                  {result.side_effects.length > 0 && (
                    <div className="bg-surface-dark/40 border border-surface-border/50 rounded-2xl p-3.5 space-y-1.5">
                      <div className="text-[11px] font-mono uppercase text-slate-400 font-semibold">
                        Side Effects
                      </div>
                      <ul className="space-y-1 text-xs text-slate-300 list-disc list-inside">
                        {result.side_effects.map((item, i) => (
                          <li key={i}>{item}</li>
                        ))}
                      </ul>
                    </div>
                  )}
                  {result.edge_cases.length > 0 && (
                    <div className="bg-surface-dark/40 border border-surface-border/50 rounded-2xl p-3.5 space-y-1.5">
                      <div className="text-[11px] font-mono uppercase text-amber-300 font-semibold">
                        Edge Cases &amp; Risks
                      </div>
                      <ul className="space-y-1 text-xs text-slate-300 list-disc list-inside">
                        {result.edge_cases.map((item, i) => (
                          <li key={i}>{item}</li>
                        ))}
                      </ul>
                    </div>
                  )}
                </div>
              )}

              {/* Related Symbols */}
              {result.related_symbols.length > 0 && (
                <div className="bg-surface-dark/40 border border-surface-border/50 rounded-2xl p-4 space-y-2.5">
                  <div className="flex items-center space-x-2 text-xs font-mono uppercase text-slate-300 font-semibold">
                    <GitBranch className="w-3.5 h-3.5 text-brand-400" />
                    <span>Related Repository Symbols ({result.related_symbols.length})</span>
                  </div>
                  <div className="space-y-2">
                    {result.related_symbols.map((rel, i) => (
                      <div
                        key={`${rel.file_path}-${rel.name}-${i}`}
                        className="bg-surface-darker/80 border border-surface-border/50 rounded-xl p-2.5 flex items-center justify-between gap-2"
                      >
                        <div className="min-w-0">
                          <div className="text-xs font-mono text-brand-300 font-semibold truncate">
                            {rel.name}{' '}
                            <span className="text-[10px] text-slate-500 font-normal">({rel.kind})</span>
                          </div>
                          <div className="text-[11px] font-mono text-slate-400 truncate">
                            {rel.file_path}:{rel.start_line}–{rel.end_line}
                          </div>
                        </div>
                        {onNavigateToLocation && (
                          <button
                            type="button"
                            onClick={() => {
                              onNavigateToLocation(rel.file_path, rel.start_line);
                              onClose();
                            }}
                            className="text-[11px] font-mono text-brand-400 hover:text-brand-300 flex items-center space-x-1 flex-shrink-0 cursor-pointer"
                          >
                            <span>Open</span>
                            <ArrowUpRight className="w-3 h-3" />
                          </button>
                        )}
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Citations */}
              {result.citations.length > 0 && (
                <div className="bg-surface-dark/40 border border-surface-border/50 rounded-2xl p-4 space-y-2">
                  <div className="text-xs font-mono uppercase text-slate-300 font-semibold">
                    Citations ({result.citations.length})
                  </div>
                  <div className="space-y-1.5">
                    {result.citations.map((c) => (
                      <div
                        key={c.source_id}
                        className="flex items-center justify-between text-xs font-mono bg-surface-darker/70 border border-surface-border/40 rounded-xl px-3 py-2"
                      >
                        <span className="text-slate-300 truncate">
                          {c.file_path} (L{c.start_line}–L{c.end_line})
                          {c.symbol_name ? ` — ${c.symbol_name}` : ''}
                        </span>
                        {onNavigateToLocation && (
                          <button
                            type="button"
                            onClick={() => {
                              onNavigateToLocation(c.file_path, c.start_line);
                              onClose();
                            }}
                            className="text-brand-400 hover:text-brand-300 ml-2 flex-shrink-0 cursor-pointer"
                          >
                            View
                          </button>
                        )}
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Limitations */}
              {result.limitations.length > 0 && (
                <div className="bg-amber-950/30 border border-amber-800/50 rounded-2xl p-4 space-y-1.5">
                  <div className="flex items-center space-x-2 text-xs font-mono uppercase text-amber-300 font-semibold">
                    <AlertTriangle className="w-3.5 h-3.5" />
                    <span>Limitations / Missing Context</span>
                  </div>
                  <ul className="space-y-1 text-xs text-amber-200/90 list-disc list-inside">
                    {result.limitations.map((lim, i) => (
                      <li key={i}>{lim}</li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
