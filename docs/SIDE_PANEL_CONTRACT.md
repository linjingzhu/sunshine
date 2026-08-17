# Side Panel — Native Ownership and Lazy-Mount Contract

## Status and scope

This contract applies to Sunshine OS on the pinned Chromium revision
`152.0.7977.42` recorded in `config/chromium.version`. It covers section 7.6 of
`docs/SUNSHINE_OS_STAGE_1_TO_3_IMPLEMENTATION_HANDOFF.md`: the side panel and
its initial panel modules — tabs, bookmarks, history, downloads — the deferral
of AI and app panels, and the requirement that panels are lazy-mounted and do
not force background loading on every browser window.

This wave is **documentation-only**. It adds no downstream patch, no first-party
module manifest, and no registered command. Nothing here has been built or run;
see *Not verified*.

| In scope | Out of scope |
|---|---|
| Which side-panel infrastructure Sunshine uses and why | The visual design of any panel |
| Which of the four panels Sunshine contributes and which it inherits | Chromium's own panel entries (Reading List, Read Anything, Lens, extensions) |
| The lazy-mount performance contract and how a violation is detected | Absolute performance numbers, which do not exist until a native build does |
| Panel state scope, session restore, split interaction, width floor, keyboard access | The command palette (§7.8) and the toolbar pinning UX |
| The eligibility rule that keeps AI and apps deferred | Whether AI or apps are ever built |

## 1. Decision: Sunshine rides on Chromium's side panel

Chromium at the pinned revision already owns a complete side panel: a resizable
per-window pane, a coordinator that arbitrates which entry is visible, per-window
and per-tab registries, lazy content creation with view caching, a readiness
protocol for content that is not instantly paintable, width and alignment
preferences, toolbar pinning, animation, and pane-level accessibility.

**Sunshine contributes entries to that infrastructure. It does not build a second
panel container, a second registry, a second coordinator, or a Sunshine-owned
docked surface beside the native one.**

The alternative — a Sunshine-owned pane hosted next to Chromium's — was
considered and rejected on five grounds:

1. **It would be a second owner of the same screen region.** Two panes competing
   for the same horizontal space, each with its own width preference, alignment,
   animation and resize handle, is a layout conflict with no correct resolution.
   The user would be able to open both and lose the page.
2. **Extensions register into the native registry.** The pinned revision has an
   extension-owned side panel path. A Sunshine-owned container would either hide
   extension panels or render them in a place inconsistent with every other
   Chromium build, which is exactly the kind of silent incompatibility
   `docs/EXTENSION_COMPATIBILITY_GATE.md` exists to prevent.
3. **The lazy-mount guarantee is enforceable only where creation happens.**
   Upstream already defers content creation to first show and caches the created
   view on the entry. A parallel container would have to reimplement that, and
   the requirement in §7.6 would then depend on Sunshine code being right rather
   than on an upstream mechanism that thousands of engineers exercise daily.
4. **Accessibility and input are already solved there.** The native panel is an
   accessible pane with keyboard pane rotation, keyboard resize with an
   announced result, and correct unhandled-key routing out of hosted web content.
   Rebuilding that would be invisible in a demonstration and wrong for a
   screen-reader user.
5. **Patch budget.** `docs/decisions/0002-native-chromium-downstream.md` commits
   Sunshine to a small, defensible patch series. A parallel panel container is
   the single largest browser-chrome patch this product could take on, against
   frequently-changing upstream layout code, in exchange for nothing the user can
   see.

### What "riding on it" means concretely

| Concern | Owner | Sunshine's part |
|---|---|---|
| The pane, its width, resize, alignment, animation, header, borders | Chromium | none |
| Which entry is visible, entry switching, precedence between per-tab and per-window registries | Chromium | none |
| Registration and deregistration of an entry | Chromium registry | Sunshine registers its own entries and deregisters them |
| Creation of an entry's content view | Chromium calls the entry's content callback on first show | Sunshine supplies the callback for its own entries only |
| Readiness of not-instantly-paintable content | Chromium's content-readiness proxy | Sunshine marks its own content available when it is genuinely paintable |
| Width preference per entry id, panel alignment | Chromium profile preferences | Sunshine writes none of its own |
| Toolbar button, pinning, open triggers, open/hide metrics | Chromium | Sunshine surfaces entry points that resolve a command |

Sunshine may not patch the coordinator, the registries, the pane, or any
upstream entry to change which entry is shown, to reorder entries, to suppress
an entry it did not register, or to force one open.

## 2. The four panels: what exists upstream and what Sunshine must contribute

