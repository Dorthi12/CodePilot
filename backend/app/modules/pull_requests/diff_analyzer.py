"""PR Diff Analyzer: parsing unified diffs, extracting changed lines, and symbol mapping.

Specifications:
- Master Architecture Specification v2.1 §10 (M7)
- API and Data Specification v1.0 §3.4.15, §4.5, §4.11
- Security & Testing Specification v1.0 §7.3.3 (SEC-API-06), §8.9 (AI-16)
"""

import ast
import re
from typing import Dict, List, Optional, Set, Tuple

from agentic.common.agent_context import RepositorySnapshotContext, SnapshotContextRegistry
from shared.types.pull_requests import DiffHunk, FileChangeStatus, PRFile

_HEADER_OLD = re.compile(r"^---\s+(?:a/)?(.+)$")
_HEADER_NEW = re.compile(r"^\+\+\+\s+(?:b/)?(.+)$")
_HUNK_PATTERN = re.compile(r"^@@\s+-(\d+)(?:,(\d+))?\s+\+(\d+)(?:,(\d+))?\s+@@")


class PRDiffAnalyzer:
    """Analyzes unified diff text, tracks modified line anchors, and maps symbols."""

    @staticmethod
    def parse_diff(
        diff_text: str,
        pull_request_id: str = "default-pr",
    ) -> List[PRFile]:
        """Parse unified diff into PRFile models with line-level hunk details."""
        if not diff_text or not diff_text.strip():
            return []

        files: Dict[str, PRFile] = {}
        current_file_path: Optional[str] = None
        current_hunk: Optional[DiffHunk] = None
        current_change_status = FileChangeStatus.MODIFIED

        old_file_path = None
        lines = diff_text.splitlines()

        i = 0
        while i < len(lines):
            line = lines[i]

            # Detect old file header (--- a/...)
            if line.startswith("--- "):
                m = _HEADER_OLD.match(line)
                if m:
                    old_file_path = m.group(1).strip()
                i += 1
                continue

            # Detect new file header (+++ b/...)
            if line.startswith("+++ "):
                m = _HEADER_NEW.match(line)
                if m:
                    new_path = m.group(1).strip()
                    if new_path == "/dev/null":
                        # Removed file
                        current_file_path = (old_file_path or "").replace("\\", "/").lstrip("/")
                        current_change_status = FileChangeStatus.REMOVED
                    else:
                        current_file_path = new_path.replace("\\", "/").lstrip("/")
                        if old_file_path == "/dev/null":
                            current_change_status = FileChangeStatus.ADDED
                        else:
                            current_change_status = FileChangeStatus.MODIFIED

                    if current_file_path and current_file_path not in files:
                        files[current_file_path] = PRFile(
                            pull_request_id=pull_request_id,
                            path=current_file_path,
                            status=current_change_status,
                            additions=0,
                            deletions=0,
                            hunks=[],
                        )
                i += 1
                continue

            # Detect hunk header (@@ -start,len +start,len @@)
            if line.startswith("@@ "):
                m = _HUNK_PATTERN.match(line)
                if m and current_file_path and current_file_path in files:
                    orig_start = int(m.group(1))
                    orig_len = int(m.group(2) or 1)
                    mod_start = int(m.group(3))
                    mod_len = int(m.group(4) or 1)

                    current_hunk = DiffHunk(
                        file_path=current_file_path,
                        orig_start=orig_start,
                        orig_len=orig_len,
                        mod_start=mod_start,
                        mod_len=mod_len,
                        header=line,
                        added_lines=[],
                        deleted_lines=[],
                        context_lines=[],
                    )
                    files[current_file_path].hunks.append(current_hunk)

                    # Now parse the hunk body lines
                    current_mod_line = mod_start
                    current_orig_line = orig_start

                    i += 1
                    while i < len(lines):
                        hline = lines[i]
                        if hline.startswith(("@@ ", "--- ", "+++ ")):
                            break

                        if hline.startswith("+"):
                            current_hunk.added_lines.append(current_mod_line)
                            files[current_file_path].additions += 1
                            current_mod_line += 1
                        elif hline.startswith("-"):
                            current_hunk.deleted_lines.append(current_orig_line)
                            files[current_file_path].deletions += 1
                            current_orig_line += 1
                        elif hline.startswith(" ") or not hline:
                            current_hunk.context_lines.append(current_mod_line)
                            current_mod_line += 1
                            current_orig_line += 1
                        i += 1
                    continue

            i += 1

        return list(files.values())

    @staticmethod
    def extract_changed_line_numbers(pr_files: List[PRFile]) -> Dict[str, Set[int]]:
        """Return a mapping of file_path -> set of 1-based changed/added line numbers in head."""
        mapping: Dict[str, Set[int]] = {}
        for f in pr_files:
            lines: Set[int] = set()
            for hunk in f.hunks:
                lines.update(hunk.added_lines)
            mapping[f.path] = lines
        return mapping

    @staticmethod
    def map_symbols_to_changes(
        pr_files: List[PRFile],
        snapshot_id: str,
    ) -> None:
        """Map changed lines in PR files to AST symbols in the repository snapshot."""
        if not SnapshotContextRegistry.contains(snapshot_id):
            return

        ctx = SnapshotContextRegistry.get(snapshot_id)

        for pr_file in pr_files:
            file_obj = ctx.get_file(pr_file.path)
            if not file_obj or not file_obj.content:
                continue

            changed_lines: Set[int] = set()
            for h in pr_file.hunks:
                changed_lines.update(h.added_lines)

            # Discover symbols in this file
            symbols_in_file = [s for s in ctx.symbols if s.file_path == pr_file.path]

            if not symbols_in_file and file_obj.language == "python":
                # Parse AST to find symbols dynamically
                try:
                    tree = ast.parse(file_obj.content)
                    for node in ast.walk(tree):
                        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                            start = getattr(node, "lineno", 1)
                            end = getattr(node, "end_lineno", start)
                            name = node.name
                            if any(start <= line <= end for line in changed_lines):
                                if name not in pr_file.mapped_symbols:
                                    pr_file.mapped_symbols.append(name)
                except Exception:
                    pass
            else:
                for sym in symbols_in_file:
                    if any(sym.start_line <= line <= sym.end_line for line in changed_lines):
                        if sym.name not in pr_file.mapped_symbols:
                            pr_file.mapped_symbols.append(sym.name)
