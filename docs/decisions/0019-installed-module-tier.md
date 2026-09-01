---
doc_id: adr-0019-installed-module-tier
version: 1.0.0
canonical_path: docs/decisions/0019-installed-module-tier.md
updated: 2026-08-27
---

# ADR 0019: A second module tier, installed from a signed bundle

## Status

**Accepted by the owner.** Sunshine gains a second kind of module: a web module
delivered as a **signed web bundle**, installed from a file, served at
`chrome-untrusted://<bundle-id>/`, mounted by the shell through the port that
already exists.

**Nothing is built.** This records a decision and the reading it rests on. The
work it authorises is scoped in *Decision*; everything else stays where it is.

`docs/decisions/0006-module-execution-model.md` is amended rather than
reversed — see *What this does to ADR 0006*.

## Context

ADR 0006 accepted Position A: a Sunshine module is a compiled capability. It
deferred Position B — a module the browser loads and executes — and it named one
investigation that would decide how expensive B really was:

> can a WebUI host serve bundled resources without a registered scheme?

The owner separately proposed an install flow — a Register button, a file
dialog, a module installed from the file it names.
`docs/MODULE_INSTALL_REVIEW.md` reviewed that against the pinned tree, and §6
recommended building it. **That recommendation stood against an accepted ADR
with nothing connecting them**, which is why it became a P0 before it became
this.

The investigation is done. §3b and §3c of that review are the reading; this is
the decision.

## What the reading established

| Question | Answer, read at `152.0.7977.42` |
| --- | --- |
| Does serving bundled resources need a registered scheme? | **No.** `chrome-untrusted://` is Chromium's and already in use by this repository. ADR 0003 is untouched. |
| Can a host be chosen at runtime? | **Yes.** `WebUIConfig(scheme, host)` takes the host as a constructor argument. |
| Can bytes be decided at request time? | **Yes.** `URLDataSource::StartDataRequest` answers with `base::RefCountedMemory`; patch `0021` already does it for a file on disk. |
| Can a config be registered after startup? | **Yes.** `AddWebUIConfigImpl` has no timing check, and `GetConfig` is a per-navigation map lookup. |
| Can the shell frame it? | **Yes.** Patch `0006` already makes a `chrome-untrusted://` surface frameable by the shell alone via `AddFrameAncestor`. |
| Is cryptography Sunshine's to write? | **No.** `//components/web_package` parses the bundle and verifies the signature. |

**Every mechanism this needs is one Sunshine already uses.** That is the fact
that changed the decision, and it is why this is an amendment rather than the
Position B the ADR 0006 brief described — no module runtime, no SDK, no
lifecycle manager, no capability broker.

## Decision

**1. Two tiers, and the boundary is native code.**

| | Compiled tier | Installed tier |
| --- | --- | --- |
| What it is | C++ in the browser, declared in `first_party/` | HTML, CSS, JS and assets in a signed bundle |
| Who may have it | Anything needing Mojo, a C++ model, or a browser capability | Anything that does not |
| How it arrives | The patch stack and a build | A file the user picks |
| Examples named today | Marketpick, Dev OS | an HTML collection, and most of what follows it |

**An installed module may not carry native code.** Loading C++ at run time is
loading a DLL, which ends the sandbox and the code-signing story in one step.
This is the line, and it is not negotiable by a later convenience.

**2. The format is a signed web bundle, not a zip.**

A zip has no identity. A signed web bundle's id is derived from its signing
key, so the origin is a name the key chose rather than a name the module chose.
Sunshine derives it in one place a guard can read, and verifies it with
`//components/web_package`.

**3. The host is the bundle id.** `MM-1` allows 63 characters and a signed
bundle id is 56, so the host is the id itself rather than a readable name with
the id appended.

**4. Three rules from §3c are part of the design, not discoveries for later.**

- **Remove before add.** `AddWebUIConfigImpl` CHECKs on a duplicate origin, and
  a re-install has the same id by construction. Install is
  `RemoveConfig` then `Add`, unconditionally.
- **Register on the UI thread.** The map has no lock and no sequence checker.
  Verification runs off-thread and hops back.
- **Scope by profile in `IsWebUIEnabled`.** The map is process-wide. Getting
  this wrong serves one profile's module to another, silently.

**5. What is authorised now, and what is not.**

Authorised: the reading is settled and the shape is fixed, so design work and
contract work may proceed against it.

**Not authorised by this ADR:** writing the installer flow, the store format, or
the verification path. Each needs its own contract first, and
`docs/MODULE_INSTALL_REVIEW.md` §4 lists the risks in the order they should be
taken. This ADR removes the blocker; it does not schedule the work.

## What this does to ADR 0006

ADR 0006's decision — *a Sunshine module is a compiled capability* — **stands
for the compiled tier and is not reversed.** What changes is that it is no
longer the only tier.

Its enforcement mechanisms stay exactly as they are until a contract replaces
them, and that is deliberate:

- `validate_first_party_modules.py` still accepts four entrypoint types and no
  bundle type, so **an installed module still cannot be declared** in
  `first_party/`;
- `verify_architecture.py` still rejects `package.json`;
- SEC-13 still rejects the scheme the original brief proposed, and nothing here
  asks for a scheme.

**So the guards do not move on this ADR.** They move when the contract that
defines an installed module's manifest arrives, and not before — which keeps
the repository in a state where the decision is recorded and the tree still
enforces the old shape, rather than one where the tree enforces nothing.

## Consequences

- **A program built to dock as a Sunshine module now has two possible shapes**,
  and which one applies is decided by whether it needs native code. Anything
  written today against the compiled tier stays valid.
- The installed tier gives up an Isolated Web App's dedicated
  `StoragePartition`: installed modules share the profile's partition, each with
  its own origin and therefore its own storage. `docs/MODULE_INSTALL_REVIEW.md`
  §3a states this, and it is the same position the document surface is already
  in.
- **Sunshine takes on enforcing the origin-to-key binding** that the browser
  enforces for a real IWA. That is a transfer of responsibility and it is the
  one part of this worth arguing about again later.
- Build time stops being the price of every module. That was the strongest
  argument for B in ADR 0006 and it is now partly answered.

## Alternatives considered

**Install Isolated Web Apps rather than bundles.** Rejected in
`docs/MODULE_INSTALL_REVIEW.md` §3a: an IWA gets its own `StoragePartition`, a
plain iframe does not cross a partition boundary, and the embedding direction
the API offers is an IWA embedding others through a guest view. The shell could
not mount one without guest views in a `chrome://` page — more machinery, and a
second mounting mechanism beside the one that works.

**A plain zip.** Rejected: no identity, and the origin would have to be a name
the module chose.

**Keep Position A alone.** Rejected by the owner. It is coherent, and its cost
is that every module carries a full Chromium build — 6 h 31 min on the only
machine that can do it, which is also the only CI.

## NOT VERIFIED

- **Nothing here has been built, compiled or run.** Every Chromium fact is read
  from the pinned tree at `152.0.7977.42`.
- Whether a 56-character bundle id is acceptable to Chromium as a host was not
  read. `MM-1`'s 63-character limit is Sunshine's rule, not Chromium's.
- §3a's conclusion that a plain iframe cannot host a document in another
  `StoragePartition` rests on the API only offering the guest-view direction.
  The enforcing code was not read.
- Signature verification was located in `//components/web_package` and not
  exercised. No bundle has been built, signed, or parsed.
- The store format — where an installed module's own files live — is untouched
  by this ADR and remains open in `docs/MODULE_INSTALL_REVIEW.md` §4.
