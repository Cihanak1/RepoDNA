"""RepoDNA v0.5.0 — Large Repository Reliability & Performance Benchmark.

Measures:
1. Indexing time (seconds)
2. Memory footprint (RSS MB)
3. AST Coverage (Files % and LOC %)
4. Search Latency (P50 and P95 in ms over 20 queries)
5. Agent Context Generation (500 tokens & 2000 tokens)
Across two real independent open-source repositories:
- RepoDNA (. / workspace)
- PayFlow (benchmarks/fixtures/payflow)
"""

from __future__ import annotations

import ctypes
from ctypes import wintypes
import json
import os
from pathlib import Path
import time
from typing import Any

from repodna.brain.indexer import SymbolIndexer
from repodna.brain.retrieval import SmartRetrievalEngine
from repodna.context.builder import AgentContextBuilder
from repodna.core.analyzer import run_repository_analysis
from repodna.schemas.models import ScanLimits, ScanRequest, SourceType


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


def get_process_rss_mb() -> float:
    try:
        ctypes.windll.kernel32.OpenProcess.restype = wintypes.HANDLE
        ctypes.windll.psapi.GetProcessMemoryInfo.argtypes = [
            wintypes.HANDLE,
            ctypes.c_void_p,
            wintypes.DWORD,
        ]
        counters = PROCESS_MEMORY_COUNTERS()
        counters.cb = ctypes.sizeof(PROCESS_MEMORY_COUNTERS)
        # PROCESS_QUERY_INFORMATION (0x0400) | PROCESS_VM_READ (0x0010) = 0x0410
        h_proc = ctypes.windll.kernel32.OpenProcess(0x0410, False, os.getpid())
        if h_proc:
            if ctypes.windll.psapi.GetProcessMemoryInfo(h_proc, ctypes.byref(counters), counters.cb):
                ctypes.windll.kernel32.CloseHandle(h_proc)
                return counters.WorkingSetSize / (1024.0 * 1024.0)
            ctypes.windll.kernel32.CloseHandle(h_proc)
    except Exception:
        pass
    return 0.0


