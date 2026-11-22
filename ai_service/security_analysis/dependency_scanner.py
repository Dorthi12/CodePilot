"""Dependency vulnerability auditor and Software Composition Analysis (SCA) engine.

Specifications:
- Master Architecture Specification v2.1 §10 (M6), §6.6
- Security and Testing Specification v1.0 §7.6 (SEC-DEP-09):
  "Dependency data about the repository (A4 inventory, M6 advisories) is read from manifests without installing anything."
"""

import hashlib
import json
import re
from typing import Any, Dict, List, Optional, Tuple
from uuid import uuid4

from shared.types.agent import FindingOrigin, FindingSeverity, FindingStatus
from shared.types.findings import (
    Finding,
    FindingEvidence,
    compute_finding_fingerprint,
)
from shared.types.security import DependencyInventoryItem, VulnerabilityAdvisory

# Curated high-fidelity known CVE advisory database for offline and enterprise auditing
DEFAULT_ADVISORIES: List[VulnerabilityAdvisory] = [
    VulnerabilityAdvisory(
        id="CVE-2023-32681",
        package="requests",
        ecosystem="pypi",
        vulnerable_versions="< 2.31.0",
        fixed_version="2.31.0",
        severity=FindingSeverity.MEDIUM,
        cvss_score=6.1,
        cwe="CWE-200",
        owasp="A01:2021-Broken Access Control",
        title="Requests Proxy-Authorization Header Leak",
        description="Requests forwards Proxy-Authorization headers to destination servers when following HTTPS redirects.",
        remediation="Upgrade requests to version 2.31.0 or higher.",
    ),
    VulnerabilityAdvisory(
        id="CVE-2023-43804",
        package="urllib3",
        ecosystem="pypi",
        vulnerable_versions="< 2.0.7",
        fixed_version="2.0.7",
        severity=FindingSeverity.HIGH,
        cvss_score=7.5,
        cwe="CWE-200",
        owasp="A01:2021-Broken Access Control",
        title="Urllib3 Cookie Header Leak on Cross-Origin Redirect",
        description="urllib3 does not strip Cookie headers when HTTP requests redirect to a different origin.",
        remediation="Upgrade urllib3 to version 2.0.7 or higher.",
    ),
    VulnerabilityAdvisory(
        id="CVE-2023-46136",
        package="cryptography",
        ecosystem="pypi",
        vulnerable_versions="< 41.0.6",
        fixed_version="41.0.6",
        severity=FindingSeverity.HIGH,
        cvss_score=7.5,
        cwe="CWE-400",
        owasp="A06:2021-Vulnerable and Outdated Components",
        title="Cryptography Resource Exhaustion during Certificate Parsing",
        description="cryptography parses certain ASN.1 structures with quadratic complexity leading to Denial of Service.",
        remediation="Upgrade cryptography to version 41.0.6 or higher.",
    ),
    VulnerabilityAdvisory(
        id="CVE-2023-27494",
        package="flask",
        ecosystem="pypi",
        vulnerable_versions="< 2.2.5",
        fixed_version="2.2.5",
        severity=FindingSeverity.HIGH,
        cvss_score=7.5,
        cwe="CWE-22",
        owasp="A01:2021-Broken Access Control",
        title="Flask Send File Path Traversal",
        description="Werkzeug/Flask send_file could be coerced into directory traversal on Windows platforms.",
        remediation="Upgrade flask to version 2.2.5 or higher.",
    ),
    VulnerabilityAdvisory(
        id="CVE-2023-37466",
        package="django",
        ecosystem="pypi",
        vulnerable_versions="< 4.2.4",
        fixed_version="4.2.4",
        severity=FindingSeverity.CRITICAL,
        cvss_score=9.8,
        cwe="CWE-89",
        owasp="A03:2021-Injection",
        title="Django SQL Injection in QuerySet.aggregate",
        description="Potential SQL injection vulnerability in QuerySet.aggregate() via column aliases.",
        remediation="Upgrade django to version 4.2.4 or higher.",
    ),
    VulnerabilityAdvisory(
        id="CVE-2024-22195",
        package="jinja2",
        ecosystem="pypi",
        vulnerable_versions="< 3.1.3",
        fixed_version="3.1.3",
        severity=FindingSeverity.MEDIUM,
        cvss_score=6.1,
        cwe="CWE-79",
        owasp="A03:2021-Injection",
        title="Jinja2 XSS via xmlattr filter",
        description="Jinja2's xmlattr filter does not properly escape keys with spaces or control characters.",
        remediation="Upgrade jinja2 to version 3.1.3 or higher.",
    ),
    VulnerabilityAdvisory(
        id="CVE-2024-23334",
        package="aiohttp",
        ecosystem="pypi",
        vulnerable_versions="< 3.9.2",
        fixed_version="3.9.2",
        severity=FindingSeverity.HIGH,
        cvss_score=7.5,
        cwe="CWE-22",
        owasp="A01:2021-Broken Access Control",
        title="aiohttp Directory Traversal Vulnerability",
        description="aiohttp directory traversal vulnerability in static file serving when follow_symlinks=True.",
        remediation="Upgrade aiohttp to version 3.9.2 or higher.",
    ),
    VulnerabilityAdvisory(
        id="CVE-2021-23337",
        package="lodash",
        ecosystem="npm",
        vulnerable_versions="< 4.17.21",
        fixed_version="4.17.21",
        severity=FindingSeverity.HIGH,
        cvss_score=7.2,
        cwe="CWE-78",
        owasp="A03:2021-Injection",
        title="Lodash Command Injection in template",
        description="Lodash versions prior to 4.17.21 are vulnerable to Command Injection via template functions.",
        remediation="Upgrade lodash to version 4.17.21 or higher.",
    ),
    VulnerabilityAdvisory(
        id="CVE-2023-45853",
        package="zlib",
        ecosystem="generic",
        vulnerable_versions="< 1.3",
        fixed_version="1.3",
        severity=FindingSeverity.CRITICAL,
        cvss_score=9.8,
        cwe="CWE-787",
        owasp="A06:2021-Vulnerable and Outdated Components",
        title="MiniZip in zlib Out-of-bounds Write",
        description="Integer overflow and out-of-bounds write in MiniZip component.",
        remediation="Upgrade zlib to version 1.3 or higher.",
    ),
]


