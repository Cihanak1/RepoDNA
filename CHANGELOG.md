# Changelog

All notable changes to **RepoDNA** are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.7.0] - 2026-11-11

### Added
- **Architecture Refactoring Advisor Engine (`repodna.advisor`)**:
  - Deterministic, graph-theoretic refactoring advisory engine analyzing dependency networks, Tarjan SCCs, Johnson elementary cycles, efferent coupling ($C_e$), instability ($I$), architectural layer hierarchies, and hub centrality.
  - Zero LLM/paid API dependencies: all recommendations are grounded in objective AST graph metrics and deterministic heuristics. Zero code rewriting of user codebases (advisory recommendations only).
  - 4 specialized refactoring recommendation categories:
    1. `circular_dependency_reduction`: Enumerates circular dependency cycles and calculates the optimal candidate edge to break based on minimum symbol dependency weight, highest instability delta, and cycle reduction potential.
    2. `high_coupling_module_review`: Flags modules with excessive efferent coupling ($C_e \ge 7$ or $I \ge 0.8$), prescribing facade patterns, dependency injection, and interface segregation.
    3. `layer_boundary_improvement`: Detects layer boundary inversions across architectural tiers (e.g. Domain -> Presentation/API bypass), proposing contract abstractions and inversion of control.
    4. `oversized_architectural_hub_review`: Identifies god files and excessive degree hubs (degree $\ge 14$ or non-comment LOC $\ge 300$), prescribing cohesive sub-module decomposition.
  - Deterministic severity classification (`critical`, `high`, `medium`, `low`) and deduplicated ordering.
  - Rich recommendation model including `target_modules`, `action_steps`, `expected_benefit`, `impact_description`, and `metric_delta_preview`.
  - Executive summary report with aggregate KPIs: `total_recommendations`, `critical_cycles`, `high_coupling_modules`, `layer_boundary_violations`, `oversized_hubs`.
- **Refactoring Advisor REST API**:
  - `GET /api/analyses/{analysis_id}/advisor`: Filterable by `category` and `min_severity`.
  - Scaled in-memory stored analysis cache from 25 to 100 entries to prevent premature cache eviction during high-volume test runs.
- **Extended Model Context Protocol (MCP) Suite (23 Tools Total)**:
  - New tool: `repodna_refactoring_advisor`:
    - Parameters: `target`, `category`, `min_severity`, `format`, `force`.
    - Returns structured recommendations, actionable remediation steps, and metric deltas for AI coding agents.
- **CLI Commands**:
  - `repodna advisor [target] [--category ...] [--min-severity ...] [--format {table,json,markdown}] [-o OUTPUT]`: Terminal-based refactoring advisory report generation with colorized table, JSON, or Markdown output.
  - `repodna start [--host ...] [--port ...] [--open-browser]`: Single-command full-stack launcher starting backend and static web workstation.
- **Windows Quick-Start & Developer Onboarding**:
  - `start-repodna.bat` and `start-repodna.ps1`: Zero-friction Windows launchers setting up dependencies, running health diagnostics, and opening the browser.
- **Refactoring Advisor UI & Unified Workstation**:
  - Dedicated **Refactoring Advisor** tab with Sparkles icon in the HeaderBar.
  - Executive KPI summary strip (Total Recommendations, Critical Cycles, High Coupling, Layer Inversions, Oversized Hubs).
  - Multi-category filter pills and minimum severity filter dropdown.
  - Interactive recommendation cards with severity badges, category tags, interactive action checklists, and metric delta previews.
  - "Copy Prompt" button generating prompt-ready instructions for AI coding assistants.
  - "Inspect in Graph" cross-navigation jumping directly from advisor cards to the module in the 3-Pane Architecture Studio graph.
  - Inspector Panel integration with "Open in Advisor" button for selected modules.
  - Command Palette integration (`Ctrl+K` -> `act-advisor`).
  - Full bilingual localization (English & Turkish).
- **Playwright End-to-End Verification**:
  - `frontend/e2e/advisor.spec.ts` verifying scan, navigation, filter pills, checklist interactions, and cross-navigation to Studio graph.
  - Production verification screenshots: `docs/design/after/advisor-overview.png` and `docs/design/after/advisor-cross-navigation-graph.png`.

## [0.6.0] - 2026-11-11

