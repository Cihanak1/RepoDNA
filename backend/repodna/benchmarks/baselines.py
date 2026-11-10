"""Evaluation baselines comparing code retrieval approaches.

Baseline A: Filename-only search (lexical path and filename token matching)
Baseline B: Symbol-name exact / substring matching (pure lexical symbol name overlap)
Baseline C: Repository Brain multi-factor retrieval (AST symbols + graph + synonyms + proximity)
"""

from __future__ import annotations

import time
from typing import Protocol

from repodna.brain.indexer import SymbolIndexer
from repodna.brain.retrieval import SmartRetrievalEngine, _split_identifier_tokens
from repodna.schemas.models import AnalysisResult

STOP_WORDS = {
    "where", "is", "are", "the", "code", "responsible", "for",
    "which", "depend", "on", "this", "what", "could", "be",
    "affected", "by", "changing", "find", "locate", "get", "in", "to",
}


class RetrievalBaseline(Protocol):
    def retrieve(self, query: str, limit: int = 10) -> tuple[list[str], float]:
        """Returns ordered list of matching file paths and retrieval duration in ms."""
        ...


class FilenameOnlyBaseline:
    """Baseline A: Tokenizes query and matches strictly against path and filenames."""

    def __init__(self, all_files: list[str]) -> None:
        self.all_files = [f.replace("\\", "/").lstrip("/") for f in all_files]
        self._file_token_map: dict[str, set[str]] = {}
        self._filename_map: dict[str, str] = {}
        for f in self.all_files:
            fname = f.rsplit("/", 1)[-1].lower()
            tokens = set(_split_identifier_tokens(f))
            self._file_token_map[f] = tokens
            self._filename_map[f] = fname

    def retrieve(self, query: str, limit: int = 10) -> tuple[list[str], float]:
        t0 = time.perf_counter()
        raw_tokens = _split_identifier_tokens(query)
        q_tokens = [t for t in raw_tokens if t not in STOP_WORDS] or raw_tokens
        q_tokens_set = set(q_tokens)
        q_low = query.lower().strip()

        scored: list[tuple[float, str]] = []
        for f in self.all_files:
            score = 0.0
            fname = self._filename_map[f]
            f_tokens = self._file_token_map[f]

            # Exact filename match
            if q_low == fname or any(q == fname for q in q_tokens):
                score += 25.0
            # Substring match in path
            elif q_low in f.lower():
                score += 15.0

            # Token overlap
            overlap = len(f_tokens.intersection(q_tokens_set))
            if overlap > 0:
                score += overlap * 6.0

            if score >= 5.0:
                scored.append((score, f))

        scored.sort(key=lambda item: (-item[0], item[1]))
        results = [f for _, f in scored[:limit]]
        duration_ms = (time.perf_counter() - t0) * 1000.0
        return results, duration_ms


class SymbolOnlyBaseline:
    """Baseline B: Matches query tokens strictly against symbol names in repository."""

    def __init__(self, indexer: SymbolIndexer) -> None:
        self.indexer = indexer
        self._files = sorted(indexer._symbols_by_file.keys())

    def retrieve(self, query: str, limit: int = 10) -> tuple[list[str], float]:
        t0 = time.perf_counter()
        raw_tokens = _split_identifier_tokens(query)
        q_tokens = [t for t in raw_tokens if t not in STOP_WORDS] or raw_tokens
        q_tokens_set = set(q_tokens)
        q_low = query.lower().strip()

        file_scores: dict[str, float] = {}
        for f in self._files:
            syms = self.indexer._symbols_by_file.get(f, [])
            f_score = 0.0
            for sym in syms:
                s_low = sym.name.lower()
                s_tokens = set(_split_identifier_tokens(sym.name))

                if s_low == q_low or s_low in q_tokens_set:
                    f_score += 25.0
                elif s_tokens.intersection(q_tokens_set):
                    f_score += len(s_tokens.intersection(q_tokens_set)) * 8.0
                elif any(qt in s_low for qt in q_tokens_set if len(qt) >= 3):
                    f_score += 4.0

            if f_score >= 5.0:
                file_scores[f] = f_score

        sorted_files = sorted(file_scores.items(), key=lambda item: (-item[1], item[0]))
        results = [f for f, _ in sorted_files[:limit]]
        duration_ms = (time.perf_counter() - t0) * 1000.0
        return results, duration_ms


class RepositoryBrainRetrieval:
    """Baseline C: Smart multi-factor retrieval engine using AST symbols, graph, and synonyms."""

    def __init__(self, indexer: SymbolIndexer, analysis: AnalysisResult | None = None) -> None:
        self.retrieval_engine = SmartRetrievalEngine(indexer=indexer, analysis=analysis)

    def retrieve(self, query: str, limit: int = 10) -> tuple[list[str], float]:
        t0 = time.perf_counter()
        resp = self.retrieval_engine.search(query=query, limit=limit)
        results = [m.file_id for m in resp.matches if m.score >= 5.0]
        duration_ms = (time.perf_counter() - t0) * 1000.0
        return results, duration_ms
