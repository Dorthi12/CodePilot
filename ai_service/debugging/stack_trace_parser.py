"""Multi-language stack trace parser and longest-suffix file mapper.

Specifications:
- Master Architecture Specification v2.1 §10 (M2), AUD-11
- Security & Testing Specification v1.0 §7.3.3 (SEC-API-06, UT-05)
Supports Python tracebacks, Node/V8 stack traces, Java stack traces, and Go panics.
Maps frames to repository files via longest-suffix match without guessing ambiguous paths.
"""

import os
import re
from typing import Dict, List, Optional, Set, Tuple
from unicodedata import normalize

from shared.types.investigation import (
    InvestigationFrame,
    ParsedStackTrace,
    StackTraceLanguage,
)
from ai_service.security_analysis.secret_detector import redact_secrets


def normalize_repo_path(path: str) -> str:
    """Normalize a path according to SEC-API-06 (NFC, forward slashes, stripped bounds)."""
    if not path:
        return ""
    # NFC normalization
    norm = normalize("NFC", path)
    # Forward slashes and strip whitespace/null
    norm = norm.replace("\\", "/").replace("\0", "").strip()
    # Strip drive letter if present on Windows (e.g. C:)
    if re.match(r"^[a-zA-Z]:", norm):
        norm = norm[2:]
    # Strip leading slashes and dot-slash
    norm = norm.lstrip("/")
    while norm.startswith("./"):
        norm = norm[2:]
    return norm


def match_longest_suffix(raw_path: str, repo_files: List[str]) -> Tuple[Optional[str], bool, List[str]]:
    """Match a raw stack-frame path against repository files using longest suffix matching.

    Returns:
        (best_match, is_ambiguous, candidates)
        - If an unambiguous longest suffix match is found: (matched_path, False, [matched_path])
        - If ambiguous matches exist with identical longest suffix: (None, True, candidates)
        - If no match found: (None, False, [])
    """
    clean_raw = normalize_repo_path(raw_path)
    if not clean_raw or not repo_files:
        return None, False, []

    raw_parts = [p.lower() for p in clean_raw.split("/") if p]
    if not raw_parts:
        return None, False, []

    candidates_with_score: List[Tuple[int, str]] = []

    for rf in repo_files:
        clean_rf = normalize_repo_path(rf)
        rf_parts = [p.lower() for p in clean_rf.split("/") if p]
        if not rf_parts:
            continue

        # Check exact match first
        if clean_raw.lower() == clean_rf.lower():
            return clean_rf, False, [clean_rf]

        # Calculate longest common suffix length
        match_len = 0
        for r_part, f_part in zip(reversed(raw_parts), reversed(rf_parts)):
            if r_part == f_part:
                match_len += 1
            else:
                break

        if match_len > 0:
            candidates_with_score.append((match_len, clean_rf))

    if not candidates_with_score:
        return None, False, []

    # Find maximum suffix score
    candidates_with_score.sort(key=lambda x: x[0], reverse=True)
    max_score = candidates_with_score[0][0]
    top_matches = [path for score, path in candidates_with_score if score == max_score]

    # De-duplicate top matches
    unique_top = list(dict.fromkeys(top_matches))

    if len(unique_top) == 1:
        return unique_top[0], False, unique_top
    # Multiple files share identical longest suffix -> Ambiguous! Do not guess (AUD-11)
    return None, True, unique_top


