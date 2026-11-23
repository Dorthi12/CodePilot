"""
Tree-sitter–based symbol extractor.

Supported languages: Python, JavaScript, TypeScript, Java, Go.

For each supported language we define a set of *visitor rules*: each rule
maps a Tree-sitter node type to a (SymbolKind, name-extraction-function).
The extractor walks every file's syntax tree and collects CodeSymbol objects.

Design notes
------------
* This module has NO side-effects on import — parsers are built lazily.
* All symbols get a deterministic ``symbol_id`` so callers can reference them
  stably across calls (matches the ``source_id`` concept in the Master Spec).
* Parsing errors for a single file are recorded as warnings rather than
  raising exceptions, following the "continue on failure" principle (§5.3).
"""

from __future__ import annotations

import hashlib
import logging
import re
from dataclasses import dataclass, field
from typing import Callable, Optional

from AIservices.core.language_utils import detect_language, is_supported
from AIservices.core.models import CodeSymbol, RepoIndex, SymbolKind, SupportedLanguage

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_symbol_id(repo_id: str, file_path: str, kind: str, qualified_name: str, start_line: int) -> str:
    """Deterministic SHA-256–based id (first 16 hex chars for readability)."""
    raw = f"{repo_id}|{file_path}|{kind}|{qualified_name}|{start_line}"
    return hashlib.sha256(raw.encode()).hexdigest()[:32]


def _node_text(node, source: bytes) -> str:
    return source[node.start_byte:node.end_byte].decode("utf-8", errors="replace")


def _node_lines(source_lines: list[str], start_row: int, end_row: int) -> str:
    """Return the lines [start_row, end_row] (0-indexed, inclusive)."""
    return "\n".join(source_lines[start_row: end_row + 1])


# ---------------------------------------------------------------------------
# Visitor rule definition
# ---------------------------------------------------------------------------

@dataclass
class VisitorRule:
    node_type: str
    kind: SymbolKind
    # Returns (name, qualified_name_suffix, signature?) from the matched node
    extract: Callable  # (node, source_bytes, parent_name) -> (name, qname, sig)


# ---------------------------------------------------------------------------
# Language-specific visitor rules
# ---------------------------------------------------------------------------

def _child_text(node, field_name: str, source: bytes) -> Optional[str]:
    child = node.child_by_field_name(field_name)
    return _node_text(child, source) if child else None


# ---- Python ----------------------------------------------------------------

def _py_function(node, source: bytes, parent: str):
    name = _child_text(node, "name", source) or "?"
    params_node = node.child_by_field_name("parameters")
    sig = f"def {name}{_node_text(params_node, source) if params_node else '()'}"
    return name, f"{parent}.{name}" if parent else name, sig


def _py_class(node, source: bytes, parent: str):
    name = _child_text(node, "name", source) or "?"
    return name, f"{parent}.{name}" if parent else name, f"class {name}"


def _py_import(node, source: bytes, parent: str):
    text = _node_text(node, source).strip()
    # Use first module name as the symbol name
    m = re.search(r"import\s+([^\s,;]+)", text)
    name = m.group(1) if m else text[:40]
    return name, name, text


def _py_import_from(node, source: bytes, parent: str):
    text = _node_text(node, source).strip()
    m = re.search(r"from\s+(\S+)\s+import", text)
    name = m.group(1) if m else text[:40]
    return name, name, text


def _py_variable(node, source: bytes, parent: str):
    # assignment: left side
    left = node.child_by_field_name("left") or (node.children[0] if node.children else None)
    name = _node_text(left, source).strip() if left else "?"
    # Keep only the identifier part
    name = name.split("=")[0].strip().split("[")[0].strip()
    qname = f"{parent}.{name}" if parent else name
    return name, qname, None


PYTHON_RULES: list[VisitorRule] = [
    VisitorRule("function_definition", SymbolKind.FUNCTION, _py_function),
    VisitorRule("decorated_definition", SymbolKind.FUNCTION, _py_function),
    VisitorRule("class_definition", SymbolKind.CLASS, _py_class),
    VisitorRule("import_statement", SymbolKind.IMPORT, _py_import),
    VisitorRule("import_from_statement", SymbolKind.IMPORT, _py_import_from),
    VisitorRule("expression_statement", SymbolKind.VARIABLE, _py_variable),
]


# ---- JavaScript / TypeScript -----------------------------------------------

