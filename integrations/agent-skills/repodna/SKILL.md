---
name: repodna
description: "Evidence-based repository intelligence platform for architecture discovery, dependency graph tracing, change impact blast radius, circular dependency detection, PR architecture guarding, and architecture contract enforcement."
---

# RepoDNA — AI-Native Repository Intelligence & Repository Brain

RepoDNA provides deterministic, read-only architectural and code intelligence for AI coding agents (Antigravity, Codex, Claude Code, Cursor). It extracts Tree-sitter AST dependency graphs, tracks cross-module symbol definitions and call sites, calculates Robert C. Martin instability metrics, detects circular dependency cycles (Tarjan SCC), verifies architectural contracts, and manages an immutable Evidence Ledger with staleness detection.

---

## 1. Fast Routing & Tool Invocation Matrix (17 MCP Tools)

RepoDNA provides 17 read-only MCP tools:

| Category | Tool Name | When to Use | Key Arguments |
| :--- | :--- | :--- | :--- |
| **Discovery** | `repodna_repository_overview` | First repo discovery, stack, LOC, hubs, cycles | `target="."`, `format="text"` |
| **Discovery** | `repodna_architecture_map` | High-level package/module clustering & layers | `target="."`, `level="clusters"`, `limit=30` |
| **Discovery** | `repodna_get_passport` | Structural identity, AST coverage, hubs, v2 brain summaries | `target="."`, `version="2.0"`, `format="json"` |
| **Navigation** | `repodna_find_modules` | Module feature location, symbol/module discovery | `target="."`, `query="..."`, `limit=10` |
| **Navigation** | `repodna_module_dependencies` | Inspect incoming & outgoing imports of a file | `target="."`, `file_path="..."`, `depth=1` |
| **Navigation** | `repodna_search_code` | Smart retrieval across code, symbols, and architecture | `target="."`, `query="..."`, `limit=10` |
| **Navigation** | `repodna_find_symbol` | Search Tree-sitter indexed symbols by name, kind, file | `target="."`, `name="..."`, `kind="function"` |
| **Intelligence** | `repodna_trace_symbol` | Trace callers, callees, imports, container & blast radius | `target="."`, `symbol_name="..."`, `symbol_id="..."` |
| **Intelligence** | `repodna_get_evidence` | Retrieve verified architectural citations & staleness | `target="."`, `evidence_id="..."`, `file_path="..."` |
| **Intelligence** | `repodna_build_context` | Budget-aware context (compact/focused/deep) for LLMs | `target="."`, `mode="focused"`, `max_tokens=2000` |
| **Governance** | `repodna_module_findings` | Audit violations (`ARCH-001` .. `ARCH-006`, `SEC-001`) | `target="."`, `rule_id="ARCH-001"` (opt) |
| **Governance** | `repodna_get_contract` | Read `.repodna/architecture.yml` rules & layers | `target="."`, `format="yaml"` |
| **Governance** | `repodna_check_contract` | Evaluate repo against architecture contract rules | `target="."`, `mode="enforce"` |
| **Governance** | `repodna_pr_guardian` | PR assessment between Git revisions with pass/fail verdict | `target="."`, `base_ref="HEAD~1"`, `head_ref="HEAD"` |
| **Delta** | `repodna_architecture_diff` | Structural diff between two Git revisions | `target="."`, `base_ref="HEAD~1"`, `head_ref="HEAD"` |
| **Delta** | `repodna_change_impact` | Pre-edit blast radius & affected dependents check | `target="."`, `changed_files=["..."]` |
| **Coverage** | `repodna_analysis_coverage` | Verify AST coverage ratio and unverified rules | `target="."` |

---

## 2. Agent Workflows for Antigravity & Codex

### Workflow 1: Repository Discovery & Orientation
1. Call `repodna_repository_overview(target=".")` to understand languages, lines of code, hub modules, and cycle groups.
2. Call `repodna_get_passport(target=".", version="2.0")` to obtain the verified Repository Passport v2 manifest with entrypoints and module roles.

### Workflow 2: Relevant Symbol Lookup & Disambiguation
1. Call `repodna_search_code(target=".", query="auth token validator")` to locate primary candidate files and symbols with relevance explanations.
2. If multiple symbols share the same name (e.g. `validate`), call `repodna_find_symbol(target=".", name="validate")` to inspect all candidates.
3. Call `repodna_trace_symbol(target=".", symbol_id="sym_...")` with the specific deterministic `symbol_id` to unambiguously trace callers and blast radius.

