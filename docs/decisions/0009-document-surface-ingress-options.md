# ADR 0009: Document surface ingress — two ways in, undecided

## Status

**Decided: Reading A, by the owner on 2026-08-27.** Content is authored or
pasted in the privileged shell. The P0 this document was written to inform is
settled and has moved to the *Settled* table in `docs/OPEN_DECISIONS.md`.

**Reading B is not closed by this.** §5 below establishes that A does not
foreclose it — import becomes an additional way in rather than a replacement,
because both readings converge on the same stored-document model. What B still
needs is the file-broker contract that does not exist, which is tracked
separately.

Everything below is as written when this was a proposal: it lays out the two
readings `docs/DOCUMENT_SURFACE_CONTRACT.md` §4 already named and records what
each costs, what security surface each opens, and what each does to the
reading-order invariant fixed in that contract's §3. **It is left in that form
on purpose.** The case for B is the part a later reader needs when B is
reconsidered, and rewriting it into a justification of the choice made would
destroy exactly that.

## Context

`docs/DOCUMENT_SURFACE_CONTRACT.md` fixes the structural decision that content
never renders in the privileged shell (§1, DOC-1, DOC-2) and fixes reading
order as the depth-first traversal of a project's node hierarchy (§3). What it
leaves open is how content arrives in the first place, and §4 states plainly
that this changes what has to be built first — not a detail to settle after
the surface exists, but the fork that decides the surface's first deliverable.

Two readings are on the table:

- **Reading A.** Content is authored or pasted directly in the shell.
- **Reading B.** Content is imported from files the user picks.

Both eventually land in the same store — §4 says so, and that is why this
memo can recommend a first step without foreclosing the second one. What
differs is what each needs before it can ship, and that is a security
question, not a UX one: `docs/SECURITY_ARCHITECTURE_CONTRACT.md` states

> SEC-8 | Module filesystem access is `none` unless a user selection grants a
> scoped, expiring permission. | O

and `scripts/validate_first_party_modules.py` enforces the `none` half today.
Its `filesystem.access` check accepts the value `user_selected` as an
expressible shape and then refuses it outright:

```text
f"{source}: scoped file access requires a future file-broker contract"
```

That refusal is not a bug to route around. It is the validator doing exactly
what SEC-8 asks: nothing reaches the disk until the scoped, expiring
permission SEC-8 describes has a broker to grant it. `SECA-3` states the
acceptance criterion this backs — *"A module requests a filesystem operation
its manifest does not declare. Assert refusal."* — and today every manifest's
only declarable filesystem statement is `none`.

## Option A — authored or pasted in the shell

**What it costs.** The shell already needs a way to create and edit the node
hierarchy — a title, an order among siblings, a document per leaf (§3) — for
either reading, because a project is Sunshine-owned data either way (DOC-3).
Reading A adds nothing beyond that: a text surface in the privileged shell
that accepts pasted or typed HTML and writes it to the profile-scoped store
alongside the node it belongs to. No file dialog, no read of anything outside
the profile directory, no new manifest shape.

**What it opens.** Nothing SEC-8 has not already settled. The manifest states
`filesystem.access: none`, which is the value the validator accepts today
without complaint. The only capability this reading exercises is one the
surface needs regardless of ingress: the untrusted-frame boundary in contract
§1 (DOC-1, DOC-2), which exists to keep whatever content lands in the store —
authored, pasted, or eventually imported — out of the privileged document.
Reading A does not touch SEC-8 at all, because nothing it does reads a path.

**First deliverable.** The surface itself, per the contract's own table in
§4. Nothing is blocked.

## Option B — imported from user-picked files

**What it costs.** A file (or directory) picker, a way to turn the bytes it
yields into the same stored hierarchy Option A writes to, and — before either
of those — a resolution of the SEC-8 question the contract's §4 states as
genuinely open both ways: *"There is a real argument that this is not what
SEC-8 forbids ... There is an equally real argument that it is exactly what
SEC-8 defers."* Building the picker is not the expensive part; the file-broker
contract SEC-8 anticipates and the validator currently refuses to accept
without is. That contract does not exist yet, and nothing in this repository
proposes its shape — SEC-9 through SEC-12's pattern of "deferred with its
subject" is the closest precedent, and it suggests the broker is its own
piece of design work, not a manifest field.

**What it opens.** However the "one-shot, no retained handle" argument is
resolved for a single file, it gets harder to sustain for the case Option B
actually needs: importing a *project* means reading more than one file — a
whole picked directory, or a multi-file selection — and mapping each into a
node. That is no longer a single bytes-in, nothing-retained operation; it is
a sequence of reads against one grant, which is closer to a session than to
the one-shot case the contract's optimistic reading rests on. This is exactly
the shape SEC-8's "scoped, expiring permission" describes, which is an
argument for building the broker properly rather than trying to characterize
directory import as outside SEC-8's scope to avoid building it.

Whichever way that argument resolves, the untrusted-frame boundary (DOC-1,
DOC-2) is unchanged and unavoidable: an imported HTML file is exactly the
untrusted content that boundary exists for, no more and no less trusted than
something pasted by hand. Option B does not add risk *there*. It adds risk at
the read, which Option A has none of.

**First deliverable.** Per the contract's own table: the file-broker contract,
or a recorded decision that directory/multi-file import is outside SEC-8's
scope. Either way, something other than the surface ships first.

