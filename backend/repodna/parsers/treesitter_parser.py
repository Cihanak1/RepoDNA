"""Tree-sitter CST/AST parsers for supported programming languages with error-tolerant recovery."""

from __future__ import annotations

import ast
import re
from typing import Any

from repodna.parsers.base import (
    ParsedFileData,
    RawImportStatement,
    count_lines,
    detect_language,
)
from repodna.schemas.models import LanguageSupportLevel, SymbolItem

# Lazy-loaded Tree-sitter parsers per language key
_TS_PARSERS: dict[str, Any] = {}
_TS_AVAILABLE: dict[str, str] = {}


def _init_treesitter_parsers() -> None:
    if _TS_PARSERS:
        return
    try:
        from tree_sitter import Language, Parser
    except ImportError:
        return

    loaders: list[tuple[str, str, str]] = [
        ("python", "tree_sitter_python", "language"),
        ("javascript", "tree_sitter_javascript", "language"),
        ("typescript", "tree_sitter_typescript", "language_typescript"),
        ("tsx", "tree_sitter_typescript", "language_tsx"),
        ("go", "tree_sitter_go", "language"),
        ("rust", "tree_sitter_rust", "language"),
    ]
    for key, mod_name, fn_name in loaders:
        try:
            mod = __import__(mod_name)
            lang_fn = getattr(mod, fn_name)
            ts_lang = Language(lang_fn())
            parser = Parser(ts_lang)
            _TS_PARSERS[key] = parser
            _TS_AVAILABLE[key] = f"tree-sitter ({mod_name})"
        except Exception:
            continue


def get_parser_engine_summary() -> dict[str, str]:
    _init_treesitter_parsers()
    return {
        "Python": _TS_AVAILABLE.get("python", "python-stdlib-ast"),
        "TypeScript / TSX": _TS_AVAILABLE.get("typescript", "static-ast-fallback"),
        "JavaScript / JSX": _TS_AVAILABLE.get("javascript", "static-ast-fallback"),
        "Go": _TS_AVAILABLE.get("go", "static-ast-fallback"),
        "Rust": _TS_AVAILABLE.get("rust", "static-ast-fallback"),
        "C / C++ / Java / C#": "static-include-import-scanner",
    }


def _node_text(source_bytes: bytes, node: Any) -> str:
    return source_bytes[node.start_byte : node.end_byte].decode("utf-8", errors="replace")


def _strip_quotes(raw: str) -> str:
    s = raw.strip()
    if len(s) >= 2 and s[0] in ("'", '"', "`") and s[-1] == s[0]:
        return s[1:-1]
    return s


