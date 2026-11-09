"""Cross-module Symbol Tracer and Blast Radius Engine for RepoDNA Repository Brain."""

from __future__ import annotations

from collections import deque

from repodna.brain.indexer import SymbolIndexer
from repodna.brain.models import (
    EvidenceReference,
    EvidenceType,
    ReferenceKind,
    SymbolReference,
    SymbolTraceResult,
)
from repodna.schemas.models import AnalysisResult, FileNode, LanguageSupportLevel


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
        symbol_name: str,
        file_path: str | None = None,
    ) -> SymbolTraceResult:
        """
        Traces a symbol across all internal repository modules.
        Returns definition evidence, verified call sites, importing files, and downstream impact.
        """
        candidates = self.indexer.find_by_name(symbol_name, file_path=file_path)
        if not candidates:
            # Try case-insensitive
            candidates = self.indexer.find_by_name(symbol_name, file_path=file_path, exact=False)

        if not candidates:
            raise KeyError(
                f"Symbol '{symbol_name}' not found in indexed repository."
                + (f" (Filtered by file: {file_path})" if file_path else "")
            )

        # Pick the most prominent candidate (prefer class/function definition)
        target_symbol = candidates[0]
        for c in candidates:
            if c.kind.value in ("class", "function"):
                target_symbol = c
                break

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

        # Verified references
        verified_refs: list[SymbolReference] = list(target_symbol.verified_references)

        # Downstream dependents from dependency graph
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
            f"Language: {target_symbol.language} | Verified References: {len(verified_refs)}",
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
            importing_modules=sorted(importing_modules),
            calling_modules=sorted(calling_modules),
            downstream_dependents=sorted(downstream),
            downstream_impact_count=len(downstream),
            cycle_warning=cycle_warning,
            summary_text="\n".join(summary_lines),
        )
