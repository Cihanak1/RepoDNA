# RepoDNA Code Intelligence Benchmark Suite (v1.0)

This directory contains the reproducible benchmark harness, dataset, and evaluation results for **RepoDNA v0.5.0 — Repository Brain**.

The benchmark objectively measures:
1. **Code Retrieval Accuracy**: Ability to locate relevant source files and symbol definitions across natural language and developer queries.
2. **Symbol Resolution & Verification Fidelity**: Strict verification of AST calls, aliases, namespaces, and barrel exports under the 3-state resolution model (`VERIFIED`, `CANDIDATE`, `UNRESOLVED`).
3. **Comparative Baseline Performance**: Side-by-side evaluation against pure filename search (Baseline A) and exact/substring symbol search (Baseline B).
4. **Context Budget Compliance**: Deterministic pruning behavior and status reporting under micro and constrained token budgets (0, 10, 25, 60, 500, 2000 tokens).
5. **Multi-Scale Scalability & Stability**: Stress testing across Small (20 files), Medium (148 files), and Large (1,020 files) repository scales.

---

## 1. Mathematical Metric Definitions

All metrics are deterministically computed in `backend/repodna/benchmarks/metrics.py`. Negative queries (queries about features that do not exist in the codebase) are strictly separated from positive retrieval metrics to prevent artificial skew or dilution of precision/recall denominators.

### Retrieval Metrics (Evaluated on $Q_{pos}$ where $|\text{Expected}_q| > 0$)

* **Hit@K**: Measures whether at least one ground-truth target file appears within the top $K$ retrieved candidates.
  $$\text{Hit}@K = \frac{1}{|Q_{pos}|} \sum_{q \in Q_{pos}} \mathbb{I}(\text{Top-}K_q \cap \text{Expected}_q \neq \emptyset)$$

* **MRR (Mean Reciprocal Rank)**: Evaluates the rank of the first relevant result.
  $$\text{MRR} = \frac{1}{|Q_{pos}|} \sum_{q \in Q_{pos}} \frac{1}{\text{rank}_q}$$
  *(where $\text{rank}_q$ is the 1-based rank of the first relevant file, or $0$ if no relevant file is returned).*

* **Precision@K**: Proportion of top-$K$ returned items that are relevant.
  $$\text{Precision}@K = \frac{1}{|Q_{pos}|} \sum_{q \in Q_{pos}} \frac{|\text{Top-}K_q \cap \text{Expected}_q|}{K}$$

* **Recall@K**: Proportion of total expected items retrieved in the top-$K$.
  $$\text{Recall}@K = \frac{1}{|Q_{pos}|} \sum_{q \in Q_{pos}} \frac{|\text{Top-}K_q \cap \text{Expected}_q|}{|\text{Expected}_q|}$$

* **nDCG@K (Normalized Discounted Cumulative Gain)**: Graded ranking quality metric rewarding relevant items ranked higher.
  $$\text{DCG}@K = \sum_{i=1}^{\min(K, |\text{Returned}|)} \frac{\text{rel}_i}{\log_2(i + 1)}, \quad \text{IDCG}@K = \sum_{i=1}^{\min(K, |\text{Expected}|)} \frac{1.0}{\log_2(i + 1)}$$
  $$\text{nDCG}@K = \frac{\text{DCG}@K}{\text{IDCG}@K}$$

### Negative Query Metrics (Evaluated on $Q_{neg}$ where $|\text{Expected}_q| = 0$)

* **Abstention Rate (True Negative Rate)**: Proportion of negative queries where the engine correctly returned an empty candidate list or abstained from low-confidence matches.
  $$\text{Abstention Rate} = \frac{|\{q \in Q_{neg} \mid \text{Returned}_q = \emptyset\}|}{|Q_{neg}|}$$

* **False Positive Rate**: Proportion of negative queries where the engine incorrectly returned confident false positive matches.
  $$\text{False Positive Rate} = \frac{|\{q \in Q_{neg} \mid \text{Returned}_q \neq \emptyset\}|}{|Q_{neg}|}$$

### Symbol Fidelity & Performance Metrics

* **Verified Reference Precision**: Proportion of `VERIFIED` references that point to an existing, verified target symbol definition in the resolved target module.
  $$\text{Verified Precision} = \frac{|\text{Verified References with confirmed target symbol in target file}|}{|\text{Total Verified References}|} \times 100\%$$

* **False Verified Count**: Count of references falsely flagged as `VERIFIED` without AST proof.
* **Unresolved Reference Count**: Calls properly classified as `UNRESOLVED` due to insufficient static AST proof (dynamic dispatch, local shadowing, or unlinked packages).
* **P50 / P95 Latency**: 50th and 95th percentile query execution latency (ms).
* **Peak Memory**: Maximum memory allocation traced during indexing and search via `tracemalloc` (MB).
* **Token Budget Compliance**: Percentage of context requests where returned content strictly complies with requested `max_tokens` or honestly signals truncation.

