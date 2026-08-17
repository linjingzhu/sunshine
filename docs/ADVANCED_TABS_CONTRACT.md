# Advanced Tabs — Native Ownership Contract

**Status:** Documentation-only wave. No downstream patch, no first-party module,
no registered command.
**Target:** Pinned Chromium revision in `config/chromium.version` (`152.0.7977.42`).
**Settles:** section 7.4 of
`docs/SUNSHINE_OS_STAGE_1_TO_3_IMPLEMENTATION_HANDOFF.md` — pin/unpin, native
tab groups, tab search, recently closed, duplicate detection, and the tab-strip
orientation sentence attached to them.

Where this document and handoff section 7.4 disagree, this document is the
implementation instruction and section 9 records why. Where this document and
`docs/TAB_WORKSPACE_SPLIT_CONTRACT.md`, `docs/TAB_LIFECYCLE_CONTRACT.md`,
`docs/OMNIBOX_CONTRACT.md`, or `docs/BOOKMARKS_HISTORY_CONTRACT.md` appear to
disagree, those documents win and the disagreement is a defect in this one.

## 0. Evidence basis

Every statement below about upstream behaviour was read from the pinned tag over
the GitHub raw mirror on 2026-08-17, file by file. Statements are labelled:

- **read-from-source** — taken from a file fetched at `152.0.7977.42`;
- **NOT LOCATED** — searched for at the pinned tag and not found in the files
  read; absence is not proven, only unlocated;
- **NOT RUN** / **NOT AVAILABLE** — a measurement that has not been taken.

No Chromium build was compiled, no browser was launched, no screenshot was
taken, and no telemetry was collected for this document: build **NOT RUN**,
runtime **NOT RUN**, visual **NOT RUN**.

Section 7.4 gives five feature names in three sentences and no observable
definition for any of them. The method used here was to establish what the
pinned revision already ships for each of the five *before* specifying anything,
on the precedent of `docs/TAB_WORKSPACE_SPLIT_CONTRACT.md` §0 — where a Sunshine
split-view model was found to have re-derived `SplitTabCollection` because
nobody checked upstream first.

## 1. Decision, per feature

| Handoff feature | Does Sunshine write code? | Why |
|---|---|---|
| Pin / unpin | **No** | Complete upstream: model, ordering constraint, menus, command IDs, observation, session persistence, startup persistence. Sunshine registers no command and stores no pinned state. One workspace seam is a *rule*, not code (§3.1, §4). |
| Native tab groups | **No new work** | Complete upstream and already contracted. `docs/TAB_WORKSPACE_SPLIT_CONTRACT.md` invariant 2 and the two registered commands `tab.group.create` / `tab.group.ungroup` are the whole of Sunshine's interest. This document adds nothing and deliberately does not restate it (§3.2). |
| Tab search | **No search code; two seam patches, conditionally** | Enumeration, filtering, ranking, recently-closed merge, and the surface all ship upstream. What does not exist upstream is any notion of a workspace, so a result can activate a tab the user cannot see. That is one commit-path rule and one attribution rule (§4), not a search feature. |
| Recently closed | **No** | Owned by `sessions::TabRestoreService`; ownership already settled by `docs/BOOKMARKS_HISTORY_CONTRACT.md`. One seam — a reopened tab's workspace membership — is real and is the subject of §5 and open question Q3. |
| Duplicate detection | **Yes — the only one** | No user-facing duplicate detection ships at the pinned revision. The one deduplication that does ship is a display filter inside Tab Search, one-directional and scoped to that surface (§3.5). §6 specifies what Sunshine may build. |

Four of five are inherited. This matches the outcome of
`docs/BROWSER_UTILITIES_CONTRACT.md`, reached independently for section 6.6, and
is the expected outcome under
`docs/decisions/0002-native-chromium-downstream.md`.

## 2. Ownership boundary

| Concern | Authority | Persistence |
|---|---|---|
| Pinned state of a tab; pinned/unpinned ordering | Chromium `TabStripModel`, `PinnedTabCollection` | Chromium session restore; Chromium startup preferences |
| Tab group id, label, colour, collapse, membership | Chromium `TabGroupModel` / `TabGroupVisualData` | Chromium tab-group and session state |
| Open-tab enumeration, filtering, ranking, presentation for tab search | Chromium Tab Search browser handler and its WebUI | None — computed per invocation |
| Closed tabs, groups, splits, and windows; reopen | Chromium `sessions::TabRestoreService` | Chromium; in-memory, capped, profile-keyed |
| Workspace membership of any tab named by any of the above | **Sunshine** | Workspace catalog and tab session extra-data, per `docs/TAB_WORKSPACE_SPLIT_CONTRACT.md` §3 |
| Whether a set of open tabs is a duplicate set | **Sunshine** | **Nothing.** Derived on demand, never stored (§6) |
| Tab-strip orientation | Chromium; Sunshine chooses the flag state | Chromium window state |

## 3. What the pinned revision already ships

### 3.1 Pin and unpin

All read-from-source.

