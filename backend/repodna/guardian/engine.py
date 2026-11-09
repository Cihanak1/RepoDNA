"""PR Architecture Guardian Engine — Continuous architectural regression assessment for Pull Requests."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from repodna.contract.evaluator import ContractEvaluator
from repodna.contract.loader import load_baseline_file
from repodna.contract.models import (
    ArchitectureContract,
    ContractMode,
    ContractSeverity,
    ContractViolation,
)
from repodna.diff.engine import ArchitectureDiffEngine
from repodna.guardian.models import (
    GuardianReport,
    GuardianVerdict,
    RiskAssessment,
    RiskLevel,
)
from repodna.schemas.models import AnalysisResult


class PRArchitectureGuardian:
    """Evaluates architectural drift, circular regressions, and contract policies between Git revisions."""

    def __init__(
        self,
        contract: ArchitectureContract | None = None,
        baseline: set[tuple[str, str, str]] | Path | str | None = None,
        mode_override: ContractMode | None = None,
    ) -> None:
        self.contract = contract
        self.mode_override = mode_override

        if isinstance(baseline, (Path, str)):
            self.baseline_set = load_baseline_file(baseline)
        elif isinstance(baseline, set):
            self.baseline_set = baseline
        else:
            self.baseline_set = set()

    def assess(
        self,
        base_analysis: AnalysisResult,
        head_analysis: AnalysisResult,
        base_ref: str = "base",
        head_ref: str = "head",
        base_commit_sha: str | None = None,
        head_commit_sha: str | None = None,
        base_is_working_tree: bool = False,
        head_is_working_tree: bool = False,
        git_renames: dict[str, str] | None = None,
    ) -> GuardianReport:
        # 1. Compute foundational architecture diff
        diff_engine = ArchitectureDiffEngine()
        diff_res = diff_engine.compare_analyses(
            base=base_analysis,
            head=head_analysis,
            base_ref=base_ref,
            head_ref=head_ref,
            base_commit_sha=base_commit_sha,
            head_commit_sha=head_commit_sha,
            base_is_working_tree=base_is_working_tree,
            head_is_working_tree=head_is_working_tree,
            git_renames=git_renames,
        )

        effective_mode = (
            self.mode_override
            or (self.contract.policy.mode if self.contract else ContractMode.ADVISORY)
        )

        # 2. Evaluate Architecture Contract if available
        base_contract_rep = None
        head_contract_rep = None
        new_violations: list[ContractViolation] = []
        resolved_violations: list[ContractViolation] = []
        existing_violations: list[ContractViolation] = []
        unknown_evals = []

        if self.contract:
            evaluator = ContractEvaluator(
                contract=self.contract,
                baseline=self.baseline_set,
                mode_override=effective_mode,
            )
            base_contract_rep = evaluator.evaluate(base_analysis)
            head_contract_rep = evaluator.evaluate(head_analysis)

            base_viol_map = {
                (v.rule_id, v.source_file, v.target_file): v for v in base_contract_rep.violations
            }
            head_viol_map = {
                (v.rule_id, v.source_file, v.target_file): v for v in head_contract_rep.violations
            }

            for key, v in head_viol_map.items():
                if key in base_viol_map or key in self.baseline_set:
                    existing_violations.append(
                        v.model_copy(update={"is_baseline": True})
                    )
                else:
                    new_violations.append(v)

            for key, v in base_viol_map.items():
                if key not in head_viol_map:
                    resolved_violations.append(v)

            unknown_evals = head_contract_rep.unknowns

        # 3. Deterministic Risk Assessment Calculation
        risk_score = 0.0
        risk_factors: list[str] = []
        mitigation_advice: list[str] = []

        # Factor A: New circular dependencies
        new_cycles_count = len(diff_res.cycle_changes.new_cycles)
        if new_cycles_count > 0:
            cycle_pts = min(60.0, new_cycles_count * 30.0)
            risk_score += cycle_pts
            risk_factors.append(f"{new_cycles_count} new circular dependency loop(s) introduced (+{cycle_pts:.0f} pts).")
            mitigation_advice.append("Break circular dependency loops using dependency inversion or event messaging.")

        # Factor B: Contract violations
        if new_violations:
            err_count = sum(1 for v in new_violations if v.severity == ContractSeverity.ERROR)
            warn_count = sum(1 for v in new_violations if v.severity == ContractSeverity.WARNING)

            if effective_mode == ContractMode.ENFORCE:
                viol_pts = min(50.0, err_count * 25.0 + warn_count * 15.0)
                risk_factors.append(f"{len(new_violations)} new enforced contract violation(s) (+{viol_pts:.0f} pts).")
            else:
                viol_pts = min(25.0, err_count * 10.0 + warn_count * 5.0)
                risk_factors.append(f"{len(new_violations)} new advisory contract violation(s) (+{viol_pts:.0f} pts).")

            risk_score += viol_pts
            mitigation_advice.append("Align imported module paths with declared boundaries in .repodna/architecture.yml.")

        # Factor C: Coupling spikes on architectural hubs
        hub_ids = {f.id for f in head_analysis.files if f.is_hub}
        hub_deltas = [c for c in diff_res.significant_coupling_deltas if c.file_id in hub_ids]
        if hub_deltas:
            hub_pts = min(20.0, len(hub_deltas) * 10.0)
            risk_score += hub_pts
            risk_factors.append(f"{len(hub_deltas)} architectural hub module(s) experienced significant coupling surge (+{hub_pts:.0f} pts).")
            mitigation_advice.append("Check if architectural hubs are becoming god objects or excessive dependencies.")

        # Factor D: Health score degradation
        if diff_res.health_delta.score_delta is not None and diff_res.health_delta.score_delta < -2.0:
            degrade = abs(diff_res.health_delta.score_delta)
            degrade_pts = min(20.0, degrade * 2.5)
            risk_score += degrade_pts
            risk_factors.append(f"Repository architectural health degraded by {degrade:.1f} pts (+{degrade_pts:.0f} pts).")

        # Clamp risk score
        risk_score = round(min(100.0, max(0.0, risk_score)), 1)
        if risk_score <= 15.0:
            risk_level = RiskLevel.LOW
        elif risk_score <= 40.0:
            risk_level = RiskLevel.MODERATE
        elif risk_score <= 70.0:
            risk_level = RiskLevel.HIGH
        else:
            risk_level = RiskLevel.CRITICAL

        if not risk_factors:
            risk_factors.append("No architectural regression indicators detected.")

        assessment = RiskAssessment(
            risk_score=risk_score,
            risk_level=risk_level,
            risk_factors=risk_factors,
            mitigation_advice=mitigation_advice,
        )

        # 4. Synthesize Guardian Verdict
        base_ast_loc = base_analysis.transparency.ast_loc_coverage_pct
        head_ast_loc = head_analysis.transparency.ast_loc_coverage_pct
        head_truncated = head_analysis.transparency.truncated_by_limits

        if head_analysis.total_files == 0:
            verdict = GuardianVerdict.INCONCLUSIVE
            verdict_reason = "Head revision contains 0 analyzable files; architecture verdict cannot be evaluated."
        elif head_truncated:
            verdict = GuardianVerdict.INCONCLUSIVE
            verdict_reason = "Head revision exceeded scan bounds/limits; analysis is incomplete."
        elif head_ast_loc < 35.0 and len(head_analysis.files) > 10 and (base_ast_loc - head_ast_loc > 20.0):
            verdict = GuardianVerdict.INCONCLUSIVE
            verdict_reason = f"Severe AST coverage collapse detected ({base_ast_loc:.1f}% -> {head_ast_loc:.1f}% LOC); changes cannot be evaluated with architectural certainty."
        elif new_cycles_count > 0:
            verdict = GuardianVerdict.FAIL
            verdict_reason = f"{new_cycles_count} new circular dependency loop(s) detected in PR."
        elif effective_mode == ContractMode.ENFORCE and any(v.severity in (ContractSeverity.ERROR, ContractSeverity.WARNING) for v in new_violations):
            verdict = GuardianVerdict.FAIL
            verdict_reason = f"{len(new_violations)} new contract violation(s) violate enforced architecture policy."
        elif new_violations or (diff_res.health_delta.score_delta is not None and diff_res.health_delta.score_delta < -3.0):
            verdict = GuardianVerdict.WARNING
            verdict_reason = "Advisory architecture violations or health score degradation detected."
        elif unknown_evals and self.contract and self.contract.policy.unknown_behavior.value == "warn":
            verdict = GuardianVerdict.WARNING
            verdict_reason = f"{len(unknown_evals)} rule evaluation(s) could not be verified due to unresolvable paths or unsupported AST."
        else:
            verdict = GuardianVerdict.PASS
            verdict_reason = "Architecture clean: no new circular dependencies or enforced contract violations detected."

        # 5. Determine Policy Gate and CI Exit Code
        if effective_mode == ContractMode.ENFORCE:
            if verdict == GuardianVerdict.FAIL:
                should_block_ci = True
                exit_code = 1
            elif verdict == GuardianVerdict.INCONCLUSIVE:
                should_block_ci = False
                exit_code = 2
            else:
                should_block_ci = False
                exit_code = 0
        else:
            # Advisory mode: Informational only, never fail CI
            should_block_ci = False
            exit_code = 0

        # 6. Build Markdown Summary
        summary_md = _build_guardian_markdown(
            base_ref=base_ref,
            head_ref=head_ref,
            verdict=verdict,
            verdict_reason=verdict_reason,
            risk=assessment,
            diff=diff_res,
            mode=effective_mode,
            new_violations=new_violations,
            resolved_violations=resolved_violations,
            existing_violations=existing_violations,
            unknown_evals=unknown_evals,
            should_block_ci=should_block_ci,
        )

        return GuardianReport(
            generated_at=datetime.now(UTC),
            base_provenance=diff_res.base_provenance,
            head_provenance=diff_res.head_provenance,
            verdict=verdict,
            verdict_reason=verdict_reason,
            risk_assessment=assessment,
            mode=effective_mode,
            should_block_ci=should_block_ci,
            exit_code=exit_code,
            added_modules=diff_res.module_changes.added,
            removed_modules=diff_res.module_changes.removed,
            renamed_modules=diff_res.module_changes.renamed,
            added_edges=diff_res.dependency_changes.added_edges,
            removed_edges=diff_res.dependency_changes.removed_edges,
            new_cycles=diff_res.cycle_changes.new_cycles,
            resolved_cycles=diff_res.cycle_changes.resolved_cycles,
            persisting_cycles_count=diff_res.cycle_changes.persisting_cycles,
            contract_evaluated=self.contract is not None,
            contract_version=self.contract.version if self.contract else None,
            new_contract_violations=new_violations,
            resolved_contract_violations=resolved_violations,
            existing_baseline_violations=existing_violations,
            unknown_evaluations=unknown_evals,
            base_contract_report=base_contract_rep,
            head_contract_report=head_contract_rep,
            coupling_deltas=diff_res.significant_coupling_deltas,
            health_delta=diff_res.health_delta,
            coverage_delta=diff_res.coverage_delta,
            diff_summary=diff_res.summary_text,
            summary_markdown=summary_md,
        )


def _build_guardian_markdown(
    base_ref: str,
    head_ref: str,
    verdict: GuardianVerdict,
    verdict_reason: str,
    risk: RiskAssessment,
    diff: Any,
    mode: ContractMode,
    new_violations: list[ContractViolation],
    resolved_violations: list[ContractViolation],
    existing_violations: list[ContractViolation],
    unknown_evals: list[Any],
    should_block_ci: bool = False,
) -> str:
    icon = {
        GuardianVerdict.PASS: "PASS",
        GuardianVerdict.WARNING: "WARNING",
        GuardianVerdict.FAIL: "FAIL",
        GuardianVerdict.INCONCLUSIVE: "INCONCLUSIVE",
    }[verdict]

    ci_status = "**CI Status:** `BLOCK (exit 1)`" if should_block_ci else (
        "**CI Status:** `INCONCLUSIVE (exit 2)`" if (mode == ContractMode.ENFORCE and verdict == GuardianVerdict.INCONCLUSIVE)
        else "**CI Status:** `PASS/ADVISORY (exit 0)`"
    )

    md: list[str] = [
        f"## RepoDNA Architecture Guardian — `{icon}`",
        "",
        f"**Revision:** `{base_ref}` → `{head_ref}` | **Policy Mode:** `{mode.value.upper()}` | {ci_status} | **Risk:** `{risk.risk_level.value}` ({risk.risk_score:.0f}/100)",
        f"> {verdict_reason}",
        "",
        "| Metric | Base | Head | Delta |",
        "| :--- | :--- | :--- | :--- |",
    ]

    # Health row
    b_score = f"{diff.health_delta.score_before:.1f}" if diff.health_delta.score_before is not None else "N/A"
    h_score = f"{diff.health_delta.score_after:.1f}" if diff.health_delta.score_after is not None else "N/A"
    d_score = (
        f"{diff.health_delta.score_delta:+.1f}" if diff.health_delta.score_delta is not None else "—"
    )
    md.append(f"| **Architecture Health** | {b_score} ({diff.health_delta.grade_before}) | {h_score} ({diff.health_delta.grade_after}) | **{d_score}** |")

    # Cycles row
    b_cyc = len(diff.cycle_changes.resolved_cycles) + diff.cycle_changes.persisting_cycles
    h_cyc = len(diff.cycle_changes.new_cycles) + diff.cycle_changes.persisting_cycles
    md.append(f"| **Circular Dependencies** | {b_cyc} cycles | {h_cyc} cycles | **+{len(diff.cycle_changes.new_cycles)} new**, -{len(diff.cycle_changes.resolved_cycles)} resolved |")

    # Contract violations row
    md.append(f"| **Contract Violations** | {len(existing_violations) + len(resolved_violations)} | {len(existing_violations) + len(new_violations)} | **+{len(new_violations)} new**, -{len(resolved_violations)} fixed ({len(existing_violations)} baseline) |")

    # Modules row
    md.append(f"| **Repository Modules** | {diff.base_provenance.total_files} | {diff.head_provenance.total_files} | +{len(diff.module_changes.added)}, -{len(diff.module_changes.removed)}, {len(diff.module_changes.renamed)} renamed |")

    # Coverage row
    b_cov = f"{diff.coverage_delta.ast_loc_coverage_before:.1f}%"
    h_cov = f"{diff.coverage_delta.ast_loc_coverage_after:.1f}%"
    d_cov = f"{diff.coverage_delta.ast_loc_coverage_delta:+.1f}%"
    md.append(f"| **AST LOC Coverage** | {b_cov} | {h_cov} | {d_cov} |")

    md.append("")

    if diff.cycle_changes.new_cycles:
        md.append("### Regressive Circular Dependencies (New in PR)")
        for c in diff.cycle_changes.new_cycles:
            md.append(f"- **[{c.id}]** ({c.length} hops): `{' -> '.join(c.nodes)}`")
        md.append("")

    if new_violations:
        md.append("### New Architectural Contract Violations")
        for v in new_violations:
            syms = f" (`{', '.join(v.import_names)}`)" if v.import_names else ""
            md.append(f"- **[{v.severity.value.upper()}] `{v.rule_id}`** — {v.source_file}:{v.line} -> `{v.target_file}`{syms}")
            md.append(f"  - *Reason:* {v.message}")
            if v.remediation:
                md.append(f"  - *Fix:* {v.remediation}")
        md.append("")

    if resolved_violations or diff.cycle_changes.resolved_cycles:
        md.append("### Architectural Improvements")
        if diff.cycle_changes.resolved_cycles:
            md.append(f"- Resolved **{len(diff.cycle_changes.resolved_cycles)}** circular dependency loop(s).")
        if resolved_violations:
            md.append(f"- Fixed **{len(resolved_violations)}** pre-existing contract violation(s).")
        md.append("")

    if unknown_evals:
        md.append(f"<details><summary>Unverified Unknown Evaluations ({len(unknown_evals)})</summary>\n")
        for u in unknown_evals[:10]:
            md.append(f"- `{u.rule_id}` at `{u.source_file}:{u.line}`: {u.detail}")
        md.append("\n</details>\n")

    return "\n".join(md)
