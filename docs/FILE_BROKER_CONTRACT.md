# File Broker — Contract

## Status and scope

Applies to Sunshine OS on the pinned Chromium revision `152.0.7977.42`. It
defines what `filesystem.access: user_selected` means in a first-party module
manifest, and it exists because `scripts/validate_first_party_modules.py`
refused that value "pending a future file-broker contract".

`docs/decisions/0016-relaxations-for-porting.md` is why it was written now.

**Nothing here is implemented.** The validator accepts the declaration; no code
opens a file on a module's behalf. §5 says what that leaves open.

## 1. The one structural decision

**The user names the place. The module names nothing.**

`SEC-8` says module filesystem access is `none` unless a user selection grants a
scoped, expiring permission. This contract is what "scoped, expiring" means, and
the shape it takes is the one `docs/DOCUMENT_SURFACE_CONTRACT.md` already
argued for `DOC-3` and `DOC-8`: what those forbid is *ambient authority* — a
module reading where it likes, writing where it likes, remembering somewhere it
wrote. A grant a user made, to one place, that expires, is none of those.

```text
user picks ──▶ browser holds the grant ──▶ module holds a handle
                        │                          │
                        │   the path lives here    │  and never here
                        ▼                          ▼
              scoped · expiring · revocable   opaque · unforgeable
```

## 2. Invariants

Class **O** is decidable offline. **B** needs the built browser.

| ID | Invariant | Class |
| --- | --- | --- |
| FB-1 | A grant originates in a user selection through a Chromium picker. A module cannot request a specific location, and cannot obtain a grant it did not watch the user make. | O |
| FB-2 | The module never receives a path. It receives an opaque handle; the path is the browser's and is not derivable from what the module holds. | O |
| FB-3 | A grant is scoped to what was selected. A handle to a file reaches that file; a handle to a directory reaches what is inside it and nothing above it. | B |
| FB-4 | A grant expires. It does not outlive the session that created it, and nothing a module stores can revive one. | B |
| FB-5 | A grant states read or write when it is made, and a read grant never becomes a write grant. | O |
| FB-6 | A grant is revocable, and revocation takes effect on the next use rather than the next restart. | B |
| FB-7 | The module cannot widen a grant. There is no operation that turns one handle into a handle for anything else. | B |
| FB-8 | Grants are visible to the user, with what was granted, to which module, and when it expires. | B |
| FB-9 | A module that declares `user_selected` and never obtains a grant behaves as though it declared `none`. Declaring the capability is not holding it. | B |

FB-1, FB-2 and FB-5 are decidable from a module's source and manifest. The rest
are properties of a broker that does not exist.

### Why the handle, and not a path

`DOC-3` and `DOC-8` in `docs/DOCUMENT_SURFACE_CONTRACT.md` work through the
distinction at length for one surface: a module that never learns a location
cannot remember one, cannot reuse one, and cannot be talked into writing
somewhere else. FB-2 is that argument made general and made structural — if the
module has no path, the failure mode is unavailable rather than guarded
against.

It also settles what happens when a module is compromised. A path is authority
that survives the compromise; a handle the browser can revoke is not.

### Why expiry is not negotiable

A grant that persists is a grant nobody re-consented to. Dev OS's session
directory is the motivating case and it is a good illustration: a user who once
allowed a read of that directory has not thereby allowed every future version of
the module to read it forever. FB-4 makes the grant a fact about a session
rather than a fact about the installation.

**This is the term most likely to be argued with**, because it is the one that
makes a ported application feel worse than it was: the app used to just read the
directory. It used to do so with the user's whole account authority, which is
what a browser is for refusing.

### What this contract does not do

It does not let a module reach a **well-known** location. `~/.claude/projects/`
is not a path a user would think to pick, but the answer is still that they pick
it — once, deliberately, seeing what they are granting. A module that reached it
without that would hold ambient authority under a different name, which is
exactly what SEC-8 forbids.

## 3. What a module declares

```json
"filesystem": { "access": "user_selected" }
```

The declaration says the module *may ask*. It says nothing about whether it
holds a grant, which is FB-9 and is why the module home shows grants separately
from declarations.

## 4. Acceptance criteria

1. **FBA-1.** No module's source contains a filesystem path literal, a path
   built from user data, or a stored location. (FB-2) — O
2. **FBA-2.** A module declaring `user_selected` declares a purpose in its own
   documentation. (FB-1) — O
3. **FBA-3.** A read grant cannot perform a write. (FB-5) — B
4. **FBA-4.** A grant is gone after the session that made it. (FB-4) — B
5. **FBA-5.** Revoking a grant stops the next operation, not the next launch.
   (FB-6) — B

None is enforced yet. FBA-1 is the one closest to a check —
`scripts/verify_no_interposition.py` already reads module sources for shapes
like this.

## 5. NOT VERIFIED

- **No broker exists.** This contract describes a subsystem the browser does
  not have. A module may now declare the capability; nothing grants it.
- The handle in FB-2 is undesigned. Chromium has machinery for user-selected
  files that would inform it, and none of it has been read at the pinned
  revision for this purpose.
- FB-3's directory scoping is the term most likely to be wrong in a first
  implementation — symlinks, junctions and paths that escape upward are exactly
  where scoping fails, and this contract asserts the property without saying how
  it is obtained.
- Nothing here has been built, compiled or run.
