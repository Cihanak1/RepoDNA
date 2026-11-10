"""Smart Context Retrieval Engine for RepoDNA Repository Brain.

Provides local-first, deterministic, explainable code and architectural location discovery.
"""

from __future__ import annotations

import re
from pathlib import Path

from repodna.brain.indexer import SymbolIndexer
from repodna.brain.models import (
    CodeSearchResult,
    SearchResponse,
    SymbolDefinition,
)
from repodna.schemas.models import AnalysisResult, FileNode, LanguageSupportLevel

# Common software engineering synonym expansions for deterministic retrieval
SYNONYM_MAP: dict[str, set[str]] = {
    "auth": {"authentication", "authenticate", "authorize", "login", "token", "session", "credential", "jwt", "oauth", "password", "user"},
    "authentication": {"auth", "authenticate", "authorize", "login", "token", "session", "credential", "jwt", "oauth"},
    "validation": {"validate", "validator", "check", "verify", "rule", "schema", "sanitizer", "guard"},
    "validate": {"validation", "validator", "check", "verify", "rule", "schema", "guard"},
    "service": {"manager", "handler", "provider", "client", "facade", "controller"},
    "database": {"db", "repository", "repo", "store", "storage", "model", "entity", "orm", "sql"},
    "db": {"database", "repository", "repo", "store", "storage", "model", "entity"},
    "router": {"route", "endpoint", "controller", "api", "handler", "view"},
    "config": {"configuration", "settings", "options", "env", "environment"},
    "cache": {"memoize", "store", "buffer", "redis", "lru", "storage"},
    "guardian": {"policy", "governance", "check", "gate", "rule", "barrier", "contract", "pr", "threshold", "verdict"},
    "contract": {"policy", "boundary", "rule", "layer", "isolation"},
    "passport": {"manifest", "identity", "metadata", "profile"},
    "module": {"mod", "file", "component", "service", "package"},
    "mod": {"module", "file", "component", "service", "package"},
    "ast": {"parser", "treesitter", "syntax", "tree"},
    "parser": {"parsing", "treesitter", "ast", "grammar"},
    "cycle": {"tarjan", "scc", "circular", "loop", "cycles"},
    "cycles": {"tarjan", "scc", "circular", "loop", "cycle"},
    "coupling": {"instability", "fan", "afferent", "efferent"},
    "diff": {"delta", "comparison", "compare", "snapshot"},
    "storage": {"workspace", "clone", "temp", "storage"},
    "report": {"exporter", "html", "export", "view", "report"},
    "graph": {"dependency", "matrix", "network", "visualizer"},
    "cli": {"main", "command", "parser", "installer", "cli"},
}

GENERIC_STRUCTURAL_WORDS = {
    "service", "handler", "manager", "client", "provider", "facade", "controller",
    "helper", "util", "utils", "config", "component", "mod", "module", "file", "item",
    "data", "schema", "rule", "view", "tab", "dialog", "panel", "modal"
}

EXTENDED_GENERIC_WORDS = GENERIC_STRUCTURAL_WORDS.union({
    "worker", "resolver", "cluster", "logic", "task", "defined", "implemented", "configured",
    "binding", "streamer", "provider", "where", "find", "locate", "what", "which", "who", "code",
    "connection", "stream", "queue", "schema", "handler", "manager", "service",
    "orchestrated", "executed", "grading", "computed", "creation", "checkout", "handling",
    "managing", "snippets", "staleness", "routes", "card", "widget", "tab", "isolated",
    "cloning", "temporary", "handled", "threshold", "exit", "entrypoint", "visualizer",
    "details", "cross", "referencing", "calls", "definitions", "constant", "declared",
})


def _split_identifier_tokens(text: str) -> list[str]:
    """Splits camelCase, PascalCase, snake_case, and alphanumeric identifiers into individual tokens."""
    raw_tokens = re.split(r"[^a-zA-Z0-9]+", text)
    tokens: list[str] = []
    for raw in raw_tokens:
        if not raw:
            continue
        sub = re.findall(r"[A-Z][a-z]+|[A-Z]+(?=[A-Z][a-z]|\d|\b)|[a-z]+[0-9]+|[a-z]+|[0-9]+", raw)
        if sub:
            tokens.extend(s.lower() for s in sub)
        else:
            tokens.append(raw.lower())
    return [t for t in tokens if len(t) >= 1]


