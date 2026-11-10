"""Ablation harness measuring individual retrieval factor contributions on Dev split."""
import json
import time
from pathlib import Path
from typing import Any

from repodna.benchmarks.metrics import (
    aggregate_method_metrics,
    compute_hit_at_k,
    compute_ndcg_at_k,
    compute_precision_at_k,
    compute_recall_at_k,
    compute_reciprocal_rank,
)
from repodna.benchmarks.models import BenchmarkQuery, SingleQueryEvaluation
from repodna.brain.indexer import SymbolIndexer
from repodna.brain.models import CodeSearchResult, SearchResponse
from repodna.brain.retrieval import (
    GENERIC_STRUCTURAL_WORDS,
    SYNONYM_MAP,
    SmartRetrievalEngine,
    _classify_query_intent,
    _split_identifier_tokens,
)
from repodna.core.analyzer import run_repository_analysis
from repodna.schemas.models import LanguageSupportLevel, ScanLimits, ScanRequest, SourceType

# Load dataset Dev split
with open("benchmarks/retrieval-v1.jsonl", "r", encoding="utf-8") as f:
    all_queries = [BenchmarkQuery.model_validate(json.loads(l)) for l in f if l.strip()]

dev_queries = [q for q in all_queries if q.split == "dev"]
print(f"Loaded {len(dev_queries)} Dev queries for ablation testing.")

# Initialize indexing
req = ScanRequest(source_type=SourceType.LOCAL, target=".", limits=ScanLimits(max_files=1500))
analysis = run_repository_analysis(req)
indexer = SymbolIndexer(root_path=Path("."), revision="ABLATION_REV", analysis=analysis)
indexer.index_all()

