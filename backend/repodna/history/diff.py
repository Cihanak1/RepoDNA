"""Architecture Evolution Diff Engine.

Compares two HistoricalSnapshots to compute detailed architectural deltas,
including module additions/removals/renames, dependency graph evolution,
cycle creation/resolution, coupling changes, and health score progression.
"""

from __future__ import annotations

import subprocess
from datetime import datetime
from pathlib import Path

from repodna.diff.engine import _canonicalize_cycle
from repodna.diff.models import (
    CouplingDeltaItem,
    CoverageDelta,
    CycleChanges,
    CycleDiffItem,
    DependencyChanges,
    EdgeDiffItem,
    HealthScoreDelta,
    ModuleChanges,
    RenamedModule,
    RuleFindingChanges,
)
from repodna.history.models import (
    SNAPSHOT_SCHEMA_VERSION,
    HistoricalDiffResult,
    HistoricalSnapshot,
)
from repodna.schemas.models import RuleFinding


class EvolutionDiffEngine:
    """Computes architectural evolution diff between two historical snapshots."""

    @staticmethod
    def compare_snapshots(
        base: HistoricalSnapshot,
        head: HistoricalSnapshot,
        repo_path: Path | str | None = None,
    ) -> HistoricalDiffResult:
        """
        Computes detailed architectural diff between base and head snapshots.
        If repo_path is provided, queries Git for verified file renames (git diff -M).
        """
        base_modules = {m.path: m for m in base.modules}
        head_modules = {m.path: m for m in head.modules}

        base_paths = set(base_modules.keys())
        head_paths = set(head_modules.keys())

        raw_added = head_paths - base_paths
        raw_removed = base_paths - head_paths

        # Caveats check
        caveats: list[str] = []
        if base.is_shallow or head.is_shallow:
            caveats.append("One or both snapshots were taken in a shallow clone repository.")

        # 1. Detect renames
        git_renames: dict[str, str] = {}
        if repo_path:
            git_renames = EvolutionDiffEngine._query_git_renames(
                Path(repo_path), base.commit_sha, head.commit_sha
            )

        renamed: list[RenamedModule] = []
        confirmed_added: list[str] = []
        confirmed_removed: list[str] = sorted(raw_removed)

        # 1a. Verified renames from Git (content similarity match, not semantic proof)
        for old_p, new_p in git_renames.items():
            if old_p in confirmed_removed and new_p in raw_added:
                renamed.append(
                    RenamedModule(
                        old_path=old_p,
                        new_path=new_p,
                        confidence=0.90,
                        reason="Git history rename detection based on content similarity (syntactic match, not semantic identity)",
                        is_verified_by_git=True,
                    )
                )
                confirmed_removed.remove(old_p)
                raw_added.remove(new_p)

        # 1b. Candidate renames via heuristics (marked explicitly as candidate, NOT verified)
        for a_p in sorted(raw_added):
            a_mod = head_modules[a_p]
            match_found = False
            for r_p in list(confirmed_removed):
                r_mod = base_modules[r_p]
                if a_mod.name == r_mod.name and a_mod.language == r_mod.language:
                    # Same filename and language
                    loc_diff = abs(a_mod.lines_code - r_mod.lines_code)
                    confidence = 0.8 if loc_diff < 15 else 0.6
                    renamed.append(
                        RenamedModule(
                            old_path=r_p,
                            new_path=a_p,
                            confidence=confidence,
                            reason=f"Candidate heuristic match: identical name '{a_mod.name}' and language '{a_mod.language}' (unverified by Git)",
                            is_verified_by_git=False,
                        )
                    )
                    confirmed_removed.remove(r_p)
                    match_found = True
                    break
            if not match_found:
                confirmed_added.append(a_p)

        if any(r.is_verified_by_git for r in renamed):
            caveats.append(
                "Git-detected renames are based on content similarity heuristics and do not imply semantic identity."
            )
        if any(not r.is_verified_by_git for r in renamed):
            caveats.append(
                "Candidate renames are heuristic filename matches without Git tracking confirmation."
            )

        # 2. Dependency edges diff
        base_edge_map = {(e.source, e.target): e.import_names for e in base.dependencies}
        head_edge_map = {(e.source, e.target): e.import_names for e in head.dependencies}

        added_edges = [
            EdgeDiffItem(source=s, target=t, import_names=names)
            for (s, t), names in head_edge_map.items()
            if (s, t) not in base_edge_map
        ]
        removed_edges = [
            EdgeDiffItem(source=s, target=t, import_names=names)
            for (s, t), names in base_edge_map.items()
            if (s, t) not in head_edge_map
        ]

        # 3. Modified dependencies per module
        base_deps_by_src: dict[str, set[str]] = {}
        for e in base.dependencies:
            base_deps_by_src.setdefault(e.source, set()).add(e.target)

        head_deps_by_src: dict[str, set[str]] = {}
        for e in head.dependencies:
            head_deps_by_src.setdefault(e.source, set()).add(e.target)

        modified_deps: list[str] = []
        for path in sorted(base_paths & head_paths):
            b_targets = base_deps_by_src.get(path, set())
            h_targets = head_deps_by_src.get(path, set())
            if b_targets != h_targets:
                modified_deps.append(path)

        module_changes = ModuleChanges(
            added=sorted(confirmed_added),
            removed=sorted(confirmed_removed),
            renamed=renamed,
            modified_dependencies=modified_deps,
        )

        dependency_changes = DependencyChanges(
            added_edges=sorted(added_edges, key=lambda x: (x.source, x.target)),
            removed_edges=sorted(removed_edges, key=lambda x: (x.source, x.target)),
        )

        # 4. Cycle diff
        base_canon_cycles = {_canonicalize_cycle(c.nodes): c for c in base.cycles}
        head_canon_cycles = {_canonicalize_cycle(c.nodes): c for c in head.cycles}

        new_cycles: list[CycleDiffItem] = []
        for canon, c in head_canon_cycles.items():
            if canon not in base_canon_cycles:
                new_cycles.append(
                    CycleDiffItem(
                        id=c.id,
                        nodes=c.nodes,
                        length=c.length,
                        severity=c.severity,
                        description=c.description,
                    )
                )

        resolved_cycles: list[CycleDiffItem] = []
        for canon, c in base_canon_cycles.items():
            if canon not in head_canon_cycles:
                resolved_cycles.append(
                    CycleDiffItem(
                        id=c.id,
                        nodes=c.nodes,
                        length=c.length,
                        severity=c.severity,
                        description=c.description,
                    )
                )

        persisting_cycles = len(set(head_canon_cycles.keys()) & set(base_canon_cycles.keys()))
        cycle_changes = CycleChanges(
            new_cycles=new_cycles,
            resolved_cycles=resolved_cycles,
            persisting_cycles=persisting_cycles,
        )

        # 5. Coupling deltas
        coupling_deltas: list[CouplingDeltaItem] = []
        all_modules = sorted(base_paths | head_paths)
        for m_path in all_modules:
            b_c = base.coupling.get(m_path)
            h_c = head.coupling.get(m_path)

            fi_b = b_c.fan_in if b_c else 0
            fi_h = h_c.fan_in if h_c else 0
            fo_b = b_c.fan_out if b_c else 0
            fo_h = h_c.fan_out if h_c else 0
            inst_b = b_c.instability if b_c else 0.0
            inst_h = h_c.instability if h_c else 0.0

            if fi_b != fi_h or fo_b != fo_h or round(inst_b, 3) != round(inst_h, 3):
                coupling_deltas.append(
                    CouplingDeltaItem(
                        file_id=m_path,
                        fan_in_before=fi_b,
                        fan_in_after=fi_h,
                        fan_in_delta=fi_h - fi_b,
                        fan_out_before=fo_b,
                        fan_out_after=fo_h,
                        fan_out_delta=fo_h - fo_b,
                        instability_before=inst_b,
                        instability_after=inst_h,
                        instability_delta=round(inst_h - inst_b, 3),
                    )
                )

        # Sort coupling deltas by highest absolute fan-in delta or instability delta
        coupling_deltas.sort(key=lambda x: abs(x.fan_in_delta) + abs(x.fan_out_delta), reverse=True)

        # 6. Health delta
        score_b = base.health.score
        score_h = head.health.score
        score_delta = (
            round(score_h - score_b, 1) if score_b is not None and score_h is not None else None
        )
        health_delta = HealthScoreDelta(
            score_before=score_b,
            score_after=score_h,
            score_delta=score_delta,
            grade_before=base.health.grade,
            grade_after=head.health.grade,
            status_before=base.health.status,
            status_after=head.health.status,
        )

        # 7. Coverage delta
        cov_b = base.ast_loc_coverage_pct
        cov_h = head.ast_loc_coverage_pct
        coverage_delta = CoverageDelta(
            ast_loc_coverage_before=cov_b,
            ast_loc_coverage_after=cov_h,
            ast_loc_coverage_delta=round(cov_h - cov_b, 2),
            supported_langs_before=sorted(base.languages.keys()),
            supported_langs_after=sorted(head.languages.keys()),
        )

        # 8. Findings delta
        base_finding_keys = {(f.rule_id, tuple(sorted(f.affected_files))): f for f in base.findings}
        head_finding_keys = {(f.rule_id, tuple(sorted(f.affected_files))): f for f in head.findings}

        new_findings: list[RuleFinding] = [
            f for k, f in head_finding_keys.items() if k not in base_finding_keys
        ]
        resolved_findings: list[RuleFinding] = [
            f for k, f in base_finding_keys.items() if k not in head_finding_keys
        ]
        persisting_findings = len(set(head_finding_keys.keys()) & set(base_finding_keys.keys()))

        finding_changes = RuleFindingChanges(
            new_findings=new_findings,
            resolved_findings=resolved_findings,
            persisting_findings_count=persisting_findings,
        )

        # 9. Time delta calculation
        time_delta_display = EvolutionDiffEngine._compute_time_delta(
            base.commit_timestamp, head.commit_timestamp
        )

        # 10. Summary text
        summary_text = EvolutionDiffEngine._generate_summary(
            base=base,
            head=head,
            module_changes=module_changes,
            dependency_changes=dependency_changes,
            cycle_changes=cycle_changes,
            health_delta=health_delta,
            coverage_delta=coverage_delta,
            time_delta_display=time_delta_display,
        )

        return HistoricalDiffResult(
            schema_version=SNAPSHOT_SCHEMA_VERSION,
            base_commit_sha=base.commit_sha,
            head_commit_sha=head.commit_sha,
            base_timestamp=base.commit_timestamp,
            head_timestamp=head.commit_timestamp,
            time_delta_display=time_delta_display,
            module_changes=module_changes,
            dependency_changes=dependency_changes,
            cycle_changes=cycle_changes,
            coupling_deltas=coupling_deltas,
            health_delta=health_delta,
            coverage_delta=coverage_delta,
            finding_changes=finding_changes,
            caveats=caveats,
            summary_text=summary_text,
        )

    @staticmethod
    def _query_git_renames(repo_path: Path, base_sha: str, head_sha: str) -> dict[str, str]:
        """Queries git diff -M --name-status for verified file renames."""
        try:
            cmd = ["git", "-C", str(repo_path), "diff", "-M", "--name-status", base_sha, head_sha]
            out = subprocess.check_output(cmd, stderr=subprocess.PIPE, text=True, timeout=15.0)
            renames: dict[str, str] = {}
            for line in out.splitlines():
                parts = line.strip().split("\t")
                if len(parts) >= 3 and parts[0].startswith("R"):
                    renames[parts[1]] = parts[2]
            return renames
        except Exception:
            return {}

    @staticmethod
    def _compute_time_delta(ts_base: str, ts_head: str) -> str:
        try:
            # Handle ISO formats
            dt_base = datetime.fromisoformat(ts_base)
            dt_head = datetime.fromisoformat(ts_head)
            delta = dt_head - dt_base
            days = abs(delta.days)
            hours = abs(delta.seconds) // 3600
            mins = (abs(delta.seconds) % 3600) // 60
            direction = "+" if delta.total_seconds() >= 0 else "-"
            parts = []
            if days > 0:
                parts.append(f"{days}d")
            if hours > 0:
                parts.append(f"{hours}h")
            if mins > 0 or not parts:
                parts.append(f"{mins}m")
            return f"{direction}{' '.join(parts)}"
        except Exception:
            return "N/A"

    @staticmethod
    def _generate_summary(
        base: HistoricalSnapshot,
        head: HistoricalSnapshot,
        module_changes: ModuleChanges,
        dependency_changes: DependencyChanges,
        cycle_changes: CycleChanges,
        health_delta: HealthScoreDelta,
        coverage_delta: CoverageDelta,
        time_delta_display: str,
    ) -> str:
        lines = [
            "=" * 76,
            "RepoDNA Architecture Evolution Diff",
            "=" * 76,
            f"Base Commit : {base.commit_sha[:10]} ({base.commit_timestamp}) by {base.commit_author}",
            f"Head Commit : {head.commit_sha[:10]} ({head.commit_timestamp}) by {head.commit_author}",
            f"Time Delta  : {time_delta_display}",
            "-" * 76,
            "MODULE CHANGES:",
            f"  Added Modules   : {len(module_changes.added)}",
            f"  Removed Modules : {len(module_changes.removed)}",
            f"  Renamed Modules : {len(module_changes.renamed)}",
            f"  Modified Deps   : {len(module_changes.modified_dependencies)}",
            "-" * 76,
            "DEPENDENCY GRAPH:",
            f"  Added Edges     : {len(dependency_changes.added_edges)}",
            f"  Removed Edges   : {len(dependency_changes.removed_edges)}",
            "-" * 76,
            "ARCHITECTURAL CYCLES:",
            f"  New Cycles      : {len(cycle_changes.new_cycles)}",
            f"  Resolved Cycles : {len(cycle_changes.resolved_cycles)}",
            f"  Persisting      : {cycle_changes.persisting_cycles}",
            "-" * 76,
            "HEALTH & COVERAGE:",
            f"  Health Score    : {health_delta.score_before} -> {health_delta.score_after} ({health_delta.score_delta:+.1f} pts)"
            if health_delta.score_delta is not None
            else "  Health Score    : N/A",
            f"  Health Grade    : {health_delta.grade_before} -> {health_delta.grade_after}",
            f"  AST Coverage    : {coverage_delta.ast_loc_coverage_before:.1f}% -> {coverage_delta.ast_loc_coverage_after:.1f}% ({coverage_delta.ast_loc_coverage_delta:+.2f}%)",
            "=" * 76,
        ]
        return "\n".join(lines)
