# RepoDNA Benchmark Ground Truth Audit & Changelog

## Executive Summary

An exhaustive, line-by-line ground truth audit was conducted on all 55 queries in `benchmarks/retrieval-v1.jsonl`.
Every expected file, symbol definition, and evidence string was cross-referenced against actual source files at revision `ab07242`.

- **Original Dataset:** `benchmarks/retrieval-v1-original.jsonl` (SHA-256: `54628b1922d623ac8a183656291a9b9c8064ce4c197aea39ba51ab38180f0770`)
- **Audited Dataset:** `benchmarks/retrieval-v1.jsonl` (SHA-256: `930247e96295c6bb2344b138b82cbed7156cc640b2009f63e818698d5eb2f25a`)
- **Target Revision SHA:** `ab07242`
- **Total Queries Audited:** 55
- **Queries Corrected:** 25 (45.5%)
- **Queries Verified Accurate:** 30 (54.5%)

---

## Categorization of Ground Truth Defects

1. **Non-Existent / Outdated File Paths (P0 Priority)**:
   - `backend/repodna/guardian/pr_guardian.py` does not exist in any commit. The actual implementation is `backend/repodna/guardian/engine.py` (affected `Q07`, `Q38`, `Q46`).
   - `backend/repodna/contract/parser.py` does not exist. Contract loading is in `backend/repodna/contract/loader.py` (affected `Q10`, `Q40`).

2. **Hallucinated Class and Function Symbol Names**:
   - `analyze_source_tree` -> `_analyze_directory_internal` (`Q01`)
   - `TreeSitterParser` class -> `parse_source_file`, `_init_treesitter_parsers` (`Q03`, `Q25`)
   - `detect_strongly_connected_components` / `TarjanCycleDetector` -> `_tarjan_scc`, `build_dependency_graph` (`Q05`, `Q37`)
   - `calculate_architecture_health` / `RuleRegistry` -> `evaluate_architecture_health` (`Q06`, `Q41`)
   - `validate_safe_path` -> `is_safe_subpath` (`Q12`, `Q39`)
   - `create_app` / `analyze_repo` -> `app`, `scan_repository_sync` (`Q22`)
   - `calculate_module_coupling` -> `build_dependency_graph` (`Q23`, `Q42`)
   - `fetchAnalysis` / `fetchDiff` -> `startAsyncScanJob`, `fetchJobResult` (`Q27`)
   - `WorkspaceManager` -> `clone_github_repo_safely`, `build_hardened_git_env` (`Q43`)

3. **Frontend Implementation Misalignments**:
   - `function App()` -> `export const App` in `App.tsx` (`Q26`)
   - `ForceGraph2D` -> `@xyflow/react` (`ReactFlow`) in `DependencyGraph.tsx` (`Q28`)
   - `token_budget` modal -> `selectedFile`, `allFindings` in `InspectorPanel.tsx` (`Q30`)
   - `ArchitectureDiffResult` -> `GuardianReport`, `GuardianVerdict` in `GuardianOverview.tsx` (`Q31`)
   - `export const VERSION` -> `export const APP_VERSION` in `version.ts` (`Q35`)

---

## Detailed Per-Query Audit Log