The pinned revision enumerates its side-panel entry ids in one macro list. Two of
the four panels §7.6 asks for are already there; two are not. This distinction
decides all the work.

| §7.6 panel | Upstream state at `152.0.7977.42` | Sunshine's decision |
|---|---|---|
| Bookmarks | Native entry `kBookmarks`, registered per window by `BookmarksSidePanelCoordinator`, content is a native WebUI view over `bookmarks::BookmarkModel` | **Inherit unchanged.** Sunshine registers nothing, patches nothing, and adds no second bookmarks panel. |
| History | Native entry `kHistory` registered by `HistorySidePanelCoordinator` behind its own `IsSupported()` predicate, with `kHistoryClusters` registered or deregistered as the Journeys preference changes | **Inherit unchanged.** Where `IsSupported()` is false the panel is absent; Sunshine must not substitute a first-party history panel to "fix" that. |
| Downloads | **No entry exists.** There is no downloads id in the entry list; downloads are presented by the native download bubble and `chrome://downloads` | **Contribute one entry**, presenting the native download model. |
| Tabs | **No entry exists** for the current window's tabs. `kTabsFromOtherDevices` is a different product (other devices' sessions), not a tab list | **Contribute one entry**, presenting `TabStripModel` and Sunshine workspace membership. |

Consequences that follow and are not negotiable:

- Sunshine's side-panel work is **two entries, not four**. A wave that produces
  four first-party panels has duplicated two Chromium features and must be
  rejected in review.
- The bookmarks and history panels are governed by
  `docs/BOOKMARKS_HISTORY_CONTRACT.md`. Sunshine adds no bookmark or history
  panel behaviour of its own, which means it also adds no bookmark or history
  panel bug.
- A Sunshine downloads panel is an additional presentation of the native
  download model, never a replacement for the native download bubble and never a
  second warning surface. `docs/DOWNLOAD_SAFETY.md` applies to it in full.
- A Sunshine tabs panel is a navigation surface over the native tab strip. The
  invariants of `docs/TAB_WORKSPACE_SPLIT_CONTRACT.md` apply to it in full; in
  particular a tab still has exactly one native owner and at most one workspace,
  and the panel is not a place where that can be bent.

## 3. Data ownership: no shadow copies

Every panel in scope displays data Chromium already owns. None of them may hold
truth.

| Panel | Authoritative owner | The panel may hold | The panel must never |
|---|---|---|---|
| Tabs | `TabStripModel` and `TabGroupModel` for live tabs; Sunshine workspace metadata for membership, as already defined in `docs/TAB_WORKSPACE_SPLIT_CONTRACT.md` | A transient render model built at mount from the native models, invalidated by native observers while mounted | Persist a tab list, cache titles/favicons/URLs beyond the mounted lifetime, reorder tabs except by asking the native model, resurrect a closed tab from its own memory, or record a tab's identity by index, pointer, or URL |
| Bookmarks | `bookmarks::BookmarkModel` | nothing — Sunshine registers no bookmarks panel | exist |
| History | `history::HistoryService` | nothing — Sunshine registers no history panel | exist |
| Downloads | `DownloadManager`, presented through Chromium's download UI model and command layer | A transient list of the native items visible while mounted | Keep a download database, retain a completed item after the native model drops it, re-derive danger state, enable an action the native command layer disables, store file paths or URLs, or write telemetry containing either |

A transient view model is permitted only while the panel is mounted. It must be
rebuilt from native models on mount, invalidated by native observers, never
become a recovery path, and never cross a profile boundary.

## 4. Lazy mount — the load-bearing requirement

§7.6 states this in eleven words. Stated that way it is unfalsifiable, and the
failure mode is silent: a panel that quietly instantiates in every window costs
memory and startup time that nobody attributes to it for years. This section
makes it checkable.

### 4.1 Four states, named

| State | Meaning | Cost |
|---|---|---|
| **Registered** | The entry's key and its content callback exist in a window's registry. The panel appears in the panel's entry list. | One small object. No content, no renderer, no service. |
| **Mounted** | The user opened the panel; the content callback ran; the view exists and, for WebUI content, a renderer hosts it. | The real cost. |
| **Cached** | The panel was mounted, then a *different* entry was shown while the panel stayed open. The view is retained for fast switching. | Still real: a retained view and, for WebUI content, a retained renderer. |
| **Discarded** | The content view is destroyed. The entry stays registered. | Back to registered. |

The requirement in §7.6 is precisely: *registration is per-window and free;
mounting is per-user-action and never implied by window creation.*

### 4.2 What must be true at window creation

For every Sunshine-contributed entry, at the moment a browser window finishes
opening, and for every subsequent window:

1. The entry is registered. Its content callback has **not** run.
2. Zero content views exist for it. Opening *N* windows creates zero panel
   content views, not *N*.
3. No renderer process exists on its behalf. The count of renderer processes
   hosting a Sunshine panel's WebUI equals the number of windows in which the
   user has opened that panel — never the number of windows.
4. It holds no handle to a profile-keyed service, and it has caused no
   profile-keyed service to load. If the history, bookmark, or download service
   is loaded when a window opens, it is because Chromium loaded it, not because a
   panel asked.
5. It has registered no observer on `TabStripModel`, `DownloadManager`, or any
   other model. Observers are established at mount and torn down at discard.
6. It has issued no network request, started no timer, scheduled no delayed or
   idle task, read no file, and performed no disk I/O.
7. It has read no user data. Deciding whether to register may read a preference;
   it may not read the data the panel would display.
8. Its registration cost is bounded by the number of entries, not by the number
   of tabs, bookmarks, history rows, downloads, or workspaces.

### 4.3 What a panel may do before it is first opened

Exactly two things:

- **Answer an eligibility question.** A static, synchronous predicate over build
  flags, policy, profile mode, and preferences — the same shape as the upstream
  history panel's `IsSupported()`. It may not query the data source.
- **Register or deregister itself when that predicate changes.** Observing a
  preference is permitted; observing a data model is not.

Nothing else. Not "prewarming", not "prefetching the first page of results", not
"keeping the list fresh so opening feels instant", not "loading in the background
after N seconds of idle". Every one of those is the prohibited behaviour wearing
a different noun.

### 4.4 What happens when the panel is closed

This is where a lazy-mount contract usually leaks, so the answer is explicit and
it is not the convenient one.

| Event | Sunshine-contributed entry |
|---|---|
| User switches to a different entry while the panel stays open | **Cached.** Fast switching is the reason the upstream cache exists, and the panel is open, so the cost is already being paid. |
| User closes the panel | **Discarded.** The content view is released and, for WebUI content, its renderer goes with it. Not hidden, not kept warm. |
| Active tab changes | No effect. Sunshine registers no per-tab entries in Stage 3 (§5). |
| Window loses focus, is minimised, or is occluded | No state change. Sunshine adds no idle-based unmounting; Chromium's own renderer management applies. |
| Window closes, profile shuts down | Everything for that window is destroyed. Nothing survives to the next window or the next launch. |
| Chromium clears cached entry views | Obeyed. Sunshine must not retain a view upstream has asked it to release. |

The reason for discarding on close rather than staying warm: a warm panel costs a
retained renderer *per window*. Multiplied across the windows a workspace user
keeps open, that is the same arithmetic §7.6 prohibits, arrived at one window at
a time. Reopening a panel rebuilds a list from an in-memory native model; it is
not an expensive operation, and if measurement ever shows otherwise the fix is a
measured, recorded decision to cache — not an unexamined default.

Two rules make discarding safe:

- **A panel must be discardable without user-visible loss.** Selection, scroll
  offset, and an in-progress filter string may be lost when the user closes the
  panel. Nothing else may be, because nothing else may live only in the panel.
- **A cached or discarded panel does no work.** While not shown, a Sunshine panel
  holds no model observers, runs no timer, and performs no rendering. If a panel
  cannot be made inert while cached, it must be discarded instead.

Sunshine controls the lifetime of its own entries only. It must not force-clear,
discard, or otherwise interfere with the cached content of Chromium's entries;
their lifetime is Chromium's decision and changing it is interposition.

### 4.5 Cross-window and cross-launch rules

9. Opening a panel in window A creates nothing in window B. Panel state is not
   broadcast, mirrored, or synchronised between windows.
10. A newly created window opens with the panel **closed**, regardless of the
    state of the window that spawned it. Inheriting "open" would make one user
    action mount content in every future window, which is the prohibited
    behaviour with a friendlier name.
11. Session restore never opens a panel. Restoring a window with thirty tabs
    mounts zero panels (§5).
12. No Sunshine code path opens a panel automatically: not on first run, not
    after an update, not on a navigation, not on a download starting, not on a
    promotion or tip. A panel opens because a person invoked a command.
13. If an inherited Chromium entry violates 9–12 at some future revision, that is
    an upstream roll finding to be raised upstream, not something Sunshine
    corrects with a patch or a compensating layer.

### 4.6 How a regression is detected

An invariant nobody measures is a comment. Each of these is a gate, not a hope.