class ConfigurableRetrievalEngine:
    """Configurable retrieval engine for single-factor ablation testing."""

    def __init__(
        self,
        indexer: SymbolIndexer,
        analysis: Any,
        enable_exact_filename_stem: bool = False,
        enable_symbol_boost_and_diminishing: bool = False,
        enable_synonym_calibration: bool = False,
        enable_negative_abstention: bool = False,
        abstention_threshold: float = 16.0,
    ) -> None:
        self.indexer = indexer
        self.analysis = analysis
        self._files_by_id = {f.id: f for f in analysis.files}
        self._content_cache: dict[str, str] = {}
        self.enable_exact_filename_stem = enable_exact_filename_stem
        self.enable_symbol_boost_and_diminishing = enable_symbol_boost_and_diminishing
        self.enable_synonym_calibration = enable_synonym_calibration
        self.enable_negative_abstention = enable_negative_abstention
        self.abstention_threshold = abstention_threshold

    def retrieve(self, query: str, limit: int = 5) -> tuple[list[str], float]:
        t0 = time.perf_counter()
        raw_tokens = _split_identifier_tokens(query)
        stop_words = {"where", "is", "are", "the", "code", "responsible", "for", "which", "depend", "on", "this", "what", "could", "be", "affected", "by", "changing", "find", "locate", "get", "in", "to"}
        literal_tokens = [t for t in raw_tokens if t not in stop_words] or raw_tokens

        # Synonym expansion
        synonym_tokens: set[str] = set()
        for t in literal_tokens:
            if t in SYNONYM_MAP:
                synonym_tokens.update(SYNONYM_MAP[t])
        all_expanded = set(literal_tokens).union(synonym_tokens)

        # Negative query domain anchor pre-check
        if self.enable_negative_abstention:
            anchor_tokens = [t for t in literal_tokens if t not in GENERIC_STRUCTURAL_WORDS and len(t) >= 4]
            # If query has distinct anchor tokens (e.g. 'stripe', 'graphql', 'redis', 'webrtc'), check if ANY file or symbol has them
            if anchor_tokens:
                has_any_anchor = False
                for fid, syms in self.indexer._symbols_by_file.items():
                    fid_low = fid.lower()
                    if any(a in fid_low for a in anchor_tokens):
                        has_any_anchor = True
                        break
                    if any(any(a in s.name.lower() for a in anchor_tokens) for s in syms):
                        has_any_anchor = True
                        break
                if not has_any_anchor:
                    # Pure negative query with 0 anchor presence anywhere in the repo
                    return [], (time.perf_counter() - t0) * 1000.0

        candidates: list[tuple[float, str]] = []
        for file_id in self._files_by_id:
            score = self._score_file(file_id, literal_tokens, synonym_tokens, all_expanded, query)
            if score is not None and score >= (self.abstention_threshold if self.enable_negative_abstention else 5.0):
                candidates.append((score, file_id))

        candidates.sort(key=lambda item: (-item[0], item[1]))
        results = [fid for _, fid in candidates[:limit]]
        dur_ms = (time.perf_counter() - t0) * 1000.0
        return results, dur_ms

    def _score_file(
        self,
        file_id: str,
        literal_tokens: list[str],
        synonym_tokens: set[str],
        all_expanded: set[str],
        raw_query: str,
    ) -> float | None:
        file_path_lower = file_id.lower()
        file_name = file_id.rsplit("/", 1)[-1].lower()
        file_stem = file_name.split(".")[0]
        node = self._files_by_id.get(file_id)
        symbols = self.indexer.find_by_file(file_id)

        score = 0.0
        raw_q_low = raw_query.lower()

        # 1. Filename & Stem Matching
        if self.enable_exact_filename_stem:
            # Full query match
            if raw_q_low == file_name or raw_q_low == file_stem:
                score += 35.0
            # Token match to filename or stem
            elif any(t == file_name or t == file_stem for t in literal_tokens):
                score += 30.0
            elif raw_q_low in file_path_lower:
                score += 15.0
        else:
            # Baseline behavior
            if raw_q_low == file_name:
                score += 25.0
            elif raw_q_low in file_path_lower:
                score += 15.0

        # 2. Path Tokens
        path_tokens = set(_split_identifier_tokens(file_id))
        if self.enable_synonym_calibration:
            literal_path_matches = path_tokens.intersection(set(literal_tokens))
            syn_path_matches = path_tokens.intersection(synonym_tokens) - literal_path_matches
            score += len(literal_path_matches) * 8.0
            score += len(syn_path_matches) * 2.5
        else:
            matching_path_terms = path_tokens.intersection(all_expanded)
            score += len(matching_path_terms) * 6.0

        # 3. Symbol Matching
        has_symbol_code_match = False
        if self.enable_symbol_boost_and_diminishing:
            # Sort symbols so exact and strong matches are processed first
            sym_scores: list[float] = []
            for sym in symbols:
                s_name_lower = sym.name.lower()
                sym_tokens = set(_split_identifier_tokens(sym.name))

                is_exact = s_name_lower in literal_tokens or s_name_lower == raw_q_low
                literal_sym_overlap = sym_tokens.intersection(set(literal_tokens))
                syn_sym_overlap = sym_tokens.intersection(synonym_tokens) - literal_sym_overlap

                if is_exact:
                    # Substantial definition boost
                    exact_val = 65.0 if sym.kind.value in ("class", "interface") else 55.0
                    sym_scores.append(exact_val)
                    has_symbol_code_match = True
                elif literal_sym_overlap:
                    val = len(literal_sym_overlap) * 12.0
                    if sym.kind.value in ("class", "interface"):
                        val += 6.0
                    sym_scores.append(val)
                    has_symbol_code_match = True
                elif syn_sym_overlap:
                    # Calibrated synonym match (lower weight)
                    val = len(syn_sym_overlap) * 4.0
                    sym_scores.append(val)
                    has_symbol_code_match = True

            # Diminishing returns: top match 100%, 2nd match 60%, 3rd match 30%, rest ignored
            if sym_scores:
                sym_scores.sort(reverse=True)
                diminished_score = sym_scores[0]
                if len(sym_scores) > 1:
                    diminished_score += sym_scores[1] * 0.5
                if len(sym_scores) > 2:
                    diminished_score += sym_scores[2] * 0.25
                # Cap non-exact symbol contribution
                if sym_scores[0] < 50.0:
                    diminished_score = min(diminished_score, 45.0)
                score += diminished_score
        else:
            # Baseline behavior (unbounded linear sum)
            for sym in symbols:
                s_name_lower = sym.name.lower()
                sym_tokens = set(_split_identifier_tokens(sym.name))
                is_exact = s_name_lower == raw_q_low or s_name_lower in literal_tokens
                common_tokens = sym_tokens.intersection(all_expanded)
                is_substr = any(t in s_name_lower for t in all_expanded)
                if is_exact:
                    score += 55.0
                    has_symbol_code_match = True
                elif common_tokens or is_substr:
                    bonus = max(len(common_tokens), 1) * 12.0
                    if sym.kind.value in ("class", "interface"): bonus += 8.0
                    elif sym.kind.value in ("function", "method"): bonus += 6.0
                    score += bonus
                    has_symbol_code_match = True

        # 4. Comments demotion
        if not has_symbol_code_match and score > 0:
            content = self._content_cache.get(file_id)
            if content is None:
                p = Path(file_id)
                content = p.read_text(encoding="utf-8", errors="ignore") if p.is_file() else ""
                self._content_cache[file_id] = content
            comments = " ".join(l.strip() for l in content.splitlines() if l.strip().startswith(("#", "//", "/*", "*"))).lower()
            if any(t in comments for t in literal_tokens) and not path_tokens.intersection(set(literal_tokens)):
                score = min(score, 3.0)

        # 5. Hub & Full AST bonus
        if node and node.is_hub and score > 15.0:
            score += 4.0
        if node and node.support_level == LanguageSupportLevel.FULL_AST and score > 10.0:
            score += 2.0

        # 6. Test file demotion
        is_test = "test" in file_path_lower or "spec" in file_path_lower
        wants_test = any(t in ("test", "tests", "spec") for t in literal_tokens)
        if is_test and not wants_test and score > 0:
            score *= 0.2

        return score if score > 0 else None

