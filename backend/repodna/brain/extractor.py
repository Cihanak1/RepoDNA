"""Tree-sitter deep symbol and reference extractor for RepoDNA Repository Brain."""

from __future__ import annotations

import ast
from typing import Any

from repodna.brain.evidence import extract_evidence_snippet
from repodna.brain.models import (
    EvidenceReference,
    EvidenceType,
    ReferenceKind,
    ResolutionStatus,
    SymbolDefinition,
    SymbolKind,
    SymbolReference,
)
from repodna.parsers.base import detect_language
from repodna.parsers.treesitter_parser import (
    _TS_PARSERS,
    _init_treesitter_parsers,
    _node_text,
)
from repodna.schemas.models import LanguageSupportLevel


def _extract_signature(content: str, line_start: int, line_end: int) -> str:
    """Extracts the first 1-3 lines representing function/class declaration signature."""
    lines = content.splitlines()
    if 1 <= line_start <= len(lines):
        chunk_lines = lines[line_start - 1 : min(len(lines), line_start + 3)]
        sig = " ".join(line.strip() for line in chunk_lines)
        if len(sig) > 160:
            sig = sig[:157] + "..."
        return sig
    return ""


def _extract_docstring(lines: list[str], line_start: int, line_end: int) -> str | None:
    """Extracts first docstring comment immediately inside or preceding the definition."""
    if not (1 <= line_start <= len(lines)):
        return None
    for i in range(line_start, min(len(lines), line_start + 4)):
        line = lines[i].strip()
        if line.startswith(('"""', "'''")):
            doc = line.strip("\"'").strip()
            if doc:
                return doc[:200]
        elif line.startswith(("//", "/*", "*")):
            doc = line.lstrip("/*").strip()
            if doc:
                return doc[:200]
    return None


