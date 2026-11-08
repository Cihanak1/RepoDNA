# Practical RepoDNA Agent Workflows

## Workflow 1: Instant Codebase Onboarding
```markdown
User: "I just cloned this codebase. What is the high-level architecture and where are the main hubs?"

Agent Action:
1. Calls `repodna_repository_overview(target=".")`.
2. Calls `repodna_architecture_map(target=".", level="clusters")`.

Agent Output:
1. Concise Conclusion: RepoDNA is a 3-layer architecture with a Python/FastAPI backend and a React/TypeScript frontend.
2. Relevant Files: `backend/repodna/core/analyzer.py`, `backend/repodna/graph/engine.py`.
3. Why They Are Relevant: Primary architectural hubs with Fan-In > 15.
4. Verified Dependencies: `analyzer.py` coordinates parsers, resolver, and rules engines.
5. Change Impact: Modifying `analyzer.py` impacts the CLI and FastAPI endpoints directly.
6. Unknowns & Coverage: 98.8% AST coverage across Python and TypeScript.
7. Recommended Next Action: Begin exploration from `backend/repodna/core/analyzer.py`.
```

## Workflow 2: Change Guardian Pre-Edit Verification
```markdown
User: "Refactor backend/repodna/parsers/resolver.py to support custom path aliases."

Agent Action:
1. Calls `repodna_change_impact(target=".", changed_files=["backend/repodna/parsers/resolver.py"])`.
2. Inspects blast radius: Fan-In=4, Direct Dependents: `analyzer.py`, `test_parsers.py`.
3. Performs the requested code edit.
4. Calls `repodna_architecture_diff(target=".", base_ref="HEAD", head_ref="working_tree")`.
5. Verifies that `cycle_changes.new_cycles` is empty and health score did not degrade.
```

## Workflow 3: Multi-Revision PR Architectural Audit
```markdown
User: "Check PR branch against main for architectural regressions."

Agent Action:
1. Calls `repodna_architecture_diff(target=".", base_ref="main", head_ref="HEAD")`.
2. Identifies:
   - +3 added modules
   - 0 new cyclic SCCs
   - Health score: 94.2 -> 95.1 (+0.9 pts)
   - Verdict: IMPROVED
```
