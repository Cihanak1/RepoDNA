"""Standalone CLI scanner, diff engine, context builder, and agent installer for RepoDNA."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from repodna.cli.installer import AgentInstaller, run_doctor
from repodna.context.builder import AgentContextBuilder
from repodna.contract import (
    ArchitectureContract,
    ContractEvaluator,
    ContractMode,
    find_contract_file,
    init_starter_contract,
    load_contract_file,
)
from repodna.core.analyzer import run_repository_analysis
from repodna.diff.engine import ArchitectureDiffEngine
from repodna.diff.snapshot import SnapshotManager
from repodna.guardian import PRArchitectureGuardian
from repodna.mcp.server import RepoDNAMCPServer
from repodna.passport import (
    export_passport_to_json,
    export_passport_to_markdown,
    generate_repository_passport,
    validate_passport_file,
)
from repodna.reports.exporter import export_analysis_to_html, export_analysis_to_json
from repodna.schemas.models import AnalysisResult, ScanLimits, ScanRequest, SourceType
from repodna.security.validators import SecurityValidationError


def _detect_source_type(target: str) -> SourceType:
    cleaned = target.strip()
    if cleaned.lower() == "demo":
        return SourceType.DEMO
    if cleaned.startswith(("http://", "https://", "git://", "ssh://", "file://")):
        return SourceType.GITHUB
    return SourceType.LOCAL


def _format_summary_table(result: AnalysisResult) -> str:
    hr = result.health_report
    gm = result.graph_metrics
    tr = result.transparency

    if hr.overall_score is not None:
        score_str = f"{hr.overall_score:.1f} / 100 (Grade {hr.grade}, Confidence: {hr.confidence.upper()})"
    elif hr.status == "insufficient_dependency_coverage":
        score_str = f"Not evaluated — Insufficient dependency coverage (Grade {hr.grade}, Confidence: {hr.confidence.upper()})"
    else:
        score_str = f"N/A — Insufficient Data ({hr.grade})"

    lines = [
        "=" * 76,
        f"RepoDNA Architectural Analysis — {result.repo_name}",
        "=" * 76,
        f"Target         : {result.target_display} ({result.source_type.value})",
        f"Duration       : {result.duration_ms} ms",
        f"Files Scanned  : {result.total_files:,} ({result.total_lines_code:,} LOC / {result.total_size_bytes:,} bytes)",
        f"Health Score   : {score_str}",
        f"AST Coverage   : {tr.ast_loc_coverage_pct:.1f}% of LOC ({tr.ast_file_coverage_pct:.1f}% of files) | Confidence: {hr.confidence.upper()}",
        f"Graph Metrics  : {gm.total_nodes} nodes, {gm.total_edges} internal edges, {gm.scc_count} cyclic SCCs, {gm.cycle_count} cycles, avg instability {gm.average_instability:.2f}",
        f"Supported AST  : {', '.join(tr.supported_languages_detected) or 'None'}",
        f"Partial Static : {', '.join(tr.partial_static_languages_detected) or 'None'} ({tr.partial_static_files_count} files / {tr.partial_static_loc_coverage_pct:.1f}% LOC — static using/include scan only, no AST graph)",
        f"Unsupported    : {', '.join(tr.unsupported_languages_detected) or 'None'} ({tr.unsupported_files_count} files / {tr.unsupported_loc_coverage_pct:.1f}% LOC)",
        "-" * 76,
        "Language Distribution:",
    ]
    for lg in result.languages:
        lines.append(
            f"  - {lg.language:<18} | {lg.support_level.value:<14} | {lg.file_count:>4} files | {lg.lines_code:>7,} LOC ({lg.percentage_of_code:>5.1f}%)"
        )

    lines.append("-" * 76)
    if result.cycles:
        lines.append(f"Circular Dependencies ({len(result.cycles)}):")
        for c in result.cycles[:10]:
            lines.append(f"  [{c.id}] ({c.length} hops): {' -> '.join(c.nodes)}")
    else:
        lines.append(f"Circular Dependencies: {hr.cycle_analysis_summary}")

    lines.append("-" * 76)
    if hr.findings:
        lines.append(f"Architecture Health Findings ({len(hr.findings)}):")
        for fn in hr.findings:
            lines.append(
                f"  [{fn.rule_id}] {fn.title} ({fn.severity.value.upper()}, -{fn.score_deduction:.1f} pts)"
            )
            lines.append(f"      Remediation: {fn.remediation}")
    elif hr.status == "insufficient_dependency_coverage":
        lines.append(
            "Architecture Health Findings: 0 triggered in evaluated rules (Dependency-graph rules not evaluated)"
        )
    else:
        lines.append("Architecture Health Findings: 0 (All rules passed)")

    if hr.unverified_rules:
        lines.append(f"Unverified / Not Evaluated Rules ({len(hr.unverified_rules)}):")
        for ur in hr.unverified_rules:
            lines.append(f"  - {ur}")

    lines.append("=" * 76)
    return "\n".join(lines)


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="repodna",
        description="RepoDNA — AI-Native Repository Intelligence Platform CLI",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # 1. analyze
    analyze_p = sub.add_parser("analyze", help="Analyze a local directory, public HTTPS GitHub URL, or 'demo'.")
    analyze_p.add_argument("target", help="Local directory path, https://github.com/<owner>/<repo>, or 'demo'.")
    analyze_p.add_argument(
        "--format",
        choices=["table", "json", "html"],
        default="table",
        help="Output report format (default: table).",
    )
    analyze_p.add_argument(
        "--output",
        "-o",
        type=str,
        default=None,
        help="Optional file path to write the report output.",
    )
    analyze_p.add_argument("--branch", type=str, default=None, help="Optional GitHub branch or tag name.")
    analyze_p.add_argument("--max-files", type=int, default=2500, help="Maximum number of files to scan.")
    analyze_p.add_argument(
        "--max-file-size",
        type=int,
        default=1_048_576,
        help="Maximum single file size in bytes (default: 1048576).",
    )
    analyze_p.add_argument("--timeout", type=float, default=60.0, help="Scan timeout in seconds (default: 60).")

    # 2. diff
    diff_p = sub.add_parser("diff", help="Compare architecture between two Git revisions or working tree.")
    diff_p.add_argument("base_ref", help="Base Git revision (e.g. HEAD~1, main, commit SHA).")
    diff_p.add_argument(
        "head_ref",
        nargs="?",
        default="HEAD",
        help="Head Git revision or 'working_tree' (default: HEAD).",
    )
    diff_p.add_argument("--target", default=".", help="Local Git repository path (default: .).")
    diff_p.add_argument(
        "--format",
        choices=["table", "json"],
        default="table",
        help="Output diff format (default: table).",
    )
    diff_p.add_argument("--output", "-o", type=str, default=None, help="Optional file path to write diff.")

    # 3. context
    ctx_p = sub.add_parser("context", help="Generate token-budgeted context for AI coding agents.")
    ctx_p.add_argument("--target", default=".", help="Local directory path or 'demo' (default: .).")
    ctx_p.add_argument(
        "--mode",
        choices=["compact", "focused", "deep"],
        default="compact",
        help="Context density mode (default: compact).",
    )
    ctx_p.add_argument("--query", type=str, default=None, help="Search query for focused context mode.")
    ctx_p.add_argument(
        "--format",
        choices=["markdown", "json"],
        default="markdown",
        help="Context format (default: markdown).",
    )
    ctx_p.add_argument("--max-tokens", type=int, default=None, help="Approximate token budget cap.")
    ctx_p.add_argument("--output", "-o", type=str, default=None, help="Optional file path to write context.")

    # 4. mcp
    mcp_p = sub.add_parser("mcp", help="Run the local Model Context Protocol (MCP) stdio server.")
    mcp_p.add_argument(
        "--allowed-root",
        action="append",
        dest="allowed_roots",
        help="Authorized workspace root directory (can be specified multiple times).",
    )

    # 5. setup
    setup_p = sub.add_parser("setup", help="Configure RepoDNA Skill and MCP server in AI agents.")
    setup_p.add_argument(
        "--agent",
        choices=["codex", "claude", "antigravity", "auto"],
        default="auto",
        help="Target AI coding agent (default: auto).",
    )
    setup_p.add_argument(
        "--scope",
        choices=["project", "user"],
        default="project",
        help="Installation scope (default: project).",
    )
    setup_p.add_argument("--dry-run", action="store_true", help="Preview planned changes without writing.")
    setup_p.add_argument("--verify", action="store_true", help="Check current agent integration status.")
    setup_p.add_argument("--repair", action="store_true", help="Repair or refresh corrupted agent integrations.")
    setup_p.add_argument("--uninstall", action="store_true", help="Remove RepoDNA integration from agent.")

    # 6. doctor
    sub.add_parser("doctor", help="Run comprehensive diagnostic of environment, parsers, and agent tools.")

    # 7. contract
    contract_p = sub.add_parser("contract", help="Define and evaluate declarative Architecture Contracts.")
    c_sub = contract_p.add_subparsers(dest="contract_action", required=True)

    c_init = c_sub.add_parser("init", help="Create starter .repodna/architecture.yml in target repository.")
    c_init.add_argument("target", nargs="?", default=".", help="Target repository directory (default: .).")
    c_init.add_argument("--force", "-f", action="store_true", help="Overwrite existing architecture.yml.")

    c_val = c_sub.add_parser("validate", help="Validate architecture contract YAML syntax and schema.")
    c_val.add_argument("path", nargs="?", default=".", help="Path to architecture.yml or repository root (default: .).")

    c_check = c_sub.add_parser("check", help="Evaluate repository against architecture contract rules.")
    c_check.add_argument("target", nargs="?", default=".", help="Target repository directory (default: .).")
    c_check.add_argument("--contract", "-c", type=str, default=None, help="Explicit path to architecture.yml.")
    c_check.add_argument("--baseline", "-b", type=str, default=None, help="Path to baseline violations JSON.")
    c_check.add_argument("--mode", choices=["advisory", "enforce"], default=None, help="Evaluation mode override.")
    c_check.add_argument("--format", choices=["table", "json"], default="table", help="Output format (default: table).")
    c_check.add_argument("--output", "-o", type=str, default=None, help="Optional output file path.")

    # 8. guardian
    guardian_p = sub.add_parser("guardian", help="Continuous pull request architecture assessment.")
    g_sub = guardian_p.add_subparsers(dest="guardian_action", required=True)

    g_check = g_sub.add_parser("check", help="Evaluate architectural regression between Git revisions.")
    g_check.add_argument("target", nargs="?", default=".", help="Target Git repository directory (default: .).")
    g_check.add_argument("--base", type=str, required=True, help="Base Git revision (e.g. main, HEAD~1, commit SHA).")
    g_check.add_argument("--head", type=str, default="HEAD", help="Head Git revision (default: HEAD).")
    g_check.add_argument("--contract", "-c", type=str, default=None, help="Explicit path to architecture.yml.")
    g_check.add_argument("--baseline", "-b", type=str, default=None, help="Path to baseline violations JSON.")
    g_check.add_argument("--mode", choices=["advisory", "enforce"], default=None, help="Enforce or advisory mode.")
    g_check.add_argument("--format", choices=["table", "markdown", "json"], default="table", help="Output format.")
    g_check.add_argument("--output", "-o", type=str, default=None, help="Optional output file path.")

    # 9. passport
    pass_p = sub.add_parser("passport", help="Manage and verify portable Repository Passport manifests.")
    p_sub = pass_p.add_subparsers(dest="passport_action", required=True)

    p_gen = p_sub.add_parser("generate", help="Generate .repodna/passport.json for AI coding agents.")
    p_gen.add_argument("target", nargs="?", default=".", help="Target directory (default: .).")
    p_gen.add_argument("--output", "-o", type=str, default=None, help="Output file path (default: .repodna/passport.json or stdout).")
    p_gen.add_argument("--format", choices=["json", "markdown"], default="json", help="Output format (default: json).")
    p_gen.add_argument("--max-modules", type=int, default=150, help="Maximum modules in inventory (default: 150).")
    p_gen.add_argument("--contract", "-c", type=str, default=None, help="Optional path to architecture.yml.")

    p_val = p_sub.add_parser("validate", help="Validate passport.json schema and integrity.")
    p_val.add_argument("path", nargs="?", default=None, help="Path to passport.json (default: .repodna/passport.json).")

    return parser


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")

    parser = build_arg_parser()
    args = parser.parse_args(argv)

    if args.command == "analyze":
        source_type = _detect_source_type(args.target)
        try:
            limits = ScanLimits(
                max_files=args.max_files,
                max_file_size_bytes=args.max_file_size,
                timeout_seconds=args.timeout,
            )
            req = ScanRequest(
                source_type=source_type,
                target=args.target,
                branch=args.branch,
                limits=limits,
            )
            result = run_repository_analysis(req)
        except SecurityValidationError as exc:
            print(f"[SECURITY ERROR] ({exc.code}): {exc.message}", file=sys.stderr)
            return 2
        except Exception as exc:
            print(f"[ERROR] Analysis failed: {exc}", file=sys.stderr)
            return 1

        if args.format == "json":
            output_text = export_analysis_to_json(result, indent=2)
        elif args.format == "html":
            output_text = export_analysis_to_html(result)
        else:
            output_text = _format_summary_table(result)

        if args.output:
            out_path = Path(args.output)
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_text(output_text, encoding="utf-8")
            print(f"Report written to {out_path}")
        else:
            print(output_text)
        return 0

    if args.command == "diff":
        try:
            mgr = SnapshotManager(args.target)
            base_analysis, base_sha, base_is_wt = mgr.create_snapshot(args.base_ref)
            head_analysis, head_sha, head_is_wt = mgr.create_snapshot(args.head_ref)
            git_renames = mgr.find_git_renames(args.base_ref, args.head_ref)
            diff_res = ArchitectureDiffEngine.compare_analyses(
                base=base_analysis,
                head=head_analysis,
                base_ref=args.base_ref,
                head_ref=args.head_ref,
                base_commit_sha=base_sha,
                head_commit_sha=head_sha,
                base_is_working_tree=base_is_wt,
                head_is_working_tree=head_is_wt,
                git_renames=git_renames,
            )
        except Exception as exc:
            print(f"[ERROR] Architecture diff failed: {exc}", file=sys.stderr)
            return 1

        output_text = diff_res.model_dump_json(indent=2) if args.format == "json" else diff_res.summary_text
        if args.output:
            out_path = Path(args.output)
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_text(output_text, encoding="utf-8")
            print(f"Diff written to {out_path}")
        else:
            print(output_text)
        return 0

    if args.command == "context":
        try:
            source_type = _detect_source_type(args.target)
            req = ScanRequest(source_type=source_type, target=args.target)
            analysis = run_repository_analysis(req)
            ctx = AgentContextBuilder.build_context(
                analysis=analysis,
                mode=args.mode,
                query=args.query,
                max_tokens=args.max_tokens,
            )
        except Exception as exc:
            print(f"[ERROR] Context generation failed: {exc}", file=sys.stderr)
            return 1

        output_text = ctx.as_json(indent=2) if args.format == "json" else ctx.as_markdown()
        if args.output:
            out_path = Path(args.output)
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_text(output_text, encoding="utf-8")
            print(f"Context written to {out_path}")
        else:
            print(output_text)
        return 0

    if args.command == "mcp":
        roots = [Path(r) for r in args.allowed_roots] if args.allowed_roots else None
        server = RepoDNAMCPServer(allowed_roots=roots)
        server.run_stdio()
        return 0

    if args.command == "setup":
        installer = AgentInstaller(
            agent=args.agent,
            scope=args.scope,
            dry_run=args.dry_run,
        )
        if args.verify:
            res = installer.verify()
            print(json.dumps(res, indent=2))
            return 0
        if args.repair:
            res = installer.repair()
            print(json.dumps(res, indent=2))
            return 0
        if args.uninstall:
            res = installer.uninstall()
            print(json.dumps(res, indent=2))
            return 0
        res = installer.install()
        print(json.dumps(res, indent=2))
        return 0

    if args.command == "doctor":
        return run_doctor()

    if args.command == "contract":
        if args.contract_action == "init":
            try:
                target_p = init_starter_contract(args.target, overwrite=args.force)
                print(f"Created starter Architecture Contract at: {target_p}")
                return 0
            except Exception as exc:
                print(f"[ERROR] Failed to init architecture contract: {exc}", file=sys.stderr)
                return 1

        if args.contract_action == "validate":
            try:
                target_path = Path(args.path).resolve()
                c_file = target_path if target_path.is_file() else find_contract_file(target_path)
                if not c_file:
                    print(f"[ERROR] No architecture contract file found at '{target_path}'", file=sys.stderr)
                    return 1
                contract = load_contract_file(c_file)
                print(
                    f"Valid Architecture Contract: '{c_file}' (Schema v{contract.version}, {len(contract.rules)} rules, "
                    f"Policy: mode={contract.policy.mode.value}, unknown_behavior={contract.policy.unknown_behavior.value})"
                )
                return 0
            except Exception as exc:
                print(f"[ERROR] Contract validation failed: {exc}", file=sys.stderr)
                return 1

        if args.contract_action == "check":
            try:
                target_path = Path(args.target).resolve()
                if args.contract:
                    c_file = Path(args.contract).resolve()
                else:
                    c_file = find_contract_file(target_path)

                if not c_file or not c_file.exists():
                    print(f"[ERROR] No architecture contract found for '{target_path}'. Run 'repodna contract init' to create one.", file=sys.stderr)
                    return 1

                contract = load_contract_file(c_file)
                stype = _detect_source_type(str(target_path))
                analysis = run_repository_analysis(ScanRequest(source_type=stype, target=str(target_path)))
                mode_override = ContractMode(args.mode) if args.mode else None
                evaluator = ContractEvaluator(
                    contract=contract,
                    baseline=args.baseline,
                    mode_override=mode_override,
                )
                report = evaluator.evaluate(analysis)
            except Exception as exc:
                print(f"[ERROR] Contract check failed: {exc}", file=sys.stderr)
                return 1

            output_text = report.model_dump_json(indent=2) if args.format == "json" else report.summary_text
            if args.output:
                out_p = Path(args.output)
                out_p.parent.mkdir(parents=True, exist_ok=True)
                out_p.write_text(output_text, encoding="utf-8")
                print(f"Report written to {out_p}")
            else:
                print(output_text)

            return 0 if (report.verdict in ("PASS", "WARNING") and report.mode == ContractMode.ADVISORY) or report.verdict == "PASS" else 1

    if args.command == "guardian":
        if args.guardian_action == "check":
            try:
                target_path = Path(args.target).resolve()
                snap_mgr = SnapshotManager(target_path)
                base_analysis, base_sha, base_is_wt = snap_mgr.create_snapshot(args.base)
                head_analysis, head_sha, head_is_wt = snap_mgr.create_snapshot(args.head)
                git_renames = snap_mgr.find_git_renames(args.base, args.head)

                guardian_contract: ArchitectureContract | None = None
                c_file = Path(args.contract).resolve() if args.contract else find_contract_file(target_path)
                if c_file and c_file.exists():
                    guardian_contract = load_contract_file(c_file)

                mode_override = ContractMode(args.mode) if args.mode else None
                guardian = PRArchitectureGuardian(
                    contract=guardian_contract,
                    baseline=args.baseline,
                    mode_override=mode_override,
                )
                guardian_report = guardian.assess(
                    base_analysis=base_analysis,
                    head_analysis=head_analysis,
                    base_ref=args.base,
                    head_ref=args.head,
                    base_commit_sha=base_sha,
                    head_commit_sha=head_sha,
                    base_is_working_tree=base_is_wt,
                    head_is_working_tree=head_is_wt,
                    git_renames=git_renames,
                )
            except Exception as exc:
                print(f"[ERROR] PR Guardian evaluation failed: {exc}", file=sys.stderr)
                return 2

            if args.format == "json":
                output_text = guardian_report.model_dump_json(indent=2)
            elif args.format == "markdown":
                output_text = guardian_report.summary_markdown
            else:
                output_text = guardian_report.summary_markdown

            if args.output:
                out_p = Path(args.output)
                out_p.parent.mkdir(parents=True, exist_ok=True)
                out_p.write_text(output_text, encoding="utf-8")
                print(f"Guardian report written to {out_p}")
            else:
                print(output_text)

            return guardian_report.exit_code

    if args.command == "passport":
        if args.passport_action == "generate":
            try:
                target_path = Path(args.target).resolve()
                stype = _detect_source_type(str(target_path))
                analysis = run_repository_analysis(ScanRequest(source_type=stype, target=str(target_path)))
                c_file = Path(args.contract).resolve() if args.contract else find_contract_file(target_path)
                passport_contract: ArchitectureContract | None = (
                    load_contract_file(c_file) if c_file and c_file.exists() else None
                )

                git_rev = "HEAD"
                try:
                    snap_mgr = SnapshotManager(target_path)
                    git_rev, _, _ = snap_mgr.resolve_commit_metadata("HEAD")
                except Exception:
                    git_rev = "working_tree"

                passport = generate_repository_passport(
                    analysis=analysis,
                    git_revision=git_rev,
                    contract=passport_contract,
                    max_modules=args.max_modules,
                )
            except Exception as exc:
                print(f"[ERROR] Failed to generate passport: {exc}", file=sys.stderr)
                return 1

            if args.format == "markdown":
                output_text = export_passport_to_markdown(passport)
            else:
                output_text = export_passport_to_json(passport)

            if args.output:
                out_p = Path(args.output).resolve()
                out_p.parent.mkdir(parents=True, exist_ok=True)
                out_p.write_text(output_text, encoding="utf-8")
                print(f"Repository passport written to {out_p}")
            elif args.format == "json":
                default_p = target_path / ".repodna" / "passport.json"
                default_p.parent.mkdir(parents=True, exist_ok=True)
                default_p.write_text(output_text, encoding="utf-8")
                print(f"Repository passport generated at: {default_p}")
            else:
                print(output_text)
            return 0

        if args.passport_action == "validate":
            try:
                target_p = Path(args.path or (Path.cwd() / ".repodna" / "passport.json")).resolve()
                passport = validate_passport_file(target_p)
                print(
                    f"Valid Repository Passport: '{target_p}' (Schema v{passport.schema_version}, "
                    f"Repo='{passport.repo_name}', Revision='{passport.git_revision}', "
                    f"Modules={len(passport.module_inventory)}, Health={passport.architecture_health.score} "
                    f"Grade {passport.architecture_health.grade})"
                )
                return 0
            except Exception as exc:
                print(f"[ERROR] Passport validation failed: {exc}", file=sys.stderr)
                return 1

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
