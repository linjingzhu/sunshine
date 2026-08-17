# Complete wrapper-runtime removal

## Status

COMPLETED

## Trigger

Product owner: the remaining wrapper-runtime content is an error and must be
removed completely.

## Finding

The code tree was already clean, but the largest wrapper-runtime artifact in the
repository was still live: `docs/SUNSHINE_OS_STAGE_1_TO_3_IMPLEMENTATION_HANDOFF.md`
was marked *Ready for implementation planning* and ended with a start prompt.
It specified an application shell, not a Chromium downstream:

- a trusted application process with `TabManager`, `NavigationService`, and
  `WindowManager` owning tabs, navigation, and windows;
- a renderer/main split joined by a typed private message channel and a preload
  bridge;
- remote-page security expressed as wrapper `webPreferences` flags;
- a required `src/main/`, `preload/`, `renderer/` source layout;
- TypeScript and React mandated for browser chrome.

Each item contradicts `.ai/PROJECT_CONTEXT.md`, which gives Chromium ownership of
tabs, omnibox, navigation, history, downloads, permissions, and renderer
isolation. Any worker starting from that document would have rebuilt the removed
architecture.

## Root cause

`scripts/verify_architecture.py` ignored `docs/`. The guard could only see code,
so it certified the tree as clean while the specification that directs
implementation still described a wrapper runtime.

## Delivered

- Removed the withdrawn ADR 0001, which still carried positive reasoning for the
  wrapper runtime and framed its safeguards as useful precedent.
- Rewrote twenty sections of the Stage 1-3 handoff in native Chromium terms:
  process and trust model, technology stack, domain ownership, repository
  layout, module boundary, omnibox classification, tab lifecycle, threat
  provider, testing matrix, implementation waves, and the start prompt.
- Product requirements, stage goals, acceptance suites, product-owner decisions,
  and non-goals were preserved; only the runtime architecture changed.
- Cleaned the two remaining narrative references in ADR 0002 and recorded why
  the ADR numbering starts at 0002.
- Extended the guard to scan `docs/` and to reject wrapper-runtime API and
  configuration names, which are the form the leak actually took in prose.
- Scoped the hardcoded-startup-URL rule to code, so documentation may quote the
  URL it forbids without a false positive.

## Boundary applied

Text that *forbids* a wrapper runtime was kept everywhere: the exclusion in
project context, the ADR decision line, the CI job name, the guard's own marker
list, and historical run reports. Deleting the prohibition would remove the
mechanism that keeps the runtime out.

Git history was not rewritten. Removing the merged history would be destructive
and is not required to remove the architecture from the working tree.

## Verification

- Repository-wide grep for wrapper-runtime design names: no remaining hit
  outside prohibitions, the guard, and historical reports.
- Guard proves the leak class is now caught: a specification containing a
  wrapper configuration name fails the check.
- Unit/contract suite: 76 passed, up from 71.
- Architecture verifier, patch manifest, module registry, Python compile: passed.
- Native compile, Windows build, runtime/visual: NOT RUN; unchanged by this work.
- Adversarial review: FALLBACK REVIEW - fresh self-review only.
- Cross-agent review: NOT AVAILABLE.

## Remaining risk

`docs/PROJECT_DEVELOPMENT_DASHBOARD_SPEC.md` names web UI frameworks as
interchangeable options for a portable dashboard document. It is not Sunshine
runtime architecture and was left unchanged.
