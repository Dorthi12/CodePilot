import pytest
import uuid
from pathlib import Path
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from unittest.mock import patch

from src.config import settings
from src.models.user import User
from src.models.repository import Repository
from src.models.snapshot import Snapshot
from src.models.repo_file import RepoFile
from src.models.symbol import Symbol
from src.models.import_statement import FileImport
from src.models.code_chunk import CodeChunk
from src.services.ingestion_service import IngestionService


@pytest.fixture
def workspace_with_code(tmp_path: Path):
    """Sets up a mock repository workspace directory with Python and TypeScript source files."""
    repo_dir = tmp_path / "mock_repo"
    repo_dir.mkdir(parents=True, exist_ok=True)

    # 1. Python source file
    src_dir = repo_dir / "src"
    src_dir.mkdir(parents=True, exist_ok=True)

    calc_file = src_dir / "calculator.py"
    calc_file.write_text(
        '"""Calculator module."""\n'
        'import math\n'
        'from os import path as ospath\n'
        '\n'
        'class Calculator:\n'
        '    """Performs arithmetic calculations."""\n'
        '    def __init__(self, precision: int = 2):\n'
        '        self.precision = precision\n'
        '\n'
        '    def add(self, a: float, b: float) -> float:\n'
        '        """Add two numbers."""\n'
        '        return a + b\n'
        '\n'
        'def compute_square_root(x: float) -> float:\n'
        '    """Compute square root safely."""\n'
        '    return math.sqrt(x)\n',
        encoding="utf-8"
    )

    # 2. TypeScript source file
    models_dir = repo_dir / "src" / "models"
    models_dir.mkdir(parents=True, exist_ok=True)

    types_file = models_dir / "types.ts"
    types_file.write_text(
        'import { Config } from "./config";\n'
        '\n'
        'export interface UserProfile {\n'
        '    id: string;\n'
        '    username: string;\n'
        '}\n'
        '\n'
        'export function formatUser(user: UserProfile): string {\n'
        '    return user.username.toUpperCase();\n'
        '}\n',
        encoding="utf-8"
    )

    # 3. JSON config file
    config_file = repo_dir / "package.json"
    config_file.write_text('{"name": "test-repo", "version": "1.0.0"}\n', encoding="utf-8")

    return repo_dir


@pytest.mark.asyncio
async def test_full_ingestion_and_snapshot_creation(
    test_db: AsyncSession,
    sample_user: User,
    workspace_with_code: Path
):
    """Verifies that IngestionService correctly creates snapshots, files, symbols, imports, and chunks."""
    # Create test repository
    repo = Repository(
        id=uuid.uuid4(),
        owner_user_id=sample_user.id,
        provider="github",
        provider_repo_id="998877",
        owner=sample_user.username,
        name="test-repo",
        canonical_url="https://github.com/athena_dev/test-repo",
        default_branch="main",
        tracked_branch="main",
        status="ACTIVE",
        analysis_status="NOT_ANALYZED"
    )
    test_db.add(repo)
    await test_db.commit()
    await test_db.refresh(repo)

    ingestion_svc = IngestionService(test_db)

    # Patch workspace path to use our temporary workspace
    with patch("src.services.ingestion_service.get_repository_workspace_path", return_value=workspace_with_code):
        snapshot = await ingestion_svc.ingest_repository(
            repository_id=repo.id,
            user_id=sample_user.id,
            branch="main",
            commit_sha="commit-abc-123"
        )

    assert snapshot.status == "READY"
    assert snapshot.total_files == 3  # calculator.py, types.ts, package.json
    assert snapshot.total_lines > 0
    assert "python" in snapshot.metadata_json["languages"]
    assert "typescript" in snapshot.metadata_json["languages"]

    # Verify database entities created
    from sqlalchemy import select
    files = (await test_db.execute(select(RepoFile).where(RepoFile.snapshot_id == snapshot.id))).scalars().all()
    assert len(files) == 3

    calc_file = next(f for f in files if f.filename == "calculator.py")
    assert calc_file.language == "python"
    assert calc_file.summary is None  # Summaries are NOT generated during ingestion

    # Verify Symbols
    symbols = (await test_db.execute(select(Symbol).where(Symbol.file_id == calc_file.id))).scalars().all()
    sym_names = [s.name for s in symbols]
    assert "Calculator" in sym_names
    assert "add" in sym_names
    assert "compute_square_root" in sym_names

    add_sym = next(s for s in symbols if s.name == "add")
    assert add_sym.qualified_name == "Calculator.add"
    assert add_sym.kind == "METHOD"
    assert add_sym.docstring == "Add two numbers."

    # Verify Imports
    imports = (await test_db.execute(select(FileImport).where(FileImport.file_id == calc_file.id))).scalars().all()
    imp_mods = [i.source_module for i in imports]
    assert "math" in imp_mods
    assert "os" in imp_mods

    # Verify CodeChunks
    chunks = (await test_db.execute(select(CodeChunk).where(CodeChunk.file_id == calc_file.id))).scalars().all()
    assert len(chunks) > 0
    assert any(c.chunk_type == "CLASS" for c in chunks)


