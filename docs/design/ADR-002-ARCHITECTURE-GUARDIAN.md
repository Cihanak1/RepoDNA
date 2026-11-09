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
- **Safety First:** Safe YAML deserialization with PyYAML `yaml.safe_load`, file size cap (512 KB), no remote fetching, no command execution, and no regex DoS vectors (POSIX glob pattern matching).
- **Honesty Invariant:** Unresolved references and unsupported language files mapped to rule patterns are recorded as `unknown_evaluations` rather than passing evaluations.
- **Baseline Support:** Existing violations can be captured in a baseline snapshot to ensure CI and PR reviews focus exclusively on newly introduced regressions.

### 2. PR Architecture Guardian (`repodna.guardian`)
- Builds atop `SnapshotManager` and `ArchitectureDiffEngine` to evaluate pull requests between two Git revisions (`base` vs `head`).
- Separates findings into three distinct, non-overlapping categories:
  - `new_violations`: Introduced in the PR (actionable).
  - `resolved_violations`: Fixed by the PR (celebrated).
  - `baseline_violations`: Pre-existing in base (tracked separately, avoiding alert fatigue).
- Traces circular dependency deltas (`new_cycles`, `resolved_cycles`, `persisting_cycles`).
- Synthesizes an authoritative architectural verdict:
  - `PASS`: Zero new cycles, zero new enforce violations, healthy metrics.
  - `WARNING`: Advisory violations or notable coupling degradation.
  - `FAIL`: Verified high-severity policy violations in `enforce` mode, or verified new circular dependencies.
  - `INCONCLUSIVE`: Analysis coverage insufficient or degraded to the point that architecture changes cannot be verified with high confidence.
- Provides GitHub Actions Job Summary output (Markdown table, collapsible details, and annotations).

### 3. Repository Passport (`repodna.passport`)
- Standardized, portable structural identity saved to `.repodna/passport.json` or generated dynamically in memory.
- Contains:
  - Schema version, Git revision, analysis timestamp, and RepoDNA version.
  - AST and static coverage percentages with explicit confidence levels.
  - Architectural hubs (high fan-in / fan-out modules).
  - Module inventory (sanitized relative paths, LOC, instability, cycle flags, hub status).
  - Active architecture contracts, verified findings, and unverified rules.
- **Security & Privacy:** Contains NO source code bodies, absolute host paths, environment variables, or secrets. Output size is deterministically capped.

### 4. Unified MCP & CLI Surface
- Exposes new MCP tools: `repodna_get_passport`, `repodna_get_contract`, `repodna_check_contract`, and `repodna_pr_guardian`.
- Enforces read-only behavior through MCP tools. Permanent file creation (`repodna passport generate`, `repodna contract init`) is strictly reserved for the explicit CLI.
- Maintains identical architectural truth across CLI, REST API, MCP, and the Workstation UI.
