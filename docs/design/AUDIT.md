# RepoDNA workstation redesign

## Baseline and direction

The clean v0.1.1 working tree was inspected before implementation. React/TypeScript,
Vite, React Flow and backend contracts remain the foundation.

Strong foundations: explicit scan initiation, cancellable jobs, previous-result
continuity, support-level filtering, deterministic graph layouts, native modal
dialogs, detailed evidence and honest missing-coverage scores.

Observed in real Edge screenshots in `before/`: six equal metric cards compete
with the graph; floating toolbars cover nodes; 320/384px fixed panels consume
almost half the desktop; mobile pushes the canvas below the viewport; selected
text and minimap controls lose contrast in light mode. Nested cards, rainbow
badges and tiny all-caps labels overwhelm the content. CSS uses hardcoded slate
utilities with high-specificity light-mode overrides. Graph nodes label
unsupported modules “Healthy”; the empty findings table claims every rule passed.

Direction: Precision Engineering Workstation. A compact repository identity bar,
quiet measurement strip, adjustable explorer/canvas/inspector, and explicit
mobile Files / Canvas / Inspector navigation. Left-aligned UI, petrol selection,
neutral graphite surfaces, readable sans UI and monospace paths. Risk colors
only encode findings. Graph nodes carry identity and support; details belong in
the inspector. No decorative gradients, glass or motion.

```text
RepoDNA   repository / analysis status     Studio | Report   Commands / Export
Repository source and scan controls (disclosable after analysis)
Health       Files / LOC       Dependencies       Coverage
Explorer | resize | Architecture + graph tools | resize | Inspector
```

Tokens: dark canvas #151b20, panel #1c242b, raised #263139, primary #e8eef0,
secondary #abb9c1, accent #75c9d0. Light canvas #edf1f2, panel #ffffff,
raised #e3eaed, primary #192c35, secondary #506570, accent #116774.
Segoe UI Variable/Segoe UI for controls; Cascadia Code/Consolas for paths.
Local font fallbacks avoid remote font requests. Radius 4/6/10px; spacing uses
4px rhythm; explicit focus, layer and motion tokens. Both themes use the same
semantic token names, including graph labels and minimap.

## Skills provenance and review

Installed locally under `.agents/skills`, excluded via `.git/info/exclude` along
with research clones. No application runtime dependencies or lifecycle hooks
were installed for these skills. The system skill-installer Python helper was
read and used with pinned commits and an explicit local destination.

| Skill | Source commit | License / scope |
|---|---|---|
| frontend-design | anthropics/skills@2c5958ecac7cee2b583967a2c4981d0f4a75c579 | Apache-2.0, text-only skill |
| ui-ux-pro-max | nextlevelbuilder/ui-ux-pro-max-skill@4f2dbb67e64969a9a30ab00742f2d55d66ddec2b | MIT; local CSV/Python search |
| web-design-guidelines | vercel-labs/agent-skills@1a2c79d4e6c4a2283dc2c614b6538cbe1ed5ca62 | No root license found; private local guidance only |

Reviewed skill instructions, licenses and search-helper imports/file/network/
process operations. No credential access, subprocess execution or outbound data
transfer found in the selected search path; terminal color environment lookup
and optional local output writing are present. Unrelated repository tools were
not executed. This scoped review is not a security certification of entire repos.

Applied principles: deliberate composition, subject-specific typography,
progressive disclosure, keyboard alternatives to drag, contrast, reduced motion,
native dialogs and responsive overflow checks. UI UX Pro Max's initial broad
query returned an irrelevant architecture portfolio: rejected. The narrowed
`developer IDE software dashboard` product query returned Developer Tool / IDE;
used its dense monitor / minimal UI guidance, rejecting bento/glass suggestions.
Vercel's live web-interface-guidelines `command.md` was fetched for review.