@pytest.mark.asyncio
async def test_idempotent_reanalysis(
    test_db: AsyncSession,
    sample_user: User,
    workspace_with_code: Path
):
    """Verifies that re-running analysis on the same commit does not duplicate files or symbols."""
    repo = Repository(
        id=uuid.uuid4(),
        owner_user_id=sample_user.id,
        provider="github",
        provider_repo_id="998878",
        owner=sample_user.username,
        name="idempotent-repo",
        canonical_url="https://github.com/athena_dev/idempotent-repo",
        status="ACTIVE"
    )
    test_db.add(repo)
    await test_db.commit()

    ingestion_svc = IngestionService(test_db)

    with patch("src.services.ingestion_service.get_repository_workspace_path", return_value=workspace_with_code):
        # First ingestion
        snap1 = await ingestion_svc.ingest_repository(repo.id, sample_user.id, commit_sha="commit-fixed-sha")
        # Second ingestion on the same commit
        snap2 = await ingestion_svc.ingest_repository(repo.id, sample_user.id, commit_sha="commit-fixed-sha")

    from sqlalchemy import select, func
    file_count = await test_db.scalar(select(func.count(RepoFile.id)).where(RepoFile.snapshot_id == snap2.id))
    assert file_count == 3  # Exactly 3 files, no duplicates!


