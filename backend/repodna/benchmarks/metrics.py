"""Mathematical metric implementations for Code Intelligence Retrieval Benchmarking.

Formulas:
- Hit@K = 1 if any expected item in returned[:K] else 0
- MRR = Mean( 1 / rank_first_relevant ) across positive queries
- Precision@K = |returned[:K] ∩ expected| / K
- Recall@K = |returned[:K] ∩ expected| / |expected|
- DCG@K = sum_{i=1}^K rel_i / log2(i + 1)
- IDCG@K = sum_{i=1}^{min(K, |expected|)} 1 / log2(i + 1)
- nDCG@K = DCG@K / IDCG@K (1.0 if both are 0)
- Abstention Rate (Negatives) = |negative queries with 0 results or abstained| / |negative queries|
- False Positive Rate (Negatives) = |negative queries returning confident match| / |negative queries|
"""

from __future__ import annotations

import math
from collections.abc import Sequence

from repodna.benchmarks.models import MethodMetricsSummary, SingleQueryEvaluation


def compute_hit_at_k(returned_files: Sequence[str], expected_files: Sequence[str], k: int) -> bool:
    """Returns True if at least one expected file is within the top-K returned files."""
    if not expected_files or k <= 0:
        return False
    expected_set = set(expected_files)
    return any(r in expected_set for r in returned_files[:k])


def compute_reciprocal_rank(returned_files: Sequence[str], expected_files: Sequence[str]) -> float:
    """Computes Reciprocal Rank (1/rank) of first relevant returned file."""
    if not expected_files:
        return 0.0
    expected_set = set(expected_files)
    for idx, f in enumerate(returned_files, 1):
        if f in expected_set:
            return 1.0 / idx
    return 0.0


def compute_precision_at_k(returned_files: Sequence[str], expected_files: Sequence[str], k: int) -> float:
    """Computes Precision@K: relevant returned in top K divided by K."""
    if k <= 0:
        return 0.0
    if not expected_files:
        return 0.0
    expected_set = set(expected_files)
    top_k = returned_files[:k]
    matched = sum(1 for f in top_k if f in expected_set)
    return matched / float(k)


def compute_recall_at_k(returned_files: Sequence[str], expected_files: Sequence[str], k: int) -> float:
    """Computes Recall@K: relevant returned in top K divided by total expected."""
    if not expected_files:
        return 0.0
    if k <= 0:
        return 0.0
    expected_set = set(expected_files)
    top_k = returned_files[:k]
    matched = sum(1 for f in top_k if f in expected_set)
    return matched / float(len(expected_files))


def compute_dcg_at_k(returned_files: Sequence[str], expected_files: Sequence[str], k: int) -> float:
    """Computes Discounted Cumulative Gain at rank K."""
    if k <= 0 or not expected_files:
        return 0.0
    expected_set = set(expected_files)
    dcg = 0.0
    for i, f in enumerate(returned_files[:k], 1):
        rel = 1.0 if f in expected_set else 0.0
        if rel > 0.0:
            dcg += rel / math.log2(i + 1)
    return dcg


def compute_idcg_at_k(expected_count: int, k: int) -> float:
    """Computes Ideal Discounted Cumulative Gain at rank K."""
    if k <= 0 or expected_count <= 0:
        return 0.0
    limit = min(expected_count, k)
    return sum(1.0 / math.log2(i + 1) for i in range(1, limit + 1))


def compute_ndcg_at_k(returned_files: Sequence[str], expected_files: Sequence[str], k: int) -> float:
    """Computes Normalized Discounted Cumulative Gain at rank K."""
    if not expected_files:
        return 0.0
    idcg = compute_idcg_at_k(len(expected_files), k)
    if idcg <= 0.0:
        return 0.0
    dcg = compute_dcg_at_k(returned_files, expected_files, k)
    return dcg / idcg


def compute_percentile(values: Sequence[float], percentile: float) -> float:
    """Computes percentile (0.0 to 100.0) from a sequence of values."""
    if not values:
        return 0.0
    sorted_vals = sorted(values)
    n = len(sorted_vals)
    if n == 1:
        return sorted_vals[0]
    rank = (percentile / 100.0) * (n - 1)
    low_idx = int(math.floor(rank))
    high_idx = int(math.ceil(rank))
    weight = rank - low_idx
    return round(sorted_vals[low_idx] * (1.0 - weight) + sorted_vals[high_idx] * weight, 2)


