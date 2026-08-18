# Document Surface — Contract

## Status and scope

Applies to Sunshine OS on the pinned Chromium revision `152.0.7977.42`. It
defines `chrome://sunshine-document`: a project of HTML documents, arranged in a
hierarchy the reader can move through a page at a time.

This is a generic document surface. It is **not** the Book OS product that
`docs/SUNSHINE_OS_STAGE_1_TO_3_IMPLEMENTATION_HANDOFF.md` §1.2 excludes — that
exclusion is about implementing an independent SaaS inside the browser, and the
owner confirmed the distinction before this document was written. Nothing here
assumes, imports, or reserves anything from that product.

It is the first surface intended to sit on the seam in
`docs/decisions/0007-module-contribution-seam.md`, so it is also the first test
of whether that seam is worth having.

## 1. The one structural decision

**Project content never renders in the privileged surface.**

Everything else in this contract follows from that sentence. A Sunshine WebUI
page runs at a privilege no website has; project HTML is authored by a person
and is exactly the kind of content the trust model calls untrusted. Rendering it
in `chrome://sunshine-document` would run user-authored markup at browser
privilege, which is the failure `docs/SECURITY_ARCHITECTURE_CONTRACT.md` exists
to prevent.

Chromium already owns the mechanism, so Sunshine builds none of it:

```text
chrome://sunshine-document                    privileged shell
    project list, hierarchy, pagination, controls
        │
        │  postMessage, one direction, content only
        ▼
chrome-untrusted://sunshine-document-content  unprivileged frame
    renders the project HTML, can reach nothing
```

`chrome-untrusted://` is **Chromium's** scheme, not one Sunshine registers, so
SEC-13 and `docs/decisions/0003-internal-scheme.md` are untouched. The
`WebUIConfigMap` header read at the pinned revision distinguishes the two
explicitly, which is what makes this a supported arrangement rather than a
workaround.

## 2. Invariants

Class **O** is decidable offline. **B** needs the built browser. **D** is
deferred with its subject.

| ID | Invariant | Class |
| --- | --- | --- |
| DOC-1 | Project content renders only in the untrusted frame. No Sunshine-authored code inserts project markup into the privileged document. | O |
| DOC-2 | The frame receives content, never capability. The shell sends documents; the frame sends back nothing that can name a resource, a path, or an operation. | B |
| DOC-3 | A project is profile-scoped data Sunshine owns. No path outside the profile directory is read or written. | O |
| DOC-4 | Pagination is presentation. The stored document is never rewritten to paginate, so what is read back is what was stored. | B |
| DOC-5 | The frame reaches no network. A project referencing a remote resource shows it as absent rather than fetching it. | B |
| DOC-6 | The hierarchy is data, not a filesystem. A node names a document Sunshine stores; it never names a location on disk. | O |
| DOC-7 | Deleting a project deletes its documents. No content outlives the project that owned it. | D |

DOC-1 and DOC-6 are the two that a check can decide from source today. DOC-3 is
decidable once the storage code exists. The rest need the browser.

SEC-14 already forbids `eval`, dynamic code, and remote resources in any
Sunshine-authored web asset, and it applies to both halves of this surface. It
is not restated here; a second copy of a rule is a rule that can disagree with
itself.

## 3. What a project is

A project is a named hierarchy of documents. A node has a title, an order among
its siblings, and either children or a document — a hierarchy in the ordinary
sense, not a graph, because a reader moving "next" through a book needs a total
order and a graph does not have one.

The reading order is the depth-first traversal of that hierarchy. That is a
choice, not a fact: it makes the structure the table of contents rather than
something separate to maintain, and it means a node moved in the tree moves in
the reading order too.

## 4. Where content comes from — **undecided, and it decides the shape**

The request that prompted this contract says the surface *loads* HTML. How
content gets in is the one question that changes what has to be built first,
and it is not settled.

**Reading A — content is authored or pasted in the shell.** Nothing touches the
filesystem, `security.filesystem.access` stays `none`, and the surface can be
built now on the seam with no deferred subsystem.

**Reading B — content is imported from files the user picks.** A file picker or
a drop is user-initiated, one-shot, and yields bytes rather than a path. There
is a real argument that this is not what SEC-8 forbids: the module never holds a
handle, never retains a location, and cannot read anything the user did not
choose. There is an equally real argument that it is exactly what SEC-8 defers,
since `filesystem.access: user_selected` is the value
`scripts/validate_first_party_modules.py` refuses today pending a file-broker
contract.

**The two readings need different work in different orders**, which is why this
is recorded rather than assumed:

| | Reading A | Reading B |
| --- | --- | --- |
| Blocked on | nothing | a file-broker contract, or a decision that this case is outside SEC-8 |
| First deliverable | the surface | the contract that unblocks it |
| Manifest | `filesystem.access: none` | `user_selected`, once the validator accepts it |

Recorded as a P0 in `docs/OPEN_DECISIONS.md`. Reading A is the smaller first
step and does not foreclose B: content arriving by import lands in the same
store, so the import path is additive rather than a rewrite.

## 5. Acceptance criteria

1. **DOCA-1.** No Sunshine-authored file inserts project content into the
   privileged document — no assignment of project data to a node's markup, no
   template rendered with project strings in the shell. (DOC-1) — O
2. **DOCA-2.** The hierarchy stored for a project names no filesystem path.
   (DOC-6, DOC-3) — O
3. **DOCA-3.** A project whose document contains a script tag renders in the
   frame with the script inert, and the shell is unaffected. (DOC-1, DOC-2) — B
4. **DOCA-4.** A document referencing a remote image shows it absent; no request
   leaves the browser. (DOC-5) — B
5. **DOCA-5.** A document read back after storing is byte-identical to what was
   stored, whatever pagination was displayed. (DOC-4) — B
6. **DOCA-6.** Deleting a project leaves no document of it in the profile.
   (DOC-7) — D

DOCA-1 and DOCA-2 are the two a guard can enforce as soon as the surface exists.

## 6. NOT VERIFIED

- **Nothing here is built.** There is no patch, no storage, no surface.
- The `chrome-untrusted://` arrangement is read from the pinned sources and from
  how Chromium uses it for its own untrusted surfaces. It has not been compiled
  or run here, and the seam it would sit on is itself unbuilt and uncompiled.
- Whether one grd can serve both a `chrome://` and a `chrome-untrusted://`
  surface is unknown, and it bears directly on ADR 0007's resource half.
- No claim is made about performance, about how large a project can be, or about
  what happens to a document larger than memory.
