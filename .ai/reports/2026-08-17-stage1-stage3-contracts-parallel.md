# Stage 1 and Stage 3 contracts — parallel wave

## Status

ACTION_REQUIRED

The documents are complete and every gate passes. The status is not COMPLETED
because the wave found a violation of ADR 0002 in already-shipped work, and the
remedy is an owner decision rather than a Manager one.

## Scope

Four workers in parallel, one new document each, closing the four requirements
that had no ownership contract. Two of them are Stage 1 — the foundation layer —
which had gone unwritten while Stage 2 and Stage 3 contracts were produced.

## Conflict control

Each worker owned exactly one new file. The command registry, tests, scripts and
workflows stayed Manager-owned. Workers were told to propose command identifiers
in their reports rather than name them in prose, because `validate_commands.py`
fails the build on an unregistered identifier and four workers inventing
commands in parallel would collide at integration. No conflicts occurred.

## Delivered

- `docs/OMNIBOX_CONTRACT.md` (552 lines) — handoff §5.3.
- `docs/TAB_LIFECYCLE_CONTRACT.md` (645 lines) — handoff §5.4.
- `docs/COMMAND_PALETTE_CONTRACT.md` (910 lines) — handoff §7.8.
- `docs/SIDE_PANEL_CONTRACT.md` (607 lines) — handoff §7.6.

Two workers read the actual pinned sources over the GitHub mirror rather than
reasoning from memory, and marked each claim as read-from-source or as a
measurement yet to be taken. That is the first time this repository's design
work has been grounded in the revision it targets, and it is why the three
findings below are facts rather than suspicions.

## Finding 1 — Sunshine reimplemented Chromium's split tabs

**Severity: highest in the wave. This violates ADR 0002 and the repository's own
domain-ownership rule.**

Chromium 152.0.7977.42 ships split tabs natively. Verified by retrieving each
file at the pinned tag:

| Sunshine | Chromium at the pinned tag |
| --- | --- |
| `ORIENTATION_COLUMNS` / `ORIENTATION_ROWS` | `SplitTabLayout::kSideBySide` / `kStacked` |
| `ratio`, default `0.5` | `split_ratio`, default `0.5` |
| `SplitLayout` dataclass | `SplitTabVisualData` |
| split state in window session extra-data | `SplitTabData` in `SplitTabCollection`, a tab-strip collection |
| — | `MultiContentsView`: two contents views, resize area, drop targets, mini toolbar |

`components/split_tabs/split_tab_visual_data.h`, `components/tabs/public/split_tab_data.h`,
`components/tabs/public/split_tab_collection.h`, `chrome/browser/ui/tabs/split_tab_util.h`
and `chrome/browser/ui/views/frame/multi_contents_view.h` all return 200 at the
pinned tag.

ADR 0002 says to use Chromium's existing tabs. Splits are part of the tab strip
at this revision, so `scripts/split_view_model.py`, the `sunshine-split-view`
module and the three `view.split.*` commands re-derive a model Chromium owns —
down to the same default ratio.

This was not detectable from the repository alone, which is why it survived
review: nothing here recorded what upstream had gained since the split-view
contract was written.

**Recommendation:** re-derive split view onto native split tabs, and reduce
Sunshine's split-view surface to whatever remains genuinely Sunshine's — most
likely only the interaction of a split with workspace membership. This deletes
code and shrinks the patch stack, so it lowers roll cost rather than raising it.

**Not done in this wave, because it is not a Manager call:** it retires shipped
work, changes a shipped contract, and changes three registered commands.

## Finding 2 — `guard` in the command registry is not a predicate

Every Sunshine-owned `guard` is the model function that *performs* the
operation, and signals refusal by raising after receiving full execution inputs:

    close_pane(layout, pane) -> str
    open_split(tabs, active_workspace_id, leading, trailing, *, orientation, ratio) -> SplitLayout
    swap_panes(layout) -> SplitLayout
    close_workspace_atomic(catalog, tabs, closed, destination, *, fail_before_commit) -> ...
    move_tabs_atomic(tabs, runtime_ids, destination, catalog, *, fail_before_commit) -> ...

Consequences, none of which the validator can see because it only checks that
the reference resolves and is callable:

- Rendering a palette by consulting guards would execute up to 27 operations to
  draw a list.
- Several `availability` sentences correspond to no code at all. Nothing
  evaluates "A tab is active"; `close_pane` receives a layout as given and
  cannot evaluate "The active window has a split layout".
- Handoff §7.8 requires a disabled command to explain itself. A boolean cannot,
  and `availability` is prose for reviewers, not a user-facing reason.

