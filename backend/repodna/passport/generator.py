"""Deterministic generator for RepoDNA Repository Passport manifests."""

from __future__ import annotations

import re
import subprocess
from collections import defaultdict
from pathlib import Path
from typing import Any

from repodna.contract.evaluator import ContractEvaluator
from repodna.contract.models import ArchitectureContract
from repodna.passport.models import (
    PASSPORT_SCHEMA_VERSION,
    PASSPORT_SCHEMA_VERSION_V2,
    PassportContractStatus,
    PassportCoverage,
    PassportDependencySummary,
    PassportEntrypoint,
    PassportEvidenceSummary,
    PassportHealth,
    PassportHubModule,
    PassportLanguageItem,
    PassportModuleItem,
    PassportModuleRole,
    PassportRetrievalCapabilities,
    PassportSymbolSummary,
    PassportTruncation,
    RepositoryPassport,
    RepositoryPassportV2,
)
from repodna.schemas.models import AnalysisResult
from repodna.security.validators import sanitize_url_for_display

HEX_COMMIT_SHA_PATTERN = re.compile(r"^[0-9a-fA-F]{7,40}$")


def sanitize_passport_target(target: str, repo_name: str) -> str:
    """Sanitizes target_display for passport manifest so absolute user/home paths and tokens are never leaked."""
    cleaned = sanitize_url_for_display(target) if ("://" in target) else target
    # If absolute Windows or Unix path, normalize to project relative identifier
    if (
        cleaned.startswith("/")
        or (len(cleaned) >= 2 and cleaned[1] == ":")
        or "\\Users\\" in cleaned
        or "/Users/" in cleaned
        or "\\home\\" in cleaned
        or "/home/" in cleaned
        or "/tmp" in cleaned
        or "\\Temp\\" in cleaned
    ):
        return f"./{repo_name}"
    return cleaned


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

    # 11. Git revision provenance check & resolution
    resolved_sha = git_revision.strip()
    provenance_verified = False
    revision_status = "unresolved_symbolic_ref"

    if HEX_COMMIT_SHA_PATTERN.match(resolved_sha):
        provenance_verified = True
        revision_status = "verified_commit_sha"
        resolved_sha = resolved_sha.lower()
    else:
        # Try resolving symbolic ref via git if analysis points to a local git directory
        try:
            target_p = Path(analysis.target_display).resolve()
            if target_p.exists() and (target_p / ".git").exists():
                res = subprocess.run(
                    ["git", "rev-parse", resolved_sha],
                    cwd=target_p,
                    capture_output=True,
                    text=True,
                    timeout=3,
                    check=False,
                )
                if res.returncode == 0 and HEX_COMMIT_SHA_PATTERN.match(res.stdout.strip()):
                    resolved_sha = res.stdout.strip().lower()
                    provenance_verified = True
                    revision_status = "verified_commit_sha"
        except Exception:
            pass

    passport_metadata: dict[str, Any] = {
        "target_display": sanitize_passport_target(analysis.target_display, analysis.repo_name),
    }
    if not provenance_verified:
        passport_metadata["provenance_warning"] = (
            f"Git revision '{git_revision}' was not resolved to an immutable commit SHA; provenance is unverified."
        )

    return RepositoryPassport(
        schema_version=PASSPORT_SCHEMA_VERSION,
        repo_name=analysis.repo_name,
        git_revision=resolved_sha,
        provenance_verified=provenance_verified,
        revision_status=revision_status,
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
        metadata=passport_metadata,
    )