def evaluate_config(name: str, engine: ConfigurableRetrievalEngine):
    evals: list[SingleQueryEvaluation] = []
    for q in dev_queries:
        is_neg = len(q.expected_files) == 0
        returned, dur = engine.retrieve(q.query, limit=5)
        evals.append(SingleQueryEvaluation(
            query_id=q.query_id,
            query=q.query,
            method=name,
            split="dev",
            returned_files=returned,
            hit_at_1=compute_hit_at_k(returned, q.expected_files, 1),
            hit_at_3=compute_hit_at_k(returned, q.expected_files, 3),
            hit_at_5=compute_hit_at_k(returned, q.expected_files, 5),
            reciprocal_rank=compute_reciprocal_rank(returned, q.expected_files),
            precision_at_1=compute_precision_at_k(returned, q.expected_files, 1),
            precision_at_3=compute_precision_at_k(returned, q.expected_files, 3),
            precision_at_5=compute_precision_at_k(returned, q.expected_files, 5),
            recall_at_1=compute_recall_at_k(returned, q.expected_files, 1),
            recall_at_3=compute_recall_at_k(returned, q.expected_files, 3),
            recall_at_5=compute_recall_at_k(returned, q.expected_files, 5),
            ndcg_at_5=compute_ndcg_at_k(returned, q.expected_files, 5),
            latency_ms=round(dur, 2),
            is_negative=is_neg,
            abstained=is_neg and len(returned) == 0,
            false_positive_on_negative=is_neg and len(returned) > 0,
        ))
    summary = aggregate_method_metrics(evals, name)
    return summary

print("\nRunning Ablation Experiments on Dev Split (43 queries)...")

configs = [
    ("1. Baseline (Current)", ConfigurableRetrievalEngine(indexer, analysis)),
    ("2. + Exact Filename & Stem", ConfigurableRetrievalEngine(indexer, analysis, enable_exact_filename_stem=True)),
    ("3. + Symbol Boost & Diminishing", ConfigurableRetrievalEngine(indexer, analysis, enable_symbol_boost_and_diminishing=True)),
    ("4. + Synonym Calibration", ConfigurableRetrievalEngine(indexer, analysis, enable_synonym_calibration=True)),
    ("5. + Negative Query Abstention", ConfigurableRetrievalEngine(indexer, analysis, enable_negative_abstention=True, abstention_threshold=16.0)),
    ("6. Combined (All Factors)", ConfigurableRetrievalEngine(
        indexer, analysis,
        enable_exact_filename_stem=True,
        enable_symbol_boost_and_diminishing=True,
        enable_synonym_calibration=True,
        enable_negative_abstention=True,
        abstention_threshold=16.0,
    )),
]

print(f"\n{'Configuration':<35} | {'Hit@1':<8} | {'Hit@3':<8} | {'Hit@5':<8} | {'MRR':<8} | {'nDCG@5':<8} | {'Abstention':<10}")
print("-" * 95)

results = {}
for name, eng in configs:
    s = evaluate_config(name, eng)
    results[name] = s
    print(f"{name:<35} | {s.hit_at_1 * 100:<8.2f} | {s.hit_at_3 * 100:<8.2f} | {s.hit_at_5 * 100:<8.2f} | {s.mrr:<8.4f} | {s.ndcg_at_5:<8.4f} | {s.negative_abstention_rate * 100:<8.1f}%")
