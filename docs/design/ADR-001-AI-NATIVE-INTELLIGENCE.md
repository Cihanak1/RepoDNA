# ADR-001: AI-Native Repository Intelligence Platform (RepoDNA v0.3.0)

## Status
Accepted

## Context
RepoDNA v0.2.0 delivered a high-precision graphical workstation for human software engineers, complete with interactive dependency graphs, Martin instability metrics, cyclic dependency detection, and bilingual localization.

However, modern AI coding agents (such as Google Antigravity, Claude Code, OpenAI Codex, and Cursor) navigate large repositories with significant limitations:
1. **Blind Exploration:** Agents repeatedly run grep/find commands, consuming tens of thousands of tokens scanning unrelated files.
2. **Hidden Dependency Risks:** Agents edit a function or module without realizing it is part of a circular dependency or has a high fan-in (is heavily depended upon by other modules).
3. **No Architectural Diffing:** Agents cannot see the architectural regression (e.g. new circular dependencies or coupling spikes) introduced between two git commits.
4. **False Confidence:** Agents assume full understanding even in repositories where language AST coverage is partial or absent.

RepoDNA v0.3.0 elevates RepoDNA from an interactive dashboard into an **open, evidence-based, model-agnostic Repository Intelligence Platform** specifically engineered for AI coding agents.

## Architectural Decisions

### 1. Read-Only Intelligence Core (`repodna.intelligence`)
We build an extensible, query-oriented intelligence service directly over RepoDNA's proven `AnalysisResult` engine.
- Every query returns both **machine-readable structured JSON** and **concise human/agent-readable summaries**.
- Queries include: `get_repository_overview`, `get_architecture_map`, `find_relevant_modules`, `get_module_details`, `get_dependencies`, `get_dependents`, `get_architecture_findings`, `get_analysis_coverage`, and `get_change_impact`.
- **Honesty Invariant:** Queries never hallucinate semantic details. If a language has no AST parser (such as C# in NiceWP), it is marked as `LanguageSupportLevel.PARTIAL_STATIC` or `UNSUPPORTED`, and unverified rules are explicitly noted.

### 2. Architecture Diff Engine (`repodna.diff`)
- We introduce immutable revision snapshots (`SnapshotManager`).
- Revisions (`HEAD~1`, `HEAD`, branch names, commit SHAs) are resolved safely through Git and analyzed independently in read-only isolation.
- The diff engine computes:
  - Added / removed / renamed modules.
  - Added / removed dependency edges.
  - New cyclic SCCs introduced (architectural regression).
  - Resolved cyclic SCCs (architectural improvement).
  - Per-module instability / coupling deltas.
  - Health score and grade delta.
  - Analysis coverage and AST differences (preventing coverage drop from masquerading as deleted files).

### 3. Agent-Ready Context Engine (`repodna.context`)
- Supports three output modes:
  - `compact`: High-density summary (< 800 tokens approx.) for quick orientation.
  - `focused`: Targeted context for specific files with direct coupling and immediate impacts.
  - `deep`: Complete metrics, symbol tables, cycle traces, and full evidence.
- Approximate budget support (`max_tokens` / `max_chars`) with stable deterministic sorting, pagination, and continuation tokens.

### 4. Portable Agent Skill (`integrations/agent-skills/repodna/`)
- Fully compliant with the [Agent Skills specification](https://agentskills.io/specification).
- Houses `SKILL.md`, `references/`, and `examples/`.
- Treats codebase files as untrusted data; enforces prompt-injection resistance.
- Defines a standardized 7-part response format for AI agents (Conclusion -> Files -> Why -> Verified Deps -> Possible Impact -> Unknowns/Coverage -> Next Action).

### 5. Local-First Model Context Protocol (MCP) Server (`repodna.mcp`)
- Implements standard JSON-RPC 2.0 over `stdio`.
- `sys.stdout` is strictly reserved for JSON-RPC frames; all server logging goes to `sys.stderr`.
- Exposes 8 read-only tools:
  - `repodna_repository_overview`
  - `repodna_architecture_map`
  - `repodna_find_modules`
  - `repodna_module_dependencies`
  - `repodna_module_findings`
  - `repodna_architecture_diff`
  - `repodna_change_impact`
  - `repodna_analysis_coverage`
- Enforces strict filesystem path boundaries (prevents path traversal / symlink escape).

### 6. One-Command Installer & Environment Doctor (`repodna.cli.installer`)
- `repodna setup --agent codex|claude|antigravity|auto` installs skills and MCP configurations idempotently with automated backups.
- `repodna doctor` verifies environment health, CLI availability, Tree-sitter parsers, git connectivity, and skill/MCP registration.
- Cross-platform support for Windows (PowerShell), macOS, and Linux.

### 7. AI Change Guardian
- Read-only impact assessment before and after proposed code edits.
- Clearly delineates "Verified dependency changes" from "Possible impact".

## Consequences
- **Positive:** Agents get instant, deterministic architectural awareness with minimal token usage. Zero hallucination regarding dependencies.
- **Positive:** Seamless compatibility with Claude Code, OpenAI Codex, and Google Antigravity.
- **Boundary:** Read-only by design. RepoDNA will not automatically edit files, commit, or push code.
