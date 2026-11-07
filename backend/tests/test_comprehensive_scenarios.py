"""Comprehensive Stage 2 test suite covering all 15 required architecture, parser, graph, security, and resilience scenarios."""

from __future__ import annotations

import json
import threading
import time
from pathlib import Path

import pytest

from repodna.core.analyzer import (
    ScanCancelledError,
    ScanTimeoutError,
    run_repository_analysis,
)
from repodna.reports.exporter import export_analysis_to_html, export_analysis_to_json
from repodna.schemas.models import AnalysisResult, ScanLimits, ScanRequest, SourceType
from repodna.security.validators import SecurityValidationError, validate_github_url


def _scan_dir(
    path: Path,
    limits: ScanLimits | None = None,
    cancel_event: threading.Event | None = None,
) -> AnalysisResult:
    req = ScanRequest(
        source_type=SourceType.LOCAL,
        target=str(path),
        limits=limits or ScanLimits(),
    )
    return run_repository_analysis(
        req,
        is_cancelled=(cancel_event.is_set if cancel_event is not None else None),
    )


def test_1_python_relative_imports(tmp_path: Path) -> None:
    """Verify single-dot and multi-dot Python relative imports resolve accurately."""
    (tmp_path / "pkg").mkdir()
    (tmp_path / "pkg" / "__init__.py").write_text("from .sub import sub_helper\n", encoding="utf-8")
    (tmp_path / "pkg" / "util.py").write_text("def base_util() -> int:\n    return 1\n", encoding="utf-8")
    (tmp_path / "pkg" / "sub").mkdir()
    (tmp_path / "pkg" / "sub" / "__init__.py").write_text(
        "from ..util import base_util\nfrom .leaf import leaf_fn\n\ndef sub_helper() -> int:\n    return base_util() + leaf_fn()\n",
        encoding="utf-8",
    )
    (tmp_path / "pkg" / "sub" / "leaf.py").write_text(
        "from .. import util\n\ndef leaf_fn() -> int:\n    return util.base_util()\n",
        encoding="utf-8",
    )

    res = _scan_dir(tmp_path)
    edge_ids = {e.id for e in res.edges}
    assert "pkg/__init__.py->pkg/sub/__init__.py" in edge_ids
    assert "pkg/sub/__init__.py->pkg/util.py" in edge_ids
    assert "pkg/sub/__init__.py->pkg/sub/leaf.py" in edge_ids
    assert "pkg/sub/leaf.py->pkg/util.py" in edge_ids


def test_2_typescript_path_aliases(tmp_path: Path) -> None:
    """Verify tsconfig.json paths and baseUrl aliases resolve to internal TypeScript modules."""
    tsconfig = {
        "compilerOptions": {
            "baseUrl": ".",
            "paths": {
                "@core/*": ["packages/core/src/*"],
                "@shared/*": ["src/shared/*"],
            },
        }
    }
    (tmp_path / "tsconfig.json").write_text(json.dumps(tsconfig), encoding="utf-8")
    (tmp_path / "packages" / "core" / "src").mkdir(parents=True)
    (tmp_path / "packages" / "core" / "src" / "engine.ts").write_text(
        "export class CoreEngine { run(): void {} }\n", encoding="utf-8"
    )
    (tmp_path / "src" / "shared").mkdir(parents=True)
    (tmp_path / "src" / "shared" / "logger.ts").write_text(
        "export function logInfo(msg: string): void { console.log(msg); }\n", encoding="utf-8"
    )
    (tmp_path / "src" / "app.ts").write_text(
        "import { CoreEngine } from '@core/engine';\nimport { logInfo } from '@shared/logger';\nexport const app = new CoreEngine();\nlogInfo('started');\n",
        encoding="utf-8",
    )

    res = _scan_dir(tmp_path)
    edge_ids = {e.id for e in res.edges}
    assert "src/app.ts->packages/core/src/engine.ts" in edge_ids
    assert "src/app.ts->src/shared/logger.ts" in edge_ids