| Capability | Where it lives at the pinned tag |
|---|---|
| Set and read pinned state | `chrome/browser/ui/tabs/tab_strip_model.h` — `SetTabPinned(int, bool)` returning the possibly-changed index, `IsTabPinned(int)`, `IndexOfFirstNonPinnedTab()` |
| Bulk pin, split-aware | `chrome/browser/ui/tabs/tab_strip_model.h` — `SetTabsPinned(std::vector<int>, bool)`: if the indices contain all tabs of a split the whole split is pinned; otherwise the tabs are processed individually and the split is dissolved |
| Pinned region as tab-strip structure | `components/tabs/public/pinned_tab_collection.h`, `components/tabs/public/unpinned_tab_collection.h`, `components/tabs/public/tab_strip_collection.h` |
| Per-tab read | `components/tabs/public/tab_interface.h` — `IsPinned()` |
| Ordering constraint | `chrome/browser/ui/tabs/tab_strip_model.h` class comment: pinned tabs are locked to the leading side, the model keeps all pinned tabs at the beginning, and a move request that would violate this is **ignored** |
| Entry points | `chrome/app/chrome_command_ids.h` — `IDC_PIN_TARGET_TAB`, `IDC_WINDOW_PIN_TAB`; `chrome/browser/ui/browser_commands.h` — `PinTab`, `PinKeyboardFocusedTab`; tab context menu `CommandTogglePinned` and `WillContextMenuPin(int)` in `chrome/browser/ui/tabs/tab_strip_model.h` |
| Change notification | `chrome/browser/ui/tabs/tab_strip_model_observer.h` — `OnTabPinnedStateChanged(tabs::TabInterface*, int)` |
| Session persistence | `components/sessions/core/session_types.h` (`SessionTab`); `components/sessions/core/tab_restore_types.h` — `tab_restore::Tab::pinned` |
| Startup persistence when the session is not restored | `chrome/browser/ui/tabs/pinned_tab_service.h` and `chrome/browser/ui/tabs/pinned_tab_codec.h` — writes the pinned set to profile preferences on exit, reads it back at startup |

The single fact that produces a Sunshine rule: `chrome/browser/ui/startup/startup_tab.h`
defines `StartupTab` as a `GURL`, a `Type` of `kNormal` / `kPinned` /
`kFromLastAndUrlsStartupPref`, and an untrusted-launch bit. There is **no**
extra-data map on it. Read-from-source. A pinned tab that returns through the
`PinnedTabCodec` path therefore returns carrying no Sunshine identifier of any
kind. See invariant AT-3.

### 3.2 Native tab groups

Ownership is complete upstream (`chrome/browser/ui/tabs/tab_group_model.h`,
`components/tabs/public/tab_group.h`, `components/tabs/public/tab_group_tab_collection.h`,
`components/tab_groups/tab_group_id.h`, `components/tab_groups/tab_group_visual_data.h`,
`chrome/browser/ui/views/tabs/tab_group_header.h`,
`chrome/browser/ui/tabs/existing_tab_group_sub_menu_model.h`,
`chrome/browser/ui/tabs/tab_group_features.h`), and Sunshine's interest in it is
already settled by `docs/TAB_WORKSPACE_SPLIT_CONTRACT.md` invariant 2 and its
two registered commands.

This document adds no group rule, no group invariant, and no group command. It
records one previously unstated fact and one question:

- Read-from-source, `components/saved_tab_groups/public/features.h` declares
  `kTabGroupsSaveV2`, `kTabGroupSyncCoordinator` helpers, and
  `kForceRemoveClosedTabGroupsOnStartup`. A saved group is a **cross-device**
  object. Sunshine's workspace UUID is profile-local and travels in tab session
  extra-data; it does not travel with a synced group. A group saved on one
  device and opened on another therefore arrives with no workspace membership.
  The default flag states of that file were **NOT RUN** for this wave.
- The recovery rule for that case is already written: a tab whose workspace
  membership is missing or unknown recovers into Default
  (`docs/TAB_WORKSPACE_SPLIT_CONTRACT.md` invariant 8). No new rule is needed;
  see open question Q4 on whether it is the *desired* rule.

### 3.3 Tab search

All read-from-source.

| Capability | Where it lives at the pinned tag |
|---|---|
| Surface and host | `chrome/browser/ui/views/tab_search_bubble_host.h`; WebUI host `tab-search.top-chrome` in `chrome/common/webui_url_constants.h`; controller `chrome/browser/ui/webui/tab_search/tab_search_ui.h` |
| Entry points | `chrome/app/chrome_command_ids.h` — `IDC_TAB_SEARCH`, `IDC_TAB_SEARCH_CLOSE`, `IDC_TAB_SEARCH_TOGGLE_PIN`; `chrome/browser/ui/browser_commands.h` — `ShowTabSearch`, `CloseTabSearch`, `ToggleTabSearchPin` |
| Data contract | `chrome/browser/ui/webui/tab_search/tab_search.mojom` — `ProfileData` carrying `Window`, `TabGroup`, `RecentlyClosedTab`, `RecentlyClosedTabGroup`, `RecentlyClosedSplitView` |
| Enumeration scope | `chrome/browser/ui/webui/tab_search/tab_search_page_handler.cc` — `CreateProfileData` iterates every current browser window ordered by activation and keeps a window when its profile matches and its type is the normal window type; `WalkContainer` then walks the tab-strip collection tree of each kept window |
| Matching and ranking | `chrome/browser/resources/tab_search/search.ts` — weighted per-field exact search with a scoring function, run in the WebUI; the browser supplies only case- and accent-insensitive match ranges through `GetRangesIgnoringCaseAndAccents` |
| Commit and mutation | `chrome/browser/ui/webui/tab_search/tab_search_page_handler.h` — `SwitchToTab`, `CloseTab`, `CloseTabs`, `OpenRecentlyClosedEntry`, `ReplaceActiveSplitTab` |
| Preference | `chrome/browser/ui/webui/tab_search/tab_search_prefs.h` — the recently-closed section expanded state |

