---
doc_id: adr-0013-module-data-portability
version: 1.0.0
canonical_path: docs/decisions/0013-module-data-portability.md
updated: 2026-08-18
---

# ADR 0013: A module's data must be able to leave the device it was written on

## Status

**Accepted** for the architectural rules in §2; the product questions in §4
remain open.

The split is deliberate and is the whole shape of this document. The rules in
§2 are architecture — they decide how a module is put together, they are
inside a Manager's authority, and they cost approximately nothing today
because no module has a data layer yet. The questions in §4 are product: they
decide behaviour the owner will see and they re-open decisions taken on
premises this ADR is not entitled to change. Nothing here marks any of them
answered, and nothing here authorises building sync, an iOS application, or
any second device.

## Context

The product owner uses an iPhone and an iPad, expects to **both read and write**
on the iPad, and asked for this to be prepared now although it will not be
built now. The instruction did not stop at the document surface: *the same
applies to every other module.* That is what makes this an architecture
question rather than a feature request. A rule that applies to one surface is
a design; a rule that applies to every module is a constraint on how modules
are written, and constraints on how things are written are cheapest before
anything is written.

Two decisions already fix most of the ground.

`docs/decisions/0006-module-execution-model.md` settled that a Sunshine module
is a compiled capability contributed through a WebUI, command, or
profile-service contribution point — Position A. Position B, the module
runtime with its bundle format and SDK, was **deferred, not rejected**, to be
judged when the Stage 1–3 gates close. Nothing below assumes B; nothing below
forecloses it either, because the rules here are about where data lives
relative to a surface, and both positions have surfaces.

`docs/decisions/0007-module-contribution-seam.md` built the seam and it is
real: its *What was actually built* section records that a second surface now
costs zero upstream-file edits, and that this was measured with a throwaway
probe patch rather than asserted. The seam solves **surface registration** —
a `WebUIConfigMap` entry, a host constant, a resource bundle. Read it for what
it says about *data* and it says nothing at all. That silence is the gap this
ADR fills. A seam that makes surfaces cheap, paired with modules that weld
their storage into those surfaces, produces a browser that is cheap to add
pages to and impossible to move anything out of.

The first candidate module makes the gap concrete.
`docs/DOCUMENT_SURFACE_CONTRACT.md` §6 states that nothing is built: "There is
no patch, no storage, no surface." The storage is precisely the part not yet
written, and it is the part an iPad would need. So the timing is not a
coincidence — this is the last moment at which these rules are free.

### Why "prepared now, built later" is the right posture and not a hedge

Retrofitting identity, or unpicking a data model out of a WebUI page, is the
expensive class of change: it rewrites stored data, and stored data belongs to
the owner. Writing the rules down before the code exists costs a document.
`docs/SECURITY_ARCHITECTURE_CONTRACT.md` §6 already makes the same argument
about the AI rules — "stated now because retrofitting them later is not
possible" — and ADR 0006 makes it about the module security rules, which are
"the part that is expensive to retrofit." This ADR is the third application of
one principle, not a new one.

## 1. What this ADR does not touch

It amends no invariant. DOC-1 through DOC-7 stand as written, SEC-1 through
SEC-14 stand as written, and no new invariant identifier is minted here — the
rules below are architecture that existing invariants already constrain, not
a new family of guarantees somebody would then have to check. Where a future
sync proposal collides with a DOC or SEC invariant, §3 says so and the
proposal must either satisfy the invariant or amend it in its owning contract,
in the open.

## 2. The rules — Accepted

### 2.1 A module's data layer is separate from its surface

**A module's data model may not live in the surface that displays it.**

