"""Migration utility for upgrading RepoDNA Repository Passport manifests from v1 to v2."""

from __future__ import annotations

from typing import Any

from repodna.passport.models import (
    PASSPORT_SCHEMA_VERSION_V2,
    PassportEntrypoint,
    PassportModuleRole,
    PassportRetrievalCapabilities,
    RepositoryPassport,
    RepositoryPassportV2,
)


def migrate_v1_to_v2(passport_v1: RepositoryPassport | dict[str, Any]) -> RepositoryPassportV2:
    """
    Migrates a v1.0 RepositoryPassport instance or dictionary into a schema-compliant
    v2.0 RepositoryPassportV2 object with backwards-compatible defaults.
    """
    if isinstance(passport_v1, dict):
        # If it's already v2, parse directly
        if passport_v1.get("schema_version") == PASSPORT_SCHEMA_VERSION_V2:
            return RepositoryPassportV2.model_validate(passport_v1)
        p1 = RepositoryPassport.model_validate(passport_v1)
    else:
        p1 = passport_v1

    # Derive entrypoints from module inventory
    entrypoint_patterns = ["main", "cli", "app", "server", "worker", "index", "api"]
    entrypoints: list[PassportEntrypoint] = []
    for m in p1.module_inventory:
        p_low = m.id.lower()
        matched_pat = next((p for p in entrypoint_patterns if p in p_low), None)
        if matched_pat:
            role = "cli" if "cli" in p_low else "api" if ("api" in p_low or "app" in p_low) else matched_pat
            entrypoints.append(
                PassportEntrypoint(
                    file_path=m.id,
                    role=role,
                    primary_symbol=None,
                    evidence_id=None,
                )
            )
            if len(entrypoints) >= 10:
                break

    # Derive major module roles
    roles: list[PassportModuleRole] = []
    for h in p1.architectural_hubs:
        roles.append(
            PassportModuleRole(
                file_path=h.file_id,
                role="hub",
                responsibility=f"Architectural hub module with high fan-in ({h.fan_in})",
            )
        )
    for m in p1.module_inventory:
        if any(r.file_path == m.id for r in roles):
            continue
        p_low = m.id.lower()
        role_type = "module"
        resp = "Internal service module"
        if "api" in p_low:
            role_type = "api"
            resp = "HTTP/REST service routes and controllers"
        elif "brain" in p_low:
            role_type = "brain"
            resp = "Repository code intelligence and symbol retrieval"
        elif "cli" in p_low:
            role_type = "cli"
            resp = "Terminal command-line interface entrypoints"
        elif "guardian" in p_low:
            role_type = "guardian"
            resp = "PR architecture gating and change impact analysis"
        elif "contract" in p_low:
            role_type = "contract"
            resp = "Architecture rules and boundary verification"
        elif "core" in p_low:
            role_type = "core"
            resp = "Core static AST graph construction and analysis"

        if role_type != "module":
            roles.append(
                PassportModuleRole(
                    file_path=m.id,
                    role=role_type,
                    responsibility=resp,
                )
            )
            if len(roles) >= 12:
                break

    retrieval_caps = PassportRetrievalCapabilities(
        supports_semantic_search=True,
        supports_symbol_resolution=True,
        supports_cross_module_trace=True,
        supports_blast_radius=True,
        token_budgeting=True,
    )

    return RepositoryPassportV2(
        schema_version=PASSPORT_SCHEMA_VERSION_V2,
        repo_name=p1.repo_name,
        git_revision=p1.git_revision,
        provenance_verified=p1.provenance_verified,
        revision_status=p1.revision_status,
        analyzed_at=p1.analyzed_at,
        repodna_version="0.5.0",
        primary_languages=p1.primary_languages,
        ast_coverage=p1.ast_coverage,
        confidence=p1.confidence,
        architectural_hubs=p1.architectural_hubs,
        module_inventory=p1.module_inventory,
        dependency_summary=p1.dependency_summary,
        identified_boundaries=p1.identified_boundaries,
        architecture_health=p1.architecture_health,
        verified_findings=p1.verified_findings,
        unknown_unverified=p1.unknown_unverified,
        contract_status=p1.contract_status,
        evidence_references=p1.evidence_references,
        truncation_metadata=p1.truncation_metadata,
        metadata=p1.metadata,
        symbol_index_summary=None,
        architectural_entrypoints=entrypoints,
        major_module_roles=roles,
        verified_reference_counts=0,
        candidate_unresolved_counts={"candidate": 0, "unresolved": 0},
        evidence_ledger_summary=None,
        retrieval_capabilities=retrieval_caps,
        analysis_limitations=list(p1.unknown_unverified),
        source_revision=p1.git_revision,
    )