Two facts here are load-bearing for Sunshine and are easy to get wrong.

**The result set already spans everything Sunshine hides.** `CreateProfileData`
is scoped to the profile and to normal windows, not to a window and not to a
visible tab set. Under `docs/TAB_WORKSPACE_SPLIT_CONTRACT.md` invariant 11 the
workspace projection never moves a tab in the tab strip — it hides and shows.
A hidden tab is therefore still in the `TabStripModel`, still in the collection
tree, and still walked by `WalkContainer`. Tab Search will list it. This is the
same collision `docs/OMNIBOX_CONTRACT.md` §10 resolves for open-tab matches, one
surface later.

**`Tab.visible` is not a workspace bit and must never be used as one.**
Read-from-source, `chrome/browser/ui/webui/tab_search/tab_search_page_handler.cc`
sets `tab_mojom_data->visible = tab->IsVisible()`, and
`components/tabs/public/tab_interface.h` documents `IsVisible()` as *whether the
tab is visible in the contents area of the browser window*, matching the
attached state except where a feature provides multiple visible tabs per window
— that is, the foreground tab, or both panes of a split. It is unrelated to
widget visibility or occlusion. `docs/TAB_LIFECYCLE_CONTRACT.md` §6.4 already
fixes that count at exactly one, or two while a split is open. The field's only
consumer in the WebUI sorts already-visible tabs to the bottom of the list
(`chrome/browser/resources/tab_search/tab_search_page.ts`). Repurposing it to
mean "in the active workspace" would both break that sort and put a Sunshine
concept into a Chromium field.

### 3.4 Recently closed

All read-from-source.

| Capability | Where it lives at the pinned tag |
|---|---|
| Store and API | `components/sessions/core/tab_restore_service.h` — `CreateHistoricalTab`, `CreateHistoricalGroup`, `CreateHistoricalSplit`, `BrowserClosing`, `entries()` ordered most-recent-first, `RestoreEntryById`, `RestoreMostRecentEntry`, `RemoveEntryById`, `ClearEntries`, `DeleteNavigationEntries` |
| Entry shapes | `components/sessions/core/tab_restore_types.h` — `Entry` with `id`, `original_id`, `type`, `timestamp`, `extra_data`; subtypes `Tab`, `Split`, `Group`, `Window` |
| Cap | `components/sessions/core/tab_restore_service_helper.h` — `kMaxEntries = 25` |
| Profile scoping | `chrome/browser/sessions/tab_restore_service_factory.h` |
| Observation | `components/sessions/core/tab_restore_service_observer.h` |
| Surfaces | `chrome/app/chrome_command_ids.h` — `IDC_RESTORE_TAB`; `chrome/browser/ui/browser_commands.h` — `RestoreTab`, `OpenWindowWithRestoredTabs`; `chrome/browser/ui/tabs/recent_tabs_sub_menu_model.h` (local closed entries plus other-device open tabs); the Recently Closed section of Tab Search |

The seam is precise and is the most valuable finding in this wave.

`tab_restore::Entry` carries an `extra_data` map, and
`components/sessions/core/tab_restore_service_helper.cc` fills it on close from
`LiveTabContext::GetExtraDataForTab(index)`. But read-from-source,
`chrome/browser/ui/browser_live_tab_context.cc` implements that method by
populating **only** the assistant keys and returning. It does not copy
`SessionTab::extra_data`. On the restore side,
`chrome/browser/ui/browser_tabrestore.cc` passes the map into tab creation
where exactly two named consumers read it back. There is no generic path that
turns a restore entry's `extra_data` into the restored tab's session
extra-data.

Consequence, stated plainly: **at the pinned revision, a tab reopened through
the tab-restore service carries no Sunshine workspace UUID, ever.** Not because
the field is missing — because nothing writes it and nothing reads it. This is
also the two-line answer to *what would have to change* if Sunshine wanted the
opposite: `GetExtraDataForTab` on the write side, and one consumer on the
restore side. See §5 and Q3.

Note also that `tab_restore::Window::workspace` is a `std::string` naming the
**platform virtual desktop**, matching `LiveTabContext::GetWorkspace()`. It is
not a Sunshine workspace and must never be read or written as one. This name
collision is the single most likely way for an implementer to corrupt window
placement while believing they are storing workspace membership.

### 3.5 Duplicate detection

**No user-facing duplicate detection ships at the pinned revision.** The
supporting evidence, in the order it was gathered:

- `chrome/browser/ui/tabs/BUILD.gn` at the pinned tag lists no declutter or tab-organization
  target; `chrome/browser/ui/BUILD.gn` names no such dependency. Five paths from
  earlier revisions were probed by hand and all five return 404 at
  `152.0.7977.42`: the tab-declutter controller under both a tabs/organization
  and a tabs/declutter directory, the tab-declutter controller directly under
  tabs, and the tab-organization service and utils headers under
  tabs/organization. They are named here without backticks precisely because
  they do not exist at the pinned tag and a citation of a non-existent path
  fails the build. **This is exactly the kind of claim that must be checked
  rather than remembered:** those files were real in earlier revisions.
- `chrome/browser/ui/tabs/organizer/BUILD.gn` and
  `chrome/browser/ui/tabs/organizer/organizer_utils.cc` show the surviving
  `organizer` target is the saved-tab-groups panel gated on
  `tab_groups::IsOrganizerPanelFeatureEnabled()` and a profile preference. It is
  not duplicate detection. `IDC_ORGANIZE_TABS` exists in
  `chrome/app/chrome_command_ids.h`.
- `chrome/browser/ui/ui_features.cc` declares `kTabStripDeclutter` as
  `FEATURE_DISABLED_BY_DEFAULT`, reachable through `IsTabStripDeclutterEnabled()`
  which also returns true under `kDesktopGlowUp`. Its tab-side implementation
  is **NOT LOCATED** in the files read.
- `chrome/browser/ui/ui_features.cc` declares `kTabDuplicateMetrics` as
  `FEATURE_ENABLED_BY_DEFAULT`. Its consumer is **NOT LOCATED**. By name it
  records metrics; nothing read attaches it to a user-visible affordance.

The one deduplication that genuinely ships, read-from-source in
`chrome/browser/ui/webui/tab_search/tab_search_page_handler.h` and `.cc`:

```
typedef std::tuple<GURL, std::optional<base::Token>> DedupKey;
```

`WalkContainer` inserts `DedupKey(tab->url, tab->group_id)` for each open tab
**and pushes the tab into the window's list unconditionally**.
`AddRecentlyClosedTab` then refuses a closed entry whose key is already present,
and separately refuses the New Tab Page URL and invalid URLs.

Three properties follow, and all three matter:

1. It is **one-directional**. Open tabs are never suppressed against each other.
   Two identical open tabs both appear in Tab Search today.
2. It is **display-only and per-invocation**. Nothing is stored; the set is
   rebuilt on every `GetProfileData`.
3. Its key includes **group identity**, so the same URL in two different groups
   is deliberately not a duplicate.

Property 3 is upstream telling us something: a duplicate is not "the same URL
twice", it is "the same URL twice in the same context". Sunshine has one more
context dimension than Chromium does, and §6 uses it.

## 4. Non-negotiable invariants

Numbering is stable; sibling contracts may cite these by number. `AT-` is the
prefix for this document.

1. **AT-1. Sunshine stores no pinned state.** Pinned state is read from
   `TabStripModel` when needed. No workspace record, catalog field, module, or
   preference mirrors it. Handoff §7.3 describes a workspace as storing "its own
   tab membership/order, pinned tabs", and the §4 domain-model table repeats
   "tabs, pinned tabs" as workspace contents; that clause is withdrawn
   (§9), because it creates a second authority for a value Chromium already
   persists twice.
2. **AT-2. Pinning is window-global, not workspace-scoped.** The pinned region
   is contiguous at the head of the tab strip and the model ignores moves that
   would break that (read-from-source, `chrome/browser/ui/tabs/tab_strip_model.h`).
   A pinned tab belonging to an inactive workspace stays in that region while
   hidden. Sunshine must not renumber, re-cluster, or re-pin to make the pinned
   region look per-workspace: under
   `docs/TAB_WORKSPACE_SPLIT_CONTRACT.md` invariant 11 any such reordering
   destroys splits it steps through, and under this invariant it also fights a
   constraint the model enforces unilaterally.
3. **AT-3. A pinned tab restored through the startup-preferences path recovers
   into Default.** `StartupTab` carries a URL and a type and nothing else, so no
   membership can survive that path. This is the ordinary missing-membership
   recovery of `docs/TAB_WORKSPACE_SPLIT_CONTRACT.md` invariant 8, not a new
   failure mode, and it must be stated rather than discovered. It applies only
   when the startup preference is not "restore the previous session"; on the
   session-restore path membership travels in tab session extra-data as usual.
4. **AT-4. Tab search results are never filtered by workspace.** A user who has
   a page open must be offered it. This is `docs/OMNIBOX_CONTRACT.md` OT-3
   applied to the second surface that enumerates open tabs; filtering would make
   Tab Search lie about the browser's state, and would also silently reduce a
   count the user can verify by looking at the strip.
5. **AT-5. Committing a tab-search result for a tab in an inactive workspace
   performs the workspace switch first, then activates the tab.** One commit,
   one visible outcome. This is `docs/OMNIBOX_CONTRACT.md` OT-1, and it is the
   same transition `workspace.switch` produces. The alternative — activating a
   hidden tab in place — would violate
   `docs/TAB_LIFECYCLE_CONTRACT.md` §10.1, under which the active tab and the
   active workspace can never disagree.