def test_3_javascript_dynamic_imports(tmp_path: Path) -> None:
    """Verify static vs dynamic import(...) handling in JavaScript modules."""
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "lazyChart.js").write_text(
        "export function renderChart() { return 'chart'; }\n", encoding="utf-8"
    )
    (tmp_path / "src" / "index.js").write_text(
        "export async function loadFeature(pluginName) {\n"
        "  const mod = await import('./lazyChart.js');\n"
        "  const dynamicPlugin = await import(`./plugins/${pluginName}.js`);\n"
        "  return { mod, dynamicPlugin };\n"
        "}\n",
        encoding="utf-8",
    )

    res = _scan_dir(tmp_path)
    edge_ids = {e.id for e in res.edges}
    assert "src/index.js->src/lazyChart.js" in edge_ids


def test_4_go_module_imports(tmp_path: Path) -> None:
    """Verify Go module imports using go.mod module path prefix vs external stdlib."""
    (tmp_path / "go.mod").write_text("module github.com/acme/ordersvc\n\ngo 1.22\n", encoding="utf-8")
    (tmp_path / "internal" / "store").mkdir(parents=True)
    (tmp_path / "internal" / "store" / "db.go").write_text(
        "package store\n\ntype Store struct{}\nfunc Connect() *Store { return &Store{} }\n",
        encoding="utf-8",
    )
    (tmp_path / "cmd" / "server").mkdir(parents=True)
    (tmp_path / "cmd" / "server" / "main.go").write_text(
        'package main\n\nimport (\n\t"fmt"\n\t"github.com/acme/ordersvc/internal/store"\n)\n\nfunc main() {\n\ts := store.Connect()\n\tfmt.Println(s)\n}\n',
        encoding="utf-8",
    )

    res = _scan_dir(tmp_path)
    edge_ids = {e.id for e in res.edges}
    assert "cmd/server/main.go->internal/store/db.go" in edge_ids
    main_node = next(f for f in res.files if f.id == "cmd/server/main.go")
    assert "fmt" in main_node.imports_external


def test_5_rust_module_declarations_and_braced_use(tmp_path: Path) -> None:
    """Verify Rust `mod foo;` declarations and braced `use crate::services::{auth, billing};` clauses."""
    (tmp_path / "src" / "services").mkdir(parents=True)
    (tmp_path / "src" / "config.rs").write_text("pub struct Config { pub port: u16 }\n", encoding="utf-8")
    (tmp_path / "src" / "services" / "mod.rs").write_text("pub mod auth;\npub mod billing;\n", encoding="utf-8")
    (tmp_path / "src" / "services" / "auth.rs").write_text("pub fn verify() -> bool { true }\n", encoding="utf-8")
    (tmp_path / "src" / "services" / "billing.rs").write_text("pub fn charge() -> bool { true }\n", encoding="utf-8")
    (tmp_path / "src" / "lib.rs").write_text(
        "mod config;\npub mod services;\nuse crate::services::{auth, billing};\n\npub fn run() -> bool {\n    auth::verify() && billing::charge()\n}\n",
        encoding="utf-8",
    )

    res = _scan_dir(tmp_path)
    edge_ids = {e.id for e in res.edges}
    assert "src/lib.rs->src/config.rs" in edge_ids
    assert "src/lib.rs->src/services/mod.rs" in edge_ids
    assert "src/lib.rs->src/services/auth.rs" in edge_ids
    assert "src/lib.rs->src/services/billing.rs" in edge_ids
    assert "src/services/mod.rs->src/services/auth.rs" in edge_ids
    assert "src/services/mod.rs->src/services/billing.rs" in edge_ids


def test_6_circular_dependency_overlapping_sccs(tmp_path: Path) -> None:
    """Verify Tarjan SCC and Johnson elementary cycle finder detect overlapping cycles in a single SCC."""
    (tmp_path / "a.py").write_text("import b\n", encoding="utf-8")
    (tmp_path / "b.py").write_text("import c\nimport d\n", encoding="utf-8")
    (tmp_path / "c.py").write_text("import a\n", encoding="utf-8")
    (tmp_path / "d.py").write_text("import a\n", encoding="utf-8")

    res = _scan_dir(tmp_path)
    assert res.graph_metrics.cycle_count == 2
    assert res.graph_metrics.nodes_in_cycles == 4
    cycle_node_sets = [set(c.nodes[:-1]) for c in res.cycles]
    assert {"a.py", "b.py", "c.py"} in cycle_node_sets
    assert {"a.py", "b.py", "d.py"} in cycle_node_sets


