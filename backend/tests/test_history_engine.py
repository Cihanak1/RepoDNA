"""Comprehensive test suite for RepoDNA Historical Architecture Snapshot Engine.

Covers:
- HistoricalSnapshotEngine determinism and immutability
- Working tree isolation (zero modifications to active workspace)
- HistoricalCache integrity, corruption detection, and LRU eviction
- EvolutionDiffEngine deltas and rename accuracy
- HistoricalEvidenceProvider path boundary security and blob inspection
- Security hardening (flag injection, path traversal, shallow clone limitations)
- CLI integration (analyze, diff, snapshots, timeline)
"""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import pytest

from repodna.cli.main import main
from repodna.history.cache import HistoricalCache
from repodna.history.diff import EvolutionDiffEngine
from repodna.history.engine import HistoricalSnapshotEngine
from repodna.history.evidence import HistoricalEvidenceProvider
from repodna.history.models import (
    HistoricalEvidenceItem,
    HistoricalModuleSummary,
    HistoricalSnapshot,
)
from repodna.history.timeline import TimelineEngine
from repodna.security.validators import SecurityValidationError


@pytest.fixture
def test_repo(tmp_path: Path) -> Path:
    """Creates a minimal Git repository with multiple commits for testing."""
    repo = tmp_path / "repo"
    repo.mkdir()

    env = os.environ.copy()
    env["GIT_AUTHOR_NAME"] = "Test Author"
    env["GIT_AUTHOR_EMAIL"] = "test@example.com"
    env["GIT_COMMITTER_NAME"] = "Test Author"
    env["GIT_COMMITTER_EMAIL"] = "test@example.com"

    def run_git(*args: str) -> str:
        res = subprocess.run(
            ["git", "-C", str(repo), *args],
            capture_output=True,
            text=True,
            check=True,
            env=env,
        )
        return res.stdout.strip()

    run_git("init")
    run_git("config", "user.name", "Test Author")
    run_git("config", "user.email", "test@example.com")

    # Commit 1: Add a.py
    (repo / "a.py").write_text("def alpha():\n    return 42\n", encoding="utf-8")
    run_git("add", "a.py")
    run_git("commit", "-m", "commit 1: initial alpha")

    # Commit 2: Add b.py importing a
    (repo / "b.py").write_text("import a\ndef beta():\n    return a.alpha()\n", encoding="utf-8")
    run_git("add", "b.py")
    run_git("commit", "-m", "commit 2: add beta importing alpha")

    # Commit 3: Modify b.py and add c.py
    (repo / "c.py").write_text("import b\ndef gamma():\n    return b.beta()\n", encoding="utf-8")
    (repo / "b.py").write_text(
        "import a\ndef beta():\n    return a.alpha() + 1\n", encoding="utf-8"
    )
    run_git("add", "b.py", "c.py")
    run_git("commit", "-m", "commit 3: add gamma and update beta")

    return repo


class TestHistoricalSnapshotEngine:
    def test_snapshot_creation_and_determinism(self, test_repo: Path) -> None:
        engine = HistoricalSnapshotEngine(repo_path=test_repo)
        head_sha = engine.resolve_commit("HEAD")[0]

        # First cold run
        snap1 = engine.create_snapshot("HEAD", use_cache=False)
        assert snap1.commit_sha == head_sha
        assert snap1.total_files == 3
        assert len(snap1.modules) == 3
        assert len(snap1.dependencies) >= 2
        assert snap1.cache_hit is False

        # Second cold run should produce 100% deterministic output
        snap2 = engine.create_snapshot("HEAD", use_cache=False)
        assert snap1.commit_sha == snap2.commit_sha
        assert snap1.total_files == snap2.total_files
        assert snap1.total_lines_code == snap2.total_lines_code
        assert snap1.health.score == snap2.health.score
        assert [m.path for m in snap1.modules] == [m.path for m in snap2.modules]

    def test_working_tree_isolation(self, test_repo: Path, tmp_path: Path) -> None:
        """Verifies that creating historical snapshots leaves working tree untouched."""
        # Create uncommitted dirty file in working tree
        dirty_file = test_repo / "uncommitted.txt"
        dirty_file.write_text("dirty content", encoding="utf-8")

        status_before = subprocess.check_output(
            ["git", "-C", str(test_repo), "status", "--porcelain"], text=True
        )

        external_cache = tmp_path / "external_cache"
        engine = HistoricalSnapshotEngine(repo_path=test_repo, cache_dir=external_cache)
        # Analyze commit 1 (where b.py and c.py don't exist yet)
        c1_sha = subprocess.check_output(
            ["git", "-C", str(test_repo), "rev-list", "--max-parents=0", "HEAD"], text=True
        ).strip()

        snap = engine.create_snapshot(c1_sha, use_cache=False)
        assert snap.total_files == 1
        assert snap.modules[0].path == "a.py"

        # Check working tree after analysis
        status_after = subprocess.check_output(
            ["git", "-C", str(test_repo), "status", "--porcelain"], text=True
        )
        assert status_before == status_after
        assert dirty_file.exists()
        assert dirty_file.read_text(encoding="utf-8") == "dirty content"
        # b.py and c.py still exist in working tree
        assert (test_repo / "b.py").exists()
        assert (test_repo / "c.py").exists()

    def test_invalid_ref_flag_injection_rejection(self, test_repo: Path) -> None:
        engine = HistoricalSnapshotEngine(repo_path=test_repo)

        with pytest.raises(SecurityValidationError) as exc:
            engine.create_snapshot("--upload-pack=evil")
        assert exc.value.code == "INVALID_GIT_REF"

        with pytest.raises(SecurityValidationError) as exc:
            engine.create_snapshot("HEAD; rm -rf /")
        assert exc.value.code == "INVALID_GIT_REF"

    def test_lfs_pointer_detection(self, test_repo: Path) -> None:
        lfs_file = test_repo / "data.bin"
        lfs_file.write_text(
            "version https://git-lfs.github.com/spec/v1\noid sha256:4d7a283\nsize 12345\n",
            encoding="utf-8",
        )
        subprocess.run(["git", "-C", str(test_repo), "add", "data.bin"], check=True)
        subprocess.run(["git", "-C", str(test_repo), "commit", "-m", "add lfs pointer"], check=True)

        engine = HistoricalSnapshotEngine(repo_path=test_repo)
        snap = engine.create_snapshot("HEAD", use_cache=False)

        assert any("Git LFS pointer detected" in lim for lim in snap.limitations)


