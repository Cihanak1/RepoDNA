"""Explainable, deterministic Rule-Based Architecture Health Engine."""

from __future__ import annotations

from repodna.schemas.models import (
    ArchitectureHealthReport,
    CategoryScore,
    CycleGroup,
    DependencyEdge,
    FileNode,
    GraphMetrics,
    LanguageSupportLevel,
    RuleFinding,
    SeverityLevel,
)


def evaluate_architecture_health(
    files: list[FileNode],
    edges: list[DependencyEdge],
    cycles: list[CycleGroup],
    metrics: GraphMetrics,
) -> ArchitectureHealthReport:
    """
    Evaluate deterministic architectural health rules.
    No LLM or opaque heuristics: every score deduction has an explicit mathematical formula,
    threshold, evidence list, and actionable remediation.
    """
    findings: list[RuleFinding] = []
    passed_rules: list[str] = []
    node_map = {f.id: f for f in files}

    category_meta = [
        ("cycles", "Acyclicity & Layering", 30.0),
        ("coupling", "Coupling & Stability", 30.0),
        ("complexity", "Module Size & Complexity", 15.0),
        ("hygiene", "Structural Hygiene", 15.0),
        ("security", "Secret & Config Safety", 10.0),
    ]

    if not files:
        return ArchitectureHealthReport(
            overall_score=None,
            grade="N/A",
            status="insufficient_data",
            methodology=(
                "Insufficient data: repository contains 0 analyzable files. "
                "RepoDNA reports N/A rather than a synthetic 100/100 score when no source modules are present."
            ),
            category_scores=[
                CategoryScore(
                    category=cat_key,
                    label=cat_label,
                    score=None,
                    weight=weight,
                    deductions=0.0,
                    findings_count=0,
                )
                for cat_key, cat_label, weight in category_meta
            ],
            findings=[],
            passed_rules=[],
            summary_metrics={
                "total_deductions": 0.0,
                "rules_evaluated": 0,
                "rules_passed": 0,
                "rules_triggered": 0,
            },
        )

    # --- RULE ARCH-001: Acyclic Dependencies Principle (ADP) ---
    if cycles:
        deduction = min(30.0, round(len(cycles) * 6.0 + metrics.nodes_in_cycles * 1.2, 1))
        severity = SeverityLevel.CRITICAL if len(cycles) >= 2 or any(c.length >= 3 for c in cycles) else SeverityLevel.WARNING
        affected = sorted({n for c in cycles for n in c.nodes})
        evidence = [f"{c.id} ({c.length} hops): {' -> '.join(c.nodes)}" for c in cycles[:10]]
        findings.append(
            RuleFinding(
                rule_id="ARCH-001",
                title="Circular Dependency Violations (ADP)",
                category="cycles",
                severity=severity,
                score_deduction=deduction,
                max_deduction=30.0,
                formula_explanation="deduction = min(30.0, 6.0 * cycle_count + 1.2 * nodes_in_cycles)",
                threshold_description="0 circular dependency cycles allowed (Acyclic Dependencies Principle).",
                affected_files=affected,
                evidence=evidence,
                remediation="Extract shared contracts/interfaces into a lower-level module or apply Dependency Inversion to break mutual imports.",
            )
        )
    else:
        passed_rules.append("ARCH-001: Zero Circular Dependencies (Acyclic Dependencies Principle satisfied)")

    # --- RULE ARCH-002: High Efferent Coupling (Fan-Out Overload) ---
    high_fanout_files = [f for f in files if f.fan_out >= 8]
    if high_fanout_files:
        high_fanout_files.sort(key=lambda x: x.fan_out, reverse=True)
        deduction = min(15.0, round(sum((f.fan_out - 7) * 1.5 for f in high_fanout_files), 1))
        findings.append(
            RuleFinding(
                rule_id="ARCH-002",
                title="Excessive Efferent Coupling (High Fan-Out)",
                category="coupling",
                severity=SeverityLevel.WARNING if deduction < 10.0 else SeverityLevel.CRITICAL,
                score_deduction=deduction,
                max_deduction=15.0,
                formula_explanation="deduction = min(15.0, sum((fan_out - 7) * 1.5 for file with fan_out >= 8))",
                threshold_description="Internal fan-out per module should remain < 8 direct internal dependencies.",
                affected_files=[f.id for f in high_fanout_files],
                evidence=[f"{f.id}: fan_out={f.fan_out}, instability={f.instability:.2f}" for f in high_fanout_files[:10]],
                remediation="Decompose orchestrator modules into focused domain services or facade sub-packages to reduce direct fan-out.",
            )
        )
    else:
        passed_rules.append("ARCH-002: Bounded Efferent Coupling (All modules have internal fan-out < 8)")

    # --- RULE ARCH-003: Stable Dependencies Principle (SDP) Violations ---
    # A stable module (I <= 0.30, fan_in >= 2) should not depend on a much more unstable module (I >= 0.70, delta >= 0.45)
    sdp_violations: list[tuple[str, str, float, float]] = []
    for e in edges:
        src = node_map.get(e.source)
        dst = node_map.get(e.target)
        if not src or not dst:
            continue
        if src.fan_in >= 2 and src.instability <= 0.35 and dst.instability >= 0.70 and (dst.instability - src.instability) >= 0.40:
            sdp_violations.append((src.id, dst.id, src.instability, dst.instability))

    if sdp_violations:
        deduction = min(15.0, round(len(sdp_violations) * 3.0, 1))
        affected = sorted({u for u, _, _, _ in sdp_violations} | {v for _, v, _, _ in sdp_violations})
        evidence = [
            f"{u} (I={iu:.2f}, stable) imports {v} (I={iv:.2f}, unstable)"
            for u, v, iu, iv in sdp_violations[:10]
        ]
        findings.append(
            RuleFinding(
                rule_id="ARCH-003",
                title="Stable Dependencies Principle (SDP) Inversion",
                category="coupling",
                severity=SeverityLevel.WARNING,
                score_deduction=deduction,
                max_deduction=15.0,
                formula_explanation="deduction = min(15.0, 3.0 * sdp_violation_edges) where I_target - I_source >= 0.40",
                threshold_description="Modules with high incoming dependency stability (I <= 0.35) must not depend on volatile modules (I >= 0.70).",
                affected_files=affected,
                evidence=evidence,
                remediation="Invert the dependency using an abstract interface or move shared types into the stable core layer.",
            )
        )
    else:
        passed_rules.append("ARCH-003: Stable Dependencies Principle (Dependencies flow in the direction of stability)")

    # --- RULE ARCH-004: God Module / Oversized Source File Complexity ---
    code_files = [f for f in files if f.support_level != LanguageSupportLevel.UNSUPPORTED]
    god_files = [f for f in code_files if f.lines_code > 450]
    if god_files:
        god_files.sort(key=lambda x: x.lines_code, reverse=True)
        deduction = min(15.0, round(sum((f.lines_code - 450) / 100.0 * 2.0 for f in god_files), 1))
        deduction = max(2.0, deduction)
        findings.append(
            RuleFinding(
                rule_id="ARCH-004",
                title="Oversized Modules / God File Risk",
                category="complexity",
                severity=SeverityLevel.CRITICAL if any(f.lines_code > 900 for f in god_files) else SeverityLevel.WARNING,
                score_deduction=deduction,
                max_deduction=15.0,
                formula_explanation="deduction = min(15.0, max(2.0, sum((lines_code - 450) / 100 * 2.0)))",
                threshold_description="Source code modules should not exceed 450 non-comment lines of code (LOC).",
                affected_files=[f.id for f in god_files],
                evidence=[f"{f.id}: {f.lines_code} LOC ({len(f.symbols)} top-level symbols)" for f in god_files[:10]],
                remediation="Split large modules along cohesive responsibility boundaries into smaller, testable modules.",
            )
        )
    else:
        passed_rules.append("ARCH-004: Module Size Discipline (All code modules <= 450 LOC)")

    # --- RULE ARCH-005: Disconnected / Orphaned Code Modules ---
    orphans = [f for f in code_files if f.is_orphan]
    if orphans and len(code_files) > 2:
        orphan_ratio = len(orphans) / len(code_files)
        if orphan_ratio > 0.25 or len(orphans) >= 3:
            deduction = min(10.0, round(len(orphans) * 1.5, 1))
            findings.append(
                RuleFinding(
                    rule_id="ARCH-005",
                    title="Isolated / Potentially Unreferenced Modules",
                    category="hygiene",
                    severity=SeverityLevel.INFO if orphan_ratio <= 0.4 else SeverityLevel.WARNING,
                    score_deduction=deduction,
                    max_deduction=10.0,
                    formula_explanation="deduction = min(10.0, 1.5 * orphan_files_count) when >= 3 orphans or > 25% of code files",
                    threshold_description="Non-entrypoint source files should participate in the internal module graph.",
                    affected_files=[f.id for f in orphans[:20]],
                    evidence=[f"{f.id}: fan_in=0, fan_out=0 ({f.lines_code} LOC)" for f in orphans[:10]],
                    remediation="Verify whether isolated modules are dead code, dynamically loaded plugins, or standalone scripts, and remove unused files.",
                )
            )
        else:
            passed_rules.append("ARCH-005: Low Orphan Module Ratio (<= 25% isolated modules)")
    else:
        passed_rules.append("ARCH-005: High Module Graph Connectivity (Minimal isolated code files)")

    # --- RULE ARCH-006: Deep Directory Nesting ---
    deep_files = [f for f in files if f.id.count("/") >= 6]
    if deep_files:
        deduction = min(5.0, round(len(deep_files) * 0.5, 1))
        deduction = max(1.0, deduction)
        findings.append(
            RuleFinding(
                rule_id="ARCH-006",
                title="Excessive Directory Hierarchy Depth",
                category="hygiene",
                severity=SeverityLevel.INFO,
                score_deduction=deduction,
                max_deduction=5.0,
                formula_explanation="deduction = min(5.0, max(1.0, 0.5 * files_with_depth_ge_6))",
                threshold_description="Directory depth should remain < 6 levels from repository root.",
                affected_files=[f.id for f in deep_files[:15]],
                evidence=[f"{f.id} (depth={f.id.count('/')})" for f in deep_files[:10]],
                remediation="Flatten deeply nested package directories to improve discoverability and shorten import paths.",
            )
        )
    else:
        passed_rules.append("ARCH-006: Clean Directory Hierarchy (All paths < 6 directory levels deep)")

    # --- RULE SEC-001: Secret & Credential Hygiene ---
    secret_files = [f for f in files if f.secret_warnings]
    if secret_files:
        deduction = min(20.0, round(len(secret_files) * 7.5, 1))
        sec_evidence: list[str] = []
        for sf in secret_files[:10]:
            for w in sf.secret_warnings[:3]:
                sec_evidence.append(f"{sf.id}: {w}")
        findings.append(
            RuleFinding(
                rule_id="SEC-001",
                title="Potential Secret or Sensitive File Exposure",
                category="security",
                severity=SeverityLevel.CRITICAL,
                score_deduction=deduction,
                max_deduction=20.0,
                formula_explanation="deduction = min(20.0, 7.5 * files_with_secret_warnings)",
                threshold_description="0 committed credential files (.env, private keys) or hardcoded API token patterns.",
                affected_files=[f.id for f in secret_files],
                evidence=sec_evidence,
                remediation="Remove sensitive files from version control, rotate any exposed credentials immediately, and add patterns to .gitignore.",
            )
        )
    else:
        passed_rules.append("SEC-001: Credential & Secret Hygiene (No sensitive files or token patterns detected)")

    # Calculate category scores and overall health score
    category_scores: list[CategoryScore] = []
    total_deduction = 0.0

    for cat_key, cat_label, weight in category_meta:
        cat_findings = [fn for fn in findings if fn.category == cat_key]
        cat_ded = sum(fn.score_deduction for fn in cat_findings)
        total_deduction += cat_ded
        # Normalize category score to 0..100
        cat_pct = max(0.0, round(100.0 * (1.0 - min(weight, cat_ded) / weight), 1))
        category_scores.append(
            CategoryScore(
                category=cat_key,
                label=cat_label,
                score=cat_pct,
                weight=weight,
                deductions=round(cat_ded, 1),
                findings_count=len(cat_findings),
            )
        )

    overall_score = max(0.0, min(100.0, round(100.0 - total_deduction, 1)))
    if overall_score >= 90.0:
        grade = "A"
    elif overall_score >= 80.0:
        grade = "B"
    elif overall_score >= 65.0:
        grade = "C"
    elif overall_score >= 50.0:
        grade = "D"
    else:
        grade = "F"

    return ArchitectureHealthReport(
        overall_score=overall_score,
        grade=grade,
        status="evaluated",
        methodology=(
            "Deterministic, rule-based engineering rubric starting at 100.0 points. "
            "Deductions are computed strictly from static AST dependency topology (Tarjan SCC cycles, "
            "Robert C. Martin Instability & Fan-Out metrics), LOC complexity thresholds, and secret hygiene checks. "
            "No generative AI or non-deterministic scoring is used."
        ),
        category_scores=category_scores,
        findings=findings,
        passed_rules=passed_rules,
        summary_metrics={
            "total_deductions": round(total_deduction, 1),
            "rules_evaluated": len(findings) + len(passed_rules),
            "rules_passed": len(passed_rules),
            "rules_triggered": len(findings),
        },
    )