### Workflow 3: Token-Budgeted Context Building
1. Call `repodna_build_context(target=".", mode="focused", query="<task_description>", max_tokens=2000)`.
2. Inspect the returned Markdown: it contains verified architectural summaries, relevant module dependencies, and exact evidence references.
3. Check `is_savings_estimated` and `token_counting_method` (`tiktoken_cl100k` vs `heuristic_chars`).

### Workflow 4: Evidence Retrieval & Staleness Detection
1. For every critical code claim, retrieve the citation via `repodna_get_evidence(target=".", evidence_id="ev_...")` or `file_path="..."`.
2. Always inspect the `staleness_reason`:
   - `FRESH`: Verified exact snippet at recorded coordinates.
   - `LINE_SHIFT`: Code moved in file (delta lines recorded); line numbers shifted.
   - `CONTENT_CHANGED`: Code snippet was modified since index creation.
   - `REVISION_MISMATCH`: Evidence was created on a different Git revision.
   - `FILE_DELETED`: File was removed or emptied.
3. **Evidence Discipline:** Never present stale evidence as freshly verified. If evidence is missing or stale, state so explicitly.

### Workflow 5: Pre-Edit Safety & PR Architecture Guardian
1. Before modifying high-impact modules, call `repodna_change_impact(target=".", changed_files=["src/core.py"])`.
2. Before opening a PR or completing a branch task, call `repodna_pr_guardian(target=".", base_ref="main", head_ref="HEAD")`.
3. Check the verdict (`PASS`, `WARNING`, `FAIL`). Any circular dependency (`ARCH-001`) or layer breach is a blocker.

---

## 3. Real User Queries & Exact Guides (TR / EN)

### Q1: Codebase Purpose & Architecture / "Bu repository ne işe yarıyor ve mimarisi nasıl?"
- **Action:** Call `repodna_repository_overview(target=".")` and `repodna_get_passport(target=".", version="2.0")`.
- **Response Structure:**
  1. Primary programming languages and AST coverage percentage.
  2. Identified architectural hubs (highest Fan-In modules).
  3. Identified cycles (Tarjan SCC count).
  4. Core entrypoints and module layering from Passport v2.

### Q2: Locating Feature & Symbol / "Kullanıcı girişiyle ilgili sembolleri ve dosyaları bul"
- **Action:** Call `repodna_search_code(target=".", query="auth login session user credentials", limit=5)`.
- **Response Structure:**
  1. Top matching file paths ranked by composite relevance score with explainable reasons.
  2. Matched symbols with exact definitions, kind, and line numbers.
  3. Verified vs candidate reference indicators.

### Q3: Symbol Callers & Blast Radius / "X fonksiyonunu değiştirirsem nereler etkilenir?"
- **Action:** Call `repodna_trace_symbol(target=".", symbol_name="X")`. If ambiguous, supply `symbol_id` or `file_path`.
- **Response Structure:**
  1. Target symbol definition with evidence ID.
  2. Verified callers (proven AST references) vs candidate callers.
  3. Downstream impact count and dependent module list.
  4. Cyclic SCC warning if symbol participates in a circular dependency.

### Q4: Evidence Audit / "Bu mimari iddia hangi kaynak kanıtına dayanıyor?"
- **Action:** Call `repodna_get_evidence(target=".", evidence_id="ev_...")`.
- **Response Structure:**
  1. Evidence ID, Git commit revision, file path, line bounds.
  2. Staleness status (`FRESH`, `LINE_SHIFT`, `CONTENT_CHANGED`, etc.).
  3. Bounded code snippet verified against file content on disk.

### Q5: PR Architecture Guardian / "PR mimari kontrolden geçer mi?"
- **Action:** Call `repodna_pr_guardian(target=".", base_ref="main", head_ref="HEAD")`.
- **Response Structure:**
  1. Verdict (`PASS`, `WARNING`, `FAIL`).
  2. New circular dependencies introduced.
  3. Architecture contract rule violations.
  4. Health score delta and coupling drift.

---

## 4. CLI Fallback Instructions (When MCP is Unavailable)

If running in terminal without MCP server:

```bash
# Context building
repodna context --mode focused --query "auth token" --max-tokens 2000

# Symbol search & inspection
repodna symbols --name "validate" --kind function

# PR architecture guard
repodna guardian assess --base main --head HEAD

# Passport v2 export
repodna passport generate --version 2.0 --format markdown
```
