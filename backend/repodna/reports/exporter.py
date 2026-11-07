"""Deterministic JSON and standalone interactive HTML report exporters."""

from __future__ import annotations

import html

from repodna.schemas.models import AnalysisResult


def export_analysis_to_json(result: AnalysisResult, indent: int = 2) -> str:
    """Serialize AnalysisResult to deterministic, formatted JSON."""
    return result.model_dump_json(indent=indent)


def export_analysis_to_html(result: AnalysisResult) -> str:
    """
    Generate a standalone, self-contained HTML architecture report with dark/light mode support,
    executive metrics, explainable rule findings, circular dependency chains, and module inventory.
    """
    esc = html.escape
    hr = result.health_report
    gm = result.graph_metrics
    tr = result.transparency

    findings_rows = ""
    if hr.findings:
        for fn in hr.findings:
            sev_badge = {
                "critical": "background:#ef444422;color:#f87171;border:1px solid #ef444466;",
                "warning": "background:#f59e0b22;color:#fbbf24;border:1px solid #f59e0b66;",
                "info": "background:#3b82f622;color:#60a5fa;border:1px solid #3b82f666;",
            }.get(fn.severity.value, "")
            ev_items = "".join(f"<li><code>{esc(ev)}</code></li>" for ev in fn.evidence[:6])
            findings_rows += f"""
            <tr>
              <th scope="row"><code>{esc(fn.rule_id)}</code><br><strong>{esc(fn.title)}</strong></th>
              <td><span style="padding:2px 8px;border-radius:999px;font-size:12px;text-transform:uppercase;{sev_badge}">{esc(fn.severity.value)}</span></td>
              <td><strong>-{fn.score_deduction:.1f}</strong> / -{fn.max_deduction:.0f}</td>
              <td>
                <div><small><strong>Formula:</strong> <code>{esc(fn.formula_explanation)}</code></small></div>
                <div><small><strong>Threshold:</strong> {esc(fn.threshold_description)}</small></div>
                <ul style="margin:6px 0 0 16px;padding:0;font-size:12px;">{ev_items}</ul>
              </td>
              <td>{esc(fn.remediation)}</td>
            </tr>
            """
    else:
        findings_rows = """
        <tr>
          <td colspan="5" style="text-align:center;padding:18px;color:#10b981;">
            All architectural health rules passed with zero deductions.
          </td>
        </tr>
        """

    cycle_rows = ""
    if result.cycles:
        for c in result.cycles:
            chain = " &rarr; ".join(f"<code>{esc(n)}</code>" for n in c.nodes)
            cycle_rows += f"""
            <tr>
              <th scope="row"><code>{esc(c.id)}</code></th>
              <td>{c.length} hops</td>
              <td>{esc(c.severity.value.upper())}</td>
              <td>{chain}</td>
            </tr>
            """
    else:
        cycle_rows = """
        <tr>
          <td colspan="4" style="text-align:center;padding:14px;color:#10b981;">
            Zero circular dependencies detected across the repository graph.
          </td>
        </tr>
        """

    lang_rows = ""
    for lg in result.languages:
        lang_rows += f"""
        <tr>
          <th scope="row">{esc(lg.language)}</th>
          <td><code>{esc(lg.support_level.value)}</code></td>
          <td>{lg.file_count}</td>
          <td>{lg.lines_code:,}</td>
          <td>{lg.percentage_of_code:.1f}%</td>
        </tr>
        """

    file_rows = ""
    for f in sorted(result.files, key=lambda x: (x.in_cycle, x.fan_in + x.fan_out, x.lines_code), reverse=True)[:150]:
        cyc_tag = "YES" if f.in_cycle else "No"
        file_rows += f"""
        <tr>
          <th scope="row"><code>{esc(f.id)}</code></th>
          <td>{esc(f.language)}</td>
          <td>{f.lines_code:,}</td>
          <td>{f.fan_in}</td>
          <td>{f.fan_out}</td>
          <td>{f.instability:.2f}</td>
          <td>{cyc_tag}</td>
        </tr>
        """

    passed_list = "".join(f"<li>{esc(pr)}</li>" for pr in hr.passed_rules)
    unsupported_str = ", ".join(esc(u) for u in tr.unsupported_languages_detected) or "None"

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="color-scheme" content="light dark">
  <title>RepoDNA Architecture Report — {esc(result.repo_name)}</title>
  <style>
    :root {{
      color-scheme: light dark;
      --bg: light-dark(#f8fafc, #090d16);
      --surface: light-dark(#ffffff, #111827);
      --border: light-dark(#e2e8f0, #1f2937);
      --text: light-dark(#0f172a, #f1f5f9);
      --muted: light-dark(#475569, #94a3b8);
      --accent: light-dark(#2563eb, #38bdf8);
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      padding: 32px 24px;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
      background: var(--bg);
      color: var(--text);
      line-height: 1.5;
    }}
    .container {{ max-width: 1280px; margin: 0 auto; }}
    header {{
      display: flex;
      flex-wrap: wrap;
      justify-content: space-between;
      align-items: center;
      gap: 16px;
      padding-bottom: 20px;
      border-bottom: 1px solid var(--border);
      margin-bottom: 24px;
    }}
    h1 {{ margin: 0; font-size: 26px; }}
    h2 {{ margin: 28px 0 12px; font-size: 18px; }}
    .kpi-grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
      gap: 14px;
    }}
    .card {{
      background: var(--surface);
      border: 1px solid var(--border);
      border-radius: 10px;
      padding: 16px;
    }}
    .kpi-label {{ font-size: 12px; text-transform: uppercase; color: var(--muted); letter-spacing: 0.05em; }}
    .kpi-value {{ font-size: 26px; font-weight: 700; margin-top: 4px; color: var(--accent); }}
    .table-wrapper {{
      overflow: auto;
      max-inline-size: 100%;
      border: 1px solid var(--border);
      border-radius: 10px;
      background: var(--surface);
      margin-bottom: 20px;
    }}
    table {{
      width: 100%;
      border-collapse: separate;
      border-spacing: 0;
      font-size: 13px;
    }}
    th, td {{
      padding: 10px 12px;
      text-align: left;
      border-bottom: 1px solid var(--border);
      vertical-align: top;
    }}
    thead th {{
      position: sticky;
      inset-block-start: 0;
      background: var(--surface);
      font-weight: 600;
      color: var(--muted);
      z-index: 1;
    }}
    code {{
      font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
      font-size: 12px;
    }}
    .methodology {{ font-size: 13px; color: var(--muted); margin-bottom: 16px; }}
  </style>
</head>
<body>
  <div class="container">
    <header>
      <div>
        <h1>RepoDNA Architectural Intelligence Report: {esc(result.repo_name)}</h1>
        <div class="methodology">
          Target: <code>{esc(result.target_display)}</code> &bull;
          Source: <code>{esc(result.source_type.value)}</code> &bull;
          Analyzed: <code>{esc(result.analyzed_at.isoformat())}</code> &bull;
          Duration: <code>{result.duration_ms} ms</code>
        </div>
      </div>
      <div class="card" style="text-align:center;min-width:160px;">
        <div class="kpi-label">Architecture Health</div>
        <div class="kpi-value">{hr.overall_score:.1f} / 100 (Grade {esc(hr.grade)})</div>
      </div>
    </header>

    <section aria-labelledby="summary-heading">
      <h2 id="summary-heading">Executive Summary</h2>
      <div class="kpi-grid">
        <div class="card"><div class="kpi-label">Total Files</div><div class="kpi-value">{result.total_files:,}</div></div>
        <div class="card"><div class="kpi-label">Lines of Code</div><div class="kpi-value">{result.total_lines_code:,}</div></div>
        <div class="card"><div class="kpi-label">Internal Dependency Edges</div><div class="kpi-value">{gm.total_edges:,}</div></div>
        <div class="card"><div class="kpi-label">Circular Dependencies</div><div class="kpi-value">{gm.cycle_count}</div></div>
        <div class="card"><div class="kpi-label">Avg Instability Index</div><div class="kpi-value">{gm.average_instability:.2f}</div></div>
        <div class="card"><div class="kpi-label">Git Commits Scanned</div><div class="kpi-value">{result.git_insights.total_commits_scanned}</div></div>
      </div>
    </section>

    <section aria-labelledby="rules-heading">
      <h2 id="rules-heading">Explainable Architecture Health Findings</h2>
      <p class="methodology">{esc(hr.methodology)}</p>
      <div class="table-wrapper" tabindex="0" role="region" aria-labelledby="rules-heading">
        <table>
          <caption>Rule-based architectural findings and deductions</caption>
          <thead>
            <tr>
              <th scope="col">Rule</th>
              <th scope="col">Severity</th>
              <th scope="col">Deduction</th>
              <th scope="col">Formula, Threshold &amp; Evidence</th>
              <th scope="col">Engineering Remediation</th>
            </tr>
          </thead>
          <tbody>
            {findings_rows}
          </tbody>
        </table>
      </div>
      <div class="card">
        <strong>Passed Architectural Rules ({len(hr.passed_rules)}):</strong>
        <ul style="margin:8px 0 0 18px;font-size:13px;">{passed_list}</ul>
      </div>
    </section>

    <section aria-labelledby="cycles-heading">
      <h2 id="cycles-heading">Circular Dependency Chains ({ len(result.cycles) })</h2>
      <div class="table-wrapper" tabindex="0" role="region" aria-labelledby="cycles-heading">
        <table>
          <caption>Detected strongly connected circular dependency chains</caption>
          <thead>
            <tr>
              <th scope="col">Cycle ID</th>
              <th scope="col">Length</th>
              <th scope="col">Severity</th>
              <th scope="col">Cycle Path</th>
            </tr>
          </thead>
          <tbody>
            {cycle_rows}
          </tbody>
        </table>
      </div>
    </section>

    <section aria-labelledby="transparency-heading">
      <h2 id="transparency-heading">Language Coverage &amp; Analysis Transparency</h2>
      <p class="methodology">
        Unsupported languages (counted in LOC but excluded from AST import resolution): <strong>{unsupported_str}</strong> &bull;
        Unresolved internal imports: <strong>{tr.unresolved_internal_imports_count}</strong> &bull;
        Dynamic imports flagged: <strong>{tr.dynamic_imports_count}</strong> &bull;
        Skipped files (symlinks/binaries/limits): <strong>{len(tr.skipped_files)}</strong>
      </p>
      <div class="table-wrapper" tabindex="0" role="region" aria-labelledby="transparency-heading">
        <table>
          <caption>Repository language breakdown and parser support level</caption>
          <thead>
            <tr>
              <th scope="col">Language</th>
              <th scope="col">AST Support Level</th>
              <th scope="col">Files</th>
              <th scope="col">Lines of Code</th>
              <th scope="col">% of Code</th>
            </tr>
          </thead>
          <tbody>
            {lang_rows}
          </tbody>
        </table>
      </div>
    </section>

    <section aria-labelledby="modules-heading">
      <h2 id="modules-heading">Module Topology Inventory (Top 150 Modules)</h2>
      <div class="table-wrapper" tabindex="0" role="region" aria-labelledby="modules-heading">
        <table>
          <caption>Per-file LOC, fan-in, fan-out, and Robert C. Martin instability metrics</caption>
          <thead>
            <tr>
              <th scope="col">Module Path</th>
              <th scope="col">Language</th>
              <th scope="col">LOC</th>
              <th scope="col">Fan-In (Ca)</th>
              <th scope="col">Fan-Out (Ce)</th>
              <th scope="col">Instability (I)</th>
              <th scope="col">In Cycle</th>
            </tr>
          </thead>
          <tbody>
            {file_rows}
          </tbody>
        </table>
      </div>
    </section>
  </div>
</body>
</html>
"""