class TestHistoricalCache:
    def test_cache_put_get_and_corruption_detection(self, tmp_path: Path) -> None:
        cache_dir = tmp_path / "cache"
        cache = HistoricalCache(cache_dir=cache_dir, max_entries=5)

        snap = HistoricalSnapshot(
            commit_sha="a" * 40,
            repo_identity="test-repo",
            commit_timestamp="2026-11-11T00:00:00Z",
            analyzed_at="2026-11-11T00:00:00Z",
            total_files=10,
            total_lines_code=500,
        )

        key = HistoricalCache.generate_key("test-repo", "a" * 40)
        assert cache.put(key, snap) is True

        # Retrieve valid entry
        retrieved = cache.get(key)
        assert retrieved is not None
        assert retrieved.commit_sha == "a" * 40
        assert retrieved.cache_hit is True

        # Tamper with file on disk to simulate disk corruption
        entry_file = cache_dir / f"{key}.json"
        data = json.loads(entry_file.read_text(encoding="utf-8"))
        data["payload"]["total_lines_code"] = 99999  # Tamper payload
        entry_file.write_text(json.dumps(data), encoding="utf-8")

        # Corrupted entry should fail integrity verification and return None
        corrupted = cache.get(key)
        assert corrupted is None
        # Corrupted file should have been safely purged
        assert not entry_file.exists()

    def test_cache_lru_eviction(self, tmp_path: Path) -> None:
        cache_dir = tmp_path / "cache"
        # Bounded cache to 2 entries
        cache = HistoricalCache(cache_dir=cache_dir, max_entries=2)

        for i in range(3):
            sha = f"{i}" * 40
            snap = HistoricalSnapshot(
                commit_sha=sha,
                repo_identity="test-repo",
                commit_timestamp="2026-11-11T00:00:00Z",
                analyzed_at="2026-11-11T00:00:00Z",
            )
            key = HistoricalCache.generate_key("test-repo", sha)
            cache.put(key, snap)

        # Cache should have evicted oldest entry, keeping at most 2
        assert len(cache.list_keys()) <= 2