def _js_function(node, source: bytes, parent: str):
    name_node = node.child_by_field_name("name")
    name = _node_text(name_node, source) if name_node else "<anonymous>"
    params_node = node.child_by_field_name("parameters")
    sig = f"function {name}{_node_text(params_node, source) if params_node else '()'}"
    return name, f"{parent}.{name}" if parent else name, sig


def _js_arrow(node, source: bytes, parent: str):
    # Arrow function assigned to a variable — parent visitor will have the name
    params_node = node.child_by_field_name("parameters") or node.child_by_field_name("parameter")
    sig = f"({_node_text(params_node, source) if params_node else ''}) => ..."
    return "<arrow>", parent or "<arrow>", sig


def _js_class(node, source: bytes, parent: str):
    name_node = node.child_by_field_name("name")
    name = _node_text(name_node, source) if name_node else "<anonymous>"
    return name, f"{parent}.{name}" if parent else name, f"class {name}"


def _js_method(node, source: bytes, parent: str):
    name_node = node.child_by_field_name("name")
    name = _node_text(name_node, source) if name_node else "?"
    return name, f"{parent}.{name}" if parent else name, f"{name}()"


def _js_import(node, source: bytes, parent: str):
    text = _node_text(node, source).strip()
    m = re.search(r'from\s+["\']([^"\']+)["\']', text)
    name = m.group(1) if m else text[:40]
    return name, name, text


def _js_variable_decl(node, source: bytes, parent: str):
    # const / let / var  x = ...
    decl = node.children[1] if len(node.children) > 1 else None
    if decl:
        name_node = decl.child_by_field_name("name")
        name = _node_text(name_node, source) if name_node else _node_text(decl, source)[:30]
    else:
        name = _node_text(node, source)[:30]
    name = name.strip()
    kind_word = _node_text(node.children[0], source) if node.children else "var"
    return name, f"{parent}.{name}" if parent else name, f"{kind_word} {name}"


def _js_export_named(node, source: bytes, parent: str):
    text = _node_text(node, source).strip()[:60]
    return text, text, None


JS_RULES: list[VisitorRule] = [
    VisitorRule("function_declaration", SymbolKind.FUNCTION, _js_function),
    VisitorRule("function", SymbolKind.FUNCTION, _js_function),
    VisitorRule("class_declaration", SymbolKind.CLASS, _js_class),
    VisitorRule("class", SymbolKind.CLASS, _js_class),
    VisitorRule("method_definition", SymbolKind.METHOD, _js_method),
    VisitorRule("arrow_function", SymbolKind.FUNCTION, _js_arrow),
    VisitorRule("import_statement", SymbolKind.IMPORT, _js_import),
    VisitorRule("lexical_declaration", SymbolKind.VARIABLE, _js_variable_decl),
    VisitorRule("variable_declaration", SymbolKind.VARIABLE, _js_variable_decl),
    VisitorRule("export_statement", SymbolKind.EXPORT, _js_export_named),
]

# TypeScript adds interface / type_alias on top of JS rules
def _ts_interface(node, source: bytes, parent: str):
    name_node = node.child_by_field_name("name")
    name = _node_text(name_node, source) if name_node else "?"
    return name, f"{parent}.{name}" if parent else name, f"interface {name}"


def _ts_type_alias(node, source: bytes, parent: str):
    name_node = node.child_by_field_name("name")
    name = _node_text(name_node, source) if name_node else "?"
    return name, f"{parent}.{name}" if parent else name, f"type {name}"


TS_RULES: list[VisitorRule] = JS_RULES + [
    VisitorRule("interface_declaration", SymbolKind.INTERFACE, _ts_interface),
    VisitorRule("type_alias_declaration", SymbolKind.TYPE_ALIAS, _ts_type_alias),
]


# ---- Java ------------------------------------------------------------------

def _java_class(node, source: bytes, parent: str):
    name_node = node.child_by_field_name("name")
    name = _node_text(name_node, source) if name_node else "?"
    return name, f"{parent}.{name}" if parent else name, f"class {name}"


def _java_method(node, source: bytes, parent: str):
    name_node = node.child_by_field_name("name")
    name = _node_text(name_node, source) if name_node else "?"
    params_node = node.child_by_field_name("parameters")
    sig = f"{name}{_node_text(params_node, source) if params_node else '()'}"
    return name, f"{parent}.{name}" if parent else name, sig


