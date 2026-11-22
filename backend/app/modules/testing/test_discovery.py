"""Test Discovery and Mapping: Discovers existing test conventions, frameworks, and graph relationships.

Specifications:
- Master Architecture Specification v2.1 §10 (M5: Test-to-target mapping via TESTS edges)
- API and Data Specification v1.0 §4.7 (TESTS edges with confidence)
- Security & Testing Specification v1.0 §8.9 (AI-08)
"""

import os
import posixpath
import re
from typing import Any, Dict, List, Optional, Set, Tuple

from agentic.common.agent_context import (
    GraphEdge,
    RepositorySnapshotContext,
    SnapshotContextRegistry,
    SnapshotFile,
)


class TestDiscoveryResult:
    """Discovered test environment, conventions, and mapped graph edges."""

    def __init__(
        self,
        framework: str,
        existing_test_files: List[str],
        mapped_tests_edges: List[Dict[str, Any]],
        detected_fixtures: List[str],
        suggested_test_path: str,
    ) -> None:
        self.framework = framework
        self.existing_test_files = existing_test_files
        self.mapped_tests_edges = mapped_tests_edges
        self.detected_fixtures = detected_fixtures
        self.suggested_test_path = suggested_test_path


class TestDiscoveryService:
    """Discovers existing test files, frameworks, conventions, and establishes TESTS relationships."""

    @staticmethod
    def discover_tests(
        snapshot_id: str,
        target_file: str,
        explicit_framework: Optional[str] = None,
        search_paths: Optional[List[str]] = None,
    ) -> TestDiscoveryResult:
        """Analyze repository snapshot to locate existing test files and establish target relationships."""
        ctx = SnapshotContextRegistry.get(snapshot_id)
        norm_target = posixpath.normpath(target_file.replace("\\", "/")).lstrip("/")
        target_basename = posixpath.basename(norm_target)
        target_stem = posixpath.splitext(target_basename)[0]

        existing_test_files: List[str] = []
        fixtures: List[str] = []
        framework = explicit_framework or "pytest"

        # 1. Scan files in snapshot for tests and fixtures
        for path, file_obj in ctx.files.items():
            norm_p = path.replace("\\", "/")
            if "conftest.py" in norm_p:
                fixtures.append(norm_p)
            if "/tests/" in norm_p or norm_p.startswith("tests/") or "test_" in norm_p or "_test." in norm_p:
                existing_test_files.append(norm_p)
                # Framework detection
                if "import pytest" in file_obj.content or "@pytest" in file_obj.content:
                    framework = "pytest"
                elif "import unittest" in file_obj.content:
                    if framework != "pytest":
                        framework = "unittest"

        # 2. Derive TESTS relationships with confidence
        mapped_edges: List[Dict[str, Any]] = []
        for t_file in existing_test_files:
            t_obj = ctx.files.get(t_file)
            confidence = "LOW"
            rel_type = "PROBABLE"

            # Check direct naming convention: test_auth.py -> auth.py
            t_basename = posixpath.basename(t_file)
            if t_basename in (f"test_{target_basename}", f"{target_stem}_test.py"):
                confidence = "HIGH"
                rel_type = "RESOLVED"
            elif t_obj and (target_stem in t_obj.content or norm_target in t_obj.content):
                confidence = "MEDIUM"
                rel_type = "RESOLVED"

            mapped_edges.append({
                "source": t_file,
                "target": norm_target,
                "relationship": "TESTS",
                "confidence": confidence,
                "resolution_method": rel_type,
            })

            # Record in snapshot context graph
            ctx.add_edge(source=t_file, target=norm_target, relationship="TESTS")

        # 3. Suggest new test file destination path matching project conventions
        if any("tests/unit" in f for f in existing_test_files):
            suggested_dir = "tests/unit"
        elif any("tests/" in f for f in existing_test_files):
            suggested_dir = "tests"
        else:
            suggested_dir = "tests"

        suggested_path = f"{suggested_dir}/test_{target_basename}"

        return TestDiscoveryResult(
            framework=framework,
            existing_test_files=existing_test_files,
            mapped_tests_edges=mapped_edges,
            detected_fixtures=fixtures,
            suggested_test_path=suggested_path,
        )
