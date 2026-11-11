# RepoDNA v0.6.0 — Historical Architecture Snapshot Engine Benchmark

**Repository:** `https://github.com/Cihanak1/RepoDNA`  
**Date:** 2026-11-11T10:15:23 UTC  
**Evaluated Commits:** 10 consecutive commits  

## Executive Performance Summary

| Metric | Measured Value | Target / Assessment |
| :--- | :--- | :--- |
| **Average Cold Snapshot Time** | **17.729 s** | Full AST parsing & evidence ledger extraction |
| **Average Cached Snapshot Time** | **227.30 ms** | Deterministic JSON disk cache retrieval |
| **Cache Retrieval Speedup** | **78.0x** | Instant timeline queries |
| **Average Pairwise Diff Time** | **78.32 ms** | Sub-50ms architectural delta calculation |
| **Peak Memory Footprint (RAM)** | **94.71 MB** | Highly bounded OS memory usage |
| **Total Disk Cache Size (10 snapshots)** | **9059.6 KB** | Bounded JSON schema envelope |

## Per-Commit Cold vs Cached Latency

| Commit | Files | LOC | Cold Time (s) | Cached Time (ms) | Peak RAM (MB) | Subject |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `2d7ed726b5` | 156 | 28,880 | 14.573 s | 180.50 ms | 63.3 MB | test(benchmarks): add independent 2nd  |
| `81fa9b7492` | 156 | 28,880 | 15.771 s | 242.10 ms | 67.5 MB | fix(benchmarks): use newline-normalize |
| `6deeb09fc8` | 165 | 32,922 | 16.666 s | 256.30 ms | 72.5 MB | feat(brain): implement intelligence wo |
| `5b0d22ada5` | 169 | 33,877 | 17.848 s | 171.40 ms | 76.7 MB | feat(hardening): path boundary securit |
| `99559a92a4` | 170 | 34,455 | 18.269 s | 262.60 ms | 79.5 MB | feat(release-gate): real external repo |
| `8371819b0d` | 170 | 34,458 | 19.378 s | 210.10 ms | 83.4 MB | fix(security): resolve cross-platform  |
| `f5b9c2cfe2` | 170 | 34,519 | 19.006 s | 215.70 ms | 84.5 MB | fix(cache): introduce deterministic co |
| `6527c64b18` | 170 | 34,519 | 18.006 s | 248.20 ms | 87.4 MB | Merge pull request #4 from Cihanak1/fe |
| `a3fbcd7efe` | 170 | 34,615 | 17.693 s | 271.90 ms | 92.5 MB | chore(release): prepare RepoDNA v0.5.0 |
| `b2e76d67ce` | 179 | 36,999 | 20.082 s | 214.50 ms | 94.7 MB | feat(history): implement historical ar |

## Pairwise Evolution Diff Latency & Churn

| Base -> Head | Diff Time (ms) | Git Changed Files | Modules Added | Modules Removed | Edges Added | Edges Removed |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `2d7ed726b5` -> `81fa9b7492` | 65.04 ms | 2 | +0 | -0 | +0 | -0 |
| `81fa9b7492` -> `6deeb09fc8` | 87.01 ms | 29 | +9 | -0 | +43 | -0 |
| `6deeb09fc8` -> `5b0d22ada5` | 97.90 ms | 30 | +4 | -0 | +20 | -0 |
| `5b0d22ada5` -> `99559a92a4` | 63.15 ms | 19 | +1 | -0 | +8 | -0 |
| `99559a92a4` -> `8371819b0d` | 58.54 ms | 1 | +0 | -0 | +0 | -0 |
| `8371819b0d` -> `f5b9c2cfe2` | 82.79 ms | 3 | +0 | -0 | +1 | -0 |
| `f5b9c2cfe2` -> `6527c64b18` | 74.59 ms | 0 | +0 | -0 | +0 | -0 |
| `6527c64b18` -> `a3fbcd7efe` | 71.63 ms | 7 | +0 | -0 | +0 | -0 |
| `a3fbcd7efe` -> `b2e76d67ce` | 104.24 ms | 13 | +9 | -0 | +42 | -0 |

## Incremental Analysis Tradeoffs & Limitations in Large Git Histories

1. **Git Object Extraction Isolation**: `git archive` streaming extraction guarantees that untrusted past commit code is never executed, user working tree is untouched, and no lock contention occurs on `.git/worktrees`.
2. **Cache Determinism**: Disk cache keys incorporate `(repo_identity, commit_sha, analyzer_version, config_fingerprint)` with SHA-256 integrity verification, avoiding re-analysis on timeline requests.
3. **Incremental Parsing Bounds**: In very large histories (thousands of commits), analyzing every commit cold requires $O(N)$ full AST passes. An incremental delta-patch parser could inspect `git diff --name-only` between parents and children to re-parse only modified AST modules; however, without true cross-module semantic resolution for affected callers/callees, pure file-level incremental parsing can miss secondary dependency ripple effects. In Phase 1, full snapshot hashing with caching is prioritized for absolute correctness over speculative incremental shortcuts.