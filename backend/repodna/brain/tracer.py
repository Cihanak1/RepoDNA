"""Cross-module Symbol Tracer and Blast Radius Engine for RepoDNA Repository Brain."""

from __future__ import annotations

from collections import deque

from repodna.brain.indexer import SymbolIndexer
from repodna.brain.models import (
    EvidenceReference,
    EvidenceType,
    ReferenceKind,
    SymbolDefinition,
    SymbolReference,
    SymbolTraceResult,
)
from repodna.schemas.models import AnalysisResult, FileNode, LanguageSupportLevel


class AmbiguousSymbolError(Exception):
    """Raised when a symbol query matches multiple candidates and requires disambiguation."""

    def __init__(self, symbol_name: str, candidates: list[SymbolDefinition]) -> None:
        self.symbol_name = symbol_name
        self.candidates = candidates
        cand_strs = [
            f"id='{c.id}' at '{c.file_path}:{c.line_start}' ({c.kind.value}"
            + (f" in class '{c.container_name}'" if c.container_name else "")
            + ")"
            for c in candidates
        ]
        msg = (
            f"Symbol '{symbol_name}' is ambiguous ({len(candidates)} definitions found). "
            f"Disambiguate by specifying symbol_id, file_path, or container_name. "
            f"Candidates: {'; '.join(cand_strs)}"
        )
        super().__init__(msg)