def _classify_query_intent(query: str) -> str:
    """Classifies developer query into an actionable retrieval intent."""
    q_low = query.lower()
    if q_low.startswith(("where is", "where's", "where are", "find where")):
        return "where_is"
    elif q_low.startswith(("which modules depend", "who calls", "what depends on", "who imports")):
        return "dependency_trace"
    elif q_low.startswith(("what could be affected", "impact of", "what breaks if")):
        return "impact_analysis"
    elif q_low.startswith(("find symbol", "find function", "find class", "symbol:")):
        return "find_symbol"
    elif q_low.startswith(("find code", "find the code", "locate")):
        return "locate_code"
    return "general_search"


class SmartRetrievalEngine:
    """Deterministic, explainable code and architecture location search."""

    def __init__(self, indexer: SymbolIndexer, analysis: AnalysisResult | None = None) -> None:
        self.indexer = indexer
        self.analysis = analysis or indexer.analysis
        self._files_by_id: dict[str, FileNode] = (
            {f.id: f for f in self.analysis.files} if self.analysis else {}
        )
        self._content_cache: dict[str, str] = {}
        self._repo_vocab: set[str] = set()
        for fid, syms in self.indexer._symbols_by_file.items():
            fid_low = fid.lower()
            self._repo_vocab.add(fid_low)
            clean_fid = fid_low.replace("_", "").replace("-", "").rsplit(".", 1)[0]
            self._repo_vocab.add(clean_fid)
            for t in _split_identifier_tokens(fid):
                self._repo_vocab.add(t.lower())
            for s in syms:
                s_low = s.name.lower()
                self._repo_vocab.add(s_low)
                clean_sym = s_low.replace("_", "").replace("-", "")
                self._repo_vocab.add(clean_sym)
                for t in _split_identifier_tokens(s.name):
                    self._repo_vocab.add(t.lower())

    def search(
        self,
        query: str,
        limit: int = 10,
        kind: str | None = None,
        language: str | None = None,
        path_filter: str | None = None,
    ) -> SearchResponse:
        """
        Executes multi-factor deterministic ranking across filenames, symbols, and dependency graph.
        Pre-filters candidate set by path, language, and symbol kind before ranking and limiting.
        """
        intent = _classify_query_intent(query)
        raw_tokens = _split_identifier_tokens(query)
        stop_words = {"where", "is", "are", "the", "code", "responsible", "for", "which", "depend", "on", "this", "what", "could", "be", "affected", "by", "changing", "find", "locate", "get", "in", "to"}
        query_tokens = [t.lower() for t in raw_tokens if t.lower() not in stop_words]
        if not query_tokens:
            query_tokens = [t.lower() for t in raw_tokens]

        # Normalized compound words (e.g., 'tree-sitter' -> 'treesitter')
        cleaned_query = query.lower().replace("-", "")
        compound_tokens = [w for w in re.findall(r"[a-z0-9_]+", cleaned_query) if w not in stop_words and not w.isdigit()]
        all_literal = list(dict.fromkeys(query_tokens + compound_tokens))

        expanded_terms: set[str] = set(all_literal)
        for t in all_literal:
            if t in SYNONYM_MAP:
                expanded_terms.update(SYNONYM_MAP[t])

        # Negative query domain anchor pre-check
        domain_anchors = [w for w in compound_tokens if w not in EXTENDED_GENERIC_WORDS and len(w) >= 4]
        if domain_anchors:
            matched_anchors = [
                a for a in domain_anchors
                if a in self._repo_vocab
                or any(syn in self._repo_vocab for syn in SYNONYM_MAP.get(a, set()))
                or any(p in self._repo_vocab for p in _split_identifier_tokens(a) if p not in EXTENDED_GENERIC_WORDS and len(p) >= 3)
            ]
            primary_aliens = [a for a in domain_anchors if a not in matched_anchors]
            should_abstain = (len(matched_anchors) == 0) or (
                len(matched_anchors) == 1 and matched_anchors[0] in ("rust", "python") and len(primary_aliens) >= 1
            )
            if should_abstain:
                return SearchResponse(
                    query=query,
                    total_matches=0,
                    matches=[],
                    summary_text=f"No modules matched query '{query}'. Feature appears to be outside repository scope.",
                    query_intent=intent,
                    tokens_evaluated=sorted(expanded_terms),
                )

        candidates: list[CodeSearchResult] = []
        all_file_ids = set(self._files_by_id.keys())
        for fid in self.indexer._symbols_by_file.keys():
            all_file_ids.add(fid)

        norm_filter = path_filter.replace("\\", "/").strip("/") if path_filter else None
        req_kind = kind.strip().lower() if kind else None
        req_lang = language.strip().lower() if language else None

        ext_to_lang = {
            ".py": "python",
            ".ts": "typescript",
            ".tsx": "typescript (tsx)",
            ".js": "javascript",
            ".jsx": "javascript (jsx)",
            ".rs": "rust",
            ".go": "go",
            ".java": "java",
            ".rb": "ruby",
            ".cpp": "c++",
            ".c": "c",
        }

        for file_id in sorted(all_file_ids):
            # 1. Path filter with strict collision avoidance
            if norm_filter:
                norm_fid = file_id.replace("\\", "/").strip("/")
                is_match = (
                    norm_fid == norm_filter
                    or norm_fid.startswith(norm_filter + "/")
                    or any(part == norm_filter for part in norm_fid.split("/"))
                    or norm_fid.endswith("/" + norm_filter)
                )
                if not is_match:
                    continue

            node = self._files_by_id.get(file_id)

            # 2. Language filter
            if req_lang:
                file_lang = (node.language if node else "").lower()
                if not file_lang:
                    ext = Path(file_id).suffix.lower()
                    file_lang = ext_to_lang.get(ext, "")
                if not (req_lang in file_lang or file_lang in req_lang):
                    continue

            # 3. Symbol kind filter: files without matching symbols of that kind are excluded
            symbols = self.indexer.find_by_file(file_id)
            if req_kind:
                symbols = [s for s in symbols if s.kind.value.lower() == req_kind]
                if not symbols:
                    continue

            res = self._score_file(file_id, node, symbols, all_literal, expanded_terms, query)
            if res is not None:
                if req_kind and not res.matched_symbols and symbols:
                    res.matched_symbols = symbols[:3]
                candidates.append(res)

        # Graph proximity boost: Boost files connected to high-confidence seed files
        if candidates and self.analysis:
            candidates.sort(key=lambda c: -c.score)
            top_seed_ids = {c.file_id for c in candidates[:3] if c.score >= 35.0}
            if top_seed_ids:
                for cand in candidates:
                    if cand.file_id not in top_seed_ids and cand.score > 0:
                        cand_node = self._files_by_id.get(cand.file_id)
                        if cand_node:
                            is_connected = any(seed in cand_node.imports_internal or seed in cand_node.imported_by for seed in top_seed_ids)
                            if is_connected:
                                cand.score += 6.0
                                cand.match_reasons.append("Dependency proximity boost: Connected to primary matched service")

        # Sort deterministically
        candidates.sort(key=lambda c: (-c.score, -c.fan_in, c.file_id))
        top_matches = candidates[:limit]

        # Assign relevance tiers
        for m in top_matches:
            if m.score >= 20.0:
                m.relevance_tier = "HIGH"
            elif m.score >= 10.0:
                m.relevance_tier = "MEDIUM"
            else:
                m.relevance_tier = "LOW"

        summary = (
            f"Found {len(candidates)} matching module(s) for query '{query}' (Intent: {intent}). "
            f"Top match: {top_matches[0].file_id} (Score {top_matches[0].score:.1f}, {top_matches[0].relevance_tier})."
            if top_matches
            else f"No modules matched query '{query}'. Try searching by symbol name, file path, or keyword."
        )

        return SearchResponse(
            query=query,
            total_matches=len(candidates),
            matches=top_matches,
            summary_text=summary,
            query_intent=intent,
            tokens_evaluated=sorted(expanded_terms),
        )

    def _get_file_content(self, file_id: str) -> str:
        content = self._content_cache.get(file_id)
        if content is None:
            full_path = self.indexer.root_path / file_id
            if full_path.is_file():
                try:
                    content = full_path.read_text(encoding="utf-8", errors="replace")
                except Exception:
                    content = ""
            else:
                content = ""
            self._content_cache[file_id] = content
        return content

    def _score_file(
        self,
        file_id: str,
        node: FileNode | None,
        symbols: list[SymbolDefinition],
        query_tokens: list[str],
        expanded_terms: set[str],
        raw_query: str,
    ) -> CodeSearchResult | None:
        file_path_lower = file_id.lower()
        file_name = file_id.rsplit("/", 1)[-1].lower()
        file_stem = file_name.rsplit(".", 1)[0]
        reasons: list[str] = []
        score = 0.0
        matched_symbols: list[SymbolDefinition] = []

        # 1. Exact filename or directory match
        raw_q_low = raw_query.lower()
        if raw_q_low == file_name or raw_q_low == file_stem:
            score += 40.0
            reasons.append(f"Exact filename/stem match on '{raw_query}'")
        elif any(t == file_name or t == file_stem for t in query_tokens):
            score += 35.0
            reasons.append(f"Identifier match on file '{file_name}'")
        elif any(t in file_name for t in query_tokens if len(t) >= 4):
            score += 20.0
            reasons.append(f"Filename substring match in '{file_name}'")
        elif raw_q_low in file_path_lower:
            score += 15.0
            reasons.append(f"Path substring match on '{raw_query}'")

        # 2. Path tokens
        path_tokens = set(_split_identifier_tokens(file_id))
        literal_path_matches = path_tokens.intersection(set(query_tokens))
        syn_path_matches = path_tokens.intersection(expanded_terms) - literal_path_matches
        if literal_path_matches:
            score += len(literal_path_matches) * 8.0
            reasons.append(f"Path matched {len(literal_path_matches)} keyword(s): {', '.join(sorted(literal_path_matches)[:3])}")
        if syn_path_matches:
            score += len(syn_path_matches) * 5.0
            reasons.append(f"Path matched {len(syn_path_matches)} synonym(s): {', '.join(sorted(syn_path_matches)[:3])}")

        # 3. Symbol matching (Definitions) with Diminishing Returns
        has_symbol_code_match = False
        sym_scored_items: list[tuple[float, SymbolDefinition, str]] = []

        for sym in symbols:
            s_name_lower = sym.name.lower()
            sym_tokens = set(_split_identifier_tokens(sym.name))

            is_exact = s_name_lower == raw_q_low or s_name_lower in query_tokens
            literal_sym_overlap = sym_tokens.intersection(set(query_tokens))
            syn_sym_overlap = sym_tokens.intersection(expanded_terms) - literal_sym_overlap

            if is_exact:
                val = 65.0 if sym.kind.value in ("class", "interface") else 55.0
                sym_scored_items.append((val, sym, f"Exact symbol definition match: {sym.kind.value} '{sym.name}'"))
                has_symbol_code_match = True
            elif literal_sym_overlap:
                val = len(literal_sym_overlap) * 12.0
                if sym.kind.value in ("class", "interface"):
                    val += 6.0
                elif sym.kind.value in ("function", "method"):
                    val += 4.0
                matched_label = ", ".join(sorted(literal_sym_overlap)[:2])
                sym_scored_items.append((val, sym, f"Symbol {sym.kind.value} '{sym.name}' matched {matched_label}"))
                has_symbol_code_match = True
            elif syn_sym_overlap:
                val = len(syn_sym_overlap) * 7.0
                if sym.kind.value in ("class", "interface"):
                    val += 4.0
                elif sym.kind.value in ("function", "method"):
                    val += 2.0
                matched_label = ", ".join(sorted(syn_sym_overlap)[:2])
                sym_scored_items.append((val, sym, f"Symbol {sym.kind.value} '{sym.name}' matched synonym {matched_label}"))
                has_symbol_code_match = True

        if sym_scored_items:
            sym_scored_items.sort(key=lambda x: -x[0])
            diminished_score = sym_scored_items[0][0]
            matched_symbols.append(sym_scored_items[0][1])
            reasons.append(sym_scored_items[0][2])

            if len(sym_scored_items) > 1:
                diminished_score += sym_scored_items[1][0] * 0.5
                matched_symbols.append(sym_scored_items[1][1])
                reasons.append(sym_scored_items[1][2])
            if len(sym_scored_items) > 2:
                diminished_score += sym_scored_items[2][0] * 0.25
                matched_symbols.append(sym_scored_items[2][1])
                reasons.append(sym_scored_items[2][2])
            if sym_scored_items[0][0] < 50.0:
                diminished_score = min(diminished_score, 35.0)

            score += diminished_score

        # 4. Check for Misleading Comments / Docstrings vs Code
        is_comment_only = False
        if score > 0 and not has_symbol_code_match and not literal_path_matches:
            file_content = self._get_file_content(file_id)
            if file_content:
                comments_text = " ".join(
                    line.strip()
                    for line in file_content.splitlines()
                    if line.strip().startswith(("#", "//", "/*", "*", '"""', "'''"))
                ).lower()
                comments_match = any(t in comments_text for t in query_tokens)
                if comments_match:
                    is_comment_only = True
                    score = min(score, 3.0)  # Severe demotion
                    reasons = ["Notice: Matched terms in code comments only; no corresponding code symbols found"]

        # 5. Graph metrics and hub bonus
        fan_in = node.fan_in if node else 0
        fan_out = node.fan_out if node else 0
        is_hub = node.is_hub if node else False
        in_cycle = node.in_cycle if node else False
        lines_code = node.lines_code if node else len(self._get_file_content(file_id).splitlines())
        lang = node.language if node else "Unknown"

        if is_hub and score >= 20.0 and not is_comment_only:
            score += 4.0
            reasons.append("Architectural hub module (high afferent coupling)")

        # 6. AST Verification Bonus
        if node and node.support_level == LanguageSupportLevel.FULL_AST and score >= 15.0 and not is_comment_only:
            score += 2.0
            reasons.append("Verified Tree-sitter AST coverage")

        # 7. Demote test files unless query specifically asks for tests
        is_test_file = (
            "/tests/" in file_path_lower
            or file_path_lower.startswith("tests/")
            or file_path_lower.startswith("test_")
            or file_name.startswith("test_")
        )
        query_wants_tests = any(t in ("test", "tests", "spec", "fixture") for t in query_tokens)
        if is_test_file and not query_wants_tests and score > 0:
            score *= 0.15
            reasons.append("Notice: Test fixture demoted for implementation search")

        if score < 10.0:
            return None

        if score <= 0:
            return None

        ev_items = self.indexer.ledger.find_by_file(file_id)
        if matched_symbols:
            matched_sym_names = {s.name for s in matched_symbols}
            ev_items = [e for e in ev_items if e.symbol_name in matched_sym_names] or ev_items[:3]
        else:
            ev_items = ev_items[:3]

        snippet = None
        if matched_symbols and matched_symbols[0].signature:
            snippet = matched_symbols[0].signature
        else:
            fc = self._get_file_content(file_id)
            if fc:
                lines = fc.splitlines()
                snippet = "\n".join(lines[:min(5, len(lines))])

        return CodeSearchResult(
            file_id=file_id,
            score=round(score, 2),
            relevance_tier="LOW",
            match_reasons=reasons,
            matched_symbols=matched_symbols[:6],
            evidence_items=ev_items[:4],
            language=lang,
            lines_code=lines_code,
            fan_in=fan_in,
            fan_out=fan_out,
            is_hub=is_hub,
            in_cycle=in_cycle,
            is_comment_only_match=is_comment_only,
            snippet=snippet,
        )