def aggregate_method_metrics(
    evaluations: Sequence[SingleQueryEvaluation],
    method_name: str,
    split_name: str = "all",
) -> MethodMetricsSummary:
    """Aggregates per-query evaluations into summary statistics.

    Negative queries are explicitly separated from positive retrieval metrics
    to avoid diluting Hit@K, MRR, Precision, Recall, and nDCG.
    """
    total = len(evaluations)
    if total == 0:
        return MethodMetricsSummary(
            method=method_name,
            split=split_name,
            total_queries=0,
            positive_queries=0,
            negative_queries=0,
            hit_at_1=0.0,
            hit_at_3=0.0,
            hit_at_5=0.0,
            mrr=0.0,
            precision_at_1=0.0,
            precision_at_3=0.0,
            precision_at_5=0.0,
            recall_at_1=0.0,
            recall_at_3=0.0,
            recall_at_5=0.0,
            ndcg_at_5=0.0,
            negative_abstention_rate=0.0,
            negative_false_positive_rate=0.0,
            p50_latency_ms=0.0,
            p95_latency_ms=0.0,
            mean_latency_ms=0.0,
        )

    pos_evals = [e for e in evaluations if not e.is_negative]
    neg_evals = [e for e in evaluations if e.is_negative]

    pos_count = len(pos_evals)
    neg_count = len(neg_evals)

    hit_1 = sum(1.0 for e in pos_evals if e.hit_at_1) / pos_count if pos_count else 0.0
    hit_3 = sum(1.0 for e in pos_evals if e.hit_at_3) / pos_count if pos_count else 0.0
    hit_5 = sum(1.0 for e in pos_evals if e.hit_at_5) / pos_count if pos_count else 0.0
    mrr = sum(e.reciprocal_rank for e in pos_evals) / pos_count if pos_count else 0.0

    p_1 = sum(e.precision_at_1 for e in pos_evals) / pos_count if pos_count else 0.0
    p_3 = sum(e.precision_at_3 for e in pos_evals) / pos_count if pos_count else 0.0
    p_5 = sum(e.precision_at_5 for e in pos_evals) / pos_count if pos_count else 0.0

    r_1 = sum(e.recall_at_1 for e in pos_evals) / pos_count if pos_count else 0.0
    r_3 = sum(e.recall_at_3 for e in pos_evals) / pos_count if pos_count else 0.0
    r_5 = sum(e.recall_at_5 for e in pos_evals) / pos_count if pos_count else 0.0

    ndcg_5 = sum(e.ndcg_at_5 for e in pos_evals) / pos_count if pos_count else 0.0

    abstention_rate = (
        sum(1.0 for e in neg_evals if e.abstained) / neg_count if neg_count else 1.0
    )
    fp_rate = (
        sum(1.0 for e in neg_evals if e.false_positive_on_negative) / neg_count
        if neg_count
        else 0.0
    )

    all_latencies = [e.latency_ms for e in evaluations]
    p50 = compute_percentile(all_latencies, 50.0)
    p95 = compute_percentile(all_latencies, 95.0)
    mean_lat = round(sum(all_latencies) / total, 2) if total else 0.0

    return MethodMetricsSummary(
        method=method_name,
        split=split_name,
        total_queries=total,
        positive_queries=pos_count,
        negative_queries=neg_count,
        hit_at_1=round(hit_1 * 100, 2),
        hit_at_3=round(hit_3 * 100, 2),
        hit_at_5=round(hit_5 * 100, 2),
        mrr=round(mrr, 4),
        precision_at_1=round(p_1, 4),
        precision_at_3=round(p_3, 4),
        precision_at_5=round(p_5, 4),
        recall_at_1=round(r_1, 4),
        recall_at_3=round(r_3, 4),
        recall_at_5=round(r_5, 4),
        ndcg_at_5=round(ndcg_5, 4),
        negative_abstention_rate=round(abstention_rate * 100, 2),
        negative_false_positive_rate=round(fp_rate * 100, 2),
        p50_latency_ms=p50,
        p95_latency_ms=p95,
        mean_latency_ms=mean_lat,
    )
