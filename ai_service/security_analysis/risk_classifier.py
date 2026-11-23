"""Risk classification, CVSS mapping, and AI triage guidance for security findings.

Specifications:
- Master Architecture Specification v2.1 §10 (M6)
- Security and Testing Specification v1.0 §8.9 (AI-10)
"""

from typing import Any, Dict, List, Optional
from shared.types.agent import FindingSeverity
from shared.types.findings import Finding

SEVERITY_WEIGHTS: Dict[FindingSeverity, float] = {
    FindingSeverity.CRITICAL: 10.0,
    FindingSeverity.HIGH: 7.5,
    FindingSeverity.MEDIUM: 5.0,
    FindingSeverity.LOW: 2.5,
    FindingSeverity.INFO: 1.0,
}


class RiskClassifier:
    """Classifies, ranks, and prioritizes security findings based on impact and reachability."""

    def calculate_risk_score(self, finding: Finding) -> float:
        """Compute normalized risk score [0.0 - 10.0] combining severity, confidence, and context."""
        base_weight = SEVERITY_WEIGHTS.get(finding.severity, 5.0)
        confidence_factor = finding.confidence

        # Bonus for presence of taint path or secret detection
        exploitability_bonus = 0.0
        if finding.metadata.get("source_to_sink_path"):
            exploitability_bonus += 1.0
        if "SECRET" in finding.rule_id:
            exploitability_bonus += 0.5

        raw_score = (base_weight * 0.8) + (confidence_factor * 1.5) + exploitability_bonus
        return round(min(10.0, max(1.0, raw_score)), 2)

    def prioritize_findings(self, findings: List[Finding]) -> List[Finding]:
        """Sort findings by risk score descending, then by line start for deterministic ordering."""
        return sorted(
            findings,
            key=lambda f: (
                self.calculate_risk_score(f),
                f.confidence,
                -f.line_start,
            ),
            reverse=True,
        )

    def generate_triage_summary(self, findings: List[Finding]) -> Dict[str, Any]:
        """Generate structured executive triage breakdown."""
        counts_by_sev: Dict[str, int] = {}
        counts_by_cwe: Dict[str, int] = {}
        counts_by_owasp: Dict[str, int] = {}

        for f in findings:
            s_name = f.severity.value
            counts_by_sev[s_name] = counts_by_sev.get(s_name, 0) + 1
            if f.cwe:
                counts_by_cwe[f.cwe] = counts_by_cwe.get(f.cwe, 0) + 1
            if f.owasp:
                counts_by_owasp[f.owasp] = counts_by_owasp.get(f.owasp, 0) + 1

        overall_posture = "CLEAN"
        if counts_by_sev.get("CRITICAL", 0) > 0:
            overall_posture = "CRITICAL_RISK"
        elif counts_by_sev.get("HIGH", 0) > 0:
            overall_posture = "HIGH_RISK"
        elif counts_by_sev.get("MEDIUM", 0) > 0:
            overall_posture = "ELEVATED_RISK"
        elif counts_by_sev.get("LOW", 0) > 0:
            overall_posture = "LOW_RISK"

        return {
            "posture": overall_posture,
            "total_findings": len(findings),
            "counts_by_severity": counts_by_sev,
            "counts_by_cwe": counts_by_cwe,
            "counts_by_owasp": counts_by_owasp,
        }
