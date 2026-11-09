"""Real Git fixture scenarios and end-to-end regression benchmarks for PR Architecture Guardian."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from repodna.contract.loader import load_contract_from_yaml
from repodna.diff.snapshot import SnapshotManager
from repodna.guardian.engine import PRArchitectureGuardian
from repodna.guardian.models import GuardianVerdict, RiskLevel
from repodna.passport.generator import generate_repository_passport
from repodna.security.validators import SecurityValidationError


def _setup_git_repo(path: Path) -> None:
    subprocess.run(["git", "init", str(path)], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(path), "config", "user.name", "RepoDNA Tester"], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(path), "config", "user.email", "tester@repodna.dev"], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(path), "config", "commit.gpgsign", "false"], check=True, capture_output=True)


def _git_commit(path: Path, msg: str) -> str:
    subprocess.run(["git", "-C", str(path), "add", "-A"], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(path), "commit", "-m", msg], check=True, capture_output=True)
    out = subprocess.check_output(["git", "-C", str(path), "rev-parse", "HEAD"], text=True).strip()
    return out


def test_scenario_python_fixture_circular_dependency_lifecycle(tmp_path: Path) -> None:
    repo = tmp_path / "py_repo"
    repo.mkdir()
    _setup_git_repo(repo)

    # Commit 1: Clean architecture
    (repo / "service.py").write_text("import repo\ndef do_service(): return repo.get_data()\n", encoding="utf-8")
    (repo / "repo.py").write_text("def get_data(): return 42\n", encoding="utf-8")
    c1 = _git_commit(repo, "Initial clean architecture")

    # Commit 2: Regressive PR introducing cycle (repo -> service)
    (repo / "repo.py").write_text("import service\ndef get_data(): return service.do_service()\n", encoding="utf-8")
    c2 = _git_commit(repo, "Introduce circular dependency")

    snap_mgr = SnapshotManager(repo)
    base_analysis, base_sha, _ = snap_mgr.create_snapshot(c1)
    head_analysis, head_sha, _ = snap_mgr.create_snapshot(c2)

    guardian = PRArchitectureGuardian()
    report = guardian.assess(base_analysis, head_analysis, base_ref=c1, head_ref=c2)

    assert report.verdict == GuardianVerdict.FAIL
    assert len(report.new_cycles) == 1
    assert report.risk_assessment.risk_level in (RiskLevel.MODERATE, RiskLevel.HIGH)

    # Commit 3: Fix cycle by inverting dependency
    (repo / "repo.py").write_text("def get_data(): return 100\n", encoding="utf-8")
    c3 = _git_commit(repo, "Fix circular dependency")

    fix_analysis, fix_sha, _ = snap_mgr.create_snapshot(c3)
    fix_report = guardian.assess(head_analysis, fix_analysis, base_ref=c2, head_ref=c3)

    assert fix_report.verdict == GuardianVerdict.PASS
    assert len(fix_report.new_cycles) == 0
    assert len(fix_report.resolved_cycles) == 1


def test_scenario_typescript_fixture_contract_violations(tmp_path: Path) -> None:
    repo = tmp_path / "ts_repo"
    repo.mkdir()
    _setup_git_repo(repo)

    # Define contract: domain must not import infra
    contract_yaml = """
version: 1
policy:
  mode: enforce
rules:
  - id: DOMAIN-001
    title: Domain Isolation
    from: "domain/**"
    disallow_imports:
      - "infra/**"
    severity: error
    remediation: Invert dependency
