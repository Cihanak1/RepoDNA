"""Smart Context Retrieval Engine for RepoDNA Repository Brain.

Provides local-first, deterministic, explainable code and architectural location discovery.
"""

from __future__ import annotations

import re

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
    "cache": {"memoize", "store", "buffer", "redis", "lru"},
    "guardian": {"policy", "governance", "check", "gate", "rule", "barrier", "contract"},
    "contract": {"policy", "boundary", "rule", "layer", "isolation"},
    "passport": {"manifest", "identity", "metadata", "profile"},
    "module": {"mod", "file", "component", "service", "package"},
    "mod": {"module", "file", "component", "service", "package"},
}


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

    def search(
        self,
        query: str,
        limit: int = 10,
        kind: str | None = None,
        path_filter: str | None = None,
    ) -> SearchResponse:
        """
        Executes multi-factor deterministic ranking across filenames, symbols, and dependency graph.
        """
        intent = _classify_query_intent(query)
        raw_tokens = _split_identifier_tokens(query)
        stop_words = {"where", "is", "are", "the", "code", "responsible", "for", "which", "depend", "on", "this", "what", "could", "be", "affected", "by", "changing", "find"}
        query_tokens = [t for t in raw_tokens if t not in stop_words]
        if not query_tokens:
            query_tokens = raw_tokens

        expanded_terms: set[str] = set(query_tokens)
        for t in query_tokens:
            if t in SYNONYM_MAP:
                expanded_terms.update(SYNONYM_MAP[t])

        candidates: list[CodeSearchResult] = []
        all_file_ids = set(self._files_by_id.keys())
        for fid in self.indexer._symbols_by_file.keys():
            all_file_ids.add(fid)

        norm_filter = path_filter.replace("\\", "/").lstrip("/") if path_filter else None

        for file_id in sorted(all_file_ids):
            if norm_filter and not (file_id == norm_filter or file_id.startswith(norm_filter) or file_id.endswith(norm_filter)):
                continue

            node = self._files_by_id.get(file_id)
            symbols = self.indexer.find_by_file(file_id)
            if kind:
                symbols = [s for s in symbols if s.kind.value == kind]

            res = self._score_file(file_id, node, symbols, query_tokens, expanded_terms, query)
            if res is not None:
                candidates.append(res)

        # Graph proximity boost: Boost files connected to top scoring seed files
        if candidates and self.analysis:
            candidates.sort(key=lambda c: -c.score)
            top_seed_ids = {c.file_id for c in candidates[:3] if c.score >= 15.0}
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
            if m.score >= 25.0:
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
        reasons: list[str] = []
        score = 0.0
        matched_symbols: list[SymbolDefinition] = []

        # 1. Exact filename or directory match
        raw_q_low = raw_query.lower()
        if raw_q_low == file_name:
            score += 25.0
            reasons.append(f"Exact filename match on '{raw_query}'")
        elif raw_q_low in file_path_lower:
            score += 15.0
            reasons.append(f"Path substring match on '{raw_query}'")

        # 2. Path tokens
        path_tokens = _split_identifier_tokens(file_id)
        matching_path_terms = set(path_tokens).intersection(expanded_terms)
        if matching_path_terms:
            score += len(matching_path_terms) * 6.0
            reasons.append(f"Path matched {len(matching_path_terms)} keyword(s): {', '.join(sorted(matching_path_terms)[:3])}")

        # 3. Symbol matching (Definitions)
        has_symbol_code_match = False
        for sym in symbols:
            s_name_lower = sym.name.lower()
            sym_tokens = set(_split_identifier_tokens(sym.name))

            is_exact = s_name_lower == raw_q_low
            common_tokens = sym_tokens.intersection(expanded_terms)
            is_substr = any(t in s_name_lower for t in expanded_terms)

            if is_exact:
                score += 35.0
                reasons.append(f"Exact symbol definition match: {sym.kind.value} '{sym.name}'")
                matched_symbols.append(sym)
                has_symbol_code_match = True
            elif common_tokens or is_substr:
                match_cnt = max(len(common_tokens), 1)
                bonus = match_cnt * 10.0
                if sym.kind.value in ("class", "interface"):
                    bonus += 6.0
                elif sym.kind.value in ("function", "method"):
                    bonus += 5.0
                score += bonus
                matched_label = ", ".join(sorted(common_tokens)[:2]) if common_tokens else raw_query
                reasons.append(f"Symbol {sym.kind.value} '{sym.name}' matched {matched_label}")
                matched_symbols.append(sym)
                has_symbol_code_match = True

        # 4. Check for Misleading Comments / Docstrings vs Code
        is_comment_only = False
        full_path = self.indexer.root_path / file_id
        file_content = ""
        if full_path.is_file():
            try:
                file_content = full_path.read_text(encoding="utf-8", errors="replace")
            except Exception:
                pass

        if file_content:
            comments_text = " ".join(
                line.strip()
                for line in file_content.splitlines()
                if line.strip().startswith(("#", "//", "/*", "*", '"""', "'''"))
            ).lower()
            comments_match = any(t in comments_text for t in query_tokens)
            if comments_match and not has_symbol_code_match and not matching_path_terms:
                is_comment_only = True
                score = min(score, 3.0)  # Severe demotion
                reasons = ["Notice: Matched terms in code comments only; no corresponding code symbols found"]

        # 5. Graph metrics and hub bonus
        fan_in = node.fan_in if node else 0
        fan_out = node.fan_out if node else 0
        is_hub = node.is_hub if node else False
        in_cycle = node.in_cycle if node else False
        lines_code = node.lines_code if node else len(file_content.splitlines())
        lang = node.language if node else "Unknown"

        if is_hub and score > 0 and not is_comment_only:
            score += 5.0
            reasons.append("Architectural hub module (high afferent coupling)")

        # 6. AST Verification Bonus
        if node and node.support_level == LanguageSupportLevel.FULL_AST and score > 0 and not is_comment_only:
            score += 3.0
            reasons.append("Verified Tree-sitter AST coverage")

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
        elif file_content:
            lines = file_content.splitlines()
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