## Effect on the reading-order invariant

Contract §3 fixes reading order as the depth-first traversal of the stored
hierarchy — a choice made so the hierarchy *is* the table of contents rather
than something maintained beside it. Both options are consistent with that
choice, but they arrive at a well-ordered hierarchy by different routes, and
only one of the routes is automatic.

**Option A orders for free.** Content enters one node at a time, through
shell actions that already place a node among its siblings as part of
creating it. There is no moment where an unordered batch has to be turned
into an order — the order is a side effect of how the content was authored.

**Option B has to manufacture an order.** A directory picker or a multi-file
selection yields a *set* of files, and neither the underlying filesystem API
nor the browser's picker guarantees the enumeration order is stable or
meaningful — it is not the reading order an author intended, it is whatever
order the OS happened to return. DOC-6 already forbids treating the hierarchy
as a live view of a filesystem — *"A node names a document Sunshine stores;
it never names a location on disk"* — and that rule is exactly what protects
this invariant from Option B's ingress path: import has to fix an explicit
order into the stored hierarchy at import time, once, from whatever signal is
available (file names, a manifest inside the picked set, or an explicit
post-import reorder step in the shell), and never re-derive it from the
filesystem on a later read. An importer that skipped this and re-enumerated
the source directory on every load would silently violate DOC-4 and DOC-6
alongside the reading-order choice in §3, all three at once — pagination is
presentation, the hierarchy is data, and reading order is depth-first over
data that no longer names where it came from.

This is not a reason to prefer one option over the other by itself — Option A
avoids the problem by never having it, Option B has a bounded, one-time fix
for it — but it is one more piece of work Option B carries that Option A does
not.

## Comparison

| | Option A — authored/pasted | Option B — imported |
| --- | --- | --- |
| Blocked on | nothing | a file-broker contract, or a recorded SEC-8 scope decision |
| New manifest shape | none — `filesystem.access: none` | `user_selected`, refused by the validator until the broker exists |
| Security surface opened | none beyond the untrusted frame every reading needs | the read itself: SEC-8, SECA-3, and the multi-file case's argument against "one-shot" |
| Reading-order (§3) work | none — order falls out of authoring | an explicit, one-time order fix at import; DOC-6 forbids re-deriving it from disk |
| First deliverable | the surface | the contract that unblocks the surface |

## Recommendation

Build Reading A first. It is buildable against the seam in
`docs/decisions/0007-module-contribution-seam.md` today, with no manifest
change and no open SEC-8 question — the fastest real test of whether that
seam is worth having, which is the question `docs/DOCUMENT_SURFACE_CONTRACT.md`
itself says the surface exists to answer. It does not foreclose Option B: the
contract's own §4 notes both readings write to the same store, so import
lands as an additive path onto a surface that already works, rather than a
rewrite of one built around a broker that does not exist yet.

This is a recommendation, not the decision the P0 in `docs/OPEN_DECISIONS.md`
is waiting on. The product owner may choose Option B first — for instance if
import is judged the only ingress worth shipping — and nothing here forces
otherwise.

## The egress decision narrowed Option B's question

Written after this ADR, and it changes what Option B still has to argue.

A download control was added to the reading pane, and it collided with DOC-3 as
that invariant was then worded — "no path outside the profile directory is read
or written". `docs/DOCUMENT_SURFACE_CONTRACT.md` resolved it by narrowing the
wording rather than granting a permission: handing content to a user-driven flow
Chromium owns is not a write by Sunshine, because Sunshine supplies bytes and
never learns, chooses, or retains a destination. DOC-8 was added to keep that a
handoff — no accepted path, none remembered, none reused, nothing written
without the user asking each time. The module manifest still declares
`filesystem: none`, because it holds no grant and receives no path.

**The argument is symmetric, and Option B is its inbound case.** This ADR's §71
frames Reading B as turning on whether importing from a user-picked file "is
outside what SEC-8 forbids" or "is exactly what SEC-8 defers". A picker the user
drives, read once, with no path retained, differs from the download in direction
and in nothing else that the reasoning above depends on. If the outbound handoff
is not filesystem access, the inbound one is not either — by the same argument,
not by a second concession.

What that leaves genuinely open is smaller than it was. It is no longer whether
a one-shot user-driven import is permissible in principle; it is whether the
import Sunshine actually wants stays one-shot. A picker that reads a file and
forgets it is the symmetric case. A directory import, a re-import that
remembers where it read from, or a watched folder are not — each retains
something, and DOC-8 names retention as the line. The file-broker contract SEC-8
anticipates is needed for those and not for the first.

This does not settle the P0. It narrows it to a question the owner can answer
without first deciding a security architecture: **is one-shot import enough?**

## NOT VERIFIED

- Whether the multi-file/directory read Option B needs is "exactly what SEC-8
  defers" or "outside what SEC-8 forbids" is argued both ways above and
  settled by neither argument; it is exactly the P0 question this memo exists
  to inform, not resolve.
- No file-broker contract has been drafted. Its shape, and therefore Option
  B's real cost, is estimated here from SEC-8's text and the validator's
  current refusal message, not from a design that exists.
- Nothing about either option has been built or run. The untrusted-frame
  boundary both options rely on is itself unverified per
  `docs/DOCUMENT_SURFACE_CONTRACT.md` §6.