### Added
- **Architecture Time Machine Engine (`repodna.history`)**:
  - **Historical Snapshot Engine (`HistoricalSnapshotEngine`)**:
    - Analyzes past Git commit SHAs and references without modifying the active working tree or branch pointer, streaming `git archive --format=tar` into an isolated in-memory extraction pipeline.
    - Full AST extraction and symbol indexing across Python, TypeScript/TSX, JavaScript/JSX, Go, and Rust for any historical revision.
    - Security-hardened extraction protecting against zip-slip / tar-slip directory traversal, Windows reserved device names (`CON`, `PRN`, `AUX`, `NUL`, `COM1-9`, `LPT1-9`), symlink escapes, and tarbomb size limits (`MAX_EXTRACT_SIZE_BYTES = 500MB`, `MAX_MEMBERS = 100,000`).
  - **Deterministic Multi-Tier Historical Cache (`HistoricalCache`)**:
    - Atomic filesystem persistence with cache keys incorporating repository identity, commit SHA, snapshot schema version, tree-sitter grammar versions, and analyzer configuration fingerprints.
    - Clean separation of deterministic architectural data from runtime execution metadata (`analyzed_at`, `analysis_duration_ms`, `cache_hit`), ensuring bitwise repeatable snapshot verification.
    - Windows-resilient atomic replace loop with exponential backoff on file-locking (`PermissionError` / WinError 32).
    - Corrupted entry detection and automatic self-healing fallback.
  - **Evolution Diff Engine (`EvolutionDiffEngine`)**:
    - Semantic comparison between historical snapshots (`base` vs `head`).
    - Granular module categorization: `added`, `removed`, `modified`, and `renamed` (detected via Git similarity heuristics and structural AST equivalence).
    - Longitudinal cycle tracking: `new_cycles`, `resolved_cycles`, and `persisting_cycles`.
    - Health score trajectory, coupling shifts, and architectural drift deltas.
  - **Historical Evidence Provider (`HistoricalEvidenceProvider`)**:
    - Non-destructive Git blob reading via `git cat-file -p <commit_sha>:<file_path>`.
    - Cryptographic SHA-256 content hashing and tamper verification with zero working tree side-effects.
  - **Historical Timeline Engine (`TimelineEngine`)**:
    - Sequential architectural trajectory generation across Git commit histories.
    - Explicit failure modeling: commits that fail analysis are captured with error messages, completely eliminating "zero fake zeros" from health metrics and trends.
    - Cooperative cancellation checkpoints allowing background jobs to cleanly abort upon request.
  - **Historical REST API & Asynchronous Job Infrastructure**:
    - Endpoints for commit history (`GET /history/commits`), snapshot extraction (`POST /history/snapshots`), evolution diff (`POST /history/diff`), timeline analysis (`POST /history/timeline`), and historical evidence inspection (`GET /history/evidence/{evidence_id}`).
    - Asynchronous background jobs (`POST /history/jobs`, `GET /history/jobs/{job_id}`, `POST /history/jobs/{job_id}/cancel`, `GET /history/jobs/{job_id}/result`).
    - Multi-analysis job isolation preventing cross-analysis data leakage or unauthorized job manipulation.
    - Completed job persistence: cancellation requests on finished jobs preserve status and results.
  - **Extended Model Context Protocol (MCP) Suite (22 Tools Total)**:
    - 5 new agent tools: `repodna_history_snapshots`, `repodna_history_analyze`, `repodna_history_diff`, `repodna_history_timeline`, `repodna_history_evidence`.
  - **Historical Intelligence Workstation UI**:
    - Dedicated "Time Machine" workspace featuring interactive timeline scrubber, commit search, snapshot module inspector, evolution diff viewer, and architecture trends table.
    - Historical Git Blob Evidence Inspector modal with syntax highlighting, line numbering, and cryptographic provenance verification.
    - Complete bilingual localization (TR/EN), keyboard shortcut collision guards, and responsive themes.
  - **CLI Commands**:
    - `repodna history snapshots [target]`
    - `repodna history analyze <commit_sha> [target]`
    - `repodna history diff <base_commit> <head_commit> [target]`
    - `repodna history timeline [target] [--limit ...]`
    - Global `--version` flag outputting version `0.6.0`.

## [0.5.0] - 2026-11-11