def _java_import(node, source: bytes, parent: str):
    text = _node_text(node, source).strip()
    # import com.example.Foo ;
    m = re.search(r"import\s+(?:static\s+)?([^\s;]+)", text)
    name = m.group(1) if m else text[:60]
    return name, name, text


def _java_field(node, source: bytes, parent: str):
    text = _node_text(node, source).strip()[:60]
    return text, f"{parent}.{text}" if parent else text, None


JAVA_RULES: list[VisitorRule] = [
    VisitorRule("class_declaration", SymbolKind.CLASS, _java_class),
    VisitorRule("interface_declaration", SymbolKind.INTERFACE, _java_class),
    VisitorRule("enum_declaration", SymbolKind.ENUM, _java_class),
    VisitorRule("method_declaration", SymbolKind.METHOD, _java_method),
    VisitorRule("constructor_declaration", SymbolKind.METHOD, _java_method),
    VisitorRule("import_declaration", SymbolKind.IMPORT, _java_import),
    VisitorRule("field_declaration", SymbolKind.FIELD, _java_field),
]


# ---- Go --------------------------------------------------------------------

def _go_function(node, source: bytes, parent: str):
    name_node = node.child_by_field_name("name")
    name = _node_text(name_node, source) if name_node else "?"
    params_node = node.child_by_field_name("parameters")
    result_node = node.child_by_field_name("result")
    sig = f"func {name}{_node_text(params_node, source) if params_node else '()'}"
    if result_node:
        sig += f" {_node_text(result_node, source)}"
    return name, name, sig


def _go_type(node, source: bytes, parent: str):
    # type_declaration contains type_spec children
    specs = [c for c in node.children if c.type == "type_spec"]
    if specs:
        name_node = specs[0].child_by_field_name("name")
        name = _node_text(name_node, source) if name_node else "?"
    else:
        name = _node_text(node, source)[:30]
    return name, name, f"type {name}"


def _go_import(node, source: bytes, parent: str):
    text = _node_text(node, source).strip()[:60]
    return text, text, None


def _go_var(node, source: bytes, parent: str):
    text = _node_text(node, source).strip()[:60]
    return text, text, None


GO_RULES: list[VisitorRule] = [
    VisitorRule("function_declaration", SymbolKind.FUNCTION, _go_function),
    VisitorRule("method_declaration", SymbolKind.METHOD, _go_function),
    VisitorRule("type_declaration", SymbolKind.CLASS, _go_type),
    VisitorRule("import_declaration", SymbolKind.IMPORT, _go_import),
    VisitorRule("var_declaration", SymbolKind.VARIABLE, _go_var),
    VisitorRule("const_declaration", SymbolKind.CONSTANT, _go_var),
]


RULES_BY_LANGUAGE: dict[SupportedLanguage, list[VisitorRule]] = {
    SupportedLanguage.PYTHON: PYTHON_RULES,
    SupportedLanguage.JAVASCRIPT: JS_RULES,
    SupportedLanguage.TYPESCRIPT: TS_RULES,
    SupportedLanguage.JAVA: JAVA_RULES,
    SupportedLanguage.GO: GO_RULES,
}


# ---------------------------------------------------------------------------
# Parser cache (lazy, built once per language)
# ---------------------------------------------------------------------------

_parser_cache: dict[SupportedLanguage, object] = {}


def _get_parser(language: SupportedLanguage):
    """Return a cached tree-sitter Parser for *language* (built on first call)."""
    if language in _parser_cache:
        return _parser_cache[language]

    try:
        import tree_sitter_python as tspython
        import tree_sitter_javascript as tsjavascript
        import tree_sitter_typescript as tstypescript
        import tree_sitter_java as tsjava
        import tree_sitter_go as tsgo
        from tree_sitter import Language, Parser

        _lang_map = {
            SupportedLanguage.PYTHON: Language(tspython.language()),
            SupportedLanguage.JAVASCRIPT: Language(tsjavascript.language()),
            SupportedLanguage.TYPESCRIPT: Language(tstypescript.language_typescript()),
            SupportedLanguage.JAVA: Language(tsjava.language()),
            SupportedLanguage.GO: Language(tsgo.language()),
        }

        for lang, ts_lang in _lang_map.items():
            p = Parser(ts_lang)
            _parser_cache[lang] = p

    except Exception as exc:
        logger.warning("tree-sitter parsers unavailable: %s — falling back to regex extractor", exc)
        for lang in SupportedLanguage:
            if lang != SupportedLanguage.UNKNOWN:
                _parser_cache[lang] = None

    return _parser_cache.get(language)