| # | Detection | Fails when |
|---|---|---|
| D1 | Every Sunshine panel's content callback increments a mount counter, exposed to browser tests and recorded as a session histogram of mounts per panel. | A test that opens five windows, restores a thirty-tab session, and never touches a panel sees a non-zero count. |
| D2 | A browser test asserts the number of renderer processes hosting Sunshine panel WebUI equals the number of *shown* panels. | It ever equals the number of windows. |
| D3 | A test asserts each unmounted panel's service handles and model observer registrations are empty. | A panel observes a model it is not displaying. |
| D4 | Window-creation time and per-window memory are measured with Sunshine panel registration enabled and disabled; the delta is the registration cost, recorded at the first native build as the baseline under §9.2 and thereafter gated as no-regression. | Registration cost grows without a recorded decision. |
| D5 | A no-network assertion over the panel's lifetime from registration to first mount. | A panel touches the network before a user opens it. |
| D6 | Upstream roll gate: re-check that the pinned revision still creates entry content on first show, still caches on the entry, and still exposes a way to release that cache; re-run D1–D5. | Upstream changes the lazy-creation model. The response is to re-plan, not to layer a Sunshine mechanism over it. |
| D7 | Each panel's shipped resources are a named line item in the release report required by `docs/SIZE_BUDGET.md`, counted in installed application size. | A panel grows the bundle past an investigation threshold without review. |

D1 is the cheapest and the most important: one counter, incremented in one place,
turns "must not force background loading" into a test that fails in CI on the day
the behaviour regresses instead of during a performance investigation two years
later.

## 5. Panel state scope and session restore

| State | Scope | Persisted? | Owner |
|---|---|---|---|
| Panel open/closed, and which entry is shown | **Per window**, in memory | **No** | Chromium coordinator |
| Panel width, keyed by entry id | Per profile | Yes — Chromium's own preference | Chromium |
| Panel alignment (left/right) | Per profile | Yes — Chromium's own preference | Chromium |
| Toolbar pinning of an entry | Per profile | Yes — Chromium's own preference | Chromium |
| Anything else | — | — | Nothing else exists |

Decisions, since §7.6 is silent on all of them:

- **Per window, not per profile.** Two windows on one profile may show different
  panels, or one may show none. A panel is a property of a window's layout, the
  same way a split is.
- **Not per workspace.** Switching workspace must not open, close, or change the
  panel. Per-workspace panel memory sounds appealing and is a trap: it makes a
  workspace switch mount content, so a user cycling workspaces pays repeated
  mount costs for a surface they did not ask for, and the panel appears and
  disappears under the pointer during an operation whose purpose is to change
  *tabs*.
- **Open state is not restored.** After restart, windows open with the panel
  closed. Persisting it would mean every restored window mounts a panel at
  startup — the precise failure §7.6 names, triggered by the one event where
  Chromium is already doing the most work. Width and alignment do persist,
  because they are cheap, they are Chromium's preferences, and they do not cause
  a mount.
- **No per-tab entries in Stage 3.** Chromium's registries support per-tab
  contextual entries. Sunshine registers none: a per-tab entry mounts and hides
  as the user switches tabs, which is the highest-frequency mount trigger in the
  browser, and none of the four required panels is about the current page.
- **Sunshine persists no panel state at all.** No entry in workspace metadata, no
  window session extra-data, no first-party preference. The persisted-state
  table above has no Sunshine row, and that is intentional.

If a future product decision requires the panel to reopen after restart, it
requires an accompanying measurement of restart cost with the panel mounted and a
recorded amendment to this section. It is not a preference someone adds.

## 6. Interaction with split view

The panel and a split compete for the same horizontal space:
a split places two independently focusable panes in the contents
region (`docs/TAB_WORKSPACE_SPLIT_CONTRACT.md` §2 and §5), and the panel takes
its width from that same region.

1. The panel and a split coexist. Neither implies nor forbids the other.
2. The panel takes its width first; the remaining contents width is divided
   between the panes according to the split's own ratio. Opening or closing the
   panel changes the panes' pixel widths, never their ratio, and never their
   membership.
3. Opening the panel never closes a split, never swaps panes, and never changes
   which pane is focused.
4. Opening, reversing and exiting a split never change which panel is shown,
   whether the panel is open, or its width. In particular reversing a split
   exchanges pane positions and must not flip panel alignment.
5. The panel is one surface per window, not one per pane. There is no pane-scoped
   panel, and the panel does not follow pane focus.
6. A tabs panel shows the window's tabs including both tabs currently in panes; a
   tab in a pane is marked as such and activating it does not silently pull it
   out of the split.
7. Where the window is too narrow for both, §7 decides, deterministically.

## 7. Minimum window width and the deterministic fallback

