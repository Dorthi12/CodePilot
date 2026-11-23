"""
Analysis and Summary Generation Engine for CodePilot AIservices.
Extracts project overview, technologies, key modules, architecture,
and structural codebase metrics from parsed AST symbols and repository files.
"""

from __future__ import annotations

import os
from collections import Counter
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from AIservices.core.models import RepoIndex, SymbolKind


class TechnologyInfo(BaseModel):
    name: str
    category: str
    confidence: str = "detected"


class ModuleInfo(BaseModel):
    name: str
    path: str
    file_count: int
    symbol_count: int
    description: str


class ComponentInfo(BaseModel):
    name: str
    kind: str
    file_path: str
    start_line: int
    end_line: int
    signature: Optional[str] = None


class ProjectSummary(BaseModel):
    repo_id: str
    snapshot_id: str
    project_overview: str
    project_purpose: str
    technologies: List[TechnologyInfo]
    modules: List[ModuleInfo]
    components: List[ComponentInfo]
    architecture_overview: str
    file_count: int
    symbol_count: int
    languages: Dict[str, int]
    breakdown_by_kind: Dict[str, int]


def _detect_technologies(files: Dict[str, str], symbols: List[Any]) -> List[TechnologyInfo]:
    """Detect frameworks and libraries based on files and import symbols."""
    techs: Dict[str, TechnologyInfo] = {}

    file_paths = set(files.keys())
    all_imports = [s.name.lower() for s in symbols if s.kind == SymbolKind.IMPORT]
    combined_source_lower = " ".join([c[:500].lower() for c in list(files.values())[:30]])

    # Framework detection rules
    if any(p.endswith(('.tsx', '.jsx')) for p in file_paths) or any('react' in imp for imp in all_imports):
        techs["React"] = TechnologyInfo(name="React", category="Frontend Framework")
    if any('fastapi' in imp for imp in all_imports) or 'fastapi' in combined_source_lower:
        techs["FastAPI"] = TechnologyInfo(name="FastAPI", category="Backend Web Framework")
    if any('flask' in imp for imp in all_imports):
        techs["Flask"] = TechnologyInfo(name="Flask", category="Backend Web Framework")
    if any('django' in imp for imp in all_imports):
        techs["Django"] = TechnologyInfo(name="Django", category="Backend Web Framework")
    if any('express' in imp for imp in all_imports):
        techs["Express.js"] = TechnologyInfo(name="Express.js", category="Backend Web Framework")
    if any('vue' in imp for imp in all_imports) or any(p.endswith('.vue') for p in file_paths):
        techs["Vue.js"] = TechnologyInfo(name="Vue.js", category="Frontend Framework")
    if any('next' in imp for imp in all_imports) or any('next.config' in p for p in file_paths):
        techs["Next.js"] = TechnologyInfo(name="Next.js", category="Fullstack Framework")
    if any(p.endswith(('.ts', '.tsx')) for p in file_paths):
        techs["TypeScript"] = TechnologyInfo(name="TypeScript", category="Programming Language")
    if any(p.endswith('.py') for p in file_paths):
        techs["Python"] = TechnologyInfo(name="Python", category="Programming Language")
    if any(p.endswith('.go') for p in file_paths):
        techs["Go"] = TechnologyInfo(name="Go", category="Programming Language")
    if any(p.endswith('.java') for p in file_paths):
        techs["Java"] = TechnologyInfo(name="Java", category="Programming Language")
    if any(p.endswith(('.js', '.jsx', '.mjs')) for p in file_paths):
        techs["JavaScript"] = TechnologyInfo(name="JavaScript", category="Programming Language")
    if any('tailwind' in p.lower() for p in file_paths) or 'tailwind' in combined_source_lower:
        techs["Tailwind CSS"] = TechnologyInfo(name="Tailwind CSS", category="Styling Framework")
    if any('sqlalchemy' in imp for imp in all_imports) or 'sqlalchemy' in combined_source_lower:
        techs["SQLAlchemy"] = TechnologyInfo(name="SQLAlchemy", category="Database ORM")
    if any('redis' in imp for imp in all_imports):
        techs["Redis"] = TechnologyInfo(name="Redis", category="Caching & Key-Value Store")
    if any('pytest' in imp for imp in all_imports) or any('test' in p.lower() for p in file_paths):
        techs["Pytest / Unit Testing"] = TechnologyInfo(name="Pytest / Test Suite", category="Testing")

    return list(techs.values())


