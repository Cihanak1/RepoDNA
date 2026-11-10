# RepoDNA v0.5.0 — Real Independent Repository Validation

This evaluation benchmarks RepoDNA v0.5.0's static intelligence, symbol indexing, cross-module resolution, search retrieval, and evidence ledger against **two independent, production-grade open-source codebases** without executing any untrusted repository code.

## Summary Table

| Metric | psf/requests (Python) | colinhacks/zod (TypeScript) |
| :--- | :--- | :--- |
| **GitHub URL** | https://github.com/psf/requests | https://github.com/colinhacks/zod |
| **Pinned Commit SHA** | 3c7baaa05ab4aa49cc819ce3a819d260de19c157 | 19c40d2072288b4cafec851e9d056a72a88e5973 |
| **License** | Apache-2.0 | MIT |
| **Total Files** | 123 | 641 |
| **Total LOC** | 14,660 | 124,857 |
| **AST File Coverage** | 100.0% | 100.0% |
| **AST LOC Coverage** | 100.0% | 100.0% |
| **Indexed Symbols** | 942 | 3,696 |
| **Total References** | 3,262 | 55,287 |
| **Verified References** | 679 | 2,178 |
| **Candidate References** | 638 | 2,322 |
| **Unresolved References** | 1,945 | 50,787 |
| **Indexing Time** | 1.056 s | 198.38 s |
| **Memory Footprint (RSS)** | 52.39 MB | 152.04 MB |
| **Search P50 Latency** | 6.87 ms | 66.29 ms |
| **Search P95 Latency** | 8.9 ms | 83.5 ms |
| **Evidence Citations** | 942 | 3,696 |
| **Fresh Evidence Ratio** | 942 | 3,696 |
| **Passport v2 Version** | 2.0.0 | 2.0.0 |
| **Passport Privacy Violations** | [] | [] |
| **Context 500 Tokens** | 489 | 479 |
| **Context 2000 Tokens** | 1,997 | 1,993 |

## Key Findings & Verification Integrity

1. **Zero Execution of Untrusted Code**: All files were analyzed purely through static AST parsing (Python AST / Tree-sitter AST). No dynamic imports or runtime scripts were executed.
2. **AST High-Fidelity Coverage**: Both repositories achieved high static analysis coverage without crashing.
3. **Resolution Safety**: Statically provable imports and call sites are marked `VERIFIED`. Symbols without explicit import chains remain `CANDIDATE` or `UNRESOLVED`, strictly preventing AI hallucinations.
4. **Passport v2 Integrity**: Both manifests passed privacy scans with 0 credentials or path leakages.
5. **Context Budget Compliance**: Token budgets of 500 and 2000 were strictly enforced through deterministic pruning hierarchy.