### Added
- **Repository Brain Core (`repodna.brain`)**:
  - Tree-sitter AST symbol extractor (`DeepSymbolExtractor`) extracting functions, classes, methods, interfaces, types, parameters, return types, signatures, and container hierarchies across Python, TypeScript/TSX, JavaScript/JSX, Go, and Rust.
  - Multi-factor deterministic smart context retrieval engine (`SmartRetrievalEngine`) scoring query intent, exact symbol matching, identifier tokenization, semantic synonyms, and graph coupling hubs.
  - Anti-hallucination and misleading comment guards demoting comments with explainable relevance scoring.
  - Hierarchical reference resolution separating symbol usages into `VERIFIED` (statically proven import and call chains), `CANDIDATE` (syntactically plausible matches), and `UNRESOLVED` (dynamic invocations).
  - Symbol impact and blast radius tracer (`SymbolTracer`) identifying direct callers, upstream dependent modules, and cycle warnings.
  - Cryptographic evidence ledger (`EvidenceLedger`) generating immutable citations (`ev_<sha256>`) tied to file path and Git commit SHA with active staleness verification.
- **Repository Passport v2 (`repodna.passport`)**:
  - Upgraded schema v2.0.0 supporting structural entrypoints, cross-module dependency links, verified findings, and strict privacy guards.
  - Two-way migration engine (`PassportMigrator`) maintaining full backward-compatibility with v1.0.0 manifests.
- **Token-Budgeted Context Engine (`repodna.context`)**:
  - Context generator enforcing strict token budgets across `compact`, `focused`, and `deep` presets, plus minimal contract mode.
  - Empirical token savings tracking and continuation pagination.
- **Intelligence Workstation UI**:
  - Precision Workstation tab with 4 dedicated workspaces: Smart Code Explorer, Symbol Relationships, Evidence Ledger, and Agent Context Generator.
  - Real-time AST previews, caller/callee inspection, staleness checking, and token budget meters.
  - Bilingual localization (TR/EN) and responsive viewports (Desktop, Tablet, Mobile).
- **Extended MCP Architecture Suite (17 Tools Total)**:
  - 5 new agent tools: `repodna_search_code`, `repodna_find_symbol`, `repodna_trace_symbol`, `repodna_get_evidence`, `repodna_build_context`.
- **CLI Commands**:
  - `repodna search <query> [target]`
  - `repodna symbols [target] [--name ...] [--kind ...] [--container ...]`
  - `repodna evidence [target] [--id ...] [--file ...] [--symbol ...]`
- **Production CI / E2E Automation**:
  - Integrated Playwright Chromium E2E test job in `.github/workflows/ci.yml` with real backend/frontend daemons and artifact uploads.

### Fixed & Hardened
- **Path Boundary & TOCTOU Security (`repodna.security`)**:
  - Replaced path-only checks with descriptor-based atomic opening (`os.open`) with `O_RDONLY | O_BINARY` and POSIX `O_NOFOLLOW`.
  - Open file descriptor containment verification (`_verify_fd_containment_and_type`) asserting regular files (`S_ISREG`) and size limits.
  - Windows NT handle path verification via `kernel32.GetFinalPathNameByHandleW` and `msvcrt.get_osfhandle(fd)` blocking symlink races.
- **Git Revision Provenance & Dirty Invalidation**:
  - Dynamic `git rev-parse HEAD` resolution replacing unverified symbolic branch names.
  - Deterministic snapshot identity (`git:{sha}+dirty.{hash}`) combining porcelain status, file sizes, mtime, and fast SHA-256 content hashes (for files <= 512KB).
- **Non-Git Fixture Symbol Extraction**:
  - Resolved Pydantic validation issue on `EvidenceReference.repository_revision` for non-git directories, defaulting safely to `"WORKING_TREE"` and fixing the 0-symbol issue in PayFlow.
- **Large Repository Reference Resolution Performance**:
  - Optimized `_resolve_cross_references` from $O(N)$ scanning to $O(1)$ set lookups across 55,000+ references.

## [0.4.0] - 2026-11-10

