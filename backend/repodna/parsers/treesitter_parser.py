"""Tree-sitter and AST parsers for supported programming languages."""

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
    summary = {
        "Python": _TS_AVAILABLE.get("python", "python-stdlib-ast") + " + stdlib ast",
        "TypeScript / TSX": _TS_AVAILABLE.get("typescript", "static-ast-fallback"),
        "JavaScript / JSX": _TS_AVAILABLE.get("javascript", "static-ast-fallback"),
        "Go": _TS_AVAILABLE.get("go", "static-ast-fallback"),
        "Rust": _TS_AVAILABLE.get("rust", "static-ast-fallback"),
        "C / C++ / Java / C#": "static-include-import-scanner",
    }
    return summary


def _node_text(source_bytes: bytes, node: Any) -> str:
    return source_bytes[node.start_byte : node.end_byte].decode("utf-8", errors="replace")


def _strip_quotes(raw: str) -> str:
    s = raw.strip()
    if len(s) >= 2 and s[0] in ("'", '"', "`") and s[-1] == s[0]:
        return s[1:-1]
    return s


def _parse_python(content: str, source_bytes: bytes) -> tuple[list[RawImportStatement], list[SymbolItem], str]:
    _init_treesitter_parsers()
    imports: list[RawImportStatement] = []
    symbols: list[SymbolItem] = []
    engine_name = "tree-sitter-python + stdlib-ast" if "python" in _TS_PARSERS else "stdlib-ast"

    # If tree-sitter-python is loaded, parse CST first to extract symbol locations even on partial syntax
    ts_parser = _TS_PARSERS.get("python")
    ts_symbols_found = False
    if ts_parser is not None:
        try:
            tree = ts_parser.parse(source_bytes)
            stack = [tree.root_node]
            while stack:
                node = stack.pop()
                if node.type in ("function_definition", "class_definition"):
                    name_node = node.child_by_field_name("name")
                    if name_node is not None:
                        kind = "class" if node.type == "class_definition" else "function"
                        symbols.append(
                            SymbolItem(
                                name=_node_text(source_bytes, name_node),
                                kind=kind,
                                line=node.start_point[0] + 1,
                            )
                        )
                        ts_symbols_found = True
                stack.extend(reversed(node.children))
        except Exception:
            pass

    # Use Python's AST for exact import resolution (relative levels, aliases, dynamic __import__)
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
                            is_relative=False,
                            relative_level=0,
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
            elif isinstance(node, ast.Call):
                # Check for dynamic __import__(...) or importlib.import_module(...)
                func_name = ""
                if isinstance(node.func, ast.Name):
                    func_name = node.func.id
                elif isinstance(node.func, ast.Attribute):
                    func_name = node.func.attr
                if func_name in ("__import__", "import_module"):
                    arg_val = "<dynamic_expression>"
                    is_dyn = True
                    if node.args and isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str):
                        arg_val = node.args[0].value
                        is_dyn = False
                    imports.append(
                        RawImportStatement(
                            module_specifier=arg_val,
                            imported_names=[func_name],
                            line=getattr(node, "lineno", 1),
                            is_relative=arg_val.startswith("."),
                            relative_level=len(arg_val) - len(arg_val.lstrip(".")) if arg_val.startswith(".") else 0,
                            is_dynamic=is_dyn,
                        )
                    )
            elif not ts_symbols_found and isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                kind = "class" if isinstance(node, ast.ClassDef) else "function"
                symbols.append(SymbolItem(name=node.name, kind=kind, line=getattr(node, "lineno", 1)))
    except SyntaxError:
        # Fallback regex when scanning Python 2 or syntax-error files
        for m in re.finditer(r"^\s*(?:from\s+([.\w]+)\s+import\s+([^\n#]+)|import\s+([\w.,\s]+))", content, re.MULTILINE):
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

    return imports, symbols[:60], engine_name


def _parse_js_ts_treesitter(
    content: str, source_bytes: bytes, parser_key: str
) -> tuple[list[RawImportStatement], list[SymbolItem], str]:
    _init_treesitter_parsers()
    imports: list[RawImportStatement] = []
    symbols: list[SymbolItem] = []
    ts_parser = _TS_PARSERS.get(parser_key)

    if ts_parser is not None:
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
                    if fn_text in ("require", "import") or fn_node.type == "import":
                        named_args = [c for c in args_node.named_children if c.type != "comment"]
                        if named_args:
                            first_arg = named_args[0]
                            if first_arg.type == "string":
                                spec = _strip_quotes(_node_text(source_bytes, first_arg))
                                if spec:
                                    imports.append(
                                        RawImportStatement(
                                            module_specifier=spec,
                                            imported_names=[fn_text],
                                            line=line_no,
                                            is_relative=spec.startswith("."),
                                        )
                                    )
                            else:
                                imports.append(
                                    RawImportStatement(
                                        module_specifier=_node_text(source_bytes, first_arg)[:60],
                                        imported_names=[fn_text],
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

    # Fallback regex if tree-sitter unavailable
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
                        imports.append(RawImportStatement(module_specifier=spec, line=line_no))
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

    for m in re.finditer(r'"([^"\n]+)"', content):
        imports.append(RawImportStatement(module_specifier=m.group(1), line=1))
    return imports, symbols, "regex-fallback"


def _parse_rust_treesitter(
    content: str, source_bytes: bytes
) -> tuple[list[RawImportStatement], list[SymbolItem], str]:
    _init_treesitter_parsers()
    imports: list[RawImportStatement] = []
    symbols: list[SymbolItem] = []
    ts_parser = _TS_PARSERS.get("rust")

    if ts_parser is not None:
        tree = ts_parser.parse(source_bytes)
        stack = [tree.root_node]
        while stack:
            node = stack.pop()
            line_no = node.start_point[0] + 1
            if node.type == "use_declaration":
                arg_node = node.child_by_field_name("argument")
                raw_use = _node_text(source_bytes, arg_node if arg_node else node)
                raw_use = raw_use.removeprefix("use ").removesuffix(";").strip()
                if raw_use:
                    imports.append(
                        RawImportStatement(
                            module_specifier=raw_use,
                            line=line_no,
                            is_relative=raw_use.startswith(("crate::", "super::", "self::")),
                        )
                    )
            elif node.type == "mod_item":
                name_node = node.child_by_field_name("name")
                body_node = node.child_by_field_name("body")
                if name_node is not None:
                    mod_name = _node_text(source_bytes, name_node)
                    if body_node is None:
                        imports.append(
                            RawImportStatement(
                                module_specifier=f"self::{mod_name}",
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

    return imports, symbols, "static-scanner"


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
