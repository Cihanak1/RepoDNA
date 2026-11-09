"""Deterministic generator for RepoDNA Repository Passport manifests."""

from __future__ import annotations

from repodna.contract.evaluator import ContractEvaluator
from repodna.contract.models import ArchitectureContract
from repodna.passport.models import (
    PASSPORT_SCHEMA_VERSION,
    PassportContractStatus,
    PassportCoverage,
    PassportDependencySummary,
    PassportHealth,
    PassportHubModule,
    PassportLanguageItem,
    PassportModuleItem,
    PassportTruncation,
    RepositoryPassport,
)
from repodna.schemas.models import AnalysisResult


def generate_repository_passport(
    analysis: AnalysisResult,
    git_revision: str = "HEAD",
    contract: ArchitectureContract | None = None,
    max_modules: int = 150,
) -> RepositoryPassport:
    """Generates an evidence-backed RepositoryPassport from an AnalysisResult."""
    # 1. Primary languages
    lang_items = [
        PassportLanguageItem(
            language=lg.language,
            support_level=lg.support_level.value,
            file_count=lg.file_count,
            lines_code=lg.lines_code,
            percentage=round(lg.percentage_of_code, 1),
        )
        for lg in analysis.languages
    ]

    # 2. Coverage
    tr = analysis.transparency
    coverage = PassportCoverage(
        ast_file_coverage_pct=tr.ast_file_coverage_pct,
        ast_loc_coverage_pct=tr.ast_loc_coverage_pct,
        supported_languages=tr.supported_languages_detected,
        partial_static_languages=tr.partial_static_languages_detected,
        unsupported_languages=tr.unsupported_languages_detected,
    )

    # 3. Architectural hubs
    hubs = [
        PassportHubModule(
            file_id=f.id,
            fan_in=f.fan_in,
            fan_out=f.fan_out,
            instability=f.instability,
            is_hub=True,
        )
        for f in analysis.files
        if f.is_hub
    ]
    # Sort hubs by fan_in descending
    hubs.sort(key=lambda h: (h.fan_in, -h.instability), reverse=True)

    # 4. Module inventory (capped by max_modules)
    # Priority sorting: hubs first, then in_cycle, then lines_code descending
    sorted_files = sorted(
        analysis.files,
        key=lambda f: (f.is_hub, f.in_cycle, f.lines_code),
        reverse=True,
    )

    total_files_count = len(sorted_files)
    effective_cap = max(1, min(max_modules, 5000))
    is_truncated = total_files_count > effective_cap
    selected_files = sorted_files[:effective_cap]

    inventory = [
        PassportModuleItem(
            id=f.id,
            language=f.language,
            lines_code=f.lines_code,
            fan_in=f.fan_in,
            fan_out=f.fan_out,
            instability=f.instability,
            in_cycle=f.in_cycle,
            is_hub=f.is_hub,
        )
        for f in selected_files
    ]

    truncation = PassportTruncation(
        is_truncated=is_truncated,
        total_inventory_count=total_files_count,
        returned_inventory_count=len(inventory),
        reason=f"Capped at {effective_cap} modules for context optimization." if is_truncated else None,
    )

    # 5. Dependency summary
    gm = analysis.graph_metrics
    dep_summary = PassportDependencySummary(
        total_modules=gm.total_nodes,
        total_internal_edges=gm.total_edges,
        cycle_count=gm.cycle_count,
        cyclic_scc_count=gm.scc_count,
        orphan_modules_count=gm.orphan_files_count,
        hub_modules_count=len(hubs),
        average_instability=gm.average_instability,
    )

    # 6. Identified boundaries (top-level folders and packages)
    top_dirs: set[str] = set()
    for f in analysis.files:
        parts = f.id.split("/")
        if len(parts) > 1:
            top_dirs.add(parts[0])
    identified_boundaries = sorted(top_dirs)

    # 7. Health
    hr = analysis.health_report
    health = PassportHealth(
        score=hr.overall_score,
        grade=hr.grade,
        status=hr.status,
        confidence=hr.confidence,
        confidence_reason=hr.confidence_reason,
    )

    # 8. Verified findings & unverified rules
    verified_findings = [
        f"[{fnd.rule_id}] {fnd.title} ({fnd.severity.value.upper()}) affected: {', '.join(fnd.affected_files[:2])}"
        for fnd in hr.findings
    ]
    unverified_rules = list(hr.unverified_rules)

    # 9. Contract status
    if contract:
        eval_report = ContractEvaluator(contract).evaluate(analysis)
        contract_status = PassportContractStatus(
            has_contract=True,
            contract_version=contract.version,
            mode=contract.policy.mode.value,
            rules_count=len(contract.rules),
            is_compliant=eval_report.is_compliant,
            active_violations_count=len(eval_report.new_violations),
        )
    else:
        contract_status = PassportContractStatus(
            has_contract=False,
            rules_count=0,
            is_compliant=None,
            active_violations_count=0,
        )

    # 10. Key evidence traces
    evidence_refs: list[str] = []
    for c in analysis.cycles[:3]:
        evidence_refs.append(f"Cycle [{c.id}]: {' -> '.join(c.nodes)}")
    for fnd in hr.findings[:3]:
        if fnd.evidence:
            evidence_refs.append(f"Finding [{fnd.rule_id}]: {fnd.evidence[0]}")

    return RepositoryPassport(
        schema_version=PASSPORT_SCHEMA_VERSION,
        repo_name=analysis.repo_name,
        git_revision=git_revision,
        analyzed_at=analysis.analyzed_at,
        repodna_version="0.4.0",
        primary_languages=lang_items,
        ast_coverage=coverage,
        confidence=hr.confidence,
        architectural_hubs=hubs,
        module_inventory=inventory,
        dependency_summary=dep_summary,
        identified_boundaries=identified_boundaries,
        architecture_health=health,
        verified_findings=verified_findings,
        unknown_unverified=unverified_rules,
        contract_status=contract_status,
        evidence_references=evidence_refs,
        truncation_metadata=truncation,
        metadata={"target_display": analysis.target_display},
    )


