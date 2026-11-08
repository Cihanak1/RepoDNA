"""Read-only Repository Intelligence Service for AI Agents and Workstations."""

from __future__ import annotations

import re
from collections import defaultdict, deque
from pathlib import PurePosixPath

from repodna.intelligence.models import (
    AnalysisCoverageReport,
    ArchitectureFindingsResponse,
    ArchitectureMap,
    ChangeImpactResponse,
    DependencyQueryResponse,
    DependencyTraceItem,
    ModuleDetails,
    PackageCluster,
    RelevantModuleMatch,
    RelevantModulesResponse,
    RepositoryOverview,
)
from repodna.schemas.models import (
    AnalysisResult,
    FileNode,
    LanguageSupportLevel,
    RuleFinding,
    SeverityLevel,
)


class RepositoryIntelligenceService:
    """Provides high-precision architectural queries over immutable AnalysisResults."""

    def __init__(self, analysis: AnalysisResult) -> None:
        self.analysis = analysis
        self._files_by_id: dict[str, FileNode] = {f.id: f for f in analysis.files}
        self._edges_by_source: dict[str, list] = defaultdict(list)
        self._edges_by_target: dict[str, list] = defaultdict(list)
        for edge in analysis.edges:
            self._edges_by_source[edge.source].append(edge)
            self._edges_by_target[edge.target].append(edge)

        self._findings_by_file: dict[str, list[RuleFinding]] = defaultdict(list)
        for finding in analysis.health_report.findings:
            for aff in finding.affected_files:
                self._findings_by_file[aff].append(finding)

    def get_repository_overview(self) -> RepositoryOverview:
        """Returns executive architectural scorecard, health status, and key hubs."""
        res = self.analysis
        hr = res.health_report
        gm = res.graph_metrics
        tr = res.transparency

        hubs = [f.id for f in res.files if f.is_hub]
        if not hubs:
            hubs = [f.id for f in sorted(res.files, key=lambda f: -f.fan_in) if f.fan_in > 0]
        primary_langs = [lg.language for lg in res.languages[:5]]

        score_desc = (
            f"{hr.overall_score:.1f}/100 (Grade {hr.grade})"
            if hr.overall_score is not None
            else f"N/A ({hr.status})"
        )

        summary_lines = [
            f"Repository: {res.repo_name} ({res.target_display})",
            f"Health Score: {score_desc} | Confidence: {hr.confidence.upper()}",
            f"AST Coverage: {tr.ast_loc_coverage_pct:.1f}% LOC ({tr.ast_file_coverage_pct:.1f}% files)",
            f"Scale: {res.total_files:,} files, {res.total_lines_code:,} LOC across {', '.join(primary_langs) or 'unspecified'}.",
            f"Architecture: {gm.total_nodes} nodes, {gm.total_edges} internal dependencies, {gm.cycle_count} cycles ({gm.scc_count} cyclic SCCs).",
        ]
        if hubs:
            summary_lines.append(f"Primary Architectural Hubs ({len(hubs)}): {', '.join(hubs[:5])}")
        if hr.unverified_rules:
            summary_lines.append(
                f"Unverified Rules ({len(hr.unverified_rules)} due to limited AST coverage): {', '.join(hr.unverified_rules)}"
            )

        return RepositoryOverview(
            repo_name=res.repo_name,
            target_display=res.target_display,
            analyzed_at=res.analyzed_at,
            analysis_version="0.3.0",
            total_files=res.total_files,
            total_lines_code=res.total_lines_code,
            total_size_bytes=res.total_size_bytes,
            health_score=hr.overall_score,
            health_grade=hr.grade,
            health_status=hr.status,
            confidence=hr.confidence,
            ast_loc_coverage_pct=tr.ast_loc_coverage_pct,
            ast_file_coverage_pct=tr.ast_file_coverage_pct,
            cycle_count=gm.cycle_count,
            cyclic_scc_count=gm.scc_count,
            hub_modules_count=len(hubs),
            primary_languages=primary_langs,
            unverified_rules=hr.unverified_rules,
            key_architectural_hubs=hubs[:10],
            summary_text="\n".join(summary_lines),
        )

    def get_architecture_map(
        self, level: str = "clusters", limit: int = 50
    ) -> ArchitectureMap:
        """Computes hierarchical package clusters and inter-cluster dependency links."""
        res = self.analysis
        clusters_dict: dict[str, list[str]] = defaultdict(list)

        for f in res.files:
            posix_path = PurePosixPath(f.id)
            parts = posix_path.parts
            if len(parts) > 1:
                cluster_name = "/".join(parts[:2]) if len(parts) > 2 else parts[0]
            else:
                cluster_name = "(root)"
            clusters_dict[cluster_name].append(f.id)

        clusters: list[PackageCluster] = []
        for cname, files in sorted(clusters_dict.items(), key=lambda x: -len(x[1])):
            external_pkgs = set()
            for fid in files:
                node = self._files_by_id.get(fid)
                if node:
                    external_pkgs.update(node.imports_external)
            clusters.append(
                PackageCluster(
                    name=cname,
                    file_count=len(files),
                    files=sorted(files)[:limit] if level == "overview" else sorted(files),
                    external_dependencies=sorted(external_pkgs)[:10],
                )
            )

        # Inter-cluster edges
        cluster_by_file = {}
        for c in clusters:
            for fid in c.files:
                cluster_by_file[fid] = c.name

        inter_edges_counts: dict[tuple[str, str], int] = defaultdict(int)
        for edge in res.edges:
            src_cluster = cluster_by_file.get(edge.source)
            tgt_cluster = cluster_by_file.get(edge.target)
            if src_cluster and tgt_cluster and src_cluster != tgt_cluster:
                inter_edges_counts[(src_cluster, tgt_cluster)] += 1

        inter_edges = [
            {"source_cluster": src, "target_cluster": tgt, "edge_count": count}
            for (src, tgt), count in sorted(inter_edges_counts.items(), key=lambda x: -x[1])[:30]
        ]

        summary_lines = [
            f"Architecture Map ({level}) — {len(clusters)} package clusters across {res.total_files} files.",
            f"Top clusters: {', '.join(f'{c.name} ({c.file_count})' for c in clusters[:6])}",
        ]

        return ArchitectureMap(
            level=level,
            total_modules=res.total_files,
            total_clusters=len(clusters),
            clusters=clusters[:limit] if level == "overview" else clusters,
            inter_cluster_edges=inter_edges,
            summary_text="\n".join(summary_lines),
        )

    def find_relevant_modules(
        self, query: str, limit: int = 10
    ) -> RelevantModulesResponse:
        """Finds modules relevant to a query based on file path, symbols, language, and hub status."""
        query_terms = [t.lower() for t in re.split(r"[\s/\\._-]+", query) if len(t) >= 2]
        if not query_terms:
            query_terms = [query.lower()]

        scored_matches: list[RelevantModuleMatch] = []

        for f in self.analysis.files:
            file_id_lower = f.id.lower()
            name_lower = f.name.lower()
            reasons = []
            score = 0.0

            # Exact path or name match
            if query.lower() == name_lower:
                score += 8.0
                reasons.append(f"Exact filename match on '{query}'")
            elif query.lower() in file_id_lower or query.lower() in name_lower:
                score += 5.0
                reasons.append(f"Path substring match on '{query}'")

            # Term matches
            term_matches = sum(1 for t in query_terms if t in file_id_lower)
            if term_matches > 0:
                score += term_matches * 2.0
                reasons.append(f"{term_matches} term(s) matched in path")

            # Symbol match (function, class, interface, struct)
            matching_symbols = []
            for sym in f.symbols:
                sym_lower = sym.name.lower()
                if any(t in sym_lower for t in query_terms):
                    matching_symbols.append(sym)
                    score += 3.5

            if matching_symbols:
                reasons.append(
                    f"Matched {len(matching_symbols)} symbol(s): {', '.join(s.name for s in matching_symbols[:3])}"
                )

            # Architectural hub boost
            if f.is_hub and score > 0:
                score += 1.5
                reasons.append("Hub module boost (high afferent coupling)")

            # In cycle note
            if f.in_cycle and score > 0:
                reasons.append("Participates in circular dependency")

            if score > 0:
                scored_matches.append(
                    RelevantModuleMatch(
                        file_id=f.id,
                        language=f.language,
                        support_level=f.support_level,
                        relevance_score=round(score, 2),
                        match_reasons=reasons,
                        matching_symbols=matching_symbols[:5],
                        fan_in=f.fan_in,
                        fan_out=f.fan_out,
                        in_cycle=f.in_cycle,
                        is_hub=f.is_hub,
                    )
                )

        scored_matches.sort(key=lambda m: (-m.relevance_score, -m.fan_in, m.file_id))
        top_matches = scored_matches[:limit]

        if top_matches:
            summary = (
                f"Found {len(scored_matches)} relevant module(s) for query '{query}'. "
                f"Top match: {top_matches[0].file_id} (score {top_matches[0].relevance_score})."
            )
        else:
            summary = f"No modules matched query '{query}'. Try searching by directory name, symbol name, or package."

        return RelevantModulesResponse(
            query=query,
            total_matches=len(scored_matches),
            matches=top_matches,
            summary_text=summary,
        )

    def get_module_details(self, file_path: str) -> ModuleDetails:
        """Returns deep architectural forensics and health findings for a specific file."""
        norm_path = file_path.replace("\\", "/").lstrip("/")
        node = self._files_by_id.get(norm_path)
        if not node:
            # Try fuzzy suffix match
            for fid, candidate in self._files_by_id.items():
                if fid.endswith(norm_path) or norm_path.endswith(fid):
                    node = candidate
                    norm_path = fid
                    break

        if not node:
            raise KeyError(
                f"Module '{file_path}' not found in analyzed repository. Available files: {len(self._files_by_id)}"
            )

        findings = self._findings_by_file.get(norm_path, [])
        limitations: list[str] = []

        if node.support_level == LanguageSupportLevel.PARTIAL_STATIC:
            limitations.append(
                f"Language '{node.language}' analyzed with partial static pattern scanner. Internal dependency graph is not evaluated for this file."
            )
        elif node.support_level == LanguageSupportLevel.UNSUPPORTED:
            limitations.append(
                f"Language '{node.language}' is unsupported for AST analysis. Only file size and LOC were captured."
            )

        if node.unresolved_imports:
            limitations.append(
                f"{len(node.unresolved_imports)} unresolved import(s) (e.g. external package or dynamic import)."
            )

        summary_lines = [
            f"Module: {node.id} ({node.language}, {node.support_level.value})",
            f"Metrics: {node.lines_code} LOC, Fan-In: {node.fan_in}, Fan-Out: {node.fan_out}, Instability: {node.instability:.2f}",
            f"State: {'In Circular Dependency' if node.in_cycle else 'No Cycles'} | {'Hub Module' if node.is_hub else 'Regular Node'}",
            f"Dependencies: {len(node.imports_internal)} internal, {len(node.imports_external)} external | Dependents: {len(node.imported_by)} internal",
        ]
        if findings:
            summary_lines.append(f"Health Findings ({len(findings)}): {', '.join(f.rule_id for f in findings)}")

        return ModuleDetails(
            file_id=node.id,
            name=node.name,
            directory=node.directory,
            language=node.language,
            support_level=node.support_level,
            size_bytes=node.size_bytes,
            lines_total=node.lines_total,
            lines_code=node.lines_code,
            lines_comment=node.lines_comment,
            fan_in=node.fan_in,
            fan_out=node.fan_out,
            instability=node.instability,
            in_cycle=node.in_cycle,
            cycle_ids=node.cycle_ids,
            is_hub=node.is_hub,
            is_orphan=node.is_orphan,
            symbols=node.symbols,
            dependencies_internal=node.imports_internal,
            dependents_internal=node.imported_by,
            external_packages=node.imports_external,
            health_findings=findings,
            secret_warnings=node.secret_warnings,
            analysis_limitations=limitations,
            summary_text="\n".join(summary_lines),
        )

    def get_dependencies(
        self, file_path: str, direction: str = "outgoing", depth: int = 1
    ) -> DependencyQueryResponse:
        """Returns direct and transitive dependencies or reverse dependents."""
        norm_path = file_path.replace("\\", "/").lstrip("/")
        if norm_path not in self._files_by_id:
            # Fuzzy match
            for fid in self._files_by_id:
                if fid.endswith(norm_path):
                    norm_path = fid
                    break

        if norm_path not in self._files_by_id:
            raise KeyError(f"Module '{file_path}' not found.")

        visited_edges: list[DependencyTraceItem] = []
        visited_nodes: set[str] = {norm_path}
        queue: deque[tuple[str, int]] = deque([(norm_path, 0)])

        while queue:
            curr, curr_depth = queue.popleft()
            if curr_depth >= depth:
                continue

            # Outgoing (imports made by curr)
            if direction in ("outgoing", "both"):
                for edge in self._edges_by_source.get(curr, []):
                    visited_edges.append(
                        DependencyTraceItem(
                            source=edge.source,
                            target=edge.target,
                            import_names=edge.import_names,
                            line=edge.line,
                            depth=curr_depth + 1,
                            in_cycle=edge.in_cycle,
                        )
                    )
                    if edge.target not in visited_nodes:
                        visited_nodes.add(edge.target)
                        queue.append((edge.target, curr_depth + 1))

            # Incoming (modules importing curr)
            if direction in ("incoming", "both"):
                for edge in self._edges_by_target.get(curr, []):
                    visited_edges.append(
                        DependencyTraceItem(
                            source=edge.source,
                            target=edge.target,
                            import_names=edge.import_names,
                            line=edge.line,
                            depth=curr_depth + 1,
                            in_cycle=edge.in_cycle,
                        )
                    )
                    if edge.source not in visited_nodes:
                        visited_nodes.add(edge.source)
                        queue.append((edge.source, curr_depth + 1))

        summary = (
            f"Traced {len(visited_edges)} {direction} dependency link(s) for '{norm_path}' "
            f"at depth {depth} across {len(visited_nodes)} module(s)."
        )

        return DependencyQueryResponse(
            root_file=norm_path,
            direction=direction,
            depth=depth,
            total_items=len(visited_edges),
            items=visited_edges,
            summary_text=summary,
        )

    def get_dependents(self, file_path: str, depth: int = 1) -> DependencyQueryResponse:
        """Returns reverse dependencies (modules that import this file)."""
        return self.get_dependencies(file_path, direction="incoming", depth=depth)

    def get_architecture_findings(
        self,
        rule_id: str | None = None,
        severity: str | None = None,
        category: str | None = None,
    ) -> ArchitectureFindingsResponse:
        """Returns architectural health rule findings filtered by rule ID, severity, or category."""
        all_findings = self.analysis.health_report.findings
        filtered: list[RuleFinding] = []

        for f in all_findings:
            if rule_id and f.rule_id != rule_id:
                continue
            if severity and f.severity.value.lower() != severity.lower():
                continue
            if category and f.category != category:
                continue
            filtered.append(f)

        crit = sum(1 for f in filtered if f.severity == SeverityLevel.CRITICAL)
        warn = sum(1 for f in filtered if f.severity == SeverityLevel.WARNING)
        inf = sum(1 for f in filtered if f.severity == SeverityLevel.INFO)

        summary = (
            f"Total Architectural Findings: {len(filtered)} "
            f"({crit} critical, {warn} warnings, {inf} info). "
            f"Unverified rules: {len(self.analysis.health_report.unverified_rules)}."
        )

        return ArchitectureFindingsResponse(
            total_findings=len(filtered),
            critical_count=crit,
            warning_count=warn,
            info_count=inf,
            findings=filtered,
            unverified_rules=self.analysis.health_report.unverified_rules,
            summary_text=summary,
        )

    def get_analysis_coverage(self) -> AnalysisCoverageReport:
        """Returns comprehensive AST coverage transparency and unsupported language disclosures."""
        tr = self.analysis.transparency
        hr = self.analysis.health_report

        guarantee = (
            "RepoDNA strictly bounds analysis to parseable AST structures. "
            "Unsupported languages or files with insufficient dependency coverage are marked N/A "
            "rather than generating speculative 100/100 passes."
        )

        summary_lines = [
            f"Analysis Confidence: {hr.confidence.upper()} ({hr.confidence_reason or 'Full structural analysis'})",
            f"AST LOC Coverage: {tr.ast_loc_coverage_pct:.1f}% ({tr.ast_file_coverage_pct:.1f}% of files)",
            f"Supported Languages: {', '.join(tr.supported_languages_detected) or 'None'}",
        ]
        if tr.partial_static_languages_detected:
            summary_lines.append(
                f"Partial Static: {', '.join(tr.partial_static_languages_detected)} "
                f"({tr.partial_static_files_count} files / {tr.partial_static_loc_coverage_pct:.1f}% LOC)"
            )
        if tr.unsupported_languages_detected:
            summary_lines.append(
                f"Unsupported: {', '.join(tr.unsupported_languages_detected)} "
                f"({tr.unsupported_files_count} files / {tr.unsupported_loc_coverage_pct:.1f}% LOC)"
            )
        if hr.unverified_rules:
            summary_lines.append(f"Unverified Rules: {', '.join(hr.unverified_rules)}")

        return AnalysisCoverageReport(
            confidence=hr.confidence,
            confidence_reason=hr.confidence_reason,
            ast_file_coverage_pct=tr.ast_file_coverage_pct,
            ast_loc_coverage_pct=tr.ast_loc_coverage_pct,
            supported_languages=tr.supported_languages_detected,
            partial_static_languages=tr.partial_static_languages_detected,
            partial_static_files_count=tr.partial_static_files_count,
            unsupported_languages=tr.unsupported_languages_detected,
            unsupported_files_count=tr.unsupported_files_count,
            skipped_files_count=len(tr.skipped_files),
            unverified_rules=hr.unverified_rules,
            honest_coverage_guarantee=guarantee,
            summary_text="\n".join(summary_lines),
        )

    def get_change_impact(
        self, changed_files: list[str], max_depth: int = 2
    ) -> ChangeImpactResponse:
        """Evaluates architectural risk and blast radius of proposed file changes."""
        normalized_targets = []
        for cf in changed_files:
            norm = cf.replace("\\", "/").lstrip("/")
            if norm in self._files_by_id:
                normalized_targets.append(norm)
            else:
                for fid in self._files_by_id:
                    if fid.endswith(norm):
                        normalized_targets.append(fid)
                        break

        if not normalized_targets:
            normalized_targets = [cf.replace("\\", "/").lstrip("/") for cf in changed_files]

        direct_dependents: set[str] = set()
        transitive_dependents: set[str] = set()
        affected_hubs: set[str] = set()
        impacted_cycles: set[str] = set()
        risk_factors: list[str] = []

        # Find direct dependents
        for target in normalized_targets:
            node = self._files_by_id.get(target)
            if node:
                if node.is_hub:
                    affected_hubs.add(target)
                    risk_factors.append(f"Target module '{target}' is an architectural hub (Fan-In: {node.fan_in}).")
                if node.in_cycle:
                    impacted_cycles.update(node.cycle_ids)
                    risk_factors.append(f"Target module '{target}' is locked inside circular dependency cycle(s).")
                for dep in node.imported_by:
                    direct_dependents.add(dep)

        # Transitive dependents BFS
        queue: deque[tuple[str, int]] = deque([(d, 1) for d in direct_dependents])
        visited: set[str] = set(direct_dependents) | set(normalized_targets)

        while queue:
            curr, depth = queue.popleft()
            if depth >= max_depth:
                continue
            curr_node = self._files_by_id.get(curr)
            if curr_node:
                if curr_node.is_hub:
                    affected_hubs.add(curr)
                for next_dep in curr_node.imported_by:
                    if next_dep not in visited:
                        visited.add(next_dep)
                        transitive_dependents.add(next_dep)
                        queue.append((next_dep, depth + 1))

        # Check cycles in all affected modules
        for aff in direct_dependents | transitive_dependents:
            node = self._files_by_id.get(aff)
            if node and node.in_cycle:
                impacted_cycles.update(node.cycle_ids)

        # Determine severity
        if affected_hubs or len(impacted_cycles) >= 2 or len(direct_dependents) > 10:
            severity = SeverityLevel.CRITICAL
        elif direct_dependents or impacted_cycles:
            severity = SeverityLevel.WARNING
        else:
            severity = SeverityLevel.INFO

        summary_lines = [
            f"Change Impact Analysis: {len(normalized_targets)} target file(s) evaluated.",
            f"Severity: {severity.value.upper()} | Direct Dependents: {len(direct_dependents)} | Transitive Dependents: {len(transitive_dependents)}",
        ]
        if affected_hubs:
            summary_lines.append(f"Affected Architectural Hubs: {', '.join(affected_hubs)}")
        if impacted_cycles:
            summary_lines.append(f"Impacted Circular Cycles ({len(impacted_cycles)}): {', '.join(sorted(impacted_cycles))}")

        return ChangeImpactResponse(
            target_files=normalized_targets,
            direct_dependents=sorted(direct_dependents),
            transitive_dependents=sorted(transitive_dependents),
            impacted_cycles=sorted(impacted_cycles),
            impact_severity=severity,
            risk_factors=risk_factors,
            affected_hubs=sorted(affected_hubs),
            summary_text="\n".join(summary_lines),
        )
