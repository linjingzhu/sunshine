# Tab Lifecycle — Native Ownership Contract

## Status and scope

This contract applies to Sunshine OS on the pinned Chromium revision
`152.0.7977.42` recorded in `config/chromium.version`. It settles section 5.4
(Tab state machine) of `docs/SUNSHINE_OS_STAGE_1_TO_3_IMPLEMENTATION_HANDOFF.md`
and the parts of sections 4.1–4.3 that describe a tab as a stored entity.

This wave is **documentation-only**. It adds no downstream patch, no first-party
module, and no registered command. Nothing here has been compiled or observed;
see *Not verified*.

Where this document and handoff section 5.4 disagree, this document is the
implementation instruction and section 12 records why. Where this document and
`docs/TAB_WORKSPACE_SPLIT_CONTRACT.md`, `docs/WORKSPACE_NATIVE_INTEGRATION_MAP.md`,
or `docs/SESSION_PROFILE_CONTRACT.md` appear to disagree, those documents win and
the disagreement is a defect in this one.

Sunshine is a native downstream of open-source Chromium. There is no wrapper
runtime and no intermediary process between the tab strip and a renderer. A
"tab state" in Sunshine is therefore never a stored object; it is a reading taken
from Chromium at the moment it is needed.

## 1. Why section 5.4 is not usable as written

The handoff gives five states, no observable definition for any of them, and no
statement of who computes them. That produces three failure modes, all of which
have been seen in browsers that mirrored a tab model into product code:

1. **Drift.** An event-driven mirror (`Ready` set here, cleared there) diverges
   from the tab strip after any event the mirror does not know about — a
   same-document navigation, a discard, a renderer crash, a restore.
2. **Unfalsifiability.** "Ready" with no predicate cannot be asserted in a test,
   so the state machine cannot fail; it can only be argued about.
3. **Resurrection.** `Closing` drawn as a one-way arrow to `Closed` hides the
   fact that a close can be refused, and hides the fact that a removal is not
   always a close.

This contract replaces the five states with states that each have a predicate
over native objects, and replaces the arrows with a rule about when to re-read
those predicates.

## 2. Ownership

| Concern | Authority | Sunshine's part |
|---|---|---|
| Tab existence, order, pinned state, selection | Chromium `TabStripModel` | Observes; requests activation and close through commands only |
| `WebContents` creation, replacement, and destruction | Chromium | Never constructs, retains, or destroys one |
| Navigation, redirects, commit, error pages, session entries | Chromium `NavigationController` | Reads; never edits, truncates, or reorders entries |
| Loading state and the tab-strip throbber | Chromium | Derives its own `Loading` from the same predicate |
| Title and favicon | Chromium `WebContents` / favicon driver | Renders the value it is given; never fabricates or caches one as truth |
| Freezing, discarding, and memory-pressure policy | Chromium tab lifecycle machinery | Never exempts, forces, or second-guesses a decision |
| Renderer crash detection and the crashed-tab surface | Chromium | Never auto-reloads (`docs/SESSION_PROFILE_CONTRACT.md`) |
| Close, `beforeunload`, unload, and window teardown | Chromium | Never suppresses a dialog or forces a close |
| Recently closed and restore | Chromium `TabRestoreService` | Recovers its own metadata from restored session extra-data |
| Durable tab identity (`sunshine_tab_uuid`) | **Sunshine** | Mints once at insertion; carries it in tab session extra-data |
| Workspace membership (`sunshine_workspace_uuid`) | **Sunshine** | Owns the value; owns nothing else about the tab |
| Which tabs a window currently shows | **Sunshine** | Projection over native tabs; never a second tab list |

## 3. Identity is prior to state

State is meaningless without a stable subject. Every rule below is stated over a
durable identity, never over an index, a `SessionID`, a `WebContents` pointer, or
a URL — all four are already forbidden as durable keys by
`docs/WORKSPACE_NATIVE_INTEGRATION_MAP.md`, and each of them changes during at
least one transition in section 4.

1. `sunshine_tab_uuid` is minted exactly once, at the moment the tab becomes
   observable in a window (`TabStripModelChange::kInserted`), and before any
   asynchronous update for that tab can be delivered to a Sunshine surface.
2. A tab that arrives from session restore already carries its UUID and
   workspace UUID in tab session extra-data and must not be re-minted.
3. Duplicating a tab mints a **new** UUID and copies workspace membership. If a
   duplicate copied the UUID, `recover_membership` in `scripts/workspace_model.py`
   would clear the UUID on *both* tabs at the next restore, silently returning
   both to the Default workspace. This is the single most likely way to lose
   workspace membership in normal use, and it is invisible until restart.
