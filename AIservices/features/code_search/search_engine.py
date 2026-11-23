"""
Feature 1: Basic Code Search — Search Engine.

Implements the ranked, filtered, multi-mode search over a RepoIndex.

Search modes
------------
exact  — the query string appears verbatim in symbol name or qualified_name
         (case-insensitive).
symbol — the query matches a symbol name as a word-boundary prefix/suffix.
fuzzy  — tokens of the query appear across name + file_path + snippet.

Results are ranked by a composite score and de-duplicated by symbol_id.

This module is intentionally stateless: it receives a RepoIndex and returns
ranked results. Callers are responsible for caching / persistence.
"""

from __future__ import annotations

import re
from AIservices.core.models import (
    CodeSymbol,
    RepoIndex,
    SearchFilters,
    SearchRequest,
    SearchResponse,
    SearchResultItem,
    SymbolKind,
    SupportedLanguage,
)


# ---------------------------------------------------------------------------
# Scoring helpers
# ---------------------------------------------------------------------------

def _score_exact(query_lower: str, symbol: CodeSymbol) -> float:
    """1.0 if query equals name exactly, 0.9 if name starts with query."""
    name_lower = symbol.name.lower()
    qname_lower = symbol.qualified_name.lower()
    if name_lower == query_lower or qname_lower == query_lower:
        return 1.0
    if name_lower.startswith(query_lower) or qname_lower.startswith(query_lower):
        return 0.9
    if query_lower in name_lower or query_lower in qname_lower:
        return 0.8
    return 0.0


def _score_symbol(query_lower: str, symbol: CodeSymbol) -> float:
    """Word-boundary match in name, qualified_name, or signature."""
    targets = [symbol.name.lower(), symbol.qualified_name.lower()]
    if symbol.signature:
        targets.append(symbol.signature.lower())

    score = 0.0
    for target in targets:
        if re.search(r'\b' + re.escape(query_lower) + r'\b', target):
            score = max(score, 0.75)
        elif query_lower in target:
            score = max(score, 0.6)
    return score


def _score_fuzzy(tokens: list[str], symbol: CodeSymbol) -> float:
    """Fraction of query tokens found in the combined symbol text."""
    combined = " ".join([
        symbol.name.lower(),
        symbol.qualified_name.lower(),
        symbol.file_path.lower(),
        (symbol.snippet or "").lower()[:300],
    ])
    if not tokens:
        return 0.0
    hits = sum(1 for tok in tokens if tok in combined)
    return (hits / len(tokens)) * 0.5


def _score(query: str, symbol: CodeSymbol) -> tuple[float, str]:
    """
    Return (score, match_type) for *symbol* against *query*.
    score == 0.0 means "no match".
    """
    q = query.strip().lower()
    tokens = [t for t in re.split(r"\W+", q) if len(t) >= 2]

    exact = _score_exact(q, symbol)
    if exact > 0:
        return exact, "exact"

    sym = _score_symbol(q, symbol)
    if sym > 0:
        return sym, "symbol"

    fuzz = _score_fuzzy(tokens, symbol)
    if fuzz > 0:
        return fuzz, "fuzzy"

    return 0.0, "none"


# ---------------------------------------------------------------------------
# Filtering
# ---------------------------------------------------------------------------

def _apply_filters(symbols: list[CodeSymbol], filters: SearchFilters | None) -> list[CodeSymbol]:
    if not filters:
        return symbols

    result = symbols

    if filters.kinds:
        allowed = {k.value if hasattr(k, "value") else k for k in filters.kinds}
        result = [s for s in result if s.kind in allowed]

    if filters.languages:
        allowed = {lg.value if hasattr(lg, "value") else lg for lg in filters.languages}
        result = [s for s in result if s.language in allowed]

    if filters.path_prefix:
        prefix = filters.path_prefix.rstrip("/")
        result = [s for s in result if s.file_path.startswith(prefix)]

    return result


# ---------------------------------------------------------------------------
# Public search entry point
# ---------------------------------------------------------------------------

def search(request: SearchRequest, index: RepoIndex) -> SearchResponse:
    """
    Execute a code search against *index*.

    Raises ValueError for invalid requests (wrong repo/snapshot).
    Returns SearchResponse with an empty results list (and a warning) when
    there are no matches — never raises for "no results found" cases.
    """
    warnings: list[str] = list(index.warnings)

    # Validate ownership
    if index.repo_id != request.repo_id:
        raise ValueError(
            f"Index repo_id '{index.repo_id}' does not match request repo_id '{request.repo_id}'"
        )
    if index.snapshot_id != request.snapshot_id:
        raise ValueError(
            f"Index snapshot_id '{index.snapshot_id}' does not match request snapshot_id '{request.snapshot_id}'"
        )

    # Guard: empty index
    if not index.symbols:
        warnings.append("Repository index is empty — no symbols were extracted.")
        return SearchResponse(
            repo_id=request.repo_id,
            snapshot_id=request.snapshot_id,
            query=request.query,
            total=0,
            results=[],
            warnings=warnings,
        )

    # Apply filters
    candidates = _apply_filters(index.symbols, request.filters)

    if not candidates:
        warnings.append("No symbols match the applied filters.")
        return SearchResponse(
            repo_id=request.repo_id,
            snapshot_id=request.snapshot_id,
            query=request.query,
            total=0,
            results=[],
            warnings=warnings,
        )

    # Score
    scored: list[tuple[float, str, CodeSymbol]] = []
    for symbol in candidates:
        score, match_type = _score(request.query, symbol)
        if score > 0:
            scored.append((score, match_type, symbol))

    if not scored:
        warnings.append(f"No symbols matched query '{request.query}'.")
        return SearchResponse(
            repo_id=request.repo_id,
            snapshot_id=request.snapshot_id,
            query=request.query,
            total=0,
            results=[],
            warnings=warnings,
        )

    # Sort by score descending, then by name asc for stability
    scored.sort(key=lambda t: (-t[0], t[2].name))

    # De-duplicate by symbol_id (keep highest score)
    seen: set[str] = set()
    deduped: list[tuple[float, str, CodeSymbol]] = []
    for score, match_type, sym in scored:
        if sym.symbol_id not in seen:
            seen.add(sym.symbol_id)
            deduped.append((score, match_type, sym))

    # Apply top_k
    top = deduped[: request.top_k]

    results = [
        SearchResultItem(
            source_id=sym.symbol_id,
            repo_id=sym.repo_id,
            snapshot_id=sym.snapshot_id,
            file_path=sym.file_path,
            language=sym.language,
            kind=sym.kind,
            name=sym.name,
            qualified_name=sym.qualified_name,
            start_line=sym.start_line,
            end_line=sym.end_line,
            snippet=sym.snippet,
            score=round(score, 4),
            match_type=match_type,
            signature=sym.signature,
        )
        for score, match_type, sym in top
    ]

    return SearchResponse(
        repo_id=request.repo_id,
        snapshot_id=request.snapshot_id,
        query=request.query,
        total=len(results),
        results=results,
        warnings=warnings,
    )
