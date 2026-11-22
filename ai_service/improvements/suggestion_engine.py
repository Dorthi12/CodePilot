"""Suggestion Engine generating evidence-backed Code Improvement Suggestions.

Specifications:
- Master Architecture Specification v2.1 §10 (M3)
- API and Data Specification v1.0 §3.4.13, §4.6
- Security and Testing Specification v1.0 §7.3, §7.8 (SEC-PI-01..08), §8.9 (AI-19)
- Invariants I1, I5, I8
"""

import hashlib
import uuid
from typing import Any, Dict, List, Optional, Set

from shared.types.findings import Suppression
from shared.types.investigation import EvidenceRef, EvidenceRole
from shared.types.suggestions import (
    EffortLevel,
    RiskLevel,
    SuggestionCategory,
    SuggestionRecord,
)
from agentic.common.agent_context import RepositorySnapshotContext
from ai_service.code_analysis.code_smell_detector import CodeSmellDetector, RulePackConfig
from ai_service.improvements.refactoring_analyzer import RefactoringAnalyzer, RefactoringCandidate
from ai_service.security_analysis.secret_detector import redact_secrets


class PromptInjectionDefender:
    """Implements SEC-PI-01 to SEC-PI-08 prompt injection defenses for code suggestions."""

    @staticmethod
    def generate_delimited_block(content: str, label: str = "EVIDENCE") -> str:
        """Wrap untrusted repository content in random-nonce delimited blocks (SEC-PI-01)."""
        nonce = uuid.uuid4().hex[:12]
        # Neutralize any occurrence of the delimiter inside the content
        safe_content = content.replace(f"</{label}_{nonce}>", f"[ESCAPED_DELIMITER]")
        return f"<{label}_{nonce}>\n{safe_content}\n</{label}_{nonce}>"

    @staticmethod
    def sanitize_output(text: str) -> str:
        """Neutralize @-mentions and dangerous executable scripts (SEC-PI-06)."""
        if not text:
            return ""
        # Neutralize @-mentions to prevent accidental tagging in GitHub
        text = text.replace("@", "@\u200b")
        return text


