# Advanced tabs, and the scheme spelling ADR 0003 abolished

## Status

COMPLETED_WITH_NOTES

## Delivered

- `docs/ADVANCED_TABS_CONTRACT.md` (604 lines) — handoff §7.4, previously
  uncontracted.
- `sunshine://` retired across five documents; 0 occurrences remain outside the
  ADR that abolished it.
- `workspace.switch`'s last active tab given an owner in
  `scripts/workspace_model.py`.

## Finding 1 — reopening a closed tab always loses its workspace

`BrowserLiveTabContext::GetExtraDataForTab` populates assistant keys only. It
never copies `SessionTab::extra_data`, and `browser_tabrestore.cc` hands the
restored map to two named consumers. Verified by reading both at the pinned tag.

So a tab reopened through the restore service carries no workspace UUID, and
`TAB_LIFECYCLE_CONTRACT.md` §10.2's rule — "the UUID in its tab session
extra-data; Default when missing" — resolved to *Default, always*. The contract
described behaviour no build produces.

Corrected in place: the session service and the restore service now have
separate rows, and the restore row states the real outcome with the reason.
Whether to accept it or patch the two seam points is an open decision.

## Finding 2 — "keeps Chromium's horizontal tab strip" is no longer a no-op

`kVerticalTabsLaunch` is `FEATURE_ENABLED_BY_DEFAULT` on every non-ChromeOS
platform, and `IsVerticalTabsFeatureEnabled()` returns true if either it or
`kVerticalTabs` is on. A Sunshine build therefore ships vertical tabs, with a
context-menu toggle defaulting to present, unless it disables an upstream
default.

`WORKSPACE_NATIVE_INTEGRATION_MAP.md` said "split view and vertical tabs remain
out of scope", which assumed both were absent until built. Neither is. Corrected.

This also corrects a claim in the side-panel wave's report, which cited
`kVerticalTabs` alone as disabled and concluded the exclusion was free. It read
the wrong flag. The claim never reached that contract's text.

## Finding 3 — duplicate detection is the only Sunshine work in §7.4

| Feature | Sunshine work |
| --- | --- |
| pin/unpin | none — two upstream persistence paths already |
| native tab groups | none new; already contracted |
| tab search | no search code; two conditional seam patches |
| recently closed | none; ownership already settled |
| duplicate detection | **yes — the only one** |

Nothing user-facing ships for duplicate detection: Tab Declutter and Tab
Organization are gone (five paths 404 at the tag), `kTabStripDeclutter` is
disabled with its implementation not located. The only real dedup is Tab
Search's `DedupKey`, which is one-directional — it suppresses recently-closed
entries against open tabs, never open against open.

Chromium's own key includes group identity, which is upstream's signal that a
duplicate means *same URL in the same context*. That is why the proposed
Sunshine key adds the workspace term.

## Also corrected or recorded

- Handoff §7.3 and the §4 domain-model row claim workspaces store pinned tabs.
  That is a third authority for state Chromium already persists twice
  (`TabStripModel` and `PinnedTabService`/`PinnedTabCodec`). Withdrawn by the new
  contract.
- `StartupTab` is `{GURL, Type, bool}` — no extra-data — so pinned tabs returning
  through `PinnedTabCodec` cannot carry membership. Stated rather than left to be
  discovered.
- `tab_restore::Window::workspace` is the platform virtual desktop, not a
  Sunshine workspace. Fenced before the name collision could be acted on.
- `TabInterface::IsVisible()` is contents-area visibility. Repurposing it as a
  workspace bit is forbidden.
- The omnibox contract's acceptance criteria said "1–21" while criterion 16 is
  now unreachable, so the gate required something that cannot pass. Both
  enumerations corrected.

## Verification

- Suite: 140 passed.
- Guards: architecture, command registry (24), module registry (2), patch
  manifest (4), doc metadata (11), compile check (21 files) — all passed.
- Pinned upstream: 7 seams, 2 tokens, **122 cited paths**, 2 patches — passed.
- Native compile: build 12 IN PROGRESS.
- Runtime, visual, installer: NOT RUN.
- Adversarial review: FALLBACK REVIEW — Manager review of worker output.
- Cross-agent review: NOT AVAILABLE.

## A note on the review that is missing

Two workers in this wave contradicted each other on a fact — the vertical-tabs
flag — and the disagreement was only visible because both reported to one
Manager who had read the source. That is the third wave in which a parallel
worker caught something Manager review had passed. It is the closest thing this
project has to the adversarial review that remains NOT AVAILABLE, and it works
because workers read shipped material as *input*, not as something to approve.

## Open for the owner

New, from this wave:

1. Is duplicate detection wanted at all? A "no" makes §7.4 entirely inherited.
2. Does the dedup key include the workspace term?
3. Reopened tabs: accept Default, or patch the two seam points?
4. Synced saved groups arrive with no workspace — where do they land?
5. Does the Sunshine build disable `kVerticalTabsLaunch`, or ship the upstream
   default and treat orientation as a user setting?
6. Does attribution of a Tab Search result to its workspace justify patching
   `chrome/browser/resources/tab_search/`?

Carried forward: the split-view flags, split membership on workspace move, MVP
split scope, the Security Center route commitment, host prefixing, the palette's
Korean initial-consonant search, the tabs and downloads panel questions, and the
Stage 2 security decisions.
