"""Deterministic evaluator for RepoDNA Architecture Contracts against AnalysisResult graphs."""

from __future__ import annotations

from pathlib import Path

import pathspec

from repodna.contract.loader import load_baseline_file
from repodna.contract.models import (
    ArchitectureContract,
    ContractEvaluationReport,
    ContractMode,
    ContractSeverity,
    ContractUnknown,
    ContractViolation,
    UnknownBehavior,
)
from repodna.schemas.models import AnalysisResult, DependencyEdge, FileNode, LanguageSupportLevel


class ContractEvaluator:
    """Evaluates architecture contract policies and rules against an AnalysisResult."""

    def __init__(
        self,
        contract: ArchitectureContract,
        baseline: set[tuple[str, str, str]] | Path | str | None = None,
        mode_override: ContractMode | None = None,
    ) -> None:
        self.contract = contract
        self.mode = mode_override or contract.policy.mode
        self.unknown_behavior = contract.policy.unknown_behavior

        if isinstance(baseline, (Path, str)):
            self.baseline_set = load_baseline_file(baseline)
        elif isinstance(baseline, set):
            self.baseline_set = baseline
        else:
            self.baseline_set = set()

    def evaluate(self, analysis: AnalysisResult) -> ContractEvaluationReport:
        # Outgoing edges grouped by source
        edges_by_source: dict[str, list[DependencyEdge]] = {}
        for edge in analysis.edges:
            edges_by_source.setdefault(edge.source, []).append(edge)

        violations: list[ContractViolation] = []
        unknowns: list[ContractUnknown] = []
        rules_violated_set: set[str] = set()
        rules_passed_set: set[str] = set()
        rules_unmatched_set: set[str] = set()
        rules_unknown_set: set[str] = set()
        rules_evaluated_count = 0

        # Pre-compile specs for all rules
        compiled_from_specs: dict[str, pathspec.PathSpec] = {
            rule.id: pathspec.PathSpec.from_lines("gitignore", rule.from_patterns)
            for rule in self.contract.rules
        }

        # Track all files in repo matched by at least one rule
        all_matched_files: list[FileNode] = [
            f for f in analysis.files
            if any(spec.match_file(f.id) for spec in compiled_from_specs.values())
        ]

        for rule in self.contract.rules:
            rules_evaluated_count += 1
            rule_has_violation = False
            rule_has_unknown = False
            rule_has_full_ast = False

            from_spec = compiled_from_specs[rule.id]
            disallow_spec = (
                pathspec.PathSpec.from_lines("gitignore", rule.disallow_imports)
                if rule.disallow_imports
                else None
            )
            allow_spec = (
                pathspec.PathSpec.from_lines("gitignore", rule.allow_imports)
                if rule.allow_imports is not None
                else None
            )

            # Match files in repository matching 'from'
            matching_files: list[FileNode] = [
                f for f in analysis.files if from_spec.match_file(f.id)
            ]

            if not matching_files:
                rules_unmatched_set.add(rule.id)
                continue

            for file_node in matching_files:
                # 1. Check support level limitations for the source file
                if file_node.support_level == LanguageSupportLevel.UNSUPPORTED:
                    rule_has_unknown = True
                    unknowns.append(
                        ContractUnknown(
                            rule_id=rule.id,
                            rule_title=rule.title,
                            source_file=file_node.id,
                            raw_import="<unsupported_language_ast>",
                            line=1,
                            reason="unsupported_language",
                            detail=f"Source file '{file_node.id}' is in language '{file_node.language}' without AST import resolution support.",
                        )
                    )
                    continue

                if file_node.support_level == LanguageSupportLevel.PARTIAL_STATIC:
                    rule_has_unknown = True
                    unknowns.append(
                        ContractUnknown(
                            rule_id=rule.id,
                            rule_title=rule.title,
                            source_file=file_node.id,
                            raw_import="<partial_static_ast>",
                            line=1,
                            reason="partial_static_language",
                            detail=f"Source file '{file_node.id}' uses regex pattern extraction; complete internal dependency graph is not guaranteed.",
                        )
                    )
                else:
                    rule_has_full_ast = True

                # 2. Check unresolved imports in source file
                for unresolved in file_node.unresolved_imports:
                    # Check if the unresolved import string matches disallow patterns
                    is_suspicious = False
                    if disallow_spec and disallow_spec.match_file(unresolved.raw_import):
                        is_suspicious = True

                    if is_suspicious or unresolved.reason not in ("external_package", "standard_library"):
                        rule_has_unknown = True
                        unknowns.append(
                            ContractUnknown(
                                rule_id=rule.id,
                                rule_title=rule.title,
                                source_file=file_node.id,
                                raw_import=unresolved.raw_import,
                                line=unresolved.line,
                                reason=unresolved.reason,
                                detail=f"Unresolved reference '{unresolved.raw_import}' from '{file_node.id}:{unresolved.line}' could not be verified.",
                            )
                        )

                # 3. Check resolved internal edges originating from file_node
                outgoing_edges = edges_by_source.get(file_node.id, [])
                for edge in outgoing_edges:
                    target_id = edge.target
                    is_violation = False
                    reason_msg = ""

                    # Disallow check
                    if disallow_spec and disallow_spec.match_file(target_id):
                        is_violation = True
                        reason_msg = (
                            f"Module '{file_node.id}' imports '{target_id}', which matches prohibited pattern(s): "
                            f"{rule.disallow_imports}"
                        )

                    # Whitelist (allow_imports) check
                    elif allow_spec is not None and not allow_spec.match_file(target_id):
                        is_violation = True
                        reason_msg = (
                            f"Module '{file_node.id}' imports '{target_id}', which is not in the allowed imports whitelist: "
                            f"{rule.allow_imports}"
                        )

                    if is_violation:
                        rule_has_violation = True
                        rules_violated_set.add(rule.id)
                        is_in_baseline = (rule.id, file_node.id, target_id) in self.baseline_set

                        violations.append(
                            ContractViolation(
                                rule_id=rule.id,
                                rule_title=rule.title,
                                severity=rule.severity,
                                source_file=file_node.id,
                                target_file=target_id,
                                import_names=edge.import_names,
                                line=edge.line,
                                message=reason_msg,
                                remediation=rule.remediation,
                                is_baseline=is_in_baseline,
                            )
                        )

            if rule_has_violation:
                rules_violated_set.add(rule.id)
            elif not rule_has_full_ast:
                # Rule only matched unsupported or partial static files
                rules_unknown_set.add(rule.id)
            elif rule_has_unknown and self.unknown_behavior != UnknownBehavior.IGNORE:
                rules_unknown_set.add(rule.id)
            else:
                rules_passed_set.add(rule.id)

        # Partition violations into new vs baseline
        new_violations = [v for v in violations if not v.is_baseline]
        baseline_violations = [v for v in violations if v.is_baseline]

        # Determine overall verdict
        ast_cov = analysis.transparency.ast_loc_coverage_pct
        all_matched_are_non_full_ast = (
            len(all_matched_files) > 0
            and all(f.support_level != LanguageSupportLevel.FULL_AST for f in all_matched_files)
        )

        if all_matched_are_non_full_ast and not new_violations:
            if self.mode == ContractMode.ENFORCE and self.unknown_behavior == UnknownBehavior.FAIL:
                verdict = "FAIL"
                is_compliant = False
            elif self.unknown_behavior == UnknownBehavior.WARN:
                verdict = "WARNING"
                is_compliant = True
            elif self.unknown_behavior == UnknownBehavior.IGNORE:
                verdict = "PASS"
                is_compliant = True
            else:
                verdict = "INCONCLUSIVE"
                is_compliant = False
        elif (
            analysis.total_files > 0
            and ast_cov < 40.0
            and len(all_matched_files) > 0
            and len(rules_passed_set) == 0
            and len(rules_violated_set) == 0
            and self.unknown_behavior != UnknownBehavior.WARN
        ):
            verdict = "INCONCLUSIVE"
            is_compliant = False
        elif self.mode == ContractMode.ENFORCE:
            # In enforce mode, any new error/warning violation causes FAIL
            enforce_breakers = [v for v in new_violations if v.severity in (ContractSeverity.ERROR, ContractSeverity.WARNING)]
            if enforce_breakers:
                verdict = "FAIL"
                is_compliant = False
            elif self.unknown_behavior == UnknownBehavior.FAIL and unknowns:
                verdict = "FAIL"
                is_compliant = False
            elif unknowns and self.unknown_behavior == UnknownBehavior.WARN:
                verdict = "WARNING"
                is_compliant = True
            elif not rules_passed_set and rules_unknown_set and not new_violations:
                verdict = "INCONCLUSIVE" if self.unknown_behavior != UnknownBehavior.IGNORE else "PASS"
                is_compliant = False if verdict == "INCONCLUSIVE" else True
            elif new_violations:
                verdict = "WARNING"
                is_compliant = True
            else:
                verdict = "PASS"
                is_compliant = True
        else:
            # Advisory mode
            if new_violations:
                verdict = "WARNING"
                is_compliant = False
            elif unknowns and self.unknown_behavior == UnknownBehavior.WARN:
                verdict = "WARNING"
                is_compliant = True
            elif unknowns and self.unknown_behavior == UnknownBehavior.FAIL:
                verdict = "WARNING"
                is_compliant = False
            elif not rules_passed_set and rules_unknown_set and not new_violations:
                verdict = "INCONCLUSIVE" if self.unknown_behavior != UnknownBehavior.IGNORE else "PASS"
                is_compliant = False if verdict == "INCONCLUSIVE" else True
            else:
                verdict = "PASS"
                is_compliant = True

        # Generate summary text
        summary_lines = [
            f"RepoDNA Architecture Contract Evaluation (Mode: {self.mode.value.upper()})",
            f"Verdict: {verdict}",
            f"Rules Evaluated: {rules_evaluated_count} ({len(rules_passed_set)} passed, {len(rules_violated_set)} triggered, {len(rules_unmatched_set)} unmatched, {len(rules_unknown_set)} inconclusive)",
            f"Violations: {len(new_violations)} new, {len(baseline_violations)} existing baseline",
            f"Unknowns / Unverified Evaluations: {len(unknowns)}",
        ]
        if rules_unmatched_set:
            summary_lines.append(f"Unmatched Rules (0 files matched): {', '.join(sorted(rules_unmatched_set))}")
        if rules_unknown_set:
            summary_lines.append(f"Inconclusive / Unknown Rules: {', '.join(sorted(rules_unknown_set))}")

        if new_violations:
            summary_lines.append("\nTop New Violations:")
            for v in new_violations[:5]:
                syms = f" ({', '.join(v.import_names)})" if v.import_names else ""
                summary_lines.append(f"  [{v.severity.value.upper()}] {v.rule_id}: {v.source_file} -> {v.target_file}{syms}")
                if v.remediation:
                    summary_lines.append(f"      Remediation: {v.remediation}")

        if unknowns:
            summary_lines.append(f"\nUnknown / Unverified Notes ({len(unknowns)}):")
            for u in unknowns[:3]:
                summary_lines.append(f"  [{u.rule_id}] {u.source_file}: {u.detail}")

        return ContractEvaluationReport(
            contract_version=self.contract.version,
            mode=self.mode,
            unknown_behavior=self.unknown_behavior,
            total_rules=len(self.contract.rules),
            rules_evaluated=rules_evaluated_count,
            rules_passed=sorted(rules_passed_set),
            rules_violated=sorted(rules_violated_set),
            rules_unmatched=sorted(rules_unmatched_set),
            rules_unknown=sorted(rules_unknown_set),
            violations=violations,
            new_violations=new_violations,
            baseline_violations=baseline_violations,
            unknowns=unknowns,
            is_compliant=is_compliant,
            verdict=verdict,
            summary_text="\n".join(summary_lines),
        )