@pytest.mark.asyncio
async def test_codebase_explorer_endpoints(
    client: AsyncClient,
    test_db: AsyncSession,
    sample_user: User,
    authenticated_session,
    workspace_with_code: Path
):
    """Verifies /tree, /file, and /symbols endpoints for Codebase Explorer."""
    session_id = authenticated_session["session_id"]
    csrf_token = authenticated_session["csrf_token"]
    client.cookies.set(settings.SESSION_COOKIE_NAME, session_id)
    client.cookies.set(settings.CSRF_COOKIE_NAME, csrf_token)
    headers = {"X-CSRF-Token": csrf_token, "Origin": settings.FRONTEND_BASE_URL}

    # Create repository owned by authenticated user
    repo = Repository(
        id=uuid.uuid4(),
        owner_user_id=authenticated_session["user"].id,
        provider="github",
        provider_repo_id="776655",
        owner=authenticated_session["user"].username,
        name="explorer-repo",
        canonical_url="https://github.com/athena_dev/explorer-repo",
        status="ACTIVE"
    )
    test_db.add(repo)
    await test_db.commit()

    # Ingest the workspace
    ingestion_svc = IngestionService(test_db)
    with patch("src.services.ingestion_service.get_repository_workspace_path", return_value=workspace_with_code):
        await ingestion_svc.ingest_repository(repo.id, authenticated_session["user"].id, commit_sha="commit-explorer")

    # 1. Test Root Tree Navigation
    root_tree_resp = await client.get(f"/api/v1/repositories/{repo.id}/tree", headers=headers)
    assert root_tree_resp.status_code == 200
    root_data = root_tree_resp.json()["data"]
    entries = root_data["entries"]
    entry_names = [e["name"] for e in entries]

    # Should contain "src" directory and "package.json" file
    assert "src" in entry_names
    assert "package.json" in entry_names

    src_entry = next(e for e in entries if e["name"] == "src")
    assert src_entry["type"] == "directory"

    # 2. Test Subdirectory Tree Navigation (/src)
    src_tree_resp = await client.get(f"/api/v1/repositories/{repo.id}/tree?path=src", headers=headers)
    assert src_tree_resp.status_code == 200
    src_data = src_tree_resp.json()["data"]
    src_entry_names = [e["name"] for e in src_data["entries"]]
    assert "calculator.py" in src_entry_names
    assert "models" in src_entry_names

    # 3. Test File Inspection (/file?path=src/calculator.py)
    # Selecting a file does NOT automatically trigger summary generation
    with patch("src.services.ingestion_service.get_repository_workspace_path", return_value=workspace_with_code):
        file_resp = await client.get(f"/api/v1/repositories/{repo.id}/file?path=src/calculator.py", headers=headers)
    assert file_resp.status_code == 200
    file_data = file_resp.json()["data"]
    assert file_data["filename"] == "calculator.py"
    assert file_data["language"] == "python"
    assert file_data["summary"] is None  # Not generated on selection
    assert file_data["content"] is not None
    assert "class Calculator:" in file_data["content"]
    assert len(file_data["symbols"]) >= 3
    assert len(file_data["imports"]) >= 2
    assert len(file_data["chunks"]) >= 1

    # 4. Test File Inspection by ID (/files/{file_id})
    file_id = file_data["id"]
    with patch("src.services.ingestion_service.get_repository_workspace_path", return_value=workspace_with_code):
        file_id_resp = await client.get(f"/api/v1/repositories/{repo.id}/files/{file_id}", headers=headers)
    assert file_id_resp.status_code == 200
    assert file_id_resp.json()["data"]["id"] == file_id
    assert file_id_resp.json()["data"]["summary"] is None

    # 5. On-Demand Summary Generation: Generate summary for calculator.py
    with patch("src.services.summary_service.get_repository_workspace_path", return_value=workspace_with_code):
        gen_resp = await client.post(f"/api/v1/repositories/{repo.id}/files/{file_id}/summary", headers=headers)
    assert gen_resp.status_code == 200
    gen_data = gen_resp.json()["data"]
    assert gen_data["file_id"] == file_id
    assert gen_data["cached"] is False
    assert "Purpose" in gen_data["summary"]
    assert "Calculator" in gen_data["summary"]

    # Verify that ONLY this file got summarized, other files remain without summary
    with patch("src.services.ingestion_service.get_repository_workspace_path", return_value=workspace_with_code):
        other_file_resp = await client.get(f"/api/v1/repositories/{repo.id}/file?path=src/models/types.ts", headers=headers)
    assert other_file_resp.status_code == 200
    assert other_file_resp.json()["data"]["summary"] is None

    # 6. Reusing Cached Summary: Calling again without code change returns cached=True
    with patch("src.services.summary_service.get_repository_workspace_path", return_value=workspace_with_code):
        cached_resp = await client.post(f"/api/v1/repositories/{repo.id}/files/{file_id}/summary", headers=headers)
    assert cached_resp.status_code == 200
    assert cached_resp.json()["data"]["cached"] is True
    assert cached_resp.json()["data"]["summary"] == gen_data["summary"]

    # 7. Force Regeneration: Calling with force=True regenerates even if hash matches
    with patch("src.services.summary_service.get_repository_workspace_path", return_value=workspace_with_code):
        force_resp = await client.post(f"/api/v1/repositories/{repo.id}/files/{file_id}/summary?force=true", headers=headers)
    assert force_resp.status_code == 200
    assert force_resp.json()["data"]["cached"] is False

    # 8. Content Hash Change: Modifying file on disk causes summary regeneration
    calc_path = workspace_with_code / "src" / "calculator.py"
    calc_path.write_text("class AdvancedCalculator:\n    def multiply(self, a, b):\n        return a * b\n", encoding="utf-8")
    with patch("src.services.summary_service.get_repository_workspace_path", return_value=workspace_with_code):
        changed_resp = await client.post(f"/api/v1/repositories/{repo.id}/files/{file_id}/summary", headers=headers)
    assert changed_resp.status_code == 200
    assert changed_resp.json()["data"]["cached"] is False
    assert "multiply" in changed_resp.json()["data"]["summary"] or "AdvancedCalculator" in changed_resp.json()["data"]["summary"]

    # 9. Test Symbol Search (/symbols)
    sym_resp = await client.get(f"/api/v1/repositories/{repo.id}/symbols?q=calc", headers=headers)
    assert sym_resp.status_code == 200
    sym_list = sym_resp.json()["data"]
    assert len(sym_list) > 0
    assert any(s["name"] in ("Calculator", "AdvancedCalculator") for s in sym_list)

    # 10. Multi-tenant Isolation: other user cannot access explorer
    other_user = User(
        id=uuid.uuid4(),
        github_id="99999999",
        username="unauthorized_user"
    )
    test_db.add(other_user)
    await test_db.commit()

    other_ingestion = IngestionService(test_db)
    from src.services.ingestion_service import IngestionError
    with pytest.raises(IngestionError) as exc_info:
        await other_ingestion.get_file_tree(repo.id, other_user.id)
    assert exc_info.value.code == "NOT_FOUND"