class SymbolTracer:
    """Traces symbol definitions to verified usages, call sites, and downstream blast radius."""

    def __init__(self, indexer: SymbolIndexer, analysis: AnalysisResult | None = None) -> None:
        self.indexer = indexer
        self.analysis = analysis or indexer.analysis
        self._files_by_id: dict[str, FileNode] = (
            {f.id: f for f in self.analysis.files} if self.analysis else {}
        )

    def trace_symbol(
        self,
        symbol_name: str | None = None,
        symbol_id: str | None = None,
        file_path: str | None = None,
        container_name: str | None = None,
        allow_ambiguous: bool = False,
    ) -> SymbolTraceResult:
        """
        Traces a symbol across all internal repository modules.
        Supports exact identification via symbol_id or discriminators (file_path, container_name).
        Raises AmbiguousSymbolError if multiple definitions match unless allow_ambiguous=True.
        """
        target_symbol: SymbolDefinition | None = None

        if symbol_id:
            target_symbol = self.indexer.get_by_id(symbol_id)
            if not target_symbol:
                raise KeyError(f"Symbol ID '{symbol_id}' not found in indexed repository.")

        elif symbol_name:
            candidates = self.indexer.find_by_name(
                symbol_name, file_path=file_path, container=container_name, exact=True
            )
            if not candidates:
                candidates = self.indexer.find_by_name(
                    symbol_name, file_path=file_path, container=container_name, exact=False
                )

            if not candidates:
                filters = []
                if file_path:
                    filters.append(f"file: '{file_path}'")
                if container_name:
                    filters.append(f"container: '{container_name}'")
                filter_str = f" ({', '.join(filters)})" if filters else ""
                raise KeyError(f"Symbol '{symbol_name}' not found in indexed repository{filter_str}.")

            if len(candidates) > 1:
                if not allow_ambiguous:
                    raise AmbiguousSymbolError(symbol_name=symbol_name, candidates=candidates)
                else:
                    # Return safe ambiguous result with candidate details and NO false verified calls
                    first = candidates[0]
                    ev = self.indexer.ledger.get_by_id(first.evidence_id) or EvidenceReference(
                        evidence_id=first.evidence_id,
                        repository_revision=self.indexer.revision,
                        file_path=first.file_path,
                        line_start=first.line_start,
                        line_end=first.line_end,
                        evidence_type=EvidenceType.SYMBOL_DEFINITION,
                        symbol_name=first.name,
                        confidence_reason="Ambiguous symbol candidate",
                    )
                    cand_strs = [f"- `{c.file_path}:{c.line_start}` ({c.kind.value}, ID: `{c.id}`)" for c in candidates]
                    return SymbolTraceResult(
                        symbol=first,
                        definition_evidence=ev,
                        references=[],
                        candidate_references=[],
                        importing_modules=[],
                        calling_modules=[],
                        downstream_dependents=[],
                        downstream_impact_count=0,
                        is_ambiguous=True,
                        ambiguity_candidates=candidates,
                        summary_text=(
                            f"⚠️ Symbol '{symbol_name}' is AMBIGUOUS ({len(candidates)} definitions found).\n"
                            f"Specify symbol_id or filter by file_path/container_name:\n"
                            + "\n".join(cand_strs)
                        ),
                    )

            target_symbol = candidates[0]
        else:
            raise ValueError("Either symbol_name or symbol_id must be provided to trace_symbol.")

        def_file = target_symbol.file_path
        def_node = self._files_by_id.get(def_file)

        # Evidence of definition
        def_ev = self.indexer.ledger.get_by_id(target_symbol.evidence_id)
        if not def_ev:
            def_ev = EvidenceReference(
                evidence_id=target_symbol.evidence_id,
                repository_revision=self.indexer.revision,
                file_path=def_file,
                line_start=target_symbol.line_start,
                line_end=target_symbol.line_end,
                evidence_type=EvidenceType.SYMBOL_DEFINITION,
                symbol_name=target_symbol.name,
                symbol_kind=target_symbol.kind,
                support_level=LanguageSupportLevel.FULL_AST,
                confidence_reason=f"Verified definition of {target_symbol.kind.value} '{target_symbol.name}'",
            )

        # Strictly separate verified references from candidate references
        verified_refs: list[SymbolReference] = [r for r in target_symbol.verified_references if r.is_verified]
        candidate_refs: list[SymbolReference] = list(target_symbol.candidate_references)

        # Downstream dependents from dependency graph (only verified calls populate calling_modules)
        calling_modules: set[str] = set()
        importing_modules: set[str] = set()
        for ref in verified_refs:
            if ref.file_path != def_file:
                importing_modules.add(ref.file_path)
                if ref.reference_kind == ReferenceKind.CALL:
                    calling_modules.add(ref.file_path)

        # Transitive downstream blast radius
        downstream: set[str] = set()
        if def_node:
            queue = deque(def_node.imported_by)
            visited = set(def_node.imported_by)
            while queue:
                curr = queue.popleft()
                downstream.add(curr)
                curr_node = self._files_by_id.get(curr)
                if curr_node:
                    for parent in curr_node.imported_by:
                        if parent not in visited:
                            visited.add(parent)
                            queue.append(parent)

        # Check circular dependency involvement
        cycle_warning = None
        if def_node and def_node.in_cycle:
            cycle_warning = (
                f"Warning: Defining module '{def_file}' participates in circular dependency cycle(s): "
                f"{', '.join(def_node.cycle_ids)}."
            )

        summary_lines = [
            f"Symbol: {target_symbol.kind.value.upper()} '{target_symbol.name}' in `{def_file}:{target_symbol.line_start}`",
            f"Language: {target_symbol.language} | Verified References: {len(verified_refs)} | Candidate Usages: {len(candidate_refs)}",
            f"Importing Modules ({len(importing_modules)}): {', '.join(sorted(importing_modules)[:5]) or 'None'}",
            f"Calling Modules ({len(calling_modules)}): {', '.join(sorted(calling_modules)[:5]) or 'None'}",
            f"Downstream Blast Radius: {len(downstream)} module(s) depend directly or transitively on this file.",
        ]
        if cycle_warning:
            summary_lines.append(f"⚠️ {cycle_warning}")

        return SymbolTraceResult(
            symbol=target_symbol,
            definition_evidence=def_ev,
            references=verified_refs,
            candidate_references=candidate_refs,
            importing_modules=sorted(importing_modules),
            calling_modules=sorted(calling_modules),
            downstream_dependents=sorted(downstream),
            downstream_impact_count=len(downstream),
            cycle_warning=cycle_warning,
            is_ambiguous=False,
            summary_text="\n".join(summary_lines),
        )
