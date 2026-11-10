# RepoDNA Code Intelligence Benchmark — Phase 2 Evaluation Report

- **Benchmark Version:** `v1.0`
- **Commit SHA:** `507ca83adae4bcc55340ec022fa8346d31f7348a`
- **Evaluated At:** `2026-11-10T00:19:23.285165+00:00`
- **Environment:** Windows (AMD64), Python 3.12.10
- **Dataset:** `C:\Users\cihan\Desktop\RepoDNA\benchmarks\retrieval-v1.jsonl` (55 queries: 43 dev, 12 holdout)

## 1. Executive Summary & Baseline Comparison

Does **Repository Brain** actually outperform naive filename search and substring symbol search?

| Method | Hit@1 (%) | Hit@3 (%) | Hit@5 (%) | MRR | Precision@1 | Recall@3 | nDCG@5 | Negative Abstention (%) | P50 Latency (ms) |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| filename_only | **29.79** | **48.94** | **53.19** | **0.3936** | 0.2979 | 0.4681 | **0.4152** | 75.0% | 0.16 ms |
| symbol_only | **12.77** | **27.66** | **38.3** | **0.2092** | 0.1277 | 0.2766 | **0.2516** | 25.0% | 4.41 ms |
| **Repository Brain (RepoDNA)** | **27.66** | **44.68** | **53.19** | **0.3582** | 0.2766 | 0.4362 | **0.3959** | 25.0% | 17.69 ms |

## 2. Dev vs Holdout Generalization

| Split | Method | Hit@1 (%) | Hit@3 (%) | MRR | nDCG@5 | Negative Abstention (%) |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: |
| Dev Split | filename_only | 32.5% | 50.0% | 0.4104 | 0.43 | 66.67% |
| Dev Split | symbol_only | 12.5% | 30.0% | 0.2208 | 0.2707 | 33.33% |
| Dev Split | repository_brain | 25.0% | 45.0% | 0.3458 | 0.3902 | 33.33% |
| Holdout Split | filename_only | 14.29% | 42.86% | 0.2976 | 0.3311 | 80.0% |
| Holdout Split | symbol_only | 14.29% | 14.29% | 0.1429 | 0.1429 | 20.0% |
| Holdout Split | repository_brain | 42.86% | 42.86% | 0.4286 | 0.4286 | 20.0% |

## 3. Symbol Reference Fidelity Audit

- **Verified Reference Precision:** `100.0%`
- **False Verified Reference Count:** `0`
- **Unresolved Reference Count:** `7487` (calls correctly left unresolved due to insufficient static AST proof)
- **Cold Indexing Time:** `18407.04 ms`
- **Warm Indexing Time:** `1960.88 ms`
- **Peak Memory Usage:** `20.21 MB`

## 4. Token Budget Compliance Matrix

| Requested `max_tokens` | Counted Tokens | Method | Compliant? | Truncated? | Deterministic? | Duration | Notes |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :--- |
| `0` | 0 | `heuristic_zero_budget` | **PASS** | Yes | Yes | 0.27 ms | Zero budget: correctly flagged as truncated with minimal metadata notice. |
| `10` | 154 | `heuristic_chars` | **PASS** | Yes | Yes | 10.19 ms | Small budget (10 tokens): minimal metadata exceeds target; truncation flagged. |
| `25` | 154 | `heuristic_chars` | **PASS** | Yes | Yes | 10.62 ms | Small budget (25 tokens): minimal metadata exceeds target; truncation flagged. |
| `60` | 154 | `heuristic_chars` | **PASS** | Yes | Yes | 9.69 ms | Tight budget (60 tokens): successfully pruned down to essential summary. |
| `500` | 465 | `heuristic_chars` | **PASS** | Yes | Yes | 8.48 ms | Generous budget (500 tokens): consumed 465 tokens safely. |
| `2000` | 1305 | `heuristic_chars` | **PASS** | Yes | Yes | 1.8 ms | Generous budget (2000 tokens): consumed 1305 tokens safely. |

## 5. Scalability & Stress Benchmark

| Tier | Files | LOC (est) | Symbols | Cold Index | Warm P50 | Warm P95 | Repeat Query | Peak RAM | Mem Growth | Status |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **Small (20 files)** | 20 | 500 | 120 | 254.24 ms | 8.79 ms | 12.56 ms | 7.66 ms | 0.5 MB | 0.0 MB | `ok` |
| **Medium (RepoDNA 148 files)** | 120 | 3000 | 707 | 18018.87 ms | 196.95 ms | 208.17 ms | 188.31 ms | 17.64 MB | 0.0 MB | `ok` |
| **Large (1,020 files synthetic)** | 1020 | 25500 | 6120 | 15495.74 ms | 501.53 ms | 695.2 ms | 490.24 ms | 23.42 MB | 0.0 MB | `ok` |