4. Discard, crash, freeze, unfreeze, navigation, move, pin, group, and split all
   preserve the UUID. Only insertion creates one; nothing destroys one except
   the tab's removal.
5. Two live tabs may never hold the same UUID. If the projection observes a
   duplicate, both are treated as unidentified and re-minted, per the existing
   recovery policy; no attempt is made to guess which one was original.

## 4. The state machine

### 4.1 States are predicates, not stored flags

**Invariant 1 — states are derived.** Every state below is a pure function of
native objects, evaluated on demand. Native events say *when* to re-evaluate;
they never *set* a state. No Sunshine field, cache, database row, or session
record stores a tab's lifecycle state, and no state survives a browser restart.

This is what makes the machine falsifiable: for any tab at any moment, the state
can be recomputed from Chromium and compared with what Sunshine is displaying.

| State | Predicate over native objects |
|---|---|
| `Created` | The tab is in a `TabStripModel` and has no committed primary main-frame document yet |
| `Loading` | The tab has live contents and Chromium reports it as loading (`WebContents::IsLoading()`) |
| `Ready` | The tab has live contents, a committed primary main-frame document, and is not loading |
| `Crashed` | `WebContents::IsCrashed()` — the primary main-frame renderer process is gone and no reload has been started |
| `Frozen` | Chromium's tab lifecycle machinery reports the tab as frozen; contents and document still exist |
| `Discarded` | Chromium's tab lifecycle machinery reports the tab as discarded; the tab is still in the strip with no live document |
| `Closing` | A close has been requested for this tab and the outcome (proceed or refuse) is not yet decided |
| `Detaching` | The tab is leaving this window's strip to be inserted into another one |

`Ready` carries one attribute, `document_is_error`, true when the committed
document is a Chromium error page. It is an attribute and not a state; see
section 5.

**Ready is defined by the native loading predicate on purpose.** `DOMContentLoaded`,
`DidFinishLoad`, and first contentful paint were all rejected. The tab strip's
own throbber is driven by the loading predicate, so defining `Ready` the same way
makes it structurally impossible for a Sunshine surface to show a spinner the
tab strip does not, or vice versa. The known consequence is accepted: a tab whose
main document is interactive but whose subframes are still loading is `Loading`,
exactly as the native strip shows it.

Same-document navigations (fragment, History API) do not set the loading
predicate and therefore cause no state change at all. This falls out of the
definition rather than needing a rule, which is the point of defining states by
predicate.

### 4.2 Transitions

`Nonexistent` and `Removed` are not states; nothing is in them. They are listed
so that the boundary conditions are explicit.

| From | Native signal | Condition | To |
|---|---|---|---|
| Nonexistent | `TabStripModelChange::kInserted` | — | `Created` (UUID minted) |
| `Created` | `DidStartNavigation` / loading begins | — | `Loading` |
| `Created` | `TabStripModelChange::kReplaced` from a discard, or restore of an unloaded tab | Tab never loaded | `Discarded` |
| `Loading` | `DidFinishNavigation` then loading ends | Committed, not an error page | `Ready` |
| `Loading` | `DidFinishNavigation` then loading ends | Committed error page | `Ready` with `document_is_error` |
| `Loading` | `DidFinishNavigation` | **Not committed** (aborted, download, 204/205, replaced by a newer navigation) | Unchanged — see section 5.2 |
| `Loading` | `DidStartNavigation` for a new cross-document navigation | — | `Loading` (idempotent; no intermediate state) |
| `Ready` | `DidStartNavigation`, cross-document, primary main frame | Includes reload and back/forward | `Loading` |
| `Ready` / `Loading` | `PrimaryMainFrameRenderProcessGone` | — | `Crashed` |
| `Crashed` | A reload is started by the user, by the native activation behaviour of the pinned revision, or by session recovery | — | `Loading` |
| `Ready` | Tab lifecycle machinery freezes the tab | Tab not visible | `Frozen` |
| `Frozen` | Tab lifecycle machinery unfreezes the tab | Usually on becoming visible | `Ready` |
| `Ready` / `Frozen` | Tab lifecycle machinery discards the tab | Tab not visible | `Discarded` |
| `Discarded` | Activation, or an explicit reload | — | `Loading` |
| Any live state | A close is requested for this tab | — | `Closing` |
| `Closing` | The close is refused (`beforeunload` answered "stay", or the transaction is cancelled) | — | Back to the state its predicates now describe |
| `Closing` | `TabStripModelChange::kRemoved`, deletion reason | — | Removed |
| Any live state | `TabStripModelChange::kRemoved`, inserted-into-another-strip reason | — | `Detaching` |
| `Detaching` | Insertion into the destination strip | — | The state its predicates describe, in the new window |

