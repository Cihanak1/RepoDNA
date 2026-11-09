"""Integration tests for RepoDNA v0.4.0 CLI commands: contract, guardian, and passport."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path


def _run_cli(args: list[str]) -> subprocess.CompletedProcess[str]:
    cmd = [sys.executable, "-m", "repodna.cli.main", *args]
    return subprocess.run(cmd, capture_output=True, text=True, timeout=30.0)


def test_cli_contract_lifecycle() -> None:
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)

        # 1. contract init
        res_init = _run_cli(["contract", "init", str(tmp_path)])
        assert res_init.returncode == 0
        assert "Created starter Architecture Contract at:" in res_init.stdout
        contract_file = tmp_path / ".repodna" / "architecture.yml"
        assert contract_file.exists()

        # 2. contract validate
        res_val = _run_cli(["contract", "validate", str(contract_file)])
        assert res_val.returncode == 0
        assert "Valid Architecture Contract:" in res_val.stdout
        assert "Schema v1" in res_val.stdout

        # Also validate by directory path
        res_val_dir = _run_cli(["contract", "validate", str(tmp_path)])
        assert res_val_dir.returncode == 0

        # 3. contract check
        # Add a dummy python file
        dummy_file = tmp_path / "domain" / "order.py"
        dummy_file.parent.mkdir(parents=True, exist_ok=True)
        dummy_file.write_text("class Order:\n    pass\n", encoding="utf-8")

        res_check = _run_cli(["contract", "check", str(tmp_path), "--format", "json"])
        assert res_check.returncode == 0
        data = json.loads(res_check.stdout)
        assert data["contract_version"] == 1
        assert data["is_compliant"] is True
        assert data["verdict"] == "PASS"


def test_cli_passport_lifecycle() -> None:
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        dummy_file = tmp_path / "src" / "index.py"
        dummy_file.parent.mkdir(parents=True, exist_ok=True)
        dummy_file.write_text("def hello():\n    return 'world'\n", encoding="utf-8")

        # 1. passport generate default file
        res_gen = _run_cli(["passport", "generate", str(tmp_path)])
        assert res_gen.returncode == 0
        passport_file = tmp_path / ".repodna" / "passport.json"
        assert passport_file.exists()

        # 2. passport validate
        res_val = _run_cli(["passport", "validate", str(passport_file)])
        assert res_val.returncode == 0
        assert "Valid Repository Passport:" in res_val.stdout

        # 3. passport generate markdown stdout
        res_md = _run_cli(["passport", "generate", str(tmp_path), "--format", "markdown"])
        assert res_md.returncode == 0
        assert "# RepoDNA Repository Passport" in res_md.stdout
        assert "Architectural Vitals" in res_md.stdout


def test_cli_guardian_check_local_repo() -> None:
    # Run guardian check comparing HEAD against HEAD on current repo
    res = _run_cli(["guardian", "check", ".", "--base", "HEAD", "--head", "HEAD", "--format", "json"])
    assert res.returncode == 0
    data = json.loads(res.stdout)
    assert data["verdict"] == "PASS"
    assert data["risk_assessment"]["risk_level"] == "LOW"
    assert "summary_markdown" in data