Upstream facts at the pinned revision: the side panel's default *and* minimum
content width is 360 px plus border insets; a user-chosen width per entry id is
stored in a profile preference and used in place of the default; the panel
enforces its minimum during resize; and the contents region enforces its own
minimum web-contents width, with a smaller constrained minimum in a split.

Sunshine's rule, in one sentence: **the panel never wins a width fight against
live page content, and the browser never enters a state the user did not choose.**

Define, for the current window:

- `panel_floor` = the panel's minimum content width plus its insets;
- `contents_floor` = the minimum width Chromium requires for the contents region
  in its current configuration — one web contents, or two panes plus the split's
  separator when a split is active.

The ladder, evaluated in order:

| Condition | Behaviour |
|---|---|
| `window ≥ panel_floor + contents_floor` | Normal. The panel opens at its remembered or default width and may be resized down to `panel_floor`. |
| Panel closed, split closed, `window < panel_floor + contents_floor` | The open-panel command is **unavailable**, with the reason stated: the window is too narrow. It does not open cramped, does not overlay the page, and does not float. |
| Panel closed, split open, `window < panel_floor + contents_floor` | The open-panel command is **unavailable**, and the reason names the split: close a pane or widen the window. Opening the panel must never close a pane on the user's behalf. |
| Panel open, split closed, window is shrunk below the floor | The panel closes and its content is discarded. Page content survives. |
| Panel open, split open, window is shrunk below the floor | **The panel closes; the split survives.** Deterministic and asymmetric on purpose: the panes hold live documents with scroll position, form state, and media, while the panel is a navigational list that costs nothing to reopen. |
| Window is widened again | **Nothing reopens.** Automatic reopening is an automatic mount, and §4.5 rule 12 forbids it. The command becomes available again; the user decides. |

A panel closed by the width ladder is closed for the same reasons as any other
close: the content is discarded (§4.4), the toolbar's pinned state is untouched,
and the close is attributed in metrics to a layout constraint rather than a user
action.

Any panel Sunshine contributes must be usable, not merely renderable, at
`panel_floor` — at 200% zoom, in both text directions, and with a screen reader.
A panel that needs more than the minimum width to be usable is a panel that will
be closed by the ladder on a laptop, which means it is not a panel.

## 8. Keyboard access and focus order

1. Every panel action is reachable from the keyboard. Opening, closing, switching
   entry, resizing, and operating every control inside the panel are all
   keyboard-operable, and each disabled control states its reason.
2. The panel participates in Chromium's pane rotation as an accessible pane. It
   is reachable without the pointer and without knowing a Sunshine-specific
   shortcut.
3. Focus order follows the visual order and therefore follows panel alignment:
   toolbar and bookmark bar, then the panel if it is left-aligned, then the
   contents region — first pane, then second pane when a split is active — then
   the panel if it is right-aligned. It never depends on which surface was opened
   most recently.
4. Opening the panel moves focus into it and announces the panel's name. Closing
   it returns focus to the control that invoked it, or to the active web contents
   if that control no longer exists. Focus is never dropped to nothing.
5. No panel takes focus it was not given: not on registration, not on tab change,
   not on entry deregistration, not on a data update.
6. Keyboard resize remains available and continues to announce the resulting
   width, as upstream does. Sunshine must not regress that when it contributes an
   entry.
7. Keys the panel's content does not handle return to the browser, so global
   shortcuts continue to work while focus is inside a panel.
8. Tab order inside a panel is a single forward sequence with no trap; Escape
   from panel content returns focus to the panel's own controls, and closing is
   an explicit action, never an incidental effect of pressing Escape in a text
   field.
9. Live updates — a download progressing, a tab title changing — must not move
   focus, must not re-announce the whole list, and must not reorder rows under a
   keyboard user's cursor.

## 9. Panel eligibility: why AI and apps are deferred

"Later AI/apps are explicitly deferred" is a promise until it is a rule. This is
the rule. A first-party module may contribute a side panel entry only if it
satisfies **all** of the following. Failing any one defers it, and the deferral
ends when the criterion is met — not when the feature is wanted.