Two arrows in the handoff have no equivalent here and must not be implemented:
`Loading → Failed` and `Closing → Closed` as an unconditional edge. Section 12
explains both.

### 4.3 Re-entry and idempotency

- Every transition is idempotent. A second `kInserted`-shaped notification for a
  tab already present, a second close request for a tab already `Closing`, or a
  redirect chain of any length must produce the same projection as one.
- No transition may be implemented as a toggle. A projection that flips a flag on
  each event is the drift failure in section 1.
- `Closing` is exited **only** by the close outcome. A navigation, a title
  change, a favicon change, a crash, or a discard occurring while a close is
  pending never returns a tab to a live state.

## 5. Navigation outcomes and history

### 5.1 A failed navigation that commits

Chromium commits an error document. The tab is `Ready` with
`document_is_error`; it is not in a distinct failure state, because everything
true of a `Ready` tab is true of it: it has a document, it can be reloaded, it
can go back, it can be found in, printed, zoomed, and put in a split pane.

- The tab's navigation entries stay under `NavigationController`. Sunshine never
  deletes, rewrites, truncates, reorders, or re-navigates them.
- Back from a committed error page returns to the previous document. Reload
  retries the failed URL. Both are native behaviour reached through
  `browser.back` and `browser.reload`; Sunshine adds no retry of its own and no
  automatic refresh timer.
- Whether an error page is recorded in global history is Chromium's decision
  (`docs/BOOKMARKS_HISTORY_CONTRACT.md`). Sunshine neither adds nor suppresses a
  history entry to make an error look tidier.
- The tab keeps its workspace membership, its position, its pinned state, its
  group, and its pane. A failed navigation is not a reason to move or close a
  tab.

### 5.2 A failed navigation that does not commit

This case is missing from the handoff entirely and is the more common one. A
navigation that turns into a download, returns 204 or 205, is aborted by the
user, is cancelled by the server, or is superseded by a newer navigation, never
commits. The previous document remains, with its scroll position, its form
state, and its entry.

- The tab returns to `Ready` with whatever it was already showing.
- `document_is_error` is **false**. There is nothing wrong with the document
  being displayed.
- Sunshine must show no error state, no toast, and no "page failed" affordance.
  Doing so would report a failure for a page the user is still successfully
  looking at.
- Nothing is written to workspace or session metadata.

Distinguishing the two cases requires reading commit status from the navigation
result, not inferring failure from a network error code. A non-committed
navigation can carry an error code while the tab is perfectly healthy.

### 5.3 History after crash and discard

A `Crashed` tab and a `Discarded` tab both retain their navigation entries. A
reload after either restores the **last** entry, not the first, and restores it
from `NavigationController`. Sunshine holds no URL from which it could
"helpfully" re-navigate, and must never re-navigate a recovering tab to a URL it
remembered.

## 6. Frozen, discarded, and crashed tabs

The handoff's five states do not mention any of these, which means an
implementation following it literally would treat a discard as a close and a
crash as a failed navigation. Both are wrong and both lose user data.

### 6.1 Discard

A discard replaces the tab's contents while the tab stays in the strip. It is
observable as a replacement, not as a removal followed by an insertion.

- **A discard is not a close and not a create.** A projection that mints a UUID
  on every insertion and drops one on every removal must special-case the
  replacement notification, or every memory-pressure event silently renumbers
  tabs and rewrites their workspace membership.
- Nothing about the tab's Sunshine metadata changes, and **no session extra-data
  is written** during a discard.
- A discarded tab keeps its workspace membership, group, pinned state, split
  pane assignment, and position.
- Sunshine must never reload a discarded tab in order to display it. Title, URL,
  and favicon for a discarded tab come from what Chromium retains for it. A tab
  list, side panel, or switcher that touches contents to render a row will
  reload every discarded tab the moment it opens, which is the exact opposite of
  what discarding achieved.

### 6.2 Freeze

A frozen tab still has a document. It is not visible, its timers are stopped,
and it resumes on becoming visible. Sunshine's only obligations are negative: do
not exempt a tab from freezing, do not force a freeze, do not treat frozen as an
error, and do not render a frozen tab differently from any other background tab.

### 6.3 Crash

