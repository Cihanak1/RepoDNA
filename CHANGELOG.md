# Changelog

All notable changes to **RepoDNA** are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.2.0] - 2026-11-08

### Added
- **Workstation Experience & Cognitive Simplicity**:
  - Two operational modes: **Simple Mode** (default) with 4 essential summary cards and reduced cognitive clutter, and **Advanced Mode** with full 6-metric technical strip, Tarjan SCC cycle counts, Robert C. Martin Instability formula ($I = C_e / (C_a + C_e)$), and Git churn insights.
  - 4-step accessible **Guided Onboarding Tour** with keyboard navigation (arrows, Escape), focus management, persistent completion state, and one-click "Try Demo Architecture" action.
  - Contextual **InfoTooltip** component with WCAG-compliant ARIA attributes for plain-language explanations of `Fan-In`, `Fan-Out`, `Instability`, `SCC`, `Circular Dependency`, `AST Coverage`, and coverage-based `Confidence`.
  - **Full Bilingual Localization (English & Türkçe)** via `react-i18next` with zero-reload dynamic toggling, browser language detection, persistent `localStorage` preference, live `document.documentElement.lang` synchronization, and Turkish case-folding search (`normalizeSearchText`).
  - Two-tier **Explainable Health Report** featuring Executive Summary view and Deep Technical Audit view with localized rule titles and remediations (`ARCH-001` through `ARCH-006` and `SEC-001`).
  - Precision Engineering Workstation with semantic dark/light tokens, resizable panels with keyboard accessibility, canvas focus (`Alt+F`), persistent layout preferences, and mobile Files / Canvas / Inspector navigation.
  - Package coverage summaries, path/metrics clipboard actions, command grouping/history, and zoom to selection.
  - Full automated Axe WCAG A/AA accessibility test suite across five viewport sizes, themes, command palette, and live NiceWP analysis.

### Fixed
- Empty minimap, compact graph overlaps, light-theme contrast and rapid command-palette reopen race.
- Unsupported modules no longer receive a generic healthy label; unverified report categories no longer display zero-score bars.
- Export feedback checks the response before reporting a download; partial-static coverage semantics remain unchanged.
- Backend error codes and deterministic architectural health rule descriptions mapped to user-facing translations while preserving canonical rule IDs and API fields.

### Performance
- Lazy-loaded graph and report views; quieter edge labels and memoized graph nodes.
- Vite production build under 4.1s; zero bundle bloat.


## [0.1.1] - 2026-11-08

### Fixed
- **Async Scan Job Completion Race Condition (`HTTP 409 RESULT_NOT_READY` / `[POLL_ERROR]`)**:
  - Removed premature `ScanStatus.COMPLETED` progress notifications from `repodna.core.analyzer` before `AnalysisResult` construction and temporary clone directory cleanup (`CloneWorkspace.__exit__`) complete.
  - Added `_complete_job_atomically` in `repodna.api.app` so `_JOB_RESULTS[job_id]`, `_RESULTS_BY_ID`, and `_JOBS[job_id].status = ScanStatus.COMPLETED` are published atomically inside a single `_LOCK` acquisition using immutable `model_copy` snapshots.
  - Added single-flight sequential polling (`pollInFlightRef` + `scanSessionIdRef` + `setTimeout`), bounded exponential backoff retry (`fetchJobResultWithRetry`) for transient `409 RESULT_NOT_READY` responses, `Previous analysis` banner/badge labeling while a new scan is in progress, and automatic switching to **Architecture Studio** upon scan completion.
