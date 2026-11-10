# RepoDNA Code Intelligence Benchmark — Phase 2 Evaluation Report

- **Benchmark Version:** `v1.0`
- **Commit SHA:** `ab072421001fd454503f382bf6b69802d21fa4de`
- **Evaluated At:** `2026-11-10T09:31:01.910017+00:00`
- **Environment:** Windows (AMD64), Python 3.12.10
- **Dataset:** `benchmarks/retrieval-v1.jsonl` (55 queries: 43 dev, 12 holdout)

## 1. Executive Summary & Baseline Comparison

Does **Repository Brain** actually outperform naive filename search and substring symbol search?

| Method | Hit@1 (%) | Hit@3 (%) | Hit@5 (%) | MRR | Precision@1 | Recall@3 | nDCG@5 | Negative Abstention (%) | P50 Latency (ms) |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| filename_only | **34.04** | **55.32** | **63.83** | **0.4539** | 0.3404 | 0.5319 | **0.4868** | 62.5% | 0.17 ms |
| symbol_only | **14.89** | **29.79** | **42.55** | **0.2394** | 0.1489 | 0.2979 | **0.2849** | 25.0% | 4.37 ms |
| **Repository Brain (RepoDNA)** | **63.83** | **80.85** | **80.85** | **0.7128** | 0.6383 | 0.7766 | **0.7157** | 100.0% | 6.91 ms |

## 2. Dev vs Holdout Generalization

| Split | Method | Hit@1 (%) | Hit@3 (%) | MRR | nDCG@5 | Negative Abstention (%) |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: |
| Dev Split | filename_only | 37.5% | 55.0% | 0.4667 | 0.4907 | 33.33% |
| Dev Split | symbol_only | 15.0% | 30.0% | 0.2437 | 0.2939 | 33.33% |
| Dev Split | repository_brain | 62.5% | 77.5% | 0.6917 | 0.6973 | 100.0% |
| Holdout Split | filename_only | 14.29% | 57.14% | 0.381 | 0.464 | 80.0% |
| Holdout Split | symbol_only | 14.29% | 28.57% | 0.2143 | 0.233 | 20.0% |
| Holdout Split | repository_brain | 71.43% | 100.0% | 0.8333 | 0.8206 | 100.0% |

## 3. Symbol Reference Fidelity Audit

- **Verified Reference Precision:** `100.0%`
- **False Verified Reference Count:** `0`
- **Unresolved Reference Count:** `8189` (calls correctly left unresolved due to insufficient static AST proof)
- **Cold Indexing Time:** `28257.02 ms`
- **Warm Indexing Time:** `2238.6 ms`
- **Peak Memory Usage:** `21.88 MB`

## 4. Token Budget Compliance Matrix

| Contract | Requested `max_tokens` | Counted Tokens | Method | Compliant? | Overflow? | Truncated? | Deterministic? | Duration | Notes |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :--- |
| `standard` | `0` | 0 | `heuristic_zero_budget (estimated)` | **PASS** | No | Yes | Yes | 0.31 ms | Zero budget: correctly returned empty payload (0 tokens) with truncation flag. |
| `standard` | `10` | 154 | `heuristic_chars (estimated)` | **FAIL** | Yes | Yes | Yes | 13.18 ms | Small budget (10 tokens): metadata overflow (154 > 10 tokens produced); termination_success=True, budget_compliant=False, metadata_overflow=True. |
| `standard` | `25` | 154 | `heuristic_chars (estimated)` | **FAIL** | Yes | Yes | Yes | 9.61 ms | Small budget (25 tokens): metadata overflow (154 > 25 tokens produced); termination_success=True, budget_compliant=False, metadata_overflow=True. |
| `standard` | `60` | 154 | `heuristic_chars (estimated)` | **FAIL** | Yes | Yes | Yes | 9.57 ms | Small budget (60 tokens): metadata overflow (154 > 60 tokens produced); termination_success=True, budget_compliant=False, metadata_overflow=True. |
| `standard` | `500` | 466 | `heuristic_chars (estimated)` | **PASS** | No | Yes | Yes | 9.0 ms | Generous budget (500 tokens): consumed 466 tokens safely (compliant=True). |
| `standard` | `2000` | 1382 | `heuristic_chars (estimated)` | **PASS** | No | Yes | Yes | 1.99 ms | Generous budget (2000 tokens): consumed 1382 tokens safely (compliant=True). |