def _parse_version_tuple(v_str: str) -> Tuple[int, ...]:
    """Parse semver string into comparable integer tuple."""
    clean = re.sub(r"[^0-9\.]", "", v_str.strip())
    parts = clean.split(".")
    res = []
    for p in parts:
        if p.isdigit():
            res.append(int(p))
    return tuple(res) if res else (0,)


def _is_version_vulnerable(installed_ver: str, constraint: str) -> bool:
    """Check if installed version satisfies vulnerability constraint (e.g. '< 2.31.0')."""
    if not installed_ver or not constraint:
        return False

    installed_tup = _parse_version_tuple(installed_ver)

    # Patterns like "< 2.31.0", "<= 2.2.4", "== 1.0.0"
    m = re.match(r"(<=?|==|>=?)\s*([0-9\.]+)", constraint.strip())
    if not m:
        return False

    op, target_str = m.groups()
    target_tup = _parse_version_tuple(target_str)

    # Pad tuples to equal length
    max_len = max(len(installed_tup), len(target_tup))
    inst_padded = installed_tup + (0,) * (max_len - len(installed_tup))
    targ_padded = target_tup + (0,) * (max_len - len(target_tup))

    if op == "<":
        return inst_padded < targ_padded
    elif op == "<=":
        return inst_padded <= targ_padded
    elif op == "==":
        return inst_padded == targ_padded
    elif op == ">=":
        return inst_padded >= targ_padded
    elif op == ">":
        return inst_padded > targ_padded
    return False


