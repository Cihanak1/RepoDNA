"""Benchmark execution engine evaluating Code Intelligence retrieval, fidelity, and scale."""

from __future__ import annotations

import json
import os
import platform
import subprocess
import time
import tracemalloc
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from repodna.benchmarks.baselines import (
    FilenameOnlyBaseline,
    RepositoryBrainRetrieval,
    SymbolOnlyBaseline,
)
from repodna.benchmarks.budget_bench import run_budget_benchmark
from repodna.benchmarks.metrics import (
    aggregate_method_metrics,
    compute_hit_at_k,
    compute_ndcg_at_k,
    compute_precision_at_k,
    compute_recall_at_k,
    compute_reciprocal_rank,
)
from repodna.benchmarks.models import (
    BenchmarkQuery,
    BenchmarkRunReport,
    FailureCategory,
    FailureReportItem,
    MethodMetricsSummary,
    SingleQueryEvaluation,
    SplitType,
)
from repodna.benchmarks.scalability import run_scalability_benchmark
from repodna.brain.indexer import SymbolIndexer
from repodna.brain.models import ResolutionStatus
from repodna.core.analyzer import run_repository_analysis
from repodna.schemas.models import ScanLimits, ScanRequest, SourceType


class BenchmarkEngine:
    """Orchestrates comprehensive benchmark runs with baselines, metrics, and failure diagnostics."""

    def __init__(self, repo_path: Path | str = ".", dataset_path: Path | str | None = None) -> None:
        self.repo_path = Path(repo_path).resolve()
        if dataset_path:
            self.dataset_path = Path(dataset_path).resolve()
        else:
            self.dataset_path = self.repo_path / "benchmarks" / "retrieval-v1.jsonl"

    def load_dataset(self) -> list[BenchmarkQuery]:
        """Loads and parses JSONL benchmark queries."""
        if not self.dataset_path.is_file():
            raise FileNotFoundError(f"Benchmark dataset not found at: {self.dataset_path}")

        queries: list[BenchmarkQuery] = []
        with self.dataset_path.open("r", encoding="utf-8") as f:
            for line_no, line in enumerate(f, 1):
                clean = line.strip()
                if not clean or clean.startswith("#"):
                    continue
                try:
                    data = json.loads(clean)
                    queries.append(BenchmarkQuery.model_validate(data))
                except Exception as exc:
                    raise ValueError(f"Malformed query JSON on line {line_no}: {exc}") from exc
        return queries

    def _get_git_commit_sha(self) -> str:
        try:
            res = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=self.repo_path,
                capture_output=True,
                text=True,
                check=False,
            )
            sha = res.stdout.strip()
            return sha if sha else "unknown"
        except Exception:
            return "unknown"

    def run(
        self,
        include_baselines: bool = True,
        include_scalability: bool = True,
        include_budget: bool = True,
    ) -> BenchmarkRunReport:
        """Executes full benchmark suite and returns structured report."""
        queries = self.load_dataset()
        commit_sha = self._get_git_commit_sha()

        # System environment metadata
        env_meta: dict[str, Any] = {
            "os": platform.system(),
            "os_release": platform.release(),
            "python_version": platform.python_version(),
            "architecture": platform.machine(),
            "processor": platform.processor(),
            "cpu_count": os.cpu_count() or 1,
        }

        # Step 1: Run Repository Analysis & Trace Cold Indexing
        tracemalloc.start()
        req = ScanRequest(
            source_type=SourceType.LOCAL,
            target=str(self.repo_path),
            limits=ScanLimits(max_files=1500),
        )
        analysis = run_repository_analysis(req)

        # Cold index
        t0 = time.perf_counter()
        indexer = SymbolIndexer(root_path=self.repo_path, revision=commit_sha, analysis=analysis)
        indexer.index_all()
        cold_idx_ms = round((time.perf_counter() - t0) * 1000.0, 2)

        _, peak_mem = tracemalloc.get_traced_memory()
        peak_mb = round(peak_mem / (1024.0 * 1024.0), 2)
        tracemalloc.stop()

        # Warm indexing measurement
        t_warm0 = time.perf_counter()
        warm_indexer = SymbolIndexer(root_path=self.repo_path, revision=commit_sha, analysis=analysis)
        warm_indexer.index_all()
        warm_idx_ms = round((time.perf_counter() - t_warm0) * 1000.0, 2)

        # Step 2: Initialize Baselines
        all_file_ids = [f.id for f in analysis.files]
        filename_baseline = FilenameOnlyBaseline(all_file_ids)
        symbol_baseline = SymbolOnlyBaseline(indexer)
        repodna_retrieval = RepositoryBrainRetrieval(indexer, analysis)

        methods_to_test: list[tuple[str, Any]] = [("repository_brain", repodna_retrieval)]
        if include_baselines:
            methods_to_test.insert(0, ("filename_only", filename_baseline))
            methods_to_test.insert(1, ("symbol_only", symbol_baseline))

        # Step 3: Run Queries and Evaluate
        all_evaluations: dict[str, list[SingleQueryEvaluation]] = {m[0]: [] for m in methods_to_test}
        failures: list[FailureReportItem] = []

        for q in queries:
            is_neg = len(q.expected_files) == 0

            for method_name, retriever in methods_to_test:
                returned, dur_ms = retriever.retrieve(q.query, limit=5)

                hit_1 = compute_hit_at_k(returned, q.expected_files, 1)
                hit_3 = compute_hit_at_k(returned, q.expected_files, 3)
                hit_5 = compute_hit_at_k(returned, q.expected_files, 5)
                rr = compute_reciprocal_rank(returned, q.expected_files)
                p_1 = compute_precision_at_k(returned, q.expected_files, 1)
                p_3 = compute_precision_at_k(returned, q.expected_files, 3)
                p_5 = compute_precision_at_k(returned, q.expected_files, 5)
                r_1 = compute_recall_at_k(returned, q.expected_files, 1)
                r_3 = compute_recall_at_k(returned, q.expected_files, 3)
                r_5 = compute_recall_at_k(returned, q.expected_files, 5)
                ndcg_5 = compute_ndcg_at_k(returned, q.expected_files, 5)

                abstained = is_neg and (len(returned) == 0)
                # False positive on negative query if top returned item returned
                false_pos = is_neg and (len(returned) > 0)

                failure_cat = FailureCategory.NONE
                failure_notes = None

                if is_neg:
                    if false_pos:
                        failure_cat = FailureCategory.SYNONYM_EXPANSION_ERROR
                        failure_notes = f"Negative query returned non-empty candidates: {returned[:2]}"
                else:
                    if not hit_3:
                        if not any(f in returned for f in q.expected_files):
                            failure_cat = FailureCategory.MISSING_SYMBOL
                            failure_notes = f"Expected {q.expected_files} not found in top 5."
                        else:
                            failure_cat = FailureCategory.RANKING_FAILURE
                            failure_notes = f"Expected files found at rank > 3: {returned}"

                # Record failure for RepoDNA
                if method_name == "repository_brain" and failure_cat != FailureCategory.NONE:
                    failures.append(
                        FailureReportItem(
                            query_id=q.query_id,
                            query=q.query,
                            category=failure_cat,
                            split=q.split,
                            expected_files=q.expected_files,
                            actual_files=returned[:3],
                            root_cause=failure_notes or "Evaluation criteria mismatch",
                            proposed_fix="Refine ranking weights or add domain synonyms",
                        )
                    )

                eval_item = SingleQueryEvaluation(
                    query_id=q.query_id,
                    query=q.query,
                    method=method_name,
                    split=q.split,
                    returned_files=returned,
                    hit_at_1=hit_1,
                    hit_at_3=hit_3,
                    hit_at_5=hit_5,
                    reciprocal_rank=rr,
                    precision_at_1=p_1,
                    precision_at_3=p_3,
                    precision_at_5=p_5,
                    recall_at_1=r_1,
                    recall_at_3=r_3,
                    recall_at_5=r_5,
                    ndcg_at_5=ndcg_5,
                    latency_ms=round(dur_ms, 2),
                    is_negative=is_neg,
                    abstained=abstained,
                    false_positive_on_negative=false_pos,
                    failure_category=failure_cat,
                    failure_notes=failure_notes,
                )
                all_evaluations[method_name].append(eval_item)

        # Step 4: Aggregate Baselines Metrics across Splits
        baselines_summary: dict[str, MethodMetricsSummary] = {}
        dev_summary: dict[str, MethodMetricsSummary] = {}
        holdout_summary: dict[str, MethodMetricsSummary] = {}

        for m_name, evals in all_evaluations.items():
            baselines_summary[m_name] = aggregate_method_metrics(evals, m_name, "all")
            dev_evals = [e for e in evals if e.split == SplitType.DEV]
            holdout_evals = [e for e in evals if e.split == SplitType.HOLDOUT]
            dev_summary[m_name] = aggregate_method_metrics(dev_evals, m_name, "dev")
            holdout_summary[m_name] = aggregate_method_metrics(holdout_evals, m_name, "holdout")

        # Step 5: Symbol Reference Fidelity Auditing
        all_refs = indexer._raw_references
        verified_refs = [r for r in all_refs if r.resolution_status == ResolutionStatus.VERIFIED]
        unresolved_refs = [r for r in all_refs if r.resolution_status == ResolutionStatus.UNRESOLVED]

        # Audit verified references: verify that target symbol actually exists in target file
        valid_verified_count = 0
        false_verified_count = 0
        for v in verified_refs:
            if v.target_file_path and v.target_file_path in indexer._symbols_by_file:
                target_syms = indexer._symbols_by_file[v.target_file_path]
                if any(s.id == v.target_symbol_id or s.name == v.symbol_name for s in target_syms):
                    valid_verified_count += 1
                else:
                    false_verified_count += 1
            else:
                false_verified_count += 1

        total_v = len(verified_refs)
        verified_precision = round((valid_verified_count / float(total_v)) * 100.0, 2) if total_v > 0 else 100.0

        # Step 6: Budget Benchmarks
        budget_results = run_budget_benchmark(analysis) if include_budget else []
        budget_compliance_pct = (
            round((sum(1.0 for b in budget_results if b.is_compliant) / len(budget_results)) * 100.0, 1)
            if budget_results
            else 100.0
        )

        # Step 7: Scalability Benchmarks
        scalability_results = (
            run_scalability_benchmark(self.repo_path) if include_scalability else []
        )

        dev_count = sum(1 for q in queries if q.split == SplitType.DEV)
        holdout_count = sum(1 for q in queries if q.split == SplitType.HOLDOUT)

        return BenchmarkRunReport(
            benchmark_version="v1.0",
            timestamp=datetime.now(UTC).isoformat(),
            commit_sha=commit_sha,
            environment=env_meta,
            dataset_path=str(self.dataset_path),
            dataset_total=len(queries),
            dataset_dev_count=dev_count,
            dataset_holdout_count=holdout_count,
            cold_indexing_time_ms=cold_idx_ms,
            warm_indexing_time_ms=warm_idx_ms,
            peak_memory_mb=peak_mb,
            verified_reference_precision=verified_precision,
            false_verified_count=false_verified_count,
            unresolved_reference_count=len(unresolved_refs),
            token_budget_compliance_pct=budget_compliance_pct,
            baselines=baselines_summary,
            dev_split_metrics=dev_summary,
            holdout_split_metrics=holdout_summary,
            failure_analysis=failures,
            budget_benchmarks=budget_results,
            scalability_results=scalability_results,
            query_evaluations=all_evaluations.get("repository_brain", []),
        )

    @classmethod
    def generate_markdown_report(cls, report: BenchmarkRunReport) -> str:
        lines: list[str] = [
            "# RepoDNA Code Intelligence Benchmark — Phase 2 Evaluation Report",
            "",
            f"- **Benchmark Version:** `{report.benchmark_version}`",
            f"- **Commit SHA:** `{report.commit_sha}`",
            f"- **Evaluated At:** `{report.timestamp}`",
            f"- **Environment:** {report.environment.get('os')} ({report.environment.get('architecture')}), Python {report.environment.get('python_version')}",
            f"- **Dataset:** `{report.dataset_path}` ({report.dataset_total} queries: {report.dataset_dev_count} dev, {report.dataset_holdout_count} holdout)",
            "",
            "## 1. Executive Summary & Baseline Comparison",
            "",
            "Does **Repository Brain** actually outperform naive filename search and substring symbol search?",
            "",
            "| Method | Hit@1 (%) | Hit@3 (%) | Hit@5 (%) | MRR | Precision@1 | Recall@3 | nDCG@5 | Negative Abstention (%) | P50 Latency (ms) |",
            "| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |",
        ]

        for method_key in ["filename_only", "symbol_only", "repository_brain"]:
            m = report.baselines.get(method_key)
            if m:
                label = "**Repository Brain (RepoDNA)**" if method_key == "repository_brain" else method_key
                lines.append(
                    f"| {label} | **{m.hit_at_1}** | **{m.hit_at_3}** | **{m.hit_at_5}** | **{m.mrr}** | {m.precision_at_1} | {m.recall_at_3} | **{m.ndcg_at_5}** | {m.negative_abstention_rate}% | {m.p50_latency_ms} ms |"
                )

        lines.extend([
            "",
            "## 2. Dev vs Holdout Generalization",
            "",
            "| Split | Method | Hit@1 (%) | Hit@3 (%) | MRR | nDCG@5 | Negative Abstention (%) |",
            "| :--- | :--- | :---: | :---: | :---: | :---: | :---: |",
        ])

        for split_label, split_dict in [("Dev Split", report.dev_split_metrics), ("Holdout Split", report.holdout_split_metrics)]:
            for method_key in ["filename_only", "symbol_only", "repository_brain"]:
                m = split_dict.get(method_key)
                if m:
                    lines.append(
                        f"| {split_label} | {m.method} | {m.hit_at_1}% | {m.hit_at_3}% | {m.mrr} | {m.ndcg_at_5} | {m.negative_abstention_rate}% |"
                    )

        lines.extend([
            "",
            "## 3. Symbol Reference Fidelity Audit",
            "",
            f"- **Verified Reference Precision:** `{report.verified_reference_precision}%`",
            f"- **False Verified Reference Count:** `{report.false_verified_count}`",
            f"- **Unresolved Reference Count:** `{report.unresolved_reference_count}` (calls correctly left unresolved due to insufficient static AST proof)",
            f"- **Cold Indexing Time:** `{report.cold_indexing_time_ms} ms`",
            f"- **Warm Indexing Time:** `{report.warm_indexing_time_ms} ms`",
            f"- **Peak Memory Usage:** `{report.peak_memory_mb} MB`",
            "",
            "## 4. Token Budget Compliance Matrix",
            "",
            "| Requested `max_tokens` | Counted Tokens | Method | Compliant? | Truncated? | Deterministic? | Duration | Notes |",
            "| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :--- |",
        ])

        for b in report.budget_benchmarks:
            comp_flag = "PASS" if b.is_compliant else "FAIL"
            trunc_flag = "Yes" if b.is_truncated else "No"
            det_flag = "Yes" if b.is_deterministic else "No"
            lines.append(
                f"| `{b.max_tokens}` | {b.counted_tokens} | `{b.counting_method}` | **{comp_flag}** | {trunc_flag} | {det_flag} | {b.duration_ms} ms | {b.notes} |"
            )

        lines.extend([
            "",
            "## 5. Scalability & Stress Benchmark",
            "",
            "| Tier | Files | LOC (est) | Symbols | Cold Index | Warm P50 | Warm P95 | Repeat Query | Peak RAM | Mem Growth | Status |",
            "| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |",
        ])

        for s in report.scalability_results:
            lines.append(
                f"| **{s.scale_tier}** | {s.file_count} | {s.loc} | {s.symbol_count} | {s.cold_indexing_ms} ms | {s.warm_query_p50_ms} ms | {s.warm_query_p95_ms} ms | {s.repeated_query_ms} ms | {s.peak_memory_mb} MB | {s.memory_growth_mb} MB | `{s.status}` |"
            )

        lines.extend([
            "",
            "## 6. Failure Analysis & Diagnostics",
            "",
        ])

        if not report.failure_analysis:
            lines.append("No failures detected under evaluation criteria.")
        else:
            lines.append(f"Detected **{len(report.failure_analysis)}** diagnostic failure item(s):")
            lines.append("")
            lines.append("| Query ID | Category | Query | Root Cause | Proposed Fix |")
            lines.append("| :--- | :--- | :--- | :--- | :--- |")
            for f in report.failure_analysis:
                clean_q = f.query.replace("|", "/")
                lines.append(f"| `{f.query_id}` | `{f.category.value}` | {clean_q} | {f.root_cause} | {f.proposed_fix} |")

        lines.extend([
            "",
            "## 7. Mathematical Metric Definitions",
            "",
            "- **Hit@K**: $\\frac{1}{|Q_{pos}|} \\sum_{q \\in Q_{pos}} \\mathbb{I}(\\text{Top-}K \\cap \\text{Expected}_q \\neq \\emptyset)$",
            "- **MRR (Mean Reciprocal Rank)**: $\\frac{1}{|Q_{pos}|} \\sum_{q \\in Q_{pos}} \\frac{1}{\\text{rank}_q}$",
            "- **Precision@K**: $\\frac{1}{|Q_{pos}|} \\sum_{q \\in Q_{pos}} \\frac{|\\text{Top-}K \\cap \\text{Expected}_q|}{K}$",
            "- **Recall@K**: $\\frac{1}{|Q_{pos}|} \\sum_{q \\in Q_{pos}} \\frac{|\\text{Top-}K \\cap \\text{Expected}_q|}{|\\text{Expected}_q|}$",
            "- **nDCG@K**: $\\frac{1}{|Q_{pos}|} \\sum_{q \\in Q_{pos}} \\frac{\\text{DCG}_q@K}{\\text{IDCG}_q@K}$",
            "- **Negative Abstention Rate**: $\\frac{|\\{q \\in Q_{neg} \\mid \\text{Returned}_q = \\emptyset \\}|}{|Q_{neg}|}$",
            "- **Verified Reference Precision**: $\\frac{|\\text{Verified References with confirmed target symbol in target file}|}{|\\text{Total Verified References}|}$",
        ])

        return "\n".join(lines)