### Added
- **PR Architecture Guardian (`repodna.guardian`)**:
  - Continuous git revision comparison engine evaluating architectural drift across PR branches via `repodna guardian check <path> --base <ref> --head <ref>`.
  - Strict separation of **newly introduced** circular dependencies (`new_cycles`) from existing baseline cycles and resolved cycles (`resolved_cycles`).
  - Coverage-aware verdict engine producing unambiguous outcomes (`PASS`, `WARNING`, `FAIL`, `INCONCLUSIVE`).
  - Deterministic risk assessment scoring ($0$–$100$) and risk tier classification (`LOW`, `MEDIUM`, `HIGH`, `CRITICAL`) based on verified cycles, contract violations, coupling spikes, and changed hub centrality.
  - Native GitHub Actions Job Summary output (`--format markdown`) and machine-readable JSON output (`--format json`).
- **Architecture Contract Engine (`repodna.contract`)**:
  - Versioned YAML architecture policy specification (`.repodna/architecture.yml`).
  - Typed Pydantic schema validation for contract rules, constraints (`disallow_imports`, `allow_imports`), and severities (`error`, `warning`, `info`).
  - Deterministic, ReDoS-safe path pattern matching implementing gitignore semantics via `pathspec`.
  - Dual policy execution modes: `advisory` (audit-only) and `enforce` (fails check on verified high-confidence violations).
  - Existing violation suppression via baseline file (`--baseline <path>`).
  - Unsupported language and unresolved import honesty disclosure with configurable `unknown_behavior` (`warn`, `ignore`, `fail`).
  - Complete CLI suite: `repodna contract init`, `repodna contract validate`, and `repodna contract check`.
- **Repository Passport (`repodna.passport`)**:
  - Portable, deterministic architectural identity manifest (`.repodna/passport.json`).
  - Verifiable structural metadata: Git commit SHA, Tree-sitter AST coverage percentage, and confidence grade.
  - Architectural hub inventory, module centrality metrics, identified boundaries, and verified findings.
  - Strict security and privacy boundaries: zero source code bodies, zero credentials/tokens, and normalized relative repository paths.
  - Complete CLI suite: `repodna passport generate` and `repodna passport validate`.
- **Extended MCP Architecture Suite (`repodna.mcp`)**:
  - Expanded official MCP SDK server from 8 to 12 read-only tools:
    - `repodna_get_passport`: Retrieve deterministic repository passport manifest.
    - `repodna_get_contract`: Inspect active architecture contract rules and policy.
    - `repodna_check_contract`: Evaluate target workspace against architectural contract rules.
    - `repodna_pr_guardian`: Assess pull request architecture drift, cycle delta, and verdict.
- **Precision Workstation UI (v0.4.0 Experience)**:
  - **Guardian Overview**: Interactive PR revision comparator, verdict badge, risk score meter, cycle delta breakdown, and markdown summary preview.
  - **Contract Inspector**: Live architectural policy rule viewer, pattern matching inspectors, and severity indicators.
  - **Passport Viewer**: Repository identity card, structural hub analysis, module inventory, and passport JSON export.
  - Full bilingual localization (English & Türkçe) across all new views and metrics.
- **GitHub Actions Integration & Automation**:
  - Production GitHub Actions workflow template (`examples/github-actions/architecture-guardian.yml`) running under least-privilege permissions (`contents: read`).
  - Enterprise integration guide (`docs/integrations/github-actions.md`).
  - Updated internal CI (`.github/workflows/ci.yml`) testing contract validation, passport generation, and guardian assessment.

### Fixed & Hardened
- **Baseline Fail-Safe Validation (`repodna.contract.loader`)**:
  - Replaced silent empty set return on corrupted or missing baselines with explicit `FileNotFoundError` and `ValueError` validation errors.
  - Enforced `is_safe_subpath` repository boundary checks and 5 MB size limit on baseline files.
- **Contract Evaluation Correctness & Disambiguation (`repodna.contract.evaluator`)**:
  - Separated rule statuses into `rules_passed`, `rules_violated`, `rules_unmatched` (0 files matched), and `rules_unknown` (inconclusive due to unsupported AST or unresolvable imports).
  - Resolved multi-rule loop variable leak (`matching_files`) in coverage calculation.
  - Reinforced `unknown_behavior` (`fail`, `warn`, `ignore`) semantics across varying AST support levels.
- **Guardian Verdict vs CI Exit Code Decoupling (`repodna.guardian.engine`)**:
  - Decoupled engineering architectural verdict (`PASS`, `WARNING`, `FAIL`, `INCONCLUSIVE`) from process exit code (`should_block_ci`).
  - Default advisory mode now strictly informs users with exit code `0`, while enforce mode blocks CI (exit code `1`) on verified circular loops and contract errors.
