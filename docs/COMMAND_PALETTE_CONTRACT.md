# Command Palette — Dispatch, Availability, and Presentation Contract

## Status and scope

This contract applies to Sunshine OS on the pinned Chromium revision
`152.0.7977.42` recorded in `config/chromium.version`. It covers section 7.8 of
`docs/SUNSHINE_OS_STAGE_1_TO_3_IMPLEMENTATION_HANDOFF.md` and, unavoidably, the
part of section 3.2 that section 7.8 puts under load.

This wave is **documentation-only**. It adds no downstream patch, no first-party
module, no registry entry, and no localised string. Nothing here has been
compiled, launched, or observed. Every claim about the pinned revision's
behaviour is stated from its documented architecture and is marked `NOT RUN`
where it would otherwise read as verified.

Sunshine is a native downstream of open-source Chromium. The palette is browser
chrome invoking browser commands. It is not a scripting console, not a second
omnibox, and not a bridge between web content and privileged code.

## 1. Why this document is not just a UI spec

Section 3.2 states the command-first rule: *every user-visible action is a
command identifier; UI affordances resolve a command rather than calling browser
internals directly.* Four invocation sources have shipped contracts —
toolbar, keyboard, context menu, gesture — and each of them can hide a violation
of that rule behind a graphical affordance.

- A toolbar button can carry state in its glyph, so one control can mean two
  things without the user being confused.
- A context menu is built against a right-click target, so an action can take a
  target without anyone having to say where the target came from.
- A gesture binds a fixed identifier, so ambiguity in that identifier never has
  to be spelled out.

The palette has none of these. It presents commands as a flat, textual,
keyboard-driven list, with no target under the cursor, no glyph state, and no
context. **A command that cannot be rendered as one row of text with one
predictable outcome and one explainable enabled state is not a command.** That
makes the palette the executable test of section 3.2, and it is why this
document makes rulings that reach back into the registry rather than describing
a list widget.

Three such rulings follow. They are binding on `first_party/commands.json`, on
`scripts/validate_commands.py`, and on every future invocation source.

## 2. Ruling 1 — what a command may carry

### 2.1 The three kinds of input, distinguished

The registry has no argument schema, and the repository has been reading that
as "commands take no parameters". That reading is false today. Guards in `first_party/commands.json` were
functions requiring arguments the registry did not describe:
`scripts.workspace_model:move_tabs_atomic` takes a destination workspace
identifier and a set of runtime tab identifiers, and
`scripts.workspace_model:close_workspace_atomic` takes both a closed and a
destination workspace. The parameters exist; they are undeclared.

The useful distinction is not "parameters or none". It is **where the value comes
from**:

| Kind | Definition | Who resolves it | Example in the shipped registry |
|---|---|---|---|
| **Context** | Browser focus state at the moment of dispatch: focused window, focused pane, active tab, tab-strip selection, active workspace, profile | The command layer, from its own state. No invocation source supplies it | `browser.back`, `browser.print`, `tab.new`, `tab.group.create` |
| **Selection** | A handle to an object the browser process already owns, chosen by the user, which focus does not by itself determine | The invoking surface, by letting the user choose from an enumeration the owning module produces | `workspace.switch`, `workspace.tab.move`, `workspace.close` |
| **Payload** | A value that originates outside the browser process's own object graph: a renderer-supplied URL or node, a screen coordinate, or free text | Nobody, safely | Link and image context-menu actions |

### 2.2 The ruling

**A command may carry context and selection. A command may never carry a
payload.**

Context is free: it is what the command layer already knows. Selection is
permitted but must be *declared*, because an undeclared selection is what makes
`workspace.switch` unrenderable in a palette — the row cannot say which workspace
it will switch to, and the availability sentence "The selected workspace exists
in the window's profile" cannot be evaluated when nothing is selected.

Payload is prohibited, and the prohibition is a security boundary, not a
convention. Admitting a payload channel would mean either:

1. carrying a renderer-supplied value — a link URL, an image URL, a frame
   identifier — from untrusted content into a privileged dispatcher, which
   creates precisely the second trust bridge section 3.1 forbids; or
2. holding an ambient "most recently right-clicked target" in the browser
   process so that a parameterless command can read it, which is the duplicate
   state `docs/BROWSER_UTILITIES_CONTRACT.md` prohibits, and which would let a
   palette entry act on a target the user chose in a menu they have since
   dismissed.

### 2.3 What this costs, stated plainly

**Link and image context-menu actions are permanently unregistrable.** That is
not a gap to be closed later; it is the correct outcome. Their target is a
`ContextMenuParams` record produced by a renderer for one menu, valid only while
that menu is open, and meaningless the instant it closes. An action whose
identity includes such a target is a *context action*, not a command.

Section 3.2 as written — "every user-visible action is a command identifier" —
is therefore false as a universal. Its true form, and the form this contract
holds to:

> Every user-visible action **whose target is the browser's current focus, or a
> browser-owned object the user can choose by name** is a command identifier.
> An action whose target is a coordinate, a document node, or a renderer-supplied
> value is a context action, owned by Chromium's context menu, and is reached
> only there.

`docs/BROWSER_UTILITIES_CONTRACT.md` already assigns the link and image menus to
Chromium and forbids Sunshine from rebuilding them. This contract adds the
reason that assignment is permanent rather than provisional. **A wave report that
lists "register the context-menu actions" as deferred work is recording a task
that must never be done.**

Two further costs, accepted:

