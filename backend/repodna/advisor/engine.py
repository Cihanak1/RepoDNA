"""Refactoring Advisor Engine for RepoDNA.

Produces deterministic, evidence-based architectural refactoring advice across four categories:
1. Circular dependency reduction
2. High coupling module review
3. Layer boundary improvement
4. Oversized architectural hub review
"""

from __future__ import annotations

import hashlib
from typing import TYPE_CHECKING

from repodna.advisor.models import (
    AdvisorCategory,
    RefactoringAdvisorReport,
    RefactoringRecommendation,
)
from repodna.schemas.models import AnalysisResult, DependencyEdge, FileNode

if TYPE_CHECKING:
    from repodna.contract.models import ArchitectureContract


class RefactoringAdvisorEngine:
    """Deterministic, evidence-grounded architectural refactoring advisor."""

    def __init__(
        self,
        analysis: AnalysisResult,
        contract: ArchitectureContract | None = None,
    ) -> None:
        self.analysis = analysis
        self.contract = contract
        self.file_map: dict[str, FileNode] = {f.id: f for f in analysis.files}
        self.edge_map: dict[tuple[str, str], list[DependencyEdge]] = {}
        for edge in analysis.edges:
            pair = (edge.source, edge.target)
            self.edge_map.setdefault(pair, []).append(edge)

    def generate_report(
        self,
        category_filter: AdvisorCategory | None = None,
        min_severity: str | None = None,
    ) -> RefactoringAdvisorReport:
        """Generates comprehensive, deduplicated refactoring advice."""
        recommendations: list[RefactoringRecommendation] = []

        # 1. Circular dependency reduction
        recs_cycle = self._analyze_circular_dependencies()
        recommendations.extend(recs_cycle)

        # 2. High coupling module review
        recs_coupling = self._analyze_high_coupling()
        recommendations.extend(recs_coupling)

        # 3. Layer boundary improvement
        recs_layer = self._analyze_layer_boundaries()
        recommendations.extend(recs_layer)

        # 4. Oversized architectural hub review
        recs_hub = self._analyze_oversized_hubs()
        recommendations.extend(recs_hub)

        # Deduplicate
        deduped = self._deduplicate_recommendations(recommendations)

        # Filter
        filtered = self._apply_filters(deduped, category_filter, min_severity)

        # Sort: critical -> high -> medium -> low
        severity_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
        filtered.sort(
            key=lambda r: (
                severity_order.get(r.severity, 4),
                r.category.value,
                r.target_module,
            )
        )

        by_cat: dict[str, int] = {cat.value: 0 for cat in AdvisorCategory}
        by_sev: dict[str, int] = {"critical": 0, "high": 0, "medium": 0, "low": 0}

        for r in filtered:
            by_cat[r.category.value] = by_cat.get(r.category.value, 0) + 1
            by_sev[r.severity] = by_sev.get(r.severity, 0) + 1

        summary = self._format_summary(filtered, by_cat, by_sev)

        repo_ident = (
            self.analysis.git_insights.snapshot_identity
            if self.analysis.git_insights and self.analysis.git_insights.snapshot_identity
            else self.analysis.target_display
        )

        return RefactoringAdvisorReport(
            schema_version="1.0.0",
            repo_identity=repo_ident,
            total_recommendations=len(filtered),
            total_modules_analyzed=len(self.analysis.files),
            by_category=by_cat,
            by_severity=by_sev,
            recommendations=filtered,
            summary_text=summary,
        )

    # -------------------------------------------------------------------------
    # Category 1: Circular Dependency Reduction
    # -------------------------------------------------------------------------
    def _analyze_circular_dependencies(self) -> list[RefactoringRecommendation]:
        recs: list[RefactoringRecommendation] = []
        revision = (
            self.analysis.git_insights.commit_sha
            if self.analysis.git_insights and self.analysis.git_insights.commit_sha
            else "WORKING_TREE"
        )

        for cycle in self.analysis.cycles:
            nodes = cycle.nodes
            if not nodes:
                continue

            unique_nodes: list[str] = []
            for n in nodes:
                if n not in unique_nodes:
                    unique_nodes.append(n)

            if len(unique_nodes) < 2:
                continue

            # Identify candidate edge to break: find the edge with highest instability or lowest symbol count
            best_break_source = unique_nodes[0]
            best_break_target = unique_nodes[1]
            min_weight = 999999

            for i in range(len(unique_nodes)):
                src = unique_nodes[i]
                tgt = unique_nodes[(i + 1) % len(unique_nodes)]
                edges = self.edge_map.get((src, tgt), [])
                import_count = sum(len(e.import_names) for e in edges) if edges else 1
                src_node = self.file_map.get(src)
                tgt_node = self.file_map.get(tgt)

                # Prioritize edges where target is unstable or import surface is small
                weight = import_count * 10
                if tgt_node:
                    weight -= int(tgt_node.instability * 5)
                if src_node and src_node.is_hub:
                    weight += 20  # Don't break at the hub if possible

                if weight < min_weight:
                    min_weight = weight
                    best_break_source = src
                    best_break_target = tgt

            # Extract evidence
            edges = self.edge_map.get((best_break_source, best_break_target), [])
            snippets: list[str] = []
            for e in edges:
                import_str = (
                    f"import {{{', '.join(e.import_names)}}}"
                    if e.import_names
                    else "import ..."
                )
                snippets.append(
                    f"{e.source}:{e.line} -> {import_str} from '{e.target}'"
                )

            # Affected modules = nodes in cycle + modules that import the cycle nodes
            affected: set[str] = set(unique_nodes)
            for n in unique_nodes:
                fn = self.file_map.get(n)
                if fn:
                    affected.update(fn.imported_by)
            affected.discard(best_break_source)

            hash_src = f"cycle:{':'.join(sorted(unique_nodes))}"
            rec_id = f"ref_cycle_{hashlib.sha256(hash_src.encode()).hexdigest()[:12]}"

            recs.append(
                RefactoringRecommendation(
                    recommendation_id=rec_id,
                    target_module=best_break_source,
                    category=AdvisorCategory.CIRCULAR_DEPENDENCY,
                    severity="critical" if len(unique_nodes) <= 3 else "high",
                    title=f"Break circular dependency cycle ({len(unique_nodes)} modules)",
                    description=(
                        f"A circular dependency loop exists between {len(unique_nodes)} modules: "
                        f"{' -> '.join(unique_nodes)} -> {unique_nodes[0]}. "
                        f"Severing the link from '{best_break_source}' to '{best_break_target}' "
                        f"will eliminate this cycle and restore an acyclic DAG."
                    ),
                    evidence_id=f"ev_cycle_{rec_id}",
                    evidence_snippets=snippets,
                    revision_source=revision,
                    affected_modules=sorted(list(affected))[:10],
                    expected_architectural_benefit=(
                        f"Eliminates 1 circular dependency chain of length {len(unique_nodes)}. "
                        f"Restores strict topological compilation order and eliminates runtime import deadlocks."
                    ),
                    suggested_action_steps=[
                        f"1. Inspect imports from '{best_break_target}' in '{best_break_source}'.",
                        "2. Extract shared data models or interface signatures into a neutral shared module (e.g. 'models.py' or 'types.ts').",
                        f"3. Invert the dependency so '{best_break_source}' depends on the shared abstraction rather than concrete '{best_break_target}'.",
                        f"4. Re-run RepoDNA analysis to verify that cycle {cycle.id} is resolved.",
                    ],
                    risks_and_limitations=(
                        "Extracting shared types may touch multiple import statements across dependent modules. "
                        "Keep backward-compatible re-exports during transition if necessary."
                    ),
                    support_level="verified",
                    metric_delta_preview={
                        "cycle_length": len(unique_nodes),
                        "cycle_id": cycle.id,
                        "cycle_reduction": 1,
                        "breaking_edge": f"{best_break_source} -> {best_break_target}",
                    },
                )
            )

        return recs

    # -------------------------------------------------------------------------
    # Category 2: High Coupling Module Review
    # -------------------------------------------------------------------------
    def _analyze_high_coupling(self) -> list[RefactoringRecommendation]:
        recs: list[RefactoringRecommendation] = []
        revision = (
            self.analysis.git_insights.commit_sha
            if self.analysis.git_insights and self.analysis.git_insights.commit_sha
            else "WORKING_TREE"
        )

        for f in self.analysis.files:
            # Skip test files and third-party files
            if any(part in f.id for part in ("tests/", "test_", "__tests__", "spec.")):
                continue

            instability = (
                f.fan_out / (f.fan_in + f.fan_out)
                if (f.fan_in + f.fan_out) > 0
                else f.instability
            )

            # Flag if fan_out >= 7 or (instability > 0.8 and fan_in + fan_out >= 8)
            if f.fan_out >= 7 or (instability >= 0.8 and (f.fan_in + f.fan_out) >= 8):
                rec_id = f"ref_coupling_{hashlib.sha256(f.id.encode()).hexdigest()[:12]}"
                severity = "high" if f.fan_out >= 10 else "medium"

                recs.append(
                    RefactoringRecommendation(
                        recommendation_id=rec_id,
                        target_module=f.id,
                        category=AdvisorCategory.HIGH_COUPLING,
                        severity=severity,
                        title=f"Decouple high efferent coupling in {f.name} (fan-out: {f.fan_out})",
                        description=(
                            f"Module '{f.id}' directly imports {f.fan_out} internal modules "
                            f"(Instability metric I = {instability:.2f}). "
                            f"High efferent coupling makes this module sensitive to changes in any of its dependencies."
                        ),
                        evidence_id=f"ev_coupling_{rec_id}",
                        evidence_snippets=[
                            f"Imports {len(f.imports_internal)} internal dependencies: {', '.join(f.imports_internal[:6])}{'...' if len(f.imports_internal) > 6 else ''}"
                        ],
                        revision_source=revision,
                        affected_modules=f.imported_by[:10],
                        expected_architectural_benefit=(
                            f"Reduces efferent coupling from {f.fan_out} to < 5. "
                            f"Lowers instability metric and limits ripple effects during dependency refactoring."
                        ),
                        suggested_action_steps=[
                            f"1. Audit the {f.fan_out} outgoing imports in '{f.id}'. Group them by cohesive domain capability.",
                            "2. Introduce a Facade or Gateway module to consolidate low-level subsystem dependencies.",
                            "3. Pass dependencies via constructor or dependency injection rather than direct concrete imports.",
                            "4. Move utility or transformation functions into separate pure modules.",
                        ],
                        risks_and_limitations=(
                            "Introducing facades adds an extra layer of indirection. Ensure interfaces remain cohesive."
                        ),
                        support_level="verified",
                        metric_delta_preview={
                            "current_fan_out": f.fan_out,
                            "current_instability": round(instability, 3),
                            "target_fan_out": max(3, f.fan_out // 2),
                        },
                    )
                )

        return recs

    # -------------------------------------------------------------------------
    # Category 3: Layer Boundary Improvement
    # -------------------------------------------------------------------------
    def _analyze_layer_boundaries(self) -> list[RefactoringRecommendation]:
        recs: list[RefactoringRecommendation] = []
        revision = (
            self.analysis.git_insights.commit_sha
            if self.analysis.git_insights and self.analysis.git_insights.commit_sha
            else "WORKING_TREE"
        )

        def get_layer(path: str) -> tuple[int, str]:
            low = path.lower()
            if any(k in low for k in ("models", "types", "schemas", "interfaces", "entities")):
                return (0, "Core Types/Domain")
            if any(k in low for k in ("utils", "common", "core", "storage", "parsers", "graph")):
                return (1, "Infrastructure/Core")
            if any(k in low for k in ("services", "brain", "history", "guardian", "rules")):
                return (2, "Business Logic/Services")
            if any(k in low for k in ("api", "cli", "mcp", "views", "components", "pages")):
                return (3, "Presentation/Interface")
            return (1, "Infrastructure/Core")

        for edge in self.analysis.edges:
            src_tier, src_layer = get_layer(edge.source)
            tgt_tier, tgt_layer = get_layer(edge.target)

            # Inversion: Lower tier importing higher tier
            if src_tier < tgt_tier and (tgt_tier - src_tier) >= 2:
                rec_id = f"ref_layer_{hashlib.sha256(f'{edge.source}->{edge.target}'.encode()).hexdigest()[:12]}"
                recs.append(
                    RefactoringRecommendation(
                        recommendation_id=rec_id,
                        target_module=edge.source,
                        category=AdvisorCategory.LAYER_BOUNDARY,
                        severity="high" if src_tier == 0 else "medium",
                        title=f"Resolve layer boundary inversion in {edge.source}",
                        description=(
                            f"Lower architectural layer '{src_layer}' ({edge.source}) imports from "
                            f"higher layer '{tgt_layer}' ({edge.target}). "
                            f"Architectural clean layers require dependencies to flow toward the core/domain."
                        ),
                        evidence_id=f"ev_layer_{rec_id}",
                        evidence_snippets=[
                            f"{edge.source}:{edge.line} -> imports '{edge.target}'"
                        ],
                        revision_source=revision,
                        affected_modules=[edge.target],
                        expected_architectural_benefit=(
                            "Enforces clean unidirectional dependency flow and preserves layer modularity."
                        ),
                        suggested_action_steps=[
                            f"1. Remove direct import of '{edge.target}' from '{edge.source}'.",
                            "2. Define an interface or abstract base class within the lower layer.",
                            f"3. Invert dependency: have '{edge.target}' implement or satisfy the contract defined in '{src_layer}'.",
                            "4. Wire the concrete instance at application bootstrap / composition root.",
                        ],
                        risks_and_limitations=(
                            "Requires dependency injection or event dispatching to avoid direct coupling."
                        ),
                        support_level="verified",
                        metric_delta_preview={
                            "source_layer": src_layer,
                            "target_layer": tgt_layer,
                            "violating_edge": f"{edge.source} -> {edge.target}",
                        },
                    )
                )

        return recs

    # -------------------------------------------------------------------------
    # Category 4: Oversized Architectural Hub Review
    # -------------------------------------------------------------------------
    def _analyze_oversized_hubs(self) -> list[RefactoringRecommendation]:
        recs: list[RefactoringRecommendation] = []
        revision = (
            self.analysis.git_insights.commit_sha
            if self.analysis.git_insights and self.analysis.git_insights.commit_sha
            else "WORKING_TREE"
        )

        for f in self.analysis.files:
            # Skip test files
            if any(part in f.id for part in ("tests/", "test_", "__tests__", "spec.")):
                continue

            is_hub_condition = (
                f.is_hub
                or (f.fan_in >= 8 and f.fan_out >= 6)
                or ((f.fan_in + f.fan_out) >= 14 and f.lines_code >= 250)
            )

            if is_hub_condition:
                rec_id = f"ref_hub_{hashlib.sha256(f.id.encode()).hexdigest()[:12]}"
                if f.lines_code >= 500 or (f.fan_in + f.fan_out) >= 20:
                    severity = "critical"
                elif f.lines_code >= 300 or (f.fan_in + f.fan_out) >= 14 or f.is_hub:
                    severity = "high"
                else:
                    severity = "medium"

                recs.append(
                    RefactoringRecommendation(
                        recommendation_id=rec_id,
                        target_module=f.id,
                        category=AdvisorCategory.OVERSIZED_HUB,
                        severity=severity,
                        title=f"Decompose oversized architectural hub {f.name}",
                        description=(
                            f"Module '{f.id}' acts as a central hub with {f.fan_in} incoming and "
                            f"{f.fan_out} outgoing dependencies ({f.lines_code} LOC). "
                            f"High degree centrality creates a Single Point of Failure (SPOF) and merge conflict hot spot."
                        ),
                        evidence_id=f"ev_hub_{rec_id}",
                        evidence_snippets=[
                            f"Fan-in: {f.fan_in} callers | Fan-out: {f.fan_out} callees | LOC: {f.lines_code}"
                        ],
                        revision_source=revision,
                        affected_modules=f.imported_by[:10],
                        expected_architectural_benefit=(
                            "Decomposes monolithic hub into cohesive domain modules, reducing blast radius and merge conflict frequency."
                        ),
                        suggested_action_steps=[
                            f"1. Audit responsibilities inside '{f.name}' ({f.lines_code} LOC, {f.fan_in} consumers).",
                            "2. Extract self-contained domain functions or classes into cohesive sibling modules.",
                            f"3. Retain '{f.id}' as a slim re-export facade during transition to preserve consumer compatibility.",
                            "4. Deprecate unused re-exports over time.",
                        ],
                        risks_and_limitations=(
                            f"Refactoring a central hub affects {f.fan_in} incoming consumers. "
                            f"Coordinate migration across dependent sub-packages."
                        ),
                        support_level="verified",
                        metric_delta_preview={
                            "current_degree": f.fan_in + f.fan_out,
                            "fan_in": f.fan_in,
                            "fan_out": f.fan_out,
                            "lines_code": f.lines_code,
                        },
                    )
                )

        return recs

    # -------------------------------------------------------------------------
    # Helper & Formatting Methods
    # -------------------------------------------------------------------------
    def _deduplicate_recommendations(
        self, recs: list[RefactoringRecommendation]
    ) -> list[RefactoringRecommendation]:
        seen_keys: set[tuple[str, str]] = set()
        deduped: list[RefactoringRecommendation] = []

        for r in recs:
            key = (r.target_module, r.category.value)
            if key not in seen_keys:
                seen_keys.add(key)
                deduped.append(r)

        return deduped

    def _apply_filters(
        self,
        recs: list[RefactoringRecommendation],
        category_filter: AdvisorCategory | None,
        min_severity: str | None,
    ) -> list[RefactoringRecommendation]:
        res = recs
        if category_filter:
            res = [r for r in res if r.category == category_filter]

        if min_severity:
            sev_levels = {"low": 1, "medium": 2, "high": 3, "critical": 4}
            min_val = sev_levels.get(min_severity.lower(), 1)
            res = [r for r in res if sev_levels.get(r.severity.lower(), 1) >= min_val]

        return res

    def _format_summary(
        self,
        recs: list[RefactoringRecommendation],
        by_cat: dict[str, int],
        by_sev: dict[str, int],
    ) -> str:
        lines = [
            "=" * 78,
            "RepoDNA Architectural Refactoring Advisor",
            "=" * 78,
            f"Total Recommendations : {len(recs)}",
            f"By Severity           : Critical: {by_sev.get('critical', 0)} | High: {by_sev.get('high', 0)} | Medium: {by_sev.get('medium', 0)} | Low: {by_sev.get('low', 0)}",
            f"By Category           : Circular: {by_cat.get(AdvisorCategory.CIRCULAR_DEPENDENCY.value, 0)} | Coupling: {by_cat.get(AdvisorCategory.HIGH_COUPLING.value, 0)} | Layers: {by_cat.get(AdvisorCategory.LAYER_BOUNDARY.value, 0)} | Hubs: {by_cat.get(AdvisorCategory.OVERSIZED_HUB.value, 0)}",
            "-" * 78,
        ]

        if not recs:
            lines.append("No architectural refactoring recommendations. Clean architecture detected!")
        else:
            for i, r in enumerate(recs, 1):
                sev_tag = f"[{r.severity.upper()}]"
                cat_tag = f"({r.category.value})"
                lines.append(f"{i}. {sev_tag} {r.title} {cat_tag}")
                lines.append(f"   Target  : {r.target_module}")
                lines.append(f"   Benefit : {r.expected_architectural_benefit}")
                if r.suggested_action_steps:
                    lines.append(f"   Action  : {r.suggested_action_steps[0]}")
                lines.append("-" * 78)

        lines.append("=" * 78)
        return "\n".join(lines)
