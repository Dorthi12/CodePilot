"""Unit tests for Dependency Vulnerability Audit and SCA (M6 / SEC-DEP-09).

Specifications:
- Master Architecture Specification v2.1 §10 (M6), §6.6
- Security and Testing Specification v1.0 §7.6 (SEC-DEP-09):
  "Dependency data about the repository is read from manifests without installing anything."
"""

import pytest
from ai_service.security_analysis.dependency_scanner import DependencyScanner
from backend.app.modules.security_analysis.dependency_audit import DependencyAuditor
from shared.types.agent import FindingSeverity


@pytest.fixture
def scanner() -> DependencyScanner:
    return DependencyScanner()


@pytest.fixture
def auditor() -> DependencyAuditor:
    return DependencyAuditor()


def test_requirements_txt_vulnerability_detection(scanner: DependencyScanner):
    """Detect vulnerable packages in requirements.txt without running setup or install."""
    content = """# Core dependencies
requests==2.28.1
urllib3==1.26.15
django==4.1.2
pydantic==2.5.0
"""
    files = {"requirements.txt": content}
    inventory, findings, warnings = scanner.scan_manifests("snap-1", "run-1", files)

    # 4 packages in inventory
    assert len(inventory) == 4
    pkg_names = {item.package for item in inventory}
    assert pkg_names == {"requests", "urllib3", "django", "pydantic"}

    # Vulnerability detections for requests, urllib3, django
    assert len(findings) >= 3
    cves = [f.metadata.get("advisory_id") for f in findings]
    assert "CVE-2023-32681" in cves  # requests
    assert "CVE-2023-43804" in cves  # urllib3
    assert "CVE-2023-37466" in cves  # django

    for f in findings:
        assert f.tool == "dependency_audit"
        assert f.category == "SECURITY"
        assert f.remediation is not None
        assert len(f.evidence) == 1


def test_clean_requirements_txt_no_findings(scanner: DependencyScanner):
    """Clean control: Patched package versions trigger no findings."""
    content = """requests==2.31.0
urllib3==2.0.7
django==4.2.8
"""
    files = {"requirements.txt": content}
    inventory, findings, _ = scanner.scan_manifests("snap-1", "run-1", files)
    assert len(inventory) == 3
    assert len(findings) == 0


def test_pyproject_toml_parsing(scanner: DependencyScanner):
    """Parse pyproject.toml dependencies without executing project build scripts."""
    content = """[project]
name = "my-service"
version = "0.1.0"
dependencies = [
    "flask==2.2.2",
    "cryptography==41.0.4",
]
"""
    files = {"pyproject.toml": content}
    inventory, findings, _ = scanner.scan_manifests("snap-1", "run-1", files)
    assert len(inventory) == 2
    assert len(findings) >= 2
    cves = [f.metadata.get("advisory_id") for f in findings]
    assert "CVE-2023-27494" in cves  # flask
    assert "CVE-2023-46136" in cves  # cryptography


def test_package_json_parsing(scanner: DependencyScanner):
    """Parse Node.js package.json manifest for runtime and dev dependencies."""
    content = """{
  "name": "web-frontend",
  "dependencies": {
    "lodash": "^4.17.19"
  },
  "devDependencies": {
    "typescript": "^5.0.0"
  }
}"""
    files = {"package.json": content}
    inventory, findings, _ = scanner.scan_manifests("snap-1", "run-1", files)
    assert len(inventory) == 2
    scopes = {item.package: item.scope for item in inventory}
    assert scopes["lodash"] == "runtime"
    assert scopes["typescript"] == "dev"
    assert len(findings) >= 1
    assert any("CVE-2021-23337" in f.rule_id for f in findings)


def test_advisory_feed_failure_reports_not_checked(auditor: DependencyAuditor):
    """When advisory feed is unavailable, audit reports failure and explicitly discloses not_checked gap."""
    files = {"requirements.txt": "requests==2.28.1\n"}
    inventory, findings, coverage, log, warnings, not_checked = auditor.run_audit(
        files=files,
        snapshot_id="snap-1",
        run_id="run-1",
        simulate_feed_failure=True,
    )
    assert coverage.status == "FAILED"
    assert len(not_checked) >= 1
    assert "feed unavailable" in not_checked[0].lower()
    assert len(warnings) >= 1
