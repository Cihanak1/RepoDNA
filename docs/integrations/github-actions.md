# GitHub Actions Integration — RepoDNA Architecture Guardian

RepoDNA Architecture Guardian protects your codebase from architectural regression on every Pull Request. It continuously detects:
- **New circular dependency loops** introduced in PRs.
- **Contract violations** against declared layer and boundary rules in `.repodna/architecture.yml`.
- **Architectural coupling spikes** on key architectural hub modules.
- **Health score degradation** and coverage drops.

---

## Security Model & Threat Boundaries

When integrating Architecture Guardian into automated CI pipelines, security and integrity are paramount:

### 1. Fork PR Security (Untrusted Code)
- **Always use `pull_request`** with minimal permissions (`permissions: contents: read`).
- **NEVER use `pull_request_target`** with elevated permissions to check out or run code from untrusted forks.
- RepoDNA runs **pure static analysis** (AST parsing and graph topology). It **never executes or imports user code** during scanning.

### 2. Secret Protection
- The Architecture Guardian action requires **zero secret tokens**. Do not pass personal access tokens (`PAT`) or organization secrets to the analysis runner.
- Generated artifacts (job summary, Markdown diff, and `.repodna/passport.json`) never contain source code bodies or host environment variables.

### 3. Pinned Dependency Installation
- Always pin the Python version (`python-version: "3.12"`) and RepoDNA version (`pip install "repodna>=0.4.0"` or `-e .`) to avoid dependency confusion.

---

## Quickstart Workflow

Create `.github/workflows/architecture-guardian.yml` in your repository:

```yaml
name: RepoDNA Architecture Guardian

on:
  pull_request:
    branches: [main, master]

permissions:
  contents: read

jobs:
  guardian:
    name: Architecture Guardian
    runs-on: ubuntu-latest
    steps:
      - name: Checkout repository (full git history for diff)
        uses: actions/checkout@v4
        with:
          fetch-depth: 0

      - name: Set up Python 3.12
        uses: actions/setup-python@v5
        with:
          python-version: "3.12"

      - name: Install RepoDNA
        run: |
          python -m pip install --upgrade pip
          python -m pip install "repodna>=0.4.0"

      - name: Run PR Architecture Guardian
        id: guardian
        run: |
          repodna guardian check . \
            --base "origin/${{ github.base_ref }}" \
            --head HEAD \
            --mode enforce \
            --format markdown \
            --output guardian-report.md

      - name: Publish Job Summary
        if: always()
        run: |
          if [ -f guardian-report.md ]; then
            cat guardian-report.md >> $GITHUB_STEP_SUMMARY
          fi

      - name: Generate Repository Passport
        if: always()
        run: |
          repodna passport generate . --max-modules 200

      - name: Upload Guardian Artifacts
        if: always()
        uses: actions/upload-artifact@v4
        with:
          name: repodna-architecture-artifacts
          path: |
            guardian-report.md
            .repodna/passport.json
          retention-days: 14
```

---

## Configuration Options

| Option | Flag | Description | Default |
| :--- | :--- | :--- | :--- |
| **Base revision** | `--base <ref>` | Base branch or commit SHA | Required |
| **Head revision** | `--head <ref>` | Target PR commit or branch | `HEAD` |
| **Policy mode** | `--mode <mode>` | `advisory` (warns) or `enforce` (fails CI on violation) | In contract or `advisory` |
| **Contract file** | `--contract <path>` | Custom path to architecture rules YAML | `.repodna/architecture.yml` |
| **Baseline file** | `--baseline <path>` | JSON file of accepted legacy violations | `.repodna/baseline.json` |
| **Output format** | `--format <fmt>` | `markdown`, `json`, or `table` | `table` |
| **Output file** | `--output <path>` | Write report directly to file | None (stdout) |

---

## Enforcement vs Advisory Mode

- **Advisory Mode (`--mode advisory`):**
  - New contract violations are highlighted as `WARNING` in the PR summary.
  - CI job succeeds (exit code 0).
  - Great for introducing architectural rules into legacy codebases without blocking ongoing feature development.
- **Enforce Mode (`--mode enforce`):**
  - Verified `error` or `warning` violations on new code cause the CI check to fail (exit code 1).
  - Existing baseline violations are excluded from breaking CI.

---

## Interpreting Verdicts

| Verdict | Meaning | Exit Code | Action |
| :--- | :--- | :--- | :--- |
| **`PASS`** | Clean architecture; zero new circular loops; contract compliant. | 0 | Ready to merge. |
| **`WARNING`** | Advisory contract violations or coupling degradation detected. | 0 | Review warnings; fix recommended before merge. |
| **`FAIL`** | New circular dependencies or enforced contract violations detected. | 1 | CI blocked; developer must resolve regressions. |
| **`INCONCLUSIVE`** | Scan exceeded bounds or AST coverage collapsed severely. | 2 | Check parser coverage or limits configuration. |
