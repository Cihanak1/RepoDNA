"""Architecture Diff Engine for comparing two immutable repository analysis snapshots."""

from __future__ import annotations

from datetime import UTC, datetime

from repodna.diff.models import (
    ArchitectureDiffResult,
    CouplingDeltaItem,
    CoverageDelta,
    CycleChanges,
    CycleDiffItem,
    DependencyChanges,
    EdgeDiffItem,
    HealthScoreDelta,
    ModuleChanges,
    RenamedModule,
    RevisionProvenance,
    RuleFindingChanges,
)
from repodna.schemas.models import AnalysisResult, FileNode


def _canonicalize_cycle(nodes: list[str]) -> tuple[str, ...]:
    """Canonicalize a cycle path [A, B, C, A] to a rotation-invariant representation."""
    cleaned = [n for n in nodes]
    if len(cleaned) > 1 and cleaned[0] == cleaned[-1]:
        cleaned = cleaned[:-1]
    if not cleaned:
        return ()
    # Find lexicographically smallest rotation
    rotations = [tuple(cleaned[i:] + cleaned[:i]) for i in range(len(cleaned))]
    return min(rotations)


class ArchitectureDiffEngine:
    """Computes architectural deltas between two analysis snapshots."""

    @staticmethod
    def compare_analyses(
        base: AnalysisResult,
        head: AnalysisResult,
        base_ref: str = "base",
        head_ref: str = "head",
        base_commit_sha: str | None = None,
        head_commit_sha: str | None = None,
        base_is_working_tree: bool = False,
        head_is_working_tree: bool = False,
    ) -> ArchitectureDiffResult:
        base_files: dict[str, FileNode] = {f.id: f for f in base.files}
        head_files: dict[str, FileNode] = {f.id: f for f in head.files}

        base_ids = set(base_files.keys())
        head_ids = set(head_files.keys())

        raw_added = head_ids - base_ids
        raw_removed = base_ids - head_ids

        # Check for coverage/skip caveats
        head_skipped_paths = {s.path for s in head.transparency.skipped_files}
        caveats: list[str] = []

        apparent_removed = set()
        for r_id in raw_removed:
            if r_id in head_skipped_paths:
                caveats.append(
                    f"Module '{r_id}' was excluded by resource/file limits in '{head_ref}' rather than deleted."
                )
            else:
                apparent_removed.add(r_id)

        # Detect renamed modules heuristic: matching filename and similar symbol overlap
        renamed: list[RenamedModule] = []
        confirmed_added: list[str] = []
        confirmed_removed: list[str] = sorted(apparent_removed)

        for a_id in sorted(raw_added):
            a_node = head_files[a_id]
            match_found = False
            for r_id in list(confirmed_removed):
                r_node = base_files[r_id]
                # Same basename and same language
                if a_node.name == r_node.name and a_node.language == r_node.language:
                    # Check symbol overlap
                    a_syms = {s.name for s in a_node.symbols}
                    r_syms = {s.name for s in r_node.symbols}
                    sym_overlap = len(a_syms & r_syms) if (a_syms and r_syms) else 0

                    if sym_overlap > 0 or (not a_syms and not r_syms and abs(a_node.lines_code - r_node.lines_code) < 10):
                        renamed.append(
                            RenamedModule(
                                old_path=r_id,
                                new_path=a_id,
                                confidence=0.85 if sym_overlap > 0 else 0.70,
                                reason=f"Identical basename '{a_node.name}' with matching language and {sym_overlap} shared symbol(s)",
                            )
                        )
                        confirmed_removed.remove(r_id)
                        match_found = True
                        break
            if not match_found:
                confirmed_added.append(a_id)

        # Dependencies
        base_edges = {(e.source, e.target): e for e in base.edges}
        head_edges = {(e.source, e.target): e for e in head.edges}

        added_edges = [
            EdgeDiffItem(source=src, target=tgt, import_names=e.import_names)
            for (src, tgt), e in head_edges.items()
            if (src, tgt) not in base_edges
        ]
        removed_edges = [
            EdgeDiffItem(source=src, target=tgt, import_names=e.import_names)
            for (src, tgt), e in base_edges.items()
            if (src, tgt) not in head_edges
        ]

        # Cycles
        base_canonical_cycles = {
            _canonicalize_cycle(c.nodes): c for c in base.cycles
        }
        head_canonical_cycles = {
            _canonicalize_cycle(c.nodes): c for c in head.cycles
        }

        new_cycles = [
            CycleDiffItem(
                id=c.id,
                nodes=c.nodes,
                length=c.length,
                severity=c.severity,
                description=c.description,
            )
            for key, c in head_canonical_cycles.items()
            if key not in base_canonical_cycles
        ]
        resolved_cycles = [
            CycleDiffItem(
                id=c.id,
                nodes=c.nodes,
                length=c.length,
                severity=c.severity,
                description=c.description,
            )
            for key, c in base_canonical_cycles.items()
            if key not in head_canonical_cycles
        ]
        persisting_cycles_count = len(head_canonical_cycles) - len(new_cycles)

        # Significant coupling deltas
        coupling_deltas: list[CouplingDeltaItem] = []
        for fid in sorted(base_ids & head_ids):
            b_n = base_files[fid]
            h_n = head_files[fid]
            fan_in_delta = h_n.fan_in - b_n.fan_in
            fan_out_delta = h_n.fan_out - b_n.fan_out
            inst_delta = round(h_n.instability - b_n.instability, 3)

            if abs(fan_in_delta) >= 2 or abs(fan_out_delta) >= 2 or abs(inst_delta) >= 0.15:
                coupling_deltas.append(
                    CouplingDeltaItem(
                        file_id=fid,
                        fan_in_before=b_n.fan_in,
                        fan_in_after=h_n.fan_in,
                        fan_in_delta=fan_in_delta,
                        fan_out_before=b_n.fan_out,
                        fan_out_after=h_n.fan_out,
                        fan_out_delta=fan_out_delta,
                        instability_before=b_n.instability,
                        instability_after=h_n.instability,
                        instability_delta=inst_delta,
                    )
                )

        # Health score delta
        b_hr = base.health_report
        h_hr = head.health_report
        score_delta = None
        if b_hr.overall_score is not None and h_hr.overall_score is not None:
            score_delta = round(h_hr.overall_score - b_hr.overall_score, 2)

        health_delta = HealthScoreDelta(
            score_before=b_hr.overall_score,
            score_after=h_hr.overall_score,
            score_delta=score_delta,
            grade_before=b_hr.grade,
            grade_after=h_hr.grade,
            status_before=b_hr.status,
            status_after=h_hr.status,
        )

        # Rule findings delta
        base_findings_map = {f.rule_id + "::" + ":".join(sorted(f.affected_files)): f for f in b_hr.findings}
        head_findings_map = {f.rule_id + "::" + ":".join(sorted(f.affected_files)): f for f in h_hr.findings}

        new_findings = [f for k, f in head_findings_map.items() if k not in base_findings_map]
        resolved_findings = [f for k, f in base_findings_map.items() if k not in head_findings_map]
        persisting_count = len(head_findings_map) - len(new_findings)

        # Coverage delta
        b_tr = base.transparency
        h_tr = head.transparency
        loc_cov_delta = round(h_tr.ast_loc_coverage_pct - b_tr.ast_loc_coverage_pct, 2)

        if b_tr.supported_languages_detected != h_tr.supported_languages_detected:
            caveats.append(
                f"Supported language set shifted between revisions: "
                f"'{b_tr.supported_languages_detected}' -> '{h_tr.supported_languages_detected}'."
            )

        coverage_delta = CoverageDelta(
            ast_loc_coverage_before=b_tr.ast_loc_coverage_pct,
            ast_loc_coverage_after=h_tr.ast_loc_coverage_pct,
            ast_loc_coverage_delta=loc_cov_delta,
            supported_langs_before=b_tr.supported_languages_detected,
            supported_langs_after=h_tr.supported_languages_detected,
            caveats=caveats,
        )

        # Verdict
        if new_cycles:
            verdict = "regressive_cycles"
        elif score_delta is not None and score_delta < -3.0:
            verdict = "degraded"
        elif (score_delta is not None and score_delta > 3.0) or (resolved_cycles and not new_cycles):
            verdict = "improved"
        else:
            verdict = "neutral"

        # Summary text
        summary_lines = [
            f"RepoDNA Architecture Diff: {base_ref} -> {head_ref}",
            f"Verdict: {verdict.upper()}",
            f"Modules: +{len(confirmed_added)} added, -{len(confirmed_removed)} removed, {len(renamed)} renamed.",
            f"Dependencies: +{len(added_edges)} added edges, -{len(removed_edges)} removed edges.",
            f"Cycles: +{len(new_cycles)} new cycles, -{len(resolved_cycles)} resolved ({persisting_cycles_count} persistent).",
        ]
        if score_delta is not None:
            sign = "+" if score_delta >= 0 else ""
            summary_lines.append(
                f"Health Score: {b_hr.overall_score:.1f} ({b_hr.grade}) -> {h_hr.overall_score:.1f} ({h_hr.grade}) [{sign}{score_delta:.1f} pts]"
            )
        else:
            summary_lines.append(f"Health Status: {b_hr.status} -> {h_hr.status}")

        if new_findings:
            summary_lines.append(
                f"New Architectural Violations ({len(new_findings)}): {', '.join(f.rule_id for f in new_findings[:3])}"
            )
        if resolved_findings:
            summary_lines.append(
                f"Resolved Violations ({len(resolved_findings)}): {', '.join(f.rule_id for f in resolved_findings[:3])}"
            )
        if caveats:
            summary_lines.append(f"Coverage Caveats: {'; '.join(caveats)}")

        base_prov = RevisionProvenance(
            ref_name=base_ref,
            commit_sha=base_commit_sha,
            is_working_tree=base_is_working_tree,
            analyzed_at=base.analyzed_at,
            total_files=base.total_files,
            total_lines_code=base.total_lines_code,
            ast_coverage_pct=b_tr.ast_loc_coverage_pct,
            health_score=b_hr.overall_score,
            health_grade=b_hr.grade,
        )

        head_prov = RevisionProvenance(
            ref_name=head_ref,
            commit_sha=head_commit_sha,
            is_working_tree=head_is_working_tree,
            analyzed_at=head.analyzed_at,
            total_files=head.total_files,
            total_lines_code=head.total_lines_code,
            ast_coverage_pct=h_tr.ast_loc_coverage_pct,
            health_score=h_hr.overall_score,
            health_grade=h_hr.grade,
        )

        return ArchitectureDiffResult(
            base_provenance=base_prov,
            head_provenance=head_prov,
            generated_at=datetime.now(UTC),
            verdict=verdict,
            module_changes=ModuleChanges(
                added=confirmed_added,
                removed=confirmed_removed,
                renamed=renamed,
            ),
            dependency_changes=DependencyChanges(
                added_edges=added_edges,
                removed_edges=removed_edges,
            ),
            cycle_changes=CycleChanges(
                new_cycles=new_cycles,
                resolved_cycles=resolved_cycles,
                persisting_cycles=persisting_cycles_count,
            ),
            significant_coupling_deltas=coupling_deltas,
            health_delta=health_delta,
            finding_changes=RuleFindingChanges(
                new_findings=new_findings,
                resolved_findings=resolved_findings,
                persisting_findings_count=persisting_count,
            ),
            coverage_delta=coverage_delta,
            summary_text="\n".join(summary_lines),
        )