## 6. Failure Analysis & Diagnostics

Detected **32** diagnostic failure item(s):

| Query ID | Category | Query | Root Cause | Proposed Fix |
| :--- | :--- | :--- | :--- | :--- |
| `Q01` | `ranking_failure` | Where is repository analysis orchestrated and executed? | Expected files found at rank > 3: ['backend/repodna/mcp/server.py', 'backend/repodna/api/app.py', 'backend/repodna/intelligence/service.py', 'backend/repodna/core/analyzer.py', 'backend/repodna/reports/exporter.py'] | Refine ranking weights or add domain synonyms |
| `Q02` | `missing_symbol` | Find function run_repository_analysis | Expected ['backend/repodna/core/analyzer.py'] not found in top 5. | Refine ranking weights or add domain synonyms |
| `Q06` | `missing_symbol` | Where is architecture health score and grading computed? | Expected ['backend/repodna/rules/health.py'] not found in top 5. | Refine ranking weights or add domain synonyms |
| `Q07` | `missing_symbol` | Find class PRArchitectureGuardian | Expected ['backend/repodna/guardian/pr_guardian.py'] not found in top 5. | Refine ranking weights or add domain synonyms |
| `Q09` | `missing_symbol` | Where is Architecture Contract evaluation and policy check? | Expected ['backend/repodna/contract/evaluator.py'] not found in top 5. | Refine ranking weights or add domain synonyms |
| `Q10` | `missing_symbol` | Where is contract schema parsing and yaml loader? | Expected ['backend/repodna/contract/parser.py'] not found in top 5. | Refine ranking weights or add domain synonyms |
| `Q14` | `ranking_failure` | Where is DeepSymbolExtractor parsing AST definitions and calls? | Expected files found at rank > 3: ['backend/repodna/mcp/server.py', 'backend/repodna/parsers/treesitter_parser.py', 'backend/repodna/brain/models.py', 'backend/repodna/brain/extractor.py', 'backend/repodna/brain/tracer.py'] | Refine ranking weights or add domain synonyms |
| `Q21` | `missing_symbol` | Where is HTML architecture report generator implemented? | Expected ['backend/repodna/reports/exporter.py'] not found in top 5. | Refine ranking weights or add domain synonyms |
| `Q22` | `ranking_failure` | Where is FastAPI REST API server routes defined? | Expected files found at rank > 3: ['backend/repodna/mcp/server.py', 'frontend/src/api/client.ts', 'frontend/src/__tests__/setup.ts', 'backend/repodna/api/app.py', 'backend/tests/test_agent_and_diff.py'] | Refine ranking weights or add domain synonyms |
| `Q23` | `missing_symbol` | Where is Martin coupling instability metric calculated? | Expected ['backend/repodna/graph/engine.py'] not found in top 5. | Refine ranking weights or add domain synonyms |
| `Q25` | `missing_symbol` | Which modules depend on Tree-sitter parser? | Expected ['backend/repodna/core/analyzer.py', 'backend/repodna/brain/extractor.py'] not found in top 5. | Refine ranking weights or add domain synonyms |
| `Q26` | `missing_symbol` | Where is frontend React main entrypoint application component? | Expected ['frontend/src/App.tsx'] not found in top 5. | Refine ranking weights or add domain synonyms |
| `Q28` | `missing_symbol` | Where is interactive architecture graph visualizer component? | Expected ['frontend/src/components/DependencyGraph.tsx'] not found in top 5. | Refine ranking weights or add domain synonyms |
| `Q29` | `missing_symbol` | Where is architecture health score card UI widget? | Expected ['frontend/src/components/HealthReportView.tsx'] not found in top 5. | Refine ranking weights or add domain synonyms |
| `Q30` | `missing_symbol` | Where is context inspector and agent token modal component? | Expected ['frontend/src/components/InspectorPanel.tsx'] not found in top 5. | Refine ranking weights or add domain synonyms |
| `Q31` | `missing_symbol` | Where is architectural diff viewer component in frontend? | Expected ['frontend/src/components/GuardianOverview.tsx'] not found in top 5. | Refine ranking weights or add domain synonyms |
| `Q32` | `missing_symbol` | Where is Repository Passport viewer tab component? | Expected ['frontend/src/components/PassportViewer.tsx'] not found in top 5. | Refine ranking weights or add domain synonyms |
| `Q33` | `missing_symbol` | Where is architecture contract inspector component? | Expected ['frontend/src/components/ContractInspector.tsx'] not found in top 5. | Refine ranking weights or add domain synonyms |
| `Q34` | `ranking_failure` | Find frontend TypeScript interfaces for AnalysisResult and FileNode | Expected files found at rank > 3: ['backend/repodna/brain/indexer.py', 'backend/repodna/api/app.py', 'backend/repodna/schemas/models.py', 'frontend/src/types/repodna.ts', 'backend/repodna/brain/models.py'] | Refine ranking weights or add domain synonyms |
| `Q37` | `missing_symbol` | What could be affected by changing Tarjan cycle detector? | Expected ['backend/repodna/core/analyzer.py', 'backend/repodna/rules/health.py'] not found in top 5. | Refine ranking weights or add domain synonyms |
| `Q38` | `missing_symbol` | Who imports ArchitectureDiffEngine? | Expected ['backend/repodna/cli/main.py', 'backend/repodna/guardian/pr_guardian.py'] not found in top 5. | Refine ranking weights or add domain synonyms |
| `Q39` | `missing_symbol` | Find symbol Validator | Expected ['backend/repodna/security/validators.py'] not found in top 5. | Refine ranking weights or add domain synonyms |
| `Q41` | `missing_symbol` | Where is rule health evaluation and circular dependency check rule defined? | Expected ['backend/repodna/rules/health.py'] not found in top 5. | Refine ranking weights or add domain synonyms |
| `Q42` | `missing_symbol` | Find function calculate_module_coupling | Expected ['backend/repodna/graph/engine.py'] not found in top 5. | Refine ranking weights or add domain synonyms |
| `Q46` | `missing_symbol` | Where is PR guardian exit code and severity threshold calculated? | Expected ['backend/repodna/guardian/pr_guardian.py'] not found in top 5. | Refine ranking weights or add domain synonyms |
| `Q47` | `missing_symbol` | Find symbol Engine | Expected ['backend/repodna/diff/engine.py', 'backend/repodna/brain/retrieval.py'] not found in top 5. | Refine ranking weights or add domain synonyms |
| `Q49` | `synonym_expansion_error` | Find GraphQL schema federation resolver | Negative query returned non-empty candidates: ['frontend/src/types/repodna.ts', 'frontend/src/utils/graphLayout.ts'] | Refine ranking weights or add domain synonyms |
| `Q50` | `synonym_expansion_error` | Find Redis cluster sentinel reconnect logic | Negative query returned non-empty candidates: ['backend/repodna/intelligence/models.py', 'backend/tests/test_brain_resolution_and_evidence.py'] | Refine ranking weights or add domain synonyms |
| `Q51` | `synonym_expansion_error` | Where is Rust PyO3 FFI binding defined? | Negative query returned non-empty candidates: ['backend/repodna/mcp/server.py', 'frontend/src/types/repodna.ts'] | Refine ranking weights or add domain synonyms |
| `Q53` | `synonym_expansion_error` | Find WebRTC peer connection audio streamer | Negative query returned non-empty candidates: ['frontend/src/types/repodna.ts', 'backend/repodna/passport/models.py'] | Refine ranking weights or add domain synonyms |
| `Q54` | `synonym_expansion_error` | Where is Celery distributed task worker queue configured? | Negative query returned non-empty candidates: ['backend/repodna/api/app.py'] | Refine ranking weights or add domain synonyms |
| `Q55` | `synonym_expansion_error` | Find OAuth2 PKCE social login provider | Negative query returned non-empty candidates: ['backend/repodna/context/builder.py', 'backend/tests/test_agent_and_diff.py'] | Refine ranking weights or add domain synonyms |