`docs/SESSION_PROFILE_CONTRACT.md` already governs: native crashed-tab surface,
explicit reload, no continuous auto-reload, same profile, no duplicate entry in
the session model. This contract adds the lifecycle consequences:

- A crashed tab remains a full member of its workspace, its group, and its split
  pane. A crash never dissolves a split and never moves a tab.
- Switching away from and back to a workspace must not reload a crashed tab.
  Workspace switching is not a user request to recover a renderer.
- A crash while a close is pending does not complete the close. The close
  outcome still decides.

### 6.4 Visibility is a lifecycle input, not a cosmetic detail

Chromium decides freezing and discarding from visibility. Sunshine changes what
is visible, so it changes lifecycle policy whether or not it intends to.

1. A tab hidden because its workspace is not active takes the same visibility as
   an ordinary background tab. It becomes freeze- and discard-eligible, and that
   is correct: a workspace the user is not looking at should not hold memory.
   Sunshine must not defeat this by keeping hidden tabs marked visible.
2. The accepted consequence, which must be stated to the user's benefit and not
   hidden: returning to a workspace after long absence may reload some of its
   tabs. That is native behaviour, identical to returning to a long-idle
   background tab.
3. Both tabs in an open split are genuinely visible, including the unfocused
   pane. If the unfocused pane's contents were marked hidden or occluded, Blink
   would throttle its timers and animations and Chromium would consider it
   discardable — producing a pane that visibly stops updating while the user
   watches it.
4. Therefore: the number of tabs a window marks visible is exactly one, or
   exactly two while a split is open. Any other count is a defect.

## 7. Closing

### 7.1 Close is a transaction, not a sequence of removals

Closing one tab, closing other tabs, closing tabs to the right, and closing a
window all produce a **set** of tabs. The set is computed once, before any tab
is removed.

Let `W` be the window, `S` the closing set, `A` the window's active workspace,
and `V = { t ∈ W : t ∉ S and workspace(t) = A }` the candidate successors.

1. Every tab in `S` enters `Closing` before any removal is processed.
2. If the active tab is not in `S`, **no activation change occurs at all.**
3. If `W` itself is closing, or the browser is shutting down, there is no
   successor selection and no tab is created. See 7.3.
4. If `V` is non-empty, the successor is whichever tab Chromium's own successor
   rule selects **when the candidate set is restricted to `V`**. Sunshine
   supplies the restriction; it does not supply the ordering.
5. If `V` is empty but `W` still has tabs in other workspaces, a New Tab is
   created in `A` and activated. See 7.4.
6. If `V` is empty and `W` has no remaining tabs, the window closes natively.
7. Exactly one activation change is observable for the whole transaction.

Rule 7 is the falsifiable form of "activates an adjacent non-closing tab". A
naive implementation that reselects after each removal walks the selection
through several tabs, and each intermediate activation makes a tab visible:
media unmutes, `visibilitychange` fires, lazy content loads, a frozen tab
unfreezes, a discarded tab reloads. Restricting the candidate set *before*
Chromium chooses, rather than correcting Chromium's choice afterwards, is what
prevents this. Correcting afterwards is prohibited for the same reason.

### 7.2 What "adjacent" means

"Adjacent" is not defined by this contract, deliberately. Chromium's successor
rule already accounts for the opener chain, tab-group cohesion, collapsed
groups, and the fall back from the following tab to the preceding one at the end
of the strip. Reimplementing it would be a second tab model in all but name and
would diverge at the first upstream change.

Sunshine contributes exactly two constraints, both expressed as membership of
`V`: a tab in the closing set is never a successor, and a tab outside the active
workspace is never a successor.

### 7.3 The last tab

**Closing the last tab of a window closes the window.** The handoff's rule —
"closing the last normal tab opens a New Tab" — describes behaviour Chromium
does not have, and implementing it would require a patch that breaks the way
every Chromium user closes a window, and that can prevent the browser from
quitting. It is rejected. The window closing is not "a dead browser surface";
it is the expected outcome, and the tabs are recoverable through the native
recently-closed path.

The handoff's rule survives only in the case it was actually reaching for, which
is a Sunshine-specific hazard the handoff could not have named: a window with
hidden tabs in other workspaces, whose *active workspace* has just become empty.
There the window must stay open, because tabs still exist in it.

### 7.4 The empty-workspace New Tab

When rule 5 of 7.1 applies:

- The window does **not** switch to another workspace, and does **not** activate
  a hidden tab. A silent workspace change on close would move the user's context
  without an action they took.