class DependencyScanner:
    """Non-executing Dependency Inventory and Vulnerability Scanner (SEC-DEP-09)."""

    def __init__(self, advisory_db: Optional[List[VulnerabilityAdvisory]] = None) -> None:
        self.advisories = advisory_db if advisory_db is not None else list(DEFAULT_ADVISORIES)

    def scan_manifests(
        self,
        snapshot_id: str,
        run_id: str,
        files: Dict[str, str],
    ) -> Tuple[List[DependencyInventoryItem], List[Finding], List[str]]:
        """Parse package manifests to build dependency inventory and detect CVE vulnerabilities.

        Never executes setup.py, install scripts, or external build commands (SEC-DEP-09).
        """
        inventory: List[DependencyInventoryItem] = []
        findings: List[Finding] = []
        warnings: List[str] = []

        manifest_count = 0

        for path, content in files.items():
            norm_path = path.replace("\\", "/").lower()

            if norm_path.endswith("requirements.txt") or "requirements" in norm_path and norm_path.endswith(".txt"):
                manifest_count += 1
                items, vuln_findings = self._parse_requirements_txt(
                    snapshot_id=snapshot_id,
                    run_id=run_id,
                    path=path,
                    content=content,
                )
                inventory.extend(items)
                findings.extend(vuln_findings)

            elif norm_path.endswith("pyproject.toml"):
                manifest_count += 1
                items, vuln_findings = self._parse_pyproject_toml(
                    snapshot_id=snapshot_id,
                    run_id=run_id,
                    path=path,
                    content=content,
                )
                inventory.extend(items)
                findings.extend(vuln_findings)

            elif norm_path.endswith("package.json"):
                manifest_count += 1
                items, vuln_findings = self._parse_package_json(
                    snapshot_id=snapshot_id,
                    run_id=run_id,
                    path=path,
                    content=content,
                )
                inventory.extend(items)
                findings.extend(vuln_findings)

        if manifest_count == 0:
            warnings.append("No package manifests found in scanned scope.")

        return inventory, findings, warnings

    def _match_advisories(
        self,
        package: str,
        ecosystem: str,
        version_spec: str,
        resolved_version: Optional[str],
        manifest_path: str,
        line_num: int,
        raw_line: str,
        snapshot_id: str,
        run_id: str,
    ) -> Tuple[List[str], List[Finding]]:
        """Check package and version against vulnerability advisories."""
        matched_advisory_ids: List[str] = []
        findings: List[Finding] = []

        test_version = resolved_version or version_spec
        # Clean operators if present e.g. "==2.28.1" -> "2.28.1"
        clean_version = re.sub(r"^[=~<>^]+", "", test_version).strip()

        for adv in self.advisories:
            if adv.package.lower() == package.lower() and (adv.ecosystem == "generic" or adv.ecosystem == ecosystem):
                if _is_version_vulnerable(clean_version, adv.vulnerable_versions):
                    matched_advisory_ids.append(adv.id)
                    rule_id = f"SEC-DEP-{adv.id}"
                    finding_fp = compute_finding_fingerprint(
                        rule_id=rule_id,
                        file_path=manifest_path,
                        symbol_or_anchor=f"{package}:{clean_version}",
                        snippet=raw_line,
                    )
                    evidence = [
                        FindingEvidence(
                            file_path=manifest_path,
                            line_start=line_num,
                            line_end=line_num,
                            snippet=raw_line,
                            snippet_hash=hashlib.sha256(raw_line.encode("utf-8")).hexdigest(),
                            role="SUPPORTS",
                        )
                    ]
                    finding = Finding(
                        snapshot_id=snapshot_id,
                        analysis_run_id=run_id,
                        fingerprint=finding_fp,
                        origin=FindingOrigin.STATIC_TOOL,
                        category="SECURITY",
                        rule_id=rule_id,
                        tool="dependency_audit",
                        tool_version="1.0.0",
                        severity=adv.severity,
                        confidence=0.95,
                        cwe=adv.cwe,
                        owasp=adv.owasp,
                        title=f"Vulnerable Dependency: {package} ({adv.id})",
                        description=(
                            f"{adv.title}: Package '{package}' version '{clean_version}' is vulnerable to {adv.id}. "
                            f"{adv.description}"
                        ),
                        remediation=adv.remediation,
                        file_path=manifest_path,
                        line_start=line_num,
                        line_end=line_num,
                        evidence=evidence,
                        status=FindingStatus.OPEN,
                        metadata={
                            "package": package,
                            "installed_version": clean_version,
                            "fixed_version": adv.fixed_version,
                            "advisory_id": adv.id,
                            "cvss_score": adv.cvss_score,
                        },
                    )
                    findings.append(finding)

        return matched_advisory_ids, findings

    def _parse_requirements_txt(
        self,
        snapshot_id: str,
        run_id: str,
        path: str,
        content: str,
    ) -> Tuple[List[DependencyInventoryItem], List[Finding]]:
        items: List[DependencyInventoryItem] = []
        findings: List[Finding] = []

        lines = content.splitlines()
        for idx, line in enumerate(lines, start=1):
            clean_line = line.strip()
            if not clean_line or clean_line.startswith("#") or clean_line.startswith("-"):
                continue

            # e.g. requests==2.28.1 or urllib3>=1.26.0,<2.0.0
            m = re.match(r"^([A-Za-z0-9_\-\.]+)\s*([=><~^!].*)?$", clean_line)
            if m:
                pkg_name = m.group(1).strip()
                v_spec = m.group(2).strip() if m.group(2) else "*"
                resolved_v = None
                if v_spec.startswith("=="):
                    resolved_v = v_spec.lstrip("=").strip()

                advisory_ids, vuln_findings = self._match_advisories(
                    package=pkg_name,
                    ecosystem="pypi",
                    version_spec=v_spec,
                    resolved_version=resolved_v,
                    manifest_path=path,
                    line_num=idx,
                    raw_line=clean_line,
                    snapshot_id=snapshot_id,
                    run_id=run_id,
                )
                findings.extend(vuln_findings)

                items.append(
                    DependencyInventoryItem(
                        snapshot_id=snapshot_id,
                        ecosystem="pypi",
                        package=pkg_name,
                        version_spec=v_spec,
                        resolved_version=resolved_v,
                        scope="runtime",
                        manifest_path=path,
                        advisory_ids=advisory_ids,
                    )
                )

        return items, findings

    def _parse_pyproject_toml(
        self,
        snapshot_id: str,
        run_id: str,
        path: str,
        content: str,
    ) -> Tuple[List[DependencyInventoryItem], List[Finding]]:
        items: List[DependencyInventoryItem] = []
        findings: List[Finding] = []

        # Lightweight regex parser for dependencies array in pyproject.toml
        lines = content.splitlines()
        in_deps = False

        for idx, line in enumerate(lines, start=1):
            clean = line.strip()
            if "dependencies = [" in clean:
                in_deps = True
                continue
            if in_deps:
                if clean.startswith("]"):
                    in_deps = False
                    continue
                # item like "requests>=2.28.0",
                m = re.match(r"""["']([A-Za-z0-9_\-\.]+)\s*([=><~^!].*?)?["']""", clean)
                if m:
                    pkg_name = m.group(1).strip()
                    v_spec = m.group(2).strip() if m.group(2) else "*"
                    resolved_v = v_spec.lstrip("=").strip() if v_spec.startswith("==") else None

                    advisory_ids, vuln_findings = self._match_advisories(
                        package=pkg_name,
                        ecosystem="pypi",
                        version_spec=v_spec,
                        resolved_version=resolved_v,
                        manifest_path=path,
                        line_num=idx,
                        raw_line=clean,
                        snapshot_id=snapshot_id,
                        run_id=run_id,
                    )
                    findings.extend(vuln_findings)
                    items.append(
                        DependencyInventoryItem(
                            snapshot_id=snapshot_id,
                            ecosystem="pypi",
                            package=pkg_name,
                            version_spec=v_spec,
                            resolved_version=resolved_v,
                            scope="runtime",
                            manifest_path=path,
                            advisory_ids=advisory_ids,
                        )
                    )

        return items, findings

    def _parse_package_json(
        self,
        snapshot_id: str,
        run_id: str,
        path: str,
        content: str,
    ) -> Tuple[List[DependencyInventoryItem], List[Finding]]:
        items: List[DependencyInventoryItem] = []
        findings: List[Finding] = []

        try:
            data = json.loads(content)
        except Exception:
            return items, findings

        for section, scope in [("dependencies", "runtime"), ("devDependencies", "dev")]:
            deps_dict = data.get(section, {})
            if isinstance(deps_dict, dict):
                for pkg_name, v_spec in deps_dict.items():
                    if not isinstance(v_spec, str):
                        continue
                    clean_v = v_spec.lstrip("^~=").strip()
                    advisory_ids, vuln_findings = self._match_advisories(
                        package=pkg_name,
                        ecosystem="npm",
                        version_spec=v_spec,
                        resolved_version=clean_v,
                        manifest_path=path,
                        line_num=1,
                        raw_line=f'"{pkg_name}": "{v_spec}"',
                        snapshot_id=snapshot_id,
                        run_id=run_id,
                    )
                    findings.extend(vuln_findings)
                    items.append(
                        DependencyInventoryItem(
                            snapshot_id=snapshot_id,
                            ecosystem="npm",
                            package=pkg_name,
                            version_spec=v_spec,
                            resolved_version=clean_v,
                            scope=scope,
                            manifest_path=path,
                            advisory_ids=advisory_ids,
                        )
                    )

        return items, findings