class DeepSymbolExtractor:
    """Extracts high-fidelity symbols, signatures, containers, imports, and reference calls."""

    @classmethod
    def extract_file_symbols(
        cls,
        file_path: str,
        content: str,
        revision: str | None = "WORKING_TREE",
    ) -> tuple[list[SymbolDefinition], list[SymbolReference], list[EvidenceReference]]:
        """
        Extracts verified symbols, calls, imports, and evidence references for a single file.
        Returns:
            (symbols, references, evidence_items)
        """
        rev = revision or "WORKING_TREE"
        norm_path = file_path.replace("\\", "/").lstrip("/")
        source_bytes = content.encode("utf-8")
        filename = norm_path.rsplit("/", 1)[-1]
        ext = "." + filename.rsplit(".", 1)[-1] if "." in filename else ""
        lang, support_lvl, _ = detect_language(filename, ext)

        _init_treesitter_parsers()

        if lang == "Python":
            return cls._extract_python(norm_path, content, source_bytes, rev, support_lvl)
        elif lang in ("TypeScript", "TypeScript (TSX)", "JavaScript", "JavaScript (JSX)"):
            parser_key = (
                "tsx"
                if "TSX" in lang
                else "typescript"
                if "TypeScript" in lang
                else "javascript"
            )
            return cls._extract_js_ts(norm_path, content, source_bytes, rev, lang, parser_key, support_lvl)
        elif lang == "Go":
            return cls._extract_go(norm_path, content, source_bytes, rev, support_lvl)
        elif lang == "Rust":
            return cls._extract_rust(norm_path, content, source_bytes, rev, support_lvl)
        else:
            return cls._extract_generic(norm_path, content, rev, lang, support_lvl)

    @classmethod
    def _extract_python(
        cls,
        file_path: str,
        content: str,
        source_bytes: bytes,
        revision: str,
        support_lvl: LanguageSupportLevel,
    ) -> tuple[list[SymbolDefinition], list[SymbolReference], list[EvidenceReference]]:
        symbols: list[SymbolDefinition] = []
        references: list[SymbolReference] = []
        evidence_items: list[EvidenceReference] = []
        lines = content.splitlines()

        ts_parser = _TS_PARSERS.get("python")
        if ts_parser is not None:
            try:
                tree = ts_parser.parse(source_bytes)

                def visit(
                    node: Any,
                    current_container: str | None,
                    local_shadows: set[str],
                ) -> None:
                    ntype = node.type
                    line_start = node.start_point[0] + 1
                    line_end = node.end_point[0] + 1
                    col_start = node.start_point[1]
                    col_end = node.end_point[1]

                    next_container = current_container
                    scope_shadows = set(local_shadows)

                    if ntype == "class_definition":
                        name_node = node.child_by_field_name("name")
                        if name_node is not None:
                            cname = _node_text(source_bytes, name_node).strip()
                            next_container = cname
                            sig = _extract_signature(content, line_start, line_end)
                            doc = _extract_docstring(lines, line_start, line_end)
                            sym_id = SymbolDefinition.generate_id(file_path, cname, SymbolKind.CLASS, line_start, current_container)
                            ev_id = EvidenceReference.generate_id(revision, file_path, line_start, line_end, EvidenceType.SYMBOL_DEFINITION, cname)

                            snippet, c_hash = extract_evidence_snippet(content, line_start, line_end)
                            ev = EvidenceReference(
                                evidence_id=ev_id,
                                repository_revision=revision,
                                file_path=file_path,
                                line_start=line_start,
                                line_end=line_end,
                                evidence_type=EvidenceType.SYMBOL_DEFINITION,
                                symbol_name=cname,
                                symbol_kind=SymbolKind.CLASS,
                                support_level=support_lvl,
                                confidence_reason=f"Tree-sitter Python verified class definition '{cname}'",
                                code_snippet=snippet,
                                content_hash=c_hash,
                            )
                            evidence_items.append(ev)

                            sym = SymbolDefinition(
                                id=sym_id,
                                name=cname,
                                kind=SymbolKind.CLASS,
                                file_path=file_path,
                                line_start=line_start,
                                line_end=line_end,
                                column_start=col_start,
                                column_end=col_end,
                                language="Python",
                                container_name=current_container,
                                signature=sig,
                                docstring=doc,
                                is_exported=not cname.startswith("_"),
                                evidence_id=ev_id,
                            )
                            symbols.append(sym)

                    elif ntype in ("function_definition", "decorated_definition"):
                        target_node = node
                        if ntype == "decorated_definition":
                            fn_child = node.child_by_field_name("definition")
                            if fn_child is not None:
                                target_node = fn_child

                        if target_node.type == "function_definition":
                            name_node = target_node.child_by_field_name("name")
                            if name_node is not None:
                                fname = _node_text(source_bytes, name_node).strip()
                                kind = SymbolKind.METHOD if current_container else SymbolKind.FUNCTION
                                sig = _extract_signature(content, line_start, line_end)
                                doc = _extract_docstring(lines, line_start, line_end)
                                sym_id = SymbolDefinition.generate_id(file_path, fname, kind, line_start, current_container)
                                ev_id = EvidenceReference.generate_id(revision, file_path, line_start, line_end, EvidenceType.SYMBOL_DEFINITION, fname)

                                snippet, c_hash = extract_evidence_snippet(content, line_start, line_end)
                                ev = EvidenceReference(
                                    evidence_id=ev_id,
                                    repository_revision=revision,
                                    file_path=file_path,
                                    line_start=line_start,
                                    line_end=line_end,
                                    evidence_type=EvidenceType.SYMBOL_DEFINITION,
                                    symbol_name=fname,
                                    symbol_kind=kind,
                                    support_level=support_lvl,
                                    confidence_reason=f"Tree-sitter Python verified {kind.value} definition '{fname}'" + (f" in class '{current_container}'" if current_container else ""),
                                    code_snippet=snippet,
                                    content_hash=c_hash,
                                )
                                evidence_items.append(ev)

                                sym = SymbolDefinition(
                                    id=sym_id,
                                    name=fname,
                                    kind=kind,
                                    file_path=file_path,
                                    line_start=line_start,
                                    line_end=line_end,
                                    column_start=col_start,
                                    column_end=col_end,
                                    language="Python",
                                    container_name=current_container,
                                    signature=sig,
                                    docstring=doc,
                                    is_exported=not fname.startswith("_"),
                                    evidence_id=ev_id,
                                )
                                symbols.append(sym)

                                # Extract parameter names to detect local shadowing inside function body
                                params_node = target_node.child_by_field_name("parameters")
                                if params_node is not None:
                                    for pchild in params_node.children:
                                        ptext = _node_text(source_bytes, pchild).strip()
                                        pident = ptext.split(":")[0].split("=")[0].strip()
                                        if pident.isidentifier() and pident not in ("self", "cls"):
                                            scope_shadows.add(pident)

                    elif ntype == "assignment":
                        left_node = node.child_by_field_name("left")
                        if left_node is not None:
                            ltext = _node_text(source_bytes, left_node).strip()
                            if ltext.isidentifier():
                                scope_shadows.add(ltext)

                    elif ntype == "import_statement":
                        # e.g. import os, sys as system
                        for child in node.children:
                            if child.type == "dotted_name":
                                mname = _node_text(source_bytes, child).strip()
                                sym_part = mname.split(".")[-1]
                                references.append(
                                    SymbolReference(
                                        file_path=file_path,
                                        line=line_start,
                                        column=col_start,
                                        symbol_name=sym_part,
                                        reference_kind=ReferenceKind.IMPORT,
                                        module_specifier=mname,
                                        source_symbol_name=current_container,
                                        is_verified=False,
                                        resolution_status=ResolutionStatus.UNRESOLVED,
                                        confidence_reason=f"Import statement 'import {mname}'",
                                    )
                                )
                            elif child.type == "aliased_import":
                                oname_node = child.child_by_field_name("name")
                                alias_node = child.child_by_field_name("alias")
                                if oname_node and alias_node:
                                    oname = _node_text(source_bytes, oname_node).strip()
                                    aname = _node_text(source_bytes, alias_node).strip()
                                    references.append(
                                        SymbolReference(
                                            file_path=file_path,
                                            line=line_start,
                                            column=col_start,
                                            symbol_name=oname.split(".")[-1],
                                            alias_name=aname,
                                            reference_kind=ReferenceKind.IMPORT,
                                            module_specifier=oname,
                                            source_symbol_name=current_container,
                                            is_verified=False,
                                            resolution_status=ResolutionStatus.UNRESOLVED,
                                            confidence_reason=f"Aliased import 'import {oname} as {aname}'",
                                        )
                                    )

                    elif ntype == "import_from_statement":
                        # e.g. from service import Engine as CoreEngine, Helper
                        mod_node = None
                        for child in node.children:
                            if child.type in ("dotted_name", "relative_import"):
                                mod_node = child
                                break
                        mod_name = _node_text(source_bytes, mod_node).strip() if mod_node else ""
                        for child in node.children:
                            if child == mod_node or child.type in ("from", "import", ","):
                                continue
                            if child.type == "dotted_name":
                                sname = _node_text(source_bytes, child).strip()
                                references.append(
                                    SymbolReference(
                                        file_path=file_path,
                                        line=line_start,
                                        column=col_start,
                                        symbol_name=sname,
                                        reference_kind=ReferenceKind.IMPORT,
                                        module_specifier=mod_name,
                                        source_symbol_name=current_container,
                                        is_verified=False,
                                        resolution_status=ResolutionStatus.UNRESOLVED,
                                        confidence_reason=f"Import statement 'from {mod_name} import {sname}'",
                                    )
                                )
                            elif child.type == "aliased_import":
                                oname_node = child.child_by_field_name("name")
                                alias_node = child.child_by_field_name("alias")
                                if oname_node and alias_node:
                                    oname = _node_text(source_bytes, oname_node).strip()
                                    aname = _node_text(source_bytes, alias_node).strip()
                                    references.append(
                                        SymbolReference(
                                            file_path=file_path,
                                            line=line_start,
                                            column=col_start,
                                            symbol_name=oname,
                                            alias_name=aname,
                                            reference_kind=ReferenceKind.IMPORT,
                                            module_specifier=mod_name,
                                            source_symbol_name=current_container,
                                            is_verified=False,
                                            resolution_status=ResolutionStatus.UNRESOLVED,
                                            confidence_reason=f"Aliased import 'from {mod_name} import {oname} as {aname}'",
                                        )
                                    )
                            elif child.type in ("wildcard_import", "*") or _node_text(source_bytes, child).strip() == "*":
                                references.append(
                                    SymbolReference(
                                        file_path=file_path,
                                        line=line_start,
                                        column=col_start,
                                        symbol_name="*",
                                        reference_kind=ReferenceKind.IMPORT,
                                        module_specifier=mod_name,
                                        source_symbol_name=current_container,
                                        is_verified=False,
                                        resolution_status=ResolutionStatus.UNRESOLVED,
                                        confidence_reason=f"Wildcard import 'from {mod_name} import *'",
                                    )
                                )

                    elif ntype == "call":
                        fn_node = node.child_by_field_name("function")
                        if fn_node is not None:
                            fn_text = _node_text(source_bytes, fn_node).strip()
                            qualifier = None
                            call_name = fn_text
                            if "." in fn_text:
                                parts = fn_text.rsplit(".", 1)
                                qualifier = parts[0]
                                call_name = parts[1]

                            if call_name and call_name.isidentifier():
                                # Check if locally shadowed
                                is_shadowed = (qualifier is None and call_name in scope_shadows)
                                conf_msg = (
                                    f"Local variable or parameter '{call_name}' shadows symbol in '{current_container or 'function'}'"
                                    if is_shadowed
                                    else "AST call expression pending resolution"
                                )
                                references.append(
                                    SymbolReference(
                                        file_path=file_path,
                                        line=line_start,
                                        column=col_start,
                                        symbol_name=call_name,
                                        qualifier=qualifier,
                                        reference_kind=ReferenceKind.CALL,
                                        source_symbol_name=current_container,
                                        is_verified=False,
                                        resolution_status=ResolutionStatus.UNRESOLVED,
                                        confidence_reason=conf_msg,
                                    )
                                )

                    for child in node.children:
                        visit(child, next_container, scope_shadows)

                visit(tree.root_node, None, set())
                if symbols or references:
                    return symbols, references, evidence_items
            except Exception:
                pass

        # Fallback to stdlib ast
        try:
            py_ast = ast.parse(content)
            for node in py_ast.body:
                line_start = getattr(node, "lineno", 1)
                line_end = getattr(node, "end_lineno", line_start)
                snippet, c_hash = extract_evidence_snippet(content, line_start, line_end)

                if isinstance(node, ast.ClassDef):
                    cname = node.name
                    doc = ast.get_docstring(node)
                    sym_id = SymbolDefinition.generate_id(file_path, cname, SymbolKind.CLASS, line_start)
                    ev_id = EvidenceReference.generate_id(revision, file_path, line_start, line_end, EvidenceType.SYMBOL_DEFINITION, cname)
                    evidence_items.append(
                        EvidenceReference(
                            evidence_id=ev_id,
                            repository_revision=revision,
                            file_path=file_path,
                            line_start=line_start,
                            line_end=line_end,
                            evidence_type=EvidenceType.SYMBOL_DEFINITION,
                            symbol_name=cname,
                            symbol_kind=SymbolKind.CLASS,
                            support_level=support_lvl,
                            confidence_reason=f"Python stdlib AST verified class '{cname}'",
                            code_snippet=snippet,
                            content_hash=c_hash,
                        )
                    )
                    symbols.append(
                        SymbolDefinition(
                            id=sym_id,
                            name=cname,
                            kind=SymbolKind.CLASS,
                            file_path=file_path,
                            line_start=line_start,
                            line_end=line_end,
                            language="Python",
                            docstring=doc[:200] if doc else None,
                            evidence_id=ev_id,
                        )
                    )
                    for item in node.body:
                        if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                            m_start = getattr(item, "lineno", line_start)
                            m_end = getattr(item, "end_lineno", m_start)
                            m_snip, m_hash = extract_evidence_snippet(content, m_start, m_end)
                            m_id = SymbolDefinition.generate_id(file_path, item.name, SymbolKind.METHOD, m_start, cname)
                            m_ev = EvidenceReference.generate_id(revision, file_path, m_start, m_end, EvidenceType.SYMBOL_DEFINITION, item.name)
                            evidence_items.append(
                                EvidenceReference(
                                    evidence_id=m_ev,
                                    repository_revision=revision,
                                    file_path=file_path,
                                    line_start=m_start,
                                    line_end=m_end,
                                    evidence_type=EvidenceType.SYMBOL_DEFINITION,
                                    symbol_name=item.name,
                                    symbol_kind=SymbolKind.METHOD,
                                    support_level=support_lvl,
                                    confidence_reason=f"Python stdlib AST verified method '{item.name}' in class '{cname}'",
                                    code_snippet=m_snip,
                                    content_hash=m_hash,
                                )
                            )
                            symbols.append(
                                SymbolDefinition(
                                    id=m_id,
                                    name=item.name,
                                    kind=SymbolKind.METHOD,
                                    file_path=file_path,
                                    line_start=m_start,
                                    line_end=m_end,
                                    language="Python",
                                    container_name=cname,
                                    docstring=ast.get_docstring(item),
                                    evidence_id=m_ev,
                                )
                            )
                elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    fname = node.name
                    doc = ast.get_docstring(node)
                    sym_id = SymbolDefinition.generate_id(file_path, fname, SymbolKind.FUNCTION, line_start)
                    ev_id = EvidenceReference.generate_id(revision, file_path, line_start, line_end, EvidenceType.SYMBOL_DEFINITION, fname)
                    evidence_items.append(
                        EvidenceReference(
                            evidence_id=ev_id,
                            repository_revision=revision,
                            file_path=file_path,
                            line_start=line_start,
                            line_end=line_end,
                            evidence_type=EvidenceType.SYMBOL_DEFINITION,
                            symbol_name=fname,
                            symbol_kind=SymbolKind.FUNCTION,
                            support_level=support_lvl,
                            confidence_reason=f"Python stdlib AST verified function '{fname}'",
                            code_snippet=snippet,
                            content_hash=c_hash,
                        )
                    )
                    symbols.append(
                        SymbolDefinition(
                            id=sym_id,
                            name=fname,
                            kind=SymbolKind.FUNCTION,
                            file_path=file_path,
                            line_start=line_start,
                            line_end=line_end,
                            language="Python",
                            docstring=doc[:200] if doc else None,
                            evidence_id=ev_id,
                        )
                    )
                elif isinstance(node, ast.Import):
                    for alias in node.names:
                        references.append(
                            SymbolReference(
                                file_path=file_path,
                                line=line_start,
                                symbol_name=alias.name.split(".")[-1],
                                alias_name=alias.asname,
                                module_specifier=alias.name,
                                reference_kind=ReferenceKind.IMPORT,
                                is_verified=False,
                                resolution_status=ResolutionStatus.UNRESOLVED,
                                confidence_reason=f"Python stdlib AST import '{alias.name}'",
                            )
                        )
                elif isinstance(node, ast.ImportFrom):
                    mod = node.module or ""
                    for alias in node.names:
                        references.append(
                            SymbolReference(
                                file_path=file_path,
                                line=line_start,
                                symbol_name=alias.name,
                                alias_name=alias.asname,
                                module_specifier=mod,
                                reference_kind=ReferenceKind.IMPORT,
                                is_verified=False,
                                resolution_status=ResolutionStatus.UNRESOLVED,
                                confidence_reason=f"Python stdlib AST from '{mod}' import '{alias.name}'",
                            )
                        )

            for walk_node in ast.walk(py_ast):
                if isinstance(walk_node, ast.Call):
                    c_line = getattr(walk_node, "lineno", 1)
                    if isinstance(walk_node.func, ast.Name):
                        references.append(
                            SymbolReference(
                                file_path=file_path,
                                line=c_line,
                                symbol_name=walk_node.func.id,
                                reference_kind=ReferenceKind.CALL,
                                is_verified=False,
                                resolution_status=ResolutionStatus.UNRESOLVED,
                            )
                        )
                    elif isinstance(walk_node.func, ast.Attribute):
                        qual = walk_node.func.value.id if isinstance(walk_node.func.value, ast.Name) else None
                        references.append(
                            SymbolReference(
                                file_path=file_path,
                                line=c_line,
                                symbol_name=walk_node.func.attr,
                                qualifier=qual,
                                reference_kind=ReferenceKind.CALL,
                                is_verified=False,
                                resolution_status=ResolutionStatus.UNRESOLVED,
                            )
                        )

            return symbols, references, evidence_items
        except Exception:
            return symbols, references, evidence_items

    @classmethod
    def _extract_js_ts(
        cls,
        file_path: str,
        content: str,
        source_bytes: bytes,
        revision: str,
        language: str,
        parser_key: str,
        support_lvl: LanguageSupportLevel,
    ) -> tuple[list[SymbolDefinition], list[SymbolReference], list[EvidenceReference]]:
        symbols: list[SymbolDefinition] = []
        references: list[SymbolReference] = []
        evidence_items: list[EvidenceReference] = []
        lines = content.splitlines()

        ts_parser = _TS_PARSERS.get(parser_key)
        if ts_parser is not None:
            try:
                tree = ts_parser.parse(source_bytes)

                def visit(
                    node: Any,
                    current_container: str | None,
                    local_shadows: set[str],
                ) -> None:
                    ntype = node.type
                    line_start = node.start_point[0] + 1
                    line_end = node.end_point[0] + 1
                    col_start = node.start_point[1]
                    col_end = node.end_point[1]

                    next_container = current_container
                    scope_shadows = set(local_shadows)

                    if ntype == "class_declaration":
                        name_node = node.child_by_field_name("name")
                        if name_node is not None:
                            cname = _node_text(source_bytes, name_node).strip()
                            next_container = cname
                            sig = _extract_signature(content, line_start, line_end)
                            doc = _extract_docstring(lines, line_start, line_end)
                            sym_id = SymbolDefinition.generate_id(file_path, cname, SymbolKind.CLASS, line_start, current_container)
                            ev_id = EvidenceReference.generate_id(revision, file_path, line_start, line_end, EvidenceType.SYMBOL_DEFINITION, cname)

                            snippet, c_hash = extract_evidence_snippet(content, line_start, line_end)
                            ev = EvidenceReference(
                                evidence_id=ev_id,
                                repository_revision=revision,
                                file_path=file_path,
                                line_start=line_start,
                                line_end=line_end,
                                evidence_type=EvidenceType.SYMBOL_DEFINITION,
                                symbol_name=cname,
                                symbol_kind=SymbolKind.CLASS,
                                support_level=support_lvl,
                                confidence_reason=f"Tree-sitter {language} verified class definition '{cname}'",
                                code_snippet=snippet,
                                content_hash=c_hash,
                            )
                            evidence_items.append(ev)

                            symbols.append(
                                SymbolDefinition(
                                    id=sym_id,
                                    name=cname,
                                    kind=SymbolKind.CLASS,
                                    file_path=file_path,
                                    line_start=line_start,
                                    line_end=line_end,
                                    column_start=col_start,
                                    column_end=col_end,
                                    language=language,
                                    container_name=current_container,
                                    signature=sig,
                                    docstring=doc,
                                    evidence_id=ev_id,
                                )
                            )

                    elif ntype == "interface_declaration":
                        name_node = node.child_by_field_name("name")
                        if name_node is not None:
                            iname = _node_text(source_bytes, name_node).strip()
                            sig = _extract_signature(content, line_start, line_end)
                            doc = _extract_docstring(lines, line_start, line_end)
                            sym_id = SymbolDefinition.generate_id(file_path, iname, SymbolKind.INTERFACE, line_start, current_container)
                            ev_id = EvidenceReference.generate_id(revision, file_path, line_start, line_end, EvidenceType.SYMBOL_DEFINITION, iname)
                            snippet, c_hash = extract_evidence_snippet(content, line_start, line_end)
                            evidence_items.append(
                                EvidenceReference(
                                    evidence_id=ev_id,
                                    repository_revision=revision,
                                    file_path=file_path,
                                    line_start=line_start,
                                    line_end=line_end,
                                    evidence_type=EvidenceType.SYMBOL_DEFINITION,
                                    symbol_name=iname,
                                    symbol_kind=SymbolKind.INTERFACE,
                                    support_level=support_lvl,
                                    confidence_reason=f"Tree-sitter {language} verified interface '{iname}'",
                                    code_snippet=snippet,
                                    content_hash=c_hash,
                                )
                            )
                            symbols.append(
                                SymbolDefinition(
                                    id=sym_id,
                                    name=iname,
                                    kind=SymbolKind.INTERFACE,
                                    file_path=file_path,
                                    line_start=line_start,
                                    line_end=line_end,
                                    column_start=col_start,
                                    column_end=col_end,
                                    language=language,
                                    container_name=current_container,
                                    signature=sig,
                                    docstring=doc,
                                    evidence_id=ev_id,
                                )
                            )

                    elif ntype == "type_alias_declaration":
                        name_node = node.child_by_field_name("name")
                        if name_node is not None:
                            tname = _node_text(source_bytes, name_node).strip()
                            sym_id = SymbolDefinition.generate_id(file_path, tname, SymbolKind.TYPE, line_start, current_container)
                            ev_id = EvidenceReference.generate_id(revision, file_path, line_start, line_end, EvidenceType.SYMBOL_DEFINITION, tname)
                            snippet, c_hash = extract_evidence_snippet(content, line_start, line_end)
                            evidence_items.append(
                                EvidenceReference(
                                    evidence_id=ev_id,
                                    repository_revision=revision,
                                    file_path=file_path,
                                    line_start=line_start,
                                    line_end=line_end,
                                    evidence_type=EvidenceType.SYMBOL_DEFINITION,
                                    symbol_name=tname,
                                    symbol_kind=SymbolKind.TYPE,
                                    support_level=support_lvl,
                                    confidence_reason=f"Tree-sitter {language} verified type '{tname}'",
                                    code_snippet=snippet,
                                    content_hash=c_hash,
                                )
                            )
                            symbols.append(
                                SymbolDefinition(
                                    id=sym_id,
                                    name=tname,
                                    kind=SymbolKind.TYPE,
                                    file_path=file_path,
                                    line_start=line_start,
                                    line_end=line_end,
                                    column_start=col_start,
                                    column_end=col_end,
                                    language=language,
                                    container_name=current_container,
                                    signature=_extract_signature(content, line_start, line_end),
                                    evidence_id=ev_id,
                                )
                            )

                    elif ntype == "method_definition":
                        name_node = node.child_by_field_name("name")
                        if name_node is not None:
                            mname = _node_text(source_bytes, name_node).strip()
                            sym_id = SymbolDefinition.generate_id(file_path, mname, SymbolKind.METHOD, line_start, current_container)
                            ev_id = EvidenceReference.generate_id(revision, file_path, line_start, line_end, EvidenceType.SYMBOL_DEFINITION, mname)
                            snippet, c_hash = extract_evidence_snippet(content, line_start, line_end)
                            evidence_items.append(
                                EvidenceReference(
                                    evidence_id=ev_id,
                                    repository_revision=revision,
                                    file_path=file_path,
                                    line_start=line_start,
                                    line_end=line_end,
                                    evidence_type=EvidenceType.SYMBOL_DEFINITION,
                                    symbol_name=mname,
                                    symbol_kind=SymbolKind.METHOD,
                                    support_level=support_lvl,
                                    confidence_reason=f"Tree-sitter {language} verified method '{mname}' in '{current_container}'",
                                    code_snippet=snippet,
                                    content_hash=c_hash,
                                )
                            )
                            symbols.append(
                                SymbolDefinition(
                                    id=sym_id,
                                    name=mname,
                                    kind=SymbolKind.METHOD,
                                    file_path=file_path,
                                    line_start=line_start,
                                    line_end=line_end,
                                    column_start=col_start,
                                    column_end=col_end,
                                    language=language,
                                    container_name=current_container,
                                    signature=_extract_signature(content, line_start, line_end),
                                    docstring=_extract_docstring(lines, line_start, line_end),
                                    evidence_id=ev_id,
                                )
                            )

                    elif ntype == "function_declaration":
                        name_node = node.child_by_field_name("name")
                        if name_node is not None:
                            fname = _node_text(source_bytes, name_node).strip()
                            sym_id = SymbolDefinition.generate_id(file_path, fname, SymbolKind.FUNCTION, line_start, current_container)
                            ev_id = EvidenceReference.generate_id(revision, file_path, line_start, line_end, EvidenceType.SYMBOL_DEFINITION, fname)
                            snippet, c_hash = extract_evidence_snippet(content, line_start, line_end)
                            evidence_items.append(
                                EvidenceReference(
                                    evidence_id=ev_id,
                                    repository_revision=revision,
                                    file_path=file_path,
                                    line_start=line_start,
                                    line_end=line_end,
                                    evidence_type=EvidenceType.SYMBOL_DEFINITION,
                                    symbol_name=fname,
                                    symbol_kind=SymbolKind.FUNCTION,
                                    support_level=support_lvl,
                                    confidence_reason=f"Tree-sitter {language} verified function '{fname}'",
                                    code_snippet=snippet,
                                    content_hash=c_hash,
                                )
                            )
                            symbols.append(
                                SymbolDefinition(
                                    id=sym_id,
                                    name=fname,
                                    kind=SymbolKind.FUNCTION,
                                    file_path=file_path,
                                    line_start=line_start,
                                    line_end=line_end,
                                    column_start=col_start,
                                    column_end=col_end,
                                    language=language,
                                    container_name=current_container,
                                    signature=_extract_signature(content, line_start, line_end),
                                    docstring=_extract_docstring(lines, line_start, line_end),
                                    evidence_id=ev_id,
                                )
                            )

                    elif ntype == "import_statement":
                        # e.g. import { User, Auth as CoreAuth } from './auth';
                        src_node = node.child_by_field_name("source")
                        raw_src = _node_text(source_bytes, src_node).strip().strip("'\"`") if src_node else ""
                        for child in node.children:
                            if child.type == "import_clause":
                                for clause_child in child.children:
                                    if clause_child.type == "identifier":
                                        default_name = _node_text(source_bytes, clause_child).strip()
                                        references.append(
                                            SymbolReference(
                                                file_path=file_path,
                                                line=line_start,
                                                column=col_start,
                                                symbol_name=default_name,
                                                reference_kind=ReferenceKind.IMPORT,
                                                module_specifier=raw_src,
                                                source_symbol_name=current_container,
                                                is_verified=False,
                                                resolution_status=ResolutionStatus.UNRESOLVED,
                                                confidence_reason=f"Default import '{default_name}' from '{raw_src}'",
                                            )
                                        )
                                    elif clause_child.type == "named_imports":
                                        for spec in clause_child.children:
                                            if spec.type == "import_specifier":
                                                n_node = spec.child_by_field_name("name")
                                                a_node = spec.child_by_field_name("alias")
                                                sname = _node_text(source_bytes, n_node).strip() if n_node else ""
                                                aname = _node_text(source_bytes, a_node).strip() if a_node else None
                                                if sname:
                                                    references.append(
                                                        SymbolReference(
                                                            file_path=file_path,
                                                            line=line_start,
                                                            column=col_start,
                                                            symbol_name=sname,
                                                            alias_name=aname,
                                                            reference_kind=ReferenceKind.IMPORT,
                                                            module_specifier=raw_src,
                                                            source_symbol_name=current_container,
                                                            is_verified=False,
                                                            resolution_status=ResolutionStatus.UNRESOLVED,
                                                            confidence_reason=f"Imported '{sname}'" + (f" as '{aname}'" if aname else "") + f" from '{raw_src}'",
                                                        )
                                                    )
                                    elif clause_child.type == "namespace_import":
                                        ns_text = _node_text(source_bytes, clause_child).strip()
                                        ns_name = ns_text.split()[-1]
                                        references.append(
                                            SymbolReference(
                                                file_path=file_path,
                                                line=line_start,
                                                column=col_start,
                                                symbol_name=ns_name,
                                                reference_kind=ReferenceKind.IMPORT,
                                                module_specifier=raw_src,
                                                source_symbol_name=current_container,
                                                is_verified=False,
                                                resolution_status=ResolutionStatus.UNRESOLVED,
                                                confidence_reason=f"Namespace import '* as {ns_name}' from '{raw_src}'",
                                            )
                                        )

                    elif ntype == "export_statement":
                        src_node = node.child_by_field_name("source")
                        raw_src = _node_text(source_bytes, src_node).strip().strip("'\"`") if src_node else ""
                        if raw_src:
                            for child in node.children:
                                if child.type == "export_clause":
                                    for spec in child.children:
                                        if spec.type == "export_specifier":
                                            n_node = spec.child_by_field_name("name")
                                            a_node = spec.child_by_field_name("alias")
                                            sname = _node_text(source_bytes, n_node).strip() if n_node else ""
                                            aname = _node_text(source_bytes, a_node).strip() if a_node else None
                                            if sname:
                                                references.append(
                                                    SymbolReference(
                                                        file_path=file_path,
                                                        line=line_start,
                                                        column=col_start,
                                                        symbol_name=sname,
                                                        alias_name=aname,
                                                        reference_kind=ReferenceKind.REEXPORT,
                                                        module_specifier=raw_src,
                                                        source_symbol_name=current_container,
                                                        is_verified=False,
                                                        resolution_status=ResolutionStatus.UNRESOLVED,
                                                        confidence_reason=f"Barrel export '{sname}' from '{raw_src}'",
                                                    )
                                                )
                                elif child.type in ("*", "star_export") or _node_text(source_bytes, child).strip() == "*":
                                    references.append(
                                        SymbolReference(
                                            file_path=file_path,
                                            line=line_start,
                                            column=col_start,
                                            symbol_name="*",
                                            reference_kind=ReferenceKind.REEXPORT,
                                            module_specifier=raw_src,
                                            source_symbol_name=current_container,
                                            is_verified=False,
                                            resolution_status=ResolutionStatus.UNRESOLVED,
                                            confidence_reason=f"Wildcard barrel export '* from {raw_src}'",
                                        )
                                    )

                    elif ntype == "call_expression":
                        fn_node = node.child_by_field_name("function")
                        if fn_node is not None:
                            fn_text = _node_text(source_bytes, fn_node).strip()
                            qualifier = None
                            call_name = fn_text
                            if "." in fn_text:
                                parts = fn_text.rsplit(".", 1)
                                qualifier = parts[0]
                                call_name = parts[1]

                            if call_name and call_name.isidentifier():
                                is_shadowed = (qualifier is None and call_name in scope_shadows)
                                conf_msg = (
                                    f"Local variable or parameter '{call_name}' shadows symbol"
                                    if is_shadowed
                                    else f"Tree-sitter {language} call expression"
                                )
                                references.append(
                                    SymbolReference(
                                        file_path=file_path,
                                        line=line_start,
                                        column=col_start,
                                        symbol_name=call_name,
                                        qualifier=qualifier,
                                        reference_kind=ReferenceKind.CALL,
                                        source_symbol_name=current_container,
                                        is_verified=False,
                                        resolution_status=ResolutionStatus.UNRESOLVED,
                                        confidence_reason=conf_msg,
                                    )
                                )

                    for child in node.children:
                        visit(child, next_container, scope_shadows)

                visit(tree.root_node, None, set())
            except Exception:
                pass

        return symbols, references, evidence_items

    @classmethod
    def _extract_go(
        cls,
        file_path: str,
        content: str,
        source_bytes: bytes,
        revision: str,
        support_lvl: LanguageSupportLevel,
    ) -> tuple[list[SymbolDefinition], list[SymbolReference], list[EvidenceReference]]:
        symbols: list[SymbolDefinition] = []
        references: list[SymbolReference] = []
        evidence_items: list[EvidenceReference] = []

        ts_parser = _TS_PARSERS.get("go")
        if ts_parser is not None:
            try:
                tree = ts_parser.parse(source_bytes)
                for node in tree.root_node.children:
                    line_start = node.start_point[0] + 1
                    line_end = node.end_point[0] + 1
                    snippet, c_hash = extract_evidence_snippet(content, line_start, line_end)
                    if node.type in ("function_declaration", "method_declaration"):
                        name_node = node.child_by_field_name("name")
                        if name_node is not None:
                            fname = _node_text(source_bytes, name_node).strip()
                            kind = SymbolKind.METHOD if node.type == "method_declaration" else SymbolKind.FUNCTION
                            sym_id = SymbolDefinition.generate_id(file_path, fname, kind, line_start)
                            ev_id = EvidenceReference.generate_id(revision, file_path, line_start, line_end, EvidenceType.SYMBOL_DEFINITION, fname)
                            evidence_items.append(
                                EvidenceReference(
                                    evidence_id=ev_id,
                                    repository_revision=revision,
                                    file_path=file_path,
                                    line_start=line_start,
                                    line_end=line_end,
                                    evidence_type=EvidenceType.SYMBOL_DEFINITION,
                                    symbol_name=fname,
                                    symbol_kind=kind,
                                    support_level=support_lvl,
                                    confidence_reason=f"Tree-sitter Go verified {kind.value} '{fname}'",
                                    code_snippet=snippet,
                                    content_hash=c_hash,
                                )
                            )
                            symbols.append(
                                SymbolDefinition(
                                    id=sym_id,
                                    name=fname,
                                    kind=kind,
                                    file_path=file_path,
                                    line_start=line_start,
                                    line_end=line_end,
                                    language="Go",
                                    signature=_extract_signature(content, line_start, line_end),
                                    evidence_id=ev_id,
                                )
                            )
                    elif node.type == "type_declaration":
                        for child in node.children:
                            if child.type == "type_spec":
                                name_node = child.child_by_field_name("name")
                                if name_node is not None:
                                    tname = _node_text(source_bytes, name_node).strip()
                                    sym_id = SymbolDefinition.generate_id(file_path, tname, SymbolKind.TYPE, line_start)
                                    ev_id = EvidenceReference.generate_id(revision, file_path, line_start, line_end, EvidenceType.SYMBOL_DEFINITION, tname)
                                    evidence_items.append(
                                        EvidenceReference(
                                            evidence_id=ev_id,
                                            repository_revision=revision,
                                            file_path=file_path,
                                            line_start=line_start,
                                            line_end=line_end,
                                            evidence_type=EvidenceType.SYMBOL_DEFINITION,
                                            symbol_name=tname,
                                            symbol_kind=SymbolKind.TYPE,
                                            support_level=support_lvl,
                                            confidence_reason=f"Tree-sitter Go verified type '{tname}'",
                                            code_snippet=snippet,
                                            content_hash=c_hash,
                                        )
                                    )
                                    symbols.append(
                                        SymbolDefinition(
                                            id=sym_id,
                                            name=tname,
                                            kind=SymbolKind.TYPE,
                                            file_path=file_path,
                                            line_start=line_start,
                                            line_end=line_end,
                                            language="Go",
                                            signature=_extract_signature(content, line_start, line_end),
                                            evidence_id=ev_id,
                                        )
                                    )
            except Exception:
                pass
        return symbols, references, evidence_items

    @classmethod
    def _extract_rust(
        cls,
        file_path: str,
        content: str,
        source_bytes: bytes,
        revision: str,
        support_lvl: LanguageSupportLevel,
    ) -> tuple[list[SymbolDefinition], list[SymbolReference], list[EvidenceReference]]:
        symbols: list[SymbolDefinition] = []
        references: list[SymbolReference] = []
        evidence_items: list[EvidenceReference] = []

        ts_parser = _TS_PARSERS.get("rust")
        if ts_parser is not None:
            try:
                tree = ts_parser.parse(source_bytes)
                for node in tree.root_node.children:
                    line_start = node.start_point[0] + 1
                    line_end = node.end_point[0] + 1
                    snippet, c_hash = extract_evidence_snippet(content, line_start, line_end)
                    if node.type in ("function_item", "struct_item", "enum_item", "trait_item"):
                        name_node = node.child_by_field_name("name")
                        if name_node is not None:
                            sname = _node_text(source_bytes, name_node).strip()
                            kind = (
                                SymbolKind.STRUCT if node.type == "struct_item"
                                else SymbolKind.INTERFACE if node.type == "trait_item"
                                else SymbolKind.FUNCTION
                            )
                            sym_id = SymbolDefinition.generate_id(file_path, sname, kind, line_start)
                            ev_id = EvidenceReference.generate_id(revision, file_path, line_start, line_end, EvidenceType.SYMBOL_DEFINITION, sname)
                            evidence_items.append(
                                EvidenceReference(
                                    evidence_id=ev_id,
                                    repository_revision=revision,
                                    file_path=file_path,
                                    line_start=line_start,
                                    line_end=line_end,
                                    evidence_type=EvidenceType.SYMBOL_DEFINITION,
                                    symbol_name=sname,
                                    symbol_kind=kind,
                                    support_level=support_lvl,
                                    confidence_reason=f"Tree-sitter Rust verified {kind.value} '{sname}'",
                                    code_snippet=snippet,
                                    content_hash=c_hash,
                                )
                            )
                            symbols.append(
                                SymbolDefinition(
                                    id=sym_id,
                                    name=sname,
                                    kind=kind,
                                    file_path=file_path,
                                    line_start=line_start,
                                    line_end=line_end,
                                    language="Rust",
                                    signature=_extract_signature(content, line_start, line_end),
                                    evidence_id=ev_id,
                                )
                            )
            except Exception:
                pass
        return symbols, references, evidence_items

    @classmethod
    def _extract_generic(
        cls,
        file_path: str,
        content: str,
        revision: str,
        language: str,
        support_lvl: LanguageSupportLevel,
    ) -> tuple[list[SymbolDefinition], list[SymbolReference], list[EvidenceReference]]:
        """Fallback for partial-static or unsupported languages: does not hallucinate false symbols."""
        return [], [], []
