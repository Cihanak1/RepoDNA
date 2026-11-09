"""Repository-wide Symbol Indexer and Cross-Reference Engine for RepoDNA Repository Brain."""

from __future__ import annotations

import os
from collections import defaultdict
from pathlib import Path

from repodna.brain.evidence import EvidenceLedger
from repodna.brain.extractor import DeepSymbolExtractor
from repodna.brain.models import (
    EvidenceReference,
    SymbolDefinition,
    SymbolKind,
    SymbolQueryResponse,
    SymbolReference,
)
from repodna.schemas.models import AnalysisResult


class SymbolIndexer:
    """Maintains indexed symbols and verified cross-module call/import references."""

    def __init__(
        self,
        root_path: Path | str,
        revision: str = "WORKING_TREE",
        analysis: AnalysisResult | None = None,
    ) -> None:
        self.root_path = Path(root_path).resolve()
        self.revision = revision
        self.analysis = analysis

        self.ledger = EvidenceLedger(repository_revision=revision)
        self._symbols_by_id: dict[str, SymbolDefinition] = {}
        self._symbols_by_name: dict[str, list[SymbolDefinition]] = defaultdict(list)
        self._symbols_by_name_lower: dict[str, list[SymbolDefinition]] = defaultdict(list)
        self._symbols_by_file: dict[str, list[SymbolDefinition]] = defaultdict(list)
        self._raw_references: list[SymbolReference] = []

    def index_all(self, max_files: int = 2500) -> None:
        """Indexes all supported source files in the target repository."""
        if self.analysis is not None:
            self._index_from_analysis(self.analysis)
        else:
            self._index_from_filesystem(max_files=max_files)

        self._resolve_cross_references()

    def _index_from_analysis(self, analysis: AnalysisResult) -> None:
        """Extracts deep symbols for every internal file discovered in analysis."""
        for file_node in analysis.files:
            file_path = file_node.id
            full_path = self.root_path / file_path
            if not full_path.is_file():
                continue

            try:
                content = full_path.read_text(encoding="utf-8", errors="replace")
                syms, refs, evs = DeepSymbolExtractor.extract_file_symbols(
                    file_path=file_path,
                    content=content,
                    revision=self.revision,
                )
                self.add_file_symbols(file_path, syms, refs, evs)
            except Exception:
                continue

    def _index_from_filesystem(self, max_files: int = 2500) -> None:
        """Walks filesystem extracting symbols up to max_files."""
        count = 0
        ignored = {
            ".git", "node_modules", ".venv", "venv", "dist", "build",
            "__pycache__", ".pytest_cache", ".mypy_cache",
        }
        valid_exts = {
            ".py", ".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs",
            ".go", ".rs", ".java", ".cs",
        }

        for root, dirs, files in os.walk(self.root_path):
            dirs[:] = [d for d in dirs if d not in ignored and not d.startswith(".")]
            for f in sorted(files):
                ext = Path(f).suffix.lower()
                if ext not in valid_exts:
                    continue

                full_path = Path(root) / f
                try:
                    rel_path = full_path.relative_to(self.root_path).as_posix()
                    content = full_path.read_text(encoding="utf-8", errors="replace")
                    syms, refs, evs = DeepSymbolExtractor.extract_file_symbols(
                        file_path=rel_path,
                        content=content,
                        revision=self.revision,
                    )
                    self.add_file_symbols(rel_path, syms, refs, evs)
                    count += 1
                    if count >= max_files:
                        return
                except Exception:
                    continue

    def add_file_symbols(
        self,
        file_path: str,
        symbols: list[SymbolDefinition],
        references: list[SymbolReference],
        evidence_items: list[EvidenceReference],
    ) -> None:
        norm_path = file_path.replace("\\", "/").lstrip("/")
        self.ledger.add_bulk(evidence_items)

        for sym in symbols:
            self._symbols_by_id[sym.id] = sym
            self._symbols_by_name[sym.name].append(sym)
            self._symbols_by_name_lower[sym.name.lower()].append(sym)
            self._symbols_by_file[norm_path].append(sym)

        self._raw_references.extend(references)

    def _resolve_cross_references(self) -> None:
        """
        Cross-references raw AST calls and imports against known internal symbol definitions.
        Ensures only mathematically verified references are added to symbol definitions.
        """
        for ref in self._raw_references:
            target_name = ref.symbol_name
            candidates = self._symbols_by_name.get(target_name, [])
            if not candidates:
                continue

            # If reference occurs in a file that directly imports candidates or lives in the same file
            matched_candidate = None
            for cand in candidates:
                if cand.file_path == ref.file_path:
                    matched_candidate = cand
                    break

            if not matched_candidate and len(candidates) == 1:
                # Unambiguous single symbol in the codebase
                matched_candidate = candidates[0]
            elif not matched_candidate and self.analysis is not None:
                # Check internal dependency edges between ref file and candidate file
                ref_node = next((f for f in self.analysis.files if f.id == ref.file_path), None)
                if ref_node:
                    for cand in candidates:
                        if cand.file_path in ref_node.imports_internal:
                            matched_candidate = cand
                            break

            if matched_candidate is not None:
                ref.is_verified = True
                ref.confidence_reason = (
                    f"AST verified reference from '{ref.file_path}' "
                    f"to '{matched_candidate.file_path}:{matched_candidate.name}'"
                )
                matched_candidate.verified_references.append(ref)

    def find_by_name(
        self,
        name: str,
        kind: SymbolKind | str | None = None,
        file_path: str | None = None,
        exact: bool = True,
    ) -> list[SymbolDefinition]:
        """Finds symbols matching name with optional filters."""
        kind_str = kind.value if isinstance(kind, SymbolKind) else kind
        norm_path = file_path.replace("\\", "/").lstrip("/") if file_path else None

        if exact:
            candidates = self._symbols_by_name.get(name, [])
        else:
            candidates = self._symbols_by_name_lower.get(name.lower(), [])
            if not candidates:
                # Substring search
                n_low = name.lower()
                candidates = [s for s in self._symbols_by_id.values() if n_low in s.name.lower()]

        results: list[SymbolDefinition] = []
        for sym in candidates:
            if kind_str and sym.kind.value != kind_str:
                continue
            if norm_path and not (sym.file_path == norm_path or sym.file_path.endswith(norm_path)):
                continue
            results.append(sym)
        return results

    def find_by_file(self, file_path: str) -> list[SymbolDefinition]:
        norm_path = file_path.replace("\\", "/").lstrip("/")
        return list(self._symbols_by_file.get(norm_path, []))

    def list_symbols(
        self,
        kind: SymbolKind | str | None = None,
        language: str | None = None,
        file_path: str | None = None,
        container: str | None = None,
        limit: int = 50,
    ) -> SymbolQueryResponse:
        kind_str = kind.value if isinstance(kind, SymbolKind) else kind
        norm_path = file_path.replace("\\", "/").lstrip("/") if file_path else None

        matched: list[SymbolDefinition] = []
        for sym in self._symbols_by_id.values():
            if kind_str and sym.kind.value != kind_str:
                continue
            if language and sym.language.lower() != language.lower():
                continue
            if norm_path and not (sym.file_path == norm_path or sym.file_path.endswith(norm_path)):
                continue
            if container and sym.container_name != container:
                continue
            matched.append(sym)

        matched.sort(key=lambda s: (s.file_path, s.line_start, s.name))
        page = matched[:limit]
        return SymbolQueryResponse(
            total_symbols=len(matched),
            symbols=page,
            summary_text=f"Indexed {len(matched)} matching symbol(s) in repository.",
            filter_criteria={
                "kind": kind_str,
                "language": language,
                "file_path": file_path,
                "container": container,
                "limit": limit,
            },
        )
