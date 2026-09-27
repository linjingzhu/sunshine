# Tab Groups, Workspaces, and Split View — Native Ownership Contract

**Status:** Implementation foundation; native runtime verification pending
**Target:** Pinned Chromium revision in `config/chromium.version` (`152.0.7977.42`)
**Constraint:** No Chromium compilation is required for this contract wave.
**Revision:** Split view re-derived onto Chromium's native split tabs. Section 8
records every claim withdrawn from the previous version and why.

## 0. Evidence basis for this revision

Every statement below about upstream behaviour was read from the pinned tag over
the GitHub mirror on 2026-08-17, file by file. Statements are labelled:

- **read-from-source** — quoted from a file fetched at `152.0.7977.42`;
- **NOT RUN** / **NOT AVAILABLE** — a measurement that has not been taken.

No Chromium build was compiled, no browser was launched, and no screenshot was
taken for this document: build **NOT RUN**, runtime **NOT RUN**, visual
**NOT RUN**.

The finding that forced this revision: Chromium already ships two-pane split
view as a first-class part of the tab strip, so Sunshine's parallel split model
was a re-derivation of upstream and a violation of
`docs/decisions/0002-native-chromium-downstream.md`. The upstream surface, all
read-from-source:

| Upstream capability | Where it lives at the pinned tag |
|---|---|
| Split identity | `components/split_tabs/split_tab_id.h` — `SplitTabId` is a `tab_groups::TokenId`, globally unique |
| Layout and ratio | `components/split_tabs/split_tab_visual_data.h` — `SplitTabLayout {kSideBySide, kStacked}`, `split_ratio` defaulting to `0.5` |
| Split as tab-strip state | `components/tabs/public/split_tab_collection.h`, `components/tabs/public/split_tab_data.h`, `components/tabs/public/tab_strip_collection.h` |
| Per-tab split membership | `components/tabs/public/tab_interface.h` — `IsSplit()`, `GetSplit()` |
| Create / dissolve / swap / relayout / resize | `chrome/browser/ui/tabs/tab_strip_model.h` — `AddToNewSplit`, `RemoveSplit`, `ReverseTabsInSplit`, `UpdateSplitLayout`, `UpdateSplitRatio`, `UpdateTabInSplit`, `MoveSplitTo`, `RestoreSplit` |
| Cross-window transfer of a whole split | `chrome/browser/ui/tabs/tab_strip_model.h` — `DetachSplitTabForInsertion`, `InsertDetachedSplitTabAt` |
| Change notification | `chrome/browser/ui/tabs/tab_strip_model_observer.h` — `SplitTabChange`, `OnSplitTabChanged` |
| Two-pane presentation, resize, drop targets, per-pane mini toolbar, accessible panes | `chrome/browser/ui/views/frame/multi_contents_view.h` |
| Active-pane location helpers | `chrome/browser/ui/tabs/split_tab_util.h` — `SplitTabActiveLocation {kStart, kEnd, kTop, kBottom}` |
| Split menu (reverse, toggle orientation, close a named tab, exit split) | `chrome/browser/ui/tabs/split_tab_menu_model.h` |
| Entry points | `chrome/app/chrome_command_ids.h` — `IDC_NEW_SPLIT_TAB`; `chrome/browser/ui/browser_commands.h` — `NewSplitTab`, `DuplicateSplit`; tab context menu `CommandAddToSplit`, `CommandSwapWithActiveSplit`, `CommandArrangeSplit` |
| Persistence | `components/sessions/core/session_types.h` — `SessionTab::split_id`, `SessionWindow::split_tabs`, `SessionSplitTab` holding `SplitTabVisualData` |
| Persistence writers | `components/sessions/core/session_service_commands.h` — `CreateSplitTabCommand`, `CreateSplitTabDataUpdateCommand`; called from `chrome/browser/sessions/session_service.cc` |
| Restore | `chrome/browser/sessions/session_restore.cc` — rebuilds each split via `RestoreSplit` and replays layout and ratio |

