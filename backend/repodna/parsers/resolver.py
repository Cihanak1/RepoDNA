"""Import resolution engine mapping AST imports to internal repository files or external packages."""

from __future__ import annotations

from pathlib import PurePosixPath

from repodna.parsers.base import RawImportStatement
from repodna.schemas.models import UnresolvedReference

JS_TS_EXTENSIONS = (".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs")
PY_EXTENSIONS = (".py",)
C_HEADER_EXTENSIONS = (".h", ".hpp", ".c", ".cpp", ".cc")


class ImportResolver:
    """Resolves raw import statements against the indexed set of repository file paths."""

    def __init__(self, all_file_ids: set[str]) -> None:
        self.all_file_ids = all_file_ids
        # Build lookup maps for fast resolution
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

            # Without extension
            no_ext = p.with_suffix("").as_posix()
            self.stem_map.setdefault(no_ext, fid)

            # Python module dotted suffixes
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
        # Register full dotted path and suffixes starting from src/backend/app roots
        self.py_module_map.setdefault(dotted, fid)
        for idx in range(1, len(parts)):
            if parts[idx - 1] in ("src", "backend", "app", "lib", "packages"):
                suffix = ".".join(parts[idx:])
                self.py_module_map.setdefault(suffix, fid)

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
                unresolved.append(
                    UnresolvedReference(
                        source_file=source_file_id,
                        raw_import=imp.module_specifier,
                        line=imp.line,
                        reason="dynamic_import",
                    )
                )
                continue

            if language == "Python":
                targets, ext_pkg, unres = self._resolve_python(source_file_id, src_dir, imp)
            elif language in ("TypeScript", "TypeScript (TSX)", "JavaScript", "JavaScript (JSX)"):
                targets, ext_pkg, unres = self._resolve_js_ts(source_file_id, src_dir, imp)
            elif language == "Go":
                targets, ext_pkg, unres = self._resolve_go(source_file_id, imp)
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
        # Relative import: e.g. from . import foo or from ..bar import baz
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

        # Absolute import in Python
        spec = imp.module_specifier.strip()
        if not spec:
            return ([], None, None)

        # Check direct module match or imported submodule match
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

        # Handle path aliases like @/... or ~/...
        norm_candidates: list[str] = []
        if spec.startswith("."):
            norm = self._normalize_rel_path(src_dir, spec)
            if norm:
                norm_candidates.append(norm)
        elif spec.startswith(("@/", "~/")):
            stripped = spec[2:]
            norm_candidates.extend(
                [
                    stripped,
                    f"src/{stripped}",
                    f"frontend/src/{stripped}",
                    f"app/{stripped}",
                ]
            )
        elif spec.startswith("src/"):
            norm_candidates.extend([spec, f"frontend/{spec}"])

        if norm_candidates:
            for cand in norm_candidates:
                # Strip .js/.jsx if importing TypeScript file via ESM .js extension
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

        # External npm package name (e.g. @xyflow/react or react/jsx-runtime)
        parts = spec.split("/")
        if spec.startswith("@") and len(parts) >= 2:
            pkg_name = f"{parts[0]}/{parts[1]}"
        else:
            pkg_name = parts[0]
        return ([], pkg_name, None)

    def _resolve_go(
        self, source_id: str, imp: RawImportStatement
    ) -> tuple[list[str], str | None, UnresolvedReference | None]:
        spec = imp.module_specifier.strip()
        if not spec:
            return ([], None, None)
        # Match suffix directories inside the repo
        parts = spec.split("/")
        for i in range(len(parts)):
            suffix_dir = "/".join(parts[i:])
            if suffix_dir in self.dir_files_map:
                go_files = [f for f in self.dir_files_map[suffix_dir] if f.endswith(".go") and not f.endswith("_test.go")]
                if go_files:
                    return (go_files, None, None)
        return ([], spec, None)

    def _resolve_rust(
        self, source_id: str, src_dir: PurePosixPath, imp: RawImportStatement
    ) -> tuple[list[str], str | None, UnresolvedReference | None]:
        spec = imp.module_specifier.strip()
        if not spec:
            return ([], None, None)
        clean = spec.split("{")[0].strip().rstrip(":")
        segments = [s for s in clean.split("::") if s]
        if not segments:
            return ([], None, None)

        if segments[0] in ("crate", "self", "super"):
            base = src_dir if segments[0] != "crate" else PurePosixPath("src")
            if segments[0] == "super" and base.as_posix() != ".":
                base = base.parent
            for seg in segments[1:]:
                cand_rs = (base / f"{seg}.rs").as_posix()
                cand_mod = (base / seg / "mod.rs").as_posix()
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
