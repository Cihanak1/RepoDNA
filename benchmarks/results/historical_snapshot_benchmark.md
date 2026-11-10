# RepoDNA v0.6.0 — Historical Architecture Snapshot Engine Benchmark

**Repository:** `https://github.com/Cihanak1/RepoDNA`  
**Date:** 2026-11-10T22:56:54 UTC  
**Evaluated Commits:** 10 consecutive commits  

## Executive Performance Summary

| Metric | Measured Value | Target / Assessment |
| :--- | :--- | :--- |
| **Average Cold Snapshot Time** | **17.499 s** | Full AST parsing & evidence ledger extraction |
| **Average Cached Snapshot Time** | **249.50 ms** | Deterministic JSON disk cache retrieval |
| **Cache Retrieval Speedup** | **70.1x** | Instant timeline queries |
| **Average Pairwise Diff Time** | **61.86 ms** | Sub-50ms architectural delta calculation |
| **Peak Memory Footprint (RAM)** | **92.15 MB** | Highly bounded OS memory usage |
| **Total Disk Cache Size (10 snapshots)** | **8827.6 KB** | Bounded JSON schema envelope |

## Per-Commit Cold vs Cached Latency

| Commit | Files | LOC | Cold Time (s) | Cached Time (ms) | Peak RAM (MB) | Subject |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `000222b0f4` | 155 | 28,860 | 11.067 s | 217.10 ms | 63.1 MB | feat(brain): optimize retrieval with s |
| `2d7ed726b5` | 156 | 28,880 | 15.993 s | 229.60 ms | 67.8 MB | test(benchmarks): add independent 2nd  |
| `81fa9b7492` | 156 | 28,880 | 10.693 s | 327.40 ms | 69.9 MB | fix(benchmarks): use newline-normalize |
| `6deeb09fc8` | 165 | 32,922 | 17.998 s | 213.30 ms | 75.0 MB | feat(brain): implement intelligence wo |
| `5b0d22ada5` | 169 | 33,877 | 19.448 s | 264.70 ms | 78.5 MB | feat(hardening): path boundary securit |
| `99559a92a4` | 170 | 34,455 | 20.449 s | 243.20 ms | 82.0 MB | feat(release-gate): real external repo |
| `8371819b0d` | 170 | 34,458 | 19.907 s | 226.90 ms | 85.6 MB | fix(security): resolve cross-platform  |
| `f5b9c2cfe2` | 170 | 34,519 | 20.886 s | 257.50 ms | 86.9 MB | fix(cache): introduce deterministic co |
| `6527c64b18` | 170 | 34,519 | 19.707 s | 275.20 ms | 89.5 MB | Merge pull request #4 from Cihanak1/fe |
| `a3fbcd7efe` | 170 | 34,615 | 18.839 s | 240.30 ms | 92.2 MB | chore(release): prepare RepoDNA v0.5.0 |

## Pairwise Evolution Diff Latency & Churn

| Base -> Head | Diff Time (ms) | Git Changed Files | Modules Added | Modules Removed | Edges Added | Edges Removed |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `000222b0f4` -> `2d7ed726b5` | 56.46 ms | 26 | +1 | -0 | +0 | -0 |
| `2d7ed726b5` -> `81fa9b7492` | 49.09 ms | 2 | +0 | -0 | +0 | -0 |
| `81fa9b7492` -> `6deeb09fc8` | 53.03 ms | 29 | +9 | -0 | +43 | -0 |
| `6deeb09fc8` -> `5b0d22ada5` | 56.50 ms | 30 | +4 | -0 | +20 | -0 |
| `5b0d22ada5` -> `99559a92a4` | 59.64 ms | 19 | +1 | -0 | +8 | -0 |
| `99559a92a4` -> `8371819b0d` | 56.29 ms | 1 | +0 | -0 | +0 | -0 |
| `8371819b0d` -> `f5b9c2cfe2` | 97.50 ms | 3 | +0 | -0 | +1 | -0 |
| `f5b9c2cfe2` -> `6527c64b18` | 60.06 ms | 0 | +0 | -0 | +0 | -0 |
| `6527c64b18` -> `a3fbcd7efe` | 68.14 ms | 7 | +0 | -0 | +0 | -0 |

## Incremental Analysis Tradeoffs & Limitations in Large Git Histories

1. **Git Object Extraction Isolation**: `git archive` streaming extraction guarantees that untrusted past commit code is never executed, user working tree is untouched, and no lock contention occurs on `.git/worktrees`.
2. **Cache Determinism**: Disk cache keys incorporate `(repo_identity, commit_sha, analyzer_version, config_fingerprint)` with SHA-256 integrity verification, avoiding re-analysis on timeline requests.
3. **Incremental Parsing Bounds**: In very large histories (thousands of commits), analyzing every commit cold requires $O(N)$ full AST passes. An incremental delta-patch parser could inspect `git diff --name-only` between parents and children to re-parse only modified AST modules; however, without true cross-module semantic resolution for affected callers/callees, pure file-level incremental parsing can miss secondary dependency ripple effects. In Phase 1, full snapshot hashing with caching is prioritized for absolute correctness over speculative incremental shortcuts.