# ---------------------------------------------------------------------------
# Tree-sitter extraction
# ---------------------------------------------------------------------------

def _extract_with_tree_sitter(
    source_bytes: bytes,
    source_lines: list[str],
    language: SupportedLanguage,
    file_path: str,
    repo_id: str,
    snapshot_id: str,
) -> list[CodeSymbol]:
    """Walk the AST and collect symbols using language-specific visitor rules."""
    parser = _get_parser(language)
    if parser is None:
        return []

    rules = RULES_BY_LANGUAGE.get(language, [])
    if not rules:
        return []

    rule_map = {r.node_type: r for r in rules}

    try:
        tree = parser.parse(source_bytes)
    except Exception as exc:
        logger.warning("Parse error in %s: %s", file_path, exc)
        return []

    symbols: list[CodeSymbol] = []
    file_stem = file_path.rsplit("/", 1)[-1].rsplit(".", 1)[0]

    def walk(node, parent_name: str = ""):
        rule = rule_map.get(node.type)
        if rule:
            try:
                # For decorated_definition in Python, dig into the inner node
                target_node = node
                if node.type == "decorated_definition":
                    for child in node.children:
                        if child.type in ("function_definition", "class_definition"):
                            target_node = child
                            rule = rule_map.get(target_node.type, rule)
                            break

                name, qualified_name, signature = rule.extract(target_node, source_bytes, parent_name or file_stem)

                start_line = target_node.start_point[0] + 1
                end_line = target_node.end_point[0] + 1
                snippet = _node_lines(source_lines, target_node.start_point[0], target_node.end_point[0])
                # Cap snippet length to avoid huge blobs
                if len(snippet) > 2000:
                    snippet = snippet[:2000] + "\n... [truncated]"

                symbol = CodeSymbol(
                    symbol_id=_make_symbol_id(repo_id, file_path, rule.kind.value, qualified_name, start_line),
                    repo_id=repo_id,
                    snapshot_id=snapshot_id,
                    file_path=file_path,
                    language=language,
                    kind=rule.kind,
                    name=name,
                    qualified_name=qualified_name,
                    start_line=start_line,
                    end_line=end_line,
                    signature=signature,
                    snippet=snippet,
                )
                symbols.append(symbol)

                # Recurse with updated parent only for class / function bodies
                new_parent = qualified_name if rule.kind in (SymbolKind.CLASS, SymbolKind.FUNCTION, SymbolKind.METHOD) else parent_name
                for child in target_node.children:
                    walk(child, new_parent)
                return  # already walked children above
            except Exception as exc:
                logger.debug("Extraction error node=%s file=%s: %s", node.type, file_path, exc)

        for child in node.children:
            walk(child, parent_name)

    walk(tree.root_node)
    return symbols


# ---------------------------------------------------------------------------
# Regex-based fallback extractor (Used when tree-sitter is unavailable)
# ---------------------------------------------------------------------------