| # | Criterion | Why |
|---|---|---|
| E1 | It presents data whose authoritative owner is a Chromium profile-keyed service or the tab strip, and it introduces no new authoritative store. | §3.3 domain ownership. A panel is a view. |
| E2 | It needs no network access; its module manifest declares `network_access: false`. | A panel is a browser surface, not a client. Network turns a lazy-mount question into a latency, consent, and privacy question. |
| E3 | It mounts lazily and discards cleanly, with no state that lives only in the panel. | §4. |
| E4 | It is window-level and navigational: it does not read, observe, or summarise the content of the active page. | §3.1 — a module must not become a path from page content into first-party code. |
| E5 | It is usable at the minimum panel width, at 200% zoom, keyboard-only, and with a screen reader. | §7, §8. |
| E6 | It holds no secret and depends on no client-side enforcement; every guard is enforced where the command executes. | Sunshine surfaces are inspectable — `docs/BROWSER_UTILITIES_CONTRACT.md`, developer-tools policy. |
| E7 | Its actions are registered commands with one owning module, an availability predicate, a telemetry event, and error results. | §3.2 command-first rule. |
| E8 | Disabling the module leaves browsing, the other panels, and the panel container fully operational. | `docs/FIRST_PARTY_MODULE_ARCHITECTURE.md`. |

Applying it:

- **Tabs panel** — satisfies E1–E8. Eligible.
- **Downloads panel** — satisfies E1–E8, and additionally inherits every rule in
  `docs/DOWNLOAD_SAFETY.md`: it must not re-derive danger state, must not enable
  an action Chromium disables, and must not become a second warning surface.
  Eligible.
- **AI panel** — fails E2 (a model is a network service), fails E4 (its value
  proposition is reading the page), and fails E6 unless every credential lives
  behind a browser-process boundary. Three independent failures, each of which is
  a product and security decision rather than an implementation detail. Deferred.
- **Apps panel** — fails E1 (an app inventory is a new authoritative store) and
  usually E2. It also collides with §7.7 of the handoff, which distinguishes
  installed web apps from future Sunshine native apps. That distinction is now
  less decided than it looks: the handoff drew it by URL scheme, and
  `docs/decisions/0003-internal-scheme.md` settles that Sunshine registers no
  scheme, so future native apps have no address of their own and the panel has
  no field to sort its two categories by. A panel cannot ship before the
  distinction is re-drawn on something that exists. Deferred.

Extension-provided panels are Chromium's, not Sunshine's. They are governed by
`docs/EXTENSION_COMPATIBILITY_GATE.md`; Sunshine neither suppresses nor
privileges them, and this eligibility list does not apply to them.

## 10. Commands are deferred, deliberately unnamed

Opening, closing, and switching a panel are user-visible actions, so §3.2 makes
each of them a command with one implementation, an availability predicate, a
telemetry event, and error results. No such command is registered today.

`first_party/commands.json` is the only authoritative list, and this document
names no identifier that is not already in it. A contract that invented panel
command ids ahead of the registry would recreate exactly the drift the registry
exists to prevent — the same drift that kept a stale split-view "toggle" alive in
prose after the split contract had replaced it.

When panel commands are registered, they must satisfy:

- one command per user-visible action, dispatched through the same command
  service used by the toolbar, menus, gestures, and later the palette;
- availability predicates that encode the width ladder in §7 and each panel's
  eligibility predicate, so a too-narrow window produces a stated reason rather
  than a silent no-op;
- an owner: a command that opens an inherited Chromium panel is
  `chromium`-owned and carries no Sunshine guard; a command that opens a
  Sunshine-contributed panel is owned by the module that declares the entry;
- no command that opens a panel as a side effect of an unrelated action.

## 11. Prohibited duplicate state

Sunshine code must not introduce:

- a second side panel container, registry, coordinator, or docked surface;
- a Sunshine-owned bookmarks or history panel while Chromium ships one;
- a persisted record of panel open state, visible entry, width, or alignment;
- a per-workspace or per-tab panel memory;
- a tab list, download list, bookmark tree, or history result set that outlives
  the mounted panel;
- a prefetch, prewarm, idle-load, or background refresh path for panel content;
- a panel-owned copy of a download's danger state, file path, or URL;
- telemetry containing a tab title, URL, download filename, bookmark title, or
  history query.

## 12. Acceptance criteria

Checkable once a native build exists. Criteria 1–8 are the ones that decide
whether §7.6 was actually implemented.

**Lazy mount**

1. Open five windows and restore a thirty-tab session without touching a panel:
   the mount counter for every Sunshine panel is zero, no renderer hosts panel
   WebUI, and no panel holds a service handle or model observer.
2. Open a panel in window A: exactly one content view and, for WebUI content, at
   most one renderer appears; window B is unchanged.
3. Close that panel: the content view is destroyed and the renderer is released
   within one second; a subsequent memory sample returns to the pre-mount level
   within the recorded tolerance.
4. Switch entries with the panel open: the previous entry's view is cached, holds
   no model observers, and performs no rendering while not shown.
5. Restart with the panel previously open: every restored window opens with the
   panel closed and the mount counter at zero.
