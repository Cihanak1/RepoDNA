# RepoDNA — Developer Repository Intelligence Platform

**RepoDNA** is a static architectural analysis, module dependency graph, circular dependency detector, and explainable code health platform for local source directories and public GitHub repositories.

Built for software architects, staff engineers, and open-source maintainers, RepoDNA parses source repositories using **Tree-sitter CST/AST parsers** without executing a single line of target code. It maps internal module relationships, identifies strongly connected circular dependency chains via **Tarjan's SCC algorithm**, calculates **Robert C. Martin's Instability ($I$) and Fan-In/Fan-Out coupling metrics**, inspects Git commit churn hotspots, and produces a **100% deterministic, rule-based Architecture Health Report**.

---

## System Architecture

```mermaid
flowchart LR
  subgraph Inputs["Target Sources (Explicit Consent)"]
    LocalDir["Local Directory Path"]
    GitHubURL["Public HTTPS GitHub URL"]
    DemoPreset["Labeled Demo Dataset"]
  end

  subgraph Security["Security & Guardrail Layer"]
    Validator["SSRF & URL Validator\nPath Traversal & Symlink Guard\nFile Size / Count / Timeout Limits"]
    TempClone["Isolated Temp Git Clone\ncore.hooksPath=empty\ncore.symlinks=false"]
  end

  subgraph CoreEngine["UI-Independent Core Engine (repodna)"]
    Parsers["Tree-sitter & AST Parsers\nPython, TS/TSX, JS/JSX, Go, Rust\n+ Static C/C++/Java/C#"]
    Resolver["Internal Module & Package\nImport Resolver"]
    GraphEngine["Tarjan SCC & Cycle Engine\nFan-In (Ca), Fan-Out (Ce), Instability (I)"]
    GitAnalyzer["Git History & Churn Hotspot\nBus-Factor Analyzer"]
    RulesEngine["Explainable Rule-Based\nArchitecture Health Rubric"]
    Exporters["Deterministic Exporters\nJSON & Standalone HTML"]
  end

  subgraph Interfaces["Consumer Interfaces"]
    CLI["Standalone Python CLI\nrepodna analyze"]
    FastAPI["FastAPI Backend Server\nSync & Async Progress/Cancel API"]
    WebUI["React 19 + TypeScript + React Flow\n3-Pane Architecture Studio"]
  end

  LocalDir --> Validator
  GitHubURL --> Validator --> TempClone
  DemoPreset --> CoreEngine
  Validator --> CoreEngine
  TempClone --> CoreEngine
  Parsers --> Resolver --> GraphEngine --> RulesEngine --> Exporters
  GitAnalyzer --> RulesEngine
  CoreEngine --> CLI
  CoreEngine --> FastAPI --> WebUI
```

### Module Structure

