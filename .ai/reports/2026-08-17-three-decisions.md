# Three owner decisions, executed

## Status

COMPLETED_WITH_NOTES

## 1. Split view re-derived onto Chromium (ADR 0002 violation closed)

Chromium owns splits at the pinned revision, including persistence:
`SplitTabCollection`/`SplitTabData`, `SplitTabVisualData {kSideBySide, kStacked}`
with `split_ratio` defaulting to `0.5`, `TabStripModel::{AddToNewSplit,
RemoveSplit, ReverseTabsInSplit, UpdateSplitLayout, UpdateSplitRatio,
MoveSplitTo, RestoreSplit, DetachSplitTabForInsertion}`, `MultiContentsView`,
and `SessionTab::split_id` + `SessionSplitTab` replayed by `session_restore.cc`.
All read at 152.0.7977.42.

Deleted: `scripts/split_view_model.py`, `tests/test_split_view_model.py`, the
`sunshine.split_view` module, and the three `view.split.*` commands. The `view`
surface has no members left and is gone from the registry. No replacement
command: each mapped one-to-one onto a native entry point, and the native swap
is strictly larger than Sunshine's was -- it reorders the view hierarchy and the
active index, which a metadata-only swap could not. Retiring them adds
capability.

What Sunshine still owns is the workspace seam, and one rule there is
load-bearing: **the projection must never move tabs.**
`MaybeRemoveSplitsForMove` dissolves the origin split when a tab leaves its
collection, and `MoveBreaksSplitContiguity` dissolves a destination split it is
inserted into, so a projection reordering tabs to cluster a workspace would
silently destroy every split it stepped through.

Two feature flags are `FEATURE_DISABLED_BY_DEFAULT` at this revision:
`kSplitViewHorizontal` (stacked) and `kSplitViewTabRestore`. They are the only
lever that changes split behaviour without writing split code.

Defects found in shipped content while doing this:
- `MIN_RATIO = 0.2` / `MAX_RATIO = 0.8` in the deleted model had no upstream
  basis. `MultiContentsView` constrains by pixels (`kMinWebContentsSize = 200`,
  `kMinWebContentsSizePercentage = 0.1`) and snaps to `0.5`. A user dragging past
  0.8 natively would have had the resulting state rejected on restore.
- The lifecycle contract said a paned tab detaching always dissolves the split.
  A whole split moves between windows intact via
  `DetachSplitTabForInsertion`/`InsertDetachedSplitTabAt`. Corrected.

## 2. Registry schema 2

`guard` never held a predicate; it held the operation. Split into
`implementation` and a side-effect-free `predicate`, with `unavailable_reasons`
declaring the closed set that predicate may return. Validator rules: predicate
and reasons present or absent together; neither on a Chromium-owned command;
reasons snake_case, unique, sorted; and no token may be both a reason and an
error, because one says the command cannot start and the other says an offered
command did not finish.

The test the old field could not support: each predicate is called with inputs
chosen to make it refuse, and the returned token must be one the registry
declared. Plus one asserting a predicate still says yes, since a predicate that
never does would disable a command permanently.

## 3. No Sunshine URL scheme (ADR 0003)

Decision: register no scheme. First-party surfaces are internal pages under
Chromium's existing internal scheme; the Security Center becomes
`chrome://sunshine-security`.

The argument is that the boundary is enforced upstream rather than promised
downstream. `webui_config_map.h` admits exactly two schemes by `CHECK`, so a
Sunshine scheme cannot serve a WebUI without a downstream patch -- and once that
patch exists, the host table deciding which routes resolve is the same table an
App SDK would extend. Under Chromium's scheme "internal surfaces only" is a
`CHECK`; under a Sunshine scheme it is a code-review convention.

Two omnibox invariants come free as a result: no search fallback for an unknown
internal host (the scheme is in the handled-protocol set), and completion from
the compiled surface list (`builtin_provider.cc` has no notion of a second
internal scheme, so under the alternative this was unobtainable without patching
a component every embedder consumes).

Correction applied to shipped content: omnibox invariant OS-1 required the
scheme be "not a savable scheme". `kDefaultSavableSchemes` in
`content/common/url_schemes.cc` includes `kChromeUIScheme` -- Chromium's internal
scheme *is* savable. Copying OS-1 literally would have diverged from the scheme
it was imitating while claiming to match it. OS-1 now states the properties as
read, including secure, CORS-enabled and service-worker-enabled, which it had
omitted.

## Verification

- Suite: 115 passed. Count fell from 131 because the split model's tests were
  deleted with it.
- Architecture verifier, command registry (24), module registry (2), patch
  manifest (4): passed.
- Pinned upstream check via the mirror: 7 seams, 2 tokens, 87 cited paths, 2
  patches -- passed.
- Native compile: run 12 IN PROGRESS at time of writing.
- Runtime, visual, installer: NOT RUN.
- Adversarial review: FALLBACK REVIEW -- Manager review of worker output.
- Cross-agent review: NOT AVAILABLE.

## Open for the owner

1. Enable `kSplitViewHorizontal` (stacked splits)? Default: no.
2. Enable `kSplitViewTabRestore` (a closed split reopens as a split)? Default: no.
3. Moving one member of a split to another workspace: dissolve by default, which
   matches upstream's pin/group behaviour, or prompt to move both?
4. Should a workspace contain a split at all in the MVP, given
   `WORKSPACE_NATIVE_INTEGRATION_MAP.md` declares split out of scope -- a
   sentence that now describes a feature arriving whether Sunshine acts or not?
5. Is `chrome://sunshine-security` acceptable, or has `sunshine://security` been
   committed externally? The ADR's default is that the commitment is withdrawn.
6. Should Sunshine internal hosts carry a common prefix, so upstream collision is
   unlikely by construction rather than checked per surface at each roll?

Carried forward unchanged: the `block` verdict's permitted actions, origin-only
egress, fail-closed strict policy, Security Center retention, `font-weight: 650`,
Korean initial-consonant search in the palette, and the tabs/downloads panel
questions.
