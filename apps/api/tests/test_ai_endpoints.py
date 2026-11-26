"""Integration tests for Phase 2 authenticated AI Code Intelligence endpoints."""

import uuid
from pathlib import Path
from unittest.mock import patch

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from AIservices.api.index_store import delete_index, list_indexes
from src.config import settings
from src.models.repository import Repository
from src.models.user import User
from src.services.ingestion_service import IngestionService


def _clear_ai_indexes() -> None:
    for item in list_indexes():
        delete_index(item["repo_id"], item["snapshot_id"])


@pytest.fixture(autouse=True)
def reset_ai_index_store():
    """Ensure in-memory AIservices index store is clean before and after each test."""
    _clear_ai_indexes()
    yield
    _clear_ai_indexes()


@pytest.fixture
def ai_workspace(tmp_path: Path) -> Path:
    """Create a realistic multi-file workspace for indexing, search, and explanation."""
    repo_dir = tmp_path / "ai_repo"
    src_dir = repo_dir / "src"
    utils_dir = src_dir / "utils"
    utils_dir.mkdir(parents=True, exist_ok=True)

    (utils_dir / "math_helpers.py").write_text(
        'def clamp_value(val: int, min_val: int, max_val: int) -> int:\n'
        '    """Clamp integer val within [min_val, max_val]."""\n'
        '    if val < min_val:\n'
        '        return min_val\n'
        '    if val > max_val:\n'
        '        return max_val\n'
        '    return val\n',
        encoding="utf-8",
    )

    (src_dir / "calculator.py").write_text(
        'from src.utils.math_helpers import clamp_value\n\n'
        'class RateLimiter:\n'
        '    """Simple token-bucket style rate limiter."""\n'
        '    def compute_quota(self, requested: int) -> int:\n'
        '        if requested <= 0:\n'
        '            return 0\n'
        '        return clamp_value(requested, 1, 100)\n',
        encoding="utf-8",
    )

    (src_dir / "user_model.ts").write_text(
        'export interface Account {\n'
        '    id: string;\n'
        '    active: boolean;\n'
        '}\n\n'
        'export function isAccountActive(account: Account): boolean {\n'
        '    return account.active;\n'
        '}\n',
        encoding="utf-8",
    )

    return repo_dir


async def _create_and_ingest_repo(
    test_db: AsyncSession,
    owner: User,
    workspace: Path,
    name: str = "ai-test-repo",
) -> Repository:
    repo = Repository(
        id=uuid.uuid4(),
        owner_user_id=owner.id,
        provider="github",
        provider_repo_id=str(uuid.uuid4())[:12],
        owner=owner.username,
        name=name,
        canonical_url=f"https://github.com/{owner.username}/{name}",
        status="ACTIVE",
    )
    test_db.add(repo)
    await test_db.commit()

    ingestion_svc = IngestionService(test_db)
    with patch("src.services.ingestion_service.get_repository_workspace_path", return_value=workspace):
        await ingestion_svc.ingest_repository(repo.id, owner.id, commit_sha="commit-ai-test-1")

    return repo


def _auth_headers(client: AsyncClient, authenticated_session: dict) -> dict[str, str]:
    session_id = authenticated_session["session_id"]
    csrf_token = authenticated_session["csrf_token"]
    client.cookies.set(settings.SESSION_COOKIE_NAME, session_id)
    client.cookies.set(settings.CSRF_COOKIE_NAME, csrf_token)
    return {"X-CSRF-Token": csrf_token, "Origin": settings.FRONTEND_BASE_URL}


@pytest.mark.asyncio
async def test_unauthenticated_requests_rejected(client: AsyncClient):
    """All three AI endpoints must reject unauthenticated requests with 401."""
    repo_id = uuid.uuid4()

    idx_resp = await client.post(f"/api/v1/repositories/{repo_id}/index", json={})
    assert idx_resp.status_code == 401

    search_resp = await client.post(
        f"/api/v1/repositories/{repo_id}/search",
        json={"query": "compute_quota"},
    )
    assert search_resp.status_code == 401

    explain_resp = await client.post(
        f"/api/v1/repositories/{repo_id}/explain",
        json={"code": "def foo(): return 1"},
    )
    assert explain_resp.status_code == 401


