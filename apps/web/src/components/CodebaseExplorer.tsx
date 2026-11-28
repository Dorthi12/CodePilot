import React, { useState, useEffect, useRef, useCallback, useMemo } from 'react';
import {
  Folder,
  FolderOpen,
  FileCode,
  FileText,
  Search,
  ChevronRight,
  ChevronDown,
  Copy,
  Check,
  Code2,
  Layers,
  Loader2,
  AlertCircle,
  FileX,
  Sparkles,
  RefreshCw
} from 'lucide-react';
import {
  FileDetailResponse
} from '../types/repository';
import { repositoryService } from '../services/repositoryService';
import { CodeExplainModal } from './CodeExplainModal';

interface CodebaseExplorerProps {
  repositoryId: string;
  initialFilePath?: string;
  initialTargetLine?: number;
  onFileSelect?: (path: string) => void;
  onExplainCode?: (code: string, filePath: string, startLine?: number, endLine?: number) => void;
}

// Tree node interface for nested representation
interface TreeNode {
  name: string;
  path: string;
  type: 'file' | 'directory';
  language?: string | null;
  size_bytes?: number;
  line_count?: number;
  summary?: string | null;
  symbol_count?: number;
  children?: TreeNode[];
  isLoaded?: boolean;
}

// Helper to determine icon by file extension / language
function getFileIcon(filename: string, language?: string | null) {
  const ext = filename.split('.').pop()?.toLowerCase();
  if (language === 'python' || ext === 'py') {
    return <span className="text-blue-400 font-mono text-[10px] font-bold">PY</span>;
  }
  if (language === 'typescript' || ext === 'ts' || ext === 'tsx') {
    return <span className="text-sky-400 font-mono text-[10px] font-bold">TS</span>;
  }
  if (language === 'javascript' || ext === 'js' || ext === 'jsx') {
    return <span className="text-amber-400 font-mono text-[10px] font-bold">JS</span>;
  }
  if (ext === 'json') {
    return <span className="text-yellow-400 font-mono text-[10px] font-bold">{"{}"}</span>;
  }
  if (ext === 'md') {
    return <FileText className="w-3.5 h-3.5 text-purple-400" />;
  }
  if (ext === 'css' || ext === 'scss') {
    return <span className="text-pink-400 font-mono text-[10px] font-bold">CSS</span>;
  }
  if (ext === 'html') {
    return <span className="text-orange-400 font-mono text-[10px] font-bold">&lt;&gt;</span>;
  }
  return <FileCode className="w-3.5 h-3.5 text-slate-400" />;
}

// Simple deterministic line-level syntax highlighter
function highlightLine(line: string, _language?: string | null): React.ReactNode {
  if (!line) return <span>&nbsp;</span>;

  // Comment matching
  if (line.trim().startsWith('#') || line.trim().startsWith('//')) {
    return <span className="text-slate-500 italic">{line}</span>;
  }

  // Tokenize keywords, strings, and identifiers
  const keywords = new Set([
    'def', 'class', 'import', 'from', 'as', 'return', 'if', 'else', 'elif',
    'for', 'while', 'try', 'except', 'finally', 'with', 'async', 'await',
    'const', 'let', 'var', 'function', 'export', 'default', 'interface', 'type',
    'public', 'private', 'protected', 'implements', 'extends', 'new', 'this',
    'true', 'false', 'null', 'undefined', 'None', 'True', 'False', 'yield',
    'lambda', 'pass', 'raise', 'throw', 'catch', 'in', 'is', 'not', 'and', 'or'
  ]);

  const regex = /(".*?"|'.*?'|`.*?`|[a-zA-Z_]\w*|[0-9]+|[{}()[\].,;:+\-*/%=<>!&|^~]+|\s+)/g;
  const parts: React.ReactNode[] = [];
  let match;
  let keyIdx = 0;

  while ((match = regex.exec(line)) !== null) {
    const token = match[0];
    keyIdx++;

    if (token.startsWith('"') || token.startsWith("'") || token.startsWith('`')) {
      parts.push(<span key={keyIdx} className="text-amber-300">{token}</span>);
    } else if (keywords.has(token)) {
      parts.push(<span key={keyIdx} className="text-brand-400 font-semibold">{token}</span>);
    } else if (/^\d+$/.test(token)) {
      parts.push(<span key={keyIdx} className="text-emerald-400">{token}</span>);
    } else if (/^[A-Z][a-zA-Z0-9_]*$/.test(token)) {
      // Class or Type identifier
      parts.push(<span key={keyIdx} className="text-teal-300">{token}</span>);
    } else if (['=>', '->', '==', '!=', '<=', '>=', '&&', '||'].includes(token)) {
      parts.push(<span key={keyIdx} className="text-rose-300">{token}</span>);
    } else {
      parts.push(<span key={keyIdx} className="text-slate-200">{token}</span>);
    }
  }

  return parts.length > 0 ? parts : <span>{line}</span>;
}

