"""Standalone CLI scanner for RepoDNA."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from repodna.core.analyzer import run_repository_analysis
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
        description="RepoDNA — Developer Repository Intelligence Platform CLI",
    )
    sub = parser.add_subparsers(dest="command", required=True)

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
    return parser


def main(argv: list[str] | None = None) -> int:
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

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