def test_7_disconnected_graph(tmp_path: Path) -> None:
    """Verify disconnected subgraphs and orphan file metrics."""
    (tmp_path / "mod_a1.py").write_text("import mod_a2\n", encoding="utf-8")
    (tmp_path / "mod_a2.py").write_text("def a2(): pass\n", encoding="utf-8")
    (tmp_path / "mod_b1.py").write_text("import mod_b2\n", encoding="utf-8")
    (tmp_path / "mod_b2.py").write_text("def b2(): pass\n", encoding="utf-8")
    (tmp_path / "isolated_helper.py").write_text("def unused(): pass\n", encoding="utf-8")

    res = _scan_dir(tmp_path)
    assert res.graph_metrics.connected_components == 3
    assert res.graph_metrics.orphan_files_count == 1
    orphan = next(f for f in res.files if f.id == "isolated_helper.py")
    assert orphan.is_orphan is True


def test_8_empty_repository(tmp_path: Path) -> None:
    """Verify empty repository completes cleanly with 0 nodes and 100.0 health score."""
    res = _scan_dir(tmp_path)
    assert len(res.files) == 0
    assert len(res.edges) == 0
    assert res.graph_metrics.total_nodes == 0
    assert res.graph_metrics.graph_density == 0.0
    assert res.health_report.overall_score == 100.0


def test_9_monorepo_workspace(tmp_path: Path) -> None:
    """Verify cross-package imports in a monorepo (`packages/ui` importing `packages/shared`)."""
    (tmp_path / "packages" / "shared" / "src").mkdir(parents=True)
    (tmp_path / "packages" / "shared" / "src" / "index.ts").write_text(
        "export const VERSION = '1.0.0';\n", encoding="utf-8"
    )
    (tmp_path / "packages" / "ui" / "src").mkdir(parents=True)
    (tmp_path / "packages" / "ui" / "src" / "App.tsx").write_text(
        "import { VERSION } from '@acme/shared';\nexport function App() { return VERSION; }\n",
        encoding="utf-8",
    )

    res = _scan_dir(tmp_path)
    edge_ids = {e.id for e in res.edges}
    assert "packages/ui/src/App.tsx->packages/shared/src/index.ts" in edge_ids


def test_10_unsupported_languages_transparency(tmp_path: Path) -> None:
    """Verify unsupported languages (.rb, .php, .sql) are inventoried and disclosed in transparency."""
    (tmp_path / "legacy.rb").write_text("class Legacy\n  def run; end\nend\n", encoding="utf-8")
    (tmp_path / "index.php").write_text("<?php echo 'hello'; ?>\n", encoding="utf-8")
    (tmp_path / "schema.sql").write_text("CREATE TABLE users (id INT PRIMARY KEY);\n", encoding="utf-8")
    (tmp_path / "main.py").write_text("def main(): pass\n", encoding="utf-8")

    res = _scan_dir(tmp_path)
    assert "Ruby" in res.transparency.unsupported_languages_detected
    assert "PHP" in res.transparency.unsupported_languages_detected
    assert "SQL" in res.transparency.unsupported_languages_detected
    assert res.transparency.unsupported_files_count == 3
    assert "Python" in res.transparency.supported_languages_detected


def test_11_large_repository_and_max_files_limit(tmp_path: Path) -> None:
    """Verify scanning a 120-file repository and respecting max_files boundary."""
    src = tmp_path / "src"
    src.mkdir()
    for i in range(120):
        nxt = (i + 1) % 120
        (src / f"mod_{i:03d}.py").write_text(
            f"import src.mod_{nxt:03d}\n\ndef fn_{i}() -> int:\n    return {i}\n",
            encoding="utf-8",
        )

    full_res = _scan_dir(tmp_path)
    assert len(full_res.files) == 120
    assert len(full_res.edges) == 120

    capped_res = _scan_dir(tmp_path, limits=ScanLimits(max_files=50))
    assert len(capped_res.files) == 50
    assert capped_res.transparency.truncated_by_limits is True
    assert "50" in (capped_res.transparency.truncation_reason or "")