## 5. Scalability & Stress Benchmark

| Tier | Files | LOC (est) | Symbols | Cold Index | Warm P50 | Warm P95 | Repeat Query | Peak RAM | Mem Growth | Status |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **Small (20 files)** | 20 | 500 | 120 | 340.22 ms | 9.11 ms | 12.8 ms | 8.36 ms | 0.5 MB | 0.0 MB | `ok` |
| **Medium (RepoDNA 148 files)** | 135 | 3375 | 725 | 20071.27 ms | 154.12 ms | 193.93 ms | 156.34 ms | 19.93 MB | 0.0 MB | `ok` |
| **Large (1,020 files synthetic)** | 1020 | 25500 | 6120 | 12935.48 ms | 1053.87 ms | 1689.55 ms | 1282.8 ms | 23.4 MB | 0.0 MB | `ok` |

## 6. Failure Analysis & Diagnostics

Detected **9** diagnostic failure item(s):

| Query ID | Category | Query | Root Cause | Proposed Fix |
| :--- | :--- | :--- | :--- | :--- |
| `Q09` | `missing_symbol` | Where is Architecture Contract evaluation and policy check? | Expected ['backend/repodna/contract/evaluator.py'] not found in top 5. | Refine ranking weights or add domain synonyms |
| `Q21` | `missing_symbol` | Where is HTML architecture report generator implemented? | Expected ['backend/repodna/reports/exporter.py'] not found in top 5. | Refine ranking weights or add domain synonyms |
| `Q22` | `missing_symbol` | Where is FastAPI REST API server routes defined? | Expected ['backend/repodna/api/app.py'] not found in top 5. | Refine ranking weights or add domain synonyms |
| `Q23` | `missing_symbol` | Where is Martin coupling instability metric calculated? | Expected ['backend/repodna/graph/engine.py'] not found in top 5. | Refine ranking weights or add domain synonyms |
| `Q25` | `missing_symbol` | Which modules depend on Tree-sitter parser? | Expected ['backend/repodna/core/analyzer.py', 'backend/repodna/brain/extractor.py'] not found in top 5. | Refine ranking weights or add domain synonyms |
| `Q26` | `missing_symbol` | Where is frontend React main entrypoint application component? | Expected ['frontend/src/App.tsx'] not found in top 5. | Refine ranking weights or add domain synonyms |
| `Q31` | `missing_symbol` | Where is architectural diff viewer component in frontend? | Expected ['frontend/src/components/GuardianOverview.tsx'] not found in top 5. | Refine ranking weights or add domain synonyms |
| `Q37` | `missing_symbol` | What could be affected by changing Tarjan cycle detector? | Expected ['backend/repodna/core/analyzer.py', 'backend/repodna/rules/health.py'] not found in top 5. | Refine ranking weights or add domain synonyms |
| `Q39` | `missing_symbol` | Find symbol Validator | Expected ['backend/repodna/security/validators.py'] not found in top 5. | Refine ranking weights or add domain synonyms |

## 7. Mathematical Metric Definitions

- **Hit@K**: $\frac{1}{|Q_{pos}|} \sum_{q \in Q_{pos}} \mathbb{I}(\text{Top-}K \cap \text{Expected}_q \neq \emptyset)$
- **MRR (Mean Reciprocal Rank)**: $\frac{1}{|Q_{pos}|} \sum_{q \in Q_{pos}} \frac{1}{\text{rank}_q}$
- **Precision@K**: $\frac{1}{|Q_{pos}|} \sum_{q \in Q_{pos}} \frac{|\text{Top-}K \cap \text{Expected}_q|}{K}$
- **Recall@K**: $\frac{1}{|Q_{pos}|} \sum_{q \in Q_{pos}} \frac{|\text{Top-}K \cap \text{Expected}_q|}{|\text{Expected}_q|}$
- **nDCG@K**: $\frac{1}{|Q_{pos}|} \sum_{q \in Q_{pos}} \frac{\text{DCG}_q@K}{\text{IDCG}_q@K}$
- **Negative Abstention Rate**: $\frac{|\{q \in Q_{neg} \mid \text{Returned}_q = \emptyset \}|}{|Q_{neg}|}$
- **Verified Reference Precision**: $\frac{|\text{Verified References with confirmed target symbol in target file}|}{|\text{Total Verified References}|}$