- One New Tab Page is created in `A`, joins `A`, and is activated.
- It is created through the same native path `tab.new` dispatches to, but the
  command's telemetry event is not emitted: telemetry counts user intent, and no
  user asked for this tab.
- This rule is suppressed entirely during window close and browser shutdown. A
  tab created during teardown either resurrects a window the user closed or
  blocks exit.
- Pinned tabs count as members of `V` like any other tab. A workspace whose only
  remaining tab is pinned is not empty.

### 7.5 Refusal and detach

- A close can be refused. `beforeunload` may present a dialog and the user may
  choose to stay; a transaction may also be cancelled before commit. Every tab
  in `S` that is not removed returns to the state its predicates describe, keeps
  its UUID, its membership, its position, and its pane.
- Sunshine never suppresses, auto-answers, pre-empts, or times out a
  `beforeunload` dialog, and never removes a tab from its projection in
  anticipation of a close that has not happened.
- **A removal is not always a close.** A tab dragged out to another window is
  removed from this strip and inserted into another. Treating that as a close
  would discard its workspace membership at exactly the moment the tab is most
  visible to the user. `Detaching` exists so that the removal notification's
  reason must be read.
- A detaching tab keeps its UUID and its workspace UUID; both travel in tab
  session extra-data and are re-read on insertion. Whether the destination
  window adopts that workspace as its active workspace depends on the open P1
  decision in section 14; until it is answered, cross-window tab movement stays
  outside the MVP scope fixed by `docs/WORKSPACE_NATIVE_INTEGRATION_MAP.md`.

## 8. Asynchronous hazards

The handoff states that "favicon and title updates are asynchronous and must be
safe for a tab closed mid-load" without saying what "safe" means or where the
danger is. Browser-process observers are not the danger: a per-tab observer is
torn down with the tab, so an update cannot arrive after teardown on that path.
The danger is entirely in **deferred delivery** — a posted task, and any Sunshine
WebUI surface that holds a list of rows.

1. No posted task, callback, or queued message carries a tab pointer, a
   contents pointer, an index, or a `SessionID`. It carries the durable UUID and
   re-resolves it against the live projection when it runs. A task that cannot
   resolve its UUID does nothing.
2. Existence is established only by insertion and removal. **An update never
   creates a row.** A title or favicon message for a UUID the surface does not
   already know is dropped, not used to add an entry.
3. Removal is terminal per UUID. A surface that has seen a tab removed drops
   every later message for that UUID, whatever its ordering or sequence number.
   Last-write-wins is specifically wrong here, because it lets a stale title
   resurrect a closed tab.
4. Updates and removals travel on different paths and their relative order is
   not guaranteed. Every surface must behave correctly when an update for a tab
   arrives after that tab's removal, and this must be tested by injecting that
   order rather than hoping it does not occur.
5. A tab in `Closing` produces no metadata write. A membership change requested
   for a tab in `Closing` is refused with the existing stale-tab error result
   rather than applied and then orphaned by the removal.
6. Sunshine never reacts to a title or favicon update by writing session
   extra-data, touching the workspace catalog, changing activation, or changing
   the split layout. These updates are display-only.
7. A navigation that commits while a close is pending may change the URL that
   the native recently-closed entry records. That entry belongs to
   `TabRestoreService`. Sunshine does not correct it, does not shadow it, and
   does not delay the close to make it tidier.
8. Nothing in this section requires Sunshine to cancel, delay, or retry a
   navigation because a close is pending. Interfering with an in-flight
   navigation to simplify bookkeeping would change page behaviour for the sake
   of internal convenience.

## 9. Interaction with split view

`docs/TAB_WORKSPACE_SPLIT_CONTRACT.md` invariants 5 and 6 hold unchanged: a tab
occupies zero or one pane and can never be live in both; closing one pane returns
the survivor to the normal active view. Chromium enforces both natively -- a split is
tab-strip state (`SplitTabCollection`), not Sunshine metadata. This contract
adds the lifecycle cases the split contract does not reach.

