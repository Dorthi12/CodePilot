"""
Context Resolver for Code Explanation.
Integrates with Feature 1 (Basic Code Search) to retrieve relevant repository context,
related functions/classes, enclosing scope, and identify missing dependencies.
"""

from __future__ import annotations

import re
from typing import Optional

from AIservices.core.models import CodeSymbol, RepoIndex, SearchRequest, SymbolKind
from AIservices.features.code_explanation.models import CitationItem, RelatedSymbolContext
from AIservices.features.code_search import search

# Common programming language keywords to ignore when scanning for referenced symbols
_COMMON_KEYWORDS = {
    # Python
    "def", "class", "return", "if", "elif", "else", "for", "while", "in", "is",
    "not", "and", "or", "try", "except", "finally", "with", "as", "raise", "pass",
    "import", "from", "lambda", "yield", "async", "await", "global", "nonlocal",
    "self", "cls", "None", "True", "False",
    # JavaScript / TypeScript
    "function", "const", "let", "var", "interface", "type", "enum", "export",
    "default", "extends", "implements", "public", "private", "protected", "static",
    "readonly", "abstract", "constructor", "super", "this", "new", "typeof",
    "instanceof", "null", "undefined", "true", "false", "void", "any", "number",
    "string", "boolean", "unknown", "never", "catch", "throw", "switch", "case",
    # Java
    "package", "public", "private", "protected", "static", "final", "abstract",
    "class", "interface", "enum", "implements", "extends", "throws", "throw",
    "try", "catch", "finally", "return", "void", "int", "double", "float", "long",
    "boolean", "byte", "short", "char", "super", "this", "null", "true", "false",
    # Go
    "func", "package", "import", "type", "struct", "interface", "var", "const",
    "return", "if", "else", "for", "range", "switch", "case", "select", "chan",
    "go", "defer", "map", "nil", "true", "false", "err", "error", "string", "int",
}


def extract_referenced_identifiers(snippet: str) -> list[str]:
    """
    Extract meaningful identifiers used in the snippet that might be
    definitions in other files (function calls, classes, interfaces).
    """
    # Match standard identifiers
    tokens = re.findall(r"\b[A-Za-z_][A-Za-z0-9_]{2,}\b", snippet)
    candidates = []
    seen = set()

    for token in tokens:
        if token not in _COMMON_KEYWORDS and token not in seen:
            seen.add(token)
            candidates.append(token)

    return candidates


def resolve_repository_context(
    snippet: str,
    repo_id: str,
    snapshot_id: str,
    index: RepoIndex,
    file_path: Optional[str] = None,
    start_line: Optional[int] = None,
    end_line: Optional[int] = None,
) -> tuple[list[RelatedSymbolContext], list[CitationItem], list[str]]:
    """
    Query Feature 1's search engine and repository index to retrieve
    related symbols, definitions, citations, and identify missing context.

    Returns:
        (related_symbols, citations, limitations)
    """
    related_symbols: list[RelatedSymbolContext] = []
    citations: list[CitationItem] = []
    limitations: list[str] = []

    # 1. Add primary citation for the selected code if file_path is available
    if file_path and start_line and end_line:
        citations.append(
            CitationItem(
                source_id=f"{repo_id}:{file_path}:{start_line}-{end_line}",
                file_path=file_path,
                start_line=start_line,
                end_line=end_line,
                symbol_name=None,
                snippet=snippet[:300],
            )
        )

    # 2. Extract referenced symbols and search the repository using Feature 1
    identifiers = extract_referenced_identifiers(snippet)
    seen_symbols = set()

    # Track which candidates were found in the repo
    for ident in identifiers[:8]:  # Limit to top candidate identifiers to prevent overhead
        try:
            search_req = SearchRequest(
                repo_id=repo_id,
                snapshot_id=snapshot_id,
                query=ident,
                top_k=2,
            )
            res = search(search_req, index)
            found_def = False

            for item in res.results:
                # Disregard the exact same location if within the same file and lines
                if (
                    file_path
                    and item.file_path == file_path
                    and start_line
                    and end_line
                    and (start_line <= item.start_line <= end_line)
                ):
                    continue

                if item.name.lower() == ident.lower() and item.score >= 0.8:
                    sym_key = (item.file_path, item.name, item.start_line)
                    if sym_key not in seen_symbols:
                        seen_symbols.add(sym_key)
                        related_symbols.append(
                            RelatedSymbolContext(
                                name=item.name,
                                kind=item.kind,
                                file_path=item.file_path,
                                start_line=item.start_line,
                                end_line=item.end_line,
                                snippet=item.snippet,
                                relevance_reason=f"Referenced symbol '{ident}' defined in {item.file_path}",
                            )
                        )
                        citations.append(
                            CitationItem(
                                source_id=item.source_id,
                                file_path=item.file_path,
                                start_line=item.start_line,
                                end_line=item.end_line,
                                symbol_name=item.name,
                                snippet=item.snippet[:300],
                            )
                        )
                    found_def = True
                    break

            # If an identifier looks like a call or explicit type and was not found
            if not found_def and (f"{ident}(" in snippet or f"new {ident}" in snippet):
                limitations.append(
                    f"Definition for referenced symbol '{ident}' was not found in repository index (may be an external library or unindexed dependency)."
                )

        except Exception:
            pass

    # 3. Check enclosing scope if file and lines are known
    if file_path and start_line and index.symbols:
        for sym in index.symbols:
            if (
                sym.file_path == file_path
                and sym.kind in (SymbolKind.CLASS, SymbolKind.INTERFACE)
                and sym.start_line <= start_line <= sym.end_line
            ):
                if (sym.file_path, sym.name, sym.start_line) not in seen_symbols:
                    seen_symbols.add((sym.file_path, sym.name, sym.start_line))
                    related_symbols.append(
                        RelatedSymbolContext(
                            name=sym.name,
                            kind=sym.kind.value if hasattr(sym.kind, "value") else str(sym.kind),
                            file_path=sym.file_path,
                            start_line=sym.start_line,
                            end_line=sym.end_line,
                            snippet=sym.snippet,
                            relevance_reason=f"Enclosing {sym.kind.value if hasattr(sym.kind, 'value') else sym.kind} for the selected code",
                        )
                    )
                break

    return related_symbols, citations, limitations