---

## 2. Dataset Specification (`benchmarks/retrieval-v1.jsonl`)

The dataset contains **55 independently validated queries** grounded in real source code across Python, TypeScript, and JavaScript:

| Query Category | Description | Query Count |
| :--- | :--- | :---: |
| `feature_location` | Natural language questions locating architectural services and features | 20 |
| `symbol_lookup` | Targeted queries for specific functions, classes, interfaces, or methods | 14 |
| `dependency_trace` | Questions tracing which modules depend on or import a core service | 4 |
| `impact_analysis` | Queries exploring blast radius or downstream effects of modifying a module | 2 |
| `ambiguous` | Queries targeting identically-named symbols across different packages (`Validator`, `Parser`, `Engine`) | 7 |
| `negative` | Queries for nonexistent features (`Stripe`, `GraphQL`, `Redis`, `Rust FFI`, `Kubernetes CRD`, etc.) | 8 |
| **Total** | | **55** |

### Dataset Splits
- **Dev Split**: 43 queries used for development, parameter tuning, and ranking diagnostic analysis.
- **Holdout Split**: 12 queries reserved for holdout verification to detect dataset overfitting.

### JSONL Schema Fields
Each line in `retrieval-v1.jsonl` defines:
```json
{
  "query_id": "Q01",
  "query": "Where is repository analysis orchestrated and executed?",
  "repository": "RepoDNA",
  "revision_sha": "507ca83",
  "language": "python",
  "expected_files": ["backend/repodna/core/analyzer.py"],
  "expected_symbols": ["run_repository_analysis", "analyze_source_tree"],
  "expected_evidence": ["run_repository_analysis", "ScanRequest", "AnalysisResult"],
  "query_category": "feature_location",
  "difficulty": "easy",
  "split": "dev",
  "notes": "Core entrypoint for AST scan and graph pipeline."
}
```

---

## 3. Evaluated Baselines

Every query is evaluated across three distinct, unbiased methods over identical ground truth:

1. **Baseline A — Filename-only Search (`filename_only`)**:
   - Tokenizes query into words.
   - Computes lexical overlap against repo-relative file paths and filenames.
   - No symbol awareness, no AST parsing, no graph metrics.

2. **Baseline B — Symbol Name Exact/Substring Matching (`symbol_only`)**:
   - Extracts raw symbols across files using Tree-sitter.
   - Scores files purely based on exact and substring matches between query tokens and symbol names.
   - No synonym expansion, no call graph proximity boost, no comment penalties.

3. **Baseline C — Repository Brain Multi-Factor Retrieval (`repository_brain`)**:
   - Multi-factor deterministic ranking engine combining:
     * AST symbol definitions and container hierarchy
     * Exact path and identifier tokens
     * Domain software synonym expansion
     * Graph proximity boosting (fan-in / fan-out connected modules)
     * Test fixture demotion for implementation queries
     * Comment-only match demotion

---

## 4. Benchmark CLI Usage

Run the benchmark using the `repodna benchmark run` command:

```bash
# Run full benchmark and print Markdown report
repodna benchmark run . --dataset benchmarks/retrieval-v1.jsonl --format markdown

# Save JSON results to file
repodna benchmark run . --dataset benchmarks/retrieval-v1.jsonl --format json -o benchmarks/results/phase2-metrics.json

# Fast run skipping scalability and budget suites
repodna benchmark run . --dataset benchmarks/retrieval-v1.jsonl --skip-scalability --skip-budget
```

### CLI Options:
* `target`: Repository root directory (default: `.`)
* `--dataset`: Path to JSONL dataset (default: `benchmarks/retrieval-v1.jsonl`)
* `--format`: Output format, `markdown` (default) or `json`
* `--output`, `-o`: File path to write the output report
* `--timeout`: Max timeout in seconds (default: `60.0`)
* `--include-baselines`: Include Filename and Symbol baselines (default: `True`)
* `--profile-memory`: Track memory via `tracemalloc` (default: `True`)
* `--skip-scalability`: Skip multi-scale stress benchmark (Small, Medium, Large)
* `--skip-budget`: Skip token budget compliance matrix

---

## 5. Output Artifacts

* `benchmarks/retrieval-v1.jsonl`: Benchmark query dataset (55 queries)
* `benchmarks/results/phase2-metrics.json`: Raw per-query and aggregated JSON metrics
* `benchmarks/results/phase2-summary.md`: Full Markdown evaluation summary with baseline comparisons and failure analysis