6. **AT-6. A tab-search result that will change the workspace is attributable to
   its workspace before commit.** `docs/OMNIBOX_CONTRACT.md` OT-2, restated for
   this surface. Attribution is presentation; it adds no field to
   `tab_search.mojom` that Sunshine then treats as state.
7. **AT-7. `TabInterface::IsVisible()` and the `visible` field of
   `tab_search.mojom` are contents-area visibility and are never read or written
   as workspace visibility.** See §3.3 and `docs/TAB_LIFECYCLE_CONTRACT.md` §6.4.
8. **AT-8. Closing tabs from tab search is a close transaction, not a loop.**
   `CloseTabs` takes a set. It resolves under `docs/TAB_LIFECYCLE_CONTRACT.md`
   §7.1 — the closing set is computed once, successor selection is restricted to
   the active workspace, and exactly one activation change occurs.
9. **AT-9. Sunshine keeps no recently-closed store.** Already required by
   `docs/BOOKMARKS_HISTORY_CONTRACT.md`; restated because the Tab Search
   Recently Closed section makes a second cache look convenient. The cap of 25
   entries and the ordering are Chromium's and are displayed as given.
10. **AT-10. A reopened tab's workspace is decided by one rule, applied
    everywhere.** Whichever rule Q3 settles on, `IDC_RESTORE_TAB`, the recent
    tabs submenu, and the Tab Search Recently Closed section must produce the
    same outcome, because all three call the same service. A per-surface rule
    would make the browser's behaviour depend on which affordance the user
    happened to use.
11. **AT-11. `tab_restore::Window::workspace` is the platform virtual desktop
    and is never read or written as a Sunshine workspace.** See §3.4.
12. **AT-12. Duplicate detection is derived, never stored.** No duplicate set,
    duplicate group id, duplicate count, canonical-URL table, or "primary of a
    duplicate set" is persisted anywhere, in any schema version. It is recomputed
    per invocation, like Chromium's own `DedupKey` set.
13. **AT-13. Duplicate detection never closes a tab on its own.** It reports;
    the user acts. Any resulting close runs through `tab.close` semantics and
    invariant AT-8. There is no automatic, timed, idle-triggered, threshold-
    triggered, or startup-triggered duplicate close.
14. **AT-14. Duplicate detection reads no page content.** It compares the values
    the tab strip already exposes. It does not read the DOM, the accessibility
    tree, page text, response bodies, or favicon bytes, and it sends nothing to
    any endpoint.

## 5. The recently-closed workspace seam

Stated as behaviour, because the choice is a product choice and §3.4 has already
established the mechanics.

Today, at the pinned revision and with no Sunshine patch:

- closing a tab creates a `tab_restore::Tab` whose `extra_data` holds no
  Sunshine key;
- reopening it creates a tab with no workspace membership;
- under `docs/TAB_WORKSPACE_SPLIT_CONTRACT.md` invariant 8 that tab recovers
  into Default;
- so a user working in workspace *Development* who reopens a closed tab gets it
  in *Default*, and — under `docs/TAB_LIFECYCLE_CONTRACT.md` §10.1, since the
  active tab and active workspace cannot disagree — either the tab is
  immediately hidden or the window changes workspace. Both are surprising.

`docs/TAB_LIFECYCLE_CONTRACT.md` §10.2 gives the origin table a row reading
"Restored by the session service **or the restore service** → the workspace UUID
in its tab session extra-data; Default when missing or unknown". For the session
service that row is implementable. For the restore service it currently resolves
to "Default, always", which is almost certainly not what the row intends. That
is recorded as a defect in §9 and as Q3.

Two candidate rules, both consistent with the sibling contracts, one of which
must be chosen before implementation:

| Rule | Cost | Behaviour |
|---|---|---|
| **R1 — reopen into the window's active workspace.** Treat a reopened tab as a tab created with no opener. | Zero patch. Consistent with `docs/TAB_LIFECYCLE_CONTRACT.md` §10.2's own "created with no opener" row. | Reopening in *Development* puts the tab in *Development*. Membership is not restored; it is assigned. |
| **R2 — carry membership through the restore entry.** Write the workspace UUID in `GetExtraDataForTab`, read it back where the restored tab is created. | Two small patch points, both in `chrome/browser/ui/`, both files that change upstream. Paid at every roll. | Reopening restores the tab to the workspace it was closed from, which may not be the active one — so the reopen must then obey AT-5. |

R1 is the recommendation of this document: it costs nothing, it never activates
a tab into a workspace the user is not in, and it makes reopen behave like every
other opener-less tab creation. R2 is defensible but buys back a property no
user has asked for yet, and it makes reopen able to change the visible workspace.
The owner decides (Q3).

## 6. Duplicate detection — the specification

This is the one feature of section 7.4 that is Sunshine's, and it is small.
Nothing in this section is authorised for implementation before Q1 and Q2 are
answered.

### 6.1 What a duplicate is

A **duplicate set** is two or more open tabs, in one profile, whose comparison
key is equal. The key is:

> (last committed URL exactly as the tab reports it, native group id or none,
> workspace id)

Rationale for each term:

- **Last committed URL, exact.** Not a normalised, query-stripped,
  fragment-stripped, or host-only form. A normalisation that discards the query
  calls two different search results the same page; one that discards the
  fragment calls two positions in one long document the same page. Chromium's
  own `DedupKey` compares a `GURL` and does not normalise. A tab with no
  committed entry is not a member of any duplicate set — the same exclusion
  `WalkContainer` applies.
- **Group id.** Copied from upstream's key. The same reference page deliberately
  opened inside two different groups is two working contexts, not a mistake.
- **Workspace id.** The Sunshine term. Two copies of one URL in two workspaces
  are the direct analogue of two copies in two groups. Without this term, the
  feature would tell a user that the tab they deliberately keep in *Reading* is
  a duplicate of the one in *Development*, and would offer to close a tab the
  user cannot currently see.

Excluded from consideration entirely, mirroring upstream: the New Tab Page,
invalid or empty URLs, and any tab with no last committed entry. First-party
`chrome://sunshine-*` surfaces are excluded on the same grounds — they are
browser chrome the user did not navigate to, and per
`docs/decisions/0003-internal-scheme.md` there is no other Sunshine scheme to
consider.

### 6.2 What it does

- Reports duplicate sets on demand, when the user asks for them. It does not run
  on a timer, on idle, at startup, or on every navigation (AT-13).
- Presents each member with the workspace it belongs to, so that a set spanning
  workspaces is legible as such before any action (the AT-6 rule, applied here).
- Offers to close all but one member of a set. The retained member is the one
  the user picks; if the user does not pick, the retained member is the most
  recently active. Never the first in strip order, which is a position and not a
  preference.
- Executes any resulting close as one transaction under AT-8, so successor
  selection happens once.

### 6.3 What it must never do

- Persist anything (AT-12).
- Close anything without an explicit user action on the reported set (AT-13).
- Read page content (AT-14).
- Merge, transfer, or discard navigation history from a closed member into the
  retained one. Two tabs with the same current URL have different back stacks;
  closing one loses that back stack, and that is the honest outcome. Anything
  else fabricates a navigation history the user never performed.
- Dissolve a split, unpin a tab, or move a tab as a side effect. A duplicate
  that is pinned or in a split is reported and, if the user closes it, closed —
  with the native consequences of `RemoveSplit` and nothing added on top.
- Silently close a member the user cannot see. A close that includes a tab in an
  inactive workspace must say so before it happens.
- Be named or presented in a way that can be confused with `tab.duplicate`,
  which is the registered command that *creates* a copy of a tab. The two are
  opposites and share a word.

### 6.4 Commands

**No command is registered for duplicate detection in this wave.** Registering
one is a coordinated edit across `first_party/commands.json`, this document, and
`tests/test_command_registry.py`, and it must not happen before the feature is
authorised. Candidate identifiers, owners, availability predicates, error
results, and unavailable reasons are recorded in the wave report for the owner
to accept or reject; they are deliberately absent from this document so that no
unregistered identifier can be quoted from it.

The existing registered commands are sufficient for everything else in section
7.4: `tab.group.create` and `tab.group.ungroup` for groups, `tab.close` for the
close path, `workspace.switch` for the transition AT-5 requires, and `tab.new`,
`tab.duplicate`, `workspace.tab.move`, `workspace.create`, `workspace.close`
unchanged. Pin/unpin, tab search, and recently closed reach the user through
Chromium's own menus, buttons, and accelerators, exactly as the seven utilities
of `docs/BROWSER_UTILITIES_CONTRACT.md` do.

## 7. Feature-flag policy

Read-from-source, `chrome/browser/ui/tabs/features.cc` and
`chrome/browser/ui/ui_features.cc` at the pinned tag. These are the flags in
section 7.4's territory; the split-view flags are governed by
`docs/TAB_WORKSPACE_SPLIT_CONTRACT.md` §6 and are not repeated.

| Flag | Declared in | Default at `152.0.7977.42` | Effect if left alone |
|---|---|---|---|
| `kVerticalTabsLaunch` | `chrome/browser/ui/tabs/features.h` | **`FEATURE_ENABLED_BY_DEFAULT`** except on ChromeOS, where it is disabled | Vertical tabs are available to users **by default**. See §7.1. |
| `kVerticalTabs` | `chrome/browser/ui/tabs/features.h` | `FEATURE_DISABLED_BY_DEFAULT` | Redundant while the launch flag is on: `IsVerticalTabsFeatureEnabled()` returns true if **either** is enabled |
| `kVerticalTabsToggleInTabContextMenu` | param of `kVerticalTabsLaunch` | `true` | The orientation toggle appears in the tab context menu |
| `kVerticalTabsExpandOnHover` | `chrome/browser/ui/tabs/features.h` | `FEATURE_DISABLED_BY_DEFAULT` | Collapsed vertical strip does not expand on hover |
| `kVerticalTabsNewBadge` | `chrome/browser/ui/tabs/features.h` | `FEATURE_ENABLED_BY_DEFAULT` | A "new" badge is shown for the feature |
| `kTabStripUnification` | `chrome/browser/ui/tabs/features.h` | `FEATURE_DISABLED_BY_DEFAULT` | Off |
| `kTabSearchCjkWordBoundary` | `chrome/browser/ui/tabs/features.h` | `FEATURE_DISABLED_BY_DEFAULT` | Tab-search matching does not apply CJK word-boundary handling |
| `kTabStripDeclutter` | `chrome/browser/ui/ui_features.h` | `FEATURE_DISABLED_BY_DEFAULT`, but `IsTabStripDeclutterEnabled()` also returns true under `kDesktopGlowUp` | Implementation **NOT LOCATED** (§3.5); the composed predicate means enabling an unrelated umbrella flag turns it on |
| `kTabDuplicateMetrics` | `chrome/browser/ui/ui_features.h` | `FEATURE_ENABLED_BY_DEFAULT` | Consumer **NOT LOCATED**; by name, metrics only |
| `kBackToOpener` | `chrome/browser/ui/tabs/features.h` | `FEATURE_DISABLED_BY_DEFAULT` | Back in a newly opened tab does not close it and return to the opener |

