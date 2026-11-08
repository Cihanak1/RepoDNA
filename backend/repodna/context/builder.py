"""Agent Context Builder with mode selection, token estimation, and deterministic truncation."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from repodna.context.models import AgentContextResponse
from repodna.intelligence.service import RepositoryIntelligenceService
from repodna.schemas.models import AnalysisResult


class AgentContextBuilder:
    """Builds controlled, token-budgeted architectural context for LLM agents."""

    @staticmethod
    def estimate_tokens(text: str) -> int:
        """Approximates tokens assuming ~4 characters per token on average for English/code."""
        if not text:
            return 0
        return max(1, len(text) // 4)

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

        if mode == "compact":
            summary = overview.summary_text
            # Top modules: hubs first, then largest
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

            # High-level evidence of any critical rule violations
            for finding in analysis.health_report.findings[:3]:
                evidence.append(
                    f"[{finding.rule_id}] {finding.title} ({finding.severity.value.upper()}): {finding.remediation}"
                )

            has_more = (start_idx + page_size) < len(hubs_and_large)

        elif mode == "focused":
            if query:
                matches_resp = service.find_relevant_modules(query, limit=page_size * (page + 1))
                summary = matches_resp.summary_text
                start_idx = page * page_size
                paged_matches = matches_resp.matches[start_idx : start_idx + page_size]
                has_more = (start_idx + page_size) < len(matches_resp.matches)

                for m in paged_matches:
                    node = service._files_by_id.get(m.file_id)
                    relevant_modules.append(
                        {
                            "id": m.file_id,
                            "language": m.language,
                            "lines_code": node.lines_code if node else 0,
                            "fan_in": m.fan_in,
                            "fan_out": m.fan_out,
                            "instability": node.instability if node else 0.0,
                            "is_hub": m.is_hub,
                            "in_cycle": m.in_cycle,
                            "matching_symbols": [s.model_dump() for s in m.matching_symbols],
                            "match_reasons": m.match_reasons,
                        }
                    )
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
                for ev in finding.evidence:
                    evidence.append(f"[{finding.rule_id}] {ev}")

        continuation_token = f"page={page + 1}" if has_more else None
        truncated = has_more

        # Check character and token budget limits
        char_budget = max_chars or (max_tokens * 4 if max_tokens else None)
        if char_budget:
            # Deterministically trim modules if markdown exceeds budget
            test_resp = AgentContextResponse(
                repository=analysis.repo_name,
                revision=revision,
                generated_at=datetime.now(UTC),
                analysis_version="0.3.0",
                mode=mode,
                analysis_coverage=coverage_data,
                confidence_level=cov.confidence,
                requested_scope=requested_scope,
                summary=summary,
                relevant_modules=relevant_modules,
                evidence=evidence,
                limitations=limitations,
                truncated=truncated,
                continuation_token=continuation_token,
            )
            md_text = test_resp.as_markdown()
            while len(md_text) > char_budget and len(relevant_modules) > 1:
                relevant_modules.pop()
                truncated = True
                continuation_token = f"page={page + 1}"
                test_resp.relevant_modules = relevant_modules
                test_resp.truncated = truncated
                test_resp.continuation_token = continuation_token
                md_text = test_resp.as_markdown()

        final_md = AgentContextResponse(
            repository=analysis.repo_name,
            revision=revision,
            generated_at=datetime.now(UTC),
            analysis_version="0.3.0",
            mode=mode,
            analysis_coverage=coverage_data,
            confidence_level=cov.confidence,
            requested_scope=requested_scope,
            summary=summary,
            relevant_modules=relevant_modules,
            evidence=evidence,
            limitations=limitations,
            truncated=truncated,
            continuation_token=continuation_token,
        ).as_markdown()

        est_tokens = cls.estimate_tokens(final_md)

        return AgentContextResponse(
            repository=analysis.repo_name,
            revision=revision,
            generated_at=datetime.now(UTC),
            analysis_version="0.3.0",
            mode=mode,
            analysis_coverage=coverage_data,
            confidence_level=cov.confidence,
            requested_scope=requested_scope,
            summary=summary,
            relevant_modules=relevant_modules,
            evidence=evidence,
            limitations=limitations,
            truncated=truncated,
            continuation_token=continuation_token,
            estimated_tokens=est_tokens,
        )
