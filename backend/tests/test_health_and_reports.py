"""Tests for explainable Architecture Health rules, limits/cancellation, and JSON/HTML exporters."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from repodna.core.analyzer import ScanCancelledError, run_repository_analysis
from repodna.reports.exporter import export_analysis_to_html, export_analysis_to_json
from repodna.schemas.models import ScanLimits, ScanRequest, SourceType


def test_analyze_temp_repo_with_cycles_and_unsupported_files(tmp_path: Path) -> None:
    repo = tmp_path / "sample_arch"
    (repo / "pkg").mkdir(parents=True)
    (repo / "pkg" / "alpha.py").write_text("from . import beta\ndef a(): pass\n", encoding="utf-8")
    (repo / "pkg" / "beta.py").write_text("from . import alpha\ndef b(): pass\n", encoding="utf-8")
    (repo / "pkg" / "legacy.rb").write_text("puts 'hello from ruby'\n", encoding="utf-8")

    req = ScanRequest(source_type=SourceType.LOCAL, target=str(repo))
    result = run_repository_analysis(req)

    assert result.total_files == 3
    assert result.graph_metrics.cycle_count == 1
    assert "Ruby" in result.transparency.unsupported_languages_detected
    assert "Python" in result.transparency.supported_languages_detected

    rule_ids = [f.rule_id for f in result.health_report.findings]
    assert "ARCH-001" in rule_ids
    assert result.health_report.overall_score is not None
    assert result.health_report.overall_score < 100.0

    # Test JSON & HTML export
    json_str = export_analysis_to_json(result)
    parsed_json = json.loads(json_str)
    assert parsed_json["repo_name"] == "sample_arch"
    assert len(parsed_json["cycles"]) == 1

    html_str = export_analysis_to_html(result)
    assert "<!DOCTYPE html>" in html_str
    assert "ARCH-001" in html_str
    assert "pkg/alpha.py" in html_str


def test_file_limits_and_cancellation(tmp_path: Path) -> None:
    repo = tmp_path / "large_repo"
    repo.mkdir()
    for i in range(15):
        (repo / f"mod_{i}.py").write_text(f"x = {i}\n" * 20, encoding="utf-8")

    # Enforce max_files=10
    req = ScanRequest(
        source_type=SourceType.LOCAL,
        target=str(repo),
        limits=ScanLimits(max_files=10),
    )
    res = run_repository_analysis(req)
    assert res.total_files == 10
    assert res.transparency.truncated_by_limits is True
    assert "max_files" in (res.transparency.truncation_reason or "")

    # Test cancellation hook
    with pytest.raises(ScanCancelledError):
        run_repository_analysis(req, is_cancelled=lambda: True)