## 7. Mathematical Metric Definitions

- **Hit@K**: $\frac{1}{|Q_{pos}|} \sum_{q \in Q_{pos}} \mathbb{I}(\text{Top-}K \cap \text{Expected}_q \neq \emptyset)$
- **MRR (Mean Reciprocal Rank)**: $\frac{1}{|Q_{pos}|} \sum_{q \in Q_{pos}} \frac{1}{\text{rank}_q}$
- **Precision@K**: $\frac{1}{|Q_{pos}|} \sum_{q \in Q_{pos}} \frac{|\text{Top-}K \cap \text{Expected}_q|}{K}$
- **Recall@K**: $\frac{1}{|Q_{pos}|} \sum_{q \in Q_{pos}} \frac{|\text{Top-}K \cap \text{Expected}_q|}{|\text{Expected}_q|}$
- **nDCG@K**: $\frac{1}{|Q_{pos}|} \sum_{q \in Q_{pos}} \frac{\text{DCG}_q@K}{\text{IDCG}_q@K}$
- **Negative Abstention Rate**: $\frac{|\{q \in Q_{neg} \mid \text{Returned}_q = \emptyset \}|}{|Q_{neg}|}$
- **Verified Reference Precision**: $\frac{|\text{Verified References with confirmed target symbol in target file}|}{|\text{Total Verified References}|}$