Two-tab limit, read-from-source: `chrome/browser/sessions/session_restore.cc`
restores a split only when the recorded member count is exactly two, and
`chrome/browser/ui/views/frame/multi_contents_view.h` presents "up to two
contents web views".

## 1. Product boundary

Sunshine does not replace Chromium's tab model. Chromium remains authoritative
for tabs, tab groups, **split tabs**, navigation, WebContents lifetime, profile
storage, and session restore. Sunshine adds only persistent workspace
membership around those native objects.

| Concept | Authority | Persistence boundary |
|---|---|---|
| Tab and active tab | Chromium `TabStripModel` | Chromium session restore |
| Tab group label, color, collapse state | Chromium `TabGroupModel` / `TabGroupVisualData` | Chromium tab-group/session state |
| Split identity, membership, orientation, ratio, pane focus | Chromium `TabStripModel` / `SplitTabCollection` / `SplitTabVisualData` | Chromium session restore |
| Profile, cookies, site storage | Chromium `Profile` / `StoragePartition` | Profile-scoped Chromium storage |
| Workspace membership and ordering | Sunshine workspace metadata | Same profile only |
| Coherence between a split and workspace membership | Sunshine | Derived; nothing persisted |

The last row is the whole of Sunshine's remaining interest in split view.
Chromium has no concept of a workspace, so nothing upstream prevents a split
whose two tabs carry different workspace labels. That single seam is what
section 2 invariants 9 to 12 govern. Everything else about split view is
upstream's, including the parts Sunshine previously specified for itself.

## 2. Non-negotiable invariants

Numbering is stable: sibling contracts cite invariants 4, 5, and 6 by number.
Invariants 1 to 8 keep their meaning; 5 and 6 are restated as guarantees
Sunshine now *inherits* rather than implements. Invariants 9 to 12 are new.

1. A tab has exactly one native owner and at most one `workspace_id`.
2. A tab group never spans workspaces. Moving a grouped tab to another
   workspace first removes it from the source group unless the whole group is
   moved atomically.
3. A workspace never crosses a Chromium profile boundary. Moving a tab to a
   workspace in another profile is rejected; it is not implemented as a silent
   copy.
4. Switching workspaces hides inactive tabs but does not destroy their
   WebContents or navigation state.
5. A tab may occupy zero or one split pane. It cannot be rendered live in both
   panes. *Upheld natively:* a split is a `SplitTabCollection` in the tab-strip
   collection tree and a tab has one parent collection
   (`components/tabs/public/tab_strip_collection.h`); `TabInterface::GetSplit()`
   returns at most one id. Sunshine adds no enforcement.
6. Closing one split pane returns the survivor to the normal active view.
   *Upheld natively:* read-from-source in
   `chrome/browser/ui/tabs/tab_strip_model.cc`, `RemoveTabFromIndexImpl`
   dissolves the whole split before removing the tab and selects the split's
   first member, so the survivor stays alive and becomes active. Sunshine adds
   no enforcement.
7. Closing a workspace requires an explicit destination workspace and atomic
   transfer of all tabs. Archive is undefined and excluded from the MVP.
   Tabs are never silently discarded.
8. Invalid or stale persisted **workspace** references fail closed: the normal
   active tab is shown and the tab recovers into Default. Split records are no
   longer a Sunshine failure mode because Sunshine no longer writes any.
9. **A split never spans workspaces.** The two members of a split always carry
   the same `workspace_id`. This is the tab-group rule of invariant 2 applied to
   splits, and it is the reason a workspace seam exists at all.
10. **A workspace operation that covers only part of a split dissolves the split
    first.** Sunshine calls `TabStripModel::RemoveSplit` before reassigning
    membership, then performs the membership change. This copies upstream's own
    partial-containment rule: read-from-source,
    `TabStripModel::MaybeRemoveSplitsForUpdate` in
    `chrome/browser/ui/tabs/tab_strip_model.cc` dissolves a split when a pin or
    group operation names fewer tabs than the split contains. A workspace move
    that names both members moves both and preserves the split.
