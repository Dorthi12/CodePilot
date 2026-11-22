import pytest
from pathlib import Path
import tempfile
import os

from src.services.parser_service import parser_service, ASTParserService


def test_detect_language():
    assert parser_service.detect_language("main.py") == "python"
    assert parser_service.detect_language("app/index.js") == "javascript"
    assert parser_service.detect_language("src/types.ts") == "typescript"
    assert parser_service.detect_language("components/Button.tsx") == "tsx"
    assert parser_service.detect_language("package.json") == "json"
    assert parser_service.detect_language("README.md") == "markdown"
    assert parser_service.detect_language("unknown.xyz123") is None


def test_parse_python_file(tmp_path: Path):
    py_file = tmp_path / "service.py"
    py_file.write_text(
        '"""Module docstring."""\n'
        'import os\n'
        'from datetime import datetime as dt, timezone\n'
        '\n'
        'class AuthService:\n'
        '    """Handles user authentication."""\n'
        '    def __init__(self, secret: str):\n'
        '        self.secret = secret\n'
        '\n'
        '    def login(self, username: str) -> bool:\n'
        '        """Perform login."""\n'
        '        return True\n'
        '\n'
        'def hash_password(raw: str) -> str:\n'
        '    """Hash a password."""\n'
        '    return "hashed"\n',
        encoding="utf-8"
    )

    parsed = parser_service.parse_file("service.py", py_file)
    assert parsed is not None
    assert parsed.language == "python"
    assert parsed.line_count in {16, 17}
    assert not parsed.is_binary

    # Symbols check
    symbol_names = [s.name for s in parsed.symbols]
    assert "AuthService" in symbol_names
    assert "__init__" in symbol_names
    assert "login" in symbol_names
    assert "hash_password" in symbol_names

    # Check method qualified name & scope
    login_sym = next(s for s in parsed.symbols if s.name == "login")
    assert login_sym.qualified_name == "AuthService.login"
    assert login_sym.kind == "METHOD"
    assert login_sym.scope == "AuthService"
    assert login_sym.docstring == "Perform login."

    # Check imports
    import_mods = [imp.source_module for imp in parsed.imports]
    assert "os" in import_mods
    assert "datetime" in import_mods

    # Check chunks
    assert len(parsed.chunks) > 0
    class_chunk = next((c for c in parsed.chunks if c.chunk_type == "CLASS"), None)
    assert class_chunk is not None
    assert "class AuthService" in class_chunk.content

    # Check default parsing does not generate summary
    assert parsed.summary is None

    # Check explicit summary generation
    parsed_with_summary = parser_service.parse_file("auth.py", py_file, generate_summary=True)
    assert parsed_with_summary is not None
    assert "Python" in parsed_with_summary.summary
    assert "AuthService" in parsed_with_summary.summary


def test_parse_javascript_file(tmp_path: Path):
    js_file = tmp_path / "util.js"
    js_file.write_text(
        'import axios from "axios";\n'
        'const fs = require("fs");\n'
        '\n'
        'export class FileHelper {\n'
        '    readFile(path) {\n'
        '        return fs.readFileSync(path);\n'
        '    }\n'
        '}\n'
        '\n'
        'export function calculateSum(a, b) {\n'
        '    return a + b;\n'
        '}\n'
        '\n'
        'export const multiply = (x, y) => x * y;\n',
        encoding="utf-8"
    )

    parsed = parser_service.parse_file("util.js", js_file)
    assert parsed is not None
    assert parsed.language == "javascript"

    symbol_names = [s.name for s in parsed.symbols]
    assert "FileHelper" in symbol_names
    assert "readFile" in symbol_names
    assert "calculateSum" in symbol_names
    assert "multiply" in symbol_names

    # Imports check
    import_sources = [imp.source_module for imp in parsed.imports]
    assert "axios" in import_sources
    assert "fs" in import_sources


def test_parse_typescript_file(tmp_path: Path):
    ts_file = tmp_path / "model.ts"
    ts_file.write_text(
        'import { User } from "./user";\n'
        '\n'
        'export interface RepositoryConfig {\n'
        '    id: string;\n'
        '    name: string;\n'
        '}\n'
        '\n'
        'export function createConfig(id: string, name: string): RepositoryConfig {\n'
        '    return { id, name };\n'
        '}\n',
        encoding="utf-8"
    )

    parsed = parser_service.parse_file("model.ts", ts_file)
    assert parsed is not None
    assert parsed.language == "typescript"

    symbol_kinds = {s.name: s.kind for s in parsed.symbols}
    assert symbol_kinds.get("RepositoryConfig") == "INTERFACE"
    assert symbol_kinds.get("createConfig") == "FUNCTION"


def test_parse_binary_file(tmp_path: Path):
    bin_file = tmp_path / "icon.png"
    bin_file.write_bytes(b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00")

    parsed = parser_service.parse_file("icon.png", bin_file)
    assert parsed is not None
    assert parsed.is_binary
    assert parsed.summary is None
    assert len(parsed.symbols) == 0


def test_malformed_syntax_recovery(tmp_path: Path):
    broken_file = tmp_path / "broken.py"
    broken_file.write_text(
        'def valid_function():\n'
        '    return 42\n'
        '\n'
        'try:\n'
        '    print(\n'
        'except Exception:\n'
        '    pass\n'
        '\n'
        'def another_valid_function():\n'
        '    return 99\n',
        encoding="utf-8"
    )

    parsed = parser_service.parse_file("broken.py", broken_file)
    assert parsed is not None
    # Tree-sitter recovers and extracts the valid functions despite the syntax error
    names = [s.name for s in parsed.symbols]
    assert "valid_function" in names
    assert "another_valid_function" in names
