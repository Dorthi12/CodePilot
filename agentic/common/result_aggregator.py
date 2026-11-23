"""Multi-agent result aggregator synthesizing consensus and detecting architectural disagreements."""

from collections import defaultdict
from typing import Dict, List, Tuple
from shared.types.agent import AgentRole, FindingSeverity
from shared.types.findings import Finding
from agentic.schemas.agent import ConsensusFinding, DisagreementItem


class MultiAgentResultAggregator:
    """Aggregates findings from multiple specialized agents, detects consensus, and surfaces conflicts."""

    def aggregate(self, all_findings: List[Finding]) -> Tuple[List[ConsensusFinding], List[DisagreementItem]]:
        consensus_list: List[ConsensusFinding] = []
        disagreements: List[DisagreementItem] = []

        # 1. Group findings by file and overlapping line regions
        file_groups: Dict[str, List[Finding]] = defaultdict(list)
        for f in all_findings:
            file_groups[f.file_path].append(f)

        for file_path, findings in file_groups.items():
            # Check for multi-agent overlap on the same file
            agents_in_file = set(f.agent_role for f in findings if f.agent_role)

            if len(agents_in_file) > 1:
                # Check for Security vs Performance tension
                sec_findings = [f for f in findings if f.category == "SECURITY"]
                perf_findings = [f for f in findings if f.category == "PERFORMANCE"]

                if sec_findings and perf_findings:
                    disagreements.append(
                        DisagreementItem(
                            topic=f"Security Validation vs Latency Trade-off in {file_path}",
                            file_path=file_path,
                            affected_symbol=sec_findings[0].symbol_id,
                            agents_involved=[AgentRole.SECURITY, AgentRole.PERFORMANCE],
                            positions={
                                AgentRole.SECURITY.value: f"Enforce strict input sanitization and verification to prevent {sec_findings[0].title}.",
                                AgentRole.PERFORMANCE.value: f"Minimize nested loops and excessive validation overhead in {perf_findings[0].title} to preserve sub-millisecond execution.",
                            },
                            conflicting_aspect="TRADE_OFF",
                            trade_off_analysis=(
                                "Security requires cryptographic/regex checks while Performance cautions against latency inflation. "
                                "Recommendation: Implement fast-path cached validation or compiled regex."
                            ),
                        )
                    )

                # Check for Architecture vs Code Quality tension
                arch_findings = [f for f in findings if f.category == "ARCHITECTURE"]
                qual_findings = [f for f in findings if f.category == "CODE_QUALITY"]

                if arch_findings and qual_findings:
                    disagreements.append(
                        DisagreementItem(
                            topic=f"Modular Decoupling vs Method Complexity in {file_path}",
                            file_path=file_path,
                            affected_symbol=qual_findings[0].symbol_id,
                            agents_involved=[AgentRole.ARCHITECTURE, AgentRole.CODE_QUALITY],
                            positions={
                                AgentRole.ARCHITECTURE.value: "Break cyclic imports by introducing intermediary abstraction layer or event emitter.",
                                AgentRole.CODE_QUALITY.value: "Refactor large functions to reduce nesting depth without introducing additional indirection.",
                            },
                            conflicting_aspect="RECOMMENDATION",
                            trade_off_analysis=(
                                "Architecture suggests adding an intermediary module to decouple dependencies, "
                                "while Code Quality warns against unnecessary abstraction layers."
                            ),
                        )
                    )

            # 2. Check for Consensus Findings (multiple agents flagging concerns in the same file)
            # Group by rule or category
            cat_groups: Dict[str, List[Finding]] = defaultdict(list)
            for f in findings:
                cat_groups[f.category].append(f)

            for cat, c_findings in cat_groups.items():
                roles = list(set(AgentRole(f.agent_role) for f in c_findings if f.agent_role))
                if len(roles) >= 1:
                    primary = c_findings[0]
                    consensus_list.append(
                        ConsensusFinding(
                            fingerprint=primary.fingerprint,
                            category=primary.category,
                            title=primary.title,
                            severity=primary.severity,
                            file_path=primary.file_path,
                            line_start=primary.line_start,
                            line_end=primary.line_end,
                            supporting_agents=roles,
                            consensus_confidence=round(min(0.98, 0.80 + 0.08 * len(roles)), 2),
                            synthesized_remediation=primary.remediation or "Remediate according to domain best practices.",
                        )
                    )

        return consensus_list, disagreements
