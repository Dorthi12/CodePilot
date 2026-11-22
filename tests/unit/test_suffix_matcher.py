"""Unit tests for longest-suffix frame-to-repository path mapping and path validation."""

import pytest
from ai_service.debugging.stack_trace_parser import (
    match_longest_suffix,
    normalize_repo_path,
)


def test_normalize_repo_path() -> None:
    assert normalize_repo_path("src\\app\\service.py") == "src/app/service.py"
    assert normalize_repo_path("./app/service.py") == "app/service.py"
    assert normalize_repo_path("/app/service.py") == "app/service.py"
    assert normalize_repo_path("C:\\app\\service.py") == "app/service.py"
    assert normalize_repo_path("app/service.py\0") == "app/service.py"


def test_match_exact() -> None:
    repo_files = ["app/api/routes.py", "app/auth/service.py", "tests/test_auth.py"]
    match, is_ambiguous, candidates = match_longest_suffix("app/auth/service.py", repo_files)
    assert match == "app/auth/service.py"
    assert not is_ambiguous
    assert candidates == ["app/auth/service.py"]


def test_match_longest_suffix_with_deployment_prefix() -> None:
    repo_files = ["src/auth/service.py", "src/api/routes.py"]
    # Simulated container or virtualenv absolute path
    raw_path = "/var/task/root/src/auth/service.py"
    match, is_ambiguous, candidates = match_longest_suffix(raw_path, repo_files)
    assert match == "src/auth/service.py"
    assert not is_ambiguous
    assert candidates == ["src/auth/service.py"]


def test_match_longest_suffix_disambiguation() -> None:
    # When one candidate matches more suffix segments than another
    repo_files = ["backend/service.py", "frontend/components/service.py", "legacy/service.py"]
    raw_path = "/opt/project/components/service.py"
    match, is_ambiguous, candidates = match_longest_suffix(raw_path, repo_files)
    # components/service.py matches 2 segments, while backend/service.py matches only 1
    assert match == "frontend/components/service.py"
    assert not is_ambiguous


def test_ambiguous_suffix_match_not_guessed() -> None:
    # AUD-11: Ambiguous matches must be reported, not guessed
    repo_files = ["services/user/service.py", "services/order/service.py"]
    raw_path = "/unknown/env/service.py"  # matches both with 1 suffix segment 'service.py'
    match, is_ambiguous, candidates = match_longest_suffix(raw_path, repo_files)
    assert match is None
    assert is_ambiguous is True
    assert len(candidates) == 2
    assert "services/user/service.py" in candidates
    assert "services/order/service.py" in candidates


def test_unmatched_path() -> None:
    repo_files = ["src/main.py"]
    match, is_ambiguous, candidates = match_longest_suffix("external_lib/module.py", repo_files)
    assert match is None
    assert not is_ambiguous
    assert candidates == []