| Event | Effect on the split |
|---|---|
| A paned tab enters `Loading`, `Ready`, or `Ready` with `document_is_error` | None. The pane shows the document. |
| A paned tab crashes | None. The pane shows the native crashed-tab surface. The split is not dissolved and the other pane is untouched. |
| A paned tab is frozen or discarded | Must not happen while the split is open: both panes are visible (6.4). If it is observed, that is a visibility defect, not a case to be handled by dissolving the split. |
| One paned tab is in a closing set | The split is dissolved when the removal completes; the survivor returns to the normal active view with its state intact. |
| **Both** paned tabs are in one closing set | The layout record is dropped once, the window returns to the normal view, and successor selection then proceeds by section 7.1 exactly as if no split had existed. There is no intermediate one-pane state and no successor is chosen twice. |
| A close is refused for a paned tab | The split is unchanged. It must not be dissolved in anticipation. |
| A paned tab detaches to another window | The split is dissolved in the source window. A *whole* split moved between windows is a different operation and stays intact: `DetachSplitTabForInsertion` and `InsertDetachedSplitTabAt` carry it across. |
| A paned tab's workspace membership changes | The split is dissolved: a pane may only hold a tab of the active workspace, which the existing model already enforces on open and on restore. |

Reversing a split exchanges positions only and causes no lifecycle transition:
no navigation, no reload, no visibility change, no re-evaluation of freeze or
discard eligibility. Exiting a split dissolves it and closes no tab; `tab.close`
closes a tab and may dissolve a split. Conflating the two — a "close pane"
affordance that closes the tab — is the most likely user-visible data-loss bug
in this area.

## 10. Interaction with workspace membership

### 10.1 The active tab and the active workspace can never disagree

**Invariant 2.** The active tab of a window is always a member of that window's
active workspace. There are two ways to keep it true, and which one applies
depends on who is choosing:

- **Where Sunshine chooses, it constrains.** Successor selection after a close
  restricts the candidate set to the active workspace before Chromium picks
  (7.1).
- **Where Chromium chooses, Sunshine follows.** If Chromium activates a tab in a
  non-active workspace — a link opened from a background tab, a native
  restore-and-focus, a platform activation Sunshine does not intercept — the
  window's active workspace changes to that tab's workspace. Sunshine does not
  hide the active tab, and does not fight the activation.

Hiding an active tab is prohibited absolutely. It produces a window with no
visible page and no way to reason about what is focused.

### 10.2 Membership at creation

| How the tab was created | Workspace it joins |
|---|---|
| Restored by the session service or the restore service | The workspace UUID in its tab session extra-data; Default when missing or unknown, per the existing recovery policy |
| Opened from another tab (link, `window.open`, a native "open in new tab" action) | The **opener's** workspace, even when the opener is hidden — the tab belongs with the work it came from |
| Duplicated | The source tab's workspace, with a new UUID (section 3) |
| Created with no opener: new-tab affordance, omnibox in a new tab, the empty-workspace rule of 7.4 | The window's active workspace |

A tab created from a hidden opener does not steal activation. If Chromium
activates it anyway, invariant 2 applies and the window follows.

### 10.3 Membership changes are the only writes

`workspace.tab.move`, `workspace.close`, and `workspace.create` change Sunshine's
persisted state. Lifecycle transitions do not. Stated as a checkable rule:

**Invariant 3.** In a tab's whole life, Sunshine writes tab session extra-data
exactly at insertion (UUID and membership) and on membership change. Loading,
commit, error commit, title, favicon, freeze, discard, unfreeze, crash, reload,
activation, pin, group, move within a strip, split open, split swap, split
close, and close produce **zero** persistent writes.

An implementation that writes on activation or on commit will emit a session
command on every navigation of every tab, which is both a performance defect and
a durability risk in the one file Sunshine is least entitled to churn.

Off-the-record windows write nothing at all; workspace and split state are
memory-only there, which the existing models already encode.

## 11. Telemetry and privacy

- Lifecycle transitions are not commands and emit no command telemetry. A
  transition Sunshine causes indirectly — the New Tab of 7.4 — does not emit the
  telemetry of the command whose implementation it borrows (7.4).
- No lifecycle telemetry may contain a URL, an origin, a page title, a favicon
  URL, a form value, or a net error string. Counts, durations, and state
  identifiers only.
- Crash, discard, and freeze counts are legitimate reliability signals and are
  the ones handoff section 6.8 asks for. They are recorded per window session,
  not per site.

## 12. Corrections to handoff section 5.4

