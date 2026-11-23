import React from 'react';
import { AgentTask } from '../../../types/agent';
import { CheckCircle2, Clock, Loader2, XCircle, Wrench } from 'lucide-react';

interface TaskTimelineProps {
  tasks: AgentTask[];
}

export const TaskTimeline: React.FC<TaskTimelineProps> = ({ tasks }) => {
  if (!tasks || tasks.length === 0) {
    return (
      <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-8 text-center text-slate-400">
        <Clock className="mx-auto h-8 w-8 text-slate-600 mb-2" />
        <p className="text-sm">No agent tasks scheduled yet.</p>
      </div>
    );
  }

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'COMPLETED':
        return <CheckCircle2 className="h-4 w-4 text-emerald-400" />;
      case 'RUNNING':
        return <Loader2 className="h-4 w-4 animate-spin text-indigo-400" />;
      case 'FAILED':
        return <XCircle className="h-4 w-4 text-rose-400" />;
      default:
        return <Clock className="h-4 w-4 text-slate-500" />;
    }
  };

  const getStatusClass = (status: string) => {
    switch (status) {
      case 'COMPLETED':
        return 'bg-emerald-500/10 text-emerald-400 border-emerald-500/30';
      case 'RUNNING':
        return 'bg-indigo-500/10 text-indigo-400 border-indigo-500/30';
      case 'FAILED':
        return 'bg-rose-500/10 text-rose-400 border-rose-500/30';
      default:
        return 'bg-slate-800 text-slate-400 border-slate-700';
    }
  };

  return (
    <div className="space-y-3">
      {tasks.map((task) => (
        <div
          key={task.id}
          className="rounded-xl border border-slate-800 bg-slate-900/80 p-4 shadow-sm transition hover:border-slate-700"
        >
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-3">
              {getStatusIcon(task.status)}
              <div>
                <h4 className="text-sm font-semibold text-slate-100">
                  {task.agent_role.replace('_', ' ').toUpperCase()} AGENT
                </h4>
                <p className="text-xs text-slate-400">
                  {task.started_at ? `Started at ${new Date(task.started_at).toLocaleTimeString()}` : 'Awaiting dispatch'}
                </p>
              </div>
            </div>

            <div className="flex items-center space-x-3">
              <span className={`rounded-full border px-2.5 py-0.5 text-[11px] font-medium ${getStatusClass(task.status)}`}>
                {task.status}
              </span>
              <div className="text-right text-xs">
                <span className="text-slate-400">Tokens: </span>
                <span className="font-mono text-slate-200">{task.tokens.toLocaleString()}</span>
              </div>
            </div>
          </div>

          {task.findings && task.findings.length > 0 && (
            <div className="mt-3 border-t border-slate-800/80 pt-2.5">
              <span className="text-xs font-medium text-slate-400">
                Discovered {task.findings.length} findings:
              </span>
              <div className="mt-1 flex flex-wrap gap-1.5">
                {task.findings.slice(0, 4).map((f) => (
                  <span
                    key={f.id}
                    className="inline-flex items-center rounded bg-slate-800 px-2 py-0.5 text-[10px] text-slate-300"
                  >
                    <span className="mr-1 h-1.5 w-1.5 rounded-full bg-indigo-400" />
                    {f.title.slice(0, 40)}...
                  </span>
                ))}
              </div>
            </div>
          )}

          {task.tool_calls && task.tool_calls.length > 0 && (
            <div className="mt-2.5 flex items-center space-x-2 text-[11px] text-slate-500">
              <Wrench className="h-3 w-3" />
              <span>{task.tool_calls.length} tool calls executed ({task.tool_calls.map((t) => t.tool).join(', ')})</span>
            </div>
          )}
        </div>
      ))}
    </div>
  );
};