class StackTraceParser:
    """Multi-language stack trace parser with automated language identification."""

    # Python patterns
    PYTHON_FRAME_RE = re.compile(
        r'^\s*File\s+"([^"]+)",\s+line\s+(\d+)(?:,\s+in\s+(.+))?',
        re.MULTILINE,
    )
    PYTHON_ERROR_RE = re.compile(
        r"^([a-zA-Z_][\w\.]*(?:Error|Exception|Warning|Fault|Interrupt|Exit|Fail)[\w]*):\s*(.*)$",
        re.MULTILINE,
    )

    # Node/V8 patterns
    NODE_FRAME_PAREN_RE = re.compile(
        r"^\s*at\s+(?:async\s+)?(?:(.+?)\s+\((.+?):(\d+):(\d+)\))",
        re.MULTILINE,
    )
    NODE_FRAME_BARE_RE = re.compile(
        r"^\s*at\s+(?:async\s+)?(?:(.+?):(\d+):(\d+))",
        re.MULTILINE,
    )
    NODE_ERROR_RE = re.compile(
        r"^([a-zA-Z_][\w]*(?:Error|Exception)?):\s*(.*)$",
        re.MULTILINE,
    )

    # Java patterns
    JAVA_FRAME_RE = re.compile(
        r"^\s*at\s+([\w\.\$]+)\.([\w\$<]+)\(([\w\.\-]+):(\d+)\)",
        re.MULTILINE,
    )
    JAVA_ERROR_RE = re.compile(
        r"^([a-zA-Z_][\w\.]*(?:Exception|Error))(?::\s*(.*))?$",
        re.MULTILINE,
    )

    # Go patterns
    GO_GOROUTINE_RE = re.compile(r"^goroutine\s+\d+\s+\[.*\]:", re.MULTILINE)
    GO_PANIC_RE = re.compile(r"^panic:\s*(.*)$", re.MULTILINE)
    GO_FRAME_FUNC_RE = re.compile(r"^([\w\.\/\-]+\.[\w]+)\(.*\)")
    GO_FRAME_FILE_RE = re.compile(r"^\s*([^\s:]+):(\d+)")

    def detect_language(self, trace_text: str) -> StackTraceLanguage:
        """Infer language format from trace syntax."""
        if not trace_text:
            return StackTraceLanguage.UNKNOWN

        if "Traceback (most recent call last):" in trace_text or 'File "' in trace_text:
            return StackTraceLanguage.PYTHON
        if "goroutine " in trace_text and "panic:" in trace_text:
            return StackTraceLanguage.GO
        if re.search(r"\bat\s+[\w\.\$]+\([\w\.\-]+:\d+\)", trace_text):
            return StackTraceLanguage.JAVA
        if re.search(r"\bat\s+(?:.*\(.*:\d+:\d+\)|.*:\d+:\d+)", trace_text):
            return StackTraceLanguage.NODE

        # Fallback keyword checks
        if "Exception:" in trace_text or "Error:" in trace_text:
            if "Traceback" in trace_text:
                return StackTraceLanguage.PYTHON
            if "\tat " in trace_text:
                return StackTraceLanguage.JAVA
            return StackTraceLanguage.NODE

        return StackTraceLanguage.UNKNOWN

    def parse(
        self,
        raw_trace: str,
        repo_files: Optional[List[str]] = None,
    ) -> ParsedStackTrace:
        """Parse raw stack trace, redact secrets, extract frames, and map to repo files."""
        repo_files = repo_files or []
        redacted = redact_secrets(raw_trace)
        lang = self.detect_language(redacted)

        if lang == StackTraceLanguage.PYTHON:
            parsed = self._parse_python(redacted, repo_files)
        elif lang == StackTraceLanguage.NODE:
            parsed = self._parse_node(redacted, repo_files)
        elif lang == StackTraceLanguage.JAVA:
            parsed = self._parse_java(redacted, repo_files)
        elif lang == StackTraceLanguage.GO:
            parsed = self._parse_go(redacted, repo_files)
        else:
            # Fallback heuristic: attempt Python then Node
            parsed = self._parse_python(redacted, repo_files)
            if not parsed.frames:
                parsed = self._parse_node(redacted, repo_files)
            if not parsed.frames:
                parsed.language = StackTraceLanguage.UNKNOWN

        parsed.raw_trace = raw_trace
        parsed.redacted_trace = redacted
        parsed.unmapped_frames_count = sum(1 for f in parsed.frames if not f.is_mapped)
        parsed.ambiguous_frames_count = sum(1 for f in parsed.frames if f.is_ambiguous)

        return parsed

    def _parse_python(self, text: str, repo_files: List[str]) -> ParsedStackTrace:
        frames: List[InvestigationFrame] = []
        lines = text.splitlines()

        error_class: Optional[str] = None
        error_message: Optional[str] = None

        # Extract frames
        i = 0
        frame_idx = 0
        while i < len(lines):
            line = lines[i]
            match = re.search(r'^\s*File\s+"([^"]+)",\s+line\s+(\d+)(?:,\s+in\s+(.+))?', line)
            if match:
                raw_path = match.group(1)
                line_no = int(match.group(2))
                func_name = match.group(3).strip() if match.group(3) else None

                code_line = None
                if i + 1 < len(lines) and not lines[i + 1].strip().startswith("File "):
                    code_line = lines[i + 1].strip()
                    i += 1

                best_match, is_ambiguous, candidates = match_longest_suffix(raw_path, repo_files)
                frames.append(
                    InvestigationFrame(
                        frame_index=frame_idx,
                        raw_file_path=raw_path,
                        mapped_file_path=best_match,
                        line=line_no,
                        function_name=func_name,
                        code_line=code_line,
                        is_mapped=bool(best_match),
                        is_ambiguous=is_ambiguous,
                        candidates=candidates,
                    )
                )
                frame_idx += 1
            else:
                # Check for trailing exception line
                err_match = self.PYTHON_ERROR_RE.search(line)
                if err_match:
                    error_class = err_match.group(1).strip()
                    error_message = err_match.group(2).strip()
            i += 1

        return ParsedStackTrace(
            language=StackTraceLanguage.PYTHON,
            error_class=error_class,
            error_message=error_message,
            frames=frames,
            raw_trace=text,
            redacted_trace=text,
        )

    def _parse_node(self, text: str, repo_files: List[str]) -> ParsedStackTrace:
        frames: List[InvestigationFrame] = []
        lines = text.splitlines()

        error_class: Optional[str] = None
        error_message: Optional[str] = None

        frame_idx = 0
        for line in lines:
            # Check error line first
            if not error_class:
                err_match = self.NODE_ERROR_RE.search(line)
                if err_match and not line.strip().startswith("at "):
                    error_class = err_match.group(1).strip()
                    error_message = err_match.group(2).strip()
                    continue

            # Check paren format: at func (/path/file.js:10:5)
            paren_match = self.NODE_FRAME_PAREN_RE.search(line)
            if paren_match:
                func_name = paren_match.group(1).strip() if paren_match.group(1) else None
                raw_path = paren_match.group(2).strip()
                line_no = int(paren_match.group(3))
                col_no = int(paren_match.group(4))

                best_match, is_ambiguous, candidates = match_longest_suffix(raw_path, repo_files)
                frames.append(
                    InvestigationFrame(
                        frame_index=frame_idx,
                        raw_file_path=raw_path,
                        mapped_file_path=best_match,
                        line=line_no,
                        column=col_no,
                        function_name=func_name,
                        is_mapped=bool(best_match),
                        is_ambiguous=is_ambiguous,
                        candidates=candidates,
                    )
                )
                frame_idx += 1
                continue

            # Check bare format: at /path/file.js:10:5
            bare_match = self.NODE_FRAME_BARE_RE.search(line)
            if bare_match:
                raw_path = bare_match.group(1).strip()
                line_no = int(bare_match.group(2))
                col_no = int(bare_match.group(3))

                best_match, is_ambiguous, candidates = match_longest_suffix(raw_path, repo_files)
                frames.append(
                    InvestigationFrame(
                        frame_index=frame_idx,
                        raw_file_path=raw_path,
                        mapped_file_path=best_match,
                        line=line_no,
                        column=col_no,
                        is_mapped=bool(best_match),
                        is_ambiguous=is_ambiguous,
                        candidates=candidates,
                    )
                )
                frame_idx += 1

        return ParsedStackTrace(
            language=StackTraceLanguage.NODE,
            error_class=error_class or "Error",
            error_message=error_message,
            frames=frames,
            raw_trace=text,
            redacted_trace=text,
        )

    def _parse_java(self, text: str, repo_files: List[str]) -> ParsedStackTrace:
        frames: List[InvestigationFrame] = []
        lines = text.splitlines()

        error_class: Optional[str] = None
        error_message: Optional[str] = None

        frame_idx = 0
        for line in lines:
            if not error_class:
                err_match = self.JAVA_ERROR_RE.search(line)
                if err_match and not line.strip().startswith("at "):
                    error_class = err_match.group(1).strip()
                    error_message = err_match.group(2).strip() if err_match.group(2) else ""
                    continue

            frame_match = self.JAVA_FRAME_RE.search(line)
            if frame_match:
                class_name = frame_match.group(1).strip()
                method_name = frame_match.group(2).strip()
                file_name = frame_match.group(3).strip()
                line_no = int(frame_match.group(4))

                # Construct package-based approximate path
                pkg_path = class_name.replace(".", "/")
                approx_path = f"{os.path.dirname(pkg_path)}/{file_name}" if "/" in pkg_path else file_name

                best_match, is_ambiguous, candidates = match_longest_suffix(approx_path, repo_files)
                frames.append(
                    InvestigationFrame(
                        frame_index=frame_idx,
                        raw_file_path=approx_path,
                        mapped_file_path=best_match,
                        line=line_no,
                        function_name=f"{class_name}.{method_name}",
                        is_mapped=bool(best_match),
                        is_ambiguous=is_ambiguous,
                        candidates=candidates,
                    )
                )
                frame_idx += 1

        return ParsedStackTrace(
            language=StackTraceLanguage.JAVA,
            error_class=error_class or "Exception",
            error_message=error_message,
            frames=frames,
            raw_trace=text,
            redacted_trace=text,
        )

    def _parse_go(self, text: str, repo_files: List[str]) -> ParsedStackTrace:
        frames: List[InvestigationFrame] = []
        lines = text.splitlines()

        error_class: Optional[str] = None
        error_message: Optional[str] = None

        panic_match = self.GO_PANIC_RE.search(text)
        if panic_match:
            error_class = "panic"
            error_message = panic_match.group(1).strip()

        frame_idx = 0
        i = 0
        while i < len(lines):
            line = lines[i].strip()
            func_match = self.GO_FRAME_FUNC_RE.match(line)
            if func_match and i + 1 < len(lines):
                func_name = func_match.group(1).strip()
                next_line = lines[i + 1].strip()
                file_match = self.GO_FRAME_FILE_RE.match(next_line)
                if file_match:
                    raw_path = file_match.group(1).strip()
                    line_no = int(file_match.group(2))

                    best_match, is_ambiguous, candidates = match_longest_suffix(raw_path, repo_files)
                    frames.append(
                        InvestigationFrame(
                            frame_index=frame_idx,
                            raw_file_path=raw_path,
                            mapped_file_path=best_match,
                            line=line_no,
                            function_name=func_name,
                            is_mapped=bool(best_match),
                            is_ambiguous=is_ambiguous,
                            candidates=candidates,
                        )
                    )
                    frame_idx += 1
                    i += 1
            i += 1

        return ParsedStackTrace(
            language=StackTraceLanguage.GO,
            error_class=error_class or "panic",
            error_message=error_message,
            frames=frames,
            raw_trace=text,
            redacted_trace=text,
        )