- These actions have no palette row and no gesture binding, ever. A user who
  wants to copy a link address right-clicks. That is one route, and one route is
  acceptable here because it is Chromium's own route, present in every locale
  and exposed to platform accessibility without Sunshine involvement.
- Later automation (section 3.2 lists it as a future invocation source) will
  want to say "open *this* URL in a new tab". Under this ruling that is not a
  command invocation. Section 2.6 states what would have to be true first.

### 2.4 Selection must be declared

For a selection-bearing command the registry must declare **what kind of object
is selected** and **which module enumerates the admissible candidates**. Without
that declaration the palette has three bad options: hide the command (a second
list that will drift from the registry — the exact failure section 3.2 records
against the old split-view "toggle" entry), show it and dispatch against an
undefined selection, or show it permanently disabled.

The concrete schema change is proposed in this wave's report rather than
asserted here, because `first_party/commands.json` is a validated shipped
interface and this wave changes no code. What the contract fixes is the
required semantics:

1. A command declares selection or declares none. The set of selectable kinds is
   closed and each kind is an object the **browser process** owns — a workspace,
   a tab, a pane. A kind whose values come from a renderer or from user-typed
   text is a payload and is rejected by section 2.2.
2. The enumeration of candidates is produced by the command's owning module —
   the same module that holds the `native_command` entrypoint. One owner
   enumerates and one owner executes, so the two cannot disagree about what
   exists.
3. Availability is evaluated **per candidate**, and separately for the command
   as a whole. The whole-command verdict is "at least one candidate is
   admissible"; a command with no admissible candidate is unavailable and says
   why (section 4).
4. A selection handle is never rendered to the user as an opaque identifier and
   never recorded anywhere the identifier alone would not already be recorded
   (section 8).

### 2.5 How the palette resolves a selection

A selection-bearing command is a **two-stage row**. Activating it does not
dispatch; it replaces the result list with the candidate enumeration for that
command, keeping the same input field, the same listbox, and the same
accessibility semantics. Choosing a candidate dispatches once.

This is not an argument channel. It is the palette doing what the tab strip and
the workspace switcher already do: making a selection, then invoking a command
against it. The rules that keep it honest:

- The second stage lists only candidates the owning module enumerated. The
  palette never constructs a candidate.
- The input field in the second stage filters that enumeration and nothing else.
  It never falls back to searching commands again, never accepts free text as a
  candidate, and never creates an object (a new workspace is created by
  `workspace.create`, which is its own row).
- `Escape` in the second stage returns to the first stage. `Escape` in the first
  stage closes the palette. This is the only place where `Escape` has two
  meanings, and it is permitted because the two states are visibly different.
- A two-stage command cannot be bound to a gesture or to a single accelerator.
  `docs/GESTURE_CONTRACT.md` section 6 already requires a binding to yield an
  identifier and nothing else; this contract confirms that a binding may only
  name a command whose selection is `none`.

### 2.6 If payloads are ever admitted

Not in Stage 3. Recorded here so that a future wave fills in a shape rather than
inventing one under deadline. All four would have to hold:

1. A typed argument schema in the registry, validated by
   `scripts/validate_commands.py` the way `errors` is validated today, with the
   type set closed.
2. Availability redefined as a function of the argument tuple, not of the
   command — so `available(command)` becomes meaningless and every caller,
   including this palette, must be rewritten to ask `available(command, args)`.
3. An origin label on every argument value, and a rule that a
   renderer-originated value can only reach a command whose declared handling of
   that argument was reviewed against site isolation.
4. An absolute exclusion of argument values from telemetry, from the recents
   store, and from crash reports — the same list `docs/SESSION_PROFILE_CONTRACT.md`
   applies to session data.

Anything less reintroduces the trust bridge section 3.1 exists to prevent.

## 3. Ruling 2 — one row, one outcome

`browser.reload` is registered as "Reload the active tab, or stop a load in
progress." with availability "A tab is active." and no error results.

For a toolbar control this is defensible: the control shows a reload glyph or a
stop glyph, the user reads the glyph, and the glyph is the promise. For a palette
row and a gesture binding it is a defect, and not merely a cosmetic one:

- The palette row is a static string. It cannot show which of two opposite
  outcomes it will produce.
- The outcome depends on a race the user cannot see. Between the moment the row
  is read and the moment `Enter` is pressed, a load can begin or finish. A user
  who typed the name intending to reload a stalled page can instead cancel the
  load that was about to complete, or the reverse.
- The two outcomes are not near-neighbours. One re-fetches, discarding
  uncommitted state; the other preserves what has arrived. There is no reading
  under which picking the wrong one is a small error.
- A gesture binding has the same problem with no text at all, and
  `docs/GESTURE_CONTRACT.md` invariant 9 guarantees exactly one command per
  press — it does not guarantee that the command means one thing.
- The registry declares no error results for it, so if the folded command is
  dispatched in a state where neither outcome applies, it has no way to say so.

**Ruling: `browser.reload` means reload, unconditionally, in every state,
including while a load is in progress (where it restarts the load). Stopping a
load is a separate command with its own identifier, its own availability
predicate, its own telemetry event, and its own error results.** The identifier
is proposed in this wave's report and must be registered by a separate reviewed
change; this document names none, for the reason
`docs/BROWSER_UTILITIES_CONTRACT.md` names none.

The general rule this instance is a case of:

