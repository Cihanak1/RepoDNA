# ADR-002: RepoDNA v0.4.0 — Architecture Guardian, Contract Engine, and Repository Passport

## Status
Accepted

## Context
RepoDNA v0.3.0 established a local-first, deterministic static analysis core, differential revision comparison (`ArchitectureDiffEngine`), and read-only Model Context Protocol (MCP) server for AI coding agents.

However, modern software engineering teams and autonomous AI agents require continuous architectural enforcement across pull requests:
1. **Unregulated Architectural Drift:** Developers and AI code generation models frequently introduce forbidden cross-layer imports (e.g. domain layers importing infrastructure frameworks, or frontend code directly importing backend models).
2. **Alert Fatigue from Baseline Violations:** Traditional linters and static analysis tools fail on existing repositories by dumping hundreds of pre-existing legacy violations onto a new PR, causing developers to disable the tool.
3. **No Portable Architecture Identity:** AI agents lack a lightweight, deterministic structural manifest ("passport") that certifies architectural hubs, dependency bounds, AST coverage limits, and verified contracts without re-indexing the entire codebase on every single prompt.
4. **False Certainty on Unsupported Languages:** When an import cannot be resolved or a language is not supported with full AST, existing tools either silently pass or guess. RepoDNA requires absolute honesty: unknown evaluations must never masquerade as passing compliance.

## Architectural Decisions

### 1. Architecture Contract Engine (`repodna.contract`)
- Defines declarative architecture policies in versioned YAML (`.repodna/architecture.yml`).
- Implements strict Pydantic v2 schemas:
  - `ArchitectureContract`: `version`, `policy` (`mode: advisory | enforce`, `unknown_behavior: warn | ignore | fail`), `rules`, `metadata`.
  - `ContractRule`: `id`, `title`, `description`, `from` (POSIX glob pattern(s)), `disallow_imports` (POSIX glob pattern(s)), `allow_imports` (optional whitelist), `severity` (`error`, `warning`, `info`).
- **Safety First:** Safe YAML deserialization with PyYAML `yaml.safe_load`, file size cap (512 KB), no remote fetching, no command execution, and ReDoS-safe POSIX glob pattern matching via `pathspec`.
- **Honesty Invariant:** Unresolved references and unsupported language files mapped to rule patterns are recorded as `unknown_evaluations` rather than passing evaluations.
- **Fail-Safe Baseline Validation:**
  - Unspecified baseline: safely returns empty baseline.
  - Explicitly specified but missing: raises `FileNotFoundError`.
  - Corrupted JSON or schema error: raises `ValueError` (never silently converts to empty baseline).
  - Path traversal and 5 MB size caps strictly enforced via `is_safe_subpath`.
- **Rule Status Partitioning:** Rules are partitioned into `rules_passed`, `rules_violated`, `rules_unmatched` (0 files matched), and `rules_unknown` (inconclusive due to unsupported AST/unresolved imports).

### 2. PR Architecture Guardian (`repodna.guardian`)
- Builds atop `SnapshotManager` and `ArchitectureDiffEngine` to evaluate pull requests between two Git revisions (`base` vs `head`).
- Separates findings into three distinct, non-overlapping categories:
  - `new_violations`: Introduced in the PR (actionable).
  - `resolved_violations`: Fixed by the PR (celebrated).
  - `baseline_violations`: Pre-existing in base (tracked separately, avoiding alert fatigue).
- Traces circular dependency deltas (`new_cycles`, `resolved_cycles`, `persisting_cycles`).
- **Decoupled Architecture Verdict vs CI Exit Code:**
  - **Verdict:** True architectural assessment (`PASS`, `WARNING`, `FAIL`, `INCONCLUSIVE`). Newly introduced cycles always receive a `FAIL` verdict.
  - **CI Gating:**
    - `advisory` mode: Informational only; `should_block_ci = False` and exit code is `0`.
    - `enforce` mode: `should_block_ci = True` and exit code is `1` on `FAIL`, `2` on `INCONCLUSIVE`, `0` on `PASS`/`WARNING`.
- **Deterministic Risk Scoring ($0$–$100$):**
  - Factor A (New cycles): $\min(60.0, \text{count} \times 30.0)$
  - Factor B (New contract violations): enforce ($\min(50.0, \text{errors} \times 25.0 + \text{warnings} \times 15.0)$), advisory ($\min(25.0, \text{errors} \times 10.0 + \text{warnings} \times 5.0)$)
  - Factor C (Coupling surges on hubs): $\min(20.0, \text{hubs} \times 10.0)$
  - Factor D (Health degradation): $\min(20.0, |\Delta \text{score}| \times 2.5)$ if $\Delta \text{score} < -2.0$
  - Tiers: `LOW` (0–15), `MODERATE` (16–40), `HIGH` (41–70), `CRITICAL` (71–100).

### 3. Repository Passport (`repodna.passport`)
- Standardized, portable structural identity saved to `.repodna/passport.json` or generated dynamically in memory.
- Contains:
  - Schema version, Git revision, analysis timestamp, and RepoDNA version.
  - AST and static coverage percentages with explicit confidence levels.
  - Architectural hubs (high fan-in / fan-out modules).
  - Module inventory (sanitized relative paths, LOC, instability, cycle flags, hub status).
  - Active architecture contracts, verified findings, and unverified rules.
- **Security & Privacy Guardrails:**
  - Zero source code bodies, environment variables, tokens, or credentials.
  - Zero absolute host paths (`/Users/`, `C:\Users\`, `/home/`, `/tmp`, `\Temp\`); all paths sanitized to repo-relative identifiers.
  - Explicit commit provenance verification: validates hexadecimal Git commit SHAs (`^[0-9a-fA-F]{7,40}$`) vs unverified symbolic refs (`HEAD`).
  - Privacy validation scanner in `validator.py` rejecting leaks with `SecurityValidationError`.

### 4. Unified MCP & CLI Surface
- Exposes new MCP tools: `repodna_get_passport`, `repodna_get_contract`, `repodna_check_contract`, and `repodna_pr_guardian`.
- Enforces read-only behavior through MCP tools. Permanent file creation (`repodna passport generate`, `repodna contract init`) is strictly reserved for the explicit CLI.
- Maintains identical architectural truth across CLI, REST API, MCP, and the Workstation UI.