6. Open a new window from a window with the panel open: the new window's panel is
   closed.
7. Trigger a download, a bookmark change, and a tab-group change with no panel
   open: no panel mounts and no panel-owned observer fires.
8. Per-window memory delta and window-creation time with panel registration
   enabled versus disabled are within the baseline tolerance recorded at the
   first native build.

**Ownership**

9. The bookmarks and history panels present are Chromium's, with no Sunshine
   entry registered for either id.
10. Where the upstream history panel reports itself unsupported, no panel
    appears and no Sunshine substitute appears.
11. The downloads panel shows exactly the items the native download model holds;
    a completed item removed natively disappears from the panel without a reload;
    every action goes through the native download command layer and a disabled
    action is disabled in the panel.
12. A dangerous download shows Chromium's warning treatment; the panel neither
    upgrades, downgrades, nor duplicates it, and warning display and user action
    are recorded once on the correct surface.
13. The tabs panel reflects `TabStripModel` order, group membership, and active
    tab exactly; reordering from the panel changes the native model, and no tab
    identity is derived from an index or a URL.
14. Closing and reopening the tabs panel loses nothing but scroll position and
    filter text.

**Layout, width, split**

15. With a split active, opening the panel changes both panes' widths and neither
    pane's ratio, membership, or focus.
16. Split open, swap, and close leave the panel's open state, entry, and width
    unchanged.
17. In a window narrower than the floor, the open-panel command is unavailable
    and states its reason; in a split, the reason names the split.
18. Shrinking a window with both open closes the panel and preserves both panes;
    widening it again reopens nothing.
19. At the minimum panel width, at 200% zoom, in RTL, and with a screen reader,
    every panel's controls are reachable and labelled.

**Keyboard and accessibility**

20. Pane rotation reaches the panel; focus order matches §8 rule 3 for both
    alignments and with a split active.
21. Opening announces the panel; closing returns focus to the invoking control.
22. Keyboard resize works and announces the result.
23. A progressing download and a changing tab title move no focus and reorder no
    row under a keyboard user's cursor.

**Privacy and profile**

24. In incognito, no panel writes to the regular profile; closing the last
    incognito window leaves no Sunshine-owned record of its tabs or downloads.
25. Panel telemetry contains no title, URL, filename, or query.

**Roll gate**

26. At each upstream roll, the source paths in §13 still exist or their
    replacements are identified, upstream still creates entry content on first
    show, and criteria 1–25 are re-run. A changed upstream behaviour blocks the
    roll for review; it is not corrected by layering a Sunshine implementation
    over Chromium.

## 13. Implementation authority in the pinned revision

