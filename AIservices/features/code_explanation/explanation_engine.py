"""
Explanation Engine Orchestrator for Feature 2: AI Code Explanation.
Coordinates code resolution, context retrieval via Feature 1, LLM/static generation,
and structured response formatting.
"""

from __future__ import annotations

import logging
from typing import Optional

from AIservices.core.language_utils import detect_language
from AIservices.core.models import RepoIndex, SupportedLanguage
from AIservices.features.code_explanation.context_resolver import (
    resolve_repository_context,
)
from AIservices.features.code_explanation.llm_provider import (
    StaticAnalysisProvider,
    get_llm_provider,
)
from AIservices.features.code_explanation.models import (
    CitationItem,
    ExplanationRequest,
    ExplanationResponse,
    RelatedSymbolContext,
)

logger = logging.getLogger(__name__)


def _infer_language_from_code(code: str) -> str:
    """Heuristic fallback to identify programming language from code constructs."""
    if "def " in code or "import " in code and ":" in code:
        return SupportedLanguage.PYTHON.value
    if "func " in code or "package " in code and ":=" in code:
        return SupportedLanguage.GO.value
    if "public class " in code or "System.out.println" in code:
        return SupportedLanguage.JAVA.value
    if "interface " in code or "type " in code or ": string" in code or ": number" in code:
        return SupportedLanguage.TYPESCRIPT.value
    if "const " in code or "let " in code or "function " in code or "console.log" in code:
        return SupportedLanguage.JAVASCRIPT.value
    return "text"


def _format_raw_markdown(
    overview: str,
    step_by_step: list[str],
    inputs: Optional[str],
    outputs: Optional[str],
    important_symbols: list[str],
    side_effects: list[str],
    edge_cases: list[str],
    related_symbols: list[RelatedSymbolContext],
    limitations: list[str],
    question: Optional[str],
) -> str:
    """Combine structured fields into a polished markdown document."""
    sections = []

    if question:
        sections.append(f"### Question\n> **{question}**\n")

    sections.append(f"### Overview\n{overview}\n")

    if step_by_step:
        steps_text = "\n".join(f"- {s}" for s in step_by_step)
        sections.append(f"### How the Code Works\n{steps_text}\n")

    if inputs or outputs:
        io_parts = []
        if inputs:
            io_parts.append(f"**Inputs:** {inputs}")
        if outputs:
            io_parts.append(f"**Outputs:** {outputs}")
        sections.append(f"### Inputs and Outputs\n" + "\n\n".join(io_parts) + "\n")

    if important_symbols or related_symbols:
        sym_parts = []
        for s in important_symbols:
            sym_parts.append(f"- {s}")
        for r in related_symbols:
            sym_parts.append(f"- **{r.name}** ({r.kind}) in `{r.file_path}`: {r.relevance_reason}")
        sections.append(f"### Important Variables & Dependencies\n" + "\n".join(sym_parts) + "\n")

    if edge_cases or side_effects:
        ec_parts = []
        for e in edge_cases:
            ec_parts.append(f"- {e}")
        for s in side_effects:
            ec_parts.append(f"- **Side effect:** {s}")
        sections.append(f"### Potential Edge Cases & Side Effects\n" + "\n".join(ec_parts) + "\n")

    if limitations:
        lim_text = "\n".join(f"- ⚠️ {l}" for l in limitations)
        sections.append(f"### Limitations & Missing Context\n{lim_text}\n")

    return "\n".join(sections)


def explain_code(request: ExplanationRequest, index: RepoIndex) -> ExplanationResponse:
    """
    Generate a context-aware, structured explanation for selected code.

    Raises:
        ValueError: For missing index, wrong repository snapshot, or invalid/empty input code.
    """
    # 1. Validate repository snapshot ownership
    if index.repo_id != request.repo_id:
        raise ValueError(
            f"Index repo_id '{index.repo_id}' does not match request repo_id '{request.repo_id}'"
        )
    if index.snapshot_id != request.snapshot_id:
        raise ValueError(
            f"Index snapshot_id '{index.snapshot_id}' does not match request snapshot_id '{request.snapshot_id}'"
        )

    code = request.code
    file_path = request.file_path
    start_line = request.start_line
    end_line = request.end_line

    # 2. Resolve code from symbol_id if provided
    if not code and request.symbol_id and index.symbols:
        for sym in index.symbols:
            if sym.symbol_id == request.symbol_id:
                code = sym.snippet
                file_path = sym.file_path
                start_line = sym.start_line
                end_line = sym.end_line
                break

    # 3. Resolve code from file_path + line range if code was not explicitly provided
    if not code and file_path and start_line and end_line and index.files:
        source_text = index.files.get(file_path)
        if source_text:
            lines = source_text.splitlines()
            if 1 <= start_line <= len(lines):
                actual_end = min(end_line, len(lines))
                code = "\n".join(lines[start_line - 1: actual_end])

    # 4. Guard against missing or empty code
    if not code or not code.strip():
        raise ValueError(
            "Selected code snippet is empty or could not be resolved from provided coordinates."
        )

    # 5. Detect language
    language = "unknown"
    if file_path:
        lang_enum = detect_language(file_path)
        if lang_enum != SupportedLanguage.UNKNOWN:
            language = lang_enum.value
    if language == "unknown":
        language = _infer_language_from_code(code)

    # 6. Retrieve repository context using Feature 1
    related_symbols, citations, limitations = resolve_repository_context(
        snippet=code,
        repo_id=request.repo_id,
        snapshot_id=request.snapshot_id,
        index=index,
        file_path=file_path,
        start_line=start_line,
        end_line=end_line,
    )

    # 7. Generate explanation using provider (with immediate static analyzer fallback)
    provider = get_llm_provider()
    try:
        data = provider.generate_explanation(
            code=code,
            language=language,
            question=request.question,
            style=request.explanation_style,
            related_symbols=related_symbols,
            limitations=limitations,
        )
    except Exception as exc:
        logger.warning("LLM provider execution failed: %s — falling back to static analyzer", exc)
        data = StaticAnalysisProvider().generate_explanation(
            code=code,
            language=language,
            question=request.question,
            style=request.explanation_style,
            related_symbols=related_symbols,
            limitations=limitations,
        )

    # 8. Build full readable markdown presentation
    raw_explanation = _format_raw_markdown(
        overview=data.get("overview", "Code explanation"),
        step_by_step=data.get("step_by_step", []),
        inputs=data.get("inputs"),
        outputs=data.get("outputs"),
        important_symbols=data.get("important_symbols", []),
        side_effects=data.get("side_effects", []),
        edge_cases=data.get("edge_cases", []),
        related_symbols=related_symbols,
        limitations=limitations,
        question=request.question,
    )

    return ExplanationResponse(
        repo_id=request.repo_id,
        snapshot_id=request.snapshot_id,
        file_path=file_path,
        language=language,
        selected_code=code,
        question=request.question,
        explanation_style=request.explanation_style.value if hasattr(request.explanation_style, "value") else str(request.explanation_style),
        overview=data.get("overview", "Code explanation"),
        step_by_step=data.get("step_by_step", []),
        inputs=data.get("inputs"),
        outputs=data.get("outputs"),
        important_symbols=data.get("important_symbols", []),
        side_effects=data.get("side_effects", []),
        edge_cases=data.get("edge_cases", []),
        related_symbols=related_symbols,
        citations=citations,
        limitations=limitations,
        raw_explanation=raw_explanation,
    )
