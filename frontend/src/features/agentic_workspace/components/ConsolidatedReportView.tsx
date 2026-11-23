import React, { useState } from 'react';
import { MultiAgentReport, FindingSeverity } from '../../../types/agent';
import {
  ShieldAlert,
  CheckCircle2,
  GitCompare,
  Flame,
  Search,
  ChevronDown,
  ChevronRight,
  Code2,
} from 'lucide-react';

interface ConsolidatedReportViewProps {
  report: MultiAgentReport;
}

export const ConsolidatedReportView: React.FC<ConsolidatedReportViewProps> = ({ report }) => {
  const [selectedCategory, setSelectedCategory] = useState<string>('ALL');
  const [searchQuery, setSearchQuery] = useState('');
  const [expandedFindingId, setExpandedFindingId] = useState<string | null>(null);

  const getSeverityBadge = (severity: FindingSeverity) => {
    switch (severity) {
      case 'CRITICAL':
        return 'bg-red-500/10 text-red-400 border-red-500/30';
      case 'HIGH':
        return 'bg-amber-500/10 text-amber-400 border-amber-500/30';
      case 'MEDIUM':
        return 'bg-yellow-500/10 text-yellow-400 border-yellow-500/30';
      case 'LOW':
        return 'bg-blue-500/10 text-blue-400 border-blue-500/30';
      default:
        return 'bg-slate-800 text-slate-400 border-slate-700';
    }
  };

  const filteredFindings = report.all_findings.filter((f) => {
    const matchesCategory = selectedCategory === 'ALL' || f.category === selectedCategory;
    const matchesSearch =
      searchQuery === '' ||
      f.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
      f.file_path.toLowerCase().includes(searchQuery.toLowerCase());
    return matchesCategory && matchesSearch;
  });

  return (
    <div className="space-y-6 text-slate-100">
      {/* 1. Metric Cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-4">
          <div className="flex items-center justify-between text-slate-400 text-xs">
            <span>Total Findings</span>
            <ShieldAlert className="h-4 w-4 text-indigo-400" />
          </div>
          <div className="mt-2 text-2xl font-bold">{report.total_findings}</div>
          <p className="text-[11px] text-slate-500 mt-1">Across 4 specialist domains</p>
        </div>

        <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-4">
          <div className="flex items-center justify-between text-slate-400 text-xs">
            <span>Citation Validity</span>
            <CheckCircle2 className="h-4 w-4 text-emerald-400" />
          </div>
          <div className="mt-2 text-2xl font-bold text-emerald-400">
            {report.verification_summary?.validity_percentage ?? 100}%
          </div>
          <p className="text-[11px] text-slate-500 mt-1">
            {report.verification_summary?.passed_checks} of {report.verification_summary?.total_checks} checks passed
          </p>
        </div>

        <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-4">
          <div className="flex items-center justify-between text-slate-400 text-xs">
            <span>Consensus Items</span>
            <Flame className="h-4 w-4 text-amber-400" />
          </div>
          <div className="mt-2 text-2xl font-bold text-amber-400">
            {report.consensus_findings?.length ?? 0}
          </div>
          <p className="text-[11px] text-slate-500 mt-1">Multi-agent confirmed</p>
        </div>

        <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-4">
          <div className="flex items-center justify-between text-slate-400 text-xs">
            <span>Domain Trade-offs</span>
            <GitCompare className="h-4 w-4 text-purple-400" />
          </div>
          <div className="mt-2 text-2xl font-bold text-purple-400">
            {report.disagreements?.length ?? 0}
          </div>
          <p className="text-[11px] text-slate-500 mt-1">Explicit disagreements recorded</p>
        </div>
      </div>

      {/* 2. Disagreements and Trade-offs (Key M1 Requirement) */}
      {report.disagreements && report.disagreements.length > 0 && (
        <div className="rounded-xl border border-purple-500/20 bg-purple-950/10 p-5">
          <div className="flex items-center space-x-2 text-purple-400 mb-3">
            <GitCompare className="h-5 w-5" />
            <h3 className="font-semibold text-sm">Cross-Domain Disagreements & Trade-Off Analysis</h3>
          </div>
          <p className="text-xs text-slate-400 mb-4">
            Under Mastermind M1 specification, conflicting agent positions are explicitly preserved rather than silently averaged out.
          </p>

          <div className="space-y-4">
            {report.disagreements.map((item, idx) => (
              <div
                key={idx}
                className="rounded-lg border border-slate-800 bg-slate-900/80 p-4 text-xs space-y-3"
              >
                <div className="flex items-center justify-between">
                  <h4 className="font-medium text-slate-200">{item.topic}</h4>
                  <span className="rounded bg-purple-500/10 text-purple-300 border border-purple-500/30 px-2 py-0.5 text-[10px]">
                    {item.conflicting_aspect}
                  </span>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                  {Object.entries(item.positions).map(([agentRole, pos]) => (
                    <div
                      key={agentRole}
                      className="rounded border border-slate-800/80 bg-slate-950/60 p-2.5"
                    >
                      <span className="font-bold text-[10px] text-indigo-400 uppercase tracking-wider block mb-1">
                        {agentRole} Perspective
                      </span>
                      <p className="text-slate-300 leading-relaxed">{pos}</p>
                    </div>
                  ))}
                </div>

                <div className="rounded bg-slate-800/50 p-2.5 text-slate-300 border-l-2 border-indigo-500">
                  <span className="font-semibold text-slate-200">Synthesis: </span>
                  {item.trade_off_analysis}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* 3. Consensus Findings */}
      {report.consensus_findings && report.consensus_findings.length > 0 && (
        <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-5">
          <div className="flex items-center space-x-2 text-amber-400 mb-3">
            <Flame className="h-5 w-5" />
            <h3 className="font-semibold text-sm">Consensus Findings</h3>
          </div>
          <div className="space-y-3">
            {report.consensus_findings.map((item, idx) => (
              <div
                key={idx}
                className="rounded-lg border border-slate-800 bg-slate-800/40 p-3.5 text-xs flex flex-col md:flex-row md:items-center justify-between gap-3"
              >
                <div>
                  <div className="flex items-center space-x-2">
                    <span className={`rounded-full border px-2 py-0.5 text-[10px] font-bold ${getSeverityBadge(item.severity)}`}>
                      {item.severity}
                    </span>
                    <span className="font-semibold text-slate-200">{item.title}</span>
                  </div>
                  <p className="text-slate-400 text-[11px] mt-1 font-mono">
                    {item.file_path}:{item.line_start}-{item.line_end}
                  </p>
                  <p className="text-slate-300 text-xs mt-1.5">{item.synthesized_remediation}</p>
                </div>

                <div className="flex items-center space-x-2 shrink-0">
                  <span className="text-[11px] text-slate-400">Supported by:</span>
                  <div className="flex space-x-1">
                    {item.supporting_agents.map((role) => (
                      <span
                        key={role}
                        className="rounded bg-indigo-500/10 text-indigo-300 border border-indigo-500/20 px-1.5 py-0.5 text-[10px]"
                      >
                        {role.slice(0, 4)}
                      </span>
                    ))}
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* 4. Filterable Full Findings List */}
      <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-5">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 mb-4">
          <div>
            <h3 className="font-semibold text-sm">All Discovered Findings ({filteredFindings.length})</h3>
            <p className="text-xs text-slate-400">Individual findings generated by specialized agents with verified line spans</p>
          </div>

          <div className="flex items-center space-x-2">
            <div className="relative">
              <Search className="absolute left-2.5 top-2 h-3.5 w-3.5 text-slate-400" />
              <input
                type="text"
                placeholder="Filter by title or file..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="rounded-lg border border-slate-700 bg-slate-800 pl-8 pr-3 py-1.5 text-xs text-slate-200 focus:outline-none focus:border-indigo-500"
              />
            </div>

            <select
              value={selectedCategory}
              onChange={(e) => setSelectedCategory(e.target.value)}
              className="rounded-lg border border-slate-700 bg-slate-800 px-2.5 py-1.5 text-xs text-slate-200 focus:outline-none focus:border-indigo-500"
            >
              <option value="ALL">All Categories</option>
              <option value="SECURITY">Security</option>
              <option value="CODE_QUALITY">Code Quality</option>
              <option value="ARCHITECTURE">Architecture</option>
              <option value="PERFORMANCE">Performance</option>
            </select>
          </div>
        </div>

        <div className="space-y-2.5">
          {filteredFindings.map((finding) => {
            const isExpanded = expandedFindingId === finding.id;
            return (
              <div
                key={finding.id}
                className="rounded-lg border border-slate-800 bg-slate-900/80 overflow-hidden transition"
              >
                <div
                  onClick={() => setExpandedFindingId(isExpanded ? null : finding.id)}
                  className="flex items-center justify-between p-3.5 cursor-pointer hover:bg-slate-800/40"
                >
                  <div className="flex items-center space-x-3">
                    {isExpanded ? (
                      <ChevronDown className="h-4 w-4 text-slate-400" />
                    ) : (
                      <ChevronRight className="h-4 w-4 text-slate-400" />
                    )}
                    <span className={`rounded-full border px-2 py-0.5 text-[10px] font-bold ${getSeverityBadge(finding.severity)}`}>
                      {finding.severity}
                    </span>
                    <span className="font-medium text-xs text-slate-200">{finding.title}</span>
                  </div>

                  <div className="flex items-center space-x-3 text-xs text-slate-400">
                    <span className="font-mono text-[11px]">{finding.file_path}:{finding.line_start}</span>
                    <span className="rounded bg-slate-800 px-2 py-0.5 text-[10px] text-slate-300">
                      {finding.category}
                    </span>
                  </div>
                </div>

                {isExpanded && (
                  <div className="border-t border-slate-800 p-4 bg-slate-950/40 text-xs space-y-3">
                    <p className="text-slate-300">{finding.description}</p>

                    {finding.remediation && (
                      <div className="rounded bg-slate-800/40 p-2.5 border-l-2 border-emerald-500 text-slate-200">
                        <span className="font-semibold text-emerald-400">Remediation: </span>
                        {finding.remediation}
                      </div>
                    )}

                    {finding.evidence && finding.evidence.length > 0 && (
                      <div>
                        <span className="font-semibold text-slate-400 flex items-center space-x-1.5 mb-1.5">
                          <Code2 className="h-3.5 w-3.5" />
                          <span>Grounded Source Citation ({finding.file_path}:{finding.line_start}-{finding.line_end})</span>
                        </span>
                        <pre className="rounded bg-slate-950 p-3 font-mono text-[11px] text-slate-300 overflow-x-auto border border-slate-800">
                          {finding.evidence[0].snippet}
                        </pre>
                      </div>
                    )}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
};
