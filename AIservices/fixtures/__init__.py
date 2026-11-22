"""
Sample repository code files used for indexing and search testing.
"""

from pathlib import Path

FIXTURES_DIR = Path(__file__).parent / "sample_repo"

def load_sample_files() -> dict[str, str]:
    files = {}
    if FIXTURES_DIR.exists():
        for f in FIXTURES_DIR.glob("**/*"):
            if f.is_file():
                rel_path = f.relative_to(FIXTURES_DIR).as_posix()
                files[rel_path] = f.read_text(encoding="utf-8")
    return files
