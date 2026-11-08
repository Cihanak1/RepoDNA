# RepoDNA frontend reimagination — delivery

Implemented on `codex/precision-workstation`. Version remains **0.1.1**; no backend
API/schema changes, framework migration, push or release. Recommended next release:
**0.2.0**, because the workspace introduces substantial new user-facing behavior.

## Design and provenance

See [the forensic audit and skill review](AUDIT.md) for the original problems,
direction, token palette, licenses and exact upstream commits. Sources:
[Anthropic](https://github.com/anthropics/skills/tree/2c5958ecac7cee2b583967a2c4981d0f4a75c579/skills/frontend-design),
[UI UX Pro Max](https://github.com/nextlevelbuilder/ui-ux-pro-max-skill/tree/4f2dbb67e64969a9a30ab00742f2d55d66ddec2b/.claude/skills/ui-ux-pro-max),
[Vercel](https://github.com/vercel-labs/agent-skills/tree/1a2c79d4e6c4a2283dc2c614b6538cbe1ed5ca62/skills/web-design-guidelines).

The product now uses a graphite/petrol engineering workspace with neutral
surfaces, restrained risk colors, compact measurements and a persistent repository
identity. `tokens.css` defines theme, semantic color, font, spacing, radius,
motion and layer tokens. Tailwind consumes those tokens directly; the previous
high-specificity light-theme override block is removed. Final light colors were
darkened after measured contrast failures (see `tokens.css` for source of truth).

## Component and behavior changes

- **App / HeaderBar / Launchpad:** separate launchpad component, disclosable source
  controls after analysis, explicit repository/status line, native scan cancellation,
  existing previous-analysis continuity and honest export success/failure feedback.
- **Workspace / PanelResizer:** independent explorer and inspector visibility;
  pointer resizing plus arrows/Home/End; validated local panel widths and graph
  layout/density/grouping preferences; canvas focus with Escape exit.
- **ExplorerSidebar:** compact directory rows, path tooltips, literal search match
  highlighting, Arrow Up/Down and Home/End navigation, existing symbol and support
  filters retained. A search can match symbols as well as filenames.
- **DependencyGraph / graphLayout:** quieter file/package nodes; no unsupported
  module labeled healthy; selected-edge labels; reduced non-neighbor emphasis;
  explicit node dimensions repair the previously empty minimap; resize-aware fit;
  zoom to selection; keyboard selection; manual dragging retained; deterministic
  reset; compact spacing and directory group heights avoid node overlaps.
  Package nodes aggregate support conservatively, with exact coverage counts in
  the inspector. Package double-click and inspector action expand back to files.
- **InspectorPanel:** sections replace nested cards; copy path/metrics with error
  feedback; package summary; support-aware dependency and stability language;
  partial-static symbols are labeled static rather than AST declarations.
- **HealthReportView / SummaryStrip:** compact measurement rail and report layout;
  full evidence/remediation retained; unverified categories have no fake progress
  bar; empty findings never imply that unverified rules passed.
- **CommandPaletteDialog:** category headings, prefix relevance, recent command
  history (command IDs only), combobox selection announcements, keyboard scrolling,
  focus restoration, and protection against stale native close events.

Keyboard: `Ctrl/Cmd+K` commands, `/` explorer search, `Alt+F` canvas focus,
`Alt+I` inspector, `Escape` exit focus/dialog. Shortcuts do not hijack typing in
inputs or dialogs. Mobile/tablet use Files / Canvas / Inspector navigation;
desktop keeps the adjustable three-panel workspace.

## Real browser evidence

All images are actual local Edge/Playwright captures, not mockups.

| Scenario | Before | After |
|---|---|---|
| Launchpad | [Before](before/launchpad.png) | [After](after/launchpad.png) |
| Demo studio | [Before](before/studio.png) | [After](after/studio-dark.png) |
| Light theme | [Before](before/light.png) | [After](after/studio-light.png) |
| Package grouping | [Before](before/packages.png) | [After](after/packages.png) |
| Command palette | [Before](before/commands.png) | [After](after/commands.png) |
| Health report | [Before](before/report.png) | [After](after/report.png) |
| File selection / self-analysis | [Before](before/self-analysis-selection.png) | [After](after/repodna-studio-live.png) |
| Loading | [Before](before/loading.png) | [After](after/loading-cancel.png) |
| Error | [Before](before/error.png) | [After](after/error.png) |
| Mobile | [Before](before/mobile.png) | [After](after/viewport-390.png) |

Additional captures: [768×1024](after/viewport-768.png),
[1366×768](after/viewport-1366.png), [1440×900](after/viewport-1440.png),
[1920×1080](after/viewport-1920.png), [previous analysis](after/loading-previous.png),
[NiceWP report](after/nicewp-report.png), [NiceWP mobile](after/nicewp-mobile.png).

Live NiceWP verification: 312 files, 263 partial-static C# files, 48 unsupported
files, about 0.2% AST LOC coverage in the tested snapshot. Overall score remains
**not evaluated — insufficient dependency coverage**, confidence low; dependency
cycles are not declared absent. Live repository counts may change upstream.

## Verification

Commands run from repository root unless indicated:

| Check | Result |
|---|---|
| `.venv/Scripts/python -m ruff check backend` | Passed |
| `.venv/Scripts/python -m mypy backend/repodna` | Passed, 25 source files |
| `.venv/Scripts/python -m pytest -q` | 46 passed |
| `npm run typecheck --prefix frontend` | Passed |
| `npm run lint --prefix frontend` | Real ESLint, zero warnings |
| `npm test --prefix frontend` | 7 passed |
| `npm run build --prefix frontend` | Passed |
| `npm run test:e2e --prefix frontend` | See final verification below |

The six E2E scenarios cover live RepoDNA, live NiceWP, the labeled demo, JSON and
HTML download completion, transient-result retries, errors, previous results,
cancellation, panel drag/keyboard/persistence, graph selection/minimap/zoom,
package expansion, search, clipboard, recent commands, modal focus and all five
requested viewport sizes. Axe checks applicable WCAG A/AA rules in both themes,
studio, report, palette and mobile, including NiceWP mobile.

Failures were investigated, not suppressed: legacy launchpad copy expectation;
selected badge and dimmed-node contrast; palette test selectors matching native
select options; stale dialog close events; symbol search legitimately returning
two modules; tiny mobile GitHub input targets. Development dependency updates
also invalidated Vite's optimized modules during one run; the suite is rerun
after dependencies settle. No retry policy masks failing tests.

## Performance

Same machine, Edge headless, 1440×900, same Vite dev server configuration/backend
and demo dataset: one warmup and five fresh browser contexts for each version.
[Raw samples and medians](performance.json) are automation wall-clock timings,
not pure React rendering latency or a statistical performance guarantee.

Baseline production output: CSS 73.05 kB / 12.25 kB gzip; JavaScript entry
533.65 kB / 160.17 kB gzip. Graph and report now load on demand; production bundle
measurements and final medians are recorded below after final verification.
No CLS or large-repository FPS improvement is claimed without measurement.

## Limits and maintenance

- Automated checks and keyboard/browser review are not a complete WCAG
  certification or a substitute for assistive-technology user testing.
- Large graphs still need clustering, filtering and zoom. No FPS/CPU claim is
  made for arbitrary multi-thousand-file repositories.
- Chromium/Edge was exercised; Firefox, Safari and physical touch hardware were
  not available in this run. Responsive checks emulate viewport sizes.
- Panel preferences are local to this browser; graph filters are not shareable
  URLs. Package detail shows aggregate coverage and a clearly identified member,
  not a backend-generated package health score.
- No new runtime dependencies. Development tooling adds ESLint, TypeScript ESLint,
  React Hooks lint rules and Axe Playwright. `npm audit --omit=dev` reports zero
  production vulnerabilities. Full dev audit reports 13 advisories (11 moderate,
  2 critical), including existing Vitest/Tinypool and lint-tool minimatch chains.
  Major test-runner upgrades were not forced into this frontend redesign.
- Non-failing upstream warnings remain: pytest asyncio loop-scope default,
  Starlette/httpx deprecation and Node's experimental localStorage warning.
- Skills/research are local excluded tooling and are not included in the Vite
  product bundle or commits. The audit records their exact provenance.

## Final verification and commits

Filled after the final checks and local commits. No Git history rewrite or
remote publication is performed.
