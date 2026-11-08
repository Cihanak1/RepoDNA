---
name: repodna
description: "Evidence-based repository intelligence platform for architecture discovery, dependency graph tracing, change impact blast radius, circular dependency detection, and git architecture diffing."
---

# RepoDNA — AI-Native Repository Intelligence

RepoDNA provides deterministic, read-only architectural intelligence for AI coding agents. It extracts Tree-sitter AST dependency graphs, calculates Robert C. Martin instability metrics, detects circular dependency cycles (Tarjan SCC), verifies architectural health rules, and computes commit-level architecture diffs.

---

## 1. Fast Routing & Tool Invocation Matrix

RepoDNA provides 8 read-only tools via MCP (or CLI fallback). Call only the specific tool required for your task:

| Tool Name | When to Use | Key Arguments | Return Value & Purpose |
| :--- | :--- | :--- | :--- |
| `repodna_repository_overview` | First repo discovery, stack, LOC, hubs, cycles | `target="."`, `format="text"` | Summary text, language distribution, top hubs, cycle count |
| `repodna_architecture_map` | High-level package/module clustering & layers | `target="."`, `level="clusters"`, `limit=30` | Multi-module architectural hierarchy and package clusters |
| `repodna_find_modules` | Feature location, symbol/module discovery | `target="."`, `query="..."`, `limit=10` | Best matching modules with AST symbol hits & coupling |
| `repodna_module_dependencies` | Inspect incoming & outgoing imports of a file | `target="."`, `file_path="..."`, `depth=1` | Direct & transitive dependencies, fan-in, fan-out |
| `repodna_module_findings` | Audit violations (`ARCH-001` .. `ARCH-006`, `SEC-001`) | `target="."`, `rule_id="ARCH-001"` (opt) | Actionable architectural findings and remediations |
| `repodna_architecture_diff` | Compare architecture between two git revisions | `target="."`, `base_ref="HEAD~1"`, `head_ref="HEAD"` | Cycle regressions, structural deltas, health score delta |
| `repodna_change_impact` | **Pre-edit safety check** (Change Guardian) | `target="."`, `changed_files=["..."]` | Blast radius, affected dependents, severity level |
| `repodna_analysis_coverage` | Verify AST coverage & unsupported languages | `target="."` | Language coverage ratio, unverified rules, honest N/A |

---

## 2. Five Real User Questions & Exact Guides (TR / EN)

### Q1: Codebase Purpose & Architecture / "Bu repository ne işe yarıyor ve mimarisi nasıl?"
- **Action:** Call `repodna_repository_overview(target=".")`. If package structure is complex, call `repodna_architecture_map(target=".", level="clusters")`.
- **Response Structure:** 
  1. Primary programming languages and AST coverage percentage.
  2. Identified architectural hubs (highest Fan-In modules).
  3. Identified cycles (Tarjan SCC count).
  4. Core entrypoints and module layering.

### Q2: Locating Feature Files / "Kullanıcı girişiyle ilgili dosyaları bul"
- **Action:** Call `repodna_find_modules(target=".", query="auth login session user credentials", limit=5)`.
- **Response Structure:**
  1. Highlight top matching file paths ranked by AST symbol relevance.
  2. Mention coupling metrics (Fan-In / Fan-Out) so the user knows which file is core vs peripheral.
  3. Do NOT sweep the directory tree with raw grep when RepoDNA returns direct matches.

### Q3: Blast Radius Assessment / "X dosyasını değiştirirsem nereler etkilenir?"
- **Action:** Call `repodna_change_impact(target=".", changed_files=["path/to/X"])`.
- **Response Structure:**
  1. **Severity:** `CRITICAL` (hub module or cycle participant), `WARNING` (direct consumers affected), or `INFO` (isolated leaf node).
  2. **Direct Dependents:** List internal modules importing `X`.
  3. **Transitive Blast Radius:** Downstream modules indirectly impacted.
  4. **Recommended Safeguard:** Specific test files to execute before committing changes.

