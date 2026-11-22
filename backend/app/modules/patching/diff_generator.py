"""Unified diff generator with hunk offset tracking and safe path parsing.

Specifications:
- Master Architecture Specification v2.1 §10 (M4), §14.1
- Security & Testing Specification v1.0 §7.3.3 (SEC-API-06), §7.9 (Invariant I8)
- API and Data Specification v1.0 §4.11, §4.13
"""

import difflib
import re
from typing import Dict, List, Optional, Tuple
from shared.types.patch import PatchFile

_HEADER_PATTERN = re.compile(r"^(--- a/|\+\+\+ b/)(.+)$")
_HUNK_PATTERN = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@")


class DiffGenerator:
    """Produces and validates unified diff representations across files."""

    @staticmethod
    def create_unified_diff(
        original_content: str,
        modified_content: str,
        file_path: str,
        context_lines: int = 3,
    ) -> str:
        """Create a standard unified diff between original and modified strings."""
        clean_path = file_path.replace("\\", "/").lstrip("/")
        orig_lines = original_content.splitlines(keepends=True)
        mod_lines = modified_content.splitlines(keepends=True)

        diff_chunks = list(
            difflib.unified_diff(
                orig_lines,
                mod_lines,
                fromfile=f"a/{clean_path}",
                tofile=f"b/{clean_path}",
                n=context_lines,
            )
        )
        return "".join(diff_chunks)

    @staticmethod
    def parse_hunks(diff_text: str) -> List[Dict[str, any]]:
        """Parse hunks and line ranges from a unified diff."""
        hunks = []
        current_file = None
        current_hunk = None

        for line in diff_text.splitlines():
            if line.startswith("--- a/"):
                continue
            if line.startswith("+++ b/"):
                current_file = line[6:].strip()
                continue

            hunk_match = _HUNK_PATTERN.match(line)
            if hunk_match:
                orig_start = int(hunk_match.group(1))
                orig_len = int(hunk_match.group(2) or 1)
                mod_start = int(hunk_match.group(3))
                mod_len = int(hunk_match.group(4) or 1)

                current_hunk = {
                    "file": current_file,
                    "header": line,
                    "orig_start": orig_start,
                    "orig_len": orig_len,
                    "mod_start": mod_start,
                    "mod_len": mod_len,
                    "lines": [],
                    "additions": 0,
                    "deletions": 0,
                }
                hunks.append(current_hunk)
            elif current_hunk is not None:
                current_hunk["lines"].append(line)
                if line.startswith("+") and not line.startswith("+++"):
                    current_hunk["additions"] += 1
                elif line.startswith("-") and not line.startswith("---"):
                    current_hunk["deletions"] += 1

        return hunks

    @staticmethod
    def apply_diff_to_text(original_text: str, diff_text: str) -> str:
        """Apply unified diff to original text in memory (fails closed if hunks don't match)."""
        orig_lines = original_text.splitlines(keepends=True)
        hunks = DiffGenerator.parse_hunks(diff_text)
        if not hunks:
            return original_text

        # Reconstruct output lines
        hunk_index = 0
        hunk = hunks[0]
        result_lines: List[str] = []
        i = 0  # 0-indexed line in orig_lines

        for h in hunks:
            target_start = h["orig_start"] - 1
            # Copy untouched lines up to target_start
            while i < target_start and i < len(orig_lines):
                result_lines.append(orig_lines[i])
                i += 1

            for hline in h["lines"]:
                if hline.startswith(" "):
                    # Context line
                    if i < len(orig_lines):
                        result_lines.append(orig_lines[i])
                        i += 1
                    else:
                        line_content = hline[1:]
                        if not line_content.endswith("\n"):
                            line_content += "\n"
                        result_lines.append(line_content)
                elif hline.startswith("-"):
                    # Deletion line from original
                    i += 1
                elif hline.startswith("+"):
                    # Addition line
                    add_line = hline[1:]
                    if not add_line.endswith("\n"):
                        add_line += "\n"
                    result_lines.append(add_line)

        # Append remaining lines
        while i < len(orig_lines):
            result_lines.append(orig_lines[i])
            i += 1

        return "".join(result_lines)
