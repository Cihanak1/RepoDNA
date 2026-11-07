"""Import resolution engine mapping AST imports to internal repository files or external packages."""

from __future__ import annotations

import json
import re
from pathlib import PurePosixPath

from repodna.parsers.base import RawImportStatement
from repodna.schemas.models import UnresolvedReference

JS_TS_EXTENSIONS = (".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs")
PY_EXTENSIONS = (".py",)
C_HEADER_EXTENSIONS = (".h", ".hpp", ".c", ".cpp", ".cc")

_JSON_COMMENTS_RE = re.compile(r"//.*?$|/\*.*?\*/", re.MULTILINE | re.DOTALL)
_TRAILING_COMMA_RE = re.compile(r",\s*([}\]])")


def parse_tsconfig_aliases(config_dir: str, content: str) -> dict[str, list[str]]:
    """
    Extract compilerOptions.paths and baseUrl from a tsconfig.json or jsconfig.json string.
    Returns mapping of alias_prefix -> list of repository-relative target prefixes.
    """
    aliases: dict[str, list[str]] = {}
    try:
        cleaned = _JSON_COMMENTS_RE.sub("", content)
        cleaned = _TRAILING_COMMA_RE.sub(r"\1", cleaned)
        data = json.loads(cleaned)
        if not isinstance(data, dict):
            return aliases
        compiler_opts = data.get("compilerOptions")
        if not isinstance(compiler_opts, dict):
            return aliases

        base_url = str(compiler_opts.get("baseUrl", ".")).strip()
        base_dir = PurePosixPath(config_dir) if config_dir and config_dir != "." else PurePosixPath("")
        if base_url and base_url != ".":
            base_dir = base_dir / base_url

        paths_obj = compiler_opts.get("paths")
        if isinstance(paths_obj, dict):
            for raw_pattern, raw_targets in paths_obj.items():
                if not isinstance(raw_pattern, str) or not isinstance(raw_targets, list):
                    continue
                alias_prefix = raw_pattern.removesuffix("*").rstrip("/")
                resolved_targets: list[str] = []
                for t in raw_targets:
                    if not isinstance(t, str):
                        continue
                    t_clean = t.removesuffix("*").lstrip("./").rstrip("/")
                    combined = (base_dir / t_clean).as_posix() if base_dir.as_posix() != "." else t_clean
                    combined = combined.lstrip("./").rstrip("/")
                    resolved_targets.append(combined)
                if alias_prefix and resolved_targets:
                    aliases[alias_prefix] = resolved_targets
    except Exception:
        pass
    return aliases


def parse_go_mod_module(go_mod_dir: str, content: str) -> tuple[str, str] | None:
    """
    Extract `module <module_path>` from a `go.mod` file and return (module_path, repo_relative_dir).
    """
    for line in content.splitlines():
        stripped = line.strip()
        if stripped.startswith("module "):
            parts = stripped.split()
            if len(parts) >= 2:
                mod_name = parts[1].strip().strip('"')
                norm_dir = "" if go_mod_dir == "." else go_mod_dir.strip("/")
                return (mod_name, norm_dir)
    return None


