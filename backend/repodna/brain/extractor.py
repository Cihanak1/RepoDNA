"""Tree-sitter deep symbol and reference extractor for RepoDNA Repository Brain."""

from __future__ import annotations

import ast
import hashlib
from typing import Any

from repodna.brain.models import (
    EvidenceReference,
    EvidenceType,
    ReferenceKind,
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
        # Grab up to 3 lines or until the colon/brace
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
    # Check lines right below declaration
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
    """Extracts high-fidelity symbols, signatures, containers, and reference calls."""

    @classmethod
    def extract_file_symbols(
        cls,
        file_path: str,
        content: str,
        revision: str = "WORKING_TREE",
    ) -> tuple[list[SymbolDefinition], list[SymbolReference], list[EvidenceReference]]:
        """
        Extracts verified symbols, calls, and evidence references for a single file.
        Returns:
            (symbols, references, evidence_items)
        """
        source_bytes = content.encode("utf-8")
        filename = file_path.rsplit("/", 1)[-1]
        ext = "." + filename.rsplit(".", 1)[-1] if "." in filename else ""
        lang, support_lvl, _ = detect_language(filename, ext)

        _init_treesitter_parsers()

        if lang == "Python":
            return cls._extract_python(file_path, content, source_bytes, revision, support_lvl)
        elif lang in ("TypeScript", "TypeScript (TSX)", "JavaScript", "JavaScript (JSX)"):
            parser_key = (
                "tsx"
                if "TSX" in lang
                else "typescript"
                if "TypeScript" in lang
                else "javascript"
            )
            return cls._extract_js_ts(file_path, content, source_bytes, revision, lang, parser_key, support_lvl)
        elif lang == "Go":
            return cls._extract_go(file_path, content, source_bytes, revision, support_lvl)
        elif lang == "Rust":
            return cls._extract_rust(file_path, content, source_bytes, revision, support_lvl)
        else:
            return cls._extract_generic(file_path, content, revision, lang, support_lvl)

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
                # We do a hierarchical DFS traversal to maintain container scope
                def visit(node: Any, current_container: str | None) -> None:
                    ntype = node.type
                    line_start = node.start_point[0] + 1
                    line_end = node.end_point[0] + 1
                    col_start = node.start_point[1]
                    col_end = node.end_point[1]

                    next_container = current_container

                    if ntype == "class_definition":
                        name_node = node.child_by_field_name("name")
                        if name_node is not None:
                            cname = _node_text(source_bytes, name_node).strip()
                            next_container = cname
                            sig = _extract_signature(content, line_start, line_end)
                            doc = _extract_docstring(lines, line_start, line_end)
                            sym_id = SymbolDefinition.generate_id(file_path, cname, SymbolKind.CLASS, line_start, current_container)
                            ev_id = EvidenceReference.generate_id(revision, file_path, line_start, line_end, EvidenceType.SYMBOL_DEFINITION, cname)

                            snippet = "\n".join(lines[line_start - 1 : min(len(lines), line_start + 5)])
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
                                content_hash=hashlib.sha256(snippet.encode("utf-8")).hexdigest()[:16],
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

                                snippet = "\n".join(lines[line_start - 1 : min(len(lines), line_start + 5)])
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
                                    content_hash=hashlib.sha256(snippet.encode("utf-8")).hexdigest()[:16],
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

                    elif ntype == "call":
                        fn_node = node.child_by_field_name("function")
                        if fn_node is not None:
                            fn_text = _node_text(source_bytes, fn_node).strip()
                            call_name = fn_text.split(".")[-1]
                            if call_name and call_name.isidentifier():
                                references.append(
                                    SymbolReference(
                                        file_path=file_path,
                                        line=line_start,
                                        column=col_start,
                                        symbol_name=call_name,
                                        reference_kind=ReferenceKind.CALL,
                                        source_symbol_name=current_container,
                                        is_verified=True,
                                        confidence_reason="Tree-sitter Python call expression",
                                    )
                                )

                    for child in node.children:
                        visit(child, next_container)

                visit(tree.root_node, None)
                if symbols:
                    return symbols, references, evidence_items
            except Exception:
                pass

        # Fallback to stdlib ast
        try:
            py_ast = ast.parse(content)
            for node in py_ast.body:
                line_start = getattr(node, "lineno", 1)
                line_end = getattr(node, "end_lineno", line_start)
                if isinstance(node, ast.ClassDef):
                    cname = node.name
                    doc = ast.get_docstring(node)
                    sym_id = SymbolDefinition.generate_id(file_path, cname, SymbolKind.CLASS, line_start)
                    ev_id = EvidenceReference.generate_id(revision, file_path, line_start, line_end, EvidenceType.SYMBOL_DEFINITION, cname)
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
                            m_id = SymbolDefinition.generate_id(file_path, item.name, SymbolKind.METHOD, m_start, cname)
                            m_ev = EvidenceReference.generate_id(revision, file_path, m_start, m_end, EvidenceType.SYMBOL_DEFINITION, item.name)
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

                def visit(node: Any, current_container: str | None) -> None:
                    ntype = node.type
                    line_start = node.start_point[0] + 1
                    line_end = node.end_point[0] + 1
                    col_start = node.start_point[1]
                    col_end = node.end_point[1]

                    next_container = current_container

                    if ntype == "class_declaration":
                        name_node = node.child_by_field_name("name")
                        if name_node is not None:
                            cname = _node_text(source_bytes, name_node).strip()
                            next_container = cname
                            sig = _extract_signature(content, line_start, line_end)
                            doc = _extract_docstring(lines, line_start, line_end)
                            sym_id = SymbolDefinition.generate_id(file_path, cname, SymbolKind.CLASS, line_start, current_container)
                            ev_id = EvidenceReference.generate_id(revision, file_path, line_start, line_end, EvidenceType.SYMBOL_DEFINITION, cname)

                            snippet = "\n".join(lines[line_start - 1 : min(len(lines), line_start + 4)])
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
                                content_hash=hashlib.sha256(snippet.encode("utf-8")).hexdigest()[:16],
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

                    elif ntype == "call_expression":
                        fn_node = node.child_by_field_name("function")
                        if fn_node is not None:
                            fn_text = _node_text(source_bytes, fn_node).strip()
                            call_name = fn_text.split(".")[-1]
                            if call_name and call_name.isidentifier():
                                references.append(
                                    SymbolReference(
                                        file_path=file_path,
                                        line=line_start,
                                        column=col_start,
                                        symbol_name=call_name,
                                        reference_kind=ReferenceKind.CALL,
                                        source_symbol_name=current_container,
                                        is_verified=True,
                                        confidence_reason=f"Tree-sitter {language} call expression",
                                    )
                                )

                    for child in node.children:
                        visit(child, next_container)

                visit(tree.root_node, None)
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
                    if node.type in ("function_declaration", "method_declaration"):
                        name_node = node.child_by_field_name("name")
                        if name_node is not None:
                            fname = _node_text(source_bytes, name_node).strip()
                            kind = SymbolKind.METHOD if node.type == "method_declaration" else SymbolKind.FUNCTION
                            sym_id = SymbolDefinition.generate_id(file_path, fname, kind, line_start)
                            ev_id = EvidenceReference.generate_id(revision, file_path, line_start, line_end, EvidenceType.SYMBOL_DEFINITION, fname)
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