- **Repository Passport Privacy & Revision Provenance (`repodna.passport`)**:
  - Automatically sanitizes target paths, stripping Windows username paths, user home folders, and tokens into relative project identifiers.
  - Verifies Git revision provenance against hexadecimal commit SHAs (`^[0-9a-fA-F]{7,40}$`), clearly distinguishing verified SHAs from unverified symbolic refs (`HEAD`).
  - Added strict privacy scanner in `validator.py` rejecting leaks with `SecurityValidationError`.
- **GitHub Actions Installation Reliability**:
  - Updated starter workflow to use pinned Git source distribution for pre-release stability and immutable pull_request event context commit SHAs (`github.event.pull_request.base.sha` and `github.event.pull_request.head.sha`).

## [0.3.0] - 2026-11-09

### Added
- **Official Model Context Protocol (MCP SDK v2) Server (`repodna.mcp`)**:
  - Implemented official Python MCP SDK (`mcp>=2.0.0`) integration on stdio transport.
  - Exposed 8 deterministic, read-only architectural intelligence tools:
    - `repodna_repository_overview`: Executive scorecard, health grade, AST coverage, and key hubs.
    - `repodna_architecture_map`: Package clusters, module hierarchy, and cross-cluster dependency links.
    - `repodna_find_modules`: Tree-sitter AST symbol and path relevance scoring with coupling metrics.
    - `repodna_module_dependencies`: Afferent ($C_a$) and efferent ($C_e$) direct and transitive dependency chains.
    - `repodna_module_findings`: Tarjan SCC circular dependency cycles (`ARCH-001`) and architectural rule violations.
    - `repodna_architecture_diff`: Bi-temporal commit and working tree architecture diffing with cycle regression tracking.
    - `repodna_change_impact`: Change Guardian pre-edit blast radius calculation and downstream risk classification.
    - `repodna_analysis_coverage`: AST grammar coverage ratio, unverified rules, and honest `N/A` guarantees.
  - Direct execution support via `python -m repodna.mcp`.
  - Strict protocol isolation (stdout reserved for JSON-RPC; all logs directed to stderr).
- **Git Architecture Diff Engine (`repodna.diff`)**:
  - Bi-temporal git revision and working tree architectural comparison via `repodna diff <base> [head]`.
  - Git-verified file rename tracking (`git diff -M --name-status`) distinguished from AST heuristic matching.
  - Critical cycle regression detection (`cycle_changes.new_cycles`) and health score delta tracking.
  - Hardened sandbox extraction with tar-slip path traversal guards (`is_safe_subpath`), symlink restrictions, and git revision validation.
- **Token-Budgeted Agent Context Builder (`repodna.context`)**:
  - Three calibrated density modes: `compact` (summary & hubs), `focused` (query-driven AST symbols & callers), and `deep` (complete graph metrics & findings).
  - Synthetic Architectural Context Reduction (-99.6% raw context reduction compared to naive whole-file prompting).
- **One-Command AI Agent Installer & Diagnostic Tool (`repodna setup`, `repodna doctor`)**:
  - Idempotent configuration for Google Antigravity (`.agents/mcp_config.json`) and OpenAI Codex (`.codex/config.toml` & `~/.codex/config.toml`).
  - Automatic `.bak` backups preserving existing user-defined tools and TOML sections.
  - Two-tier diagnostic motor in `repodna doctor` separating Core Engine (`HEALTHY`) from Agent Integration (`READY` / `INCOMPLETE` / `NOT INSTALLED ON HOST`).
  - Live stdio connection handshake verification before reporting `READY`.
  - `--repair` subcommand for refreshing missing or corrupted integrations.
- **Portable Agent Skill (`integrations/agent-skills/repodna`)**:
  - Standards-compliant `SKILL.md` package with bilingual (TR/EN) guidance, 5 canonical developer workflows, CLI fallback, and unsupported language honesty rules.
  - Enforced 100% mathematical guarantee against same-size same-mtime content modifications on repositories with <= 300 files via direct Blake2b hashing.
  - Implemented force=True parameter on all MCP tools for unconditional cache bypass on large repositories.
  - Hardened default workspace boundary against execution from drive root or user home directory, returning explicit ROOT_VIOLATION security errors.

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