### Q4: Commit & PR Risk Check / "Son iki commit arasında mimari bir risk oluştu mu?"
- **Action:** Call `repodna_architecture_diff(target=".", base_ref="HEAD~1", head_ref="HEAD")`.
- **Response Structure:**
  1. **Verdict:** `IMPROVED`, `NEUTRAL`, or `REGRESSED`.
  2. **Cycle Delta:** Check `cycle_changes.new_cycles`. Any new circular dependency is a critical blocker.
  3. **Health Score Delta:** Note whether health points increased or decreased.
  4. **Structural Changes:** Added/removed modules and Git-verified renames.

### Q5: Circular Dependency Audit / "Döngüsel bağımlılık var mı?"
- **Action:** Call `repodna_module_findings(target=".", rule_id="ARCH-001")`.
- **Response Structure:**
  1. Return cycle count and exact cycle chains (e.g., `A -> B -> C -> A`).
  2. Provide deterministic remediation (e.g., extract shared interface or apply Dependency Inversion Principle).
  3. If 0 cycles, confirm mathematical Tarjan SCC proof.

---

## 3. CLI Fallback Instructions (When MCP is Unavailable)
If the MCP client cannot establish a connection, stdio transport fails, or you are running in a CLI-only environment:

### A. Targeted Agent Context (`repodna context`)
Supports three calibrated density modes:
- `--mode compact`: Executive high-level summary, key architectural hubs, and cycle count (lowest token footprint).
- `--mode focused`: Keyword/symbol-targeted context focusing on matching files and their immediate dependencies (requires `--query`).
- `--mode deep`: Full architectural breakdown including module coupling metrics, dependency edges, and complete findings.

```bash
# High-level architecture overview
repodna context --mode compact

# Feature-targeted context
repodna context --mode focused --query "auth security"

# Deep comprehensive context with token budget
repodna context --mode deep --max-tokens 4000
```

### B. Architecture Diff (`repodna diff`)
```bash
# Compare last two commits
repodna diff HEAD~1 HEAD

# Compare working tree against HEAD
repodna diff HEAD working_tree
```

### C. Terminal Analysis (`repodna analyze`)
```bash
repodna analyze . --format table
repodna analyze . --format json
```

### D. Diagnostic & Repair (`repodna doctor`, `repodna setup`)
```bash
# Diagnose environment, grammars, and agent integrations
repodna doctor

# Repair or refresh missing agent configs idempotently
repodna setup --repair
```

---

## 4. Cache Invalidation & Stale Snapshot Warning
- **Disk Synchronization:** RepoDNA analyses are indexed against repository state.
- **When to Refresh:** If you edit, rename, add, or delete files on disk during a session, subsequent queries with `target="."` will automatically re-index modified files.
- **Git Commit Transitions:** After running `git checkout`, `git commit`, or `git rebase`, invoke `repodna_repository_overview` to refresh the cached architecture graph against the new HEAD.

---

## 5. Unsupported Languages & N/A Honesty Principle
- **Supported Full AST Grammars:** Python, TypeScript, JavaScript, Go, Rust.
- **Partially Supported / Unsupported Languages (e.g. C#, PHP, Ruby):**
  - RepoDNA tracks file count and LOC, but does not hallucinate unresolved import graphs.
  - Architecture health score will report: `N/A (Insufficient dependency coverage)`.
  - Rules depending on call graphs (`ARCH-001` through `ARCH-004`) are cataloged under `unverified_rules`.
  - **Never** claim 100/100 health or 0 cycles for codebases with unsupported languages. State clearly: *"Sağlık puanı N/A çünkü bu dilde AST bağımlılık çözümleme desteği mevcut değildir."*

---

## 6. Detailed References
For in-depth mathematical formulations and rules catalogs:
- [Architecture Rules & Coupling Reference](references/architecture-rules.md)
- [Practical Agent Workflows](examples/workflows.md)