| Handoff text | Defect | This contract |
|---|---|---|
| `Created → Loading → Ready`, `↘ Failed` | `Failed` is not a sibling of `Ready`. A committed error page is a document like any other; a non-committed failure changes nothing at all. One arrow hides two opposite outcomes. | `Failed` deleted. `Ready` gains `document_is_error`; non-committed failures cause no transition (5.1, 5.2) |
| `Any non-closed state → Closing → Closed` | A close can be refused, so `Closing` is not one-way. A removal can also be a detach, not a close. `Closed` is not observable — there is no tab to be in it. | `Closing` may return to a live state; `Detaching` added; removal is a boundary, not a state (4.2, 7.5) |
| "Closing the active tab activates an adjacent non-closing tab" | "Adjacent" undefined; silent about multi-tab closes, about a closing adjacent tab, and about hidden tabs in other workspaces; invites a per-removal reselection loop | Close is a transaction over a set; candidate set restricted before Chromium chooses; exactly one activation change (7.1, 7.2) |
| "Closing the last normal tab opens a New Tab; it must not leave a dead browser surface" | Chromium closes the window instead. Implementing this needs a patch that breaks window closing and can block quitting. | Rejected for windows; retained only for an emptied active workspace in a window that still holds tabs (7.3, 7.4) |
| "A failed navigation retains the tab and shows an error state rather than deleting its history" | Right instinct, wrong scope: it does not say which history, and it would show an error state for a navigation that never committed | Navigation entries are `NavigationController`'s and are never edited; no error state for a non-committed navigation (5.1, 5.2) |
| "Favicon and title updates are asynchronous and must be safe for a tab closed mid-load" | "Safe" is not a specification. It also points at the wrong layer: browser-process observers are torn down with the tab; deferred delivery to surfaces is the hazard. | Eight explicit rules, including that an update never creates a row and that removal is terminal per UUID (section 8) |
| Five states, no mention of discard, freeze, or crash | An implementation following it treats a discard as close-plus-create and a crash as a failed navigation, losing membership and reloading unnecessarily | `Discarded`, `Frozen`, `Crashed` added with predicates and with the visibility rules that drive them (sections 4, 6) |
| §4.1 `BrowserTab` with `url`, `title`, `isLoading`, `canGoBack`, `canGoForward`, `isPinned`, `isMuted`, `webContentsId`, `createdAt`, `lastActivatedAt` | Reads as a stored entity duplicating Chromium tab state, contradicting §3.3, §4.3, and `docs/TAB_WORKSPACE_SPLIT_CONTRACT.md` §3. `webContentsId` is a forbidden durable key. `createdAt` and `lastActivatedAt` have no owner. | It is a **view model**, constructed on demand for one surface and discarded. Only the durable UUID and the workspace UUID are Sunshine-owned and persisted; every other field is read from Chromium at render time |
| §7.3: "Switch workspace … restore last active tab", with no field for it anywhere | The catalog stores only id, profile, name, colour, order; nothing stores a per-workspace last active tab. The behaviour is specified with no storage. | Store `last_active_tab_uuid` per workspace in **window** session extra-data beside the active workspace: window-local, references a durable UUID, shadows no Chromium state. Missing or unresolvable → Chromium's restored active tab. This must be added to the workspace model when it is next touched |

## 13. Acceptance criteria

Checkable once a native build exists. Criteria 1–4 are the ones that catch a
mirrored tab model; run them first.

**Derivation**

1. For a scripted sequence of at least 200 operations (navigate, reload,
   fragment navigate, background-load, discard, unfreeze, crash, reload, pin,
   group, move, split, close, restore), every tab's Sunshine-displayed state
   equals the state recomputed from native predicates after each operation.
2. No Sunshine-owned field, file, or session record contains a lifecycle state.
   A search of first-party sources finds no stored `Ready`, `Loading`, or
   equivalent per-tab flag.
3. Fragment navigation and History API navigation within a page cause no state
   change and no throbber in any Sunshine surface, matching the native strip.
4. A tab whose main document is interactive while a subframe still loads is
   shown as loading in both the native strip and every Sunshine surface.

**Identity**

5. Duplicating a tab and restarting cleanly leaves both tabs in their original
   workspace with distinct UUIDs; neither falls back to Default.
6. Discarding a tab under induced memory pressure leaves its UUID, workspace,
   group, pinned state, and position unchanged, and writes no session command.
7. A crashed and then reloaded tab keeps its UUID, membership, and pane.
8. Reopening a recently closed tab recovers its UUID and workspace, or — if
   extra-data is not carried by the restore path at the pinned tag — joins the
   active workspace with a fresh UUID, deterministically and without duplicating
   an existing UUID.

**Closing**

9. Closing other tabs in a window of 20 tabs produces exactly one activation
   change; a trace of visibility changes shows no tab other than the final
   successor ever becoming visible.
10. Closing a set containing the tab immediately after the active tab activates
    a tab outside the set; no tab in the set is ever activated.
11. Closing every tab of the active workspace in a window that also holds tabs
    of another workspace leaves the window open, in the same workspace, showing
    one new New Tab Page, with no hidden tab activated and no workspace change.
