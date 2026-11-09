"""Critical hardening integration tests for RepoDNA v0.4.0.

Covers the 10 real-world scenarios:
1. RepoDNA's own repository
2. Independent Python fixture repository
3. Independent TypeScript fixture repository
4. NiceWP C#/.NET repository
5. Fork PR simulation
6. Corrupted baseline
7. Parser coverage deficient repository
8. Rules with zero matches
9. New and resolved circular dependencies
10. Passport stale/invalid Git revision & privacy validation
"""

from __future__ import annotations

import json
import subprocess
import tempfile
from datetime import UTC, datetime
from pathlib import Path

import pytest

from repodna.contract.evaluator import ContractEvaluator
from repodna.contract.loader import load_baseline_file, load_contract_from_yaml
from repodna.contract.models import ContractMode
from repodna.core.analyzer import run_repository_analysis
from repodna.diff.snapshot import SnapshotManager
from repodna.guardian.engine import PRArchitectureGuardian
from repodna.guardian.models import GuardianVerdict
from repodna.passport.generator import (
    generate_repository_passport,
    sanitize_passport_target,
)
from repodna.passport.validator import (
    check_passport_privacy,
    validate_passport_json,
)
from repodna.schemas.models import (
    AnalysisResult,
    ArchitectureHealthReport,
    FileNode,
    GitInsights,
    GraphMetrics,
    LanguageBreakdownItem,
    LanguageSupportLevel,
    ScanRequest,
    SourceType,
    TransparencyReport,
)
from repodna.security.validators import SecurityValidationError