11. **The workspace projection never moves a tab in the tab strip.** Workspace
    switching hides and shows; it does not reorder. Read-from-source,
    `TabStripModel::MoveTabToIndexImpl` calls `MaybeRemoveSplitsForMove`, which
    dissolves the origin split whenever a tab leaves its split collection and
    also dissolves a destination split whose contiguity the insertion would
    break (`MoveBreaksSplitContiguity`). A projection that reordered tabs to
    cluster a workspace would therefore destroy every split it stepped through,
    silently and without user intent.
12. **Sunshine writes no split state and contains no split model.** Orientation,
    ratio, pane focus, pane identity, and split persistence are read from
    Chromium when needed and never mirrored.

## 3. Minimum persisted metadata

Chromium's session service is the only authority for tab order, pinned state,
navigation, group membership, **split membership and split layout**, and
restoration. Sunshine does not keep a shadow tab/session database. The profile
catalog persists only workspace definitions:

```json
{
  "schema_version": 1,
  "workspaces": [
    {
      "id": "workspace-development",
      "profile_id": "profile-default",
      "name": "Development",
      "color": "blue",
      "order": 0
    }
  ]
}
```

Rules:

- `schema_version` is mandatory; unknown future versions are not rewritten.
- Workspace IDs are opaque UUIDs, never array indexes.
- Durable tab UUID and workspace UUID travel with Chromium `SessionTab`
  `extra_data`; they are not joined later by URL, title, position, SessionID,
  WebContents pointer, native group ID, or `SplitTabId`.
- Active workspace is window-local session extra-data. This is the *only*
  remaining Sunshine use of window session extra-data.
- **No split record is written anywhere.** Read-from-source, Chromium already
  writes `SessionTab::split_id` and a `SessionSplitTab` carrying
  `SplitTabVisualData` per window
  (`components/sessions/core/session_types.h`,
  `components/sessions/core/session_service_commands.cc`,
  `chrome/browser/sessions/session_service.cc`) and rebuilds both on restore
  (`chrome/browser/sessions/session_restore.cc`). A second Sunshine-written
  record would be a competing authority that can disagree with the first on
  exactly the restart path where disagreement is invisible until a user loses a
  layout.
- Unknown future schemas are preserved without rewrite.
- Missing/invalid membership recovers the native tab into Default; no tab is
  discarded.

`SplitTabId` is explicitly added to the forbidden-durable-key list. It is a
random token minted per split; it is stable across a restore only because
Chromium itself carries it through the session file, and it is not a Sunshine
identifier.

## 4. Commands

All UI entry points invoke the same command implementation.

### 4.1 Sunshine-owned commands

| Command ID | Result |
|---|---|
| `tab.group.create` | Uses Chromium native tab-group APIs |
| `tab.group.ungroup` | Removes membership without closing tabs |
| `workspace.create` | Creates an empty same-profile context with a New Tab |
| `workspace.switch` | Projects the selected workspace and restores its last active tab |
| `workspace.tab.move` | Transfers membership while retaining native tab state; split-aware per invariant 10 |
| `workspace.close` | Requires destination choice; moves all tabs atomically |

`workspace.switch` gains one clause and no new state: the per-workspace last
active tab is recorded as a tab, never as a split. Activating a tab that belongs
to a split foregrounds both panes natively — read-from-source,
`TabStripModel::GetForegroundTabs` returns the active tab or, if it is split,
every tab in that split. `chrome/browser/ui/tabs/split_tab_util.h` provides
`GetIndexOfLastActiveTab` for the case where the split's last active member
matters.