def _extract_modules(files: Dict[str, str], symbols: List[Any]) -> List[ModuleInfo]:
    """Group files by top-level or second-level directory to identify architectural modules."""
    module_files: Dict[str, List[str]] = {}
    for p in files.keys():
        parts = p.strip("/").split("/")
        mod_name = parts[0] if len(parts) > 1 else "root"
        if len(parts) > 2 and parts[0] in ("src", "app", "apps", "pkg", "internal", "lib"):
            mod_name = f"{parts[0]}/{parts[1]}"
        module_files.setdefault(mod_name, []).append(p)

    symbols_by_path: Dict[str, int] = Counter([s.file_path for s in symbols])

    modules: List[ModuleInfo] = []
    for mod_name, f_list in sorted(module_files.items(), key=lambda x: len(x[1]), reverse=True):
        sym_count = sum(symbols_by_path.get(f, 0) for f in f_list)
        desc = f"Contains {len(f_list)} file(s) and {sym_count} indexed code symbol(s)."
        if "auth" in mod_name.lower():
            desc = "Handles authentication, tokens, permissions, and identity security."
        elif "api" in mod_name.lower() or "routes" in mod_name.lower():
            desc = "Defines REST / HTTP endpoints, request validation, and routing."
        elif "models" in mod_name.lower() or "schemas" in mod_name.lower():
            desc = "Domain data models, database entities, and validation schemas."
        elif "services" in mod_name.lower():
            desc = "Core application business logic and external service integrations."
        elif "components" in mod_name.lower() or "views" in mod_name.lower():
            desc = "UI components, interactive views, and frontend layout."

        modules.append(ModuleInfo(
            name=mod_name,
            path=mod_name,
            file_count=len(f_list),
            symbol_count=sym_count,
            description=desc,
        ))

    return modules[:10]


def _extract_major_components(symbols: List[Any]) -> List[ComponentInfo]:
    """Pick highest priority classes, interfaces, and primary functions."""
    major_kinds = {SymbolKind.CLASS, SymbolKind.INTERFACE, SymbolKind.FUNCTION}
    filtered = [s for s in symbols if s.kind in major_kinds]
    # Classes first, then functions with exported=True or top line count
    sorted_syms = sorted(
        filtered,
        key=lambda s: (0 if s.kind == SymbolKind.CLASS else 1 if s.kind == SymbolKind.INTERFACE else 2, -(s.end_line - s.start_line))
    )
    return [
        ComponentInfo(
            name=s.name,
            kind=s.kind.value if hasattr(s.kind, "value") else str(s.kind),
            file_path=s.file_path,
            start_line=s.start_line,
            end_line=s.end_line,
            signature=s.signature,
        )
        for s in sorted_syms[:15]
    ]


def generate_project_summary(index: RepoIndex) -> ProjectSummary:
    """
    Generate an authoritative, structured project summary from index symbols and files.
    """
    files = index.files or {}
    symbols = index.symbols or []

    # Language breakdown
    lang_counter: Dict[str, int] = Counter()
    for s in symbols:
        lang_str = s.language.value if hasattr(s.language, "value") else str(s.language)
        lang_counter[lang_str] += 1
    if not lang_counter and files:
        for f in files.keys():
            ext = os.path.splitext(f)[1].lower()
            lang_counter[ext or "other"] += 1

    # Kind breakdown
    kind_counter: Dict[str, int] = Counter()
    for s in symbols:
        k_str = s.kind.value if hasattr(s.kind, "value") else str(s.kind)
        kind_counter[k_str] += 1

    technologies = _detect_technologies(files, symbols)
    modules = _extract_modules(files, symbols)
    components = _extract_major_components(symbols)

    # Primary language
    primary_lang = lang_counter.most_common(1)[0][0] if lang_counter else "multi-language"

    # Purpose and overview synthesis
    overview = (
        f"This repository consists of {len(files)} source file(s) containing {len(symbols)} parsed code symbol(s). "
        f"The primary language is {primary_lang.capitalize()}, organized into {len(modules)} primary architectural module(s)."
    )

    purpose = (
        f"The codebase serves as a {primary_lang}-centric system with structured definitions for {kind_counter.get('CLASS', 0)} "
        f"class(es), {kind_counter.get('FUNCTION', 0) + kind_counter.get('METHOD', 0)} function(s)/method(s), and "
        f"{kind_counter.get('VARIABLE', 0)} key symbol(s)."
    )

    tech_names = ", ".join([t.name for t in technologies[:4]]) or primary_lang.capitalize()
    architecture = (
        f"Modular architecture built with {tech_names}. "
        f"Modules include {', '.join([m.name for m in modules[:4]])}, separating domain entities, "
        f"core execution logic, and interface definitions."
    )

    return ProjectSummary(
        repo_id=index.repo_id,
        snapshot_id=index.snapshot_id,
        project_overview=overview,
        project_purpose=purpose,
        technologies=technologies,
        modules=modules,
        components=components,
        architecture_overview=architecture,
        file_count=len(files),
        symbol_count=len(symbols),
        languages=dict(lang_counter),
        breakdown_by_kind=dict(kind_counter),
    )