12. Closing every tab of a window closes the window. No New Tab Page appears, no
    new window appears, and quitting the browser from the last window exits the
    process.
13. Refusing a `beforeunload` prompt leaves the tab in the strip, in its
    workspace, at its index, in its pane, with the same UUID, and leaves the
    active tab unchanged.
14. Dragging a tab to a new window does not clear its workspace UUID; the value
    in tab session extra-data is byte-identical before and after.

**Asynchronous safety**

15. With favicon and title delivery artificially delayed past tab removal, no
    Sunshine surface shows a row for a removed tab, and none is re-created.
16. Injecting an update message for a UUID a surface has never seen adds no row.
17. Closing a tab during a slow load, with a navigation committing between the
    close request and the removal, produces no Sunshine metadata write and no
    crash.
18. A membership change requested for a tab whose close is already pending is
    refused with the stale-tab error result and leaves the projection unchanged.

**Split and visibility**

19. With a split open, exactly two tabs report visible; a long-running timer and
    an animation in the unfocused pane keep running at full rate.
20. Closing both paned tabs in one operation dissolves the layout once and
    performs one successor selection.
21. Crashing one paned tab leaves the split open, the other pane untouched, and
    the layout record unchanged.
22. Switching to another workspace and back does not reload a crashed tab and
    does not reload tabs that Chromium did not discard.

**Persistence**

23. Instrumenting session-command writes over a five-minute browsing session
    with 30 tabs shows writes only at tab insertion and at membership changes —
    none from navigation, activation, title, favicon, freeze, discard, or crash.
24. An off-the-record window performs zero persistent Sunshine writes across the
    whole of criteria 1–23.

**Roll gate**

25. At each upstream roll, the signals in section 4.2 still exist or their
    replacements are identified, and criteria 1–24 are re-run. A changed
    successor-selection rule upstream is adopted, not compensated for.

## 14. Open decisions

| Priority | Question | Why it blocks | Required by |
|---|---|---|---|
| P1 | Can a workspace span multiple windows? (already open as P1 in handoff §11) | Decides what a detached tab's workspace means in its new window, and whether a window's active workspace can be set by an arriving tab | Before tab drag-out is supported |
| P1 | When a workspace is returned to after its tabs were discarded, should Sunshine restore only the last active tab, or all previously loaded tabs? | Eager restoration undoes the memory benefit of hiding a workspace; lazy restoration means returning to a workspace shows blank tabs briefly | Stage 3 workspace release |
| P2 | Should the empty-workspace New Tab (7.4) use the workspace's optional home URL from handoff §4.1 rather than the New Tab Page? | The field exists in the domain model with no defined consumer | Stage 3 workspace release |
| P2 | Should closing the last tab of the last workspace in a window be treated differently from closing the last tab of a window with one workspace? | 7.3 currently makes them identical; a user with one workspace should see plain Chromium behaviour, which is what 7.3 gives | Stage 3 workspace release |

## 15. Not verified

- No Chromium checkout, configuration, compilation, or link of the pinned
  revision was performed. **NOT RUN.**
- No Sunshine or Chromium binary was launched on any platform. **NOT RUN.**
- No acceptance criterion in section 13 was executed. **NOT RUN.**
- No visual, accessibility, keyboard, or localisation check was performed.
  **NOT RUN.**
- The native signal names in section 4.2 are stated from the documented
  architecture of the pinned line. Their exact spelling at
  `refs/tags/152.0.7977.42` is **NOT VERIFIED**, and neither is the symbol that
  exposes frozen and discarded state; `docs/WORKSPACE_NATIVE_INTEGRATION_MAP.md`
  is the only place in this repository where pinned-tag symbols have actually
  been checked, and it does not cover them.
- Whether the restore path carries tab session extra-data at the pinned tag is
  **NOT VERIFIED**; criterion 8 exists to settle it, and section 12's storage
  decision for the per-workspace last active tab is **NOT IMPLEMENTED** in
  `scripts/workspace_model.py`.
- Chromium's exact successor-selection rule was not read at the pinned tag. This
  contract deliberately does not restate it (7.2), so the risk is limited to the
  restriction in 7.1 being applied at the wrong point — which criteria 9 and 10
  detect.
- No command was registered and none is proposed by name here.
  `first_party/commands.json` remains the only authoritative list.

## 16. Completion gate

This contract is complete when reviewed. Handoff section 5.4 is complete when a
native build exists, the projection derives every state from native predicates,
the close transaction and successor restriction are implemented, and criteria
1–25 have been run and recorded on the supported desktop platforms.