**This also corrects a claim I made in the Stage 2 report.** I recorded
"commands take no parameters" as an unstated assumption. It was not an
assumption; it was false. Three of the five guards already require undeclared
arguments. The parameters exist and are undocumented, which is worse than
either alternative.

The palette contract rules on provenance instead: context parameters are free,
selection parameters are permitted but must be declared, and renderer-supplied
payloads are prohibited permanently. Under that ruling the link and image
context-menu actions are not deferred work — they are permanently unregistrable,
and a future wave that "finally registers them" would be building something that
must not exist. `docs/BROWSER_UTILITIES_CONTRACT.md` has been corrected to say
so.

## Finding 3 — an internal `sunshine` scheme is a security decision, not branding

The omnibox contract traced the scheme classifier at the pinned tag. It consults
the external-protocol handler and the OS application registry, so if the
installer registers `sunshine:` with the operating system, **every web page in
every browser on the machine becomes a launcher for internal Sunshine routes.**

Meanwhile the handoff answers the question two ways: §1.2 excludes the
`sunshine://` App SDK, while §6.7 requires `sunshine://security`. Today
`sunshine://settings` would classify as unknown and be sent to the search
provider as a query string — leaking the internal route name and failing the
Stage 1 acceptance suite.

## Corrections to shipped content, applied in this wave

- `docs/BROWSER_UTILITIES_CONTRACT.md` claimed "No command identifier exists yet
  for any utility in this contract". Eleven had been registered in the same wave
  that wrote the sentence; my integration missed it. Rewritten, and extended
  with the permanent-exclusion ruling above.
- `scripts/verify_architecture.py` rejected the string `WebContentsView`
  everywhere, including documentation. It is a real Chromium type in `content/`,
  which a side-panel or split-view patch reaches directly. The wrapper runtime's
  class of the same name cannot be used without importing the runtime, which the
  remaining markers already catch, so the entry added no detection and would
  have failed the build on legitimate upstream terminology. Removed, with two
  tests pinning both halves: the import is still caught, and the Chromium type
  is allowed.

## Also reported, not yet acted on

- `docs/TAB_WORKSPACE_SPLIT_CONTRACT.md` specifies that `workspace.switch`
  restores a workspace's last active tab. No storage for that exists anywhere —
  not in the catalog, not in `workspace_model.py`, not in window extra-data. The
  behaviour is specified with no owner.
- `browser.reload` folds stop-loading into reload, declares no errors, and
  claims availability "A tab is active." Both palette and lifecycle contracts
  independently recommend splitting out a stop command.
- `tab.group.create` states its availability and its error as the same
  condition, so the error can never fire.
- Three widely-cited Chromium paths do not exist at the pinned tag:
  `components/omnibox/browser/omnibox_edit_model.*` and `omnibox_view.*` (moved
  under `chrome/browser/ui/omnibox/`), and
  `content/browser/child_process_security_policy_impl.h` (the public header is
  `content/public/browser/child_process_security_policy.h`).
- `validate_commands.py`'s `DOC_TOKEN` matches any backticked lowercase dotted
  token whose first segment is a declared surface, so prose writing
  `` `workspace.name` `` fails the build.

## Verification

- Unit/contract suite: 122 passed, up from 120.
- Architecture verifier, command registry (27), module registry (3), patch
  manifest (4 targets): passed.
- Pinned upstream check via the mirror: passed.
- Native compile, runtime, visual: NOT RUN in this wave.
- Adversarial review: FALLBACK REVIEW — Manager review of worker output.
- Cross-agent review: NOT AVAILABLE.

## Decisions needed from the owner

Carried forward, plus new:

1. **Split view on native split tabs** — retire the Sunshine split model, or
   keep it and accept a standing ADR 0002 violation. Recommended: retire.
2. **Registry schema v2** — separate the operation from the availability
   predicate, and give availability a reason token so a disabled command can
   explain itself. `validate_commands.py` compares keys in both directions, so
   this is an atomic change across the registry, the validator, its tests and
   all 27 entries. Until it lands, handoff §7.8 is unsatisfiable.
3. **Is an internal `sunshine` scheme registered at all**, and if so, is it
   registered with the OS? Blocks the Security Center surface.
4. Whether the tabs panel lists only the active workspace or all workspaces.
5. Whether the downloads panel coexists with the native download bubble or
   replaces it — replacement changes a shipped safety surface.
6. Korean initial-consonant search in the palette, which a Korean-first product
   plausibly needs and which is currently scoped out.

Unchanged from Stage 2: the `block` verdict's permitted actions, origin-only
egress, fail-closed strict policy, Security Center retention, and the
`font-weight: 650` question.