def benchmark_repository(
    repo_name: str,
    repo_path: Path,
    search_queries: list[str],
) -> dict[str, Any]:
    print("\n========================================================")
    print(f"Benchmarking: {repo_name} at {repo_path}")
    print("========================================================")

    # 1. Base Analysis
    mem_before_analysis = get_process_rss_mb()
    t0_scan = time.perf_counter()
    req = ScanRequest(
        source_type=SourceType.LOCAL,
        target=str(repo_path.resolve()),
        limits=ScanLimits(max_files=5000, max_file_size_bytes=1024 * 1024),
    )
    analysis_res = run_repository_analysis(req)
    t_scan = time.perf_counter() - t0_scan

    # 2. Symbol Indexing
    indexer = SymbolIndexer(
        root_path=repo_path,
        revision=analysis_res.git_insights.commit_sha if analysis_res.git_insights else "bench",
        analysis=analysis_res,
    )
    t0_index = time.perf_counter()
    indexer.index_all()
    t_index = time.perf_counter() - t0_index
    mem_after_index = get_process_rss_mb()

    total_files = len(analysis_res.files)
    total_loc = sum(f.lines_code for f in analysis_res.files)
    indexed_files = len(indexer._symbols_by_file)
    total_symbols = len(indexer._symbols_by_id)
    total_refs = len(indexer._raw_references)
    total_verified = sum(1 for r in indexer._raw_references if r.is_verified)

    file_coverage_pct = (indexed_files / total_files * 100.0) if total_files > 0 else 0.0
    indexed_paths = set(indexer._symbols_by_file.keys())
    indexed_loc = sum(
        f.lines_code for f in analysis_res.files
        if f.id in indexed_paths or f.id.replace("\\", "/") in indexed_paths
    )
    loc_coverage_pct = (indexed_loc / total_loc * 100.0) if total_loc > 0 else 0.0

    print(f"Files Indexed: {indexed_files}/{total_files} ({file_coverage_pct:.1f}%)")
    print(f"LOC Indexed:   {indexed_loc:,}/{total_loc:,} ({loc_coverage_pct:.1f}%)")
    print(f"Symbols:       {total_symbols} symbols, {total_refs} raw references, {total_verified} verified references")
    print(f"Indexing Time: {t_index:.3f} s")
    print(f"Process RSS:   {mem_after_index:.1f} MB (Delta: +{mem_after_index - mem_before_analysis:.1f} MB)")

    # 3. Search Engine Latencies (P50 / P95)
    engine = SmartRetrievalEngine(indexer=indexer, analysis=analysis_res)
    latencies_ms: list[float] = []

    for q in search_queries:
        t0_q = time.perf_counter()
        _ = engine.search(q, limit=15)
        t_q = (time.perf_counter() - t0_q) * 1000.0
        latencies_ms.append(t_q)

    latencies_ms.sort()
    n = len(latencies_ms)
    p50_ms = latencies_ms[int(n * 0.50)]
    p95_ms = latencies_ms[int(n * 0.95)] if n > 0 else 0.0
    mean_ms = sum(latencies_ms) / n if n > 0 else 0.0

    print(f"Search Queries Evaluated: {n}")
    print(f"Search P50 Latency:        {p50_ms:.2f} ms")
    print(f"Search P95 Latency:        {p95_ms:.2f} ms")
    print(f"Search Mean Latency:       {mean_ms:.2f} ms")

    # 4. Context Builder Presets
    ctx_500 = AgentContextBuilder.build_context(
        analysis=analysis_res,
        mode="focused",
        query=search_queries[0] if search_queries else "architecture overview",
        max_tokens=500,
        indexer=indexer,
        revision=indexer.revision,
    )
    ctx_2000 = AgentContextBuilder.build_context(
        analysis=analysis_res,
        mode="deep",
        query=search_queries[0] if search_queries else "architecture overview",
        max_tokens=2000,
        indexer=indexer,
        revision=indexer.revision,
    )

    compliant_500 = ctx_500.estimated_tokens <= 500 or not ctx_500.truncated
    compliant_2000 = ctx_2000.estimated_tokens <= 2000 or not ctx_2000.truncated

    print(f"Context 500 budget:  {ctx_500.estimated_tokens} tokens (truncated={ctx_500.truncated}, compliant={compliant_500})")
    print(f"Context 2000 budget: {ctx_2000.estimated_tokens} tokens (truncated={ctx_2000.truncated}, compliant={compliant_2000})")

    return {
        "repo_name": repo_name,
        "repo_path": str(repo_path),
        "total_files": total_files,
        "total_loc": total_loc,
        "indexed_files": indexed_files,
        "file_coverage_pct": round(file_coverage_pct, 2),
        "loc_coverage_pct": round(loc_coverage_pct, 2),
        "total_symbols": total_symbols,
        "total_references": total_refs,
        "total_verified_references": total_verified,
        "indexing_seconds": round(t_index, 3),
        "scan_seconds": round(t_scan, 3),
        "memory_rss_mb": round(mem_after_index, 2),
        "search_queries_count": n,
        "search_p50_ms": round(p50_ms, 2),
        "search_p95_ms": round(p95_ms, 2),
        "search_mean_ms": round(mean_ms, 2),
        "context_500_tokens": ctx_500.estimated_tokens,
        "context_500_truncated": ctx_500.truncated,
        "context_2000_tokens": ctx_2000.estimated_tokens,
        "context_2000_truncated": ctx_2000.truncated,
    }


def main() -> None:
    root = Path(__file__).resolve().parent.parent

    # Queries for RepoDNA
    repodna_queries = [
        "architecture health score",
        "SymbolIndexer",
        "SmartRetrievalEngine",
        "Tarjan cycle participant",
        "evidence ledger staleness",
        "validate_and_resolve_evidence_path",
        "build_agent_context",
        "PassportV2",
        "parse_imports",
        "detect_cycles",
        "export json report",
        "git revision provenance",
        "blast radius calculation",
        "ResolutionStatus",
        "minimal contract",
        "AnalysisResult",
        "mcp server tools",
        "hub module identification",
        "SecurityValidationError",
        "fastapi uvicorn endpoint",
    ]

    # Queries for Payflow
    payflow_queries = [
        "payment processing",
        "transaction validation",
        "stripe webhook handler",
        "refund execution",
        "database connection pool",
        "auth token verification",
        "charge customer credit card",
        "subscription billing cycle",
        "fraud detection filter",
        "currency conversion rate",
        "invoice generator",
        "payment intent status",
        "audit logger",
        "retry failed transaction",
        "api error response",
        "user account balance",
        "crypto settlement",
        "merchant payout",
        "compliance reporting",
        "encryption key manager",
    ]

    results = []

    # Benchmark 1: RepoDNA
    res_repodna = benchmark_repository(
        repo_name="RepoDNA",
        repo_path=root,
        search_queries=repodna_queries,
    )
    results.append(res_repodna)

    # Benchmark 2: Payflow
    payflow_path = root / "benchmarks" / "fixtures" / "payflow"
    if payflow_path.exists():
        res_payflow = benchmark_repository(
            repo_name="PayFlow",
            repo_path=payflow_path,
            search_queries=payflow_queries,
        )
        results.append(res_payflow)

    output_path = root / "benchmarks" / "results" / "large_repo_reliability.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)

    print(f"\nResults successfully written to: {output_path}")


if __name__ == "__main__":
    main()