> A **control** may choose between two commands when it displays, at the moment
> of invocation, which one it will run. A surface that cannot display that
> choice must name each outcome separately.

Consequences:

- The toolbar keeps one reload-or-stop control. Controls are allowed to be
  stateful; commands are not. The control resolves to one of two identifiers and
  dispatches it through the same service as everything else.
- The palette shows two rows. During a load, one is available and one is
  available; neither is hidden, because hiding a row on page state would make the
  list reorder under the user's fingers (section 6).
- The same rule retires any future proposal to fold a modifier into a command —
  a cache-bypassing reload is a third identifier, not `browser.reload` with a
  flag, because a flag is an argument and section 2.2 permits none.

A parallel case is already correct and should stay that way: `browser.find.next`
and `browser.find.previous` are separate identifiers rather than one
"find again" command with a direction. That is the pattern.

## 4. Ruling 3 — availability must return a verdict, not a boolean

### 4.1 What is shipped today

Section 7.8 requires "disabled-state explanation". When this contract was
written the registry offered two fields and neither could produce one. Schema
version 2 resolved it along the lines set out here; the diagnosis is kept
because it is the reason the schema has the shape it now has. What follows
describes schema version 1 unless it says otherwise.

| Field | What it is | Why it cannot explain a disabled row |
|---|---|---|
| `availability` | An English sentence, validated only for being a non-empty string ending in a period | Written for a reviewer, not a user. Not localised, not keyed, not a stable token. It states the condition under which the command *is* available, which is not the same as the reason this particular invocation *is not* |
| `guard` | A dotted reference to a Python callable, resolved and checked for callability by `scripts/validate_commands.py` | Not a predicate. Every shipped guard was the model function that performs the operation -- `scripts.workspace_model:move_tabs_atomic` returns a new projection, `scripts.workspace_model:close_workspace_atomic` returns a new catalog and projection -- signalling refusal by raising after being given full execution inputs |

The second row is the material finding. **Asking a shipped guard whether a
command is available requires calling the thing that performs it.** A palette
that rendered twenty-seven rows by consulting the guards would execute up to
twenty-seven operations to draw a list. And several availability sentences
correspond to no guard code at all: `close_pane` accepts a layout as given and
cannot answer "The active window has a split layout"; nothing anywhere evaluates
"A tab is active."

So the honest statement of the position is not "prose cannot be shown to a user".
It is: **Sunshine has no availability evaluation at all.** It has a prose
description of one and an implementation function that raises.

### 4.2 What availability must return

A **verdict**, produced by one evaluation, consumed by every surface:

- **Available** — nothing more.
- **Unavailable**, carrying a **reason token**: a `snake_case` identifier drawn
  from a closed set the command declares, exactly as `errors` is declared and
  validated today.

Requirements on the verdict:

1. **One evaluation, two consumers.** The verdict that greys the palette row is
   produced by the same evaluation the dispatcher consults before executing. A
   surface may cache a verdict for rendering; it may never dispatch on a cached
   one (section 4.4).
2. **Side-effect free and cheap.** Evaluating availability must not mutate state,
   must not touch the network, and must not require a round trip to a renderer.
   A predicate whose answer is not obtainable from browser-process state is
   redefined until it is, or reports unavailable with a reason. A hung renderer
   must not be able to hang the palette; this requirement is what makes that
   true.
3. **Reason tokens are the presentation contract.** The surface maps a token to
   localised copy. The token itself is never shown, never logged with user data,
   and never constructed at runtime by string formatting.
4. **Reasons carry no user data.** A reason token is a constant. It never
   embeds, and its rendered copy never includes, a URL, origin, hostname, page
   title, filename, workspace name, profile name, or tab title. This is the
   prohibition list `docs/GESTURE_CONTRACT.md` section 7 applies to telemetry,
   applied here because a palette is screen-visible and screenshot-visible.
5. **Reasons and errors stay distinct.** A reason explains why an invocation
   cannot start. An error explains why one that started did not complete. They
   may share spelling — a find command is plausibly unavailable and plausibly
   fails for the same stated condition — but they are separate declared lists,
   because merging them would let a command be marked available on the strength
   of a failure it has not yet had.
6. **Every unavailable state is reachable to a reason.** A command may not have
   an unavailable state with no token. "Disabled for a reason we did not
   enumerate" is a build failure, not a runtime string.

For Chromium-owned commands the evaluation lives on the Chromium side of the
command layer and its verdicts must still be drawn from the declared token set.
The registry check that a token is *declared* is executable without a build; the
check that the runtime *uses only* declared tokens requires a native build and is
listed in section 12.

### 4.3 This is a change to a shipped interface, and it is not small

`first_party/commands.json` is validated by `scripts/validate_commands.py`, and
`validate_command` compares each entry's keys against `REQUIRED_KEYS` in both
directions — missing keys and unknown keys both raise. **Adding any key to any
command is a hard build failure until the validator is changed in the same
change.** The migration is therefore atomic across the registry, the validator,
the tests in `tests/test_command_registry.py`, and every command entry at once;
there is no incremental path where some commands carry reasons and others do
not.

Three further honest consequences:

- The `guard` field was misnamed for what it held: the authoritative model
  function, not a predicate. **Settled in schema version 2.** `guard` became
  `implementation`, a side-effect-free `predicate` was added beside it, and
  `unavailable_reasons` declares the closed set of tokens that predicate may
  return. The validator requires the predicate and its reasons to be present or
  absent together, forbids a Chromium-owned command from carrying either, and
  rejects a token used as both an unavailable reason and an error -- the first
  says the command cannot start, the second says an offered command did not
  finish. `tests/test_command_registry.py` calls each predicate with inputs
  chosen to make it refuse and asserts the returned token was declared, which is
  the check the old field could not support.