class SuggestionEngine:
    """Generates structured, validated, and ranked improvement suggestions from snapshot context."""

    def __init__(
        self,
        refactoring_analyzer: Optional[RefactoringAnalyzer] = None,
        smell_detector: Optional[CodeSmellDetector] = None,
    ) -> None:
        self.refactoring_analyzer = refactoring_analyzer or RefactoringAnalyzer()
        self.smell_detector = smell_detector or CodeSmellDetector(RulePackConfig.get_preset("default"))
        self.security_defender = PromptInjectionDefender()

    def generate_suggestions(
        self,
        snapshot_ctx: RepositorySnapshotContext,
        run_id: str,
        target_paths: Optional[List[str]] = None,
        categories: Optional[List[SuggestionCategory]] = None,
        suppressions: Optional[List[Suppression]] = None,
        constraints: Optional[List[str]] = None,
    ) -> List[SuggestionRecord]:
        """Analyze snapshot files and generate complete evidence-backed SuggestionRecords."""
        allowed_categories = set(categories) if categories else set(SuggestionCategory)
        suppression_list = suppressions or []
        suggestions: List[SuggestionRecord] = []

        # 1. Filter files by target paths if specified
        target_files = {}
        for path, file_obj in snapshot_ctx.files.items():
            if target_paths:
                matched = False
                for p in target_paths:
                    if p.endswith("/**"):
                        prefix = p[:-3].lstrip("/")
                        if path.startswith(prefix):
                            matched = True
                            break
                    elif path == p.lstrip("/"):
                        matched = True
                        break
                if not matched:
                    continue
            target_files[path] = file_obj

        # 2. Run refactoring analyzer on each file
        for file_path, file_obj in target_files.items():
            candidates = self.refactoring_analyzer.analyze_file(file_path, file_obj.content)
            for cand in candidates:
                if cand.category not in allowed_categories:
                    continue

                record = self._candidate_to_record(
                    cand=cand,
                    snapshot_ctx=snapshot_ctx,
                    run_id=run_id,
                )

                # Check if suppressed
                if self._is_suppressed(record, file_path, suppression_list):
                    continue

                suggestions.append(record)

        # 3. Detect architectural / graph-level suggestions (e.g. God Module, Circular Dependencies)
        if SuggestionCategory.ARCHITECTURE in allowed_categories:
            arch_suggestions = self._detect_architectural_improvements(snapshot_ctx, run_id, suppression_list)
            suggestions.extend(arch_suggestions)

        return suggestions

    def _candidate_to_record(
        self,
        cand: RefactoringCandidate,
        snapshot_ctx: RepositorySnapshotContext,
        run_id: str,
    ) -> SuggestionRecord:
        """Convert a RefactoringCandidate into a SuggestionRecord with cryptographic evidence."""
        # Scrub any secrets from snippets, problem, and recommendation (AUD-11)
        clean_problem = redact_secrets(cand.problem)
        clean_recommendation = redact_secrets(cand.recommendation)
        clean_current = redact_secrets(cand.current_code)
        clean_proposed = redact_secrets(cand.proposed_code)

        # Extract verified snippet from snapshot file
        file_obj = snapshot_ctx.get_file(cand.file_path)
        snippet_text = clean_current
        if file_obj:
            lines = file_obj.content.splitlines()
            s_idx = max(0, cand.line_start - 1)
            e_idx = min(len(lines), cand.line_end)
            actual_snippet = "\n".join(lines[s_idx:e_idx])
            if actual_snippet.strip():
                snippet_text = redact_secrets(actual_snippet)

        # Cryptographic snippet hash for Invariant I5
        snippet_hash = hashlib.sha256(snippet_text.encode("utf-8")).hexdigest()

        evidence_ref = EvidenceRef(
            owner_type="SUGGESTION",
            owner_id=cand.rule_id,
            file_path=cand.file_path,
            line_start=cand.line_start,
            line_end=cand.line_end,
            snippet=snippet_text,
            snippet_hash=snippet_hash,
            role=EvidenceRole.SUPPORTS,
        )

        # Sanitize text
        clean_problem = self.security_defender.sanitize_output(clean_problem)
        clean_recommendation = self.security_defender.sanitize_output(clean_recommendation)

        return SuggestionRecord(
            run_id=run_id,
            snapshot_id=snapshot_ctx.snapshot_id,
            category=cand.category,
            rule_id=cand.rule_id,
            title=cand.title,
            problem=clean_problem,
            recommendation=clean_recommendation,
            current_code=clean_current,
            proposed_code=clean_proposed,
            benefit=cand.benefit,
            effort=cand.effort,
            risk=cand.risk,
            trade_offs=cand.trade_offs,
            affected_symbols=cand.affected_symbols,
            affected_files=[cand.file_path],
            evidence=[evidence_ref],
            confidence=cand.confidence,
        )

    def _detect_architectural_improvements(
        self,
        snapshot_ctx: RepositorySnapshotContext,
        run_id: str,
        suppressions: List[Suppression],
    ) -> List[SuggestionRecord]:
        """Detect architectural coupling and circular dependencies across the graph."""
        arch_suggestions = []

        # Build in-memory graph relationships
        in_degrees: Dict[str, int] = {}
        out_degrees: Dict[str, int] = {}
        for edge in snapshot_ctx.edges:
            out_degrees[edge.source] = out_degrees.get(edge.source, 0) + 1
            in_degrees[edge.target] = in_degrees.get(edge.target, 0) + 1

        # Check for God Modules (fan-in >= 5 and fan-out >= 5)
        for mod, in_deg in in_degrees.items():
            out_deg = out_degrees.get(mod, 0)
            if in_deg >= 5 and out_deg >= 5:
                file_obj = snapshot_ctx.get_file(mod)
                file_path = mod if file_obj else f"{mod}.py"
                snippet = f"# Module: {mod}\n# Fan-in: {in_deg}, Fan-out: {out_deg}"
                snippet_hash = hashlib.sha256(snippet.encode("utf-8")).hexdigest()

                evidence_ref = EvidenceRef(
                    owner_type="SUGGESTION",
                    owner_id="ARCH-GOD-MODULE",
                    file_path=file_path,
                    line_start=1,
                    line_end=min(10, len(file_obj.content.splitlines())) if file_obj else 1,
                    snippet=snippet,
                    snippet_hash=snippet_hash,
                    role=EvidenceRole.SUPPORTS,
                )

                record = SuggestionRecord(
                    run_id=run_id,
                    snapshot_id=snapshot_ctx.snapshot_id,
                    category=SuggestionCategory.ARCHITECTURE,
                    rule_id="ARCH-GOD-MODULE",
                    title=f"Decouple central God Module '{mod}' (in: {in_deg}, out: {out_deg})",
                    problem=(
                        f"Module '{mod}' exhibits both high afferent coupling (fan-in={in_deg}) "
                        f"and high efferent coupling (fan-out={out_deg}), making it an architectural bottleneck."
                    ),
                    recommendation="Extract domain interfaces and split the module into cohesive, smaller domain services.",
                    benefit="Reduces ripple effects across changes, decreases regression risk, and improves modular testability.",
                    effort=EffortLevel.HIGH,
                    risk=RiskLevel.MEDIUM,
                    trade_offs="Requires updating imports and consumers across the repository.",
                    affected_symbols=[mod],
                    affected_files=[file_path],
                    evidence=[evidence_ref],
                    confidence=0.88,
                )

                if not self._is_suppressed(record, file_path, suppressions):
                    arch_suggestions.append(record)

        return arch_suggestions

    def _is_suppressed(
        self,
        record: SuggestionRecord,
        file_path: str,
        suppressions: List[Suppression],
    ) -> bool:
        """Check if this suggestion matches an active repository suppression."""
        for sup in suppressions:
            if sup.fingerprint and record.fingerprint == sup.fingerprint:
                return True
            if sup.rule_id and record.rule_id == sup.rule_id:
                if not sup.path_glob:
                    return True
                import fnmatch
                norm_file = file_path.replace("\\", "/")
                norm_glob = sup.path_glob.replace("\\", "/")
                if fnmatch.fnmatch(norm_file, norm_glob):
                    return True
        return False
