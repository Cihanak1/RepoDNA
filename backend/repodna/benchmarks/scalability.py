"""Scalability and stress benchmark harness across Small, Medium, and Large repository scales.

Measures:
- Cold indexing latency
- Warm query latency (P50, P95)
- Repeated query latency & memory growth
- Large symbol tables, duplicate symbol names, deep directories
"""

from __future__ import annotations

import tempfile
import time
import tracemalloc
from pathlib import Path

from repodna.benchmarks.metrics import compute_percentile
from repodna.benchmarks.models import ScalabilityScaleResult
from repodna.brain.indexer import SymbolIndexer
from repodna.brain.retrieval import SmartRetrievalEngine


def _create_synthetic_repo(base_dir: Path, file_count: int, deep_paths: bool = False) -> None:
    """Generates synthetic multi-package source code files with symbols and imports."""
    packages = ["core", "api", "auth", "billing", "storage", "analytics", "workers", "common", "models", "utils"]
    for i in range(file_count):
        pkg = packages[i % len(packages)]
        if deep_paths:
            sub = f"sub_{i % 5}"
            level3 = f"deep_{(i * 7) % 11}"
            folder = base_dir / "src" / pkg / sub / level3
        else:
            folder = base_dir / pkg
        folder.mkdir(parents=True, exist_ok=True)

        idx = i + 1
        # Generates duplicate symbol names across different files to stress indexer disambiguation
        code = f'''"""Module {idx} in package {pkg}."""

class ServiceConfig:
    """Duplicate symbol config across packages."""
    def __init__(self, key: str = "key_{idx}"):
        self.key = key

class Entity_{idx}:
    """Entity model {idx}."""
    def __init__(self, id_val: int = {idx}):
        self.id_val = id_val

    def process_item_{idx}(self, value: int) -> int:
        return self.id_val + value

def handle_request_{idx}(payload: str) -> str:
    """Request handler {idx}."""
    cfg = ServiceConfig()
    return f"handled_{{cfg.key}}_{{payload}}"
'''
        (folder / f"module_{idx}.py").write_text(code, encoding="utf-8")


def benchmark_scale_tier(
    tier_name: str,
    repo_path: Path,
    expected_files: int,
    query_samples: list[str],
    timeout_seconds: float = 30.0,
) -> ScalabilityScaleResult:
    """Benchmarks a single scale tier with cold indexing, warm queries, and memory tracking."""
    tracemalloc.start()
    t_start = time.perf_counter()

    try:
        indexer = SymbolIndexer(root_path=repo_path, revision="SCALE_BENCH")
        t0 = time.perf_counter()
        indexer.index_all(max_files=expected_files + 500)
        cold_idx_ms = (time.perf_counter() - t0) * 1000.0

        current_mem, peak_mem = tracemalloc.get_traced_memory()
        peak_mb = round(peak_mem / (1024.0 * 1024.0), 2)

        engine = SmartRetrievalEngine(indexer=indexer)

        # Warm queries
        latencies: list[float] = []
        for q in query_samples:
            tq0 = time.perf_counter()
            engine.search(query=q, limit=5)
            latencies.append((time.perf_counter() - tq0) * 1000.0)

        p50 = compute_percentile(latencies, 50.0)
        p95 = compute_percentile(latencies, 95.0)

        # Repeated queries & memory growth test
        mem_before_repeat = tracemalloc.get_traced_memory()[0]
        rep_latencies: list[float] = []
        for _ in range(15):
            t_rep = time.perf_counter()
            engine.search(query=query_samples[0], limit=5)
            rep_latencies.append((time.perf_counter() - t_rep) * 1000.0)

        mem_after_repeat = tracemalloc.get_traced_memory()[0]
        mem_growth_mb = max(0.0, round((mem_after_repeat - mem_before_repeat) / (1024.0 * 1024.0), 2))
        avg_rep_ms = round(sum(rep_latencies) / len(rep_latencies), 2)

        total_symbols = len(indexer._symbols_by_id)
        total_files = len(indexer._symbols_by_file)

        status = "ok"
        if (time.perf_counter() - t_start) > timeout_seconds:
            status = "timeout"

        return ScalabilityScaleResult(
            scale_tier=tier_name,
            file_count=total_files,
            loc=total_files * 25,  # estimated or exact
            symbol_count=total_symbols,
            cold_indexing_ms=round(cold_idx_ms, 2),
            warm_query_p50_ms=p50,
            warm_query_p95_ms=p95,
            repeated_query_ms=avg_rep_ms,
            peak_memory_mb=peak_mb,
            memory_growth_mb=mem_growth_mb,
            status=status,
        )
    finally:
        tracemalloc.stop()


def run_scalability_benchmark(root_repo_path: Path) -> list[ScalabilityScaleResult]:
    """Runs complete 3-tier scalability benchmark: Small (20 files), Medium (RepoDNA), Large (1,000+ files)."""
    results: list[ScalabilityScaleResult] = []

    # Tier 1: Small (20 source files)
    with tempfile.TemporaryDirectory(prefix="repodna_bench_small_") as tmp_dir:
        tmp_p = Path(tmp_dir)
        _create_synthetic_repo(tmp_p, file_count=20, deep_paths=False)
        queries = ["ServiceConfig", "handle_request_5", "Entity_12 process_item", "analytics worker"]
        res_small = benchmark_scale_tier("Small (20 files)", tmp_p, 20, queries, timeout_seconds=15.0)
        results.append(res_small)

    # Tier 2: Medium (Real RepoDNA codebase — 148 files)
    med_queries = [
        "run_repository_analysis",
        "calculate_architecture_health",
        "ArchitectureDiffEngine",
        "where is authentication",
        "PRArchitectureGuardian assess",
    ]
    res_medium = benchmark_scale_tier("Medium (RepoDNA 148 files)", root_repo_path, 150, med_queries, timeout_seconds=60.0)
    results.append(res_medium)

    # Tier 3: Large (1,000+ files synthetic stress fixture)
    with tempfile.TemporaryDirectory(prefix="repodna_bench_large_") as tmp_dir:
        tmp_p = Path(tmp_dir)
        _create_synthetic_repo(tmp_p, file_count=1020, deep_paths=True)
        queries = [
            "ServiceConfig in storage",
            "handle_request_512",
            "Entity_800 process_item_800",
            "crypto vault config",
            "analytics worker",
        ]
        res_large = benchmark_scale_tier("Large (1,020 files synthetic)", tmp_p, 1020, queries, timeout_seconds=90.0)
        results.append(res_large)

    return results
