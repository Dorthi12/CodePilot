import React, { useState, useEffect, useRef } from 'react';
import {
  Folder,
  FolderOpen,
  FileCode2,
  ChevronRight,
  ChevronDown,
  Sparkles,
  Loader2,
  AlertCircle,
  Code2,
  Layers,
  Cpu,
  BookOpen,
  Boxes,
  HelpCircle
} from 'lucide-react';
import { aiService } from '../services/aiService';
import {
  ProjectSummaryResponse,
  RepositoryFilesResponse,
  FileTreeNode,
  FileContentResponse
} from '../types/ai';
import { Repository } from '../types/repository';

interface CodeExplorerModalProps {
  repository: Repository;
  isOpen: boolean;
  onClose: () => void;
  onExplainSelection: (code: string, filePath: string, startLine?: number, endLine?: number) => void;
  initialSelectedFile?: string;
}

export const CodeExplorerModal: React.FC<CodeExplorerModalProps> = ({
  repository,
  isOpen,
  onClose,
  onExplainSelection,
  initialSelectedFile,
}) => {
  const [activeTab, setActiveTab] = useState<'summary' | 'files'>('summary');

  // Summary state
  const [summary, setSummary] = useState<ProjectSummaryResponse | null>(null);
  const [summaryLoading, setSummaryLoading] = useState<boolean>(true);
  const [summaryError, setSummaryError] = useState<string | null>(null);

  // Files state
  const [filesData, setFilesData] = useState<RepositoryFilesResponse | null>(null);
  const [filesLoading, setFilesLoading] = useState<boolean>(false);
  const [filesError, setFilesError] = useState<string | null>(null);
  const [expandedFolders, setExpandedFolders] = useState<Set<string>>(new Set());

  // Active file viewing state
  const [selectedFilePath, setSelectedFilePath] = useState<string | null>(initialSelectedFile || null);
  const [fileContentData, setFileContentData] = useState<FileContentResponse | null>(null);
  const [contentLoading, setContentLoading] = useState<boolean>(false);
  const [contentError, setContentError] = useState<string | null>(null);

  // Text selection state for code explanation
  const [selectedCodeSnippet, setSelectedCodeSnippet] = useState<string>('');
  const [selectedLinesRange, setSelectedLinesRange] = useState<{ start?: number; end?: number }>({});
  const codePreRef = useRef<HTMLPreElement | null>(null);

  // Load summary and file tree when opened
  useEffect(() => {
    if (!isOpen) return;

    let mounted = true;

    async function loadData() {
      setSummaryLoading(true);
      setSummaryError(null);
      try {
        const sum = await aiService.getRepositorySummary(repository.id);
        if (mounted) setSummary(sum);
      } catch (err: unknown) {
        if (mounted) {
          let msg = 'Failed to load project summary.';
          if (err && typeof err === 'object' && 'response' in err) {
            const axErr = err as { response?: { data?: { error?: { message?: string } } } };
            msg = axErr.response?.data?.error?.message || msg;
          }
          setSummaryError(msg);
        }
      } finally {
        if (mounted) setSummaryLoading(false);
      }

      setFilesLoading(true);
      setFilesError(null);
      try {
        const fData = await aiService.getRepositoryFiles(repository.id);
        if (mounted) {
          setFilesData(fData);
          // Auto-expand first level folders
          const initialExpanded = new Set<string>();
          fData.tree?.forEach((node) => {
            if (node.type === 'directory') initialExpanded.add(node.path);
          });
          setExpandedFolders(initialExpanded);

          // If no initial file selected but files exist, select first file
          if (!selectedFilePath && fData.files?.length > 0) {
            handleSelectFile(fData.files[0].path);
          }
        }
      } catch (err: unknown) {
        if (mounted) {
          let msg = 'Failed to load file tree.';
          if (err && typeof err === 'object' && 'response' in err) {
            const axErr = err as { response?: { data?: { error?: { message?: string } } } };
            msg = axErr.response?.data?.error?.message || msg;
          }
          setFilesError(msg);
        }
      } finally {
        if (mounted) setFilesLoading(false);
      }
    }

    loadData();

    return () => {
      mounted = false;
    };
  }, [isOpen, repository.id]);

  // Load file content when a file is selected
  const handleSelectFile = async (path: string) => {
    setSelectedFilePath(path);
    setContentLoading(true);
    setContentError(null);
    setSelectedCodeSnippet('');
    setSelectedLinesRange({});

    try {
      const data = await aiService.getFileContent(repository.id, path);
      setFileContentData(data);
    } catch (err: unknown) {
      let msg = `Failed to load content for '${path}'.`;
      if (err && typeof err === 'object' && 'response' in err) {
        const axErr = err as { response?: { data?: { error?: { message?: string } } } };
        msg = axErr.response?.data?.error?.message || msg;
      }
      setContentError(msg);
    } finally {
      setContentLoading(false);
    }
  };

  const toggleFolder = (path: string) => {
    setExpandedFolders((prev) => {
      const next = new Set(prev);
      if (next.has(path)) {
        next.delete(path);
      } else {
        next.add(path);
      }
      return next;
    });
  };

  // Capture user text selection within the code preview block
  const handleTextSelection = () => {
    const selection = window.getSelection();
    if (!selection || selection.isCollapsed) {
      return;
    }
    const text = selection.toString();
    if (text && text.trim().length > 0) {
      setSelectedCodeSnippet(text);
    }
  };

  const handleExplainButtonClick = () => {
    if (!selectedCodeSnippet.trim() || !selectedFilePath) return;
    onExplainSelection(
      selectedCodeSnippet.trim(),
      selectedFilePath,
      selectedLinesRange.start,
      selectedLinesRange.end
    );
  };

  if (!isOpen) return null;

  // Recursive Tree Node Renderer
  const renderTreeNode = (node: FileTreeNode) => {
    const isDir = node.type === 'directory';
    const isExpanded = expandedFolders.has(node.path);
    const isSelected = selectedFilePath === node.path;

    if (isDir) {
      return (
        <div key={node.path} className="select-none">
          <button
            onClick={() => toggleFolder(node.path)}
            className="w-full flex items-center space-x-1.5 py-1 px-2 rounded-lg text-xs text-slate-300 hover:bg-surface-dark hover:text-slate-100 transition-colors text-left"
          >
            {isExpanded ? (
              <ChevronDown className="w-3.5 h-3.5 text-slate-400 flex-shrink-0" />
            ) : (
              <ChevronRight className="w-3.5 h-3.5 text-slate-400 flex-shrink-0" />
            )}
            {isExpanded ? (
              <FolderOpen className="w-4 h-4 text-amber-400/80 flex-shrink-0" />
            ) : (
              <Folder className="w-4 h-4 text-amber-400/80 flex-shrink-0" />
            )}
            <span className="truncate font-mono">{node.name}</span>
          </button>

          {isExpanded && node.children && node.children.length > 0 && (
            <div className="pl-3.5 border-l border-surface-border/50 ml-2.5 space-y-0.5 mt-0.5">
              {node.children.map((child) => renderTreeNode(child))}
            </div>
          )}
        </div>
      );
    }

    return (
      <button
        key={node.path}
        onClick={() => {
          handleSelectFile(node.path);
          setActiveTab('files');
        }}
        className={`w-full flex items-center space-x-2 py-1 px-2 rounded-lg text-xs font-mono transition-colors text-left truncate cursor-pointer ${
          isSelected
            ? 'bg-brand-500/20 text-brand-300 border border-brand-500/40 font-semibold'
            : 'text-slate-400 hover:text-slate-200 hover:bg-surface-dark'
        }`}
      >
        <FileCode2 className={`w-3.5 h-3.5 flex-shrink-0 ${isSelected ? 'text-brand-400' : 'text-slate-500'}`} />
        <span className="truncate">{node.name}</span>
      </button>
    );
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-3 sm:p-6 bg-black/80 backdrop-blur-md animate-in fade-in duration-200">
      <div className="bg-surface-darker border border-surface-border rounded-3xl w-full max-w-6xl h-[92vh] flex flex-col shadow-2xl overflow-hidden">
        {/* Top Header */}
        <div className="px-6 py-4 border-b border-surface-border/60 flex items-center justify-between flex-shrink-0">
          <div className="flex items-center space-x-3">
            <div className="w-9 h-9 rounded-2xl bg-brand-500/10 border border-brand-500/20 flex items-center justify-center text-brand-400">
              <Layers className="w-5 h-5" />
            </div>
            <div>
              <div className="flex items-center space-x-2">
                <h2 className="text-sm font-semibold text-slate-100">
                  {repository.name}
                </h2>
                <span className="px-2 py-0.5 rounded-full text-[10px] font-mono bg-surface-dark text-slate-400 border border-surface-border">
                  {repository.tracked_branch}
                </span>
              </div>
              <p className="text-[11px] font-mono text-slate-400">
                Code Explorer & Project Intelligence
              </p>
            </div>
          </div>

          <div className="flex items-center space-x-3">
            {/* Nav Tabs */}
            <div className="flex items-center space-x-1 bg-surface-dark p-1 rounded-xl border border-surface-border">
              <button
                onClick={() => setActiveTab('summary')}
                className={`px-3 py-1 rounded-lg text-xs font-semibold flex items-center space-x-1.5 transition-colors cursor-pointer ${
                  activeTab === 'summary'
                    ? 'bg-brand-500 text-surface-darkest font-bold'
                    : 'text-slate-400 hover:text-slate-200'
                }`}
              >
                <BookOpen className="w-3.5 h-3.5" />
                <span>Project Summary</span>
              </button>
              <button
                onClick={() => setActiveTab('files')}
                className={`px-3 py-1 rounded-lg text-xs font-semibold flex items-center space-x-1.5 transition-colors cursor-pointer ${
                  activeTab === 'files'
                    ? 'bg-brand-500 text-surface-darkest font-bold'
                    : 'text-slate-400 hover:text-slate-200'
                }`}
              >
                <Code2 className="w-3.5 h-3.5" />
                <span>Code Explorer</span>
              </button>
            </div>

            <button
              onClick={onClose}
              className="text-slate-400 hover:text-slate-200 text-sm px-2.5 py-1 rounded-xl hover:bg-surface-dark transition-colors cursor-pointer"
            >
              ✕
            </button>
          </div>
        </div>

        {/* Modal Main Body */}
        <div className="flex-1 overflow-hidden flex flex-col">
          {/* TAB 1: PROJECT SUMMARY */}
          {activeTab === 'summary' && (
            <div className="flex-1 overflow-y-auto p-6 space-y-6">
              {summaryLoading ? (
                <div className="flex flex-col items-center justify-center py-20 space-y-3">
                  <Loader2 className="w-7 h-7 text-brand-400 animate-spin" />
                  <span className="text-xs font-mono text-slate-400">Generating project intelligence summary...</span>
                </div>
              ) : summaryError ? (
                <div className="p-4 rounded-2xl bg-rose-950/40 border border-rose-800 text-xs text-rose-200 flex items-center space-x-2">
                  <AlertCircle className="w-4 h-4 flex-shrink-0" />
                  <span>{summaryError}</span>
                </div>
              ) : summary ? (
                <>
                  {/* Overview Hero */}
                  <div className="p-6 rounded-3xl bg-surface-dark/60 border border-surface-border/70 space-y-3 shadow-sm">
                    <div className="flex items-center space-x-2 text-brand-300 text-xs font-mono font-semibold">
                      <Sparkles className="w-4 h-4" />
                      <span>EXECUTIVE OVERVIEW</span>
                    </div>
                    <p className="text-sm text-slate-200 leading-relaxed font-normal">
                      {summary.project_overview}
                    </p>
                    <p className="text-xs text-slate-400 leading-relaxed pt-1 border-t border-surface-border/40">
                      <span className="font-semibold text-slate-300">Purpose: </span>
                      {summary.project_purpose}
                    </p>
                  </div>

                  {/* Architecture Overview */}
                  <div className="p-5 rounded-2xl bg-surface-dark/40 border border-surface-border/60 space-y-2">
                    <div className="flex items-center space-x-2 text-slate-300 text-xs font-semibold font-mono">
                      <Cpu className="w-4 h-4 text-brand-400" />
                      <span>ARCHITECTURE & DESIGN PATTERNS</span>
                    </div>
                    <p className="text-xs text-slate-300 leading-relaxed">
                      {summary.architecture_overview}
                    </p>
                  </div>

                  {/* Technologies & Frameworks */}
                  <div className="space-y-3">
                    <h3 className="text-xs font-mono font-semibold text-slate-300 uppercase tracking-wider flex items-center space-x-2">
                      <Boxes className="w-4 h-4 text-brand-400" />
                      <span>Detected Technologies & Libraries</span>
                    </h3>
                    <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-3">
                      {summary.technologies.map((tech, i) => (
                        <div
                          key={i}
                          className="p-3 rounded-2xl bg-surface-dark/50 border border-surface-border/60 space-y-1"
                        >
                          <div className="font-semibold text-xs text-brand-300 font-mono truncate">{tech.name}</div>
                          <div className="text-[11px] text-slate-400">{tech.category}</div>
                        </div>
                      ))}
                    </div>
                  </div>

                  {/* Key Modules */}
                  <div className="space-y-3">
                    <h3 className="text-xs font-mono font-semibold text-slate-300 uppercase tracking-wider flex items-center space-x-2">
                      <Folder className="w-4 h-4 text-brand-400" />
                      <span>Primary Modules & Packages</span>
                    </h3>
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                      {summary.modules.map((mod, i) => (
                        <div
                          key={i}
                          className="p-4 rounded-2xl bg-surface-dark/40 border border-surface-border/50 space-y-1.5"
                        >
                          <div className="flex items-center justify-between">
                            <span className="font-mono text-xs font-bold text-slate-100">{mod.name}</span>
                            <span className="text-[10px] font-mono text-slate-400 bg-surface-darkest px-2 py-0.5 rounded-full border border-surface-border/40">
                              {mod.file_count} files • {mod.symbol_count} symbols
                            </span>
                          </div>
                          <p className="text-xs text-slate-400 leading-relaxed">{mod.description}</p>
                        </div>
                      ))}
                    </div>
                  </div>

                  {/* Major Components & Entities */}
                  <div className="space-y-3">
                    <div className="flex items-center justify-between">
                      <h3 className="text-xs font-mono font-semibold text-slate-300 uppercase tracking-wider flex items-center space-x-2">
                        <Code2 className="w-4 h-4 text-brand-400" />
                        <span>Major Code Components & Classes</span>
                      </h3>
                      <button
                        onClick={() => setActiveTab('files')}
                        className="text-xs text-brand-400 hover:text-brand-300 font-mono"
                      >
                        Browse all in Code Explorer →
                      </button>
                    </div>

                    <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                      {summary.components.slice(0, 9).map((comp, i) => (
                        <div
                          key={i}
                          onClick={() => {
                            handleSelectFile(comp.file_path);
                            setActiveTab('files');
                          }}
                          className="p-3.5 rounded-2xl bg-surface-dark/40 border border-surface-border/60 hover:border-brand-500/50 cursor-pointer transition-all space-y-1 group"
                        >
                          <div className="flex items-center space-x-1.5">
                            <span className="text-[10px] font-mono px-1.5 py-0.2 rounded bg-brand-500/10 text-brand-300 border border-brand-500/20 font-bold">
                              {comp.kind}
                            </span>
                            <span className="text-xs font-mono font-semibold text-slate-200 truncate group-hover:text-brand-300">
                              {comp.name}
                            </span>
                          </div>
                          <div className="text-[11px] font-mono text-slate-500 truncate">
                            {comp.file_path}:{comp.start_line}
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                </>
              ) : null}
            </div>
          )}

          {/* TAB 2: CODE EXPLORER & VIEWER */}
          {activeTab === 'files' && (
            <div className="flex-1 flex flex-col md:flex-row overflow-hidden">
              {/* Sidebar: File Tree */}
              <div className="w-full md:w-80 border-b md:border-b-0 md:border-r border-surface-border/60 flex flex-col bg-surface-darkest/40 flex-shrink-0">
                <div className="p-3.5 border-b border-surface-border/50 text-xs font-mono font-semibold text-slate-400 flex items-center justify-between">
                  <span>FILES & PACKAGES</span>
                  <span className="text-[10px] bg-surface-dark px-2 py-0.5 rounded-full border border-surface-border">
                    {filesData?.file_count || 0} files
                  </span>
                </div>

                <div className="flex-1 overflow-y-auto p-2 space-y-0.5">
                  {filesLoading ? (
                    <div className="py-12 text-center text-xs text-slate-500 flex flex-col items-center space-y-2">
                      <Loader2 className="w-4 h-4 animate-spin text-brand-400" />
                      <span>Loading file tree...</span>
                    </div>
                  ) : filesError ? (
                    <div className="p-3 text-xs text-rose-300 font-mono">{filesError}</div>
                  ) : filesData?.tree && filesData.tree.length > 0 ? (
                    filesData.tree.map((node) => renderTreeNode(node))
                  ) : (
                    <div className="text-xs text-slate-500 p-4 text-center">No indexed files found.</div>
                  )}
                </div>
              </div>

              {/* Main Content: Code Viewer with Selection Action */}
              <div className="flex-1 flex flex-col overflow-hidden bg-surface-darkest">
                {/* File Header & Selection Bar */}
                <div className="px-5 py-3 border-b border-surface-border/60 bg-surface-darker/60 flex items-center justify-between flex-wrap gap-2 flex-shrink-0">
                  <div className="flex items-center space-x-2 min-w-0">
                    <FileCode2 className="w-4 h-4 text-brand-400 flex-shrink-0" />
                    <span className="font-mono text-xs font-semibold text-slate-200 truncate">
                      {selectedFilePath || 'Select a file to inspect'}
                    </span>
                    {fileContentData && (
                      <span className="text-[11px] font-mono text-slate-400">
                        ({fileContentData.line_count} lines)
                      </span>
                    )}
                  </div>

                  {/* Explain Selection Action Banner */}
                  <div className="flex items-center space-x-2">
                    {selectedCodeSnippet.trim() ? (
                      <button
                        onClick={handleExplainButtonClick}
                        className="px-3.5 py-1.5 rounded-xl text-xs font-bold bg-brand-500 hover:bg-brand-400 text-surface-darkest flex items-center space-x-1.5 transition-all shadow-md shadow-brand-500/20 cursor-pointer animate-in fade-in"
                        title="Explain selected lines with AI"
                      >
                        <Sparkles className="w-3.5 h-3.5" />
                        <span>Explain Selected Code</span>
                      </button>
                    ) : (
                      <div className="text-[11px] text-slate-400 font-mono flex items-center space-x-1">
                        <HelpCircle className="w-3.5 h-3.5 text-slate-400" />
                        <span>Select any code snippet below to explain</span>
                      </div>
                    )}
                  </div>
                </div>

                {/* Code Text Area with Line Numbers */}
                <div className="flex-1 overflow-auto p-4 font-mono text-xs text-slate-200 relative">
                  {contentLoading ? (
                    <div className="flex flex-col items-center justify-center h-full space-y-2">
                      <Loader2 className="w-6 h-6 animate-spin text-brand-400" />
                      <span className="text-slate-400">Loading file content...</span>
                    </div>
                  ) : contentError ? (
                    <div className="p-4 text-xs text-rose-300 font-mono">{contentError}</div>
                  ) : fileContentData ? (
                    <div className="flex select-text" onMouseUp={handleTextSelection}>
                      {/* Line Numbers */}
                      <div className="select-none text-slate-500 text-right pr-4 border-r border-surface-border/40 font-mono text-xs space-y-0 leading-5">
                        {fileContentData.content.split('\n').map((_, idx) => (
                          <div key={idx} className="h-5 text-[11px]">
                            {idx + 1}
                          </div>
                        ))}
                      </div>

                      {/* Source Text */}
                      <pre
                        ref={codePreRef}
                        className="flex-1 pl-4 leading-5 overflow-x-auto whitespace-pre font-mono text-xs text-slate-200"
                      >
                        {fileContentData.content}
                      </pre>
                    </div>
                  ) : (
                    <div className="flex flex-col items-center justify-center h-full text-slate-500 space-y-2">
                      <Code2 className="w-8 h-8 text-slate-600" />
                      <span>Select a file from the repository tree to view and explain code.</span>
                    </div>
                  )}
                </div>

                {/* Bottom Bar: Quick Symbol Jump */}
                {fileContentData?.symbols && fileContentData.symbols.length > 0 && (
                  <div className="p-2.5 border-t border-surface-border/40 bg-surface-darker/60 flex items-center space-x-2 overflow-x-auto text-[11px] font-mono flex-shrink-0">
                    <span className="text-slate-500 flex-shrink-0">Symbols:</span>
                    {fileContentData.symbols.slice(0, 8).map((sym) => (
                      <button
                        key={sym.symbol_id}
                        onClick={() => {
                          // Preload symbol snippet for explanation
                          onExplainSelection(
                            sym.name,
                            selectedFilePath || '',
                            sym.start_line,
                            sym.end_line
                          );
                        }}
                        className="px-2 py-0.5 rounded-lg bg-surface-dark hover:bg-brand-500/20 text-slate-300 hover:text-brand-300 border border-surface-border/50 flex-shrink-0 cursor-pointer"
                      >
                        {sym.name} ({sym.kind})
                      </button>
                    ))}
                  </div>
                )}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
