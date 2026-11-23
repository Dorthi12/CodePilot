"""
Language detection utilities.
Maps file extensions → SupportedLanguage enum values.
"""

from pathlib import PurePosixPath
from AIservices.core.models import SupportedLanguage

_EXT_MAP: dict[str, SupportedLanguage] = {
    ".py": SupportedLanguage.PYTHON,
    ".js": SupportedLanguage.JAVASCRIPT,
    ".mjs": SupportedLanguage.JAVASCRIPT,
    ".cjs": SupportedLanguage.JAVASCRIPT,
    ".ts": SupportedLanguage.TYPESCRIPT,
    ".tsx": SupportedLanguage.TYPESCRIPT,
    ".java": SupportedLanguage.JAVA,
    ".go": SupportedLanguage.GO,
}


def detect_language(file_path: str) -> SupportedLanguage:
    """Return the language for *file_path* based on its extension."""
    ext = PurePosixPath(file_path).suffix.lower()
    return _EXT_MAP.get(ext, SupportedLanguage.UNKNOWN)


def is_supported(file_path: str) -> bool:
    """Return True when the file can be parsed by one of our extractors."""
    return detect_language(file_path) != SupportedLanguage.UNKNOWN