_LANG_PATTERNS: dict[SupportedLanguage, list[tuple[re.Pattern, SymbolKind, int]]] = {
    SupportedLanguage.PYTHON: [
        (re.compile(r"^(\s*)def\s+([A-Za-z_]\w*)\s*\(([^)]*)\)", re.M), SymbolKind.FUNCTION, 2),
        (re.compile(r"^(\s*)class\s+([A-Za-z_]\w*)", re.M), SymbolKind.CLASS, 2),
        (re.compile(r"^import\s+(\S+)", re.M), SymbolKind.IMPORT, 1),
        (re.compile(r"^from\s+(\S+)\s+import", re.M), SymbolKind.IMPORT, 1),
        (re.compile(r"^([A-Z_][A-Z0-9_]{2,})\s*=", re.M), SymbolKind.CONSTANT, 1),
        (re.compile(r"^([a-z_][a-z0-9_]*)\s*=", re.M), SymbolKind.VARIABLE, 1),
    ],
    SupportedLanguage.JAVASCRIPT: [
        (re.compile(r"^\s*(?:export\s+)?(?:async\s+)?function\s+([A-Za-z_$]\w*)\s*\([^)]*\)", re.M), SymbolKind.FUNCTION, 1),
        (re.compile(r"^\s*(?:export\s+)?class\s+([A-Za-z_$]\w*)", re.M), SymbolKind.CLASS, 1),
        (re.compile(r"^\s*(?:export\s+)?(?:const|let|var)\s+([A-Za-z_$]\w*)\s*=\s*(?:async\s*)?\([^)]*\)\s*=>", re.M), SymbolKind.FUNCTION, 1),
        (re.compile(r"^\s*(?:export\s+)?(?:const|let|var)\s+([A-Za-z_$]\w*)\s*=", re.M), SymbolKind.VARIABLE, 1),
        (re.compile(r"^\s*import\s+.*?from\s+['\"]([^'\"]+)['\"]", re.M), SymbolKind.IMPORT, 1),
        (re.compile(r"^\s*import\s+['\"]([^'\"]+)['\"]", re.M), SymbolKind.IMPORT, 1),
        (re.compile(r"^\s*export\s+(?:default\s+)?(?:const|let|var|function|class)?\s*([A-Za-z_$]\w*)?", re.M), SymbolKind.EXPORT, 1),
    ],
    SupportedLanguage.TYPESCRIPT: [
        (re.compile(r"^\s*(?:export\s+)?(?:async\s+)?function\s+([A-Za-z_$]\w*)\s*(?:<[^>]*>)?\s*\([^)]*\)", re.M), SymbolKind.FUNCTION, 1),
        (re.compile(r"^\s*(?:export\s+)?class\s+([A-Za-z_$]\w*)", re.M), SymbolKind.CLASS, 1),
        (re.compile(r"^\s*(?:export\s+)?interface\s+([A-Za-z_$]\w*)", re.M), SymbolKind.INTERFACE, 1),
        (re.compile(r"^\s*(?:export\s+)?type\s+([A-Za-z_$]\w*)\s*=", re.M), SymbolKind.TYPE_ALIAS, 1),
        (re.compile(r"^\s*(?:export\s+)?enum\s+([A-Za-z_$]\w*)", re.M), SymbolKind.ENUM, 1),
        (re.compile(r"^\s*(?:export\s+)?(?:const|let|var)\s+([A-Za-z_$]\w*)\s*=\s*(?:async\s*)?\([^)]*\)\s*=>", re.M), SymbolKind.FUNCTION, 1),
        (re.compile(r"^\s*(?:export\s+)?(?:const|let|var)\s+([A-Za-z_$]\w*)", re.M), SymbolKind.VARIABLE, 1),
        (re.compile(r"^\s*import\s+.*?from\s+['\"]([^'\"]+)['\"]", re.M), SymbolKind.IMPORT, 1),
        (re.compile(r"^\s*import\s+['\"]([^'\"]+)['\"]", re.M), SymbolKind.IMPORT, 1),
        (re.compile(r"^\s*export\s+(?:default\s+)?(?:const|let|var|function|class|interface|type)?\s*([A-Za-z_$]\w*)?", re.M), SymbolKind.EXPORT, 1),
    ],
    SupportedLanguage.JAVA: [
        (re.compile(r"^\s*(?:public|protected|private|static|final|\s)*class\s+([A-Za-z_]\w*)", re.M), SymbolKind.CLASS, 1),
        (re.compile(r"^\s*(?:public|protected|private|static|final|\s)*interface\s+([A-Za-z_]\w*)", re.M), SymbolKind.INTERFACE, 1),
        (re.compile(r"^\s*(?:public|protected|private|static|final|\s)*enum\s+([A-Za-z_]\w*)", re.M), SymbolKind.ENUM, 1),
        (re.compile(r"^\s*(?:public|protected|private|static|final|\s)+[\w<>\[\],]+\s+([A-Za-z_]\w*)\s*\([^)]*\)\s*(?:throws\s+[\w,\s]+)?\s*\{?", re.M), SymbolKind.METHOD, 1),
        (re.compile(r"^\s*import\s+(?:static\s+)?([^\s;]+)", re.M), SymbolKind.IMPORT, 1),
    ],
    SupportedLanguage.GO: [
        (re.compile(r"^func\s+([A-Za-z_]\w*)\s*\([^)]*\)", re.M), SymbolKind.FUNCTION, 1),
        (re.compile(r"^func\s*\([^)]+\)\s*([A-Za-z_]\w*)\s*\([^)]*\)", re.M), SymbolKind.METHOD, 1),
        (re.compile(r"^type\s+([A-Za-z_]\w*)\s+struct", re.M), SymbolKind.CLASS, 1),
        (re.compile(r"^type\s+([A-Za-z_]\w*)\s+interface", re.M), SymbolKind.INTERFACE, 1),
        (re.compile(r"^import\s+\(?\s*\"([^\"]+)\"", re.M), SymbolKind.IMPORT, 1),
        (re.compile(r"^(?:var|const)\s+([A-Za-z_]\w*)", re.M), SymbolKind.VARIABLE, 1),
    ],
}