### 7.1 The horizontal tab strip sentence is now a decision

Handoff section 7.4 ends: "The initial Sunshine scope keeps Chromium's
horizontal tab strip." When that sentence was written it read as *Sunshine will
not build vertical tabs*. At the pinned revision it no longer means that.
Read-from-source: `kVerticalTabsLaunch` is `FEATURE_ENABLED_BY_DEFAULT` on every
platform except ChromeOS, `IDC_TOGGLE_VERTICAL_TABS` and three companion command
IDs exist in `chrome/app/chrome_command_ids.h`, the context-menu toggle
parameter defaults to `true`, and `chrome/browser/ui/tabs/vertical_tab_strip_state_controller.h`
persists per-window collapsed state and width.

So the sentence now describes one of two different acts:

- **keep the upstream default** — vertical tabs ship, users can switch, and
  "initial Sunshine scope keeps the horizontal strip" describes only the
  *default* orientation, not the available set; or
- **disable an enabled-by-default upstream feature** in the Sunshine build,
  which is a removal of native capability and needs the justification that
  `docs/decisions/0002-native-chromium-downstream.md` demands of any divergence.

This document does not choose. It records that the sentence can no longer be
implemented by doing nothing, which is what it appears to ask for. See Q5.

One derived constraint, whichever way Q5 goes:
`chrome/browser/ui/browser_live_tab_context.cc` writes
`vertical_tab_strip_collapsed` and the uncollapsed width into the tab-restore
service's **window** extra-data map. That is a different map from the session
service's `SessionWindow::extra_data`, where
`docs/TAB_WORKSPACE_SPLIT_CONTRACT.md` §3 places the active workspace, so there
is no conflict today. Sunshine keys in either map must nonetheless be
namespaced and must never overwrite or delete a key it did not write, because
both maps are shared with upstream and both are read at restore.

## 8. UX contract

- **Entry points:** all native. Pin/unpin from the tab context menu and the
  native accelerators; groups from the tab context menu; tab search from its
  tab-strip button and `IDC_TAB_SEARCH`; recently closed from the History menu,
  the native reopen accelerator, and the Tab Search Recently Closed section.
  Sunshine adds no wrapper entry point for any of them.
- **Visible result:** committing a tab-search result for a tab in another
  workspace changes the visible tab set and then activates the tab — one
  transition, not two (AT-5), and the result said so beforehand (AT-6).
- **Blocked behaviour:** there is none to state for pin, groups, or recently
  closed. Cross-profile is structurally impossible: the tab-restore service is
  profile-keyed, tab search filters by profile, and a workspace never crosses a
  profile. A rule that cannot be violated is not written here.
- **Duplicate reporting:** a duplicate set spanning workspaces names its
  workspaces. Closing members that include a tab in an inactive workspace states
  that before it happens. Nothing is closed without the user acting (AT-13).
- **Accessibility:** every native affordance keeps its native keyboard path and
  accessible name. Any Sunshine-added attribution for AT-6 is exposed to the
  accessibility tree, not conveyed by colour alone, on the same terms as group
  identity in `docs/TAB_WORKSPACE_SPLIT_CONTRACT.md` §5.

## 9. Defects and withdrawals

Recorded so that a reader of the handoff can see exactly what changed and why.

