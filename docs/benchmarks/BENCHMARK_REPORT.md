# RepoDNA v0.3.0 — AI Agent Architectural Intelligence Benchmark

## 1. Executive Summary & Honest Metric Framing
This benchmark evaluates the empirical efficiency and factual accuracy of AI coding agents navigating a software repository under two distinct operational paradigms:
- **Scenario A (Naive Baseline):** Standard unassisted agent exploration relying on iterative file reads, raw regex grep, directory tree sweeps, and raw `git diff` outputs.
- **Scenario B (RepoDNA Platform):** Agent leveraging the RepoDNA Agent Skill and MCP tools (`repodna_repository_overview`, `repodna_find_modules`, `repodna_change_impact`, `repodna_architecture_diff`).

### Honest Metric Labeling: Synthetic Architectural Context Reduction
The aggregate **-99.5% reduction** measured below represents **Synthetic Architectural Context Reduction**. 

> [!IMPORTANT]
> **Payload Tokens vs. Conversational Session Tokens:**
> RepoDNA optimizes the **architectural tool payload tokens** injected into the LLM's working context window. It does **not** claim to reduce total conversational session tokens by 99.5%, as multi-turn conversations also contain user prompts, system instructions, reasoning tokens, and conversation history. Rather, by replacing thousands of lines of raw source code and noisy grep results with concise, AST-grounded architectural facts, RepoDNA reduces the architectural knowledge footprint from ~86,000 tokens down to ~417 tokens.

---

## 2. Evaluation Results Summary
*Evaluated on the RepoDNA repository (105 files, 15,924 LOC across Python and TypeScript).*

| Task | Scenario A (Tool Calls / Est. Tokens) | Scenario B with RepoDNA (Tool Calls / Est. Tokens) | Synthetic Architectural Context Reduction | Accuracy Gain & Algorithmic Verification |
| :--- | :--- | :--- | :--- | :--- |
| **TASK-1: Entrypoints & Hubs** | 16 calls / 18,000 tokens | 1 call / 127 tokens | **-99.3%** | Heuristic file guessing → Exact Martin fan-in coupling metrics |
| **TASK-2: Relevant Modules Search** | 11 calls / 8,400 tokens | 1 call / 30 tokens | **-99.6%** | Raw text grep noise → Tree-sitter AST symbol & path scoring |
| **TASK-3: Trace Dependencies** | 9 calls / 8,800 tokens | 1 call / 27 tokens | **-99.7%** | Manual import following → AST resolved internal dependency edges |
| **TASK-4: Refactor Blast Radius** | 13 calls / 10,800 tokens | 1 call / 86 tokens | **-99.2%** | Incomplete caller guesses → Graph BFS traversal & cycle risk |
| **TASK-5: Circular Cycle Detection** | 15 calls / 15,000 tokens | 1 call / 21 tokens | **-99.9%** | High LLM cycle hallucination → Mathematical Tarjan SCC verification |
| **TASK-6: Architecture Commit Diff** | 5 calls / 25,000 tokens | 1 call / 126 tokens | **-99.5%** | Raw multi-file git diff → Structural delta, cycle delta & score diff |
| **TOTALS** | **69 tool calls / 86,000 tokens** | **6 tool calls / 417 tokens** | **-99.5%** | **Deterministic, Evidence-Based Truth** |

---

## 3. Methodology, Assumptions & Overhead Analysis

### Baseline Scenario A Assumptions
- The agent attempts to locate architecture hubs by listing directory trees and inspecting suspected entrypoint files (`main.py`, `app.py`, `index.ts`, `server.py`, etc.), averaging 1,200 tokens per file read.
- For feature searches, the agent executes regex grep across all files, resulting in comment/documentation noise, followed by reading multiple candidate files.
- For circular dependencies, LLMs reading sequential source files struggle to close cyclic paths beyond length 2; Tarjan's Strongly Connected Components algorithm cannot be executed reliably in raw prompting.
- For architectural diffs, `git diff HEAD~1..HEAD` emits thousands of lines of syntax diff without extracting module coupling shifts, cycle additions/removals, or health score regressions.

### RepoDNA Scenario B Overhead & Cache Behavior
1. **Initial Scan Overhead (Cold Cache):**
   - RepoDNA executes an initial repository scan utilizing Tree-sitter AST parsers and Martin graph metrics.
   - On this repository (105 files, 15,924 LOC), the initial cold scan completes in **~380ms - 420ms** CPU time.
2. **Subsequent Queries (Cache Hit):**
   - Once indexed in memory or backed by the local SQLite cache, subsequent MCP queries (`get_repository_overview`, `find_relevant_modules`, `get_dependencies`, `get_change_impact`) execute in **< 5ms** with zero re-parsing overhead.
3. **Reproducibility:**
   - The entire benchmark harness is automated and reproducible via:
     ```bash
     python -m repodna.benchmarks.evaluator
     ```
   - Token estimation heuristic uses the standard 4 characters per token calculation.

---

## 4. Unsupported Languages & Partial Coverage Honesty
When evaluated against multi-language codebases containing unsupported or partially supported languages (such as C# in NiceWP, PHP, or Ruby):
- RepoDNA refuses to emit an artificial `100/100` health score or hallucinated dependency graphs.
- If AST grammars cover file metrics but cannot resolve module imports, the architecture health score reports `N/A (Insufficient dependency coverage)`.
- All graph-dependent rules (ARCH-001 through ARCH-004) are explicitly cataloged under `unverified_rules`, informing the AI agent that dependency-level risk cannot be certified from source code alone.