def export_passport_to_json(passport: RepositoryPassport, indent: int = 2) -> str:
    """Serializes passport to formatted JSON."""
    return passport.model_dump_json(indent=indent)


def export_passport_to_markdown(passport: RepositoryPassport) -> str:
    """Formats passport as an AI-friendly, readable Markdown manifest."""
    h = passport.architecture_health
    cov = passport.ast_coverage
    dep = passport.dependency_summary

    score_str = f"{h.score:.1f}/100 ({h.grade})" if h.score is not None else f"{h.status} ({h.grade})"

    md: list[str] = [
        f"# RepoDNA Repository Passport — `{passport.repo_name}`",
        f"**Revision:** `{passport.git_revision}` | **Analyzed At:** `{passport.analyzed_at.isoformat()}` | **RepoDNA:** `v{passport.repodna_version}`",
        "",
        "## Architectural Vitals",
        f"- **Health:** {score_str} (Confidence: **{passport.confidence.upper()}**)",
        f"- **AST Coverage:** {cov.ast_loc_coverage_pct:.1f}% LOC ({cov.ast_file_coverage_pct:.1f}% files)",
        f"- **Component Scope:** {dep.total_modules} modules, {dep.total_internal_edges} internal edges, {dep.cycle_count} cycles",
        f"- **Boundaries Detected:** {', '.join(passport.identified_boundaries) or 'None'}",
        "",
        "## Primary Languages",
        "| Language | Support Level | Files | LOC | Code % |",
        "| :--- | :--- | :--- | :--- | :--- |",
    ]
    for lg in passport.primary_languages:
        md.append(f"| {lg.language} | `{lg.support_level}` | {lg.file_count} | {lg.lines_code:,} | {lg.percentage:.1f}% |")

    md.append("")
    md.append("## Architectural Hubs (High Fan-In / Impact)")
    if passport.architectural_hubs:
        md.append("| Module | Fan-In (Dependents) | Fan-Out | Instability |")
        md.append("| :--- | :--- | :--- | :--- |")
        for hub in passport.architectural_hubs[:8]:
            md.append(f"| `{hub.file_id}` | {hub.fan_in} | {hub.fan_out} | {hub.instability:.2f} |")
    else:
        md.append("- No architectural hub bottlenecks detected.")
    md.append("")

    if passport.contract_status.has_contract:
        c = passport.contract_status
        status = "COMPLIANT" if c.is_compliant else f"VIOLATIONS ({c.active_violations_count})"
        md.append(f"## Architecture Contract Status: `{status}`")
        md.append(f"- Rules defined: {c.rules_count} (Mode: `{c.mode}`)")
        md.append("")

    if passport.verified_findings:
        md.append(f"## Verified Architecture Findings ({len(passport.verified_findings)})")
        for vf in passport.verified_findings[:5]:
            md.append(f"- {vf}")
        md.append("")

    if passport.unknown_unverified:
        md.append(f"## Unverified Rules / Limitations ({len(passport.unknown_unverified)})")
        for ur in passport.unknown_unverified:
            md.append(f"- {ur}")
        md.append("")

    return "\n".join(md)
