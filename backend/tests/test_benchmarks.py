"""Unit and integration tests for RepoDNA Code Intelligence Benchmark Suite."""

from __future__ import annotations

from pathlib import Path

from repodna.benchmarks.baselines import FilenameOnlyBaseline, SymbolOnlyBaseline
from repodna.benchmarks.budget_bench import _strip_dynamic_timestamps, run_budget_benchmark
from repodna.benchmarks.engine import BenchmarkEngine
from repodna.benchmarks.metrics import (
    aggregate_method_metrics,
    compute_hit_at_k,
    compute_idcg_at_k,
    compute_ndcg_at_k,
    compute_percentile,
    compute_precision_at_k,
    compute_recall_at_k,
    compute_reciprocal_rank,
)
from repodna.benchmarks.models import (
    QueryCategory,
    SingleQueryEvaluation,
    SplitType,
)
from repodna.brain.indexer import SymbolIndexer
from repodna.core.analyzer import run_repository_analysis
from repodna.schemas.models import ScanLimits, ScanRequest, SourceType


def test_metric_hit_at_k():
    returned = ["a.py", "b.py", "c.py"]
    expected = ["b.py"]
    assert not compute_hit_at_k(returned, expected, 1)
    assert compute_hit_at_k(returned, expected, 2)
    assert compute_hit_at_k(returned, expected, 3)
    assert not compute_hit_at_k(returned, [], 5)
    assert not compute_hit_at_k(returned, expected, 0)


def test_metric_reciprocal_rank():
    returned = ["a.py", "b.py", "c.py"]
    assert compute_reciprocal_rank(returned, ["a.py"]) == 1.0
    assert compute_reciprocal_rank(returned, ["b.py"]) == 0.5
    assert round(compute_reciprocal_rank(returned, ["c.py"]), 4) == 0.3333
    assert compute_reciprocal_rank(returned, ["nonexistent.py"]) == 0.0
    assert compute_reciprocal_rank(returned, []) == 0.0


def test_metric_precision_and_recall():
    returned = ["a.py", "b.py", "c.py", "d.py"]
    expected = ["b.py", "c.py", "e.py"]

    # Precision@2: in top 2 (a, b), only b is expected -> 1/2 = 0.5
    assert compute_precision_at_k(returned, expected, 2) == 0.5
    # Precision@3: in top 3 (a, b, c), b and c expected -> 2/3
    assert round(compute_precision_at_k(returned, expected, 3), 4) == 0.6667
    # Recall@2: in top 2 (a, b), b is matched out of 3 expected -> 1/3
    assert round(compute_recall_at_k(returned, expected, 2), 4) == 0.3333
    # Recall@3: in top 3 (a, b, c), b and c matched out of 3 expected -> 2/3
    assert round(compute_recall_at_k(returned, expected, 3), 4) == 0.6667


def test_metric_ndcg():
    returned = ["a.py", "b.py", "c.py"]
    expected = ["a.py", "b.py"]
    # Perfect ranking: both expected in top 2 in order
    assert compute_ndcg_at_k(returned, expected, 3) == 1.0

    # Inverted ranking
    inverted_returned = ["x.py", "a.py", "b.py"]
    ndcg_inverted = compute_ndcg_at_k(inverted_returned, expected, 3)
    assert 0.0 < ndcg_inverted < 1.0

    # No matches
    assert compute_ndcg_at_k(["x.py", "y.py"], expected, 2) == 0.0
    assert compute_idcg_at_k(0, 3) == 0.0


def test_metric_percentile():
    vals = [10.0, 20.0, 30.0, 40.0, 50.0]
    assert compute_percentile(vals, 50.0) == 30.0
    assert compute_percentile(vals, 0.0) == 10.0
    assert compute_percentile(vals, 100.0) == 50.0
    assert compute_percentile([], 50.0) == 0.0


def test_aggregate_method_metrics_separates_negatives():
    evals = [
        SingleQueryEvaluation(
            query_id="Q1",
            query="find auth",
            method="test_method",
            split=SplitType.DEV,
            returned_files=["auth.py"],
            hit_at_1=True,
            hit_at_3=True,
            hit_at_5=True,
            reciprocal_rank=1.0,
            precision_at_1=1.0,
            precision_at_3=0.3333,
            precision_at_5=0.2,
            recall_at_1=1.0,
            recall_at_3=1.0,
            recall_at_5=1.0,
            ndcg_at_5=1.0,
            latency_ms=10.0,
            is_negative=False,
            abstained=False,
            false_positive_on_negative=False,
        ),
        SingleQueryEvaluation(
            query_id="Q2_neg",
            query="find nonexistent feature",
            method="test_method",
            split=SplitType.DEV,
            returned_files=[],
            hit_at_1=False,
            hit_at_3=False,
            hit_at_5=False,
            reciprocal_rank=0.0,
            precision_at_1=0.0,
            precision_at_3=0.0,
            precision_at_5=0.0,
            recall_at_1=0.0,
            recall_at_3=0.0,
            recall_at_5=0.0,
            ndcg_at_5=0.0,
            latency_ms=5.0,
            is_negative=True,
            abstained=True,
            false_positive_on_negative=False,
        ),
    ]

    summary = aggregate_method_metrics(evals, "test_method", "dev")
    assert summary.total_queries == 2
    assert summary.positive_queries == 1
    assert summary.negative_queries == 1
    # Negative query should NOT dilute positive Hit@1 (must be 100%, not 50%!)
    assert summary.hit_at_1 == 100.0
    assert summary.mrr == 1.0
    # Abstention on negative query must be 100%
    assert summary.negative_abstention_rate == 100.0
    assert summary.negative_false_positive_rate == 0.0