**Two of these six had no implementation until 2026-09-27, and the table above
did not say so.** `workspace.create` and `workspace.switch` carried
`implementation: null` and `predicate: null` in `first_party/commands.json`
while `0025-sunshine-command-titles.patch` shipped their palette labels ("New
workspace", "Switch workspace") and `sunshine-workspace` listed both as targets
— a row a user can be shown and Sunshine cannot run. `workspace.close` and
`workspace.tab.move` had both fields filled the whole time, which is what made
the gap easy to miss: the module looked implemented because two thirds of the
visible surface was.

Both now resolve, in the same compile-free layer as their two siblings:
`create_workspace` / `can_create_workspace` and `switch_workspace` /
`can_switch_workspace` in `scripts/workspace_model.py`. `switch_workspace` is an
assembly rather than new behaviour — `record_active_tab` and
`resolve_switch_target` already existed and nothing put them on either side of
one transition, so leaving a workspace and arriving at one could be performed
separately and a caller that did only the second would silently lose the user's
place. The clause above is what the assembly enforces: the record names one tab.

`scripts/validate_commands.py` now rejects a Sunshine-owned command that
declares no predicate, and one that declares no implementation unless it is
named in `NO_SUNSHINE_SIDE_EFFECT`. It previously enforced only the opposite
direction — that a Chromium-owned command carries no Sunshine code — so a null
on the Sunshine side short-circuited every rule and passed. **None of this is
native wiring.** No patch in the stack implements workspaces; the runtime order
in `.ai/PROJECT_CONTEXT.md` still has workspace metadata and switching ahead of
split view, and split view is the part that has been built.

### 4.2 Split commands, retired

Sunshine registered three split commands. They are gone, together with
`scripts/split_view_model.py`, its tests, and the `sunshine.split_view` module.
Each mapped one-to-one onto an upstream entry point that already existed, so a
Sunshine command in front of it bought nothing and created a second code path
that could drift from the native one:

| Retired Sunshine command | Native entry point, read-from-source |
|---|---|
| open | `IDC_NEW_SPLIT_TAB` (`chrome/app/chrome_command_ids.h`); `NewSplitTab` (`chrome/browser/ui/browser_commands.h`); tab context menu `CommandAddToSplit`; drag-to-edge drop target in `chrome/browser/ui/views/frame/multi_contents_view.h` |
| swap | `TabStripModel::ReverseTabsInSplit`; split menu `kReversePosition` (`chrome/browser/ui/tabs/split_tab_menu_model.h`); view-level `MultiContentsView::SwapContentsInSplitView` |
| close | `TabStripModel::RemoveSplit`; split menu `kExitSplit`, `kCloseStartTab`, `kCloseEndTab` |

The native swap is strictly larger than the Sunshine one was: it reorders the tab
strip *and* the view hierarchy and updates the active index, which a
metadata-only swap cannot do. Retiring the commands therefore adds capability
rather than removing it.

No replacement command is registered. The `view` surface has no members and has
been removed from the registry's surface list; the side-panel contract proposes
the next commands that would reintroduce it.

Retirement is a coordinated edit, not a documentation change. These identifiers
must leave `first_party/commands.json`, this section, and the two tests that
assert their presence in the same commit, because `scripts/validate_commands.py`
fails the build when a document names an unregistered command and
`tests/test_command_registry.py` fails when the registry and this table
disagree. Until that commit lands, the table above is the contract.

No replacement Sunshine command is proposed. Split view needs no Sunshine
command surface.

That remains true after `downstream/patches/0027-sunshine-split-swap-button.patch`,
which adds a swap button to the splitter. A button on a view is not a command:
nothing enters `first_party/commands.json`, nothing enters the registry's
surface list, and the retirement above is not reversed. The button reaches the
same `MultiContentsView::OnSwap()` the splitter's own double-click reaches, so
the "second code path that could drift from the native one" this section
retired the commands to avoid is still not created. See
`docs/decisions/0021-split-swap-affordance.md`.

It also remains true after
`downstream/patches/0032-sunshine-split-hover-widget.patch`, which turns that
button into a widget of three on hover. Two of the three are the same move:
반전 is `OnSwap()` again, and 분리 is `TabStripModel::RemoveSplit` — the native
entry point the retired `close` command mapped onto, called directly, with no
Sunshine command in front of it. Nothing enters `first_party/commands.json`.

**The third is new behaviour and this section should say so plainly.** 링크 —
a link clicked in one half of a split opens in the other half — has no upstream
entry point to be an affordance for. It is the first thing in this contract's
area that Sunshine *adds* rather than *exposes*, and
`docs/decisions/0028-split-hover-widget.md` is the record.

It is still not a command, and it still stores no split metadata: the mode is a
`content::WebContentsUserData` holding a weak pointer to the other tab, it
keeps no ratio, layout, orientation or pane identity, and it answers "no
destination" as soon as `tabs::TabInterface::GetSplit()` stops agreeing across
the two tabs. §3's persisted metadata is untouched and invariant 12 holds.

## 5. UX contract

- **Entry points:** tab context menu for groups/move/split; workspace switcher
  adjacent to the tab strip. Split entry points are Chromium's, unchanged and
  unwrapped, with **one Sunshine addition**: a swap button on the splitter,
  `docs/decisions/0021-split-swap-affordance.md`. It calls
  `MultiContentsView::OnSwap()`, which is the function a double-click on the
  splitter already reaches, so it wraps nothing — it makes an existing entry
  point visible. Every other split entry point is untouched.
- **Visible result:** workspace switching changes the visible tab set without a
  page reload; split view displays exactly two independently focusable pages.
- **Blocked behavior:** cross-profile moves remain blocked and show a concise
  reason. Same-tab and cross-profile split attempts are structurally impossible
  upstream — a split is a collection of distinct tabs inside one window, and a
  window belongs to one profile — so Sunshine states no rule and writes no
  check for them.
- **Recovery:** closing a split preserves both tabs; closing a workspace asks
  where its tabs should go.
- **Workspace switch with a split open:** nothing happens to the split. It is
  tab-strip state, it survives the switch untouched, and returning to that
  workspace shows it again. Sunshine must not dissolve a split on switch; doing
  so would discard user state that Chromium treats as durable across a full
  restart.
- **Moving one member of a split to another workspace:** the split is dissolved
  first and the user is told that is what happened, by the same wording used
  when a grouped tab leaves its group. Moving both members together preserves
  the split.
- **Accessibility:** group identity uses label plus color; pane focus and pane
  traversal order are Chromium's — `MultiContentsView::GetAccessiblePanes`
  supplies the pane order to the browser view. Every Sunshine command is
  keyboard reachable and exposes its disabled reason.

## 6. Feature-flag policy — a real Sunshine decision

Read-from-source, `chrome/browser/ui/tabs/features.cc` at the pinned tag:

| Flag (`chrome/browser/ui/tabs/features.h`) | Default at `152.0.7977.42` | Effect if left alone |
|---|---|---|
| `kSplitViewHorizontal` | `FEATURE_DISABLED_BY_DEFAULT` | `SplitTabLayout::kStacked` is unreachable; split view ships side-by-side only |
| `kSplitViewTabRestore` | `FEATURE_DISABLED_BY_DEFAULT` | A closed split does not reopen as a split; `TabStripModel::CreateHistoricalSplitIfClosing` never records one |

Side-by-side split view itself is not behind a flag in that file at this
revision. Whether either flag should be enabled in the Sunshine build is a
product decision, not an engineering one, and it is open — see section 9. It is
also the only place where Sunshine can change split-view *behaviour* without
writing split-view *code*.

## 7. Implementation sequence

1. Verify native Chromium tab-group create/rename/color/collapse/restore behavior.
2. Add profile-scoped catalog metadata; keep active workspace in window session
   extra-data and tab membership in tab session extra-data.
3. Add move-tab and close-workspace transactions with rollback on failure,
   including the split-aware step of invariant 10.
4. Observe `OnSplitTabChanged` (`chrome/browser/ui/tabs/tab_strip_model_observer.h`)
   only to keep the workspace projection coherent. Do not mirror the payload.
5. Add restart recovery and corruption fallback tests for workspace metadata.
6. Compile and run the pinned Windows Chromium target before claiming the
   feature as shipped.

Removed from the sequence: the former step 4, "add two-pane split metadata and
focus routing". There is no such work.

## 8. What this revision withdraws

A reader of the previous contract should be able to see exactly what changed.

| Withdrawn | Why |
|---|---|
| The §1 row "Split panes, orientation, ratio — Sunshine window session metadata" | Chromium owns all three in the tab strip and the session file |
| The split half of invariant 8 ("damaged split metadata is ignored") | Sunshine writes no split metadata, so it has none to damage |
| The `columns` / `rows` orientation vocabulary | The only orientation vocabulary is now `SplitTabLayout::kSideBySide` / `kStacked`. The original rationale — avoid confusion with tab-strip orientation — is better served by the upstream names, which contain no axis word at all |
| `leading` / `trailing` pane names and Sunshine-owned pane focus | Upstream uses `SplitTabActiveLocation {kStart, kEnd, kTop, kBottom}` and owns pane focus in `MultiContentsView` |
| The ratio range `[0.2, 0.8]` and the clamp-on-drag rule | Invented. Upstream constrains by pixels, not by a fixed fraction: `MultiContentsView` clamps to `kMinWebContentsSize` or 10% of available width and snaps to `0.5` |
| Split state in window session extra-data | A second authority for state Chromium already persists and restores |
| The acceptance line "split open, resize, swap, pane close, and restart recovery preserve tab state" as *Sunshine* evidence | Now upstream's acceptance criterion, not Sunshine's |
| The acceptance line "a malformed split record falls back to one pane" | No Sunshine split record exists |
| The UX rule blocking "same-tab split attempts" | Structurally impossible upstream; a rule that cannot be violated is not a rule |

Retained without change: invariants 1 to 4 and 7, the workspace catalog schema,
the forbidden-durable-key list (now extended), and the profile boundary.

## 9. Open questions for the product owner

1. Should `kSplitViewHorizontal` be enabled in the Sunshine build, giving users
   stacked splits, or does Sunshine ship upstream's side-by-side-only default?
2. Should `kSplitViewTabRestore` be enabled, so that closing both halves of a
   split and reopening restores the split rather than two loose tabs?
3. When a user moves one member of a split to another workspace, is dissolving
   the split (invariant 10) the right default, or should Sunshine offer to move
   both members? The dissolve matches upstream's own behaviour for pin and
   group operations; the offer is friendlier and costs a prompt.
4. Should a workspace be allowed to *contain* a split at all in the MVP, given
   that `docs/WORKSPACE_NATIVE_INTEGRATION_MAP.md` currently declares split view
   out of scope for the first runtime experiment? That declaration was written
   when split view was Sunshine's to build; it now describes a feature that
   arrives whether Sunshine acts or not.

## 10. Acceptance evidence

- A native tab group survives restart with label, color, membership, and order.
- Three workspaces retain independent visible tab sets in one profile.
- Switching workspaces does not reload pages or alter cookies.
- A grouped tab move cannot create a cross-workspace group.
- A split's two tabs always report the same workspace; moving one of them out
  dissolves the split before the membership changes, and both tabs survive.
- Switching away from and back to a workspace leaves an open split open, with
  the same two tabs, the same orientation, and the same ratio.
- The workspace projection performs zero tab moves; a session that opens a
  split, switches workspaces repeatedly, and switches back still has the split.
- A restart restores the split from Chromium's session data alone, with no
  Sunshine split record present in any profile or window store.
- Incognito and Guest state is not written to persistent workspace metadata.

Status of that evidence: **NOT RUN**. It requires the pinned Windows build,
which is **NOT AVAILABLE** in this wave.

Until the pinned Windows build and runtime suite pass, this work is reported as
an **implementation foundation**, not a completed browser feature.