def _parse_python(content: str, source_bytes: bytes) -> tuple[list[RawImportStatement], list[SymbolItem], str]:
    """
    Parse Python source using Tree-sitter CST in a single pass with error-tolerant recovery
    even on broken syntax files, falling back to stdlib ast if tree-sitter is unavailable.
    """
    _init_treesitter_parsers()
    imports: list[RawImportStatement] = []
    symbols: list[SymbolItem] = []

    ts_parser = _TS_PARSERS.get("python")
    if ts_parser is not None:
        try:
            tree = ts_parser.parse(source_bytes)
            stack = [tree.root_node]
            while stack:
                node = stack.pop()
                ntype = node.type
                line_no = node.start_point[0] + 1

                if ntype in ("function_definition", "class_definition"):
                    name_node = node.child_by_field_name("name")
                    if name_node is not None:
                        kind = "class" if ntype == "class_definition" else "function"
                        symbols.append(
                            SymbolItem(
                                name=_node_text(source_bytes, name_node),
                                kind=kind,
                                line=line_no,
                            )
                        )
                elif ntype == "import_statement":
                    # e.g., import os, sys as s, pkg.mod
                    for child in node.named_children:
                        if child.type == "dotted_name":
                            mod_name = _node_text(source_bytes, child).strip()
                            if mod_name:
                                imports.append(
                                    RawImportStatement(
                                        module_specifier=mod_name,
                                        imported_names=[mod_name],
                                        line=line_no,
                                    )
                                )
                        elif child.type == "aliased_import":
                            name_child = child.child_by_field_name("name")
                            alias_child = child.child_by_field_name("alias")
                            if name_child is not None:
                                mod_name = _node_text(source_bytes, name_child).strip()
                                alias_name = (
                                    _node_text(source_bytes, alias_child).strip()
                                    if alias_child is not None
                                    else mod_name
                                )
                                imports.append(
                                    RawImportStatement(
                                        module_specifier=mod_name,
                                        imported_names=[alias_name],
                                        line=line_no,
                                    )
                                )
                elif ntype == "import_from_statement":
                    # e.g., from ..pkg.mod import a, b as c  OR  from . import x
                    mod_node = node.child_by_field_name("module_name")
                    raw_mod_text = _node_text(source_bytes, mod_node).strip() if mod_node is not None else ""
                    rel_level = 0
                    mod_spec = raw_mod_text
                    if raw_mod_text.startswith("."):
                        rel_level = len(raw_mod_text) - len(raw_mod_text.lstrip("."))
                        mod_spec = raw_mod_text.lstrip(".")

                    imported_names: list[str] = []
                    for child in node.named_children:
                        if mod_node is not None and child.id == mod_node.id:
                            continue
                        if child.type == "relative_import":
                            rel_text = _node_text(source_bytes, child).strip()
                            rel_level = len(rel_text) - len(rel_text.lstrip("."))
                            mod_spec = rel_text.lstrip(".")
                        elif child.type == "dotted_name":
                            imported_names.append(_node_text(source_bytes, child).strip())
                        elif child.type == "aliased_import":
                            orig_n = child.child_by_field_name("name")
                            if orig_n is not None:
                                imported_names.append(_node_text(source_bytes, orig_n).strip())
                        elif child.type == "wildcard_import":
                            imported_names.append("*")

                    imports.append(
                        RawImportStatement(
                            module_specifier=mod_spec,
                            imported_names=imported_names,
                            line=line_no,
                            is_relative=rel_level > 0,
                            relative_level=rel_level,
                        )
                    )
                elif ntype == "call":
                    fn_node = node.child_by_field_name("function")
                    args_node = node.child_by_field_name("arguments")
                    if fn_node is not None and args_node is not None:
                        fn_text = _node_text(source_bytes, fn_node).strip()
                        if fn_text in ("__import__", "importlib.import_module", "import_module"):
                            named_args = [c for c in args_node.named_children if c.type != "comment"]
                            arg_val = "<dynamic_expression>"
                            is_dyn = True
                            if named_args and named_args[0].type == "string":
                                arg_val = _strip_quotes(_node_text(source_bytes, named_args[0]))
                                is_dyn = True
                            imports.append(
                                RawImportStatement(
                                    module_specifier=arg_val,
                                    imported_names=[fn_text.split(".")[-1]],
                                    line=line_no,
                                    is_relative=arg_val.startswith("."),
                                    relative_level=(
                                        len(arg_val) - len(arg_val.lstrip("."))
                                        if arg_val.startswith(".")
                                        else 0
                                    ),
                                    is_dynamic=is_dyn,
                                )
                            )

                stack.extend(reversed(node.children))
            return imports, symbols[:60], "tree-sitter-python"
        except Exception:
            pass

    # Fallback to stdlib ast or regex recovery when tree-sitter is unavailable
    try:
        py_tree = ast.parse(content)
        for node in ast.walk(py_tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.append(
                        RawImportStatement(
                            module_specifier=alias.name,
                            imported_names=[alias.asname or alias.name],
                            line=getattr(node, "lineno", 1),
                        )
                    )
            elif isinstance(node, ast.ImportFrom):
                mod = node.module or ""
                level = node.level or 0
                names = [alias.name for alias in node.names]
                imports.append(
                    RawImportStatement(
                        module_specifier=mod,
                        imported_names=names,
                        line=getattr(node, "lineno", 1),
                        is_relative=level > 0,
                        relative_level=level,
                    )
                )
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                kind = "class" if isinstance(node, ast.ClassDef) else "function"
                symbols.append(SymbolItem(name=node.name, kind=kind, line=getattr(node, "lineno", 1)))
        return imports, symbols[:60], "stdlib-ast"
    except (SyntaxError, ValueError, RecursionError, MemoryError):
        for m in re.finditer(
            r"^\s*(?:from\s+([.\w]+)\s+import\s+([^\n#]+)|import\s+([\w.,\s]+))",
            content,
            re.MULTILINE,
        ):
            line_no = content.count("\n", 0, m.start()) + 1
            if m.group(1):
                raw_mod = m.group(1)
                lvl = len(raw_mod) - len(raw_mod.lstrip("."))
                imports.append(
                    RawImportStatement(
                        module_specifier=raw_mod.lstrip("."),
                        imported_names=[x.strip() for x in m.group(2).split(",") if x.strip()],
                        line=line_no,
                        is_relative=lvl > 0,
                        relative_level=lvl,
                    )
                )
            elif m.group(3):
                for part in m.group(3).split(","):
                    clean = part.strip().split()[0]
                    if clean:
                        imports.append(RawImportStatement(module_specifier=clean, line=line_no))
        return imports, symbols[:60], "error-recovery-fallback"


def _parse_js_ts_treesitter(
    content: str, source_bytes: bytes, parser_key: str
) -> tuple[list[RawImportStatement], list[SymbolItem], str]:
    _init_treesitter_parsers()
    imports: list[RawImportStatement] = []
    symbols: list[SymbolItem] = []
    ts_parser = _TS_PARSERS.get(parser_key)

    if ts_parser is not None:
        try:
            tree = ts_parser.parse(source_bytes)
            stack = [tree.root_node]
            while stack:
                node = stack.pop()
                ntype = node.type
                line_no = node.start_point[0] + 1

                if ntype in ("import_statement", "export_statement"):
                    source_node = node.child_by_field_name("source")
                    if source_node is not None:
                        spec = _strip_quotes(_node_text(source_bytes, source_node))
                        if spec:
                            imports.append(
                                RawImportStatement(
                                    module_specifier=spec,
                                    imported_names=[ntype.replace("_statement", "")],
                                    line=line_no,
                                    is_relative=spec.startswith("."),
                                )
                            )
                elif ntype == "call_expression":
                    fn_node = node.child_by_field_name("function")
                    args_node = node.child_by_field_name("arguments")
                    if fn_node is not None and args_node is not None:
                        fn_text = _node_text(source_bytes, fn_node).strip()
                        is_dyn_call = fn_node.type == "import" or fn_text == "import"
                        if fn_text == "require" or is_dyn_call:
                            named_args = [c for c in args_node.named_children if c.type != "comment"]
                            if named_args:
                                first_arg = named_args[0]
                                if first_arg.type == "string":
                                    spec = _strip_quotes(_node_text(source_bytes, first_arg))
                                    if spec:
                                        imports.append(
                                            RawImportStatement(
                                                module_specifier=spec,
                                                imported_names=["import()" if is_dyn_call else "require"],
                                                line=line_no,
                                                is_relative=spec.startswith("."),
                                                is_dynamic=is_dyn_call,
                                            )
                                        )
                                else:
                                    imports.append(
                                        RawImportStatement(
                                            module_specifier=_node_text(source_bytes, first_arg)[:60],
                                            imported_names=["import()" if is_dyn_call else "require"],
                                            line=line_no,
                                            is_dynamic=True,
                                        )
                                    )
                elif ntype in (
                    "function_declaration",
                    "class_declaration",
                    "interface_declaration",
                    "type_alias_declaration",
                ):
                    name_node = node.child_by_field_name("name")
                    if name_node is not None:
                        kind_map = {
                            "function_declaration": "function",
                            "class_declaration": "class",
                            "interface_declaration": "interface",
                            "type_alias_declaration": "type",
                        }
                        symbols.append(
                            SymbolItem(
                                name=_node_text(source_bytes, name_node),
                                kind=kind_map.get(ntype, "symbol"),
                                line=line_no,
                            )
                        )
                stack.extend(reversed(node.children))
            return imports, symbols[:60], f"tree-sitter-{parser_key}"
        except Exception:
            pass

    for m in re.finditer(
        r"""(?:import|export)\s+(?:[^'"]*?\s+from\s+)?['"]([^'"]+)['"]|require\(\s*['"]([^'"]+)['"]\s*\)""",
        content,
    ):
        spec = m.group(1) or m.group(2)
        if spec:
            line_no = content.count("\n", 0, m.start()) + 1
            imports.append(
                RawImportStatement(
                    module_specifier=spec,
                    line=line_no,
                    is_relative=spec.startswith("."),
                )
            )
    return imports, symbols, "regex-fallback"


def _parse_go_treesitter(
    content: str, source_bytes: bytes
) -> tuple[list[RawImportStatement], list[SymbolItem], str]:
    _init_treesitter_parsers()
    imports: list[RawImportStatement] = []
    symbols: list[SymbolItem] = []
    ts_parser = _TS_PARSERS.get("go")

    if ts_parser is not None:
        try:
            tree = ts_parser.parse(source_bytes)
            stack = [tree.root_node]
            while stack:
                node = stack.pop()
                line_no = node.start_point[0] + 1
                if node.type == "import_spec":
                    path_node = node.child_by_field_name("path")
                    if path_node is not None:
                        spec = _strip_quotes(_node_text(source_bytes, path_node))
                        if spec:
                            imports.append(
                                RawImportStatement(
                                    module_specifier=spec,
                                    line=line_no,
                                    is_relative=spec.startswith("."),
                                )
                            )
                elif node.type in ("function_declaration", "method_declaration", "type_spec"):
                    name_node = node.child_by_field_name("name")
                    if name_node is not None:
                        kind = "type" if node.type == "type_spec" else "function"
                        symbols.append(
                            SymbolItem(
                                name=_node_text(source_bytes, name_node),
                                kind=kind,
                                line=line_no,
                            )
                        )
                stack.extend(reversed(node.children))
            return imports, symbols[:60], "tree-sitter-go"
        except Exception:
            pass

    for m in re.finditer(r'"([^"\n]+)"', content):
        imports.append(RawImportStatement(module_specifier=m.group(1), line=1))
    return imports, symbols, "regex-fallback"


def _expand_rust_use_clause(raw_use: str) -> list[str]:
    """Expand `crate::services::{auth, billing::invoice}` into individual module specifiers."""
    cleaned = raw_use.strip()
    if "{" not in cleaned or "}" not in cleaned:
        return [cleaned] if cleaned else []

    prefix, rest = cleaned.split("{", 1)
    prefix = prefix.strip().rstrip(":")
    inner = rest.rsplit("}", 1)[0]
    expanded: list[str] = []
    for item in inner.split(","):
        part = item.strip().split(" as ")[0].strip()
        if not part:
            continue
        if part == "self":
            if prefix:
                expanded.append(prefix)
        else:
            expanded.append(f"{prefix}::{part}" if prefix else part)
    return expanded


def _parse_rust_treesitter(
    content: str, source_bytes: bytes
) -> tuple[list[RawImportStatement], list[SymbolItem], str]:
    _init_treesitter_parsers()
    imports: list[RawImportStatement] = []
    symbols: list[SymbolItem] = []
    ts_parser = _TS_PARSERS.get("rust")

    if ts_parser is not None:
        try:
            tree = ts_parser.parse(source_bytes)
            stack = [tree.root_node]
            while stack:
                node = stack.pop()
                line_no = node.start_point[0] + 1
                if node.type == "use_declaration":
                    arg_node = node.child_by_field_name("argument")
                    raw_use = _node_text(source_bytes, arg_node if arg_node else node)
                    raw_use = raw_use.removeprefix("pub ").removeprefix("use ").removesuffix(";").strip()
                    for expanded_spec in _expand_rust_use_clause(raw_use):
                        imports.append(
                            RawImportStatement(
                                module_specifier=expanded_spec,
                                line=line_no,
                                is_relative=expanded_spec.startswith(("crate::", "super::", "self::")),
                            )
                        )
                elif node.type == "mod_item":
                    name_node = node.child_by_field_name("name")
                    body_node = node.child_by_field_name("body")
                    if name_node is not None:
                        mod_name = _node_text(source_bytes, name_node).strip()
                        symbols.append(SymbolItem(name=mod_name, kind="module", line=line_no))
                        if body_node is None:
                            imports.append(
                                RawImportStatement(
                                    module_specifier=f"mod::{mod_name}",
                                    imported_names=[f"mod {mod_name}"],
                                    line=line_no,
                                    is_relative=True,
                                )
                            )
                elif node.type in ("function_item", "struct_item", "enum_item", "trait_item"):
                    name_node = node.child_by_field_name("name")
                    if name_node is not None:
                        kind = node.type.removesuffix("_item")
                        symbols.append(
                            SymbolItem(
                                name=_node_text(source_bytes, name_node),
                                kind=kind,
                                line=line_no,
                            )
                        )
                stack.extend(reversed(node.children))
            return imports, symbols[:60], "tree-sitter-rust"
        except Exception:
            pass

    return imports, symbols, "regex-fallback"


def _parse_partial_static(content: str, language: str) -> tuple[list[RawImportStatement], list[SymbolItem], str]:
    imports: list[RawImportStatement] = []
    symbols: list[SymbolItem] = []

    if language in ("C", "C++", "C/C++ Header", "C++ Header"):
        for m in re.finditer(r'^\s*#\s*include\s*([<"])([^>"]+)[>"]', content, re.MULTILINE):
            bracket, header = m.group(1), m.group(2).strip()
            line_no = content.count("\n", 0, m.start()) + 1
            imports.append(
                RawImportStatement(
                    module_specifier=header,
                    line=line_no,
                    is_relative=(bracket == '"'),
                )
            )
    elif language in ("Java", "Kotlin", "C#"):
        pattern = r"^\s*(?:import|using)\s+(?:static\s+)?([A-Za-z0-9_.*]+)\s*;?"
        for m in re.finditer(pattern, content, re.MULTILINE):
            spec = m.group(1).strip()
            line_no = content.count("\n", 0, m.start()) + 1
            imports.append(RawImportStatement(module_specifier=spec, line=line_no))
        for sm in re.finditer(
            r"^\s*(?:(?:public|internal|private|protected|static|abstract|sealed|partial)\s+)*\b(class|interface|struct|enum|record)\s+([A-Za-z_][A-Za-z0-9_]*)",
            content,
            re.MULTILINE,
        ):
            line_no = content.count("\n", 0, sm.start()) + 1
            symbols.append(SymbolItem(name=sm.group(2), kind=sm.group(1), line=line_no))

    return imports, symbols[:60], "static-scanner"


def parse_source_file(filename: str, extension: str, content: str) -> ParsedFileData:
    """Parse a single text file and extract line metrics, AST imports, and symbols."""
    language, support_level, comment_prefix = detect_language(filename, extension)
    total, code, comment, blank = count_lines(content, comment_prefix)

    if support_level == LanguageSupportLevel.UNSUPPORTED:
        return ParsedFileData(
            language=language,
            support_level=support_level,
            lines_total=total,
            lines_code=code,
            lines_comment=comment,
            lines_blank=blank,
            parser_used="unsupported",
        )

    source_bytes = content.encode("utf-8", errors="replace")
    ext = extension.lower()

    if ext == ".py":
        imports, symbols, engine = _parse_python(content, source_bytes)
    elif ext == ".ts":
        imports, symbols, engine = _parse_js_ts_treesitter(content, source_bytes, "typescript")
    elif ext == ".tsx":
        imports, symbols, engine = _parse_js_ts_treesitter(content, source_bytes, "tsx")
    elif ext in (".js", ".jsx", ".mjs", ".cjs"):
        imports, symbols, engine = _parse_js_ts_treesitter(content, source_bytes, "javascript")
    elif ext == ".go":
        imports, symbols, engine = _parse_go_treesitter(content, source_bytes)
    elif ext == ".rs":
        imports, symbols, engine = _parse_rust_treesitter(content, source_bytes)
    else:
        imports, symbols, engine = _parse_partial_static(content, language)

    return ParsedFileData(
        language=language,
        support_level=support_level,
        lines_total=total,
        lines_code=code,
        lines_comment=comment,
        lines_blank=blank,
        raw_imports=imports,
        symbols=symbols,
        parser_used=engine,
    )