def test_dataset_loading_and_validation():
    dataset_path = Path("benchmarks/retrieval-v1.jsonl").resolve()
    assert dataset_path.is_file()

    engine = BenchmarkEngine(repo_path=".", dataset_path=dataset_path)
    queries = engine.load_dataset()
    assert len(queries) >= 50

    # Verify query structure
    categories = {q.query_category for q in queries}
    assert QueryCategory.NEGATIVE in categories
    assert QueryCategory.FEATURE_LOCATION in categories
    assert QueryCategory.SYMBOL_LOOKUP in categories
    assert QueryCategory.AMBIGUOUS in categories

    splits = {q.split for q in queries}
    assert SplitType.DEV in splits
    assert SplitType.HOLDOUT in splits

    # Negative queries have empty expected_files
    negatives = [q for q in queries if q.query_category == QueryCategory.NEGATIVE]
    assert len(negatives) >= 5
    for neg in negatives:
        assert len(neg.expected_files) == 0


def test_baselines_execution(tmp_path: Path):
    (tmp_path / "auth_service.py").write_text(
        "class AuthService:\n    def authenticate(self): return True\n",
        encoding="utf-8",
    )
    (tmp_path / "billing_manager.py").write_text(
        "class BillingManager:\n    def charge(self): return True\n",
        encoding="utf-8",
    )

    all_files = ["auth_service.py", "billing_manager.py"]
    fn_baseline = FilenameOnlyBaseline(all_files)
    ret_files, dur = fn_baseline.retrieve("Where is authentication service?", limit=2)
    assert len(ret_files) >= 1
    assert "auth_service.py" in ret_files
    assert dur >= 0.0

    indexer = SymbolIndexer(root_path=tmp_path, revision="test_base")
    indexer.index_all()

    sym_baseline = SymbolOnlyBaseline(indexer)
    ret_sym_files, dur_sym = sym_baseline.retrieve("AuthService", limit=2)
    assert len(ret_sym_files) >= 1
    assert "auth_service.py" in ret_sym_files


def test_strip_dynamic_timestamps_normalizer():
    raw_md = "Generated at 2026-11-10T02:45:00Z by RepoDNA."
    normalized = _strip_dynamic_timestamps(raw_md)
    assert "TIMESTAMP_NORMALIZED" in normalized
    assert "2026-11-10" not in normalized


def test_budget_benchmark_matrix():
    req = ScanRequest(
        source_type=SourceType.LOCAL,
        target=".",
        limits=ScanLimits(max_files=15),
    )
    analysis = run_repository_analysis(req)
    results = run_budget_benchmark(analysis)

    assert len(results) == 6
    budgets = [r.max_tokens for r in results]
    assert budgets == [0, 10, 25, 60, 500, 2000]

    for r in results:
        assert r.is_deterministic
        assert r.duration_ms >= 0.0
        assert r.iterations <= 100


def test_budget_compliance_semantics_separation():
    """P0: Explicitly verify separation of termination_success, budget_compliant, and metadata_overflow."""
    req = ScanRequest(source_type=SourceType.LOCAL, target=".", limits=ScanLimits(max_files=15))
    analysis = run_repository_analysis(req)
    results = run_budget_benchmark(analysis, include_minimal=True)

    by_budget_std = {r.max_tokens: r for r in results if r.contract == "standard"}
    by_budget_min = {r.max_tokens: r for r in results if r.contract == "minimal_response"}

    # 10 tokens in standard mode: metadata overflow
    r10 = by_budget_std[10]
    assert r10.termination_success is True
    assert r10.budget_compliant is False
    assert r10.metadata_overflow is True
    assert r10.truncated is True
    assert r10.estimated_token_count > 10
    assert "heuristic" in r10.tokenizer_method
    assert "estimated" in r10.tokenizer_method

    # 25 tokens in standard mode: metadata overflow
    r25 = by_budget_std[25]
    assert r25.termination_success is True
    assert r25.budget_compliant is False
    assert r25.metadata_overflow is True

    # 0 tokens in standard mode: compliant with zero payload
    r0 = by_budget_std[0]
    assert r0.termination_success is True
    assert r0.budget_compliant is True
    assert r0.metadata_overflow is False
    assert r0.estimated_token_count == 0

    # 500 tokens in standard mode: fully compliant
    r500 = by_budget_std[500]
    assert r500.termination_success is True
    assert r500.budget_compliant is True
    assert r500.metadata_overflow is False

    # Minimal-response contract: 10 and 25 tokens strictly compliant
    r10_min = by_budget_min[10]
    assert r10_min.termination_success is True
    assert r10_min.budget_compliant is True
    assert r10_min.metadata_overflow is False
    assert r10_min.estimated_token_count <= 10

    r25_min = by_budget_min[25]
    assert r25_min.termination_success is True
    assert r25_min.budget_compliant is True
    assert r25_min.metadata_overflow is False
    assert r25_min.estimated_token_count <= 25


def test_dataset_ground_truth_audit_integrity():
    """Verify ground-truth dataset integrity: files exist and symbols are verified."""
    import hashlib
    import json
    from pathlib import Path

    dataset_path = Path("benchmarks/retrieval-v1.jsonl")
    assert dataset_path.is_file()

    content_bytes = dataset_path.read_bytes()
    dataset_hash = hashlib.sha256(content_bytes).hexdigest()
    assert dataset_hash == "930247e96295c6bb2344b138b82cbed7156cc640b2009f63e818698d5eb2f25a"

    queries = [json.loads(line) for line in dataset_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert len(queries) == 55

    for q in queries:
        for fp in q["expected_files"]:
            assert Path(fp).exists(), f"Query {q['query_id']} references missing file {fp}"
