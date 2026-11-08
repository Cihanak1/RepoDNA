# Practical RepoDNA Agent Workflows & Canonical Question Guide

This document provides concrete interaction examples for the 5 most common developer inquiries.

---

## Guide 1: Codebase Purpose & Architecture
**Turkish Prompt:** "Bu repository ne işe yarıyor ve mimarisi nasıl?"  
**English Prompt:** "What does this repository do and what is its architecture?"

```markdown
Step 1: Agent calls `repodna_repository_overview(target=".")`.
Step 2: Agent calls `repodna_architecture_map(target=".", level="clusters")`.

Agent Output:
- Primary Stack: 54% Python, 46% TypeScript (100% Tree-sitter AST coverage).
- Architectural Hubs: `backend/repodna/core/analyzer.py` (Fan-In: 18), `backend/repodna/api/app.py` (Fan-In: 12).
- Health & Cycles: 95.8/100, 0 circular dependencies (Tarjan SCC verified).
- Architecture Style: Multi-layer workstation — FastAPI REST & MCP backend with React Flow visualization.
```

---

## Guide 2: Locating Feature & Subsystem Files
**Turkish Prompt:** "Kullanıcı girişi ve kimlik doğrulama ile ilgili dosyaları bul"  
**English Prompt:** "Find modules related to authentication, login, and security"

```markdown
Step 1: Agent calls `repodna_find_modules(target=".", query="auth login security validation", limit=5)`.

Agent Output:
- Matched Files:
  1. `backend/repodna/security/validators.py` (AST Symbols: `validate_git_revision`, `is_safe_subpath`, Fan-In: 14)
  2. `backend/repodna/security/sanitizer.py` (AST Symbols: `sanitize_text`, Fan-In: 6)
- Recommendation: Review `validators.py` for input boundary validation rules.
```

---

## Guide 3: Change Guardian & Blast Radius Assessment
**Turkish Prompt:** "analyzer.py dosyasını değiştirirsem nereler etkilenir?"  
**English Prompt:** "If I change analyzer.py, what is the blast radius and affected files?"

```markdown
Step 1: Agent calls `repodna_change_impact(target=".", changed_files=["backend/repodna/core/analyzer.py"])`.

Agent Output:
- Impact Severity: CRITICAL (Architectural Hub, Fan-In: 18).
- Direct Dependents:
  - `backend/repodna/api/app.py`
  - `backend/repodna/cli/main.py`
  - `backend/repodna/diff/snapshot.py`
- Transitive Impact: 34 downstream modules indirectly impacted.
- Guardrail: Run `pytest backend/tests` immediately after any signature refactoring.
```

---

## Guide 4: Commit & PR Risk Check (Architecture Diff)
**Turkish Prompt:** "Son iki commit arasında mimari bir risk oluştu mu?"  
**English Prompt:** "Was any architectural risk introduced between the last two commits?"

```markdown
Step 1: Agent calls `repodna_architecture_diff(target=".", base_ref="HEAD~1", head_ref="HEAD")`.

Agent Output:
- Verdict: NEUTRAL / IMPROVED.
- Structural Delta: +1 module added, 0 removed, 0 renamed.
- Cycle Changes: 0 new cycles introduced.
- Health Score Delta: 95.8 -> 95.8 (0.0 pts delta).
```

---

## Guide 5: Circular Dependency Cycle Audit
**Turkish Prompt:** "Projede döngüsel bağımlılık var mı?"  
**English Prompt:** "Are there any circular dependencies in the codebase?"

```markdown
Step 1: Agent calls `repodna_module_findings(target=".", rule_id="ARCH-001")`.

Agent Output:
- Active Violations: 0 circular dependencies detected.
- Verification Method: Tarjan Strongly Connected Components (SCC) over Tree-sitter AST import graph.
```