- **Analysis Coverage, Confidence & Low-Coverage Dependency Graph Reliability (`Cihanak1/NiceWP` Verification)**:
  - Separated file-based (`ast_file_coverage_pct`, `partial_static_file_coverage_pct`, `unsupported_file_coverage_pct`) and LOC-based (`ast_loc_coverage_pct`, `partial_static_loc_coverage_pct`, `unsupported_loc_coverage_pct`) coverage metrics in `TransparencyReport` and `ArchitectureHealthReport`.
  - Added `confidence` (`"high" | "medium" | "low" | "none"`), `confidence_reason`, `dependency_graph_evaluated`, `cycle_analysis_summary`, and `unverified_rules` to `ArchitectureHealthReport`.
  - When `full_ast` coverage is below `50%` of total LOC (such as `Cihanak1/NiceWP`, where 263 C# files / `92.2%` of LOC are `partial_static` and only 1 Python file / `0.2%` of LOC is `full_ast`), RepoDNA sets `dependency_graph_evaluated = False`, `status = "insufficient_dependency_coverage"`, `overall_score = None`, and `grade = "N/A"` (`Not evaluated — Insufficient dependency coverage`) instead of reporting a misleading `85/100` score or claiming repository-wide acyclicity.
  - Replaced unqualified acyclicity claims with bounded phrasing (`No cycles detected in analyzed graph (<X>% full_ast LOC, <Y>% full_ast files)` when evaluated, or `Not evaluated — Insufficient dependency coverage` when below threshold).
- **`partial_static` Language Transparency & Orphan Rule Boundary (C#, Java, Kotlin, C/C++)**:
  - Added `partial_static_languages_detected` and `partial_static_files_count` to `TransparencyReport` so `partial_static` languages are never misclassified under `supported_languages_detected` (`full_ast`).
  - Scoped `ARCH-005` (`Isolated / Potentially Unreferenced Modules`) and `FileNode.is_orphan` strictly to `full_ast` modules so `partial_static` files are not falsely penalized for having `0` resolved AST graph edges.

## [0.1.0-rc.1] - 2026-11-07 (Release Candidate 1)

### Added
- **Core Static AST Engine (`repodna.parsers`)**:
  - Single-pass C-level Tree-sitter CST parsing for Python, TypeScript (`.ts`/`.tsx`), JavaScript (`.js`/`.jsx`/`.mjs`), Go, and Rust with error-tolerant syntax recovery.
  - Partial static `#include` / `import` scanning for C, C++, Java, Kotlin, and C#.
  - Support for `tsconfig.json` / `jsconfig.json` `paths` and `baseUrl` aliases, `go.mod` module path prefix resolution, monorepo workspace packages (`packages/*`), Rust `mod foo;` declarations, and braced `use crate::a::{b, c}` imports.
  - Explicit transparency tracking for unsupported languages, unresolved internal imports, dynamic imports (`import(...)`, `__import__`), and skipped files.
- **Dependency Graph & Cycle Detection Engine (`repodna.graph`)**:
  - Iterative Tarjan Strongly Connected Components (`scc_count`) and Johnson's blocked-set canonical elementary cycle extraction (`cycle_count`), bounded by per-SCC `max_cycles=25`, global `max_total_cycles=100`, `25,000` operation budget, and `0.75s` timeout per SCC with `cycles_truncated` disclosure.
  - Per-module Fan-In ($C_a$), Fan-Out ($C_e$), Robert C. Martin Instability Index ($I = C_e / (C_a + C_e)$), hub detection, and orphan detection.
- **Explainable Architecture Health Engine (`repodna.rules`)**:
  - Deterministic 100-point rubric (`status="evaluated"`) evaluating Acyclic Dependencies Principle (`ARCH-001`), Efferent Coupling (`ARCH-002`), Stable Dependencies Principle (`ARCH-003`), Oversized Modules (`ARCH-004`), Isolated Modules (`ARCH-005`), Directory Nesting (`ARCH-006`), and Credential/Secret Hygiene (`SEC-001`).
  - Explicit `N/A` (`overall_score=None`, `grade="N/A"`, `status="insufficient_data"`) semantics for empty repositories (`0` files) so missing data is never reported as a synthetic 100/100 score.
- **Git Insights (`repodna.git_insights`)**:
  - Read-only commit history inspection (`%x1f` unit-separator delimiter, `core.quotepath=false` for Unicode paths), 60%-threshold bus-factor estimation, and file churn hotspot scoring.
- **Security & Guardrails (`repodna.security`, `repodna.storage`)**:
  - Strict HTTPS GitHub URL allowlisting, SSRF IP/localhost blocking, Git branch option-injection prevention, hardened temporary cloning (`build_hardened_git_env` allowlist, `GIT_CONFIG_NOSYSTEM=1`, `GIT_CONFIG_GLOBAL=<empty>`, `protocol.allow=never`, `protocol.https.allow=always`, `http.followRedirects=false`, `http.lowSpeedLimit=1024`, process-group tree termination), symlink/path-traversal protection, UTF-16 BOM source decoding, and configurable file/byte/timeout limits with cooperative cancellation.
- **Interfaces & Exporters**:
  - Standalone Python CLI (`python -m repodna.cli.main analyze ...` / `repodna analyze ...`) with `table`, `json`, and `html` output modes.
  - FastAPI backend (`repodna.api.app`) with synchronous scan, asynchronous progress/cancellation jobs, safe directory browsing, and deterministic JSON/HTML export endpoints.
  - React 19 + TypeScript + Tailwind CSS + React Flow (`@xyflow/react`) 3-pane engineering workstation with full Dark/Light theme support, `Ctrl+K` Command Palette, Directory Package Clustering, Graph Density controls, and responsive container-query tables.