@pytest.mark.asyncio
async def test_authenticated_indexing_and_idempotency(
    client: AsyncClient,
    test_db: AsyncSession,
    authenticated_session: dict,
    ai_workspace: Path,
):
    """Indexing succeeds for owner and repeated calls on same snapshot are idempotent."""
    headers = _auth_headers(client, authenticated_session)
    repo = await _create_and_ingest_repo(test_db, authenticated_session["user"], ai_workspace)

    with patch("src.services.ai_service.get_repository_workspace_path", return_value=ai_workspace):
        first = await client.post(
            f"/api/v1/repositories/{repo.id}/index",
            json={},
            headers=headers,
        )
        assert first.status_code == 200
        first_data = first.json()["data"]
        assert first_data["repo_id"] == str(repo.id)
        assert first_data["file_count"] == 3
        assert first_data["symbol_count"] >= 4
        assert first_data["cached"] is False

        # Second call for the same snapshot must reuse cache idempotently
        second = await client.post(
            f"/api/v1/repositories/{repo.id}/index",
            json={"snapshot_id": first_data["snapshot_id"]},
            headers=headers,
        )
        assert second.status_code == 200
        second_data = second.json()["data"]
        assert second_data["snapshot_id"] == first_data["snapshot_id"]
        assert second_data["symbol_count"] == first_data["symbol_count"]
        assert second_data["cached"] is True


@pytest.mark.asyncio
async def test_repository_ownership_isolation(
    client: AsyncClient,
    test_db: AsyncSession,
    authenticated_session: dict,
    ai_workspace: Path,
):
    """Users cannot index, search, or explain repositories they do not own or have access to."""
    other_owner = User(
        id=uuid.uuid4(),
        github_id="999888777",
        username="other_owner",
        email="other_owner@example.com",
    )
    test_db.add(other_owner)
    await test_db.commit()

    other_repo = await _create_and_ingest_repo(test_db, other_owner, ai_workspace, name="private-other-repo")
    headers = _auth_headers(client, authenticated_session)

    with patch("src.services.ai_service.get_repository_workspace_path", return_value=ai_workspace):
        r1 = await client.post(f"/api/v1/repositories/{other_repo.id}/index", json={}, headers=headers)
        assert r1.status_code == 404

        r2 = await client.post(
            f"/api/v1/repositories/{other_repo.id}/search",
            json={"query": "RateLimiter"},
            headers=headers,
        )
        assert r2.status_code == 404

        r3 = await client.post(
            f"/api/v1/repositories/{other_repo.id}/explain",
            json={"file_path": "src/calculator.py"},
            headers=headers,
        )
        assert r3.status_code == 404


@pytest.mark.asyncio
async def test_search_modes_and_filters(
    client: AsyncClient,
    test_db: AsyncSession,
    authenticated_session: dict,
    ai_workspace: Path,
):
    """Search supports exact, symbol, fuzzy modes plus language, kind, and path_prefix filters."""
    headers = _auth_headers(client, authenticated_session)
    repo = await _create_and_ingest_repo(test_db, authenticated_session["user"], ai_workspace)

    with patch("src.services.ai_service.get_repository_workspace_path", return_value=ai_workspace):
        # 1. Exact match
        exact_resp = await client.post(
            f"/api/v1/repositories/{repo.id}/search",
            json={"query": "clamp_value"},
            headers=headers,
        )
        assert exact_resp.status_code == 200
        exact_data = exact_resp.json()["data"]
        assert exact_data["total"] >= 1
        assert exact_data["results"][0]["name"] == "clamp_value"
        assert exact_data["results"][0]["match_type"] == "exact"

        # 2. Symbol word-boundary / partial match
        symbol_resp = await client.post(
            f"/api/v1/repositories/{repo.id}/search",
            json={"query": "quota"},
            headers=headers,
        )
        assert symbol_resp.status_code == 200
        names = [item["name"] for item in symbol_resp.json()["data"]["results"]]
        assert "compute_quota" in names

        # 3. Fuzzy search
        fuzzy_resp = await client.post(
            f"/api/v1/repositories/{repo.id}/search",
            json={"query": "bucket rate"},
            headers=headers,
        )
        assert fuzzy_resp.status_code == 200
        assert fuzzy_resp.json()["data"]["total"] >= 1

        # 4. Language & Kind & Path Prefix filters
        filtered_resp = await client.post(
            f"/api/v1/repositories/{repo.id}/search",
            json={
                "query": "Account",
                "filters": {
                    "languages": ["typescript"],
                    "kinds": ["INTERFACE"],
                    "path_prefix": "src/",
                },
                "top_k": 5,
            },
            headers=headers,
        )
        assert filtered_resp.status_code == 200
        filtered_results = filtered_resp.json()["data"]["results"]
        assert len(filtered_results) >= 1
        assert all(item["language"] == "typescript" for item in filtered_results)
        assert all(item["kind"] == "INTERFACE" for item in filtered_results)