def _extract_regex_fallback(
    source: str,
    source_lines: list[str],
    language: SupportedLanguage,
    file_path: str,
    repo_id: str,
    snapshot_id: str,
) -> list[CodeSymbol]:
    """Regex-based extractor used when tree-sitter is unavailable or returns empty."""
    patterns = _LANG_PATTERNS.get(language, [])
    if not patterns:
        return []

    symbols: list[CodeSymbol] = []
    file_stem = file_path.rsplit("/", 1)[-1].rsplit(".", 1)[0]
    seen_keys: set[tuple[str, str, int]] = set()

    for pattern, kind, name_group in patterns:
        for match in pattern.finditer(source):
            line_no = source.count("\n", 0, match.start()) + 1
            name = None
            if name_group <= len(match.groups()) and match.group(name_group):
                name = match.group(name_group).strip()
            if not name:
                name = match.group(0).strip().split()[0] if match.group(0).strip() else "unknown"

            dedup_key = (kind.value, name, line_no)
            if dedup_key in seen_keys:
                continue
            seen_keys.add(dedup_key)

            qualified_name = f"{file_stem}.{name}" if kind not in (SymbolKind.IMPORT, SymbolKind.EXPORT) else name
            snippet_lines = source_lines[line_no - 1 : min(line_no + 4, len(source_lines))]
            snippet = "\n".join(snippet_lines)
            end_line = min(line_no + max(0, len(snippet_lines) - 1), len(source_lines))

            symbols.append(CodeSymbol(
                symbol_id=_make_symbol_id(repo_id, file_path, kind.value, qualified_name, line_no),
                repo_id=repo_id,
                snapshot_id=snapshot_id,
                file_path=file_path,
                language=language,
                kind=kind,
                name=name,
                qualified_name=qualified_name,
                start_line=line_no,
                end_line=end_line,
                signature=match.group(0).strip(),
                snippet=snippet,
            ))

    symbols.sort(key=lambda s: (s.start_line, s.name))
    return symbols


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def extract_symbols(
    source: str,
    file_path: str,
    repo_id: str,
    snapshot_id: str,
) -> tuple[list[CodeSymbol], list[str]]:
    """
    Extract code symbols from *source* text at *file_path*.

    Returns:
        (symbols, warnings) — warnings is a list of human-readable notes about
        parse errors or unsupported features; never raises.
    """
    warnings: list[str] = []

    if not source or not source.strip():
        return [], []

    language = detect_language(file_path)
    if language == SupportedLanguage.UNKNOWN:
        warnings.append(f"Unsupported file type: {file_path}")
        return [], warnings

    source_lines = source.splitlines()
    source_bytes = source.encode("utf-8", errors="replace")

    symbols = _extract_with_tree_sitter(source_bytes, source_lines, language, file_path, repo_id, snapshot_id)

    if not symbols:
        # Fallback to regex for Python
        symbols = _extract_regex_fallback(source, source_lines, language, file_path, repo_id, snapshot_id)
        if symbols:
            warnings.append(f"Used regex fallback for {file_path} (tree-sitter unavailable or empty result)")

    return symbols, warnings


def index_repository(
    repo_id: str,
    snapshot_id: str,
    files: dict[str, str],  # path -> source text
) -> RepoIndex:
    """
    Build a RepoIndex from a dict of {path: source_text} pairs.

    This is the entry point other AIservices features will call.
    *files* is whatever the caller supplies — no GitHub auth here.
    """
    all_symbols: list[CodeSymbol] = []
    all_warnings: list[str] = []

    for file_path, source in files.items():
        if not is_supported(file_path):
            all_warnings.append(f"Skipped unsupported file: {file_path}")
            continue
        syms, warns = extract_symbols(source, file_path, repo_id, snapshot_id)
        all_symbols.extend(syms)
        all_warnings.extend(warns)

    return RepoIndex(
        repo_id=repo_id,
        snapshot_id=snapshot_id,
        symbols=all_symbols,
        files=files,
        warnings=all_warnings,
    )