| Concern | Chromium source |
|---|---|
| Entry identity, lazy content callback, view caching, show/hide notifications, default content width (`kSidePanelDefaultContentWidth`) | [`chrome/browser/ui/side_panel/side_panel_entry.h`](https://github.com/chromium/chromium/blob/152.0.7977.42/chrome/browser/ui/side_panel/side_panel_entry.h) |
| The authoritative list of entry ids | [`chrome/browser/ui/side_panel/side_panel_entry_id.h`](https://github.com/chromium/chromium/blob/152.0.7977.42/chrome/browser/ui/side_panel/side_panel_entry_id.h) |
| Entry key, including the extension-provided case | [`chrome/browser/ui/side_panel/side_panel_entry_key.h`](https://github.com/chromium/chromium/blob/152.0.7977.42/chrome/browser/ui/side_panel/side_panel_entry_key.h) |
| Per-window and per-tab registries, registration/deregistration, cached-view clearing | [`chrome/browser/ui/side_panel/side_panel_registry.h`](https://github.com/chromium/chromium/blob/152.0.7977.42/chrome/browser/ui/side_panel/side_panel_registry.h) |
| The side panel API: show, close, toggle, current entry, shown-state observation | [`chrome/browser/ui/side_panel/side_panel_ui.h`](https://github.com/chromium/chromium/blob/152.0.7977.42/chrome/browser/ui/side_panel/side_panel_ui.h) |
| Open triggers, hide reasons, content-readiness states | [`chrome/browser/ui/side_panel/side_panel_enums.h`](https://github.com/chromium/chromium/blob/152.0.7977.42/chrome/browser/ui/side_panel/side_panel_enums.h) |
| Readiness protocol for content that is not instantly paintable | [`chrome/browser/ui/side_panel/side_panel_content_proxy.h`](https://github.com/chromium/chromium/blob/152.0.7977.42/chrome/browser/ui/side_panel/side_panel_content_proxy.h) |
| Coordinator: registry consolidation, precedence of per-tab over per-window, population, cached-view clearing | [`chrome/browser/ui/views/side_panel/side_panel_coordinator.h`](https://github.com/chromium/chromium/blob/152.0.7977.42/chrome/browser/ui/views/side_panel/side_panel_coordinator.h) |
| The pane itself: minimum size, width preference, alignment, resize, header, animation, open/close | [`chrome/browser/ui/views/side_panel/side_panel.h`](https://github.com/chromium/chromium/blob/152.0.7977.42/chrome/browser/ui/views/side_panel/side_panel.h) |
| Hosting WebUI content in a panel, including keyboard-event routing back to the browser | [`chrome/browser/ui/views/side_panel/side_panel_web_ui_view.h`](https://github.com/chromium/chromium/blob/152.0.7977.42/chrome/browser/ui/views/side_panel/side_panel_web_ui_view.h) |
| Bookmarks panel registration and content | [`chrome/browser/ui/views/side_panel/bookmarks/bookmarks_side_panel_coordinator.h`](https://github.com/chromium/chromium/blob/152.0.7977.42/chrome/browser/ui/views/side_panel/bookmarks/bookmarks_side_panel_coordinator.h) |
| History panel registration, support predicate, Journeys preference handling | [`chrome/browser/ui/views/side_panel/history/history_side_panel_coordinator.h`](https://github.com/chromium/chromium/blob/152.0.7977.42/chrome/browser/ui/views/side_panel/history/history_side_panel_coordinator.h) |
| Per-window ownership of the coordinator and every panel coordinator | [`chrome/browser/ui/browser_window/public/browser_window_features.h`](https://github.com/chromium/chromium/blob/152.0.7977.42/chrome/browser/ui/browser_window/public/browser_window_features.h) |
| Panel width-by-entry-id and alignment preferences | [`chrome/common/pref_names.h`](https://github.com/chromium/chromium/blob/152.0.7977.42/chrome/common/pref_names.h) |
| Contents-region minimums when two contents views are shown side by side | [`chrome/browser/ui/views/frame/multi_contents_view.h`](https://github.com/chromium/chromium/blob/152.0.7977.42/chrome/browser/ui/views/frame/multi_contents_view.h) |

These paths are this contract's evidence, not an instruction to modify them.

## 14. Decisions required from the product owner

| Priority | Decision | Required by |
|---|---|---|
| P1 | Does the tabs panel list only the active workspace's tabs, or all workspaces in the profile with the inactive ones collapsed? The second requires reading workspace metadata for contexts that are not projected, and interacts with the open P1 question in §11 of the handoff about a workspace spanning windows. | Before the tabs panel is designed |
| P1 | Does the downloads panel replace the native download bubble as the default surface, or coexist with it? This contract assumes coexistence; replacing it is a change to a shipped safety surface and needs an explicit decision. | Before the downloads panel ships |
| P2 | Is a keyboard shortcut assigned to the panel, and if so is it per-entry or a single "last entry" toggle? Only the latter is compatible with "no automatic mount". | Before panel commands are registered |

## 15. Not verified

Nothing in this document has been executed. Specifically:

- no Chromium checkout, configuration, compilation, or link of the pinned
  revision; no Sunshine or Chromium binary was launched on any platform;
- no acceptance criterion in §12 was run; no visual, accessibility,
  localisation, or keyboard verification of any panel was performed;
- no performance, memory, renderer-count, or size measurement exists — every
  budget in §4.6 is defined as a procedure, not as a number, because the number
  does not exist yet;
- the source paths in §13 were confirmed to exist at `refs/tags/152.0.7977.42`
  by retrieving each file from the upstream mirror on 2026-08-17, and the
  statements drawn from them (entry id list, minimum content width, lazy content
  callback and view caching, per-window ownership, the two width/alignment
  preferences, absence of a preference recording panel open state) are read from
  those files. Their *runtime* behaviour is unverified: no build was made and no
  code was executed;
- the width-ladder thresholds in §7 combine an upstream minimum that was read
  from source with a contents-region minimum whose exact application by the
  browser layout code was **NOT VERIFIED**; the ladder's ordering is a Sunshine
  decision, not an upstream behaviour;
- no downstream patch, no first-party module manifest, and no command-registry
  change accompanies this document.

## 16. Completion gate

This contract is complete when reviewed. Section 7.6 is complete when the two
inherited panels have been exercised unmodified on a native pinned build, the two
Sunshine-contributed panels exist as registered modules with registered commands,
criteria 1–26 have passed on the supported desktop platforms, and the first
native build has recorded the baselines that §4.6 gates against.