def _run_git(cwd: Path, *args: str) -> str:
    res = subprocess.run(
        ["git", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        check=True,
    )
    return res.stdout.strip()


# -----------------------------------------------------------------------------
# Scenario 1: RepoDNA's own repository
# -----------------------------------------------------------------------------
def test_scenario_1_repodna_self_repository() -> None:
    root = Path.cwd().resolve()
    # 1. Analyze RepoDNA repository
    analysis = run_repository_analysis(ScanRequest(source_type=SourceType.LOCAL, target=str(root)))
    assert analysis.total_files > 30
    assert analysis.transparency.ast_loc_coverage_pct > 80.0

    # 2. Generate and validate passport
    passport = generate_repository_passport(analysis)
    assert passport.repo_name == analysis.repo_name
    assert passport.provenance_verified is True  # Resolved to real commit SHA
    assert len(passport.git_revision) >= 7

    # 3. Privacy check on passport
    leaks = check_passport_privacy(passport)
    assert leaks == [], f"Privacy leaks found in RepoDNA self passport: {leaks}"

    # 4. JSON export and schema validation
    passport_json = passport.model_dump_json(indent=2)
    validated = validate_passport_json(passport_json)
    assert validated.repo_name == analysis.repo_name


# -----------------------------------------------------------------------------
# Scenario 2: Independent Python fixture repository
# -----------------------------------------------------------------------------
def test_scenario_2_independent_python_fixture() -> None:
    with tempfile.TemporaryDirectory() as td:
        repo_dir = Path(td).resolve()
        _run_git(repo_dir, "init")
        _run_git(repo_dir, "config", "user.email", "ci@repodna.dev")
        _run_git(repo_dir, "config", "user.name", "RepoDNA CI")

        (repo_dir / "domain").mkdir()
        (repo_dir / "infra").mkdir()

        (repo_dir / "infra" / "db.py").write_text("class Database:\n    pass\n", encoding="utf-8")
        (repo_dir / "domain" / "entity.py").write_text(
            "from infra.db import Database\nclass User(Database):\n    pass\n",
            encoding="utf-8",
        )

        contract_yaml = """
version: 1
policy:
  mode: enforce
  unknown_behavior: warn
rules:
  - id: DOMAIN-ISOLATION
    title: Domain cannot import Infrastructure
    from: "domain/**"
    disallow_imports:
      - "infra/**"
    severity: error
"""
        contract = load_contract_from_yaml(contract_yaml)
        analysis = run_repository_analysis(ScanRequest(source_type=SourceType.LOCAL, target=str(repo_dir)))
        evaluator = ContractEvaluator(contract, mode_override=ContractMode.ENFORCE)
        report = evaluator.evaluate(analysis)

        # Enforce mode must fail on domain importing infra
        assert report.verdict == "FAIL"
        assert report.is_compliant is False
        assert len(report.new_violations) == 1
        assert report.new_violations[0].rule_id == "DOMAIN-ISOLATION"


# -----------------------------------------------------------------------------
# Scenario 3: Independent TypeScript fixture repository
# -----------------------------------------------------------------------------
def test_scenario_3_independent_typescript_fixture() -> None:
    with tempfile.TemporaryDirectory() as td:
        repo_dir = Path(td).resolve()
        _run_git(repo_dir, "init")
        _run_git(repo_dir, "config", "user.email", "ci@repodna.dev")
        _run_git(repo_dir, "config", "user.name", "RepoDNA CI")

        (repo_dir / "src" / "ui").mkdir(parents=True)
        (repo_dir / "src" / "db").mkdir(parents=True)

        (repo_dir / "src" / "db" / "pool.ts").write_text(
            "export const pool = { connect: () => true };\n", encoding="utf-8"
        )
        (repo_dir / "src" / "ui" / "view.tsx").write_text(
            "import { pool } from '../db/pool';\nexport const View = () => pool.connect();\n",
            encoding="utf-8",
        )

        contract_yaml = """
version: 1
policy:
  mode: enforce
rules:
  - id: UI-NO-DIRECT-DB
    title: UI must not access DB pool
    from: "src/ui/**"
    disallow_imports:
      - "src/db/**"
    severity: error
"""
        contract = load_contract_from_yaml(contract_yaml)
        analysis = run_repository_analysis(ScanRequest(source_type=SourceType.LOCAL, target=str(repo_dir)))
        report = ContractEvaluator(contract, mode_override=ContractMode.ENFORCE).evaluate(analysis)

        assert report.verdict == "FAIL"
        assert len(report.new_violations) == 1
        assert report.new_violations[0].rule_id == "UI-NO-DIRECT-DB"


# -----------------------------------------------------------------------------
# Scenario 4: NiceWP C#/.NET repository honesty
# -----------------------------------------------------------------------------
def test_scenario_4_nicewp_csharp_repository() -> None:
    # Simulate a C# repository where support is partial_static
    csharp_files = [
        FileNode(
            id=f"Services/Service{i}.cs",
            name=f"Service{i}.cs",
            directory="Services",
            extension=".cs",
            language="C#",
            support_level=LanguageSupportLevel.PARTIAL_STATIC,
            size_bytes=1000,
            lines_total=100,
            lines_code=100,
            lines_comment=0,
            lines_blank=0,
        )
        for i in range(1, 10)
    ]
    analysis = AnalysisResult(
        analysis_id="nicewp_sim",
        repo_name="NiceWP",
        source_type=SourceType.LOCAL,
        target_display="./NiceWP",
        analyzed_at=datetime.now(UTC),
        duration_ms=50,
        total_files=len(csharp_files),
        total_lines_code=900,
        total_lines_all=900,
        total_size_bytes=9000,
        languages=[
            LanguageBreakdownItem(
                language="C#",
                support_level=LanguageSupportLevel.PARTIAL_STATIC,
                file_count=9,
                lines_code=900,
                lines_total=900,
                size_bytes=9000,
                percentage_of_code=100.0,
            )
        ],
        files=csharp_files,
        edges=[],
        cycles=[],
        graph_metrics=GraphMetrics(total_nodes=9, total_edges=0),
        health_report=ArchitectureHealthReport(
            overall_score=None,
            grade="N/A",
            status="insufficient_dependency_coverage",
            confidence="none",
            methodology="Standard",
        ),
        git_insights=GitInsights(is_git_repo=True),
        transparency=TransparencyReport(
            ast_loc_coverage_pct=0.0,
            partial_static_languages_detected=["C#"],
            partial_static_files_count=9,
        ),
    )

    contract_yaml = """
version: 1
policy:
  mode: advisory
  unknown_behavior: warn
rules:
  - id: CSHARP-RULE-01
    title: Service Isolation
    from: "Services/**"
    disallow_imports:
      - "Database/**"
"""
    contract = load_contract_from_yaml(contract_yaml)
    report = ContractEvaluator(contract).evaluate(analysis)

    # Must NOT report false pass!
    assert "CSHARP-RULE-01" not in report.rules_passed
    assert "CSHARP-RULE-01" in report.rules_unknown
    assert len(report.unknowns) >= 9
    assert report.verdict in ("WARNING", "INCONCLUSIVE")


# -----------------------------------------------------------------------------
# Scenario 5: Fork PR simulation
# -----------------------------------------------------------------------------
def test_scenario_5_fork_pr_simulation() -> None:
    with tempfile.TemporaryDirectory() as td:
        root = Path(td).resolve()
        upstream = root / "upstream"
        upstream.mkdir()
        _run_git(upstream, "init")
        _run_git(upstream, "config", "user.email", "upstream@repodna.dev")
        _run_git(upstream, "config", "user.name", "Upstream Maintainer")

        (upstream / "app.py").write_text("print('base app')\n", encoding="utf-8")
        _run_git(upstream, "add", ".")
        _run_git(upstream, "commit", "-m", "Initial upstream commit")
        base_sha = _run_git(upstream, "rev-parse", "HEAD")

        # Developer opens branch (simulating fork branch commit)
        _run_git(upstream, "checkout", "-b", "fork-pr-feature")
        (upstream / "feature.py").write_text("import app\nprint('feature')\n", encoding="utf-8")
        _run_git(upstream, "add", ".")
        _run_git(upstream, "commit", "-m", "Add feature from fork")
        head_sha = _run_git(upstream, "rev-parse", "HEAD")

        # SnapshotManager evaluates using immutable commit SHAs
        snap = SnapshotManager(upstream)
        base_analysis, b_sha, _ = snap.create_snapshot(base_sha)
        head_analysis, h_sha, _ = snap.create_snapshot(head_sha)

        guardian = PRArchitectureGuardian(mode_override=ContractMode.ADVISORY)
        report = guardian.assess(
            base_analysis=base_analysis,
            head_analysis=head_analysis,
            base_ref=base_sha,
            head_ref=head_sha,
            base_commit_sha=b_sha,
            head_commit_sha=h_sha,
        )

        assert report.verdict == GuardianVerdict.PASS
        assert report.exit_code == 0
        assert report.should_block_ci is False
        assert "feature.py" in report.added_modules
        assert "## RepoDNA Architecture Guardian — `PASS`" in report.summary_markdown


# -----------------------------------------------------------------------------
# Scenario 6: Corrupted and invalid baseline handling
# -----------------------------------------------------------------------------
def test_scenario_6_corrupted_baseline() -> None:
    with tempfile.TemporaryDirectory() as td:
        root = Path(td).resolve()

        # 1. Unspecified baseline -> empty set
        assert load_baseline_file(None) == set()
        assert load_baseline_file("") == set()

        # 2. Missing baseline explicitly requested -> FileNotFoundError
        missing = root / "does_not_exist.json"
        with pytest.raises(FileNotFoundError, match="Baseline file explicitly specified but does not exist"):
            load_baseline_file(missing)

        # 3. Corrupted JSON -> ValueError
        corrupted = root / "corrupt.json"
        corrupted.write_text("{ this is not valid json", encoding="utf-8")
        with pytest.raises(ValueError, match="Corrupted or invalid JSON"):
            load_baseline_file(corrupted)

        # 4. Invalid schema (not a list or dict with baseline_violations)
        bad_schema = root / "bad_schema.json"
        bad_schema.write_text(json.dumps({"wrong": 123}), encoding="utf-8")
        with pytest.raises(ValueError, match="Invalid baseline format"):
            load_baseline_file(bad_schema)

        # 5. Corrupted items inside list
        bad_entry = root / "bad_entry.json"
        bad_entry.write_text(json.dumps([{"rule_id": "R1"}]), encoding="utf-8")  # missing source & target
        with pytest.raises(ValueError, match="Corrupted baseline entry"):
            load_baseline_file(bad_entry)

        # 6. Valid empty baseline
        empty_b = root / "empty.json"
        empty_b.write_text("[]", encoding="utf-8")
        assert load_baseline_file(empty_b) == set()

        # 7. Valid populated baseline
        valid_b = root / "valid.json"
        valid_b.write_text(
            json.dumps([{"rule_id": "R1", "source_file": "a.py", "target_file": "b.py"}]),
            encoding="utf-8",
        )
        assert load_baseline_file(valid_b) == {("R1", "a.py", "b.py")}


# -----------------------------------------------------------------------------
# Scenario 7: Parser coverage deficient repository
# -----------------------------------------------------------------------------
def test_scenario_7_parser_coverage_deficient_repository() -> None:
    unsupported_files = [
        FileNode(
            id=f"legacy/prog{i}.cob",
            name=f"prog{i}.cob",
            directory="legacy",
            extension=".cob",
            language="COBOL",
            support_level=LanguageSupportLevel.UNSUPPORTED,
            size_bytes=2000,
            lines_total=200,
            lines_code=200,
            lines_comment=0,
            lines_blank=0,
        )
        for i in range(5)
    ]
    analysis = AnalysisResult(
        analysis_id="unsupported_sim",
        repo_name="LegacyCore",
        source_type=SourceType.LOCAL,
        target_display="./LegacyCore",
        analyzed_at=datetime.now(UTC),
        duration_ms=30,
        total_files=5,
        total_lines_code=1000,
        total_lines_all=1000,
        total_size_bytes=10000,
        languages=[
            LanguageBreakdownItem(
                language="COBOL",
                support_level=LanguageSupportLevel.UNSUPPORTED,
                file_count=5,
                lines_code=1000,
                lines_total=1000,
                size_bytes=10000,
                percentage_of_code=100.0,
            )
        ],
        files=unsupported_files,
        edges=[],
        cycles=[],
        graph_metrics=GraphMetrics(total_nodes=5, total_edges=0),
        health_report=ArchitectureHealthReport(
            overall_score=None,
            grade="N/A",
            status="insufficient_data",
            confidence="none",
            methodology="Standard",
        ),
        git_insights=GitInsights(is_git_repo=True),
        transparency=TransparencyReport(
            ast_loc_coverage_pct=0.0,
            unsupported_languages_detected=["COBOL"],
            unsupported_files_count=5,
        ),
    )

    contract_yaml = """
version: 1
policy:
  mode: enforce
  unknown_behavior: fail
rules:
  - id: STRICT-RULE
    title: Strict Rule
    from: "legacy/**"
    disallow_imports: ["secret/**"]
"""
    contract = load_contract_from_yaml(contract_yaml)
    report = ContractEvaluator(contract, mode_override=ContractMode.ENFORCE).evaluate(analysis)

    # When unknown_behavior is fail on unsupported files, must FAIL in enforce mode
    assert report.verdict == "FAIL"
    assert report.is_compliant is False


# -----------------------------------------------------------------------------
# Scenario 8: Rules with zero matches
# -----------------------------------------------------------------------------
def test_scenario_8_unmatched_architectural_rules() -> None:
    files = [
        FileNode(
            id="src/main.py",
            name="main.py",
            directory="src",
            extension=".py",
            language="Python",
            support_level=LanguageSupportLevel.FULL_AST,
            size_bytes=100,
            lines_total=10,
            lines_code=10,
            lines_comment=0,
            lines_blank=0,
        )
    ]
    analysis = AnalysisResult(
        analysis_id="unmatched_test",
        repo_name="demo",
        source_type=SourceType.LOCAL,
        target_display="./demo",
        analyzed_at=datetime.now(UTC),
        duration_ms=10,
        total_files=1,
        total_lines_code=10,
        total_lines_all=10,
        total_size_bytes=100,
        languages=[
            LanguageBreakdownItem(
                language="Python",
                support_level=LanguageSupportLevel.FULL_AST,
                file_count=1,
                lines_code=10,
                lines_total=10,
                size_bytes=100,
                percentage_of_code=100.0,
            )
        ],
        files=files,
        edges=[],
        cycles=[],
        graph_metrics=GraphMetrics(total_nodes=1, total_edges=0),
        health_report=ArchitectureHealthReport(
            overall_score=100.0,
            grade="A",
            status="evaluated",
            confidence="high",
            methodology="Standard",
        ),
        git_insights=GitInsights(is_git_repo=True),
        transparency=TransparencyReport(ast_loc_coverage_pct=100.0, supported_languages_detected=["Python"]),
    )

    contract_yaml = """
version: 1
rules:
  - id: GHOST-RULE-01
    title: Rule that matches nothing
    from: "nonexistent_folder/**"
    disallow_imports: ["any/**"]
"""
    contract = load_contract_from_yaml(contract_yaml)
    report = ContractEvaluator(contract).evaluate(analysis)

    # Must be tracked in rules_unmatched and NOT in rules_passed!
    assert "GHOST-RULE-01" in report.rules_unmatched
    assert "GHOST-RULE-01" not in report.rules_passed
    assert "GHOST-RULE-01" not in report.rules_violated


# -----------------------------------------------------------------------------
# Scenario 9: New and resolved circular dependencies
# -----------------------------------------------------------------------------
def test_scenario_9_new_and_resolved_circular_dependencies() -> None:
    with tempfile.TemporaryDirectory() as td:
        repo_dir = Path(td).resolve()
        _run_git(repo_dir, "init")
        _run_git(repo_dir, "config", "user.email", "dev@repodna.dev")
        _run_git(repo_dir, "config", "user.name", "Developer")

        # Base commit: Cycle between A and B
        (repo_dir / "a.py").write_text("import b\n", encoding="utf-8")
        (repo_dir / "b.py").write_text("import a\n", encoding="utf-8")
        (repo_dir / "c.py").write_text("pass\n", encoding="utf-8")
        (repo_dir / "d.py").write_text("pass\n", encoding="utf-8")
        _run_git(repo_dir, "add", ".")
        _run_git(repo_dir, "commit", "-m", "Base: A and B in cycle")
        base_sha = _run_git(repo_dir, "rev-parse", "HEAD")

        # Head commit: Resolve A-B cycle, but create C-D cycle!
        (repo_dir / "b.py").write_text("pass\n", encoding="utf-8")  # Breaks A-B cycle
        (repo_dir / "c.py").write_text("import d\n", encoding="utf-8")
        (repo_dir / "d.py").write_text("import c\n", encoding="utf-8")  # Creates C-D cycle
        _run_git(repo_dir, "add", ".")
        _run_git(repo_dir, "commit", "-m", "Head: Resolve A-B, introduce C-D cycle")
        head_sha = _run_git(repo_dir, "rev-parse", "HEAD")

        snap = SnapshotManager(repo_dir)
        base_res, _, _ = snap.create_snapshot(base_sha)
        head_res, _, _ = snap.create_snapshot(head_sha)

        # Advisory mode test
        guardian_advisory = PRArchitectureGuardian(mode_override=ContractMode.ADVISORY)
        report_adv = guardian_advisory.assess(
            base_analysis=base_res,
            head_analysis=head_res,
            base_ref=base_sha,
            head_ref=head_sha,
        )
        assert len(report_adv.new_cycles) == 1
        assert len(report_adv.resolved_cycles) == 1
        assert report_adv.verdict == GuardianVerdict.FAIL
        assert report_adv.exit_code == 0  # Advisory mode never blocks CI!
        assert report_adv.should_block_ci is False

        # Enforce mode test
        guardian_enforce = PRArchitectureGuardian(mode_override=ContractMode.ENFORCE)
        report_enf = guardian_enforce.assess(
            base_analysis=base_res,
            head_analysis=head_res,
            base_ref=base_sha,
            head_ref=head_sha,
        )
        assert report_enf.verdict == GuardianVerdict.FAIL
        assert report_enf.exit_code == 1  # Enforce mode blocks CI on new cycle!
        assert report_enf.should_block_ci is True


# -----------------------------------------------------------------------------
# Scenario 10: Passport stale/invalid Git revision & privacy validation
# -----------------------------------------------------------------------------
def test_scenario_10_passport_stale_or_invalid_git_revision_and_privacy() -> None:
    # 1. Path sanitization check
    assert sanitize_passport_target(r"C:\Users\admin\SecretProject", "myrepo") == "./myrepo"
    assert sanitize_passport_target("/Users/alice/RepoDNA", "repodna") == "./repodna"
    assert sanitize_passport_target("/home/bob/work", "work") == "./work"
    assert "github.com/org/repo" in sanitize_passport_target("https://ghp_token1234567890@github.com/org/repo", "repo")
    assert "ghp_token" not in sanitize_passport_target("https://ghp_token1234567890@github.com/org/repo", "repo")

    # 2. Mock analysis with dirty target display
    files = [
        FileNode(
            id="src/index.ts",
            name="index.ts",
            directory="src",
            extension=".ts",
            language="TypeScript",
            support_level=LanguageSupportLevel.FULL_AST,
            size_bytes=100,
            lines_total=10,
            lines_code=10,
            lines_comment=0,
            lines_blank=0,
        )
    ]
    analysis = AnalysisResult(
        analysis_id="priv_test",
        repo_name="private-app",
        source_type=SourceType.LOCAL,
        target_display=r"C:\Users\victim\workspace\private-app",
        analyzed_at=datetime.now(UTC),
        duration_ms=10,
        total_files=1,
        total_lines_code=10,
        total_lines_all=10,
        total_size_bytes=100,
        languages=[],
        files=files,
        edges=[],
        cycles=[],
        graph_metrics=GraphMetrics(total_nodes=1, total_edges=0),
        health_report=ArchitectureHealthReport(
            overall_score=100.0,
            grade="A",
            status="evaluated",
            confidence="high",
            methodology="Standard",
        ),
        git_insights=GitInsights(is_git_repo=False),
        transparency=TransparencyReport(ast_loc_coverage_pct=100.0),
    )

    # Generate passport with symbolic unresolvable ref
    passport = generate_repository_passport(analysis, git_revision="symbolic-unresolved-ref")
    assert passport.provenance_verified is False
    assert passport.revision_status == "unresolved_symbolic_ref"
    assert passport.metadata["target_display"] == "./private-app"

    # Validate privacy: default generated passport MUST be clean
    leaks = check_passport_privacy(passport)
    assert leaks == [], f"Generated passport leaked private paths: {leaks}"

    # Now simulate a passport with an injected leak and verify validator catches it
    dirty_passport = passport.model_copy(deep=True)
    dirty_passport.metadata["leaked_path"] = r"C:\Users\victim\AppData\Local\Temp"
    with pytest.raises(SecurityValidationError, match="Passport manifest violates privacy guardrails"):
        validate_passport_json(dirty_passport.model_dump_json())