def test_12_cancellation_and_timeout(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify cooperative cancellation via threading.Event and timeout enforcement."""
    for i in range(20):
        (tmp_path / f"f_{i}.py").write_text(f"x = {i}\n", encoding="utf-8")

    cancel_event = threading.Event()
    cancel_event.set()

    with pytest.raises(ScanCancelledError):
        _scan_dir(tmp_path, cancel_event=cancel_event)

    # Simulate timeout expiration via monotonic clock advance
    real_monotonic = time.monotonic
    call_count = 0

    def advancing_clock() -> float:
        nonlocal call_count
        call_count += 1
        return real_monotonic() + (call_count * 15.0)

    monkeypatch.setattr("repodna.core.analyzer.time.monotonic", advancing_clock)
    with pytest.raises(ScanTimeoutError):
        _scan_dir(tmp_path, limits=ScanLimits(timeout_seconds=10.0))


def test_13_malformed_and_ssrf_github_urls() -> None:
    """Verify strict GitHub URL validator blocks SSRF, credentials, non-HTTPS, and traversal."""
    canonical, owner, repo = validate_github_url("https://github.com/fastapi/fastapi.git")
    assert (canonical, owner, repo) == ("https://github.com/fastapi/fastapi.git", "fastapi", "fastapi")

    invalid_urls = [
        "http://github.com/owner/repo",
        "ssh://git@github.com/owner/repo.git",
        "https://user:token@github.com/owner/repo",
        "https://127.0.0.1/owner/repo",
        "https://169.254.169.254/latest/meta-data",
        "https://evil.example.com/owner/repo",
        "https://github.com/owner/repo?webhook=http://internal",
        "https://github.com/owner/../etc/passwd",
        "https://github.com/-flaginjection/repo",
    ]
    for bad in invalid_urls:
        with pytest.raises(SecurityValidationError):
            validate_github_url(bad)


def test_14_parser_failure_recovery_utf16_and_unicode(tmp_path: Path) -> None:
    """Verify broken syntax files, UTF-16 BOM files, and Unicode filenames do not crash analysis."""
    (tmp_path / "helper.py").write_text("def ok() -> int:\n    return 42\n", encoding="utf-8")
    (tmp_path / "broken.py").write_text(
        "import helper\n\ndef incomplete_func(x, y:\n    return x +\n",
        encoding="utf-8",
    )
    (tmp_path / "utf16_mod.py").write_bytes(
        "import helper\n\ndef utf16_fn() -> int:\n    return helper.ok()\n".encode("utf-16")
    )
    (tmp_path / "çekirdek_modülü.py").write_text(
        "import helper\n\ndef çalıştır() -> int:\n    return helper.ok()\n",
        encoding="utf-8",
    )

    res = _scan_dir(tmp_path)
    file_ids = {f.id for f in res.files}
    assert "helper.py" in file_ids
    assert "broken.py" in file_ids
    assert "utf16_mod.py" in file_ids
    assert "çekirdek_modülü.py" in file_ids

    edge_ids = {e.id for e in res.edges}
    assert "broken.py->helper.py" in edge_ids
    assert "utf16_mod.py->helper.py" in edge_ids
    assert "çekirdek_modülü.py->helper.py" in edge_ids


def test_15_deterministic_export(tmp_path: Path) -> None:
    """Verify deterministic JSON export produces byte-for-byte identical output across repeated scans."""
    (tmp_path / "alpha.py").write_text("import beta\n\ndef a(): return beta.b()\n", encoding="utf-8")
    (tmp_path / "beta.py").write_text("def b(): return 1\n", encoding="utf-8")

    res1 = _scan_dir(tmp_path)
    res2 = _scan_dir(tmp_path)

    json1 = export_analysis_to_json(res1, deterministic=True)
    json2 = export_analysis_to_json(res2, deterministic=True)
    assert json1 == json2

    html_out = export_analysis_to_html(res1)
    assert "<!DOCTYPE html>" in html_out
    assert "alpha.py" in html_out
