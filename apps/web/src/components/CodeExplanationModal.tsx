import React, { useState } from 'react';
import { Sparkles, HelpCircle, AlertCircle, Loader2, BookOpen, AlertTriangle } from 'lucide-react';
import { aiService } from '../services/aiService';
import { ExplanationResponse } from '../types/ai';
import { Repository } from '../types/repository';

interface CodeExplanationModalProps {
  repository: Repository;
  initialCode?: string;
  initialFilePath?: string;
  initialStartLine?: number;
  initialEndLine?: number;
  onClose: () => void;
}

export const CodeExplanationModal: React.FC<CodeExplanationModalProps> = ({
  repository,
  initialCode = '',
  initialFilePath = '',
  initialStartLine,
  initialEndLine,
  onClose,
}) => {
  const [code] = useState(initialCode);
  const [filePath] = useState(initialFilePath);
  const [question, setQuestion] = useState('');
  const [style, setStyle] = useState<'beginner' | 'technical' | 'deep'>('technical');
  const [explanation, setExplanation] = useState<ExplanationResponse | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const quickQuestions = [
    'What does this code do?',
    'Explain this code line by line.',
    'Why is this condition used?',
    'What will happen if this input is provided?',
    'Are there any potential bugs or edge cases?',
  ];

  const handleExplain = async (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    if (!code.trim() && !filePath.trim()) return;

    setIsLoading(true);
    setError(null);

    try {
      const res = await aiService.explainCode(repository.id, {
        code: code.trim() || undefined,
        file_path: filePath.trim() || undefined,
        start_line: initialStartLine,
        end_line: initialEndLine,
        question: question.trim() || undefined,
        explanation_style: style,
      });

      setExplanation(res);
    } catch (err: unknown) {
      let msg = 'Failed to generate code explanation.';
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
              <Sparkles className="w-4 h-4" />
            </div>
            <div>
              <h2 className="text-sm font-semibold text-slate-100">AI Code Explanation</h2>
              <p className="text-xs text-slate-400 font-mono truncate max-w-md">
                {filePath ? `${repository.name} • ${filePath}` : `${repository.owner}/${repository.name}`}
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="text-slate-400 hover:text-slate-200 text-sm px-2.5 py-1 rounded-lg hover:bg-surface-dark transition-colors cursor-pointer"
          >
            ✕
          </button>
        </div>

        {/* Content Body */}
        <div className="flex-1 overflow-y-auto p-6 space-y-6">
          {/* Selected Code Preview Card (Read-only view of what was selected) */}
          <div className="rounded-2xl border border-surface-border/70 bg-surface-dark/50 overflow-hidden space-y-0">
            <div className="px-4 py-2 bg-surface-darker/80 border-b border-surface-border/50 flex items-center justify-between text-xs font-mono">
              <span className="text-brand-300 font-semibold flex items-center gap-1.5">
                <BookOpen className="w-3.5 h-3.5" />
                <span>Selected Code for Analysis</span>
              </span>
              {filePath && (
                <span className="text-slate-400">
                  {filePath}{initialStartLine ? `:${initialStartLine}-${initialEndLine || ''}` : ''}
                </span>
              )}
            </div>
            <pre className="p-4 text-xs font-mono text-slate-200 overflow-x-auto max-h-48 leading-relaxed whitespace-pre">
              {code || '(No code snippet selected)'}
            </pre>
          </div>

          {/* Configuration Form */}
          <form onSubmit={handleExplain} className="space-y-4">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <label className="block text-xs font-medium text-slate-300 mb-1.5">
                  Explanation Style
                </label>
                <div className="grid grid-cols-3 gap-2">
                  {(['beginner', 'technical', 'deep'] as const).map((s) => (
                    <button
                      key={s}
                      type="button"
                      onClick={() => setStyle(s)}
                      className={`py-1.5 px-3 rounded-xl text-xs capitalize transition-colors cursor-pointer ${
                        style === s
                          ? 'bg-brand-500/20 text-brand-300 border border-brand-500/40 font-semibold'
                          : 'bg-surface-dark text-slate-400 hover:text-slate-200 border border-surface-border/60'
                      }`}
                    >
                      {s}
                    </button>
                  ))}
                </div>
              </div>

              <div>
                <label className="block text-xs font-medium text-slate-300 mb-1.5">
                  Active Context File
                </label>
                <div className="px-3 py-2 bg-surface-dark rounded-xl border border-surface-border text-xs font-mono text-slate-300 truncate">
                  {filePath || 'Context automatically linked from Code Explorer'}
                </div>
              </div>
            </div>

            <div>
              <label className="block text-xs font-medium text-slate-300 mb-1.5">
                Developer Question
              </label>
              <div className="relative mb-2">
                <HelpCircle className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
                <input
                  type="text"
                  value={question}
                  onChange={(e) => setQuestion(e.target.value)}
                  placeholder="Ask a specific question about this code..."
                  className="w-full bg-surface-dark border border-surface-border/80 focus:border-brand-500 rounded-xl pl-9 pr-4 py-2 text-xs text-slate-100 placeholder-slate-500 focus:outline-none"
                />
              </div>

              {/* Quick Questions Pills */}
              <div className="flex flex-wrap gap-1.5">
                {quickQuestions.map((q) => (
                  <button
                    key={q}
                    type="button"
                    onClick={() => {
                      setQuestion(q);
                    }}
                    className="text-[11px] px-2.5 py-1 rounded-lg bg-surface-dark hover:bg-surface-border/50 text-slate-400 hover:text-slate-200 transition-colors border border-surface-border/50"
                  >
                    {q}
                  </button>
                ))}
              </div>
            </div>

            <div className="flex justify-end pt-2">
              <button
                type="submit"
                disabled={isLoading || (!code.trim() && !filePath.trim())}
                className="px-6 py-2.5 bg-brand-500 hover:bg-brand-400 disabled:opacity-50 text-surface-darkest text-xs font-semibold rounded-xl flex items-center space-x-1.5 transition-colors cursor-pointer shadow-lg shadow-brand-500/10"
              >
                {isLoading ? (
                  <>
                    <Loader2 className="w-3.5 h-3.5 animate-spin" />
                    <span>Analyzing & Explaining...</span>
                  </>
                ) : (
                  <>
                    <Sparkles className="w-3.5 h-3.5" />
                    <span>Explain Code</span>
                  </>
                )}
              </button>
            </div>
          </form>

          {error && (
            <div className="p-4 rounded-xl bg-rose-950/40 border border-rose-800 text-rose-200 text-xs flex items-center space-x-2">
              <AlertCircle className="w-4 h-4 flex-shrink-0" />
              <span>{error}</span>
            </div>
          )}

          {/* Explanation Output Section */}
          {explanation && (
            <div className="space-y-6 pt-4 border-t border-surface-border/60 animate-in fade-in duration-300">
              {/* Overview */}
              <div className="p-4 rounded-xl bg-surface-dark/80 border border-surface-border/70 space-y-2">
                <div className="flex items-center space-x-2 text-brand-300 text-xs font-semibold">
                  <BookOpen className="w-4 h-4" />
                  <span>Overview</span>
                </div>
                <p className="text-xs text-slate-200 leading-relaxed">
                  {explanation.overview}
                </p>
              </div>

              {/* Step by step */}
              {explanation.step_by_step?.length > 0 && (
                <div className="space-y-2">
                  <h3 className="text-xs font-semibold text-slate-200 uppercase tracking-wider font-mono">
                    Execution Steps
                  </h3>
                  <div className="space-y-1.5">
                    {explanation.step_by_step.map((step, idx) => (
                      <div
                        key={idx}
                        className="text-xs text-slate-300 p-2.5 rounded-lg bg-surface-dark/40 border border-surface-border/40 font-mono"
                      >
                        {step}
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Inputs & Outputs */}
              {(explanation.inputs || explanation.outputs) && (
                <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                  {explanation.inputs && (
                    <div className="p-3 bg-surface-dark/60 rounded-xl border border-surface-border/60 space-y-1">
                      <div className="text-[11px] font-mono font-semibold text-slate-400">Inputs / Parameters</div>
                      <div className="text-xs text-slate-200">{explanation.inputs}</div>
                    </div>
                  )}
                  {explanation.outputs && (
                    <div className="p-3 bg-surface-dark/60 rounded-xl border border-surface-border/60 space-y-1">
                      <div className="text-[11px] font-mono font-semibold text-slate-400">Outputs / Return</div>
                      <div className="text-xs text-slate-200">{explanation.outputs}</div>
                    </div>
                  )}
                </div>
              )}

              {/* Edge Cases & Side Effects */}
              {explanation.edge_cases?.length > 0 && (
                <div className="p-4 bg-amber-950/20 border border-amber-800/40 rounded-xl space-y-2">
                  <div className="flex items-center space-x-2 text-amber-300 text-xs font-semibold">
                    <AlertTriangle className="w-4 h-4" />
                    <span>Potential Edge Cases & Bug Risks</span>
                  </div>
                  <ul className="list-disc list-inside text-xs text-slate-300 space-y-1">
                    {explanation.edge_cases.map((ec, idx) => (
                      <li key={idx}>{ec}</li>
                    ))}
                  </ul>
                </div>
              )}

              {/* Citations & Related Symbols */}
              {explanation.related_symbols?.length > 0 && (
                <div className="space-y-2">
                  <h3 className="text-xs font-semibold text-slate-200 uppercase tracking-wider font-mono">
                    Cross-File Context & Dependencies
                  </h3>
                  <div className="grid grid-cols-1 gap-2">
                    {explanation.related_symbols.map((sym, idx) => (
                      <div
                        key={idx}
                        className="p-3 bg-surface-dark/40 border border-surface-border/40 rounded-xl space-y-1 text-xs"
                      >
                        <div className="flex items-center justify-between">
                          <span className="font-mono font-bold text-brand-300">{sym.name} ({sym.kind})</span>
                          <span className="text-slate-400 font-mono text-[11px]">{sym.file_path}:{sym.start_line}-{sym.end_line}</span>
                        </div>
                        <p className="text-slate-400 text-[11px]">{sym.relevance_reason}</p>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