def generate_repository_passport_v2(
    analysis: AnalysisResult,
    git_revision: str = "HEAD",
    contract: ArchitectureContract | None = None,
    max_modules: int = 150,
    indexer: Any = None,
) -> RepositoryPassportV2:
    """Generates an evidence-backed RepositoryPassportV2 manifest from an AnalysisResult and optional SymbolIndexer."""
    v1 = generate_repository_passport(
        analysis=analysis,
        git_revision=git_revision,
        contract=contract,
        max_modules=max_modules,
    )

    # 1. Symbol index summary
    symbol_summary: PassportSymbolSummary | None = None
    verified_refs_count: int | None = None
    candidate_unresolved: dict[str, int] = {}
    evidence_summary: PassportEvidenceSummary | None = None

    if indexer is not None and hasattr(indexer, "_symbols_by_id"):
        verified_refs_count = 0
        symbols = list(indexer._symbols_by_id.values())
        lang_counts: dict[str, int] = defaultdict(int)
        kind_counts: dict[str, int] = defaultdict(int)
        cand_count = 0
        unres_count = 0

        for s in symbols:
            lang_counts[s.language] += 1
            kind_counts[s.kind.value] += 1
            verified_refs_count += len(s.verified_references)
            cand_count += len(s.candidate_references)

        if hasattr(indexer, "_raw_references"):
            unres_count = sum(
                1 for r in indexer._raw_references if getattr(r, "resolution_status", None) == "unresolved"
            )

        candidate_unresolved = {"candidate": cand_count, "unresolved": unres_count}
        symbol_summary = PassportSymbolSummary(
            total_symbols=len(symbols),
            language_counts=dict(lang_counts),
            symbols_by_kind=dict(kind_counts),
            total_verified_references=verified_refs_count,
            total_candidate_references=cand_count,
            total_unresolved_references=unres_count,
        )

        if hasattr(indexer, "ledger") and hasattr(indexer.ledger, "_evidence_by_id"):
            ledger = indexer.ledger
            all_evs = list(ledger._evidence_by_id.values())
            stale_c = sum(1 for e in all_evs if e.is_stale)
            ev_types: dict[str, int] = defaultdict(int)
            for e in all_evs:
                ev_types[e.evidence_type.value] += 1

            evidence_summary = PassportEvidenceSummary(
                total_evidence=len(all_evs),
                fresh_count=len(all_evs) - stale_c,
                stale_count=stale_c,
                evidence_by_type=dict(ev_types),
            )

    # 2. Architectural Entrypoints
    entrypoints: list[PassportEntrypoint] = []
    entrypoint_patterns = ["main", "cli", "app", "server", "worker", "index", "api"]
    for f in analysis.files:
        path_lower = f.id.lower()
        matched_pat = next((p for p in entrypoint_patterns if p in path_lower), None)
        if matched_pat:
            role = "cli" if "cli" in path_lower else "api" if ("api" in path_lower or "app" in path_lower) else matched_pat
            primary_sym = None
            ev_id = None
            if indexer is not None and hasattr(indexer, "find_by_file"):
                file_syms = indexer.find_by_file(f.id)
                if file_syms:
                    top_sym = next((s for s in file_syms if s.is_exported), file_syms[0])
                    primary_sym = top_sym.name
                    ev_id = top_sym.evidence_id
            entrypoints.append(
                PassportEntrypoint(
                    file_path=f.id,
                    role=role,
                    primary_symbol=primary_sym,
                    evidence_id=ev_id,
                    source="ast_verified",
                )
            )
            if len(entrypoints) >= 12:
                break

    # 3. Major Module Roles
    roles: list[PassportModuleRole] = []
    for f in analysis.files:
        path_lower = f.id.lower()
        role_type = "module"
        resp = "Internal service module"
        if "api" in path_lower:
            role_type = "api"
            resp = "HTTP/REST service routes and controllers"
        elif "brain" in path_lower or "retrieval" in path_lower:
            role_type = "brain"
            resp = "Repository code intelligence and symbol retrieval"
        elif "cli" in path_lower:
            role_type = "cli"
            resp = "Terminal command-line interface entrypoints"
        elif "guardian" in path_lower:
            role_type = "guardian"
            resp = "PR architecture gating and change impact analysis"
        elif "contract" in path_lower:
            role_type = "contract"
            resp = "Architecture rules and boundary verification"
        elif "passport" in path_lower:
            role_type = "passport"
            resp = "Repository Passport manifest generation and validation"
        elif "core" in path_lower or "analyzer" in path_lower:
            role_type = "core"
            resp = "Core static AST graph construction and analysis"
        elif f.is_hub:
            role_type = "hub"
            resp = f"High fan-in architectural hub module (fan-in: {f.fan_in})"

        if role_type != "module" or f.is_hub:
            roles.append(
                PassportModuleRole(
                    file_path=f.id,
                    role=role_type,
                    responsibility=resp,
                    source="ast_verified",
                    evidence_id=None,
                )
            )
            if len(roles) >= 15:
                break

    # 4. Analysis limitations
    limitations: list[str] = list(v1.unknown_unverified)
    cov = analysis.transparency
    if cov.partial_static_languages_detected:
        limitations.append(
            f"Languages {cov.partial_static_languages_detected} use partial static extraction. Deep AST edges are unverified."
        )
    if cov.unsupported_languages_detected:
        limitations.append(
            f"Languages {cov.unsupported_languages_detected} have no AST support; only file inventory was analyzed."
        )

    # 5. Retrieval capabilities
    retrieval_caps = PassportRetrievalCapabilities(
        supports_semantic_search=True,
        supports_symbol_resolution=True,
        supports_cross_module_trace=True,
        supports_blast_radius=True,
        token_budgeting=True,
    )

    return RepositoryPassportV2(
        schema_version=PASSPORT_SCHEMA_VERSION_V2,
        repo_name=v1.repo_name,
        git_revision=v1.git_revision,
        provenance_verified=v1.provenance_verified,
        revision_status=v1.revision_status,
        analyzed_at=v1.analyzed_at,
        repodna_version="0.5.0",
        primary_languages=v1.primary_languages,
        ast_coverage=v1.ast_coverage,
        confidence=v1.confidence,
        architectural_hubs=v1.architectural_hubs,
        module_inventory=v1.module_inventory,
        dependency_summary=v1.dependency_summary,
        identified_boundaries=v1.identified_boundaries,
        architecture_health=v1.architecture_health,
        verified_findings=v1.verified_findings,
        unknown_unverified=v1.unknown_unverified,
        contract_status=v1.contract_status,
        evidence_references=v1.evidence_references,
        truncation_metadata=v1.truncation_metadata,
        metadata=v1.metadata,
        symbol_index_summary=symbol_summary,
        architectural_entrypoints=entrypoints,
        major_module_roles=roles,
        verified_reference_counts=verified_refs_count,
        candidate_unresolved_counts=candidate_unresolved,
        evidence_ledger_summary=evidence_summary,
        retrieval_capabilities=retrieval_caps,
        analysis_limitations=limitations,
        source_revision=git_revision,
    )


