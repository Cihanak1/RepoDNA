# Changelog

All notable changes to **RepoDNA** are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2026-11-07 (Public Preview Release)

### Added
- **Core Static AST Engine (`repodna.parsers`)**:
  - Single-pass C-level Tree-sitter CST parsing for Python, TypeScript (`.ts`/`.tsx`), JavaScript (`.js`/`.jsx`/`.mjs`), Go, and Rust with error-tolerant syntax recovery.
  - Partial static `#include` / `import` scanning for C, C++, Java, Kotlin, and C#.
  - Support for `tsconfig.json` / `jsconfig.json` `paths` and `baseUrl` aliases, `go.mod` module path prefix resolution, monorepo workspace packages (`packages/*`), Rust `mod foo;` declarations, and braced `use crate::a::{b, c}` imports.
  - Explicit transparency tracking for unsupported languages, unresolved internal imports, dynamic imports (`import(...)`, `__import__`), and skipped files.
- **Dependency Graph & Cycle Detection Engine (`repodna.graph`)**:
  - Iterative Tarjan Strongly Connected Components (SCC) and Johnson's blocked-set canonical elementary cycle extraction.
  - Per-module Fan-In ($C_a$), Fan-Out ($C_e$), Robert C. Martin Instability Index ($I = C_e / (C_a + C_e)$), hub detection, and orphan detection.
- **Explainable Architecture Health Engine (`repodna.rules`)**:
  - Deterministic 100-point rubric evaluating Acyclic Dependencies Principle (`ARCH-001`), Efferent Coupling (`ARCH-002`), Stable Dependencies Principle (`ARCH-003`), Oversized Modules (`ARCH-004`), Isolated Modules (`ARCH-005`), Directory Nesting (`ARCH-006`), and Credential/Secret Hygiene (`SEC-001`).
- **Git Insights (`repodna.git_insights`)**:
  - Read-only commit history inspection (`%x1f` unit-separator delimiter, `core.quotepath=false` for Unicode paths), 60%-threshold bus-factor estimation, and file churn hotspot scoring.
- **Security & Guardrails (`repodna.security`, `repodna.storage`)**:
  - Strict HTTPS GitHub URL allowlisting, SSRF IP/localhost blocking, Git branch option-injection prevention, hardened temporary cloning (`stdin=DEVNULL`, `GIT_CONFIG_NOSYSTEM=1`, `http.lowSpeedLimit`), symlink/path-traversal protection, UTF-16 BOM source decoding, and configurable file/byte/timeout limits with cooperative cancellation.
- **Interfaces & Exporters**:
  - Standalone Python CLI (`python -m repodna.cli.main analyze ...`) with `table`, `json`, and `html` output modes.
  - FastAPI backend (`repodna.api.app`) with synchronous scan, asynchronous progress/cancellation jobs, safe directory browsing, and deterministic JSON/HTML export endpoints.
  - React 19 + TypeScript + Tailwind CSS + React Flow (`@xyflow/react`) 3-pane engineering workstation with full Dark/Light theme support, `Ctrl+K` Command Palette, Directory Package Clustering, Graph Density controls, and responsive container-query tables.