```text
RepoDNA/
├── pyproject.toml                  # Python 3.12+ package, CLI entrypoint, Ruff/Mypy/Pytest config
├── README.md                       # English architecture, setup, usage, security & test documentation
├── LICENSE                         # MIT License
├── SECURITY.md                     # Threat model, SSRF/symlink/secret boundaries & vulnerability policy
├── CONTRIBUTING.md                 # Contribution guidelines & development workflow
├── CHANGELOG.md                    # Release history
├── .github/workflows/ci.yml        # GitHub Actions CI pipeline
├── backend/
│   ├── repodna/
│   │   ├── schemas/models.py       # Typed Pydantic v2 data contracts
│   │   ├── security/validators.py  # HTTPS GitHub URL allowlist, SSRF block, symlink & secret guards
│   │   ├── storage/workspace.py    # Hardened temporary Git clone & automatic cleanup
│   │   ├── parsers/                # Tree-sitter AST & static import/symbol extractors + path resolver
│   │   ├── graph/engine.py         # Tarjan SCC, elementary cycle finder, Fan-In/Out & Instability (I)
│   │   ├── git_insights/analyzer.py# Read-only Git commit history, bus-factor & churn hotspot calculator
│   │   ├── rules/health.py         # Explainable rule-based Architecture Health engine
│   │   ├── reports/exporter.py     # Deterministic JSON & standalone self-contained HTML report generator
│   │   ├── core/analyzer.py        # Orchestrator with progress callbacks, cancellation & timeouts
│   │   ├── api/app.py              # FastAPI server (sync scan, async jobs, cancel, exports, safe browse)
│   │   └── cli/main.py             # Standalone Python CLI scanner
│   └── tests/                      # Pytest unit, security, graph, CLI & FastAPI integration suite
└── frontend/
    ├── src/
    │   ├── api/client.ts           # Typed API client
    │   ├── types/repodna.ts        # TypeScript domain models
    │   ├── utils/graphLayout.ts    # Deterministic Layered, Cluster & Radial graph layouts + filters
    │   ├── components/             # 3-Pane Studio (HeaderBar, SummaryStrip, ExplorerSidebar,
    │   │                           # DependencyGraph, InspectorPanel, HealthReportView, FolderBrowserDialog)
    │   └── __tests__/              # Vitest component & layout unit tests
    └── e2e/repodna.spec.ts         # Playwright real-browser end-to-end verification suite
```

---

## Key Features

1. **Explicit Consent Local Scanning & Hardened GitHub Cloning**:
   - Never scans local directories automatically in the background; local scans begin only when explicitly triggered by the user.
   - Clones public `https://github.com/<owner>/<repo>` repositories into disposable temporary directories with Git hooks (`core.hooksPath`) and symbolic links (`core.symlinks=false`) disabled. Source code is **never** executed.
2. **Multi-Language Tree-sitter AST & Static Import Resolution**:
   - **Full AST Support (`full_ast`)**: Python (`.py`), TypeScript (`.ts`, `.tsx`), JavaScript (`.js`, `.jsx`, `.mjs`, `.cjs`), Go (`.go`), and Rust (`.rs`).
   - **Partial Static Support (`partial_static`)**: C/C++ (`.c`, `.h`, `.cpp`, `.hpp`), Java (`.java`), Kotlin (`.kt`), and C# (`.cs`).
   - **Full Transparency (`unsupported`)**: Files in other languages (`.rb`, `.php`, `.swift`, `.sql`, `.yaml`, `.md`, etc.) are counted in LOC and language distribution and explicitly listed under **Unsupported Languages** in the Transparency Report. Dynamic imports (`__import__`, `import(expr)`) and unresolved relative paths are explicitly reported with line numbers.
3. **Explainable, Rule-Based Architecture Health Rubric**:
   - Zero hallucinated AI scores. Starts at `100.0` points and evaluates deterministic engineering rules with explicit mathematical formulas, thresholds, evidence, and remediation:
     - `ARCH-001`: **Circular Dependency Violations (ADP)** — Tarjan SCC & elementary cycle detection.
     - `ARCH-002`: **Excessive Efferent Coupling (High Fan-Out)** — Flags modules importing $\ge 8$ internal modules.
     - `ARCH-003`: **Stable Dependencies Principle (SDP) Inversion** — Flags stable modules ($I \le 0.35$) depending on volatile modules ($I \ge 0.70$).
     - `ARCH-004`: **Oversized Modules / God File Risk** — Flags code modules exceeding `450` non-comment LOC.
     - `ARCH-005`: **Isolated / Orphaned Modules** — Flags non-entrypoint modules with zero internal graph edges.
     - `ARCH-006`: **Excessive Directory Hierarchy Depth** — Flags paths nested $\ge 6$ levels deep.
     - `SEC-001`: **Potential Secret or Sensitive File Exposure** — Flags committed `.env` / private key files or high-confidence token patterns (with values redacted).
