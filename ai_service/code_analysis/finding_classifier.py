"""Finding classifier and normalizer ensuring strict origin separation and metadata enrichment."""

from typing import Any, Dict, List, Optional
from shared.types.agent import FindingOrigin, FindingSeverity, FindingStatus
from shared.types.findings import (
    Finding,
    FindingEvidence,
    FindingLocation,
    compute_finding_fingerprint,
)


class FindingClassifier:
    """Classifies, normalizes, and validates findings according to CodePilot specifications."""

    CWE_MAPPINGS: Dict[str, str] = {
        "SEC-SECRET-001": "CWE-798",
        "SEC-SECRET-002": "CWE-798",
        "SEC-SECRET-003": "CWE-798",
        "SEC-SQLI-001": "CWE-89",
        "SEC-CODEI-001": "CWE-94",
        "BUG-MUTABLE-DEFAULT": "CWE-665",
        "BUG-BARE-EXCEPT": "CWE-391",
        "BUG-RESOURCE-LEAK": "CWE-775",
        "BUG-NONE-DEREF": "CWE-476",
        "BUG-ASSERT-PROD": "CWE-617",
        "QUAL-LEN-001": "CWE-1078",
        "QUAL-COMPLEX-001": "CWE-1120",
        "QUAL-CLONE-001": "CWE-1041",
        "QUAL-DEAD-001": "CWE-1164",
        "ARCH-CYCLE-001": "CWE-1047",
        "ARCH-GOD-001": "CWE-1061",
    }

    OWASP_MAPPINGS: Dict[str, str] = {
        "SEC-SECRET-001": "A07:2021",
        "SEC-SECRET-002": "A07:2021",
        "SEC-SECRET-003": "A07:2021",
        "SEC-SQLI-001": "A03:2021",
        "SEC-CODEI-001": "A03:2021",
        "BUG-MUTABLE-DEFAULT": "A06:2021",
        "BUG-BARE-EXCEPT": "A09:2021",
        "BUG-RESOURCE-LEAK": "A04:2021",
    }

    DEFAULT_CONFIDENCE: Dict[FindingOrigin, float] = {
        FindingOrigin.STATIC_TOOL: 0.95,
        FindingOrigin.GRAPH_RULE: 0.90,
        FindingOrigin.CONFIRMED: 1.00,
        FindingOrigin.AI_HYPOTHESIS: 0.75,
    }

    @classmethod
    def create_normalized_finding(
        cls,
        snapshot_id: str,
        analysis_run_id: str,
        rule_id: str,
        title: str,
        file_path: str,
        line_start: int,
        line_end: int,
        origin: FindingOrigin,
        category: str = "CODE_QUALITY",
        severity: FindingSeverity = FindingSeverity.MEDIUM,
        tool: str = "codepilot_engine",
        tool_version: str = "1.0.0",
        description: str = "",
        remediation: Optional[str] = None,
        symbol_id: Optional[str] = None,
        snippet: str = "",
        confidence: Optional[float] = None,
        evidence: Optional[List[FindingEvidence]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Finding:
        """Create a validated Finding object with deterministic fingerprint and enriched metadata."""
        # Enforce Rule: AI_HYPOTHESIS is never classified as CONFIRMED without reproduction
        if origin == FindingOrigin.AI_HYPOTHESIS and severity == FindingSeverity.CRITICAL:
            # An unverified model hypothesis cannot be presented as a critical
            # confirmed defect; preserve the signal while capping its severity.
            severity = FindingSeverity.HIGH
            confidence_score = confidence if confidence is not None else 0.70
        else:
            confidence_score = confidence if confidence is not None else cls.DEFAULT_CONFIDENCE.get(origin, 0.80)

        cwe = cls.CWE_MAPPINGS.get(rule_id)
        owasp = cls.OWASP_MAPPINGS.get(rule_id)

        # Build evidence list if not provided and snippet exists
        evidence_list = list(evidence or [])
        if not evidence_list and snippet:
            evidence_list.append(
                FindingEvidence(
                    file_path=file_path,
                    line_start=line_start,
                    line_end=line_end,
                    snippet=snippet,
                    role="SUPPORTS",
                )
            )

        fingerprint = compute_finding_fingerprint(
            rule_id=rule_id,
            file_path=file_path,
            # Line numbers drift as files evolve. Use a stable symbol anchor
            # when available; otherwise the rule, path and normalized snippet
            # form the fingerprint.
            symbol_or_anchor=symbol_id or "",
            snippet=snippet,
        )

        return Finding(
            snapshot_id=snapshot_id,
            analysis_run_id=analysis_run_id,
            fingerprint=fingerprint,
            origin=origin,
            category=category,
            rule_id=rule_id,
            tool=tool,
            tool_version=tool_version,
            severity=severity,
            confidence=confidence_score,
            cwe=cwe,
            owasp=owasp,
            title=title,
            description=description,
            remediation=remediation,
            file_path=file_path,
            line_start=line_start,
            line_end=line_end,
            symbol_id=symbol_id,
            evidence=evidence_list,
            status=FindingStatus.OPEN,
            metadata=metadata or {},
        )
