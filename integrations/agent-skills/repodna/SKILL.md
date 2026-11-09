---
name: repodna
description: "Evidence-based repository intelligence platform for architecture discovery, dependency graph tracing, change impact blast radius, circular dependency detection, PR architecture guarding, and architecture contract enforcement."
---

# RepoDNA — AI-Native Repository Intelligence (v0.4.0)

RepoDNA provides deterministic, read-only architectural intelligence for AI coding agents. It extracts Tree-sitter AST dependency graphs, calculates Robert C. Martin instability metrics, detects circular dependency cycles (Tarjan SCC), verifies architectural health rules, evaluates declarative Architecture Contracts (`.repodna/architecture.yml`), guards Pull Requests (`repodna_pr_guardian`), and serves portable Repository Passports (`.repodna/passport.json`).

---

## 1. Fast Routing & Tool Invocation Matrix

RepoDNA provides 12 read-only tools via MCP (or CLI fallback). Call only the specific tool required for your task:

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
| `repodna_get_passport` | **Repository Passport** structural identity & vitals | `target="."`, `max_modules=150`, `format="json"` | Complete portable manifest (hubs, coverage, contracts) |
| `repodna_get_contract` | Read declared architecture rules & layer boundaries | `target="."`, `format="yaml"` | Active rules from `.repodna/architecture.yml` |
| `repodna_check_contract` | Verify compliance against architecture contract | `target="."`, `mode="enforce"` (opt) | Violations, baseline items, unknowns, compliant status |
| `repodna_pr_guardian` | **PR Architecture Guardian** (Pass/Fail gate) | `target="."`, `base_ref="main"`, `head_ref="HEAD"` | New cycles, new violations, baseline diff, risk verdict |

---

## 2. Core Questions & Exact Agent Guides (TR / EN)

### Q1: PR Architectural Safety / "Bu PR mimari açıdan güvenli mi?"
- **Action:** Call `repodna_pr_guardian(target=".", base_ref="main", head_ref="HEAD")`.
- **Response Structure:**
  1. **Verdict:** `PASS`, `WARNING`, `FAIL`, or `INCONCLUSIVE`.
  2. **Risk Assessment:** Score (0-100) and risk factors (e.g. new cycles, coupling surge on hubs).
  3. **New vs Baseline Violations:** State clearly that baseline violations are not counted against this PR.
  4. **Circular Dependencies:** Confirm whether `new_cycles` is 0 or lists offending paths.

### Q2: Circular Dependency Regression / "Değişiklik yeni bir circular dependency oluşturuyor mu?"
- **Action:** Check `new_cycles` in `repodna_pr_guardian` or `repodna_architecture_diff`.
- **Response Structure:**
  1. If `new_cycles` is non-empty, list each exact loop (e.g., `A -> B -> C -> A`).
  2. Explain the root import edge causing the cycle.
  3. Provide concrete remediation (extract common interface or apply Dependency Inversion Principle).

### Q3: Architectural Contract Violations / "Projenin mimari kurallarına aykırı dosyalar hangileri?"
- **Action:** Call `repodna_check_contract(target=".")`.
- **Response Structure:**
  1. List triggered violations with `rule_id`, source file, target file, and line number.
  2. Distinguish newly introduced violations from existing baseline items.
  3. Disclose any `unknowns` caused by unresolvable imports or unsupported languages.

### Q4: Architecture Contract Discovery / "Bu repository'nin Architecture Contract dosyası var mı?"
- **Action:** Call `repodna_get_contract(target=".")`.
- **Response Structure:**
  1. If contract exists, summarize the policy mode (`advisory` vs `enforce`), rules count, and key boundaries.
  2. If missing, recommend running `repodna contract init` to establish `.repodna/architecture.yml`.

### Q5: Repository Passport Inspection / "Bu projenin Repository Passport bilgisi nedir?"
- **Action:** Call `repodna_get_passport(target=".", format="json")`.
- **Freshness Invariant:** Inspect `git_revision` in the passport against active `HEAD`. If different, note that manifest is stale or query with `force=True`.
- **Response Structure:**
  1. Summary of primary languages, AST coverage percentage, and health grade.
  2. Top architectural hubs (highest fan-in modules).
  3. Active architecture boundaries and contract status.

### Q6: Pre-Edit Boundary Safeguards / "Bu modülü değiştirmeden önce hangi mimari sınırları korumalıyım?"
- **Action:** Call `repodna_get_contract(target=".")` to find rules matching this file, and `repodna_change_impact(target=".", changed_files=[file_path])`.
- **Response Structure:**
  1. List forbidden import targets governed by `.repodna/architecture.yml`.
  2. List direct and transitive dependents importing this module.
  3. Instability rating ($I = Ce / (Ca + Ce)$) to caution against making an abstract module unstable.

---

## 3. CLI Fallback Instructions (When MCP is Unavailable)

### A. Architecture Contract CLI
```bash
# Initialize starter contract
repodna contract init

# Validate YAML syntax and schema
repodna contract validate

# Check repository against contract rules
repodna contract check . --mode enforce --format json
```

### B. PR Architecture Guardian CLI
```bash
# Evaluate PR between base and head
repodna guardian check . --base origin/main --head HEAD --format markdown --output guardian-report.md
```

### C. Repository Passport CLI
```bash
# Generate passport manifest
repodna passport generate . --max-modules 200

# Validate passport schema
repodna passport validate .repodna/passport.json
```

---

## 4. Unsupported Languages & Honesty Principle
- **Supported Full AST Grammars:** Python, TypeScript, JavaScript, Go, Rust.
- **Partially Supported / Unsupported Languages (e.g. C#, PHP, Ruby):**
  - RepoDNA tracks LOC and file counts, but does NOT guess unparsed imports.
  - If AST coverage is below 50%, dependency-graph rules report `insufficient_dependency_coverage`.
  - Guardian reports `INCONCLUSIVE` if AST coverage collapsed.
  - **Never** give a false positive safety clearance when AST coverage is insufficient.
