# RepoDNA v0.3.0 — AI Agent Architectural Intelligence Benchmark

## 1. Executive Summary
This benchmark evaluates the empirical efficiency and factual accuracy of AI coding agents navigating a software repository under two conditions:
- **Scenario A (Baseline):** Standard blind agent exploration using file reads, grep, and directory listings.
- **Scenario B (RepoDNA Platform):** Agent leveraging RepoDNA Agent Skill and MCP tools (`repodna_repository_overview`, `repodna_find_modules`, `repodna_change_impact`, `repodna_architecture_diff`).

---

## 2. Evaluation Results Summary
*Evaluated on RepoDNA repository (105 files, 15,924 LOC across Python and TypeScript).*

| Task | Scenario A (Tool Calls / Est. Tokens) | Scenario B with RepoDNA (Tool Calls / Est. Tokens) | Token Reduction | Accuracy Gain |
| :--- | :--- | :--- | :--- | :--- |
| **TASK-1: Entrypoints & Hubs** | 16 calls / 18,000 tokens | 1 call / 127 tokens | **-99.3%** | Heuristic file guessing → Exact Martin fan-in coupling metrics |
| **TASK-2: Relevant Modules Search** | 11 calls / 8,400 tokens | 1 call / 30 tokens | **-99.6%** | Raw text grep noise → Tree-sitter AST symbol & path scoring |
| **TASK-3: Trace Dependencies** | 9 calls / 8,800 tokens | 1 call / 27 tokens | **-99.7%** | Manual import following → AST resolved internal dependency edges |
| **TASK-4: Refactor Blast Radius** | 13 calls / 10,800 tokens | 1 call / 86 tokens | **-99.2%** | Incomplete caller guesses → Graph BFS traversal & cycle risk |
| **TASK-5: Circular Cycle Detection** | 15 calls / 15,000 tokens | 1 call / 21 tokens | **-99.9%** | High LLM cycle error rate → Mathematical Tarjan SCC verification |
| **TASK-6: Architecture Commit Diff** | 5 calls / 25,000 tokens | 1 call / 126 tokens | **-99.5%** | Raw multi-file git diff → Structural delta, cycle delta & score diff |
| **TOTALS** | **69 tool calls / 86,000 tokens** | **6 tool calls / 417 tokens** | **-99.5%** | **Deterministic, Evidence-Based Truth** |

---

## 3. Methodology & Reproducibility
- All tests can be re-run locally via:
  ```bash
  python -m repodna.benchmarks.evaluator
  ```
- **Token Estimation Heuristic:** Calculated at 4 characters per token average.
- **Language Coverage Honesty:** In partially supported repositories (e.g. C# in NiceWP), RepoDNA marks health score as `N/A (Insufficient dependency coverage)` and catalogs unverified rules, preventing artificial 100/100 passes.