// Render formatted sections from generated summary
function renderFormattedSummary(summaryText: string): React.ReactNode {
  const sections = summaryText.split(/(?=###\s+)/);
  return (
    <div className="space-y-3">
      {sections.map((sec, i) => {
        const trimmed = sec.trim();
        if (!trimmed) return null;
        if (trimmed.startsWith('### ')) {
          const firstLineEnd = trimmed.indexOf('\n');
          const title = firstLineEnd === -1 ? trimmed.slice(4) : trimmed.slice(4, firstLineEnd).trim();
          const body = firstLineEnd === -1 ? '' : trimmed.slice(firstLineEnd + 1).trim();
          return (
            <div key={i} className="space-y-1">
              <h5 className="text-[11px] font-mono font-bold text-brand-400 uppercase tracking-wider">
                {title}
              </h5>
              <div className="text-xs text-slate-300 leading-relaxed whitespace-pre-line pl-2 border-l border-surface-border/50">
                {body}
              </div>
            </div>
          );
        }
        return (
          <p key={i} className="text-xs text-slate-300 leading-relaxed whitespace-pre-line">
            {trimmed}
          </p>
        );
      })}
    </div>
  );
}

export const CodebaseExplorer: React.FC<CodebaseExplorerProps> = ({
  repositoryId,
  initialFilePath,
  initialTargetLine,
  onFileSelect
}) => {
  // Navigation & Tree State
  const [treeData, setTreeData] = useState<TreeNode[]>([]);
  const [expandedFolders, setExpandedFolders] = useState<Set<string>>(new Set());
  const [treeLoading, setTreeLoading] = useState<boolean>(true);
  const [fileFilter, setFileFilter] = useState<string>('');

  // Selected File State
  const [selectedPath, setSelectedPath] = useState<string | null>(initialFilePath || null);
  const [fileDetail, setFileDetail] = useState<FileDetailResponse | null>(null);
  const [fileLoading, setFileLoading] = useState<boolean>(false);
  const [fileError, setFileError] = useState<string | null>(null);

  // Code selection state
  const [selectedText, setSelectedText] = useState<string>('');

  const handleCodeSelectionChange = () => {
    const selection = window.getSelection();
    if (selection) {
      const text = selection.toString();
      if (text.trim().length > 0) {
        setSelectedText(text.trim());
      }
    }
  };

  // On-demand Summary State
  const [summaryLoading, setSummaryLoading] = useState<boolean>(false);
  const [summaryError, setSummaryError] = useState<string | null>(null);

  // Symbol & Line Jump State
  const [targetLine, setTargetLine] = useState<number | null>(initialTargetLine || null);
  const [symbolFilter, setSymbolFilter] = useState<string>('');
  const [selectedKind, setSelectedKind] = useState<string>('ALL');

  // AI Code Explanation Modal State
  const [explainModal, setExplainModal] = useState<{
    isOpen: boolean;
    startLine?: number;
    endLine?: number;
    symbolName?: string;
  }>({ isOpen: false });

  useEffect(() => {
    if (initialFilePath) {
      setSelectedPath(initialFilePath);
    }
    if (initialTargetLine !== undefined) {
      setTargetLine(initialTargetLine);
    }
  }, [initialFilePath, initialTargetLine]);

  // UI Panels
  const [copied, setCopied] = useState<boolean>(false);
  const [isIntelligenceOpen, setIsIntelligenceOpen] = useState<boolean>(true);
  const codeContainerRef = useRef<HTMLDivElement>(null);

  // 1. Fetch initial root tree
  const loadTreeDirectory = useCallback(async (dirPath = '') => {
    try {
      const res = await repositoryService.getFileTree(repositoryId, dirPath);
      return res.entries;
    } catch (err) {
      console.error('Failed to load tree path', dirPath, err);
      return [];
    }
  }, [repositoryId]);

  useEffect(() => {
    let mounted = true;
    async function initTree() {
      setTreeLoading(true);
      const rootEntries = await loadTreeDirectory('');
      if (!mounted) return;

      const nodes: TreeNode[] = rootEntries.map(e => ({
        ...e,
        isLoaded: e.type === 'file',
        children: []
      }));
      setTreeData(nodes);
      setTreeLoading(false);

      // Auto-select first file if none selected
      if (!selectedPath) {
        const firstFile = nodes.find(n => n.type === 'file');
        if (firstFile) {
          setSelectedPath(firstFile.path);
        }
      }
    }
    initTree();
    return () => { mounted = false; };
  }, [loadTreeDirectory, repositoryId]);

  // Handle expanding folder and lazy-loading its children
  const handleToggleFolder = async (folderPath: string) => {
    setExpandedFolders(prev => {
      const next = new Set(prev);
      if (next.has(folderPath)) {
        next.delete(folderPath);
      } else {
        next.add(folderPath);
      }
      return next;
    });

    // Check if children already loaded
    const findAndLoadNode = async (nodes: TreeNode[]): Promise<TreeNode[]> => {
      const result: TreeNode[] = [];
      for (const node of nodes) {
        if (node.path === folderPath) {
          if (!node.isLoaded) {
            const subEntries = await loadTreeDirectory(folderPath);
            result.push({
              ...node,
              isLoaded: true,
              children: subEntries.map(e => ({
                ...e,
                isLoaded: e.type === 'file',
                children: []
              }))
            });
          } else {
            result.push(node);
          }
        } else if (node.children && node.children.length > 0) {
          const updatedChildren = await findAndLoadNode(node.children);
          result.push({ ...node, children: updatedChildren });
        } else {
          result.push(node);
        }
      }
      return result;
    };

    const updated = await findAndLoadNode(treeData);
    setTreeData(updated);
  };

  // 2. Fetch File Detail when selectedPath changes
  useEffect(() => {
    if (!selectedPath) return;

    let mounted = true;
    async function fetchFile() {
      setFileLoading(true);
      setFileError(null);
      setTargetLine(null);
      setSummaryError(null);
      setSummaryLoading(false);
      try {
        const detail = await repositoryService.getFileDetail(repositoryId, selectedPath!);
        if (mounted) {
          setFileDetail(detail);
          onFileSelect?.(selectedPath!);
        }
      } catch (err: any) {
        if (mounted) {
          setFileError(err.response?.data?.error?.message || 'Failed to inspect file.');
          setFileDetail(null);
        }
      } finally {
        if (mounted) setFileLoading(false);
      }
    }
    fetchFile();
    return () => { mounted = false; };
  }, [repositoryId, selectedPath, onFileSelect]);

  const handleGenerateSummary = async (force = false) => {
    if (!fileDetail) return;
    setSummaryLoading(true);
    setSummaryError(null);
    try {
      const res = await repositoryService.generateFileSummary(repositoryId, fileDetail.id, { force });
      setFileDetail(prev => (prev ? { ...prev, summary: res.summary } : null));
    } catch (err: any) {
      setSummaryError(err.response?.data?.error?.message || 'Failed to generate file summary.');
    } finally {
      setSummaryLoading(false);
    }
  };

  // Jump to line when targetLine is set
  useEffect(() => {
    if (targetLine && codeContainerRef.current) {
      const lineEl = document.getElementById(`code-line-${targetLine}`);
      if (lineEl) {
        lineEl.scrollIntoView({ behavior: 'smooth', block: 'center' });
      }
    }
  }, [targetLine]);

  // Copy code to clipboard
  const handleCopyCode = () => {
    if (!fileDetail?.content) return;
    navigator.clipboard.writeText(fileDetail.content);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  // Filtered symbols for intelligence panel
  const filteredSymbols = useMemo(() => {
    if (!fileDetail?.symbols) return [];
    return fileDetail.symbols.filter(s => {
      const matchesSearch = !symbolFilter || s.name.toLowerCase().includes(symbolFilter.toLowerCase()) || s.qualified_name.toLowerCase().includes(symbolFilter.toLowerCase());
      const matchesKind = selectedKind === 'ALL' || s.kind === selectedKind;
      return matchesSearch && matchesKind;
    });
  }, [fileDetail?.symbols, symbolFilter, selectedKind]);

  // Recursive tree renderer
  const renderTreeNodes = (nodes: TreeNode[], depth = 0): React.ReactNode => {
    return nodes
      .filter(n => {
        if (!fileFilter) return true;
        return n.name.toLowerCase().includes(fileFilter.toLowerCase()) || n.path.toLowerCase().includes(fileFilter.toLowerCase());
      })
      .map(node => {
        const isDir = node.type === 'directory';
        const isExpanded = expandedFolders.has(node.path);
        const isSelected = selectedPath === node.path;

        return (
          <div key={node.path} className="select-none">
            <div
              onClick={() => {
                if (isDir) {
                  handleToggleFolder(node.path);
                } else {
                  setSelectedPath(node.path);
                }
              }}
              style={{ paddingLeft: `${depth * 14 + 10}px` }}
              className={`flex items-center justify-between py-1.5 pr-2 rounded-lg text-xs cursor-pointer transition-colors ${
                isSelected
                  ? 'bg-brand-500/15 text-brand-300 font-medium border-l-2 border-brand-400 pl-[8px]'
                  : 'text-slate-300 hover:bg-surface-dark/70 hover:text-slate-100'
              }`}
            >
              <div className="flex items-center space-x-2 min-w-0">
                {isDir ? (
                  <>
                    {isExpanded ? (
                      <ChevronDown className="w-3.5 h-3.5 text-slate-400 flex-shrink-0" />
                    ) : (
                      <ChevronRight className="w-3.5 h-3.5 text-slate-400 flex-shrink-0" />
                    )}
                    {isExpanded ? (
                      <FolderOpen className="w-4 h-4 text-brand-400 flex-shrink-0" />
                    ) : (
                      <Folder className="w-4 h-4 text-slate-400 flex-shrink-0" />
                    )}
                  </>
                ) : (
                  <div className="w-4 h-4 flex items-center justify-center flex-shrink-0">
                    {getFileIcon(node.name, node.language)}
                  </div>
                )}
                <span className="truncate">{node.name}</span>
              </div>

              {!isDir && node.symbol_count !== undefined && node.symbol_count > 0 && (
                <span className="text-[10px] font-mono text-slate-500 px-1 py-0.2 rounded bg-surface-dark/40 flex-shrink-0">
                  {node.symbol_count}
                </span>
              )}
            </div>

            {isDir && isExpanded && node.children && node.children.length > 0 && (
              <div>{renderTreeNodes(node.children, depth + 1)}</div>
            )}
          </div>
        );
      });
  };

  const fileLines = useMemo(() => {
    if (!fileDetail?.content) return [];
    return fileDetail.content.split(/\r?\n/);
  }, [fileDetail?.content]);

  return (
    <div className="bg-surface-darker/95 border border-surface-border/70 rounded-2xl overflow-hidden shadow-2xl flex flex-col h-[750px]">
      {/* 3-Panel Main Content Layout */}
      <div className="flex-1 flex overflow-hidden">
        {/* ============================================================ */}
        {/* 1. LEFT PANEL: File Explorer */}
        {/* ============================================================ */}
        <div className="w-72 sm:w-80 flex-shrink-0 border-r border-surface-border/60 bg-surface-dark/40 flex flex-col">
          {/* Explorer Header & Search */}
          <div className="p-3.5 border-b border-surface-border/50 space-y-2.5">
            <div className="flex items-center justify-between">
              <span className="text-xs font-semibold text-slate-300 uppercase tracking-wider font-mono flex items-center space-x-1.5">
                <Layers className="w-3.5 h-3.5 text-brand-400" />
                <span>Files & Directories</span>
              </span>
              <span className="text-[11px] text-slate-500 font-mono">
                {treeData.length} entries
              </span>
            </div>

            <div className="relative">
              <Search className="w-3.5 h-3.5 text-slate-500 absolute left-2.5 top-1/2 -translate-y-1/2" />
              <input
                type="text"
                value={fileFilter}
                onChange={e => setFileFilter(e.target.value)}
                placeholder="Search files..."
                className="w-full bg-surface-dark/90 border border-surface-border/60 rounded-xl pl-8 pr-3 py-1.5 text-xs text-slate-200 placeholder-slate-500 focus:outline-none focus:border-brand-500/50"
              />
            </div>
          </div>

          {/* Collapsible Tree View */}
          <div className="flex-1 overflow-y-auto p-2 space-y-0.5 custom-scrollbar">
            {treeLoading ? (
              <div className="p-6 flex flex-col items-center justify-center text-slate-500 space-y-2">
                <Loader2 className="w-5 h-5 animate-spin text-brand-400" />
                <span className="text-xs">Loading tree...</span>
              </div>
            ) : treeData.length === 0 ? (
              <div className="p-6 text-center text-xs text-slate-500">
                No files found in snapshot.
              </div>
            ) : (
              renderTreeNodes(treeData)
            )}
          </div>
        </div>

        {/* ============================================================ */}
        {/* 2. MAIN PANEL: Code Viewer */}
        {/* ============================================================ */}
        <div className="flex-1 flex flex-col overflow-hidden bg-surface-darkest">
          {/* Code Viewer Top Bar: Breadcrumbs & Actions */}
          <div className="px-4 py-2.5 border-b border-surface-border/60 bg-surface-darker/80 flex items-center justify-between">
            <div className="flex items-center space-x-2 min-w-0 text-xs font-mono">
              <FileCode className="w-4 h-4 text-brand-400 flex-shrink-0" />
              <span className="text-slate-400 truncate">
                {fileDetail ? fileDetail.path : (selectedPath || 'Select a file to inspect')}
              </span>
              {fileDetail?.language && (
                <span className="px-2 py-0.5 rounded-full text-[10px] font-semibold bg-brand-500/10 text-brand-300 border border-brand-500/30 uppercase">
                  {fileDetail.language}
                </span>
              )}
            </div>

            <div className="flex items-center space-x-2 flex-shrink-0">
              {fileDetail && (
                <div className="text-[11px] font-mono text-slate-400 mr-2 hidden sm:block">
                  {fileLines.length} lines • {(fileDetail.size_bytes / 1024).toFixed(1)} KB
                </div>
              )}

              {fileDetail?.content && (
                <>
                  <button
                    onClick={() => setExplainModal({ isOpen: true })}
                    className="px-2.5 py-1 rounded-lg border border-brand-500/40 bg-brand-500/10 text-brand-300 hover:bg-brand-500/20 text-xs flex items-center space-x-1.5 transition-colors cursor-pointer"
                    title="Explain this file or a line range with AI"
                  >
                    <Sparkles className="w-3.5 h-3.5" />
                    <span>Explain</span>
                  </button>
                  <button
                    onClick={handleCopyCode}
                    className="px-2.5 py-1 rounded-lg border border-surface-border text-slate-400 hover:text-slate-200 hover:bg-surface-dark text-xs flex items-center space-x-1.5 transition-colors cursor-pointer"
                    title="Copy code to clipboard"
                  >
                    {copied ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5" />}
                    <span>{copied ? 'Copied' : 'Copy'}</span>
                  </button>
                </>
              )}

              {/* Explain with AI / Selected Code */}
              {onExplainCode && fileDetail?.content && (
                <button
                  type="button"
                  onClick={() => {
                    if (selectedText.trim()) {
                      onExplainCode(selectedText.trim(), fileDetail.path);
                    } else if (fileDetail.content) {
                      onExplainCode(
                        fileDetail.content.slice(0, 3000),
                        fileDetail.path,
                        1,
                        Math.min(fileDetail.line_count || 100, 100)
                      );
                    }
                  }}
                  className={`px-2.5 py-1 rounded-lg border text-xs flex items-center space-x-1.5 transition-all cursor-pointer font-semibold ${
                    selectedText.trim()
                      ? 'bg-brand-500 text-surface-darkest border-brand-400 font-bold shadow-md shadow-brand-500/20'
                      : 'border-surface-border text-brand-300 hover:text-brand-200 hover:border-brand-500/40 bg-surface-dark'
                  }`}
                  title={selectedText.trim() ? 'Explain selected text with AI' : 'Explain file with AI'}
                >
                  <Sparkles className="w-3.5 h-3.5" />
                  <span>
                    {selectedText.trim()
                      ? `Explain Selection (${selectedText.trim().length} chars)`
                      : 'Explain with AI'}
                  </span>
                </button>
              )}

              <button
                onClick={() => setIsIntelligenceOpen(!isIntelligenceOpen)}
                className={`p-1.5 rounded-lg border text-xs flex items-center transition-colors cursor-pointer ${
                  isIntelligenceOpen
                    ? 'border-brand-500/40 text-brand-300 bg-brand-500/10'
                    : 'border-surface-border text-slate-400 hover:text-slate-200 hover:bg-surface-dark'
                }`}
                title={isIntelligenceOpen ? 'Collapse Code Intelligence' : 'Expand Code Intelligence'}
              >
                <Code2 className="w-3.5 h-3.5" />
              </button>
            </div>
          </div>

          {/* Code Viewer Body */}
          <div
            ref={codeContainerRef}
            onMouseUp={handleCodeSelectionChange}
            className="flex-1 overflow-auto font-mono text-xs leading-relaxed custom-scrollbar bg-[#080c14]"
          >
            {fileLoading ? (
              <div className="h-full flex flex-col items-center justify-center text-slate-500 space-y-3">
                <Loader2 className="w-6 h-6 animate-spin text-brand-400" />
                <span className="text-xs font-mono">Parsing file content...</span>
              </div>
            ) : fileError ? (
              <div className="h-full flex flex-col items-center justify-center p-8 text-center space-y-3">
                <AlertCircle className="w-8 h-8 text-rose-400" />
                <div className="text-sm font-semibold text-rose-200">Could not display file</div>
                <div className="text-xs text-rose-300/80 max-w-md">{fileError}</div>
              </div>
            ) : !fileDetail ? (
              <div className="h-full flex flex-col items-center justify-center text-slate-500 space-y-2 p-8">
                <Layers className="w-8 h-8 text-slate-600 mb-2" />
                <p className="text-sm font-medium text-slate-400">Select a file from the explorer</p>
                <p className="text-xs text-slate-600">Explore parsed source code, AST classes, and functions</p>
              </div>
            ) : !fileDetail.content ? (
              <div className="h-full flex flex-col items-center justify-center p-8 text-center space-y-2 text-slate-500">
                <FileX className="w-8 h-8 text-slate-600 mb-1" />
                <p className="text-sm font-medium text-slate-400">Binary or empty file</p>
                <p className="text-xs text-slate-600">{fileDetail.summary || 'Content cannot be rendered as text.'}</p>
              </div>
            ) : (
              <div className="min-w-full py-3 inline-block">
                {fileLines.map((line, idx) => {
                  const lineNum = idx + 1;
                  const isHighlighted = targetLine === lineNum;

                  return (
                    <div
                      key={lineNum}
                      id={`code-line-${lineNum}`}
                      className={`flex items-start hover:bg-slate-800/30 transition-colors ${
                        isHighlighted ? 'bg-brand-500/20 border-l-2 border-brand-400' : ''
                      }`}
                    >
                      {/* Line Number Gutter */}
                      <span className="w-12 flex-shrink-0 text-right pr-4 select-none text-slate-600 font-mono text-[11px] leading-5">
                        {lineNum}
                      </span>
                      {/* Code Line Text */}
                      <span className="flex-1 pr-6 whitespace-pre leading-5">
                        {highlightLine(line, fileDetail.language)}
                      </span>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        </div>

        {/* ============================================================ */}
        {/* 3. RIGHT PANEL: Code Intelligence & Symbols */}
        {/* ============================================================ */}
        {isIntelligenceOpen && (
          <div className="w-72 sm:w-80 flex-shrink-0 border-l border-surface-border/60 bg-surface-dark/40 flex flex-col overflow-hidden">
            {/* Panel Header */}
            <div className="p-3.5 border-b border-surface-border/50 flex items-center justify-between">
              <span className="text-xs font-semibold text-slate-300 uppercase tracking-wider font-mono flex items-center space-x-1.5">
                <Sparkles className="w-3.5 h-3.5 text-brand-400" />
                <span>Code Intelligence</span>
              </span>
              {fileDetail?.symbols && (
                <span className="text-[11px] font-mono text-brand-400">
                  {fileDetail.symbols.length} symbols
                </span>
              )}
            </div>

            <div className="flex-1 overflow-y-auto p-3.5 space-y-4 custom-scrollbar">
              {/* File Info Bar */}
              {fileDetail && (
                <div className="flex items-center justify-between text-[11px] font-mono text-slate-400 bg-surface-darker/60 px-3 py-1.5 rounded-xl border border-surface-border/40">
                  <span>{fileDetail.line_count} lines</span>
                  <span>•</span>
                  <span>{(fileDetail.size_bytes / 1024).toFixed(1)} KB</span>
                  <span>•</span>
                  <span className="uppercase text-brand-400">{fileDetail.language || 'plain'}</span>
                </div>
              )}

              {/* On-Demand AI File Summary Card */}
              {fileDetail && (
                <div className="bg-surface-darker/90 border border-surface-border/60 rounded-xl p-3.5 space-y-2.5 shadow-sm">
                  <div className="flex items-center justify-between">
                    <div className="text-[11px] font-mono uppercase text-slate-300 font-semibold flex items-center space-x-1.5">
                      <Sparkles className="w-3.5 h-3.5 text-brand-400" />
                      <span>AI File Summary</span>
                      {fileDetail.summary && (
                        <span className="text-[9px] font-mono px-1.5 py-0.2 rounded-full bg-brand-500/10 text-brand-400 border border-brand-500/30 uppercase font-semibold">
                          Generated
                        </span>
                      )}
                    </div>
                    {fileDetail.summary && (
                      <button
                        onClick={() => handleGenerateSummary(true)}
                        disabled={summaryLoading}
                        className="text-[11px] font-mono text-slate-400 hover:text-slate-200 flex items-center space-x-1 transition-colors cursor-pointer disabled:opacity-50"
                        title="Regenerate Summary from code"
                      >
                        <RefreshCw className={`w-3 h-3 ${summaryLoading ? 'animate-spin' : ''}`} />
                        <span>Regenerate</span>
                      </button>
                    )}
                  </div>

                  {summaryLoading ? (
                    <div className="py-4 flex flex-col items-center justify-center text-slate-400 space-y-2 text-center">
                      <Loader2 className="w-5 h-5 animate-spin text-brand-400" />
                      <span className="text-xs font-mono text-slate-300">Generating summary...</span>
                      <span className="text-[10px] text-slate-500">Synthesizing purpose, responsibilities, and architecture</span>
                    </div>
                  ) : summaryError ? (
                    <div className="p-2.5 rounded-xl bg-rose-950/30 border border-rose-800/40 text-xs text-rose-300 space-y-2">
                      <div className="flex items-center space-x-1.5 font-semibold text-rose-200">
                        <AlertCircle className="w-3.5 h-3.5" />
                        <span>Generation Failed</span>
                      </div>
                      <p className="text-[11px] leading-relaxed">{summaryError}</p>
                      <button
                        onClick={() => handleGenerateSummary(false)}
                        className="px-2.5 py-1 rounded-lg bg-surface-dark border border-surface-border text-[11px] text-slate-300 hover:text-slate-100 transition-colors cursor-pointer"
                      >
                        Retry
                      </button>
                    </div>
                  ) : fileDetail.summary ? (
                    <div className="text-xs text-slate-300 leading-relaxed bg-surface-dark/40 p-3 rounded-xl border border-surface-border/40">
                      {renderFormattedSummary(fileDetail.summary)}
                    </div>
                  ) : (
                    <div className="space-y-2.5 bg-surface-dark/30 p-3 rounded-xl border border-surface-border/40">
                      <p className="text-xs text-slate-400 leading-relaxed">
                        No summary generated yet for this file. Click below to generate an on-demand AI explanation.
                      </p>
                      <button
                        onClick={() => handleGenerateSummary(false)}
                        disabled={summaryLoading}
                        className="w-full py-2 px-3 rounded-xl bg-brand-500 hover:bg-brand-400 text-surface-darkest text-xs font-bold flex items-center justify-center space-x-2 transition-all cursor-pointer shadow-md shadow-brand-500/20 disabled:opacity-50"
                      >
                        <Sparkles className="w-3.5 h-3.5" />
                        <span>Generate Summary</span>
                      </button>
                    </div>
                  )}
                </div>
              )}

              {/* ============================================================ */}
              {/* AST Code Metadata Header */}
              {/* ============================================================ */}
              <div className="pt-2 border-t border-surface-border/50">
                <div className="flex items-center justify-between mb-2">
                  <span className="text-[10px] font-mono uppercase tracking-wider text-slate-400 font-semibold flex items-center space-x-1.5">
                    <Code2 className="w-3 h-3 text-brand-400" />
                    <span>AST Code Metadata</span>
                  </span>
                  <span className="text-[10px] font-mono text-slate-500">
                    Static AST
                  </span>
                </div>
              </div>

              {/* Symbol Kind Filter Tabs */}
              {fileDetail?.symbols && fileDetail.symbols.length > 0 && (
                <div className="space-y-2">
                  <div className="flex items-center justify-between">
                    <span className="text-[11px] font-mono uppercase text-slate-400 font-semibold">
                      Symbols ({filteredSymbols.length})
                    </span>
                    <span className="text-[10px] text-slate-500">Click to jump</span>
                  </div>

                  {/* Search inside symbols */}
                  <input
                    type="text"
                    value={symbolFilter}
                    onChange={e => setSymbolFilter(e.target.value)}
                    placeholder="Filter symbols..."
                    className="w-full bg-surface-dark/90 border border-surface-border/60 rounded-xl px-2.5 py-1 text-xs text-slate-200 placeholder-slate-500 focus:outline-none focus:border-brand-500/50"
                  />

                  {/* Kind Pills */}
                  <div className="flex flex-wrap gap-1 pt-1">
                    {['ALL', 'CLASS', 'FUNCTION', 'METHOD', 'INTERFACE'].map(kind => (
                      <button
                        key={kind}
                        onClick={() => setSelectedKind(kind)}
                        className={`text-[10px] font-mono px-2 py-0.5 rounded-full cursor-pointer transition-colors ${
                          selectedKind === kind
                            ? 'bg-brand-500 text-surface-darkest font-bold'
                            : 'bg-surface-dark text-slate-400 hover:text-slate-200'
                        }`}
                      >
                        {kind}
                      </button>
                    ))}
                  </div>

                  {/* Symbol List */}
                  <div className="space-y-1 pt-1 max-h-56 overflow-y-auto custom-scrollbar">
                    {filteredSymbols.map(sym => (
                      <div
                        key={sym.id}
                        onClick={() => setTargetLine(sym.start_line)}
                        className="p-2 rounded-xl bg-surface-darker/70 hover:bg-brand-500/10 border border-surface-border/40 hover:border-brand-500/40 cursor-pointer transition-all flex items-center justify-between group"
                      >
                        <div className="min-w-0 pr-2">
                          <div className="flex items-center space-x-1.5">
                            <span
                              className={`text-[9px] font-mono uppercase px-1.5 py-0.2 rounded font-bold ${
                                sym.kind === 'CLASS'
                                  ? 'bg-purple-950 text-purple-300 border border-purple-800/40'
                                  : sym.kind === 'INTERFACE'
                                  ? 'bg-sky-950 text-sky-300 border border-sky-800/40'
                                  : sym.kind === 'METHOD'
                                  ? 'bg-amber-950 text-amber-300 border border-amber-800/40'
                                  : 'bg-emerald-950 text-emerald-300 border border-emerald-800/40'
                              }`}
                            >
                              {sym.kind.substring(0, 3)}
                            </span>
                            <span className="text-xs font-mono font-medium text-slate-200 truncate group-hover:text-brand-300">
                              {sym.name}
                            </span>
                          </div>
                          {sym.scope && (
                            <div className="text-[10px] font-mono text-slate-500 truncate mt-0.5">
                              scope: {sym.scope}
                            </div>
                          )}
                        </div>

                        <div className="flex items-center space-x-1.5 flex-shrink-0">
                          <button
                            type="button"
                            onClick={(e) => {
                              e.stopPropagation();
                              setExplainModal({
                                isOpen: true,
                                startLine: sym.start_line,
                                endLine: sym.end_line,
                                symbolName: sym.name,
                              });
                            }}
                            className="p-1 rounded-lg text-slate-500 hover:text-brand-300 hover:bg-brand-500/15 opacity-0 group-hover:opacity-100 transition-opacity cursor-pointer"
                            title={`Explain ${sym.name}`}
                          >
                            <Sparkles className="w-3 h-3" />
                          </button>
                          <span className="text-[10px] font-mono text-slate-500 group-hover:text-brand-400">
                            L{sym.start_line}
                          </span>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Imports Section */}
              {fileDetail?.imports && fileDetail.imports.length > 0 && (
                <div className="space-y-1.5 pt-2 border-t border-surface-border/40">
                  <div className="text-[11px] font-mono uppercase text-slate-400 font-semibold flex items-center justify-between">
                    <span>Dependencies ({fileDetail.imports.length})</span>
                  </div>
                  <div className="space-y-1 max-h-40 overflow-y-auto custom-scrollbar">
                    {fileDetail.imports.map(imp => (
                      <div
                        key={imp.id}
                        className="px-2.5 py-1.5 rounded-lg bg-surface-darker/60 border border-surface-border/30 text-[11px] font-mono flex items-center justify-between"
                      >
                        <span className="text-slate-300 truncate">
                          {imp.source_module}
                        </span>
                        {imp.imported_symbol && (
                          <span className="text-brand-400 text-[10px] truncate ml-2">
                            {imp.imported_symbol}
                          </span>
                        )}
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Chunks Section */}
              {fileDetail?.chunks && fileDetail.chunks.length > 0 && (
                <div className="space-y-1.5 pt-2 border-t border-surface-border/40">
                  <div className="text-[11px] font-mono uppercase text-slate-400 font-semibold flex items-center justify-between">
                    <span>Semantic Chunks ({fileDetail.chunks.length})</span>
                  </div>
                  <div className="space-y-1 max-h-36 overflow-y-auto custom-scrollbar">
                    {fileDetail.chunks.map(chk => (
                      <div
                        key={chk.id}
                        onClick={() => setTargetLine(chk.start_line)}
                        className="p-2 rounded-lg bg-surface-darker/60 border border-surface-border/30 text-[10px] font-mono flex items-center justify-between hover:border-brand-500/40 cursor-pointer"
                      >
                        <div className="flex items-center space-x-1.5">
                          <span className="text-slate-400">{chk.chunk_type}</span>
                          <span className="text-slate-600">•</span>
                          <span className="text-slate-500">{chk.token_count} tokens</span>
                        </div>
                        <span className="text-slate-400">
                          L{chk.start_line}-{chk.end_line}
                        </span>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          </div>
        )}
      </div>

      {fileDetail && (
        <CodeExplainModal
          isOpen={explainModal.isOpen}
          onClose={() => setExplainModal({ isOpen: false })}
          repositoryId={repositoryId}
          filePath={fileDetail.path}
          totalLines={fileDetail.line_count}
          initialStartLine={explainModal.startLine}
          initialEndLine={explainModal.endLine}
          symbolName={explainModal.symbolName}
          onNavigateToLocation={(path, line) => {
            setSelectedPath(path);
            setTargetLine(line);
            if (onFileSelect) onFileSelect(path);
          }}
        />
      )}
    </div>
  );
};
