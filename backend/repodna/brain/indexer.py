"""Repository-wide Symbol Indexer and Cross-Reference Engine for RepoDNA Repository Brain."""

from __future__ import annotations

import os
from collections import defaultdict
from pathlib import Path

from repodna.brain.evidence import EvidenceLedger
from repodna.brain.extractor import DeepSymbolExtractor
from repodna.brain.models import (
    EvidenceReference,
    EvidenceType,
    ReferenceKind,
    ResolutionStatus,
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
        revision: str | None = "WORKING_TREE",
        analysis: AnalysisResult | None = None,
    ) -> None:
        self.root_path = Path(root_path).resolve()
        self.revision = revision or "WORKING_TREE"
        self.analysis = analysis

        self.ledger = EvidenceLedger(repository_revision=self.revision)
        self._symbols_by_id: dict[str, SymbolDefinition] = {}
        self._symbols_by_name: dict[str, list[SymbolDefinition]] = defaultdict(list)
        self._symbols_by_name_lower: dict[str, list[SymbolDefinition]] = defaultdict(list)
        self._symbols_by_file: dict[str, list[SymbolDefinition]] = defaultdict(list)
        self._imports_by_file: dict[str, list[SymbolReference]] = defaultdict(list)
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
                # Graceful fallback: construct definitions from analysis file symbols
                if file_node.symbols:
                    fallback_syms: list[SymbolDefinition] = []
                    fallback_evs: list[EvidenceReference] = []
                    for s_item in file_node.symbols:
                        kind_val = s_item.kind.lower() if s_item.kind else "function"
                        try:
                            kind_enum = SymbolKind(kind_val)
                        except Exception:
                            kind_enum = SymbolKind.FUNCTION
                        sym_id = SymbolDefinition.generate_id(file_path, s_item.name, kind_enum.value, s_item.line)
                        ev_id = EvidenceReference.generate_id(
                            self.revision,
                            file_path,
                            s_item.line,
                            s_item.line,
                            "symbol_definition",
                            s_item.name,
                        )
                        ev = EvidenceReference(
                            evidence_id=ev_id,
                            repository_revision=self.revision,
                            file_path=file_path,
                            line_start=s_item.line,
                            line_end=s_item.line,
                            evidence_type=EvidenceType.SYMBOL_DEFINITION,
                            symbol_name=s_item.name,
                            symbol_kind=kind_enum,
                            confidence_reason="Analysis AST symbol node citation",
                        )
                        sym_def = SymbolDefinition(
                            id=sym_id,
                            name=s_item.name,
                            kind=kind_enum,
                            file_path=file_path,
                            line_start=s_item.line,
                            line_end=s_item.line,
                            language=file_node.language,
                            signature=f"{kind_enum.value} {s_item.name}",
                            docstring=None,
                            is_exported=True,
                            evidence_id=ev_id,
                        )
                        fallback_syms.append(sym_def)
                        fallback_evs.append(ev)
                    self.add_file_symbols(file_path, fallback_syms, [], fallback_evs)
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
            "__pycache__", ".pytest_cache", ".mypy_cache", "fixtures",
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
        # Ensure file is tracked even if it defines no symbols (e.g. index.ts or __init__.py with only re-exports)
        self._symbols_by_file.setdefault(norm_path, [])

        for sym in symbols:
            self._symbols_by_id[sym.id] = sym
            self._symbols_by_name[sym.name].append(sym)
            self._symbols_by_name_lower[sym.name.lower()].append(sym)
            self._symbols_by_file[norm_path].append(sym)

        for ref in references:
            if ref.reference_kind in (ReferenceKind.IMPORT, ReferenceKind.REEXPORT):
                self._imports_by_file[norm_path].append(ref)
            self._raw_references.append(ref)

    def _resolve_module_specifier(self, caller_file: str, specifier: str | None) -> str | None:
        """Resolves an import module specifier to a repo-relative file path."""
        if not specifier:
            return None

        caller_dir = Path(caller_file).parent.as_posix()
        norm_caller_dir = "" if caller_dir == "." else caller_dir

        # 1. Relative import (e.g. "./utils", "../pkg/service", ".service")
        if specifier.startswith("."):
            dots = len(specifier) - len(specifier.lstrip("."))
            spec_rest = specifier.lstrip(".")
            curr = Path(caller_file).parent
            # In Python, from . import x (dots=1) means current dir; from .. import x (dots=2) means parent dir
            for _ in range(max(0, dots - 1)):
                curr = curr.parent
            base_rel = curr.as_posix()
            if base_rel == ".":
                base_rel = ""

            cand_base = f"{base_rel}/{spec_rest}".strip("/") if base_rel else spec_rest.strip("/")
            candidates = [
                f"{cand_base}.py",
                f"{cand_base}/__init__.py",
                f"{cand_base}.ts",
                f"{cand_base}.tsx",
                f"{cand_base}.js",
                f"{cand_base}/index.ts",
                f"{cand_base}/index.js",
            ]
            for cand in candidates:
                norm_c = cand.lstrip("/")
                if norm_c in self._symbols_by_file:
                    return norm_c

        # 2. Package-style or absolute import (e.g. "service", "app.models", "utils")
        spec_slash = specifier.replace(".", "/").strip("/")
        direct_candidates = [
            f"{spec_slash}.py",
            f"{spec_slash}/__init__.py",
            f"{spec_slash}.ts",
            f"{spec_slash}.tsx",
            f"{spec_slash}.js",
            f"{spec_slash}/index.ts",
            f"{spec_slash}/index.js",
        ]
        # Also relative to caller dir
        if norm_caller_dir:
            direct_candidates.extend([
                f"{norm_caller_dir}/{spec_slash}.py",
                f"{norm_caller_dir}/{spec_slash}/__init__.py",
                f"{norm_caller_dir}/{spec_slash}.ts",
                f"{norm_caller_dir}/{spec_slash}.tsx",
                f"{norm_caller_dir}/{spec_slash}.js",
            ])

        for cand in direct_candidates:
            if cand in self._symbols_by_file:
                return cand

        # Match by filename suffix in known files
        target_name = spec_slash.split("/")[-1]
        for f in self._symbols_by_file:
            stem = Path(f).stem
            if stem == target_name or f.endswith(f"/{target_name}.py"):
                return f

        return None

    def _resolve_cross_references(self) -> None:
        """
        Cross-references raw AST calls and imports against known internal symbol definitions.
        Applies strict 3-state resolution:
        - VERIFIED: Statically proven target definition (local definition, explicit import, or qualified namespace).
        - CANDIDATE: Plausible target (e.g. imported module exports it, or unique repo symbol without import proof).
        - UNRESOLVED: Insufficient evidence, shadowed identifier, or foreign/unimported symbol.
        """
        imports_internal_by_file: dict[str, set[str]] = (
            {f.id: set(f.imports_internal) for f in self.analysis.files}
            if self.analysis
            else {}
        )
        for ref in self._raw_references:
            # 1. Imports resolution
            if ref.reference_kind in (ReferenceKind.IMPORT, ReferenceKind.REEXPORT):
                target_file = self._resolve_module_specifier(ref.file_path, ref.module_specifier)
                if target_file and target_file in self._symbols_by_file:
                    tgt_syms = self._symbols_by_file[target_file]
                    matched = next((s for s in tgt_syms if s.name == ref.symbol_name), None)
                    if matched is None and ref.symbol_name != "*":
                        # Check for barrel re-export in target_file (e.g. index.ts or __init__.py)
                        reexp_cands = [
                            r for r in self._imports_by_file[target_file]
                            if ((r.alias_name or r.symbol_name) == ref.symbol_name or r.symbol_name == "*")
                        ]
                        for reexp in reexp_cands:
                            reexp_target = self._resolve_module_specifier(target_file, reexp.module_specifier)
                            if reexp_target and reexp_target in self._symbols_by_file:
                                reexp_orig = reexp.symbol_name if reexp.symbol_name != "*" else ref.symbol_name
                                matched_re = next((s for s in self._symbols_by_file[reexp_target] if s.name == reexp_orig), None)
                                if matched_re is not None:
                                    matched = matched_re
                                    break

                    if matched is not None:
                        ref.is_verified = True
                        ref.resolution_status = ResolutionStatus.VERIFIED
                        ref.target_symbol_id = matched.id
                        ref.target_file_path = matched.file_path
                        ref.confidence_reason = (
                            f"Verified import from '{target_file}' (definition at line {matched.line_start})"
                        )
                        matched.verified_references.append(ref)
                    else:
                        ref.is_verified = False
                        ref.resolution_status = (
                            ResolutionStatus.CANDIDATE if ref.symbol_name == "*" else ResolutionStatus.UNRESOLVED
                        )
                        ref.confidence_reason = (
                            f"Wildcard import from '{target_file}'"
                            if ref.symbol_name == "*"
                            else f"Unresolved import: symbol '{ref.symbol_name}' not defined in '{target_file}'"
                        )
                else:
                    ref.is_verified = False
                    ref.resolution_status = ResolutionStatus.UNRESOLVED
                    ref.confidence_reason = (
                        f"Unresolved import: module '{ref.module_specifier}' could not be resolved internally"
                    )
                continue

            # 2. Calls resolution
            if ref.reference_kind == ReferenceKind.CALL:
                # A. Local Shadowing Check
                if "shadows symbol" in ref.confidence_reason:
                    ref.is_verified = False
                    ref.resolution_status = ResolutionStatus.UNRESOLVED
                    continue

                # B. Local definition in same file
                if ref.qualifier is None:
                    local_cands = [s for s in self._symbols_by_file[ref.file_path] if s.name == ref.symbol_name]
                    top_level = next((s for s in local_cands if s.container_name is None), None)
                    if top_level is not None:
                        ref.is_verified = True
                        ref.resolution_status = ResolutionStatus.VERIFIED
                        ref.target_symbol_id = top_level.id
                        ref.target_file_path = top_level.file_path
                        ref.confidence_reason = f"Statically verified local call within '{ref.file_path}'"
                        top_level.verified_references.append(ref)
                        continue
                elif ref.qualifier in ("self", "cls"):
                    local_methods = [
                        s for s in self._symbols_by_file[ref.file_path]
                        if s.name == ref.symbol_name and s.container_name == ref.source_symbol_name
                    ]
                    if local_methods:
                        m = local_methods[0]
                        ref.is_verified = True
                        ref.resolution_status = ResolutionStatus.VERIFIED
                        ref.target_symbol_id = m.id
                        ref.target_file_path = m.file_path
                        ref.confidence_reason = f"Statically verified member call 'self.{ref.symbol_name}' in '{ref.source_symbol_name}'"
                        m.verified_references.append(ref)
                        continue

                # C. Explicit Imports in caller file
                file_imports = self._imports_by_file[ref.file_path]

                # C1: Call by alias (e.g. from service import Engine as CoreEngine; e = CoreEngine())
                aliased_imp = next((imp for imp in file_imports if imp.alias_name == ref.symbol_name), None)
                if aliased_imp is not None:
                    tgt_file = self._resolve_module_specifier(ref.file_path, aliased_imp.module_specifier)
                    if tgt_file and tgt_file in self._symbols_by_file:
                        orig_sym = next((s for s in self._symbols_by_file[tgt_file] if s.name == aliased_imp.symbol_name), None)
                        if orig_sym is not None:
                            ref.is_verified = True
                            ref.resolution_status = ResolutionStatus.VERIFIED
                            ref.target_symbol_id = orig_sym.id
                            ref.target_file_path = orig_sym.file_path
                            ref.confidence_reason = (
                                f"Statically verified aliased import ('{ref.symbol_name}' -> '{orig_sym.name}') from '{tgt_file}'"
                            )
                            orig_sym.verified_references.append(ref)
                            continue

                # C2: Direct import (e.g. from service import Engine; e = Engine())
                direct_imp = next((imp for imp in file_imports if imp.symbol_name == ref.symbol_name and not imp.alias_name), None)
                if direct_imp is not None:
                    tgt_file = self._resolve_module_specifier(ref.file_path, direct_imp.module_specifier)
                    if tgt_file and tgt_file in self._symbols_by_file:
                        tgt_sym = next((s for s in self._symbols_by_file[tgt_file] if s.name == ref.symbol_name), None)
                        if tgt_sym is None:
                            reexp_cands = [
                                r for r in self._imports_by_file[tgt_file]
                                if ((r.alias_name or r.symbol_name) == ref.symbol_name or r.symbol_name == "*")
                            ]
                            for reexp in reexp_cands:
                                reexp_target = self._resolve_module_specifier(tgt_file, reexp.module_specifier)
                                if reexp_target and reexp_target in self._symbols_by_file:
                                    reexp_orig = reexp.symbol_name if reexp.symbol_name != "*" else ref.symbol_name
                                    matched_re = next((s for s in self._symbols_by_file[reexp_target] if s.name == reexp_orig), None)
                                    if matched_re is not None:
                                        tgt_sym = matched_re
                                        break
                        if tgt_sym is not None:
                            ref.is_verified = True
                            ref.resolution_status = ResolutionStatus.VERIFIED
                            ref.target_symbol_id = tgt_sym.id
                            ref.target_file_path = tgt_sym.file_path
                            ref.confidence_reason = f"Statically verified explicit import of '{ref.symbol_name}' from '{tgt_file}'"
                            tgt_sym.verified_references.append(ref)
                            continue

                # C3: Qualified namespace call: obj.method() where obj was imported as module
                if ref.qualifier:
                    qual_imp = next((imp for imp in file_imports if (imp.alias_name or imp.symbol_name) == ref.qualifier), None)
                    if qual_imp is not None:
                        tgt_file = self._resolve_module_specifier(ref.file_path, qual_imp.module_specifier or qual_imp.symbol_name)
                        if tgt_file and tgt_file in self._symbols_by_file:
                            tgt_sym = next((s for s in self._symbols_by_file[tgt_file] if s.name == ref.symbol_name), None)
                            if tgt_sym is not None:
                                ref.is_verified = True
                                ref.resolution_status = ResolutionStatus.VERIFIED
                                ref.target_symbol_id = tgt_sym.id
                                ref.target_file_path = tgt_sym.file_path
                                ref.confidence_reason = f"Statically verified qualified call '{ref.qualifier}.{ref.symbol_name}' from '{tgt_file}'"
                                tgt_sym.verified_references.append(ref)
                                continue

                # C4: Wildcard imports (e.g. from service import *; e = Engine())
                # Must be classified as CANDIDATE, never VERIFIED (lacks explicit static proof)
                wildcard_imps = [imp for imp in file_imports if imp.symbol_name == "*"]
                wildcard_resolved = False
                for w_imp in wildcard_imps:
                    tgt_file = self._resolve_module_specifier(ref.file_path, w_imp.module_specifier)
                    if tgt_file and tgt_file in self._symbols_by_file:
                        tgt_sym = next((s for s in self._symbols_by_file[tgt_file] if s.name == ref.symbol_name), None)
                        if tgt_sym is not None:
                            ref.is_verified = False
                            ref.resolution_status = ResolutionStatus.CANDIDATE
                            ref.target_symbol_id = tgt_sym.id
                            ref.target_file_path = tgt_sym.file_path
                            ref.confidence_reason = (
                                f"Candidate: matched symbol '{ref.symbol_name}' defined in wildcard-imported module '{tgt_file}', but lacks explicit static import"
                            )
                            tgt_sym.candidate_references.append(ref)
                            wildcard_resolved = True
                            break
                if wildcard_resolved:
                    continue

                # D. Dependency Graph / Candidate Resolution
                candidates = self._symbols_by_name.get(ref.symbol_name, [])
                if not candidates:
                    ref.is_verified = False
                    ref.resolution_status = ResolutionStatus.UNRESOLVED
                    ref.confidence_reason = f"Unresolved: symbol '{ref.symbol_name}' not defined in repository"
                    continue

                if self.analysis is not None:
                    internal_imps = imports_internal_by_file.get(ref.file_path)
                    if internal_imps is not None:
                        imported_cands = [c for c in candidates if c.file_path in internal_imps]
                        if len(imported_cands) == 1:
                            c = imported_cands[0]
                            ref.is_verified = False
                            ref.resolution_status = ResolutionStatus.CANDIDATE
                            ref.target_symbol_id = c.id
                            ref.target_file_path = c.file_path
                            ref.confidence_reason = (
                                f"Candidate: module '{ref.file_path}' imports '{c.file_path}' which defines '{ref.symbol_name}', but call is unqualified"
                            )
                            c.candidate_references.append(ref)
                        elif len(imported_cands) > 1:
                            ref.is_verified = False
                            ref.resolution_status = ResolutionStatus.CANDIDATE
                            ref.confidence_reason = f"Ambiguous candidate: multiple imported modules define '{ref.symbol_name}'"
                            for c in imported_cands:
                                c.candidate_references.append(ref)
                        else:
                            # Not imported in dependency graph -> UNRESOLVED (Never assume verified just because unique!)
                            ref.is_verified = False
                            ref.resolution_status = ResolutionStatus.UNRESOLVED
                            ref.confidence_reason = (
                                f"Unresolved: module '{ref.file_path}' has no import or dependency link to '{candidates[0].file_path}' defining '{ref.symbol_name}'"
                            )
                    else:
                        ref.is_verified = False
                        ref.resolution_status = ResolutionStatus.UNRESOLVED
                        ref.confidence_reason = f"Unresolved: module '{ref.file_path}' not found in dependency graph"
                else:
                    # Without dependency graph, single candidate is at best CANDIDATE, never VERIFIED
                    if len(candidates) == 1:
                        c = candidates[0]
                        ref.is_verified = False
                        ref.resolution_status = ResolutionStatus.CANDIDATE
                        ref.target_symbol_id = c.id
                        ref.target_file_path = c.file_path
                        ref.confidence_reason = (
                            f"Candidate: unique repository symbol '{ref.symbol_name}' in '{c.file_path}', but no explicit import verified"
                        )
                        c.candidate_references.append(ref)
                    else:
                        ref.is_verified = False
                        ref.resolution_status = ResolutionStatus.UNRESOLVED
                        ref.confidence_reason = (
                            f"Ambiguous: {len(candidates)} definitions of '{ref.symbol_name}' exist without import linking"
                        )

    def get_by_id(self, symbol_id: str) -> SymbolDefinition | None:
        """Retrieves an exact symbol definition by its deterministic ID."""
        return self._symbols_by_id.get(symbol_id)

    def find_by_name(
        self,
        name: str,
        kind: SymbolKind | str | None = None,
        file_path: str | None = None,
        container: str | None = None,
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
                n_low = name.lower()
                candidates = [s for s in self._symbols_by_id.values() if n_low in s.name.lower()]

        results: list[SymbolDefinition] = []
        for sym in candidates:
            if kind_str and sym.kind.value != kind_str:
                continue
            if norm_path and not (sym.file_path == norm_path or sym.file_path.endswith(norm_path)):
                continue
            if container and sym.container_name != container:
                continue
            results.append(sym)
        return results

    def find_by_file(self, file_path: str) -> list[SymbolDefinition]:
        norm_path = file_path.replace("\\", "/").lstrip("/")
        return list(self._symbols_by_file.get(norm_path, []))

    def get_references_in_file(self, file_path: str) -> list[SymbolReference]:
        """Returns all cross-references originating from the given file."""
        norm_path = file_path.replace("\\", "/").lstrip("/")
        return [r for r in self._raw_references if r.file_path == norm_path or r.file_path.endswith(f"/{norm_path}")]

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
