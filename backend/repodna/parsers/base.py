"""Language metadata, line counting, and base parser contracts."""

from __future__ import annotations

from dataclasses import dataclass, field

from repodna.schemas.models import LanguageSupportLevel, SymbolItem


@dataclass
class RawImportStatement:
    module_specifier: str
    imported_names: list[str] = field(default_factory=list)
    line: int = 1
    is_relative: bool = False
    relative_level: int = 0
    is_dynamic: bool = False


@dataclass
class ParsedFileData:
    language: str
    support_level: LanguageSupportLevel
    lines_total: int
    lines_code: int
    lines_comment: int
    lines_blank: int
    raw_imports: list[RawImportStatement] = field(default_factory=list)
    symbols: list[SymbolItem] = field(default_factory=list)
    parser_used: str = "none"


# Extension -> (Language Name, Support Level, Single-line comment prefix)
LANGUAGE_REGISTRY: dict[str, tuple[str, LanguageSupportLevel, str]] = {
    ".py": ("Python", LanguageSupportLevel.FULL_AST, "#"),
    ".ts": ("TypeScript", LanguageSupportLevel.FULL_AST, "//"),
    ".tsx": ("TypeScript (TSX)", LanguageSupportLevel.FULL_AST, "//"),
    ".js": ("JavaScript", LanguageSupportLevel.FULL_AST, "//"),
    ".jsx": ("JavaScript (JSX)", LanguageSupportLevel.FULL_AST, "//"),
    ".mjs": ("JavaScript", LanguageSupportLevel.FULL_AST, "//"),
    ".cjs": ("JavaScript", LanguageSupportLevel.FULL_AST, "//"),
    ".go": ("Go", LanguageSupportLevel.FULL_AST, "//"),
    ".rs": ("Rust", LanguageSupportLevel.FULL_AST, "//"),
    ".c": ("C", LanguageSupportLevel.PARTIAL_STATIC, "//"),
    ".h": ("C/C++ Header", LanguageSupportLevel.PARTIAL_STATIC, "//"),
    ".cpp": ("C++", LanguageSupportLevel.PARTIAL_STATIC, "//"),
    ".hpp": ("C++ Header", LanguageSupportLevel.PARTIAL_STATIC, "//"),
    ".cc": ("C++", LanguageSupportLevel.PARTIAL_STATIC, "//"),
    ".java": ("Java", LanguageSupportLevel.PARTIAL_STATIC, "//"),
    ".kt": ("Kotlin", LanguageSupportLevel.PARTIAL_STATIC, "//"),
    ".cs": ("C#", LanguageSupportLevel.PARTIAL_STATIC, "//"),
    # Tracked non-import or unsupported languages
    ".rb": ("Ruby", LanguageSupportLevel.UNSUPPORTED, "#"),
    ".php": ("PHP", LanguageSupportLevel.UNSUPPORTED, "//"),
    ".swift": ("Swift", LanguageSupportLevel.UNSUPPORTED, "//"),
    ".scala": ("Scala", LanguageSupportLevel.UNSUPPORTED, "//"),
    ".lua": ("Lua", LanguageSupportLevel.UNSUPPORTED, "--"),
    ".sh": ("Shell", LanguageSupportLevel.UNSUPPORTED, "#"),
    ".bash": ("Shell", LanguageSupportLevel.UNSUPPORTED, "#"),
    ".ps1": ("PowerShell", LanguageSupportLevel.UNSUPPORTED, "#"),
    ".sql": ("SQL", LanguageSupportLevel.UNSUPPORTED, "--"),
    ".html": ("HTML", LanguageSupportLevel.UNSUPPORTED, "<!--"),
    ".css": ("CSS", LanguageSupportLevel.UNSUPPORTED, "/*"),
    ".scss": ("SCSS", LanguageSupportLevel.UNSUPPORTED, "//"),
    ".json": ("JSON", LanguageSupportLevel.UNSUPPORTED, ""),
    ".yaml": ("YAML", LanguageSupportLevel.UNSUPPORTED, "#"),
    ".yml": ("YAML", LanguageSupportLevel.UNSUPPORTED, "#"),
    ".toml": ("TOML", LanguageSupportLevel.UNSUPPORTED, "#"),
    ".md": ("Markdown", LanguageSupportLevel.UNSUPPORTED, ""),
    ".xml": ("XML", LanguageSupportLevel.UNSUPPORTED, "<!--"),
    ".vue": ("Vue SFC", LanguageSupportLevel.UNSUPPORTED, "//"),
    ".svelte": ("Svelte", LanguageSupportLevel.UNSUPPORTED, "//"),
    ".dart": ("Dart", LanguageSupportLevel.UNSUPPORTED, "//"),
    ".ex": ("Elixir", LanguageSupportLevel.UNSUPPORTED, "#"),
    ".exs": ("Elixir", LanguageSupportLevel.UNSUPPORTED, "#"),
}


def detect_language(filename: str, extension: str) -> tuple[str, LanguageSupportLevel, str]:
    lower_name = filename.lower()
    if lower_name == "dockerfile" or lower_name.startswith("dockerfile."):
        return ("Dockerfile", LanguageSupportLevel.UNSUPPORTED, "#")
    if lower_name == "makefile":
        return ("Makefile", LanguageSupportLevel.UNSUPPORTED, "#")
    ext = extension.lower()
    if ext in LANGUAGE_REGISTRY:
        return LANGUAGE_REGISTRY[ext]
    return ("Other", LanguageSupportLevel.UNSUPPORTED, "#")


def count_lines(content: str, comment_prefix: str) -> tuple[int, int, int, int]:
    """Return (total, code, comment, blank) line counts."""
    if not content:
        return (0, 0, 0, 0)
    lines = content.splitlines()
    total = len(lines)
    blank = 0
    comment = 0
    code = 0
    in_block_comment = False

    for raw in lines:
        stripped = raw.strip()
        if not stripped:
            blank += 1
            continue

        if in_block_comment:
            comment += 1
            if "*/" in stripped:
                in_block_comment = False
            continue

        if comment_prefix in ("//", "/*") and stripped.startswith("/*"):
            comment += 1
            if "*/" not in stripped[2:]:
                in_block_comment = True
            continue

        if comment_prefix and stripped.startswith(comment_prefix):
            comment += 1
        else:
            code += 1

    return (total, code, comment, blank)
