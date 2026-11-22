"""Citation and Evidence Validator enforcing the V1-V6 verification pipeline."""

from typing import Dict, List, Set
from shared.types.agent import VerificationCheck
from shared.types.findings import Finding
from agentic.common.agent_context import SnapshotContextRegistry
from agentic.schemas.agent import VerificationResult


class EvidenceValidator:
    """Verifies that all finding evidence and source citations are grounded in the pinned snapshot."""

    def verify_findings(
        self,
        snapshot_id: str,
        run_id: str,
        findings: List[Finding],
    ) -> List[VerificationResult]:
        ctx = SnapshotContextRegistry.get(snapshot_id)
        results: List[VerificationResult] = []
        seen_fingerprints: Set[str] = set()

        for finding in findings:
            # Check 1: Schema Compliance
            schema_passed = bool(
                finding.id
                and finding.rule_id
                and finding.title
                and finding.category
                and finding.severity
            )
            results.append(
                VerificationResult(
                    run_id=run_id,
                    finding_id=finding.id,
                    check=VerificationCheck.SCHEMA,
                    passed=schema_passed,
                    detail="Finding adheres to standardized metadata schema."
                    if schema_passed
                    else "Missing mandatory schema fields.",
                )
            )

            # Check 2: Duplicate Check
            if finding.fingerprint in seen_fingerprints:
                results.append(
                    VerificationResult(
                        run_id=run_id,
                        finding_id=finding.id,
                        check=VerificationCheck.DUPLICATE,
                        passed=False,
                        detail=f"Duplicate finding detected with fingerprint {finding.fingerprint[:12]}.",
                    )
                )
            else:
                seen_fingerprints.add(finding.fingerprint)
                results.append(
                    VerificationResult(
                        run_id=run_id,
                        finding_id=finding.id,
                        check=VerificationCheck.DUPLICATE,
                        passed=True,
                        detail="Finding fingerprint is unique within run.",
                    )
                )

            # Check 3: Citation Grounding (V1 - V5)
            file_obj = ctx.get_file(finding.file_path)
            if not file_obj:
                results.append(
                    VerificationResult(
                        run_id=run_id,
                        finding_id=finding.id,
                        check=VerificationCheck.CITATION,
                        passed=False,
                        detail=f"Cited file '{finding.file_path}' does not exist in snapshot '{snapshot_id}'.",
                    )
                )
                continue

            file_lines = len(file_obj.content.splitlines())
            if not (1 <= finding.line_start <= finding.line_end <= max(1, file_lines)):
                results.append(
                    VerificationResult(
                        run_id=run_id,
                        finding_id=finding.id,
                        check=VerificationCheck.CITATION,
                        passed=False,
                        detail=f"Line range {finding.line_start}-{finding.line_end} exceeds file bounds (1-{file_lines}).",
                    )
                )
                continue

            # Verify evidence items if present
            evidence_valid = True
            for ev in finding.evidence:
                ev_file = ctx.get_file(ev.file_path)
                if not ev_file:
                    evidence_valid = False
                    break
                if ev.snippet_hash and ev_file.content_hash != ev.snippet_hash:
                    # Content drift detected
                    evidence_valid = False
                    break

            results.append(
                VerificationResult(
                    run_id=run_id,
                    finding_id=finding.id,
                    check=VerificationCheck.CITATION,
                    passed=evidence_valid,
                    detail="Citation resolves to authentic lines and matching content hash."
                    if evidence_valid
                    else "Evidence snippet hash or file reference failed verification.",
                )
            )

        return results