| Statement | Where | Disposition |
|---|---|---|
| "Each stores its own tab membership/order, **pinned tabs**, optional home URL…" | Handoff §7.3, repeated as "tabs, pinned tabs" in the §4 domain-model table | **Withdrawn.** Pinned state is Chromium's, persisted by the session service *and* by `PinnedTabCodec`. A third Sunshine copy is a competing authority on the restart path, which is the failure `docs/TAB_WORKSPACE_SPLIT_CONTRACT.md` §3 already forbids for split state. Replaced by AT-1. |
| "duplicate detection" listed beside four inherited features, implying comparable scope | Handoff §7.4 | **Re-scoped.** It is the only one of the five with no upstream implementation, and the only one where Sunshine writes behaviour. §6 bounds it to detect-and-offer. |
| "The initial Sunshine scope keeps Chromium's horizontal tab strip." | Handoff §7.4 | **Re-read as a decision, not a scope note.** Vertical tabs are enabled by default at the pinned revision (§7.1). Escalated as Q5. |
| Origin table row: "Restored by the session service **or the restore service** → the workspace UUID in its tab session extra-data; Default when missing or unknown" | `docs/TAB_LIFECYCLE_CONTRACT.md` §10.2 | **Defect.** Correct for the session service. For the restore service the UUID is *always* missing at the pinned revision (§3.4), so the row silently resolves to "Default, always". Not corrected here — that document is authoritative over this one — but escalated as Q3 with two candidate rules in §5. |
| "Sunshine adds only persistent workspace membership around those native objects" read as covering the tab-search and recently-closed surfaces | `docs/TAB_WORKSPACE_SPLIT_CONTRACT.md` §1 | **Consistent, and extended.** True; but two profile-scoped surfaces enumerate tabs the workspace projection hides, which that document does not mention. AT-4 to AT-6 close the gap by copying `docs/OMNIBOX_CONTRACT.md` OT-1 to OT-3 rather than inventing a second rule. |

Nothing in `docs/BROWSER_UTILITIES_CONTRACT.md`, `docs/BOOKMARKS_HISTORY_CONTRACT.md`,
or `docs/COMMAND_PALETTE_CONTRACT.md` is contradicted by this document.

## 10. Open questions for the product owner

1. **Q1 — Is duplicate detection wanted at all in the MVP?** It is the only one
   of the five that costs implementation, ongoing maintenance, and a new user
   concept. Chromium's own attempt at this class of feature is absent from the
   pinned revision. "Not in the MVP" is a coherent answer and would make section
   7.4 an entirely inherited section.
2. **Q2 — If yes, is the workspace term of the §6.1 key correct?** Including it
   means two copies of a URL in two workspaces are not duplicates. Excluding it
   means the feature will regularly propose closing a tab the user deliberately
   keeps in another context. This document recommends including it.
3. **Q3 — R1 or R2 for a reopened tab's workspace (§5)?** This also decides
   whether the `docs/TAB_LIFECYCLE_CONTRACT.md` §10.2 row is corrected or is
   implemented with a patch. R1 is recommended.
4. **Q4 — What workspace does a synced saved tab group land in on a second
   device (§3.2)?** Default, by the existing recovery rule, is the current
   answer by omission. If that is wrong, the fix is a workspace concept that
   crosses devices, which is well outside this contract and probably outside
   the MVP.
5. **Q5 — Does the Sunshine build disable `kVerticalTabsLaunch`, or ship
   upstream's default with the horizontal strip as the default orientation
   only (§7.1)?**
6. **Q6 — Does AT-6 attribution appear in the Tab Search WebUI, which means a
   downstream patch to `chrome/browser/resources/tab_search/`, or is tab search
   left entirely native and the workspace transition of AT-5 explained only at
   the moment it happens?** The second costs no patch and gives the user less
   warning.

## 11. Acceptance evidence

Each item is falsifiable at runtime once a native build exists.

1. **ATA-1.** Pinning a tab moves it into the pinned region and unpinning
   returns it to the unpinned region, with no Sunshine record written in either
   direction.
2. **ATA-2.** Pinning both members of a split pins the split; pinning one member
   dissolves the split, with both tabs surviving.
3. **ATA-3.** A pinned tab in an inactive workspace stays in the pinned region
   while hidden, and switching workspaces performs zero tab moves.
4. **ATA-4.** With the startup preference set to something other than
   restore-last-session, pinned tabs return at startup and recover into Default,
   with no tab lost.
5. **ATA-5.** Tab search lists tabs from inactive workspaces, and the count of
   listed tabs equals the count of open tabs in the profile's normal windows.
6. **ATA-6.** Committing a tab-search result for a tab in an inactive workspace
   produces exactly one visible transition: the workspace changes, then the tab
   is active. The tab is never active while its workspace is not.
7. **ATA-7.** The number of tabs a window reports as visible in the contents
   area is one, or two while a split is open, regardless of how many workspaces
   hold tabs.
8. **ATA-8.** Closing three tabs from tab search produces one activation change,
   and the successor is in the active workspace.
9. **ATA-9. Not yet evaluable — blocked on Q3.** Reopening a closed tab produces
   the workspace outcome chosen in Q3, and the same outcome from all three
   reopen surfaces.
10. **ATA-10.** No Sunshine-owned file, preference, or catalog field contains a
    pinned flag, a recently-closed entry, a duplicate set, or a canonical-URL
    table, after a session that exercises all of the above and restarts twice.
11. **ATA-11.** Incognito and Guest windows contribute nothing to any persistent
    Sunshine record produced by any of the five features.
12. **ATA-12.** If duplicate detection ships: a duplicate set is reported only
    on request, reports the workspace of each member, retains the member the
    user chooses, and closes nothing until the user acts.

Status of every item above: **NOT RUN**. All require the pinned native build,
which is **NOT AVAILABLE** in this wave.

Until that build and a runtime suite pass, section 7.4 is reported as an
**ownership decision with one authorised feature specification**, not a
completed browser feature.