4. **Interactive 3-Pane Architecture Studio**:
   - **Left (Repository Explorer)**: Search by file path or AST symbol name, filter by language or AST support level, and toggle quick filters for **In Cycle**, **Hubs**, and **Orphans**.
   - **Center (Interactive Dependency Graph)**: Powered by `@xyflow/react` with **Layered Hierarchy**, **Directory Clusters**, and **Radial Ring** layouts, **Zoom/Pan/FitView**, **MiniMap**, **1-Hop Neighborhood Focus**, and **Circular Dependency Highlighting**.
   - **Right (Module Deep Inspector)**: Inspect per-file LOC, Fan-In ($C_a$), Fan-Out ($C_e$), Instability ($I$), participating Circular Dependency chains, clickable internal imports & dependents, external packages, unresolved/dynamic imports, AST symbols, Git churn, and triggered health rules.
5. **JSON & Standalone HTML Export**:
   - Export complete machine-readable JSON or a self-contained, dark/light-aware HTML executive architecture report from either the Web UI or the CLI.

---

## Installation & Quick Start

### Prerequisites
- **Python**: `3.12+`
- **Node.js**: `20+` (tested with Node.js LTS)
- **Git**: Installed and available on `PATH`

### 1. Backend & Standalone CLI Setup

```bash
# Install backend package and development/test dependencies
python -m pip install -e ".[dev]"

# Verify CLI help
python -m repodna.cli.main --help
```

### 2. Frontend Setup

```bash
cd frontend
npm install
```

### 3. Running the Full-Stack Platform

Start the FastAPI backend server on port `8000`:

```bash
python -m uvicorn repodna.api.app:app --host 127.0.0.1 --port 8000
```

In a second terminal, start the Vite development server on port `5173`:

```bash
cd frontend
npm run dev
```

Open `http://127.0.0.1:5173` in your browser.

---

## Standalone CLI Usage

RepoDNA's core analysis engine runs independently of the web UI via `python -m repodna.cli.main`:

```bash
# Analyze a local directory and print an executive summary table
python -m repodna.cli.main analyze .

# Export a deterministic JSON report
python -m repodna.cli.main analyze . --format json --output repodna-report.json

# Export a standalone, self-contained HTML report
python -m repodna.cli.main analyze . --format html --output repodna-report.html

# Analyze a public HTTPS GitHub repository with custom file/timeout guardrails
python -m repodna.cli.main analyze https://github.com/Cihanak1/AImage --max-files 1500 --timeout 45

# Run against the explicitly labeled Demo showcase dataset
python -m repodna.cli.main analyze demo --format table
```

---

## Limitations & Transparency

- **Static Analysis Scope**: Dynamic runtime reflection, metaprogramming (`eval`, dynamic `importlib.import_module(var)`), or dependency injection containers wired via external XML/YAML files cannot be statically linked to a target file. RepoDNA explicitly records dynamic import calls under `unresolved_imports` with `reason="dynamic_import"` so they are never silently hidden.
- **GitHub Host Scope**: By design, remote cloning initially supports only canonical `https://github.com/<owner>/<repo>` URLs over port 443 to prevent SSRF against internal networks or unverified Git servers.
- **Large Monorepo Guardrails**: Default scan limits (`max_files=2500`, `max_file_size_bytes=1MB`, `max_total_size_bytes=100MB`, `timeout_seconds=60s`) protect workstation memory and CPU. These limits are user-configurable in both the UI (**Guardrails** dialog) and CLI (`--max-files`, `--max-file-size`, `--timeout`), and any truncation is prominently reported in `transparency.truncated_by_limits`.

---

## Testing, Linting & Verification Commands

### Backend Verification

```bash
# Run pytest unit & integration suite (27 tests)
python -m pytest -v

# Run Ruff linter
python -m ruff check backend

# Run Mypy static type checker
python -m mypy backend
```

### Frontend Verification

```bash
cd frontend

# Run TypeScript compiler typecheck
npm run typecheck

# Run Vitest unit tests
npm test

# Build production bundle
npm run build
```

### End-to-End Browser Verification (Playwright)

```bash
cd frontend
npx playwright test
```

---

## License

Released under the [MIT License](./LICENSE).