- Twenty-seven commands currently declare no reason tokens. Every one needs its
  set enumerated by whoever owns it, and for the twenty-one Chromium-owned
  commands that enumeration is a claim about the pinned revision that this wave
  has **not** checked against source.
- Until that change lands, the palette cannot satisfy section 7.8. A palette
  built on today's registry can grey a row but cannot say why. That is a blocking
  dependency, not a polish item.

### 4.4 Timing, staleness, and the dispatch check

- The palette evaluates availability when it builds or rebuilds the list, and
  re-evaluates on browser state changes it observes. Those verdicts are
  **advisory**: they decide rendering only.
- The dispatcher re-evaluates immediately before executing. A command that was
  rendered available and has since become unavailable performs no action,
  produces no dialog, and is reported exactly as `docs/GESTURE_CONTRACT.md`
  section 6 requires for the gesture case: nothing happens, and the attempt is
  recorded.
- The palette must not re-open, re-render, or announce anything on that path.
  A surface that had already closed does not come back to editorialise.
- Availability is never re-evaluated by the surface *after* dispatch to decide
  whether the command "worked". Whether it worked is the command's error result.

## 5. Which commands the palette shows

**All of them. There is no palette-hidden set.**

Every command in `first_party/commands.json` appears in the palette's corpus.
The reasons are structural rather than aesthetic:

- A hidden set is a second list of command identifiers maintained beside the
  registry. Section 3.2 records what happened the last time this repository kept
  two such lists, and `scripts/validate_commands.py` exists because of it.
- Palette-completeness is the test in section 1. If a command is too strange to
  appear as a row, the correct response is to fix the command, not to hide it.
- The cost is a handful of rows that are rarely the answer. Ranking (section 6)
  already puts them where they belong, and availability (section 4) already
  explains them when they are dead.

Two things follow that the registry does not currently provide:

1. **Every command needs a localised user-facing title.** `summary` is a
   developer-facing sentence ending in a period; a palette row is a short
   imperative label. Titles belong in Chromium's localisation system keyed by
   command identifier — the registry stays language-free, consistent with
   handoff section 8.2 ("Korean-first product copy is acceptable; implementation
   identifiers remain English"). A build check must fail when a registered
   command has no title string, so the string table cannot drift from the
   registry the way a hidden set would.
2. **Opening the palette is itself a command.** It is a user-visible action, so
   section 3.2 applies to it with no exception. It therefore appears in the
   palette's own corpus and is reported unavailable there, with a reason, for the
   obvious cause. The self-reference is harmless and is cheaper than a special
   case; a corpus with one exception acquires more. The identifier and its owning
   module are proposed in the report.

## 6. Matching and ranking

### 6.1 What is matched

Matching runs over the **localised title** and the command's **localised
keywords**, after Unicode NFKC normalisation and case folding, on grapheme
clusters.

Command identifiers are never matched and never displayed. They are English
implementation strings; matching them would make the palette behave differently
for a Korean-first user than for an English one in a way no copy could explain,
and would leak internal naming into a user-facing surface.

Match classes, best first:

| Class | Condition |
|---|---|
| 0 | Query equals the title |
| 1 | Query is a prefix of the title |
| 2 | Query is a subsequence whose every matched cluster begins a word |
| 3 | Query is a subsequence of the title |
| 4 | Query is a subsequence of a keyword only |

A candidate matching no class is excluded. There is no fuzzy tolerance for
transposition or substitution: a scoring function that accepts a near-miss also
accepts a near-miss the user did not intend, and cannot be explained to a user
who is trying to build muscle memory.

### 6.2 Ranking is a pure function of the query

**With a non-empty query, the order of results is a pure function of the query
and the registered command set. Nothing else is an input — not recency, not
frequency, not availability, not the time, not the current page.**

The order is the lexicographic order of the tuple:

`(match class, index of first matched cluster, span of the match, title length, command identifier)`

The final term is the command identifier, which is unique by construction, so
the order is **total**: there are no ties and no tie broken by hash order,
dictionary iteration order, or the order commands happen to appear in the JSON
file.

Why this is non-negotiable:

1. **Palette use is a motor skill.** Section 7.9 offers "command palette faster
   than menus" as evidence of a durable advantage. That speed comes from typing a
   remembered prefix and pressing `Enter` without reading the list. That
   behaviour is only safe if the same prefix always produces the same first row.
2. **Some first rows are destructive.** `tab.close` and `workspace.close`
   destroy or relocate user state. A ranking that shifts under a user who is not
   reading converts a habit into a hazard.
3. **A varying order cannot be tested.** An acceptance criterion has to assert an
   exact list. A criterion that asserts "roughly the right thing near the top" is
   not falsifiable and will be quietly weakened whenever it fails.

Two corollaries that are easy to get wrong:

- **Recency does not boost ranked results.** It is not an input above. Recents
  appear only in the zero-query state (section 7). The cost is real: a user who
  half-remembers a name gets no help from having run the command yesterday. The
  benefit is that the list a user learned this morning is the same list this
  afternoon. Revisit only with measured evidence that users are failing to find
  commands they have previously run — not because a comparison product does it.
- **Availability does not reorder.** An unavailable command sits exactly where
  its match score puts it. Sorting unavailable rows to the bottom would make the
  order depend on page and window state, which is the same determinism failure
  from the other direction: the same keystrokes would select different commands
  on different pages. Availability changes how a row is drawn and what `Enter`
  does (section 9), never where it is.

### 6.3 Query mechanics

- The visible list updates on every input event with no debounce. Only the
  accessibility announcement is coalesced (section 10).
- Whitespace is collapsed; a query of only whitespace is the empty query.
- A query matching nothing produces a deliberate empty state, announced, per
  handoff section 8.2. It never produces a web search, a suggestion to search,
  or a "did you mean".
- Query text is never persisted, never sent anywhere, and never recorded in
  telemetry (section 11).

### 6.4 Korean matching is unfinished

Matching over composed Hangul syllables works for a user typing a full syllable
and fails for a user typing initial consonants, which is how Korean users
habitually search. Choseong search is **out of scope for Stage 3** and must be
specified as a named matching rule with its own match class if it is added —
never introduced as a scoring heuristic, which would break section 6.2's
totality guarantee. For a Korean-first product this is a real defect in the
Stage 3 palette and is raised as an open question in the report.

## 7. Recently executed commands

### 7.1 Scope and storage

| Property | Ruling |
|---|---|
| Scope | **Per profile.** Not per window, not per workspace, not global |
| Contents | An ordered list of command identifiers, most recent first |
| Cap | Bounded and small; 10 entries |
| Timestamps | **None** |
| Counts | **None** |
| Selection handles | **Never** |
| Query text | **Never** |
| Sync | Never |
| Where | Sunshine-owned profile preferences, written through the profile's normal preference service |

Per-profile follows from the profile being the boundary that already governs
what commands exist and what they can reach: policy, workspaces, and installed
state are all profile-scoped, and `docs/SESSION_PROFILE_CONTRACT.md` treats
cross-profile visibility of browsing behaviour as a leak. A global recents list
would let one profile's palette describe another profile's use.

### 7.2 A command history is a behaviour log

This is the privacy-relevant part and it should not be softened. A list of
recently executed commands says what the user was doing: that they printed, that
they saved a page, that they opened developer tools, that they split the view,
that they moved tabs between workspaces. It contains no URLs and is still
sensitive, because behaviour is sensitive. It is visible on screen to anyone
looking at it, and it is in every screenshot of the palette's empty state.

Hence:

1. **Identifiers only.** Storing timestamps would turn the list into a timeline;
   storing counts would turn it into a frequency profile. Neither is needed to
   render "recently executed". Neither is stored.
2. **No off-the-record recording, and no off-the-record display.** In an
   incognito or Guest window the palette records nothing *and shows no recents at
   all* — not the regular profile's. Recording would write off-the-record
   behaviour into a persistent store; displaying would show regular-profile
   behaviour to someone the user opened an off-the-record window to be private
   from. The empty state is deliberate and states that recents are unavailable
   here, per handoff section 8.2.
3. **Clearing is all-or-nothing, and that is a consequence of ruling 1.** With no
   timestamps, no time-ranged deletion is expressible. Therefore the list is
   cleared **in full** whenever browsing history is cleared for any range, and is
   independently clearable. A design that honoured time ranges would require the
   timeline this contract refuses to keep.
4. **Selection is never recorded.** A recent entry for a selection-bearing
   command records the command, not the chosen workspace or tab. Activating it
   re-opens the second stage (section 2.5). The list can therefore never reveal a
   workspace name.
5. **Unknown identifiers are dropped silently on read.** After an upgrade that
   retires a command, its entry disappears. A stored identifier is never a route
   to a command the registry no longer declares — the same rule
   `docs/GESTURE_CONTRACT.md` invariant 6 applies to bindings.

### 7.3 Presentation

- Recents appear only when the query is empty, above the default list, visually
  and semantically separated.
- Recents are **not** filtered by availability. An unavailable recent is shown in
  place with its reason. Dropping it would make the empty-state list move for
  reasons the user cannot see, defeating the same muscle memory section 6.2
  protects.
- The default list below recents is a fixed order, not a popularity order.

## 8. What the palette must not become

Stage 3 is **Browser commands only**. The following are prohibited, and the
prohibition is architectural rather than a matter of taste.

| Prohibited | Why |
|---|---|
| URL entry | Handoff section 5.3 gives navigation classification to Chromium's `AutocompleteClassifier`, through the omnibox. A palette that accepted a URL would need to decide whether a string is a URL, a search, or an intranet host. Two classifiers give two answers to the same string, and the disagreement is security-relevant: it decides whether text is sent to a search provider or resolved as a host |
| Web search | Same reason, plus it would put user-typed text on the network from a surface this contract requires to have no network access |
| History, bookmark, or open-tab results | These are search surfaces over user data. Chromium already ships tab search, and handoff section 7.2 lists it beside the palette rather than inside it. Mixing them would put URLs and page titles into a list this contract keeps free of them |
| Arbitrary text execution, a query language, or a developer console | The corpus is the registry. A palette that runs anything not in the registry has left the command-first rule rather than testing it |
| Extension commands | Extension compatibility is gated by handoff section 2.3 and `docs/EXTENSION_COMPATIBILITY_GATE.md`. An extension-supplied row is a third-party string in privileged chrome |
| AI, suggestion, or completion of any kind | Handoff section 12 defers AI while Stage 1–3 gates are open. Section 6.2 independently forbids any non-deterministic ranking input |
| Remote content, network access, or any fetch | The palette is browser chrome. It has no network surface at all |
| Being the only route to a command | `docs/GESTURE_CONTRACT.md` section 8 requires accelerators never to be sole routes; the same applies here. A command reachable only by palette is unreachable when the palette fails to open |
| Settings editing | Settings are a settings surface. A row that flips a preference is a command only if it is registered as one and behaves identically from every source |

The single rule these all follow from: **the palette's corpus is exactly the
registered command set, and its input field is a filter over that corpus, never
an interpreter of user intent.**

## 9. Keyboard model and focus

### 9.1 Opening

- `Ctrl+K` opens the palette. It is registered as a browser accelerator handled
  in the browser process, so that a web page cannot consume it. Whether the
  pinned revision delivers this chord to the renderer first in any circumstance
  is `NOT VERIFIED` and is acceptance criterion 15.
- The palette is per-window. Opening it does not change which tab is active, does
  not change which pane of a split is focused, and does not navigate.
- Opening captures a **focus token** for the element that had focus.
- Opening the palette while it is open is a no-op, not a re-open: it does not
  clear the query and does not reset the active option.

### 9.2 Navigation

| Key | Behaviour |
|---|---|
| Printable input | Filters. Focus stays in the input field at all times |
| `ArrowDown` / `ArrowUp` | Move the active option by one. **They do not wrap** |
| `Home` / `End` | First / last option |
| `PageDown` / `PageUp` | Move by one visible page, clamped |
| `Enter` | Activate the active option (section 9.3) |
| `Escape` | Close, or return from a second stage to the first (section 2.5) |
| `Tab` | Does not move focus within the palette. The palette is modal |

Arrow keys do not wrap because the list re-ranks as the user types, which would
place the last row adjacent to the first, and the first row is the type-and-press
target that section 6.2 exists to protect. An overshoot should stop, not land on
a destructive row.

`Escape` always closes from the first stage even with a non-empty query. A
two-stage `Escape` in a single visual state is the same defect as ruling 2: one
key, two outcomes, no way to see which applies.

### 9.3 Activation

- Activating an **available** command closes the palette and dispatches once.
- Activating an **unavailable** command dispatches nothing, **does not close the
  palette**, does not move the active option, and surfaces the reason (section
  10). Closing on a no-op would leave the user with no feedback and no surface
  to read the reason on.
- Activating a **selection-bearing** command opens the second stage (section
  2.5).
- At most one dispatch per opening of the palette.

### 9.4 Focus return

Focus is never dropped. The sequence on activating an available command:

1. The palette closes.
2. The command dispatches.
3. If the command moved focus — `tab.new`, `tab.close`, `workspace.switch`,
   `browser.find.open`, `browser.devtools.open` all do — **the command's focus
   outcome wins**. The palette does not restore anything.
4. Otherwise the captured focus token is restored, if the element it names still
   exists.
5. If it does not exist, focus goes to the focused pane's web contents.

The palette never restores focus to the browser chrome root and never leaves
focus on a removed element or on the document body. A screen-reader user must
land somewhere with a name, on every path, including the path where the command
destroyed the thing that had focus.

Closing without activating restores the focus token unconditionally.

## 10. Accessibility contract for the listbox

The palette is a **combobox with a listbox popup**, in a modal dialog.

| Element | Requirement |
|---|---|
| Dialog | `aria-modal="true"`, an accessible name, focus contained, the rest of the chrome inert by Chromium's own modal semantics |
| Input | `role="combobox"`, `aria-expanded`, `aria-controls` naming the listbox, `aria-autocomplete="list"`, `aria-activedescendant` naming the active option. Focus stays here for the palette's whole lifetime |
| List | `role="listbox"` with an accessible name |
| Option | `role="option"`, `aria-selected` reflecting the active option, and **no `tabindex`**. Positive `tabindex` is prohibited by `docs/DESIGN_SYSTEM_CONTRACT.md` section 8.2; options are reached by `aria-activedescendant`, not by focus |
| Unavailable option | **`aria-disabled="true"`, never the `disabled` attribute and never removal from the tree** |
| Reason | Associated with its option by `aria-describedby`, so it is announced when the option becomes active |
| Result count | One `role="status"` live region, `aria-live="polite"` |

The `aria-disabled` row is the crux of section 7.8's "disabled-state
explanation". An option removed from the accessibility tree, or given the
`disabled` attribute, cannot be reached by the arrow keys, so a screen-reader
user can never hear why it is disabled. **Unavailable options remain fully
navigable.** Only activation is refused.

Further requirements:

- The reason is **visible on screen as well as exposed to assistive technology**.
  Hover-only or tooltip-only disclosure is prohibited: a keyboard user does not
  hover, and this is a keyboard surface by construction.
- Disabled state is never conveyed by colour or opacity alone. Under forced
  colours, author colours are replaced and opacity distinctions can collapse; the
  row needs a non-colour marker in addition to the reason text
  (`docs/DESIGN_SYSTEM_CONTRACT.md` section 5.1).
- The live region announces a **coalesced** result count after typing settles.
  Announcing on every keystroke floods the speech queue and makes the palette
  slower for the users it is meant to serve. The visual list is never delayed by
  this coalescing.
- The active-option indicator meets `docs/DESIGN_SYSTEM_CONTRACT.md` section 8.2:
  driven by state rather than `:focus`, at least 2 CSS px, at least 3:1 against
  every colour it abuts, and surviving forced colours. `forced-color-adjust: none`
  is prohibited here as everywhere.
- Under reduced motion the palette presents with no entrance animation and is
  interactive at first paint. It must never be the case that a keystroke sent
  during an animation is lost.
- At 200% page zoom and at the platform's largest text size, the list scrolls and
  no reason text is clipped or truncated. A truncated reason is not an
  explanation.
- Empty state, second-stage state, and the off-the-record no-recents state are
  each deliberate, named, announced UI, per handoff section 8.2.
- Colour is never the only carrier of any distinction in this surface — including
  the separation between recents and the default list.

## 11. Dispatch, telemetry, and errors

1. The palette resolves a command identifier and dispatches it through the same
   command service used by the toolbar, the keyboard, the context menu, and
   gestures. It never calls browser internals, never navigates a `WebContents`,
   and never consults navigation history directly.
2. A palette-dispatched command records **its registry telemetry event, once**,
   from the dispatcher, with a source label. The palette does not emit a second
   execution event, and palette-specific events must never be used to count
   command executions — the rule `docs/GESTURE_CONTRACT.md` section 7 states for
   gestures.
3. Palette-specific telemetry is limited to: opened, dismissed without
   activation, activated from a ranked result, activated from recents, activated
   an unavailable row, and a **bucketed** query length. Prohibited without
   exception: query text or any substring of it, result titles, reason text,
   selection handles, and every field in `docs/GESTURE_CONTRACT.md` section 7's
   prohibition list. Query text is arbitrary user keystrokes and may contain
   anything the user typed into the wrong surface.
4. A command that fails presents its error through the same presentation it would
   use when invoked from the toolbar. The palette is closed by then and does not
   reopen. The palette must not become a second error channel: an error must not
   look different because of where the command was invoked from.
5. The palette never retries, never queues, and never undoes a command.

## 12. Interaction with split view and workspaces

- The palette is per-window and targets the **focused pane**, consistent with
  `docs/BROWSER_UTILITIES_CONTRACT.md`. Opening it does not change pane focus,
  and closing it does not either.
- Commands scoped to a tab act on the focused pane's tab, not on the most
  recently clicked one.
- Splits are Chromium's (ADR 0002), so the palette registers no split command
  and offers none. Chromium's own split entry points remain reachable from the
  tab strip and its context menu.
- Workspace commands operate in the window's profile only. The second-stage
  enumeration for a workspace selection never lists a workspace from another
  profile.

## 13. Invariants

1. Every palette row resolves a command identifier registered in
   `first_party/commands.json`. A row for an unregistered identifier is a build
   failure, not a runtime fallback.
2. The palette's corpus is the whole registry. There is no hidden set and no
   second list of identifiers anywhere in the product.
3. A command carries context and declared selection only. No invocation source,
   including this one, may supply a payload.
4. Every command has exactly one implementation, one availability evaluation, one
   telemetry event, and one error-result set, shared by every invocation source.
5. Availability is evaluated by the command layer, is side-effect free, and
   returns a declared reason token when false.
6. The dispatcher re-evaluates availability immediately before executing. No
   dispatch ever proceeds on a cached verdict.
7. One row means one outcome. No registered command selects between two
   user-distinguishable behaviours based on state the invoking surface cannot
   display.
8. With a non-empty query, result order is a pure, total function of the query
   and the registered command set.
9. Availability and recency never affect result order.
10. At most one command is dispatched per opening of the palette.
11. The palette performs no network activity and hosts no remote content.
12. Query text is never persisted, transmitted, or recorded.
13. The recents store contains command identifiers and nothing else, is
    per-profile, and is neither written nor read off the record.
14. No reason token, reason string, row title, or telemetry field contains a URL,
    origin, hostname, page title, filename, workspace name, or profile name.
15. Unavailable rows remain present, navigable, and announced, with a visible
    reason.
16. Focus is never dropped, on any path, including paths where the executed
    command destroyed the element that had focus.
17. No command is reachable by palette alone.

## 14. Acceptance criteria

Runnable once a native build and a palette exist. All are `NOT RUN`.

**Dispatch and equivalence**

1. **CPA-1.** A command invoked from the palette and the same command invoked
   from the toolbar produce identical observable state and identical telemetry,
   differing only in the source label.
2. **CPA-2.** Exactly one registry telemetry event is recorded per palette
   activation.
3. **CPA-3.** Tracing a palette activation shows dispatch through the command
   service, with no direct call into browser internals from palette code.

**Ruling 2**

4. **CPA-4.** With a load in progress, the palette offers reload and stop as two
   rows; each produces its own outcome, and neither produces the other's, on 100
   consecutive activations timed to straddle load completion.
5. **CPA-5.** `browser.reload` during a load restarts the load and never cancels
   it.
6. **CPA-6.** The toolbar's reload-or-stop control dispatches whichever
   identifier its displayed glyph promises, on every transition.

**Availability and explanation**

7. **CPA-7.** Rendering a full palette list evaluates availability for every
   command with no state mutation observable in the tab strip, session store,
   workspace catalog, or split layout.
8. **CPA-8.** With a renderer deliberately hung, the palette opens, lists, and
   explains within the same frame budget as with a responsive renderer.
9. **CPA-9.** Every unavailable row shows a reason that is a member of that
   command's declared token set; no runtime reason token is undeclared.
10. **CPA-10.** A command rendered available that becomes unavailable before
    `Enter` performs no action, shows no dialog, and records one unavailable
    attempt.
11. **CPA-11.** No reason string rendered anywhere in the palette contains a
    URL, hostname, title, filename, workspace name, or profile name, across a
    fixture covering every declared token.

**Ranking**

12. **CPA-12.** The same query produces a byte-identical ordered result list
    across: a restart, a different page, a different workspace, a profile with
    different policy, and after executing an arbitrary sequence of commands.
13. **CPA-13.** No two candidates ever compare equal under the section 6.2
    tuple.
14. **CPA-14.** Typing a fixed prefix and pressing `Enter` selects the same
    command on 100 trials interleaved with unrelated browsing.

**Keyboard and focus**

15. **CPA-15.** `Ctrl+K` opens the palette on a page that installs a capturing
    key handler for that chord and calls `preventDefault`.
16. **CPA-16.** `ArrowDown` at the last row and `ArrowUp` at the first row do
    not move.
17. **CPA-17.** `Escape` from the first stage closes with a non-empty query;
    `Escape` from a second stage returns to the first with the query intact.
18. **CPA-18.** After `tab.close` from the palette, focus is on a named element
    and a screen reader announces it; the same holds after `workspace.switch`
    and after dismissing without activating.
19. **CPA-19.** Activating an unavailable row leaves the palette open with the
    same active option and announces the reason.

**Recents and privacy**

20. **CPA-20.** Executing commands writes only identifiers to the profile store;
    a byte inspection of the stored value finds no timestamp, count, selection
    handle, or query text.
21. **CPA-21.** An incognito window's palette records nothing and displays no
    recents from the regular profile.
22. **CPA-22.** Clearing browsing history for any range empties the recents list
    entirely.
23. **CPA-23.** A recents entry for a selection-bearing command re-opens the
    second stage and never re-uses a previous selection.
24. **CPA-24.** After a build that retires a command, a stored entry for it
    disappears without error and without offering a row.

**Scope**

25. **CPA-25.** Typing a URL, a search phrase, a file path, and a command
    identifier each produce either matching command rows or the empty state —
    never a navigation, a search, a history result, or an open-tab result.
26. **CPA-26.** Network tracing during a full palette session shows no request
    attributable to the palette.

**Accessibility**

27. **CPA-27.** With a screen reader, every row including every unavailable row
    is reachable by arrow keys, and each unavailable row's reason is announced
    when it becomes active.
28. **CPA-28.** Under forced colours, in both a light and a dark forced theme,
    every row's text meets 4.5:1, the active-option indicator remains visible,
    and available and unavailable rows remain distinguishable without colour.
29. **CPA-29.** At 200% zoom and the platform's largest text size, no reason
    text is clipped and the list scrolls.
30. **CPA-30.** Under reduced motion the palette is interactive at first paint
    and no keystroke issued during presentation is lost.
31. **CPA-31.** The result-count announcement is coalesced: rapid typing
    produces at most one announcement per settle, while the visual list updates
    on every keystroke.

**Split and workspaces**

32. **CPA-32.** Opening and closing the palette in a split changes neither pane
    focus nor the active tab; a tab-scoped command acts on the focused pane.
33. **CPA-33.** A workspace second-stage enumeration in a window of one profile
    lists no workspace of another profile.

## 15. Not verified

Nothing in this document has been executed. Specifically:

- No Chromium checkout, configuration, compilation, or link of the pinned
  revision. **NOT RUN.**
- No launch of any binary on any platform; no palette exists to launch. **NOT
  AVAILABLE.**
- None of the 33 acceptance criteria has been run. **NOT RUN.**
- No visual, contrast, forced-colours, zoom, localisation, screen-reader, or
  keyboard verification of any surface described here. **NOT RUN.**
- The claim that `Ctrl+K` cannot be consumed by web content on the pinned
  revision is stated from the documented accelerator model and has **not** been
  checked against source.
- The reason-token sets that section 4 requires now exist as a schema field
  (`unavailable_reasons`, schema version 2), populated for the four
  Sunshine-owned commands and empty for the Chromium-owned ones, whose
  enumeration is a claim about upstream behaviour this wave did not check.
  Counts here read 27 registered and 21 Chromium-owned when this contract was
  written; the registry holds **24 (20 Chromium-owned, 4 `sunshine.workspace`)**
  since the three `view.split.*` commands were retired to Chromium's native
  split tabs.
- `scripts/validate_commands.py` was read, not modified. The registry, the module
  registry, the patch stack, and the localisation resources are unchanged by this
  wave.

The findings in sections 2.1 and 4.1 about the shipped `guard` field were reached
by reading `scripts/workspace_model.py`. They
are source claims about this repository, not about Chromium, and they are
checkable by reading those files.

## 16. Completion gate

This contract is complete when reviewed.

Section 7.8 is complete when, in order:

1. The registry and `scripts/validate_commands.py` carry declared selection and
   declared unavailability reasons, changed atomically together with
   `tests/test_command_registry.py`;
2. reload and stop are separate registered commands;
3. every registered command has a localised title, enforced by a build check;
4. a first-party module owns the palette surface and its opening command;
5. the palette dispatches through the single command service; and
6. criteria 1–33 have passed on a native build of the pinned revision on the
   supported desktop platforms.

Items 1 and 2 are blocking dependencies on the command registry, not palette
work. A palette built before them can be demonstrated and cannot be shipped.