| Query ID | Split | Category | Type of Change | Source Code Evidence & Justification |
| :--- | :---: | :---: | :--- | :--- |
| `Q01` | `dev` | `feature_location` | **Original Files:** `['backend/repodna/core/analyzer.py']`<br>**Corrected Files:** `['backend/repodna/core/analyzer.py']` | `analyze_source_tree` was hallucinated; actual internal scanning function is `_analyze_directory_internal` in `backend/repodna/core/analyzer.py`. |
| `Q03` | `dev` | `feature_location` | **Original Files:** `['backend/repodna/parsers/treesitter_parser.py']`<br>**Corrected Files:** `['backend/repodna/parsers/treesitter_parser.py']` | `TreeSitterParser` class was hallucinated; module exports functions `parse_source_file`, `_init_treesitter_parsers`, and `get_parser_engine_summary` in `backend/repodna/parsers/treesitter_parser.py`. |
| `Q05` | `dev` | `feature_location` | **Original Files:** `['backend/repodna/graph/engine.py']`<br>**Corrected Files:** `['backend/repodna/graph/engine.py']` | `detect_strongly_connected_components` / `TarjanCycleDetector` were hallucinated; Tarjan SCC is implemented as `_tarjan_scc` and invoked within `build_dependency_graph` in `backend/repodna/graph/engine.py`. |
| `Q06` | `dev` | `feature_location` | **Original Files:** `['backend/repodna/rules/health.py']`<br>**Corrected Files:** `['backend/repodna/rules/health.py']` | `calculate_architecture_health` and `RuleRegistry` were hallucinated; health engine entrypoint is `evaluate_architecture_health` returning `ArchitectureHealthReport` in `backend/repodna/rules/health.py`. |
| `Q07` | `dev` | `symbol_lookup` | **Original Files:** `['backend/repodna/guardian/pr_guardian.py']`<br>**Corrected Files:** `['backend/repodna/guardian/engine.py']` | `backend/repodna/guardian/pr_guardian.py` does not exist; `PRArchitectureGuardian` class is declared in `backend/repodna/guardian/engine.py`. |
| `Q10` | `dev` | `feature_location` | **Original Files:** `['backend/repodna/contract/parser.py']`<br>**Corrected Files:** `['backend/repodna/contract/loader.py']` | `backend/repodna/contract/parser.py` does not exist; contract schema parsing and yaml loader is `backend/repodna/contract/loader.py`. |
| `Q12` | `dev` | `symbol_lookup` | **Original Files:** `['backend/repodna/security/validators.py']`<br>**Corrected Files:** `['backend/repodna/security/validators.py']` | `validate_safe_path` was hallucinated; the actual path traversal validation function in `backend/repodna/security/validators.py` is `is_safe_subpath`. |
| `Q19` | `dev` | `feature_location` | **Original Files:** `['backend/repodna/mcp/server.py']`<br>**Corrected Files:** `['backend/repodna/mcp/server.py']` | `repodna_get_repository_overview` was hallucinated; MCP tool is registered as `repodna_repository_overview` (method `tool_repository_overview`) in `backend/repodna/mcp/server.py`. |
| `Q22` | `dev` | `feature_location` | **Original Files:** `['backend/repodna/api/app.py']`<br>**Corrected Files:** `['backend/repodna/api/app.py']` | `create_app` and `analyze_repo` were hallucinated; FastAPI application instance is `app` and synchronous scan route is `scan_repository_sync` (`@app.post('/api/scan')`) in `backend/repodna/api/app.py`. |
| `Q23` | `dev` | `feature_location` | **Original Files:** `['backend/repodna/graph/engine.py']`<br>**Corrected Files:** `['backend/repodna/graph/engine.py']` | `calculate_module_coupling` and `CouplingMetrics` were hallucinated; coupling metrics (fan_in, fan_out, instability) are calculated in `build_dependency_graph` in `backend/repodna/graph/engine.py`. |
| `Q25` | `dev` | `dependency_trace` | **Original Files:** `['backend/repodna/core/analyzer.py', 'backend/repodna/brain/extractor.py']`<br>**Corrected Files:** `['backend/repodna/core/analyzer.py', 'backend/repodna/brain/extractor.py']` | `TreeSitterParser` was hallucinated; dependent modules import `parse_source_file` and `_init_treesitter_parsers` from `repodna.parsers.treesitter_parser`. |
| `Q26` | `dev` | `feature_location` | **Original Files:** `['frontend/src/App.tsx']`<br>**Corrected Files:** `['frontend/src/App.tsx']` | `App` is declared as `export const App: React.FC = () => {` in `frontend/src/App.tsx`, not `function App()`. |
| `Q27` | `dev` | `symbol_lookup` | **Original Files:** `['frontend/src/api/client.ts']`<br>**Corrected Files:** `['frontend/src/api/client.ts']` | `fetchAnalysis` / `fetchDiff` were hallucinated; real API client functions are `startAsyncScanJob`, `fetchJobResult`, `runSyncScan` in `frontend/src/api/client.ts`. |
| `Q28` | `dev` | `feature_location` | **Original Files:** `['frontend/src/components/DependencyGraph.tsx']`<br>**Corrected Files:** `['frontend/src/components/DependencyGraph.tsx']` | Dependency graph visualizer uses `@xyflow/react` (`ReactFlow`), not `ForceGraph2D` in `frontend/src/components/DependencyGraph.tsx`. |
| `Q30` | `dev` | `feature_location` | **Original Files:** `['frontend/src/components/InspectorPanel.tsx']`<br>**Corrected Files:** `['frontend/src/components/InspectorPanel.tsx']` | UI has `InspectorPanel` for inspecting file details and architecture findings; no `token_budget` modal exists in frontend. |
| `Q31` | `dev` | `feature_location` | **Original Files:** `['frontend/src/components/GuardianOverview.tsx']`<br>**Corrected Files:** `['frontend/src/components/GuardianOverview.tsx']` | `ArchitectureDiffResult` is a backend model; `GuardianOverview.tsx` in frontend renders `GuardianReport` and `GuardianVerdict`. |
| `Q35` | `dev` | `feature_location` | **Original Files:** `['frontend/src/version.ts']`<br>**Corrected Files:** `['frontend/src/version.ts']` | Constant in `frontend/src/version.ts` is `APP_VERSION`, not `VERSION`. |
| `Q37` | `dev` | `impact_analysis` | **Original Files:** `['backend/repodna/core/analyzer.py', 'backend/repodna/rules/health.py']`<br>**Corrected Files:** `['backend/repodna/core/analyzer.py', 'backend/repodna/rules/health.py']` | `detect_strongly_connected_components` was hallucinated; `analyzer.py` calls `build_dependency_graph` and `health.py` evaluates resulting cycle groups via rule `ARCH-001`. |
| `Q38` | `dev` | `dependency_trace` | **Original Files:** `['backend/repodna/cli/main.py', 'backend/repodna/guardian/pr_guardian.py']`<br>**Corrected Files:** `['backend/repodna/cli/main.py', 'backend/repodna/guardian/engine.py']` | `backend/repodna/guardian/pr_guardian.py` does not exist; `ArchitectureDiffEngine` is imported by `backend/repodna/guardian/engine.py` and `backend/repodna/cli/main.py`. |
| `Q39` | `dev` | `ambiguous` | **Original Files:** `['backend/repodna/security/validators.py']`<br>**Corrected Files:** `['backend/repodna/security/validators.py']` | `validate_safe_path` was hallucinated; security validator symbols are `SecurityValidationError`, `validate_local_directory`, `is_safe_subpath`. |
| `Q40` | `dev` | `ambiguous` | **Original Files:** `['backend/repodna/parsers/treesitter_parser.py', 'backend/repodna/contract/parser.py']`<br>**Corrected Files:** `['backend/repodna/parsers/treesitter_parser.py', 'backend/repodna/cli/main.py']` | `backend/repodna/contract/parser.py` does not exist; ambiguous query 'Parser' targets Tree-sitter parser engine and CLI argument parser (`build_arg_parser`). |
| `Q41` | `holdout` | `feature_location` | **Original Files:** `['backend/repodna/rules/health.py']`<br>**Corrected Files:** `['backend/repodna/rules/health.py']` | `RuleRegistry` and `evaluate_circular_dependencies` were hallucinated; circular dependency rules are evaluated in `evaluate_architecture_health` checking `ARCH-001` in `backend/repodna/rules/health.py`. |
| `Q42` | `holdout` | `symbol_lookup` | **Original Files:** `['backend/repodna/graph/engine.py']`<br>**Corrected Files:** `['backend/repodna/graph/engine.py']` | `calculate_module_coupling` was hallucinated; graph construction and coupling metrics are calculated in `build_dependency_graph` in `backend/repodna/graph/engine.py`. |
| `Q43` | `holdout` | `feature_location` | **Original Files:** `['backend/repodna/storage/workspace.py']`<br>**Corrected Files:** `['backend/repodna/storage/workspace.py']` | `class WorkspaceManager` was hallucinated; isolated workspace cloning is handled by `clone_github_repo_safely` and `build_hardened_git_env` in `backend/repodna/storage/workspace.py`. |
| `Q46` | `holdout` | `feature_location` | **Original Files:** `['backend/repodna/guardian/pr_guardian.py']`<br>**Corrected Files:** `['backend/repodna/guardian/engine.py']` | `backend/repodna/guardian/pr_guardian.py` does not exist; guardian verdict and severity thresholds are evaluated in `backend/repodna/guardian/engine.py`. |

---

## Unaltered Ground Truth Queries

The following 30 queries were audited and confirmed 100% accurate against real repository code:
`Q02`, `Q04`, `Q08`, `Q09`, `Q11`, `Q13`, `Q14`, `Q15`, `Q16`, `Q17`, `Q18`, `Q20`, `Q21`, `Q24`, `Q29`, `Q32`, `Q33`, `Q34`, `Q36`, `Q44`, `Q45`, `Q47`, `Q48`, `Q49`, `Q50`, `Q51`, `Q52`, `Q53`, `Q54`, `Q55`.
