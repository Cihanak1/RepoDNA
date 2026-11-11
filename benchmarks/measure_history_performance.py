"""Benchmark performance and resource consumption of the Historical Architecture Snapshot Engine.

Measures:
- Cold snapshot time across 10 real commits in RepoDNA Git history
- Cached snapshot retrieval time
- Pairwise evolution diff time
- Peak RAM footprint via OS process counters
- Disk cache size and entry bounds
- Changed files count per commit step
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from datetime import UTC, datetime
from pathlib import Path

from repodna.history.cache import HistoricalCache
from repodna.history.diff import EvolutionDiffEngine
from repodna.history.engine import HistoricalSnapshotEngine


def get_peak_memory_mb() -> float:
    """Returns peak working set (RSS) in MB across Windows/Linux without tracer overhead."""
    if os.name == "nt":
        import ctypes
        from ctypes import wintypes

        class PROCESS_MEMORY_COUNTERS(ctypes.Structure):
            _fields_ = [
                ("cb", wintypes.DWORD),
                ("PageFaultCount", wintypes.DWORD),
                ("PeakWorkingSetSize", ctypes.c_size_t),
                ("WorkingSetSize", ctypes.c_size_t),
                ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                ("PagefileUsage", ctypes.c_size_t),
                ("PeakPagefileUsage", ctypes.c_size_t),
            ]

        try:
            psapi = ctypes.WinDLL("psapi")
            kernel32 = ctypes.WinDLL("kernel32")
            get_current_process = kernel32.GetCurrentProcess
            get_current_process.restype = wintypes.HANDLE
            get_memory_info = psapi.GetProcessMemoryInfo
            get_memory_info.argtypes = [
                wintypes.HANDLE,
                ctypes.POINTER(PROCESS_MEMORY_COUNTERS),
                wintypes.DWORD,
            ]
            get_memory_info.restype = wintypes.BOOL

            pmc = PROCESS_MEMORY_COUNTERS()
            pmc.cb = ctypes.sizeof(PROCESS_MEMORY_COUNTERS)
            if get_memory_info(get_current_process(), ctypes.byref(pmc), pmc.cb):
                return round(pmc.PeakWorkingSetSize / (1024 * 1024), 2)
        except Exception:
            pass
        return 0.0
    else:
        try:
            import resource

            ru = resource.getrusage(resource.RUSAGE_SELF)
            # macOS returns bytes, Linux returns kilobytes
            divisor = (1024 * 1024) if sys.platform == "darwin" else 1024
            return round(ru.ru_maxrss / divisor, 2)
        except Exception:
            return 0.0


def run_benchmark(repo_path: Path, num_commits: int = 10) -> dict:
    repo_path = repo_path.resolve()

    # Get commit list
    cmd = ["git", "-C", str(repo_path), "log", f"-n{num_commits}", "--format=%H%x1f%s"]
    out = subprocess.check_output(cmd, text=True).strip()
    commits = []
    for line in out.splitlines():
        if line.strip():
            sha, msg = line.split("\x1f", 1)
            commits.append({"sha": sha, "subject": msg})

    # Reverse to chronological order (oldest to newest)
    commits.reverse()
    print(f"Loaded {len(commits)} historical commits for benchmarking.")

    temp_cache_dir = tempfile.mkdtemp(prefix="repodna_bench_cache_")
    try:
        cache = HistoricalCache(temp_cache_dir)
        engine = HistoricalSnapshotEngine(repo_path=repo_path, cache_dir=temp_cache_dir)

        cold_times = []
        cached_times = []
        snapshots = []
        peak_rams_mb = []

        # 1. Measure Cold & Cached Snapshot Latencies
        for idx, c in enumerate(commits, 1):
            sha = c["sha"]
            print(
                f"[{idx}/{len(commits)}] Benchmarking commit {sha[:10]}: {c['subject'][:40]}...",
                flush=True,
            )

            # Cold analysis (bypassing cache)
            t0 = time.perf_counter()
            cold_snap = engine.create_snapshot(sha, use_cache=False)
            t_cold = time.perf_counter() - t0
            peak_mb = get_peak_memory_mb()

            # Store in cache
            cache_key = HistoricalCache.generate_key(engine.repo_identity, sha)
            cache.put(cache_key, cold_snap)

            # Cached retrieval
            t0_cached = time.perf_counter()
            cached_snap = engine.create_snapshot(sha, use_cache=True)
            t_cached = time.perf_counter() - t0_cached

            assert cached_snap.cache_hit is True
            cold_times.append(t_cold)
            cached_times.append(t_cached)
            snapshots.append(cached_snap)
            peak_rams_mb.append(peak_mb)
            print(
                f"    -> Cold: {t_cold:.2f}s | Cached: {t_cached * 1000:.2f}ms | RAM: {peak_mb:.1f} MB",
                flush=True,
            )

        # 2. Measure Pairwise Diff Latencies
        pairwise_diffs = []
        for i in range(len(snapshots) - 1):
            base_s = snapshots[i]
            head_s = snapshots[i + 1]

            # Changed files count via git diff
            diff_cmd = [
                "git",
                "-C",
                str(repo_path),
                "diff",
                "--name-only",
                base_s.commit_sha,
                head_s.commit_sha,
            ]
            diff_out = subprocess.check_output(diff_cmd, text=True).strip()
            changed_files_count = len([line for line in diff_out.splitlines() if line.strip()])

            t0_diff = time.perf_counter()
            diff_res = EvolutionDiffEngine.compare_snapshots(
                base=base_s, head=head_s, repo_path=repo_path
            )
            t_diff = time.perf_counter() - t0_diff

            pairwise_diffs.append(
                {
                    "base_sha": base_s.commit_sha[:10],
                    "head_sha": head_s.commit_sha[:10],
                    "diff_time_ms": round(t_diff * 1000, 2),
                    "changed_files_git": changed_files_count,
                    "added_modules": len(diff_res.module_changes.added),
                    "removed_modules": len(diff_res.module_changes.removed),
                    "renamed_modules": len(diff_res.module_changes.renamed),
                    "added_edges": len(diff_res.dependency_changes.added_edges),
                    "removed_edges": len(diff_res.dependency_changes.removed_edges),
                }
            )

        cache_stats = cache.get_stats()

        avg_cold = sum(cold_times) / len(cold_times)
        avg_cached = sum(cached_times) / len(cached_times)
        avg_diff = sum(p["diff_time_ms"] for p in pairwise_diffs) / len(pairwise_diffs)
        max_ram = max(peak_rams_mb)

        results = {
            "timestamp": datetime.now(UTC).isoformat(),
            "repository": engine.repo_identity,
            "evaluated_commits_count": len(commits),
            "metrics": {
                "avg_cold_snapshot_sec": round(avg_cold, 3),
                "min_cold_snapshot_sec": round(min(cold_times), 3),
                "max_cold_snapshot_sec": round(max(cold_times), 3),
                "avg_cached_snapshot_sec": round(avg_cached, 4),
                "cached_speedup_factor": round(avg_cold / max(avg_cached, 0.0001), 1),
                "avg_pairwise_diff_ms": round(avg_diff, 2),
                "peak_ram_mb": round(max_ram, 2),
                "total_cache_entries": cache_stats["total_entries"],
                "total_cache_size_kb": round(cache_stats["total_size_bytes"] / 1024, 1),
            },
            "per_commit_benchmarks": [
                {
                    "commit_sha": c["sha"][:10],
                    "subject": c["subject"],
                    "files": s.total_files,
                    "loc": s.total_lines_code,
                    "cold_time_sec": round(t_c, 3),
                    "cached_time_sec": round(t_ch, 4),
                    "peak_ram_mb": round(ram, 2),
                }
                for c, s, t_c, t_ch, ram in zip(
                    commits, snapshots, cold_times, cached_times, peak_rams_mb, strict=True
                )
            ],
            "pairwise_diffs": pairwise_diffs,
        }

        return results

    finally:
        shutil.rmtree(temp_cache_dir, ignore_errors=True)


def generate_markdown(results: dict) -> str:
    m = results["metrics"]
    lines = [
        "# RepoDNA v0.6.0 — Historical Architecture Snapshot Engine Benchmark",
        "",
        f"**Repository:** `{results['repository']}`  ",
        f"**Date:** {results['timestamp'][:19]} UTC  ",
        f"**Evaluated Commits:** {results['evaluated_commits_count']} consecutive commits  ",
        "",
        "## Executive Performance Summary",
        "",
        "| Metric | Measured Value | Target / Assessment |",
        "| :--- | :--- | :--- |",
        f"| **Average Cold Snapshot Time** | **{m['avg_cold_snapshot_sec']:.3f} s** | Full AST parsing & evidence ledger extraction |",
        f"| **Average Cached Snapshot Time** | **{m['avg_cached_snapshot_sec'] * 1000:.2f} ms** | Deterministic JSON disk cache retrieval |",
        f"| **Cache Retrieval Speedup** | **{m['cached_speedup_factor']}x** | Instant timeline queries |",
        f"| **Average Pairwise Diff Time** | **{m['avg_pairwise_diff_ms']:.2f} ms** | Sub-50ms architectural delta calculation |",
        f"| **Peak Memory Footprint (RAM)** | **{m['peak_ram_mb']:.2f} MB** | Highly bounded OS memory usage |",
        f"| **Total Disk Cache Size (10 snapshots)** | **{m['total_cache_size_kb']:.1f} KB** | Bounded JSON schema envelope |",
        "",
        "## Per-Commit Cold vs Cached Latency",
        "",
        "| Commit | Files | LOC | Cold Time (s) | Cached Time (ms) | Peak RAM (MB) | Subject |",
        "| :--- | :--- | :--- | :--- | :--- | :--- | :--- |",
    ]
    for c in results["per_commit_benchmarks"]:
        lines.append(
            f"| `{c['commit_sha']}` | {c['files']} | {c['loc']:,} | {c['cold_time_sec']:.3f} s | {c['cached_time_sec'] * 1000:.2f} ms | {c['peak_ram_mb']:.1f} MB | {c['subject'][:38]} |"
        )

    lines.extend(
        [
            "",
            "## Pairwise Evolution Diff Latency & Churn",
            "",
            "| Base -> Head | Diff Time (ms) | Git Changed Files | Modules Added | Modules Removed | Edges Added | Edges Removed |",
            "| :--- | :--- | :--- | :--- | :--- | :--- | :--- |",
        ]
    )
    for p in results["pairwise_diffs"]:
        lines.append(
            f"| `{p['base_sha']}` -> `{p['head_sha']}` | {p['diff_time_ms']:.2f} ms | {p['changed_files_git']} | +{p['added_modules']} | -{p['removed_modules']} | +{p['added_edges']} | -{p['removed_edges']} |"
        )

    lines.extend(
        [
            "",
            "## Incremental Analysis Tradeoffs & Limitations in Large Git Histories",
            "",
            "1. **Git Object Extraction Isolation**: `git archive` streaming extraction guarantees that untrusted past commit code is never executed, user working tree is untouched, and no lock contention occurs on `.git/worktrees`.",
            "2. **Cache Determinism**: Disk cache keys incorporate `(repo_identity, commit_sha, analyzer_version, config_fingerprint)` with SHA-256 integrity verification, avoiding re-analysis on timeline requests.",
            "3. **Incremental Parsing Bounds**: In very large histories (thousands of commits), analyzing every commit cold requires $O(N)$ full AST passes. An incremental delta-patch parser could inspect `git diff --name-only` between parents and children to re-parse only modified AST modules; however, without true cross-module semantic resolution for affected callers/callees, pure file-level incremental parsing can miss secondary dependency ripple effects. In Phase 1, full snapshot hashing with caching is prioritized for absolute correctness over speculative incremental shortcuts.",
        ]
    )

    return "\n".join(lines)


if __name__ == "__main__":
    target = Path(sys.argv[1] if len(sys.argv) > 1 else ".")
    res = run_benchmark(target, num_commits=10)

    out_json = target / "benchmarks" / "results" / "historical_snapshot_benchmark.json"
    out_md = target / "benchmarks" / "results" / "historical_snapshot_benchmark.md"

    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(res, indent=2), encoding="utf-8")
    out_md.write_text(generate_markdown(res), encoding="utf-8")

    print(f"\nBenchmark results written to:\n  - {out_json}\n  - {out_md}")
