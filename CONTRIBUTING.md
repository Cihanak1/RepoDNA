# Contributing to RepoDNA

Thank you for your interest in contributing to **RepoDNA — Developer Repository Intelligence Platform**!

## Architecture Principles

1. **Core Engine Independence**:
   - All static analysis logic under `backend/repodna/` (`parsers`, `graph`, `git_insights`, `rules`, `reports`, `security`, `storage`) must remain decoupled from the web UI so the standalone CLI (`repodna analyze`) and FastAPI server share the exact same deterministic engine.
2. **Deterministic, Explainable Rules**:
   - Never add opaque or non-deterministic scoring to `backend/repodna/rules/health.py`. Every architectural rule must declare its mathematical deduction formula, threshold, concrete file evidence, and actionable engineering remediation.
3. **Security First**:
   - Never execute code from scanned repositories.
   - Preserve all SSRF, symlink, path traversal, and file size guardrails in `backend/repodna/security/validators.py`.

## Development Setup

### Backend (Python 3.12+)

```bash
python -m pip install -e ".[dev]"
python -m ruff check backend
python -m mypy backend
python -m pytest -v
```

### Frontend (Node.js 20+ / TypeScript / Vite)

```bash
cd frontend
npm install
npm run typecheck
npm test
npm run build
```

### End-to-End Browser Verification (Playwright)

```bash
# Terminal 1: Start Backend API on port 8000
python -m uvicorn repodna.api.app:app --host 127.0.0.1 --port 8000

# Terminal 2: Start Frontend on port 5173 and run Playwright
cd frontend
npx playwright test
```

## Commit Message Convention

We follow [Conventional Commits](https://www.conventionalcommits.org/):
- `feat(backend): ...` / `feat(ui): ...`
- `fix(security): ...`
- `test(e2e): ...`
- `docs: ...`
