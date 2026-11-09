"""Agent Context Builder with mode selection, token estimation, and deterministic truncation."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from repodna.brain.indexer import SymbolIndexer
from repodna.brain.retrieval import SmartRetrievalEngine
from repodna.context.models import AgentContextResponse
from repodna.intelligence.service import RepositoryIntelligenceService
from repodna.schemas.models import AnalysisResult


class AgentContextBuilder:
    """Builds controlled, token-budgeted architectural context for LLM agents."""

    @classmethod
    def count_tokens(cls, text: str) -> tuple[int, str]:
        """
        Counts tokens using a real tokenizer (tiktoken) if available, or deterministic heuristic.
        Returns (token_count, method_name).
        """
        if not text:
            return 0, "empty"
        try:
            import tiktoken

            enc = tiktoken.get_encoding("cl100k_base")
            return len(enc.encode(text)), "tiktoken_cl100k"
        except Exception:
            return max(1, len(text) // 4), "heuristic_chars"

    @classmethod
    def estimate_tokens(cls, text: str) -> int:
        """Approximates tokens assuming ~4 characters per token on average for English/code."""
        count, _ = cls.count_tokens(text)
        return count

    @classmethod
    def build_context(
        cls,
        analysis: AnalysisResult,
        mode: str = "compact",
        query: str | None = None,
        target_files: list[str] | None = None,
        max_tokens: int | None = None,
        max_chars: int | None = None,
        page: int = 0,
        page_size: int = 15,
        revision: str = "HEAD",
        indexer: SymbolIndexer | None = None,
    ) -> AgentContextResponse:
        service = RepositoryIntelligenceService(analysis)
        overview = service.get_repository_overview()
        cov = service.get_analysis_coverage()

        coverage_data = {
            "confidence": cov.confidence,
            "confidence_reason": cov.confidence_reason,
            "ast_loc_coverage_pct": cov.ast_loc_coverage_pct,
            "ast_file_coverage_pct": cov.ast_file_coverage_pct,
            "supported_languages": cov.supported_languages,
            "partial_static_languages": cov.partial_static_languages,
            "unsupported_languages": cov.unsupported_languages,
            "unverified_rules": cov.unverified_rules,
        }

        requested_scope = {
            "mode": mode,
            "query": query,
            "target_files": target_files,
            "page": page,
            "page_size": page_size,
        }

        evidence: list[str] = []
        evidence_records: list[dict[str, Any]] = []
        limitations: list[str] = []
        relevant_modules: list[dict[str, Any]] = []

        if cov.partial_static_languages:
            limitations.append(
                f"Languages {cov.partial_static_languages} were analyzed using partial static patterns. Full AST dependency edges are not guaranteed."
            )
        if cov.unsupported_languages:
            limitations.append(
                f"Languages {cov.unsupported_languages} are unsupported for AST graph analysis. Only basic file stats were gathered."
            )
        if cov.unverified_rules:
            limitations.append(
                f"Rules {cov.unverified_rules} could not be fully verified due to partial dependency coverage."
            )

        # Raw code tokens calculation across candidate / total codebase
        total_raw_code_tokens = sum(max(1, f.lines_code * 8) for f in analysis.files)

        # Zero or negative token budget: return safe minimal truncated response
        if max_tokens is not None and max_tokens <= 0:
            limitations.append(
                f"Requested token budget ({max_tokens}) is zero or negative. Returned minimal truncated response."
            )
            return AgentContextResponse(
                repository=analysis.repo_name,
                revision=revision,
                generated_at=datetime.now(UTC),
                analysis_version="0.5.0",
                mode=mode,
                analysis_coverage=coverage_data,
                confidence_level=cov.confidence,
                requested_scope=requested_scope,
                summary="Requested token budget is zero or negative.",
                relevant_modules=[],
                evidence=[],
                evidence_records=[],
                limitations=limitations,
                truncated=True,
                continuation_token=f"page={page}",
                estimated_tokens=0,
                raw_tokens_estimate=total_raw_code_tokens,
                token_savings_pct=100.0,
                estimated_savings_pct=100.0,
                is_savings_estimated=True,
                token_counting_method="heuristic_zero_budget",
            )

        if mode == "compact":
            summary = overview.summary_text
            hubs_and_large = sorted(
                analysis.files, key=lambda f: (-int(f.is_hub), -f.fan_in, -f.lines_code, f.id)
            )
            start_idx = page * page_size
            page_files = hubs_and_large[start_idx : start_idx + page_size]

            for f in page_files:
                relevant_modules.append(
                    {
                        "id": f.id,
                        "language": f.language,
                        "lines_code": f.lines_code,
                        "fan_in": f.fan_in,
                        "fan_out": f.fan_out,
                        "instability": f.instability,
                        "is_hub": f.is_hub,
                        "in_cycle": f.in_cycle,
                        "cycle_ids": f.cycle_ids,
                    }
                )

            for finding in analysis.health_report.findings[:3]:
                evidence.append(
                    f"[{finding.rule_id}] {finding.title} ({finding.severity.value.upper()}): {finding.remediation}"
                )

            has_more = (start_idx + page_size) < len(hubs_and_large)

        elif mode == "focused":
            if query:
                if indexer is not None:
                    retrieval_engine = SmartRetrievalEngine(indexer=indexer, analysis=analysis)
                    search_res = retrieval_engine.search(query=query, limit=page_size * (page + 1))
                    summary = search_res.summary_text
                    start_idx = page * page_size
                    paged_matches = search_res.matches[start_idx : start_idx + page_size]
                    has_more = (start_idx + page_size) < len(search_res.matches)

                    for m in paged_matches:
                        relevant_modules.append(
                            {
                                "id": m.file_id,
                                "language": m.language,
                                "lines_code": m.lines_code,
                                "fan_in": m.fan_in,
                                "fan_out": m.fan_out,
                                "is_hub": m.is_hub,
                                "in_cycle": m.in_cycle,
                                "relevance_score": m.score,
                                "relevance_tier": m.relevance_tier,
                                "match_reasons": m.match_reasons,
                                "matching_symbols": [s.model_dump() for s in m.matched_symbols],
                            }
                        )
                        for ev_item in m.evidence_items:
                            evidence_records.append(ev_item.model_dump())
                            evidence.append(f"[{ev_item.evidence_id}] {ev_item.file_path}:{ev_item.line_start} {ev_item.confidence_reason}")
                else:
                    matches_resp = service.find_relevant_modules(query, limit=page_size * (page + 1))
                    summary = matches_resp.summary_text
                    start_idx = page * page_size
                    legacy_matches = matches_resp.matches[start_idx : start_idx + page_size]
                    has_more = (start_idx + page_size) < len(matches_resp.matches)

                    for lm in legacy_matches:
                        node = service._files_by_id.get(lm.file_id)
                        relevant_modules.append(
                            {
                                "id": lm.file_id,
                                "language": lm.language,
                                "lines_code": node.lines_code if node else 0,
                                "fan_in": lm.fan_in,
                                "fan_out": lm.fan_out,
                                "is_hub": node.is_hub if node else False,
                                "in_cycle": node.in_cycle if node else False,
                                "cycle_ids": node.cycle_ids if node else [],
                                "relevance_score": lm.relevance_score,
                                "match_reasons": lm.match_reasons,
                            }
                        )
                    for lm in legacy_matches:
                        for reason in lm.match_reasons:
                            evidence.append(f"[{lm.file_id}] {reason}")

            elif target_files:
                impact = service.get_change_impact(target_files)
                summary = impact.summary_text
                has_more = False

                for tf in target_files:
                    try:
                        dtls = service.get_module_details(tf)
                        relevant_modules.append(
                            {
                                "id": dtls.file_id,
                                "language": dtls.language,
                                "lines_code": dtls.lines_code,
                                "fan_in": dtls.fan_in,
                                "fan_out": dtls.fan_out,
                                "instability": dtls.instability,
                                "is_hub": dtls.is_hub,
                                "in_cycle": dtls.in_cycle,
                                "cycle_ids": dtls.cycle_ids,
                                "dependencies_internal": dtls.dependencies_internal,
                                "dependents_internal": dtls.dependents_internal,
                            }
                        )
                    except KeyError:
                        limitations.append(f"Target file '{tf}' not recognized in repository index.")

                for risk in impact.risk_factors:
                    evidence.append(risk)
            else:
                summary = overview.summary_text
                has_more = False

        else:  # "deep" mode
            arch_map = service.get_architecture_map(level="clusters")
            summary = (
                f"{overview.summary_text}\n\n"
                f"{arch_map.summary_text}\n"
                f"Total Package Clusters: {arch_map.total_clusters}"
            )
            start_idx = page * page_size
            sorted_all = sorted(analysis.files, key=lambda f: (-f.fan_in, f.id))
            page_files = sorted_all[start_idx : start_idx + page_size]
            has_more = (start_idx + page_size) < len(sorted_all)

            for f in page_files:
                relevant_modules.append(
                    {
                        "id": f.id,
                        "language": f.language,
                        "lines_code": f.lines_code,
                        "fan_in": f.fan_in,
                        "fan_out": f.fan_out,
                        "instability": f.instability,
                        "is_hub": f.is_hub,
                        "in_cycle": f.in_cycle,
                        "cycle_ids": f.cycle_ids,
                        "symbols": [s.name for s in f.symbols[:5]],
                    }
                )

            for finding in analysis.health_report.findings:
                for ev_str in finding.evidence:
                    evidence.append(f"[{finding.rule_id}] {ev_str}")

        continuation_token = f"page={page + 1}" if has_more else None
        truncated = has_more

        # Check character and token budget limits
        char_budget = max_chars or (max_tokens * 4 if max_tokens else None)
        target_tokens = max_tokens or (char_budget // 4 if char_budget else None)

        if char_budget or target_tokens:
            test_resp = AgentContextResponse(
                repository=analysis.repo_name,
                revision=revision,
                generated_at=datetime.now(UTC),
                analysis_version="0.5.0",
                mode=mode,
                analysis_coverage=coverage_data,
                confidence_level=cov.confidence,
                requested_scope=requested_scope,
                summary=summary,
                relevant_modules=relevant_modules,
                evidence=evidence,
                evidence_records=evidence_records,
                limitations=limitations,
                truncated=truncated,
                continuation_token=continuation_token,
            )
            md_text = test_resp.as_markdown()
            curr_tokens, method_used = cls.count_tokens(md_text)

            max_prune_steps = len(evidence_records) + len(evidence) + len(relevant_modules) + 10
            step = 0
            while step < max_prune_steps:
                step += 1
                exceeds_chars = bool(char_budget and len(md_text) > char_budget)
                exceeds_tokens = bool(target_tokens and curr_tokens > target_tokens)
                if not (exceeds_chars or exceeds_tokens):
                    break

                truncated = True
                continuation_token = f"page={page + 1}"

                # Pruning hierarchy: evidence_records -> evidence -> relevant_modules -> summary
                if evidence_records:
                    evidence_records.pop()
                elif evidence:
                    evidence.pop()
                elif relevant_modules:
                    relevant_modules.pop()
                elif len(summary) > 30 and not summary.endswith("[TRUNCATED DUE TO BUDGET]"):
                    summary = summary[:30] + "... [TRUNCATED DUE TO BUDGET]"
                else:
                    # Minimal metadata alone exceeds budget
                    msg = f"Header metadata alone exceeds requested budget of {target_tokens} tokens."
                    if msg not in limitations:
                        limitations.append(msg)
                    break

                test_resp.summary = summary
                test_resp.relevant_modules = relevant_modules
                test_resp.evidence = evidence
                test_resp.evidence_records = evidence_records
                test_resp.limitations = limitations
                test_resp.truncated = truncated
                test_resp.continuation_token = continuation_token
                md_text = test_resp.as_markdown()
                curr_tokens, method_used = cls.count_tokens(md_text)

        final_resp = AgentContextResponse(
            repository=analysis.repo_name,
            revision=revision,
            generated_at=datetime.now(UTC),
            analysis_version="0.5.0",
            mode=mode,
            analysis_coverage=coverage_data,
            confidence_level=cov.confidence,
            requested_scope=requested_scope,
            summary=summary,
            relevant_modules=relevant_modules,
            evidence=evidence,
            evidence_records=evidence_records,
            limitations=limitations,
            truncated=truncated,
            continuation_token=continuation_token,
        )
        final_md = final_resp.as_markdown()
        final_tokens, method = cls.count_tokens(final_md)
        savings = (
            max(0.0, (1.0 - (final_tokens / max(1, total_raw_code_tokens))) * 100.0)
            if total_raw_code_tokens > final_tokens
            else 0.0
        )
        final_resp.estimated_tokens = final_tokens
        final_resp.raw_tokens_estimate = total_raw_code_tokens
        final_resp.token_savings_pct = round(savings, 1)
        final_resp.estimated_savings_pct = round(savings, 1)
        final_resp.is_savings_estimated = (method != "tiktoken_cl100k")
        final_resp.token_counting_method = method
        return final_resp