Chromium already made this decision, for exactly this reason, and it is worth
stating in Chromium's own terms rather than as a general principle about
layering. `components/` exists so that non-UI logic can be shared across
platforms whose UI and web engine have nothing in common. That is not an
inference from the directory name. At the pinned revision `152.0.7977.42`, the
iOS port reuses the same classes the desktop browser uses:
[`ios/chrome/browser/bookmarks/model/bookmark_model_factory.h`](https://github.com/chromium/chromium/blob/152.0.7977.42/ios/chrome/browser/bookmarks/model/bookmark_model_factory.h)
returns a `bookmarks::BookmarkModel*` — the model declared in
[`components/bookmarks/browser/bookmark_model.h`](https://github.com/chromium/chromium/blob/152.0.7977.42/components/bookmarks/browser/bookmark_model.h),
which `docs/BOOKMARKS_HISTORY_CONTRACT.md` already cites as the owner of
bookmark CRUD — and
[`ios/chrome/browser/history/model/history_service_factory.h`](https://github.com/chromium/chromium/blob/152.0.7977.42/ios/chrome/browser/history/model/history_service_factory.h)
returns a `history::HistoryService*` from `components/history/`. Bookmarks,
history, sync and autofill are one implementation used by two products whose
user interfaces and web engines are entirely separate.

The corollary is the rule. **A Sunshine module built as WebUI-plus-storage
welded together is desktop-only by construction**, because the storage cannot
be reached without the page, and the page is a `chrome://` WebUI that does not
exist outside a Chromium browser. The same module with its data layer
separated is portable by construction — not portable *later, with work*, but
portable in the sense that the portable half already exists as its own thing.

**Where this sits in this repository's patch stack.** The seam's layout gives
a surface two Sunshine-owned directories:
`chrome/browser/ui/webui/sunshine/<name>/` for the browser-side C++ and
`chrome/browser/resources/sunshine/<name>/` for the TypeScript, HTML and CSS.
Neither is a place a data layer may live. A module's data layer belongs in a
third directory the stack creates, under `components/sunshine/<module>/`, as
its own GN target, and the dependency runs one way:

```text
components/sunshine/<module>/           model, storage, identity, ordering
        ▲                               no //chrome dependency, no UI
        │  depends on
chrome/browser/ui/webui/sunshine/<name>/   surface: WebUIConfig, message handler
        │  serves
chrome/browser/resources/sunshine/<name>/  the page
```

This costs no upstream-file edit, which is the same property ADR 0007 measured
for surfaces and it holds here for the same reason. The dependency is added in
the seam's own `BUILD.gn` under `chrome/browser/ui/webui/sunshine`, a file the
seam patch **created**, and `scripts/patch_manifest.py` exempts stack-created paths from exclusive
ownership precisely so later patches can extend them. Upstream's
`chrome/browser/ui/webui/BUILD.gn` already depends on the seam's source_set and
needs no further edit; `components/sunshine/` is a new directory upstream does
not have, so it can conflict with nothing.

What the rule forbids, concretely: storing project state in the WebUI
handler's own members as the authoritative copy; a schema whose only definition
is the shape of the messages the page and the handler exchange; persistence
written in TypeScript in the resources directory. Each of those is a data model
that cannot be compiled for a platform that has no `chrome://` host.

For the document surface specifically, the shell/frame split already pushes in
this direction. DOC-2 says the untrusted frame "receives content, never
capability," so the shell already has to hold documents as data it hands over
by message rather than as anything the renderer owns. The rule here says the
shell is not where that data is *defined* either.

### 2.2 Every unit of module data carries a stable identity that is not its position

**A project, a node, and a document each carry an identifier that survives
being moved in the hierarchy, renamed, or edited on another device.** The
identifier is not the title, not the index among siblings, not the path
through the tree, and not a row number.

Chromium makes the distinction explicitly on the object this repository's
document hierarchy most resembles. At the pinned revision,
[`components/bookmarks/browser/bookmark_node.h`](https://github.com/chromium/chromium/blob/152.0.7977.42/components/bookmarks/browser/bookmark_node.h)
carries two identifiers on one node, and the header says what separates them:

> ```cpp
> // The UUID for this node. A BookmarkNode UUID is generally immutable (barring
> // advanced scenarios) and differs from the `id_` in that it is consistent
> // across different clients.
> ```

The `int64_t id_` is persisted across sessions on this device. The UUID is what
is meaningful on another one. A model with only the first kind of identifier is
a model that cannot say "this is the same node you have," and it did not notice,
because on a single device the two are indistinguishable.

**Why the retrofit is the expensive case, stated as mechanism rather than as
warning.** Without stable identity there is nothing to merge *by*. A later sync
holds two trees and must decide which node on the left is which node on the
right, and the only evidence available is position and content — this is the
third child of the second chapter, and it is titled "Draft". So it compares
positionally, and every ordinary edit defeats it: a node inserted above shifts
every sibling, so unrelated nodes are matched to each other; a rename makes the
same node look like a different one, so it is copied rather than merged; a move
looks like a delete on one side and a create on the other, so the copy is kept
and the original is dropped. That is the duplicate-and-lose outcome, and it is
not a bug in the sync implementation — it is the data model failing to carry the
information the sync needed, discovered at the point where the data already
belongs to the owner and cannot be re-keyed without rewriting it.

Assigning identity later is not a schema migration that can be done well. There
is no correct answer to "which identifier should this node have had," so a
retrofit invents one, and each device invents a different one for the same node.

This does not disturb DOC-6, which says a node "names a document Sunshine
stores; it never names a location on disk" — an identifier is precisely such a
name and precisely not such a location. Nor does it disturb the reading order
fixed in `docs/DOCUMENT_SURFACE_CONTRACT.md` §3: the depth-first traversal of
the hierarchy stays the reading order. Order remains an attribute of a node;
identity stops being derived from it.

### 2.3 No module data model may assume a single writer

**Even while only one device exists.** The assumption is invisible while it is
true, which is why it has to be excluded by a rule rather than noticed in
review.

What it rules out, concretely:

- **An auto-increment counter used as identity.** A per-device sequence
  produces the same value on two devices for different objects. It is fine as a
  local storage detail — Chromium keeps its `int64_t id_` for exactly that —
  and it is not the identifier §2.2 requires.
- **Last-write-wins over a whole record where a field-level merge was
  possible.** A node has a title, an order among its siblings, and a document.
  If a title edit on one device and a reorder on the other collapse into "the
  later save wins", one of two independent changes is destroyed for no reason
  other than that the model stored them as one opaque blob. Storing them as
  separate fields with independent last-modified information does not decide
  the conflict policy — §4 leaves that open — it preserves the possibility of
  deciding it well.
- **Ordering that depends on insertion sequence alone.** "Position 0, 1, 2 …"
  requires renumbering siblings on every insert, which turns one user action
  into an edit of every neighbour, which turns a merge into a conflict on nodes
  nobody touched. An explicit order key that can be assigned *between* two
  existing neighbours without disturbing either is the alternative, and it is a
  choice about the field's type, made once.

**What it costs today: very little.** Each of these is a decision made at the
moment the model is first written, and the alternatives are the same amount of
code. None of them requires a sync engine, a version vector, or a merge
algorithm to exist — this rule is not "implement CRDTs", it is "do not write
down an assumption you will have to un-write."

**One honest limit.** DOC-4 fixes that "the stored document is never rewritten
to paginate, so what is read back is what was stored," and the document body is
therefore an opaque unit: byte-identical readback is a promise about the whole
stored thing. Field-level granularity stops at that boundary. Two devices
editing the *same document body* offline is a genuine whole-value conflict, and
no model choice available today dissolves it — which is exactly the question
§4 declines to answer, named there rather than papered over here.

### 2.4 The data layer never reaches the network by itself

**Whatever sync is later chosen, it is a separate component that reads the data
layer.** The data layer has no network code, no client, no endpoint, and no
knowledge that a second device could exist.

This ADR relaxes nothing. SEC-6's deny-by-default stands as written — "Module
network access is `deny` unless an allowlist of concrete hosts is granted.
Wildcards are not hosts" — and a module's manifest still declares
`network: deny`, `filesystem: none`, and `credentials.direct_access: false`,
which `scripts/validate_first_party_modules.py` enforces today. A data layer
built under these rules is not closer to the network than a module was before;
it is arranged so that a *future, separately reviewed* component could read it
without the data layer changing.

The separation is also what keeps a future sync reviewable. A component whose
whole job is egress is a component whose manifest states egress, whose hosts
are concrete, and whose logging obligations can be written against SEC-12 the
way `docs/decisions/0011-ai-credential-broker.md` §5 already wrote them for
another broker: metadata about what happened, never a second copy of the
content, and never a credential — including on the error path. A sync woven
through the data layer offers no such seam to review.

### 2.5 A module's surface talks to its host through one narrow interface

The four rules above are about data. They were written against an instruction
that stopped at data, and then the owner widened it: **eventually every app
developed here has to run on the iPad.** That sentence does not stay inside
this ADR's original subject, and the honest response is to say where it lands
rather than to design quietly around it.

It lands on ADR 0006. A module today is a compiled Chromium contribution point
— a `WebUIController` in C++, a `WebUIConfigMap` registration, a grd bundle, a
`chrome://` host. All four are desktop Chromium and none of them exists on
iOS. Ten modules built this way are ten rewrites, not ten ports. That is a
direct tension with Position A, and §4.4 records it as a question for the
owner rather than resolving it here.

What can be decided now is the part that costs nothing now and everything
later. A module's *surface* is already `app.html`, `app.css` and `app.ts` —
ordinary web assets, which a `WKWebView` can host as readily as a WebUI data
source can. What binds them to the desktop is not the markup; it is every
place the markup reaches for something only Chromium provides. So:

**A module's web assets communicate with whatever hosts them through a single,
named, explicitly-declared interface, and through nothing else.** No scattered
calls to Chromium-specific globals, no assumption about which object delivers
a message, no reaching past the interface because a browser API happens to be
in scope. The interface is the module's whole contract with its container.

The cost today is a naming discipline in code that has not been written. The
cost of skipping it is that every module's assets acquire an unbounded number
of small dependencies on Chromium, and "run this on the iPad" becomes a
rewrite whose size nobody can state in advance. This is the same argument as
§2.2's, applied one layer up: the expensive retrofit is not the feature, it is
the absence of a boundary to attach the feature to.

**What this does not achieve, stated plainly.** An iPad host application still
has to be written; portable assets do not host themselves. This rule makes the
assets host-agnostic and nothing more.

**What this paragraph first got wrong.** It said Sunshine the browser does not
go to the iPad under any reading, and that some of its modules might. The owner
answered that modules arriving without the browser is not the product — a
document module alone on an iPad is a notes app, not Sunshine, because the
integration *is* the thing — and that is correct, and it exposes an error in
the reasoning rather than a difference of preference.

The error was assessing portability by the engine instead of by where this
product's value sits. Sort what Sunshine has built or specified by layer and
almost none of it is engine-level: branding, the New Tab wordmark, the security
surface, the document surface, the command palette and workspaces are all above
the engine; gestures are an input-layer interpretation that a host reimplements;
only ADR 0004's codec selection and ADR 0005's Safe Browsing posture reach below
it. iOS forbids a third-party engine, so a Sunshine there would render with
WebKit — which is what Chrome, Edge, Brave and Firefox all already do on iOS,
and users call those browsers. What such a shell forfeits is engine-level
differentiation, and that is not where this product competes.

So an iOS Sunshine is a *smaller* loss than this paragraph claimed: the same
modules, palette, workspaces and documents, with a different renderer. What it
is not is cheap. It is a second product with a second UI codebase to maintain,
sharing only the `components/` data layer and these web assets, and the patch
stack that carries the desktop work is worth nothing there. Whether that is
built remains §4.2's question and this ADR still does not answer it.

What does change is the weight of the rules above. They stop being preparation
for moving a few modules and become the precondition for moving the product at
all: two hosts running the same modules is exactly what a host-agnostic asset
and a separated data layer are for. §4.4's suggestion that someone look again
at ADR 0006 gets heavier for the same reason — a defined module format is the
thing that lets one module run in a Chromium host and a WKWebView host without
being written twice.

## 3. Where these rules meet the document surface contract

The document surface contract was written for a single device, and three of its
invariants constrain any future sync rather than merely coexisting with it.
Recording the collisions is the point; a sync proposal that has not answered
them is not ready.

**DOC-3 — "A project is profile-scoped data Sunshine owns. No path outside the
profile directory is read or written."** This is the sharpest one, and it makes
the cheapest-sounding sync design the most expensive. "Export to a folder the
OS already syncs" reads like the option that needs no infrastructure; under
DOC-3 it is a write outside the profile directory, and under SEC-8 it is
filesystem access, which is `none` until a scoped, expiring permission and a
file broker exist. `scripts/validate_first_party_modules.py` refuses
`filesystem.access: user_selected` today for that reason. So the folder-based
design is not the free one: it is blocked on the same file-broker contract that
Reading B of the ingress question is blocked on, and it would additionally need
DOC-3 amended in its own contract, not worked around in a sync design.

**DOC-4 — the stored document is never rewritten to paginate.** This helps and
limits. It helps because it fixes what the unit of storage *is*: what was
stored is what is read back, so there is a well-defined thing to compare, and
no presentation-time rewriting to disentangle from a real edit. It limits
because that unit is whole, as §2.3 concedes.

**DOC-6 — the hierarchy is data, not a filesystem.** A sync design may not
reintroduce the filesystem as the model by making directories the hierarchy and
filenames the identity. Filenames are positions with better manners: they
change when a title changes, they collide, and they are a location on disk,
which is the thing DOC-6 says a node never names. A file-based *transport* is
compatible with DOC-6; a file-based *model* is not.

**DOC-7 — deleting a project deletes its documents.** On one device this is a
statement about storage. Across two it becomes a question with a visible
answer: a project deleted on the iPad while a document in it was edited on the
desktop is a delete-versus-edit conflict, and DOC-7 alone does not say whether
the edit resurrects the project or the deletion wins. That is conflict
semantics; §4 leaves it open. What §2.2 provides is the precondition for
answering it at all — a deletion can only be expressed as a fact about an
identified object, and a device that never had identifiers cannot say what was
deleted, only that something is now absent.

## 4. What this ADR deliberately does not decide

Three questions are named here and left open on purpose. Each is either the
owner's to answer or is downstream of a P0 that is already recorded in
`docs/OPEN_DECISIONS.md`. Deciding them inside an architecture ADR would be the
failure that index exists to end: a question recorded as open in one document
and quietly answered in another.

### 4.1 Whether sync exists at all, and of what kind

Not decided: whether Sunshine ever synchronises anything; and if it does,
whether by file export to a folder the operating system syncs, by a
self-hosted endpoint, or by an account.

The account-based option collides head-on with a P0 the index states as:

> Is a permanently account-free browser the product, or is local-only the
> Stage 1 state of a browser that later gains sign-in?

That is not a question about a sync backend. `docs/PROFILE_ONBOARDING_CONTRACT.md`
§3.2 states the current answer's cost plainly — "**No sync of anything.** No
cross-device tabs, bookmarks, history, passwords, addresses, settings, themes,
extensions, or saved tab groups" — and PO-6 forbids product surfaces
presenting that as a problem to be fixed by signing in. A module-level account
sync introduced beneath that would make the browser's account-free posture true
of the browser and false of the product, which is worse than either answer
taken deliberately.

The file-based option collides with DOC-3 and SEC-8 as §3 describes, and with
the ingress P0 the index states as:

> How does content reach the document surface — authored in the shell, or
> imported from files the user picks? The second is either outside SEC-8
> (one-shot, no path retained, no handle held) or exactly what SEC-8 defers;
> that reading decides whether a file-broker contract has to come first.

An export path is the same question pointing outward, and it does not get a
different answer by facing the other way.

`docs/PROFILE_ONBOARDING_CONTRACT.md` §12 already carries the adjacent P2 —
whether Sunshine ships a local-only encrypted export as the honest substitute
for the sync it does not have — and says it would need its own contract. This
ADR does not write that contract and does not pre-empt it.

Also unchanged: `docs/SUNSHINE_OS_STAGE_1_TO_3_IMPLEMENTATION_HANDOFF.md` line
697 forbids adding NAS sync or a Universal Object Store while the Stage 1–3
gates remain open, and its scope table places NAS sync and cloud storage
outside this project entirely. Nothing here reopens that gate. The rules in §2
are how a module is built; none of them is a synchronisation mechanism, and
none of them becomes buildable work by being written down.

### 4.2 Whether an iOS application is ever built, and how it would be distributed

Not decided, and not this ADR's to decide.

Two facts are worth recording so the question is argued from the real
constraints rather than from folklore. **App Store review is not the only
path**: a paid Apple Developer account permits installing a build directly on
devices the developer controls, and TestFlight internal testing distributes to
a small internal group without App Store review. So "the App Store would never
approve it" is not, on its own, a reason the owner's own iPad cannot run
something.

But the choice is downstream of a P0 the index states as:

> When, if ever, is Sunshine distributed? The answer gates code signing and
> auto-update, and re-opens ADR 0004 (codec licensing) and ADR 0005 (no Safe
> Browsing) together.

`docs/SECURITY_ARCHITECTURE_CONTRACT.md` §9 spells out why: ADR 0004 enables
H.264/AAC under a personal-use premise that "does not travel with the
artifact," and ADR 0005 leaves the build without Safe Browsing, which is a
materially different thing to hand to someone who did not choose it. A signed
iOS artifact, even one installed only on the owner's own iPad, is the first
build that exists outside the machine that made it, so it is the distribution
question arriving early rather than a way around it.

One further asymmetry belongs on the record because it changes what an iOS
build could even be. A Sunshine iOS application would not be a Chromium
downstream in the sense `docs/decisions/0002-native-chromium-downstream.md`
means: Chromium's own iOS port pairs the shared `components/` layer with a
platform-specific UI, and the browser engine is not the portable part. The
portable part is exactly the layer §2.1 requires a module to have. That makes
§2.1 the rule that survives every answer to this question — including "no iOS
application, ever" — because it is not an iOS rule, it is a rule about not
welding a model to one shell.

### 4.3 Conflict-resolution semantics

Not decided: **what happens when the same document is edited on two devices
while both are offline, and they then meet.**

Say plainly what kind of question this is. It is a product decision about
behaviour the owner will see, not an implementation detail to be settled by
whoever writes the merge code. The candidate answers are visibly different to
the person using the browser: the later save silently replaces the earlier one;
both versions are kept and the loser is preserved as a sibling or a revision;
the surface stops and asks. Each has a different failure — the first loses work
without saying so, the second grows duplicates the owner must tidy, the third
interrupts. The same question repeats for delete-versus-edit (§3, DOC-7) and
for move-versus-move.

§2.2 and §2.3 are what make any of those answers *implementable*, and they are
deliberately not an answer. A model with stable identities and independently
tracked fields can express "these are the same node, changed in two ways"; what
should then happen is the owner's call.

### 4.4 Whether ADR 0006's Position A survives "every app runs on the iPad"

Not decided, and it is the largest question this document raises.

`docs/decisions/0006-module-execution-model.md` chose Position A — a module is
a compiled capability — and deferred Position B, the module runtime with its
bundle format and SDK. Position B's entire subject is modules that are not
welded to one browser binary, which is exactly what "eventually every app
developed here has to run on the iPad" asks for. The requirement did not exist
when 0006 was decided; it does now.

The question is therefore not whether §2.5's discipline is enough. It is
whether Position A is still the right position, and that is the owner's, for
two reasons. It reverses a recorded decision, and 0006's own reasoning was not
mainly about portability: it declined Position B partly because a first-party
module is not trusted by default, and a runtime that loads bundles is a larger
trusted surface than a patch that is compiled in. That argument is untouched by
the iPad requirement and does not go away because a new requirement arrived.

What §2.5 buys in the meantime is time rather than an answer: modules written
under it keep their assets host-agnostic, so the eventual decision is a choice
about hosts rather than a rewrite of everything built until then. If the answer
is "stay with A and accept that only some modules reach the iPad", §2.5 costs
nothing and the assets are tidier. If the answer is B, §2.5 is the first
requirement B would have imposed anyway.

**Nothing here re-opens ADR 0006 by itself.** It records that a premise changed
and that someone should look again.

## 5. What this costs if there is never a second device

Close to nothing, and the reason is that none of the rules is about sync.

- **A separated data layer is what makes DOC-7 checkable.** "Deleting a project
  deletes its documents" is a claim about storage, and it is decidable by asking
  the data layer whether any document still names the deleted project. Welded
  into a WebUI handler, the same claim is a statement about a page — which is
  why `docs/DOCUMENT_SURFACE_CONTRACT.md` classes DOCA-6 as needing the browser
  and defers it with its subject.
- **It is what makes a module removable**, which is the property
  `docs/FIRST_PARTY_MODULE_ARCHITECTURE.md` already claims — features
  "independently owned, reviewable, switchable, and removable." A module whose
  data is a component target can be removed by removing a target and a
  dependency line. A module whose data lives inside a page cannot be removed
  without deciding what happens to the page's contents.
- **Stable identity is worth having on one device.** It survives a rename, so a
  bookmark, a command, a link, an undo record or a restored session can refer to
  a node without breaking when the owner retitles it. Chromium's bookmarks carry
  a stable id on a single device for the same reason, independent of sync.
- **A component target is testable without a browser**, which matters
  disproportionately in a project whose full build is measured at 6 h 31 min on
  its only build machine, which is also its only CI.
- **It is the precondition for the local-only export** already recorded as a
  P2 in `docs/PROFILE_ONBOARDING_CONTRACT.md` §12 — an export needs something to
  serialise that is not a page.

**The costs, named rather than waved off.** There are three, and they are
small but real:

1. **A boundary somebody has to hold.** The data layer must not acquire a
   `//chrome` dependency, and nothing enforces that today. It is a review
   obligation until some check claims it, and review obligations decay — this
   contract set has a documented history of settled decisions nothing enforced
   (SEC-13's own origin story). Naming a guard is out of scope here, but the
   gap is real and is not zero.
2. **Identifiers are not free.** A UUID costs more bytes than a row number and
   indexes less efficiently than an integer key. At the scale of one owner's
   projects this is irrelevant; it is not nothing, and claiming it were would
   be the overselling this section is supposed to avoid.
3. **An explicit order key is harder to reason about than an integer
   position.** Schemes that allow a value to be placed between two neighbours
   have their own failure mode — keys that grow without bound when items are
   repeatedly inserted in the same gap — and a rebalance path is work a plain
   integer index does not need.

And one cost that is not a design cost but should be stated: **this discipline
is only free while it is unwritten.** If the owner decides against a second
device *after* module storage exists, the three costs above have already been
paid and are not refundable. That is an argument for answering §4.1 early — not
an argument for this ADR answering it.

## 6. Out of scope, and not authorised by this document

- **Any implementation.** No patch, no GN target, no C++ class, no storage
  format, no schema. `components/sunshine/<module>/` in §2.1 is a placement
  argument, not a directory anyone is instructed to create.
- **A manifest schema change.** Schema 2 of `first_party/modules/*/module.json`
  is unchanged; nothing here adds a field, and the values the validator refuses
  today it still refuses.
- **Any amendment to DOC-3, DOC-4, DOC-6, DOC-7 or SEC-6 through SEC-8.** §3
  records collisions; it resolves none of them. Each is amended, if ever, in
  its owning contract.
- **Reopening the Stage 4 gate**, or the handoff's scope exclusion of NAS sync
  and cloud storage.
- **Which module goes first.** The document surface is the example throughout
  because it is the one with a contract, not because it is scheduled.

## 7. NOT VERIFIED

- **Nothing here is built or compiled.** ADR 0007 records that neither the seam
  nor its first surface has been through a build; a data-layer target sitting
  beside them is another unbuilt thing, and the placement argument in §2.1 is
  read from the patch stack's layout rather than observed in a build.
- **That a `components/sunshine/` target builds, and that GN and Chromium's
  dependency rules accept a `//chrome` target depending on it, is unobserved
  here.** The direction is the conventional one — `//chrome` depends on
  `//components`, not the reverse — and the seam's own `BUILD.gn` files are
  stack-created, so `scripts/patch_manifest.py` permits later patches to extend
  them; neither fact is a build.
- **The upstream claims in §2.1 and §2.2 were read at the pinned revision**
  `152.0.7977.42` and are cited by path. What was read is that the iOS factories
  return the `components/` types and that `BookmarkNode` carries a UUID
  documented as consistent across clients. No claim is made about how Chromium's
  sync engine uses either.
- **The statement in §4.2 that Chromium's iOS port does not carry the desktop
  browser engine is general knowledge about that port, not something read from
  the pinned tree for this document.** It is offered as context for a question
  this ADR leaves open, and nothing in §2 depends on it.
- **The Apple distribution facts in §4.2 are stated from general knowledge of
  the developer programme, not from a citation, and Apple's terms change.** They
  are recorded to keep the option honest, not to plan against.
- No claim is made about performance, storage size, or how a merge would
  behave. There is no merge.