class TestEvolutionDiffEngine:
    def test_pairwise_diff(self, test_repo: Path) -> None:
        engine = HistoricalSnapshotEngine(repo_path=test_repo)
        commits = subprocess.check_output(
            ["git", "-C", str(test_repo), "log", "--reverse", "--format=%H"], text=True
        ).splitlines()

        c1_sha = commits[0]
        c2_sha = commits[1]

        snap1 = engine.create_snapshot(c1_sha)
        snap2 = engine.create_snapshot(c2_sha)

        diff = EvolutionDiffEngine.compare_snapshots(base=snap1, head=snap2, repo_path=test_repo)
        assert "b.py" in diff.module_changes.added
        assert len(diff.module_changes.removed) == 0
        assert len(diff.dependency_changes.added_edges) >= 1
        assert diff.base_commit_sha == c1_sha
        assert diff.head_commit_sha == c2_sha
        assert "MODULE CHANGES:" in diff.summary_text

    def test_candidate_rename_distinction(self) -> None:
        """Verifies that heuristic rename is marked as candidate and not verified."""
        base = HistoricalSnapshot(
            commit_sha="1" * 40,
            repo_identity="repo",
            commit_timestamp="2026-11-10T00:00:00Z",
            analyzed_at="2026-11-10T00:00:00Z",
            modules=[
                HistoricalModuleSummary(
                    path="src/old/utils.py", name="utils.py", language="Python", lines_code=50
                )
            ],
        )
        head = HistoricalSnapshot(
            commit_sha="2" * 40,
            repo_identity="repo",
            commit_timestamp="2026-11-11T00:00:00Z",
            analyzed_at="2026-11-11T00:00:00Z",
            modules=[
                HistoricalModuleSummary(
                    path="src/new/utils.py", name="utils.py", language="Python", lines_code=52
                )
            ],
        )

        diff = EvolutionDiffEngine.compare_snapshots(base=base, head=head, repo_path=None)
        assert len(diff.module_changes.renamed) == 1
        ren = diff.module_changes.renamed[0]
        assert ren.old_path == "src/old/utils.py"
        assert ren.new_path == "src/new/utils.py"
        assert ren.is_verified_by_git is False
        assert "Candidate heuristic match" in ren.reason


class TestHistoricalEvidenceProvider:
    def test_read_historical_file_and_verify_evidence(self, test_repo: Path) -> None:
        commits = subprocess.check_output(
            ["git", "-C", str(test_repo), "log", "--reverse", "--format=%H"], text=True
        ).splitlines()

        c1_sha = commits[0]
        provider = HistoricalEvidenceProvider(repo_path=test_repo)

        content = provider.read_historical_file(c1_sha, "a.py")
        assert "def alpha():" in content

        # File b.py does not exist at commit 1
        with pytest.raises(FileNotFoundError):
            provider.read_historical_file(c1_sha, "b.py")

        # Security check: path traversal
        with pytest.raises(SecurityValidationError):
            provider.read_historical_file(c1_sha, "../secret.txt")

    def test_verify_evidence_at_commit(self, test_repo: Path) -> None:
        commits = subprocess.check_output(
            ["git", "-C", str(test_repo), "log", "--reverse", "--format=%H"], text=True
        ).splitlines()
        c1_sha = commits[0]
        provider = HistoricalEvidenceProvider(repo_path=test_repo)

        item = HistoricalEvidenceItem(
            evidence_id="ev_001",
            commit_sha=c1_sha,
            file_path="a.py",
            line_start=1,
            line_end=2,
            evidence_type="declaration",
            code_snippet="def alpha():\n    return 42",
            content_hash="mock",
            support_level="verified",
            snapshot_identity=f"git:{c1_sha}",
        )

        # Set real content hash
        from repodna.brain.evidence import extract_evidence_snippet

        _, real_hash = extract_evidence_snippet("def alpha():\n    return 42\n", 1, 2)
        item.content_hash = real_hash

        is_fresh, reason, _ = provider.verify_evidence_at_commit(item)
        assert is_fresh is True
        assert reason.value == "fresh"


class TestTimelineEngine:
    def test_build_timeline(self, test_repo: Path) -> None:
        engine = HistoricalSnapshotEngine(repo_path=test_repo)
        timeline = TimelineEngine(engine=engine)

        res = timeline.build_timeline(limit=5)
        assert res.total_commits == 3
        assert len(res.entries) == 3
        assert res.entries[0].modules_count == 1
        assert res.entries[-1].modules_count == 3
        assert "RepoDNA Architecture Timeline" in res.summary_text


class TestHistoryCLI:
    def test_cli_history_analyze_and_snapshots(self, test_repo: Path) -> None:
        exit_code = main(
            ["history", "analyze", str(test_repo), "--rev", "HEAD", "--format", "json"]
        )
        assert exit_code == 0

        exit_code_snap = main(["history", "snapshots", str(test_repo), "--format", "json"])
        assert exit_code_snap == 0

    def test_cli_history_diff(self, test_repo: Path) -> None:
        commits = subprocess.check_output(
            ["git", "-C", str(test_repo), "log", "--reverse", "--format=%H"], text=True
        ).splitlines()
        exit_code = main(
            [
                "history",
                "diff",
                str(test_repo),
                "--base",
                commits[0],
                "--head",
                commits[1],
                "--format",
                "json",
            ]
        )
        assert exit_code == 0

    def test_cli_history_timeline(self, test_repo: Path) -> None:
        exit_code = main(
            ["history", "timeline", str(test_repo), "--limit", "5", "--format", "json"]
        )
        assert exit_code == 0
