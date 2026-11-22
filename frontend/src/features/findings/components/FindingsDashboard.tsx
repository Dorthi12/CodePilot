import React, { useState, useEffect } from 'react';
import {
  AnalysisRunResponse,
  Finding,
  FindingOrigin,
  FindingSeverity,
  FindingStatus,
} from '../../../types/findings';
import { findingsApi } from '../services/findings_api';
import { FindingDetailModal } from './FindingDetailModal';
import {
  AlertCircle,
  AlertTriangle,
  Bug,
  CheckCircle2,
  Clock,
  Code2,
  Filter,
  Play,
  RotateCcw,
  Search,
  Shield,
  ShieldAlert,
  Sparkles,
} from 'lucide-react';

export const FindingsDashboard: React.FC = () => {
  // Run parameters
  const [snapshotId, setSnapshotId] = useState<string>('snap-prod-main');
  const [rulePack, setRulePack] = useState<string>('default');
  const [severityThreshold, setSeverityThreshold] = useState<FindingSeverity>('LOW');
  const [scopePaths, setScopePaths] = useState<string>('');

  // Execution state
  const [isRunning, setIsRunning] = useState<boolean>(false);
  const [activeRun, setActiveRun] = useState<AnalysisRunResponse | null>(null);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  // Findings list and filters
  const [findings, setFindings] = useState<Finding[]>([]);
  const [findingsTotal, setFindingsTotal] = useState<number>(0);
  const [isLoadingFindings, setIsLoadingFindings] = useState<boolean>(false);
  const [searchQuery, setSearchQuery] = useState<string>('');
  const [selectedOrigin, setSelectedOrigin] = useState<string>('ALL');
  const [selectedSeverity, setSelectedSeverity] = useState<string>('ALL');
  const [selectedStatus, setSelectedStatus] = useState<string>('ALL');
  const [selectedCategory, setSelectedCategory] = useState<string>('ALL');

  // Modal inspection
  const [inspectingFinding, setInspectingFinding] = useState<Finding | null>(null);

  // Load findings on initial mount or when snapshot changes
  const fetchFindings = async (offset = 0, append = false) => {
    setIsLoadingFindings(true);
    try {
      const res = await findingsApi.listFindings({
        snapshot_id: snapshotId || undefined,
        origin: selectedOrigin !== 'ALL' ? selectedOrigin : undefined,
        severity: selectedSeverity !== 'ALL' ? selectedSeverity : undefined,
        status: selectedStatus !== 'ALL' ? selectedStatus : undefined,
        category: selectedCategory !== 'ALL' ? selectedCategory : undefined,
        limit: 100,
        offset,
      });
      setFindings((current) => append ? [...current, ...res.items] : res.items);
      setFindingsTotal(res.total);
    } catch (err: any) {
      console.error('Failed to load findings', err);
    } finally {
      setIsLoadingFindings(false);
    }
  };

  useEffect(() => {
    fetchFindings();
  }, [snapshotId, selectedOrigin, selectedSeverity, selectedStatus, selectedCategory]);

  const handleRunAnalysis = async () => {
    setIsRunning(true);
    setErrorMsg(null);
    try {
      const pathsArray = scopePaths.trim()
        ? scopePaths.split(',').map((p) => p.trim())
        : undefined;

      const launchRes = await findingsApi.startQualityRun({
        snapshot_id: snapshotId,
        rule_pack: rulePack,
        severity_threshold: severityThreshold,
        scope: { paths: pathsArray },
        repository_id: 'default-repo',
      });

      // Runs execute off the request path. Poll their durable status and keep
      // the coverage panel current while the analyzers work.
      let runData = await findingsApi.getAnalysisRun(launchRes.run_id);
      setActiveRun(runData);
      for (let attempt = 0; attempt < 60 && ['CREATED', 'RUNNING'].includes(runData.status); attempt += 1) {
        await new Promise((resolve) => window.setTimeout(resolve, 1000));
        runData = await findingsApi.getAnalysisRun(launchRes.run_id);
        setActiveRun(runData);
      }

      // Refresh findings list
      await fetchFindings();
    } catch (err: any) {
      setErrorMsg(
        err.response?.data?.detail || err.message || 'Failed to execute code quality analysis.'
      );
    } finally {
      setIsRunning(false);
    }
  };

  const handleStatusUpdated = (updated: Finding) => {
    setFindings((prev) =>
      prev.map((f) => (f.id === updated.id ? updated : f))
    );
  };

  // Client-side text filter
  const filteredFindings = findings.filter((f) => {
    if (!searchQuery.trim()) return true;
    const q = searchQuery.toLowerCase();
    return (
      f.title.toLowerCase().includes(q) ||
      f.rule_id.toLowerCase().includes(q) ||
      f.file_path.toLowerCase().includes(q) ||
      f.category.toLowerCase().includes(q)
    );
  });

  const getOriginBadge = (origin: FindingOrigin) => {
    switch (origin) {
      case 'STATIC_TOOL':
        return (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-semibold bg-blue-500/10 text-blue-400 border border-blue-500/20">
            <Code2 className="w-3 h-3" /> Static Tool
          </span>
        );
      case 'GRAPH_RULE':
        return (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-semibold bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
            <CheckCircle2 className="w-3 h-3" /> Graph Rule
          </span>
        );
      case 'AI_HYPOTHESIS':
        return (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-semibold bg-purple-500/10 text-purple-400 border border-purple-500/20">
            <Sparkles className="w-3 h-3" /> AI Hypothesis
          </span>
        );
      case 'CONFIRMED':
        return (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-semibold bg-rose-500/10 text-rose-400 border border-rose-500/20">
            <ShieldAlert className="w-3 h-3" /> Confirmed
          </span>
        );
    }
  };

  const getSeverityBadge = (severity: FindingSeverity) => {
    const colors: Record<FindingSeverity, string> = {
      CRITICAL: 'bg-rose-500/20 text-rose-300 border-rose-500/30',
      HIGH: 'bg-orange-500/20 text-orange-300 border-orange-500/30',
      MEDIUM: 'bg-amber-500/20 text-amber-300 border-amber-500/30',
      LOW: 'bg-sky-500/20 text-sky-300 border-sky-500/30',
      INFO: 'bg-slate-500/20 text-slate-300 border-slate-500/30',
    };
    return (
      <span
        className={`px-2 py-0.5 rounded text-[10px] font-bold border uppercase tracking-wider ${colors[severity]}`}
      >
        {severity}
      </span>
    );
  };

  return (
    <div className="max-w-7xl mx-auto p-6 space-y-6">
      {/* Top Banner */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 pb-4 border-b border-slate-800">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-2xl font-bold tracking-tight text-white flex items-center gap-2">
              <Bug className="w-6 h-6 text-blue-400" /> Bug and Code Smell Detection
            </h1>
            <span className="px-2 py-0.5 rounded text-[11px] font-semibold bg-blue-500/10 text-blue-400 border border-blue-500/20">
              Feature A3
            </span>
          </div>
          <p className="text-sm text-slate-400 mt-1">
            Deterministic AST analysis, graph-based maintainability rules, and anti-tamper finding triage.
          </p>
        </div>

        <button
          onClick={fetchFindings}
          className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium bg-slate-800 text-slate-300 hover:text-white hover:bg-slate-700 transition border border-slate-700 self-start md:self-auto"
        >
          <RotateCcw className="w-3.5 h-3.5" /> Refresh Findings
        </button>
      </div>

      {/* Analysis Launch Form Card */}
      <div className="bg-slate-900 border border-slate-800 rounded-xl p-5 shadow-lg space-y-4">
        <h3 className="text-sm font-semibold text-slate-200 uppercase tracking-wider flex items-center gap-2">
          <Play className="w-4 h-4 text-emerald-400" /> Start Code Quality Analysis Run
        </h3>

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          <div className="space-y-1">
            <label className="text-xs text-slate-400 font-medium">Snapshot ID</label>
            <input
              type="text"
              value={snapshotId}
              onChange={(e) => setSnapshotId(e.target.value)}
              className="w-full px-3 py-2 bg-slate-950 border border-slate-800 rounded-lg text-xs text-slate-200 focus:outline-none focus:border-blue-500 font-mono"
            />
          </div>

          <div className="space-y-1">
            <label className="text-xs text-slate-400 font-medium">Rule Pack</label>
            <select
              value={rulePack}
              onChange={(e) => setRulePack(e.target.value)}
              className="w-full px-3 py-2 bg-slate-950 border border-slate-800 rounded-lg text-xs text-slate-200 focus:outline-none focus:border-blue-500"
            >
              <option value="default">Default Rule Pack</option>
              <option value="strict">Strict (Lower Thresholds)</option>
              <option value="lenient">Lenient (Tolerant)</option>
            </select>
          </div>

          <div className="space-y-1">
            <label className="text-xs text-slate-400 font-medium">Severity Floor</label>
            <select
              value={severityThreshold}
              onChange={(e) => setSeverityThreshold(e.target.value as FindingSeverity)}
              className="w-full px-3 py-2 bg-slate-950 border border-slate-800 rounded-lg text-xs text-slate-200 focus:outline-none focus:border-blue-500"
            >
              <option value="INFO">INFO & Above</option>
              <option value="LOW">LOW & Above</option>
              <option value="MEDIUM">MEDIUM & Above</option>
              <option value="HIGH">HIGH & Above</option>
              <option value="CRITICAL">CRITICAL Only</option>
            </select>
          </div>

          <div className="space-y-1">
            <label className="text-xs text-slate-400 font-medium">Path Scope (Optional)</label>
            <input
              type="text"
              placeholder="e.g. app/**, src/services/*"
              value={scopePaths}
              onChange={(e) => setScopePaths(e.target.value)}
              className="w-full px-3 py-2 bg-slate-950 border border-slate-800 rounded-lg text-xs text-slate-200 focus:outline-none focus:border-blue-500"
            />
          </div>
        </div>

        <div className="flex items-center justify-between pt-2">
          <div className="text-xs text-slate-400">
            Runs 11 graph rules + AST bug detectors with sub-second content-hash cache.
          </div>
          <button
            onClick={handleRunAnalysis}
            disabled={isRunning}
            className="flex items-center gap-2 px-5 py-2 rounded-lg text-xs font-semibold bg-blue-600 hover:bg-blue-500 text-white disabled:opacity-50 transition shadow"
          >
            {isRunning ? (
              <>
                <div className="w-3.5 h-3.5 border-2 border-white/20 border-t-white rounded-full animate-spin" />
                Analyzing Snapshot...
              </>
            ) : (
              <>
                <Play className="w-3.5 h-3.5" /> Execute Quality Run
              </>
            )}
          </button>
        </div>

        {errorMsg && (
          <div className="p-3 rounded-lg bg-rose-500/10 border border-rose-500/30 text-rose-400 text-xs">
            {errorMsg}
          </div>
        )}
      </div>

      {/* Metric Breakdown Cards */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
        <div className="bg-slate-900 border border-slate-800 rounded-xl p-4">
          <div className="text-xs font-medium text-rose-400 uppercase tracking-wider flex items-center justify-between">
            <span>Critical Defects</span>
            <ShieldAlert className="w-4 h-4 text-rose-500" />
          </div>
          <div className="text-2xl font-bold text-white mt-1">
            {findings.filter((f) => f.severity === 'CRITICAL').length}
          </div>
        </div>

        <div className="bg-slate-900 border border-slate-800 rounded-xl p-4">
          <div className="text-xs font-medium text-orange-400 uppercase tracking-wider flex items-center justify-between">
            <span>High Severity</span>
            <AlertTriangle className="w-4 h-4 text-orange-500" />
          </div>
          <div className="text-2xl font-bold text-white mt-1">
            {findings.filter((f) => f.severity === 'HIGH').length}
          </div>
        </div>

        <div className="bg-slate-900 border border-slate-800 rounded-xl p-4">
          <div className="text-xs font-medium text-amber-400 uppercase tracking-wider flex items-center justify-between">
            <span>Medium / Smells</span>
            <AlertCircle className="w-4 h-4 text-amber-500" />
          </div>
          <div className="text-2xl font-bold text-white mt-1">
            {findings.filter((f) => f.severity === 'MEDIUM').length}
          </div>
        </div>

        <div className="bg-slate-900 border border-slate-800 rounded-xl p-4">
          <div className="text-xs font-medium text-emerald-400 uppercase tracking-wider flex items-center justify-between">
            <span>Total Findings</span>
            <CheckCircle2 className="w-4 h-4 text-emerald-500" />
          </div>
          <div className="text-2xl font-bold text-white mt-1">{findings.length}</div>
        </div>
      </div>

      {/* Tool Execution Coverage (When available) */}
      {activeRun && activeRun.tool_coverage && (
        <div className="bg-slate-900/60 border border-slate-800 rounded-xl p-4 space-y-2">
          <div className="text-xs font-semibold text-slate-300 uppercase tracking-wider">
            Tool Execution & Coverage Report
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            {activeRun.tool_coverage.map((tc) => (
              <div
                key={tc.tool}
                className="p-3 rounded-lg bg-slate-950/60 border border-slate-800 flex items-center justify-between text-xs"
              >
                <div>
                  <span className="font-semibold text-slate-200">{tc.tool}</span>
                  <span className="text-slate-500 ml-1.5">v{tc.version}</span>
                  <div className="text-slate-400 text-[11px] mt-0.5">
                    Scanned {tc.files_scanned} files • {tc.rules_run} rules • Found {tc.findings_count}
                  </div>
                </div>
                <div className="text-right">
                  <span
                    className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                      tc.status === 'SUCCESS'
                        ? 'bg-emerald-500/20 text-emerald-300'
                        : 'bg-rose-500/20 text-rose-300'
                    }`}
                  >
                    {tc.status}
                  </span>
                  <div className="text-slate-500 text-[11px] mt-0.5">{tc.duration_ms} ms</div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Search & Filter Toolbar */}
      <div className="flex flex-col md:flex-row items-stretch md:items-center justify-between gap-3 bg-slate-900 p-3 rounded-xl border border-slate-800">
        <div className="relative flex-1">
          <Search className="w-4 h-4 absolute left-3 top-2.5 text-slate-500" />
          <input
            type="text"
            placeholder="Search findings by title, rule ID, path..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full pl-9 pr-4 py-1.5 bg-slate-950 border border-slate-800 rounded-lg text-xs text-slate-200 focus:outline-none focus:border-blue-500 placeholder-slate-500"
          />
        </div>

        <div className="flex items-center gap-2 flex-wrap">
          {/* Origin filter */}
          <select
            value={selectedOrigin}
            onChange={(e) => setSelectedOrigin(e.target.value)}
            className="px-2.5 py-1.5 bg-slate-950 border border-slate-800 rounded-lg text-xs text-slate-300 focus:outline-none"
          >
            <option value="ALL">All Origins</option>
            <option value="STATIC_TOOL">Static Tool</option>
            <option value="GRAPH_RULE">Graph Metric Rule</option>
            <option value="AI_HYPOTHESIS">AI Hypothesis</option>
            <option value="CONFIRMED">Confirmed Defect</option>
          </select>

          {/* Severity filter */}
          <select
            value={selectedSeverity}
            onChange={(e) => setSelectedSeverity(e.target.value)}
            className="px-2.5 py-1.5 bg-slate-950 border border-slate-800 rounded-lg text-xs text-slate-300 focus:outline-none"
          >
            <option value="ALL">All Severities</option>
            <option value="CRITICAL">Critical</option>
            <option value="HIGH">High</option>
            <option value="MEDIUM">Medium</option>
            <option value="LOW">Low</option>
            <option value="INFO">Info</option>
          </select>

          {/* Status filter */}
          <select
            value={selectedStatus}
            onChange={(e) => setSelectedStatus(e.target.value)}
            className="px-2.5 py-1.5 bg-slate-950 border border-slate-800 rounded-lg text-xs text-slate-300 focus:outline-none"
          >
            <option value="ALL">All Statuses</option>
            <option value="OPEN">Open</option>
            <option value="ACKNOWLEDGED">Acknowledged</option>
            <option value="FALSE_POSITIVE">False Positive</option>
            <option value="ACCEPTED_RISK">Accepted Risk</option>
          </select>
        </div>
      </div>

      {/* Findings Table */}
      <div className="bg-slate-900 border border-slate-800 rounded-xl overflow-hidden shadow-xl">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs text-slate-300">
            <thead className="bg-slate-950/80 text-slate-400 font-semibold border-b border-slate-800">
              <tr>
                <th className="py-3 px-4">Severity</th>
                <th className="py-3 px-4">Origin</th>
                <th className="py-3 px-4">Rule / ID</th>
                <th className="py-3 px-4">Title & Location</th>
                <th className="py-3 px-4">Category</th>
                <th className="py-3 px-4">Status</th>
                <th className="py-3 px-4 text-right">Action</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/60 font-sans">
              {isLoadingFindings ? (
                <tr>
                  <td colSpan={7} className="text-center py-10 text-slate-500">
                    Loading repository findings...
                  </td>
                </tr>
              ) : filteredFindings.length === 0 ? (
                <tr>
                  <td colSpan={7} className="text-center py-12 text-slate-500">
                    No findings match the current criteria. Run an analysis above to inspect the codebase!
                  </td>
                </tr>
              ) : (
                filteredFindings.map((finding) => (
                  <tr
                    key={finding.id}
                    className="hover:bg-slate-800/40 transition group cursor-pointer"
                    onClick={() => setInspectingFinding(finding)}
                  >
                    <td className="py-3 px-4">{getSeverityBadge(finding.severity)}</td>
                    <td className="py-3 px-4">{getOriginBadge(finding.origin)}</td>
                    <td className="py-3 px-4 font-mono font-medium text-slate-300">
                      {finding.rule_id}
                    </td>
                    <td className="py-3 px-4 max-w-md">
                      <div className="font-semibold text-slate-100 truncate group-hover:text-blue-400 transition">
                        {finding.title}
                      </div>
                      <div className="text-[11px] text-slate-500 font-mono truncate">
                        {finding.file_path}:{finding.line_start}–{finding.line_end}
                      </div>
                    </td>
                    <td className="py-3 px-4">
                      <span className="text-[11px] font-mono text-slate-400">
                        {finding.category}
                      </span>
                    </td>
                    <td className="py-3 px-4">
                      <span
                        className={`px-2 py-0.5 rounded text-[10px] font-medium ${
                          finding.status === 'OPEN'
                            ? 'bg-blue-500/10 text-blue-400'
                            : finding.status === 'ACKNOWLEDGED'
                            ? 'bg-amber-500/10 text-amber-400'
                            : finding.status === 'FALSE_POSITIVE'
                            ? 'bg-slate-700 text-slate-300'
                            : 'bg-emerald-500/10 text-emerald-400'
                        }`}
                      >
                        {finding.status.replace('_', ' ')}
                      </span>
                    </td>
                    <td className="py-3 px-4 text-right">
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          setInspectingFinding(finding);
                        }}
                        className="px-2.5 py-1 rounded bg-slate-800 hover:bg-slate-700 text-slate-200 text-[11px] font-medium transition border border-slate-700"
                      >
                        Inspect
                      </button>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>
      <div className="flex items-center justify-between text-xs text-slate-500">
        <span>Showing {findings.length} of {findingsTotal} findings</span>
        {findings.length < findingsTotal && (
          <button
            onClick={() => fetchFindings(findings.length, true)}
            disabled={isLoadingFindings}
            className="rounded-lg border border-slate-700 px-3 py-1.5 text-slate-300 hover:bg-slate-800 disabled:opacity-50"
          >
            {isLoadingFindings ? 'Loading…' : 'Load more'}
          </button>
        )}
      </div>

      {/* Finding Detail & Triage Modal */}
      <FindingDetailModal
        finding={inspectingFinding}
        onClose={() => setInspectingFinding(null)}
        onStatusUpdated={handleStatusUpdated}
      />
    </div>
  );
};
