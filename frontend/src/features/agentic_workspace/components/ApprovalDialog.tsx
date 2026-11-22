import React, { useState } from 'react';
import { AnalysisPlan } from '../../../types/agent';
import { AlertTriangle, CheckCircle, Shield, X } from 'lucide-react';

interface ApprovalDialogProps {
  isOpen: boolean;
  plan: AnalysisPlan;
  onApprove: (comment: string) => void;
  onCancel: () => void;
  isSubmitting?: boolean;
}

export const ApprovalDialog: React.FC<ApprovalDialogProps> = ({
  isOpen,
  plan,
  onApprove,
  onCancel,
  isSubmitting = false,
}) => {
  const [comment, setComment] = useState('Approved by repository maintainer');

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4 backdrop-blur-sm">
      <div className="w-full max-w-2xl rounded-xl border border-slate-700 bg-slate-900 p-6 shadow-2xl text-slate-100">
        <div className="flex items-center justify-between border-b border-slate-800 pb-4">
          <div className="flex items-center space-x-3">
            <div className="rounded-lg bg-amber-500/10 p-2 text-amber-400">
              <Shield className="h-6 w-6" />
            </div>
            <div>
              <h2 className="text-lg font-semibold tracking-tight">Human Approval Gate (M1)</h2>
              <p className="text-xs text-slate-400">Review plan before autonomous execution begins</p>
            </div>
          </div>
          <button
            onClick={onCancel}
            className="rounded-lg p-1.5 text-slate-400 hover:bg-slate-800 hover:text-slate-200"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        <div className="my-5 space-y-4">
          <div className="rounded-lg border border-amber-500/20 bg-amber-950/20 p-3.5 text-sm text-amber-200">
            <div className="flex items-start space-x-2.5">
              <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-amber-400" />
              <div>
                <p className="font-medium">Plan authorization required</p>
                <p className="mt-1 text-xs text-amber-300/80">
                  {plan.approval_reason || 'This run requires explicit verification of planned tools and estimated budget.'}
                </p>
              </div>
            </div>
          </div>

          <div className="grid grid-cols-2 gap-3 text-xs">
            <div className="rounded-lg border border-slate-800 bg-slate-800/40 p-3">
              <span className="text-slate-400">Estimated Tokens:</span>
              <p className="text-sm font-semibold text-slate-100">{plan.estimated_total_tokens.toLocaleString()}</p>
            </div>
            <div className="rounded-lg border border-slate-800 bg-slate-800/40 p-3">
              <span className="text-slate-400">Estimated Cost:</span>
              <p className="text-sm font-semibold text-emerald-400">${plan.estimated_cost_usd.toFixed(4)} USD</p>
            </div>
          </div>

          <div>
            <h4 className="mb-2 text-xs font-semibold uppercase tracking-wider text-slate-400">Planned Steps</h4>
            <div className="max-h-48 space-y-2 overflow-y-auto pr-1">
              {plan.steps.map((step, idx) => (
                <div
                  key={step.step_id}
                  className="flex items-center justify-between rounded-lg border border-slate-800 bg-slate-800/50 p-2.5 text-xs"
                >
                  <div className="flex items-center space-x-2.5">
                    <span className="flex h-5 w-5 items-center justify-center rounded-full bg-slate-700 text-[10px] font-bold text-slate-300">
                      {idx + 1}
                    </span>
                    <div>
                      <p className="font-medium text-slate-200">{step.title}</p>
                      <p className="text-[11px] text-slate-400">{step.description}</p>
                    </div>
                  </div>
                  <span className="rounded bg-slate-700/60 px-2 py-0.5 text-[10px] font-mono text-slate-300">
                    {step.permission_level}
                  </span>
                </div>
              ))}
            </div>
          </div>

          <div>
            <label className="block text-xs font-medium text-slate-400 mb-1">Approval Note / Audit Trail</label>
            <input
              type="text"
              value={comment}
              onChange={(e) => setComment(e.target.value)}
              className="w-full rounded-lg border border-slate-700 bg-slate-800 px-3 py-2 text-xs text-slate-200 focus:border-indigo-500 focus:outline-none"
              placeholder="Reason for approval"
            />
          </div>
        </div>

        <div className="flex items-center justify-end space-x-3 border-t border-slate-800 pt-4">
          <button
            onClick={onCancel}
            disabled={isSubmitting}
            className="rounded-lg border border-slate-700 px-4 py-2 text-xs font-medium text-slate-300 hover:bg-slate-800 transition"
          >
            Cancel Run
          </button>
          <button
            onClick={() => onApprove(comment)}
            disabled={isSubmitting}
            className="flex items-center space-x-1.5 rounded-lg bg-indigo-600 px-4 py-2 text-xs font-medium text-white hover:bg-indigo-500 transition shadow-lg shadow-indigo-600/30"
          >
            <CheckCircle className="h-4 w-4" />
            <span>{isSubmitting ? 'Approving...' : 'Approve & Execute Plan'}</span>
          </button>
        </div>
      </div>
    </div>
  );
};