def export_passport_to_json(passport: RepositoryPassport | RepositoryPassportV2, indent: int = 2) -> str:
    """Serializes passport to formatted JSON."""
    return passport.model_dump_json(indent=indent)


def export_passport_v2_to_json(passport: RepositoryPassportV2, indent: int = 2) -> str:
    """Serializes passport v2 to formatted JSON."""
    return passport.model_dump_json(indent=indent)


def export_passport_to_markdown(passport: RepositoryPassport | RepositoryPassportV2) -> str:
    """Formats passport as an AI-friendly, readable Markdown manifest."""
    h = passport.architecture_health
    cov = passport.ast_coverage
    dep = passport.dependency_summary

    score_str = f"{h.score:.1f}/100 ({h.grade})" if h.score is not None else f"{h.status} ({h.grade})"

    md: list[str] = [
        f"# RepoDNA Repository Passport — `{passport.repo_name}`",
        f"**Revision:** `{passport.git_revision}` | **Analyzed At:** `{passport.analyzed_at.isoformat()}` | **RepoDNA:** `v{passport.repodna_version}` | **Schema:** `v{passport.schema_version}`",
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

    if isinstance(passport, RepositoryPassportV2) and passport.symbol_index_summary:
        sym = passport.symbol_index_summary
        md.append("## Symbol Intelligence (Repository Brain)")
        md.append(f"- **Total Symbols:** {sym.total_symbols:,}")
        md.append(f"- **Verified References:** {sym.total_verified_references:,}")
        md.append(f"- **Candidate References:** {sym.total_candidate_references:,}")
        md.append(f"- **Unresolved References:** {sym.total_unresolved_references:,}")
        if sym.symbols_by_kind:
            kind_str = ", ".join(f"{k}: {v}" for k, v in sorted(sym.symbols_by_kind.items()))
            md.append(f"- **Symbols by Kind:** {kind_str}")
        md.append("")

    if isinstance(passport, RepositoryPassportV2) and passport.architectural_entrypoints:
        md.append("## Architectural Entrypoints")
        md.append("| Entrypoint | Role | Primary Symbol |")
        md.append("| :--- | :--- | :--- |")
        for ep in passport.architectural_entrypoints[:8]:
            md.append(f"| `{ep.file_path}` | `{ep.role}` | `{ep.primary_symbol or '-'}` |")
        md.append("")

    if isinstance(passport, RepositoryPassportV2) and passport.major_module_roles:
        md.append("## Major Module Roles")
        md.append("| Module | Role | Responsibility |")
        md.append("| :--- | :--- | :--- |")
        for mr in passport.major_module_roles[:8]:
            md.append(f"| `{mr.file_path}` | `{mr.role}` | {mr.responsibility} |")
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