class ImportResolver:
    """Resolves raw import statements against the indexed set of repository file paths."""

    def __init__(
        self,
        all_file_ids: set[str],
        tsconfig_aliases: dict[str, list[str]] | None = None,
        go_modules: dict[str, str] | None = None,
    ) -> None:
        self.all_file_ids = all_file_ids
        self.tsconfig_aliases: dict[str, list[str]] = tsconfig_aliases or {}
        # go_modules maps module_name (e.g. "github.com/acme/app") -> repo_relative_dir (e.g. "" or "services/auth")
        self.go_modules: dict[str, str] = go_modules or {}

        self.stem_map: dict[str, str] = {}
        self.basename_map: dict[str, list[str]] = {}
        self.py_module_map: dict[str, str] = {}
        self.dir_files_map: dict[str, list[str]] = {}

        for fid in sorted(all_file_ids):
            p = PurePosixPath(fid)
            parent_str = p.parent.as_posix()
            if parent_str == ".":
                parent_str = ""
            self.dir_files_map.setdefault(parent_str, []).append(fid)
            self.basename_map.setdefault(p.name, []).append(fid)

            no_ext = p.with_suffix("").as_posix()
            self.stem_map.setdefault(no_ext, fid)

            if p.suffix.lower() == ".py":
                if p.name == "__init__.py":
                    pkg_path = parent_str.replace("/", ".")
                    if pkg_path:
                        self._register_py_suffixes(pkg_path, fid)
                else:
                    dotted = no_ext.replace("/", ".")
                    self._register_py_suffixes(dotted, fid)

    def _register_py_suffixes(self, dotted: str, fid: str) -> None:
        parts = dotted.split(".")
        self.py_module_map.setdefault(dotted, fid)
        for idx in range(1, len(parts)):
            if parts[idx - 1] in ("src", "backend", "app", "lib", "packages", "services", "apps"):
                suffix = ".".join(parts[idx:])
                self.py_module_map.setdefault(suffix, fid)
                # In monorepos like packages.pkg_a.src.mod or packages.pkg_a.mod, also register fromidx+1
                if parts[idx - 1] in ("packages", "services", "apps") and idx + 1 < len(parts):
                    sub_suffix = ".".join(parts[idx + 1 :])
                    self.py_module_map.setdefault(sub_suffix, fid)

    def resolve_for_file(
        self,
        source_file_id: str,
        language: str,
        raw_imports: list[RawImportStatement],
    ) -> tuple[list[tuple[str, RawImportStatement]], list[str], list[UnresolvedReference]]:
        """
        Resolve imports for a single file.

        Returns:
            (resolved_internal_edges, external_packages, unresolved_references)
        """
        resolved_internal: list[tuple[str, RawImportStatement]] = []
        external_pkgs: set[str] = set()
        unresolved: list[UnresolvedReference] = []

        src_path = PurePosixPath(source_file_id)
        src_dir = src_path.parent

        for imp in raw_imports:
            if imp.is_dynamic:
                # Always record dynamic_import in unresolved_imports for transparency
                unresolved.append(
                    UnresolvedReference(
                        source_file=source_file_id,
                        raw_import=imp.module_specifier,
                        line=imp.line,
                        reason="dynamic_import",
                    )
                )
                # If the dynamic import used a string literal (e.g. import('./lazy.js')), also resolve the edge!
                if imp.module_specifier and not imp.module_specifier.startswith("<"):
                    if language in ("TypeScript", "TypeScript (TSX)", "JavaScript", "JavaScript (JSX)"):
                        targets, _, _ = self._resolve_js_ts(source_file_id, src_dir, imp)
                        for t in targets:
                            if t != source_file_id:
                                resolved_internal.append((t, imp))
                continue

            if language == "Python":
                targets, ext_pkg, unres = self._resolve_python(source_file_id, src_dir, imp)
            elif language in ("TypeScript", "TypeScript (TSX)", "JavaScript", "JavaScript (JSX)"):
                targets, ext_pkg, unres = self._resolve_js_ts(source_file_id, src_dir, imp)
            elif language == "Go":
                targets, ext_pkg, unres = self._resolve_go(source_file_id, src_dir, imp)
            elif language == "Rust":
                targets, ext_pkg, unres = self._resolve_rust(source_file_id, src_dir, imp)
            else:
                targets, ext_pkg, unres = self._resolve_generic(source_file_id, src_dir, imp)

            for t in targets:
                if t != source_file_id:
                    resolved_internal.append((t, imp))
            if ext_pkg:
                external_pkgs.add(ext_pkg)
            if unres:
                unresolved.append(unres)

        return resolved_internal, sorted(external_pkgs), unresolved

    def _normalize_rel_path(self, base_dir: PurePosixPath, rel_spec: str) -> str | None:
        parts = list(base_dir.parts) if base_dir.as_posix() != "." else []
        for token in rel_spec.split("/"):
            if not token or token == ".":
                continue
            if token == "..":
                if not parts:
                    return None
                parts.pop()
            else:
                parts.append(token)
        return "/".join(parts)

    def _resolve_python(
        self, source_id: str, src_dir: PurePosixPath, imp: RawImportStatement
    ) -> tuple[list[str], str | None, UnresolvedReference | None]:
        if imp.is_relative:
            base_parts = list(src_dir.parts) if src_dir.as_posix() != "." else []
            up_steps = max(0, imp.relative_level - 1)
            if up_steps > len(base_parts):
                return (
                    [],
                    None,
                    UnresolvedReference(
                        source_file=source_id,
                        raw_import="." * imp.relative_level + imp.module_specifier,
                        line=imp.line,
                        reason="unresolvable_relative_import",
                    ),
                )
            target_base_parts = base_parts[: len(base_parts) - up_steps]
            if imp.module_specifier:
                target_base_parts.extend(imp.module_specifier.split("."))
            candidate_prefix = "/".join(target_base_parts)

            matched = self._match_py_prefix(candidate_prefix, imp.imported_names)
            if matched:
                return (matched, None, None)
            return (
                [],
                None,
                UnresolvedReference(
                    source_file=source_id,
                    raw_import="." * imp.relative_level + imp.module_specifier,
                    line=imp.line,
                    reason="unresolvable_internal_path",
                ),
            )

        spec = imp.module_specifier.strip()
        if not spec:
            return ([], None, None)

        abs_matched: list[str] = []
        for name in imp.imported_names:
            sub_dotted = f"{spec}.{name}"
            if sub_dotted in self.py_module_map:
                abs_matched.append(self.py_module_map[sub_dotted])

        if spec in self.py_module_map:
            abs_matched.append(self.py_module_map[spec])

        if abs_matched:
            return (sorted(set(abs_matched)), None, None)

        top_pkg = spec.split(".")[0]
        return ([], top_pkg, None)

    def _match_py_prefix(self, prefix: str, imported_names: list[str]) -> list[str]:
        results: list[str] = []
        for name in imported_names:
            sub_py = f"{prefix}/{name}.py" if prefix else f"{name}.py"
            sub_init = f"{prefix}/{name}/__init__.py" if prefix else f"{name}/__init__.py"
            if sub_py in self.all_file_ids:
                results.append(sub_py)
            elif sub_init in self.all_file_ids:
                results.append(sub_init)

        direct_py = f"{prefix}.py"
        direct_init = f"{prefix}/__init__.py" if prefix else "__init__.py"
        if direct_py in self.all_file_ids:
            results.append(direct_py)
        elif direct_init in self.all_file_ids:
            results.append(direct_init)

        return sorted(set(results))

    def _resolve_js_ts(
        self, source_id: str, src_dir: PurePosixPath, imp: RawImportStatement
    ) -> tuple[list[str], str | None, UnresolvedReference | None]:
        spec = imp.module_specifier.strip()
        if not spec:
            return ([], None, None)

        norm_candidates: list[str] = []
        is_alias_or_relative = False

        # 1. Check tsconfig.json / jsconfig.json path aliases first
        for alias_prefix, target_prefixes in self.tsconfig_aliases.items():
            if spec == alias_prefix or spec.startswith(alias_prefix + "/"):
                is_alias_or_relative = True
                rest = spec[len(alias_prefix) :].lstrip("/")
                for tp in target_prefixes:
                    cand = f"{tp}/{rest}".strip("/") if tp else rest
                    if cand:
                        norm_candidates.append(cand)

        # 2. Standard relative or common @/ ~/ aliases
        if spec.startswith("."):
            is_alias_or_relative = True
            norm = self._normalize_rel_path(src_dir, spec)
            if norm:
                norm_candidates.append(norm)
        elif spec.startswith(("@/", "~/")):
            is_alias_or_relative = True
            stripped = spec[2:]
            # Also check relative to current package root in a monorepo (e.g. packages/web/src/...)
            src_parts = src_dir.parts
            if len(src_parts) >= 2 and src_parts[0] in ("packages", "apps", "services"):
                pkg_root = f"{src_parts[0]}/{src_parts[1]}"
                norm_candidates.extend([f"{pkg_root}/src/{stripped}", f"{pkg_root}/{stripped}"])
            norm_candidates.extend(
                [
                    stripped,
                    f"src/{stripped}",
                    f"frontend/src/{stripped}",
                    f"app/{stripped}",
                ]
            )
        elif spec.startswith("src/"):
            is_alias_or_relative = True
            norm_candidates.extend([spec, f"frontend/{spec}"])

        # 3. Monorepo workspace package imports (e.g. "@acme/shared" -> "packages/shared/src/index")
        if not is_alias_or_relative and spec.startswith("@") and "/" in spec:
            pkg_short = spec.split("/", 1)[1]
            for root_folder in ("packages", "apps", "libs"):
                for entry_cand in (
                    f"{root_folder}/{pkg_short}/src/index",
                    f"{root_folder}/{pkg_short}/index",
                    f"{root_folder}/{pkg_short}",
                ):
                    for ext in JS_TS_EXTENSIONS:
                        if f"{entry_cand}{ext}" in self.all_file_ids:
                            return ([f"{entry_cand}{ext}"], None, None)

        if norm_candidates:
            for cand in norm_candidates:
                cand_base = cand
                for js_ext in (".js", ".jsx", ".mjs"):
                    if cand.endswith(js_ext):
                        cand_base = cand[: -len(js_ext)]
                        break

                if cand in self.all_file_ids:
                    return ([cand], None, None)
                for ext in JS_TS_EXTENSIONS:
                    if f"{cand}{ext}" in self.all_file_ids:
                        return ([f"{cand}{ext}"], None, None)
                    if f"{cand_base}{ext}" in self.all_file_ids:
                        return ([f"{cand_base}{ext}"], None, None)
                    if f"{cand}/index{ext}" in self.all_file_ids:
                        return ([f"{cand}/index{ext}"], None, None)

            return (
                [],
                None,
                UnresolvedReference(
                    source_file=source_id,
                    raw_import=spec,
                    line=imp.line,
                    reason="unresolvable_internal_path",
                ),
            )

        parts = spec.split("/")
        if spec.startswith("@") and len(parts) >= 2:
            pkg_name = f"{parts[0]}/{parts[1]}"
        else:
            pkg_name = parts[0]
        return ([], pkg_name, None)

    def _resolve_go(
        self, source_id: str, src_dir: PurePosixPath, imp: RawImportStatement
    ) -> tuple[list[str], str | None, UnresolvedReference | None]:
        spec = imp.module_specifier.strip()
        if not spec:
            return ([], None, None)

        # 1. Relative Go import
        if spec.startswith("."):
            norm = self._normalize_rel_path(src_dir, spec)
            if norm and norm in self.dir_files_map:
                go_files = [
                    f for f in self.dir_files_map[norm] if f.endswith(".go") and not f.endswith("_test.go")
                ]
                if go_files:
                    return (go_files, None, None)

        # 2. Exact go.mod module prefix match
        if self.go_modules:
            for mod_name, mod_dir in self.go_modules.items():
                if spec == mod_name or spec.startswith(mod_name + "/"):
                    sub = spec[len(mod_name) :].lstrip("/")
                    target_dir = f"{mod_dir}/{sub}".strip("/") if mod_dir else sub
                    if target_dir in self.dir_files_map:
                        go_files = [
                            f
                            for f in self.dir_files_map[target_dir]
                            if f.endswith(".go") and not f.endswith("_test.go")
                        ]
                        if go_files:
                            return (go_files, None, None)
                    return (
                        [],
                        None,
                        UnresolvedReference(
                            source_file=source_id,
                            raw_import=spec,
                            line=imp.line,
                            reason="unresolvable_internal_path",
                        ),
                    )
            return ([], spec, None)

        # 3. Fallback when no go.mod is present in repository
        parts = spec.split("/")
        for i in range(1, len(parts)):
            suffix_dir = "/".join(parts[i:])
            if suffix_dir in self.dir_files_map:
                go_files = [
                    f for f in self.dir_files_map[suffix_dir] if f.endswith(".go") and not f.endswith("_test.go")
                ]
                if go_files:
                    return (go_files, None, None)
        return ([], spec, None)

    def _resolve_rust(
        self, source_id: str, src_dir: PurePosixPath, imp: RawImportStatement
    ) -> tuple[list[str], str | None, UnresolvedReference | None]:
        spec = imp.module_specifier.strip()
        if not spec:
            return ([], None, None)

        # Find the enclosing crate's `src` directory (supports workspace crates like crates/core/src/lib.rs)
        src_parts = list(src_dir.parts) if src_dir.as_posix() != "." else []
        crate_src_dir = PurePosixPath("src")
        if "src" in src_parts:
            src_idx = len(src_parts) - 1 - src_parts[::-1].index("src")
            crate_src_dir = PurePosixPath("/".join(src_parts[: src_idx + 1]))
        elif src_dir.as_posix() != ".":
            crate_src_dir = src_dir

        # Handle `mod foo;` declaration
        if spec.startswith("mod::"):
            mod_name = spec.removeprefix("mod::").strip()
            src_file = PurePosixPath(source_id)
            search_dirs = [src_dir]
            if src_file.name not in ("lib.rs", "main.rs", "mod.rs"):
                # In Rust 2018+, `src/foo.rs` containing `mod bar;` resolves to `src/foo/bar.rs`
                search_dirs.insert(0, src_dir / src_file.stem)
            for sdir in search_dirs:
                base_str = "" if sdir.as_posix() == "." else sdir.as_posix()
                cand_rs = f"{base_str}/{mod_name}.rs".lstrip("/")
                cand_mod = f"{base_str}/{mod_name}/mod.rs".lstrip("/")
                if cand_rs in self.all_file_ids:
                    return ([cand_rs], None, None)
                if cand_mod in self.all_file_ids:
                    return ([cand_mod], None, None)
            return (
                [],
                None,
                UnresolvedReference(
                    source_file=source_id,
                    raw_import=f"mod {mod_name}",
                    line=imp.line,
                    reason="unresolvable_internal_path",
                ),
            )

        clean = spec.split("{")[0].strip().rstrip(":")
        segments = [s for s in clean.split("::") if s]
        if not segments:
            return ([], None, None)

        if segments[0] in ("crate", "self", "super"):
            base = crate_src_dir if segments[0] == "crate" else src_dir
            if segments[0] == "super" and base.as_posix() != ".":
                base = base.parent

            # Walk segments from longest prefix down to 1 to match either module file or item inside module file
            rel_segs = segments[1:]
            for length in range(len(rel_segs), 0, -1):
                sub_path = "/".join(rel_segs[:length])
                base_str = "" if base.as_posix() == "." else base.as_posix()
                cand_rs = f"{base_str}/{sub_path}.rs".lstrip("/")
                cand_mod = f"{base_str}/{sub_path}/mod.rs".lstrip("/")
                if cand_rs in self.all_file_ids:
                    return ([cand_rs], None, None)
                if cand_mod in self.all_file_ids:
                    return ([cand_mod], None, None)
            return ([], None, None)

        return ([], segments[0], None)

    def _resolve_generic(
        self, source_id: str, src_dir: PurePosixPath, imp: RawImportStatement
    ) -> tuple[list[str], str | None, UnresolvedReference | None]:
        spec = imp.module_specifier.strip()
        if not spec:
            return ([], None, None)
        norm = self._normalize_rel_path(src_dir, spec)
        if norm and norm in self.all_file_ids:
            return ([norm], None, None)
        base_name = PurePosixPath(spec).name
        if base_name in self.basename_map:
            return ([self.basename_map[base_name][0]], None, None)
        return ([], spec, None)