"""
    contract = load_contract_from_yaml(contract_yaml)

    # Commit 1: Clean TS setup
    (repo / "domain").mkdir()
    (repo / "domain" / "user.ts").write_text("export interface User { id: string; }\n", encoding="utf-8")
    (repo / "infra").mkdir()
    (repo / "infra" / "db.ts").write_text("export const db = {};\n", encoding="utf-8")
    c1 = _git_commit(repo, "Initial clean TS architecture")

    # Commit 2: Regressive PR: user.ts imports db.ts directly
    (repo / "domain" / "user.ts").write_text("import { db } from '../infra/db';\nexport const u = db;\n", encoding="utf-8")
    c2 = _git_commit(repo, "Violate domain boundary")

    snap_mgr = SnapshotManager(repo)
    base_analysis, _, _ = snap_mgr.create_snapshot(c1)
    head_analysis, _, _ = snap_mgr.create_snapshot(c2)

    guardian = PRArchitectureGuardian(contract=contract)
    report = guardian.assess(base_analysis, head_analysis, base_ref=c1, head_ref=c2)

    assert report.verdict == GuardianVerdict.FAIL
    assert len(report.new_contract_violations) == 1
    v = report.new_contract_violations[0]
    assert v.rule_id == "DOMAIN-001"
    assert v.source_file == "domain/user.ts"
    assert v.target_file == "infra/db.ts"


def test_scenario_readme_only_change(tmp_path: Path) -> None:
    repo = tmp_path / "docs_repo"
    repo.mkdir()
    _setup_git_repo(repo)

    (repo / "main.py").write_text("print('hello')\n", encoding="utf-8")
    (repo / "README.md").write_text("# Old Title\n", encoding="utf-8")
    c1 = _git_commit(repo, "Initial commit")

    # Only change README
    (repo / "README.md").write_text("# New Title\nDocumentation update only\n", encoding="utf-8")
    c2 = _git_commit(repo, "Docs only update")

    snap_mgr = SnapshotManager(repo)
    base_analysis, _, _ = snap_mgr.create_snapshot(c1)
    head_analysis, _, _ = snap_mgr.create_snapshot(c2)

    guardian = PRArchitectureGuardian()
    report = guardian.assess(base_analysis, head_analysis, base_ref=c1, head_ref=c2)

    assert report.verdict == GuardianVerdict.PASS
    assert len(report.new_cycles) == 0
    assert len(report.added_modules) == 0
    assert len(report.removed_modules) == 0
    assert report.health_delta.score_delta == 0.0


def test_scenario_file_lifecycle_add_remove_rename(tmp_path: Path) -> None:
    repo = tmp_path / "rename_repo"
    repo.mkdir()
    _setup_git_repo(repo)

    (repo / "mod_a.py").write_text("def a(): return 1\n", encoding="utf-8")
    (repo / "obsolete.py").write_text("def dead(): pass\n", encoding="utf-8")
    c1 = _git_commit(repo, "Initial state")

    # Rename mod_a -> mod_b, delete obsolete, add brand_new
    subprocess.run(["git", "-C", str(repo), "mv", "mod_a.py", "mod_b.py"], check=True, capture_output=True)
    (repo / "obsolete.py").unlink()
    (repo / "brand_new.py").write_text("def fresh(): return 99\n", encoding="utf-8")
    c2 = _git_commit(repo, "Refactor modules")

    snap_mgr = SnapshotManager(repo)
    base_analysis, _, _ = snap_mgr.create_snapshot(c1)
    head_analysis, _, _ = snap_mgr.create_snapshot(c2)
    git_renames = snap_mgr.find_git_renames(c1, c2)

    guardian = PRArchitectureGuardian()
    report = guardian.assess(base_analysis, head_analysis, base_ref=c1, head_ref=c2, git_renames=git_renames)

    assert "brand_new.py" in report.added_modules
    assert "obsolete.py" in report.removed_modules
    assert len(report.renamed_modules) == 1
    assert report.renamed_modules[0].old_path == "mod_a.py"
    assert report.renamed_modules[0].new_path == "mod_b.py"


def test_scenario_nicewp_partial_coverage_honesty(tmp_path: Path) -> None:
    """NiceWP scenario: repository in C# with partial or no AST parser."""
    repo = tmp_path / "nicewp"
    repo.mkdir()
    (repo / "Program.cs").write_text("using System;\nclass Program { static void Main() {} }\n", encoding="utf-8")
    (repo / "Service.cs").write_text("using System;\nclass Service {}\n", encoding="utf-8")

    from repodna.core.analyzer import run_repository_analysis
    from repodna.schemas.models import ScanRequest, SourceType

    analysis = run_repository_analysis(ScanRequest(source_type=SourceType.LOCAL, target=str(repo)))
    passport = generate_repository_passport(analysis)

    # Invariant: Never claim fake 100/100 or fake High confidence on unparsed C#
    assert passport.ast_coverage.ast_loc_coverage_pct == 0.0
    assert passport.architecture_health.grade in ("N/A", "F")
    assert len(passport.unknown_unverified) > 0


def test_scenario_security_invalid_git_ref(tmp_path: Path) -> None:
    repo = tmp_path / "sec_repo"
    repo.mkdir()
    _setup_git_repo(repo)
    (repo / "a.py").write_text("print(1)\n", encoding="utf-8")
    _git_commit(repo, "Init")

    snap_mgr = SnapshotManager(repo)

    # 1. Flag injection
    with pytest.raises(SecurityValidationError, match="Invalid git reference syntax"):
        snap_mgr.create_snapshot("--upload-pack=evil")

    # 2. Command injection shell character
    with pytest.raises(SecurityValidationError, match="Invalid git reference syntax"):
        snap_mgr.create_snapshot("HEAD;rm -rf /")

    # 3. Non-existent commit
    with pytest.raises(SecurityValidationError, match="does not exist"):
        snap_mgr.create_snapshot("non_existent_commit_123456789")