@pytest.mark.asyncio
async def test_explain_styles_citations_and_offline_fallback(
    client: AsyncClient,
    test_db: AsyncSession,
    authenticated_session: dict,
    ai_workspace: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    """Explain endpoint supports styles, cross-file citations, and offline StaticAnalysisProvider fallback."""
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    monkeypatch.setattr(settings, "GEMINI_API_KEY", None)

    headers = _auth_headers(client, authenticated_session)
    repo = await _create_and_ingest_repo(test_db, authenticated_session["user"], ai_workspace)

    with patch("src.services.ai_service.get_repository_workspace_path", return_value=ai_workspace):
        for style in ("beginner", "technical", "deep"):
            resp = await client.post(
                f"/api/v1/repositories/{repo.id}/explain",
                json={
                    "file_path": "src/calculator.py",
                    "start_line": 5,
                    "end_line": 8,
                    "question": "Are there any potential bugs or edge cases?",
                    "explanation_style": style,
                },
                headers=headers,
            )
            assert resp.status_code == 200
            data = resp.json()["data"]
            assert data["explanation_style"] == style
            assert data["language"] == "python"
            assert data["overview"]
            assert len(data["citations"]) >= 1
            assert data["citations"][0]["file_path"] == "src/calculator.py"
            # Cross-file reference to clamp_value from math_helpers.py
            related_names = [r["name"] for r in data["related_symbols"]]
            assert "clamp_value" in related_names


@pytest.mark.asyncio
async def test_missing_snapshot_invalid_snapshot_and_validation(
    client: AsyncClient,
    test_db: AsyncSession,
    authenticated_session: dict,
    ai_workspace: Path,
):
    """Missing snapshots, invalid snapshot IDs, and path traversal inputs return safe errors."""
    headers = _auth_headers(client, authenticated_session)

    # Repo with NO snapshot yet
    empty_repo = Repository(
        id=uuid.uuid4(),
        owner_user_id=authenticated_session["user"].id,
        provider="github",
        provider_repo_id="empty-123",
        owner=authenticated_session["user"].username,
        name="no-snapshot-repo",
        canonical_url="https://github.com/athena_dev/no-snapshot-repo",
        status="ACTIVE",
    )
    test_db.add(empty_repo)
    await test_db.commit()

    no_snap_idx = await client.post(
        f"/api/v1/repositories/{empty_repo.id}/index",
        json={},
        headers=headers,
    )
    assert no_snap_idx.status_code == 404
    assert no_snap_idx.json()["error"]["code"] == "NO_SNAPSHOT"

    no_snap_search = await client.post(
        f"/api/v1/repositories/{empty_repo.id}/search",
        json={"query": "anything"},
        headers=headers,
    )
    assert no_snap_search.status_code == 404

    # Ingested repo with nonexistent snapshot_id
    repo = await _create_and_ingest_repo(test_db, authenticated_session["user"], ai_workspace, name="valid-repo")
    fake_snapshot_id = uuid.uuid4()

    with patch("src.services.ai_service.get_repository_workspace_path", return_value=ai_workspace):
        bad_snap = await client.post(
            f"/api/v1/repositories/{repo.id}/search",
            json={"query": "clamp_value", "snapshot_id": str(fake_snapshot_id)},
            headers=headers,
        )
        assert bad_snap.status_code == 404

        # Malformed snapshot UUID -> 422 validation error
        malformed_snap = await client.post(
            f"/api/v1/repositories/{repo.id}/search",
            json={"query": "clamp_value", "snapshot_id": "not-a-uuid"},
            headers=headers,
        )
        assert malformed_snap.status_code == 422

        # Path traversal attempt in explain -> 422 validation error
        traversal = await client.post(
            f"/api/v1/repositories/{repo.id}/explain",
            json={"file_path": "../../etc/passwd"},
            headers=headers,
        )
        assert traversal.status_code == 422

        # Inverted line range -> 422 validation error
        bad_lines = await client.post(
            f"/api/v1/repositories/{repo.id}/explain",
            json={"file_path": "src/calculator.py", "start_line": 10, "end_line": 2},
            headers=headers,
        )
        assert bad_lines.status_code == 422
