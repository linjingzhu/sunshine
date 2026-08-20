# Document Store — Contract

## Status and scope

Applies to Sunshine OS on the pinned Chromium revision `152.0.7977.42`. It
defines where a module's documents live, what they look like on disk, and what
happens when two devices disagree about one.

**Three decisions the owner made, which everything below follows from:**

| | Decision |
| --- | --- |
| Where | A directory **the user picks**, in a folder something else already syncs — a cloud client's folder or a mounted NAS share. |
| Naming | The filename is the document's **title, readable**. Identity lives **inside the document**, and in a sidecar only where the format cannot carry it. |
| Conflicts | **Last save wins, and the loser is preserved and shown.** Nothing is deleted to resolve a conflict. |

**No implementation exists.** §8 says what that leaves open. This contract is
worth writing before the code because two of the three decisions cannot be
changed afterwards without migrating every document a user has.

## 1. The one structural decision

**The store is the user's folder, not Sunshine's database.**

Every rule below is a consequence of that sentence, and the consequence that
matters most is this: **something else is always also touching these files.** A
sync client is writing into the directory, a second Sunshine on another machine
is writing into it, and the user is opening it in a file manager. A design that
assumes exclusive access is wrong on all three counts.

It also fixes what the store is *for*. These are the user's documents, kept in
the user's own storage, in a form that outlives this browser. A person who
stops using Sunshine keeps their documents and can still open them.

## 2. Where it is

| Rule | |
| --- | --- |
| One directory, chosen once | Through the file dialog. `docs/FILE_BROKER_CONTRACT.md`'s `user_selected`, held as a persistent grant. |
| Sunshine holds the grant | A module never receives the path, never learns where the store is, and cannot name a location. `DOC-3`, `DOC-8`, `MA-2`. |
| One subdirectory per module | `<store>/<module-id>/`. The module says `write(key, bytes)` and the browser maps it. |
| The boundary is the broker's | A module cannot reach another module's directory because it never names one. It is not a rule modules are asked to respect. |

If the store has not been chosen, a module that asks for storage is told there
is none — not given a fallback in the profile. A silent fallback is how a user
ends up with documents in two places and only one of them synced.

## 3. What a document looks like

**One file per document. No database file anywhere under the store, ever.**

SQLite's locking over SMB and NFS is unreliable, and the failure mode is not a
lost write but a corrupted database. The same reasoning forbids a per-module
**index file**: every save would contend on one file, which is the shape that
produces conflicts fastest.

| | |
| --- | --- |
| Filename | The document's title, as a person would write it. Readable in a file manager, openable without Sunshine. |
| Identity | **Inside the document.** For HTML, `<meta name="sunshine-id">` and its siblings. |
| Sidecar | Only for formats that cannot carry metadata — an image, a PDF. `<name>.sunshine.json` beside the file. |

The whole set of fields, and no others:

| Field | |
| --- | --- |
| `id` | Opaque, stable, generated once. **Never derived from the title**, so renaming is free. |
| `updated_at` | RFC 3339, UTC. Written on every save. The only input to §4. |
| `device` | The name of the machine that wrote it, so a conflict can be described to a person rather than shown as two identical rows. |
| `module` | Which module owns it. The directory already says this; the field says it again so a file the user moved can still be attributed. |

**Why identity lives in the file and not in the name.** A title is something the
user changes. If the name were the identity, a rename would be a delete and a
create — which is exactly what a sync client would replicate to the other
device, and how a document is lost by being tidied.

## 4. Conflicts

The sync client produces the conflict; Sunshine does not detect it, it *finds*
it — two files carrying the same `id`.

| Situation | What happens |
| --- | --- |
| Two files, same `id` | The newer `updated_at` is the document. The other is **kept, listed, and marked as a conflict**, naming the device that wrote it. |
| A file with no `id` | A document Sunshine has not seen. It is **adopted** — given an id and left where it is. The user put it there on purpose. |
| `id` matches, file is newer than its own `updated_at` | Edited outside Sunshine. The file is right; re-read it. |
| A conflict the user resolves | They keep one and delete the other, in Sunshine or in their file manager. Both work, because both are just files. |

**Nothing is deleted to resolve a conflict, and nothing is merged.** Merging is
the only available behaviour that can produce a document neither person wrote,
and it would do so silently.

## 5. What the store is not

- **Not a database.** Nothing under it is a format only Sunshine can read.
- **Not a cache.** Sunshine must never be the only place a document exists.
- **Not Sunshine's scratch space.** No lock files, no indexes, no state files.
  Anything Sunshine needs for itself lives in the profile, which is not synced.
  **The store contains the user's documents and nothing else.**

The last one is the rule most likely to be broken by accident, and it is the one
that keeps the folder trustworthy when a person opens it.

## 6. Invariants

Class **O** is decidable offline. **B** needs the built browser. **U** needs a
person and two machines.

| ID | Invariant | Class |
| --- | --- | --- |
| DS-1 | The store is one user-chosen directory, held as a grant. A module never receives a path and never names a location. | O |
| DS-2 | One file per document. No database file and no index file anywhere under the store. | O |
| DS-3 | A document's identity is inside it, or in a sidecar where the format cannot carry it. It is never derived from the filename. | O |
| DS-4 | The metadata fields are exactly `id`, `updated_at`, `device`, `module`. | O |
| DS-5 | Sunshine writes nothing under the store that is not a document the user created, or its sidecar. | O |
| DS-6 | Two files with one `id`: the newer is current, the other is preserved and shown. Neither is deleted and neither is merged. | B |
| DS-7 | A file with no `id` is adopted rather than ignored. | B |
| DS-8 | With no store chosen, a module asking for storage is refused. There is no fallback into the profile. | B |
| DS-9 | Editing on two machines while both are offline loses nothing when they reconnect. | U |

**No check claims any of these yet, because no code implements them.** DS-1 to
DS-5 become decidable the moment the store is written, and the guard that
decides them should be written with it rather than after — this project's own
record is that a rule with no check is a rule that drifts.

## 7. What this reverses

`docs/MARKETPICK_PORT_PLAN.md` and `docs/FIRST_MODULE_GUIDE.md` both suggest
Chromium's `//sql` for a module's storage. **For the shared store that is now
wrong**, and DS-2 says why.

Profile-local state can still be SQLite: the profile is not synced, is not
shared between devices, and is not the user's to open. The distinction is not
"which database" but **which volume** — and a store the user picked is, by
construction, a volume something else is writing to.

## 8. NOT VERIFIED

- **Nothing here is built.** No directory is chosen, no document is written, no
  conflict has been seen. Every row in §4 is a rule rather than an observation.
- **No sync client has been tested against these rules.** Their conflict naming,
  their timing, and what they do with a sidecar beside a renamed file are all
  assumed from documented behaviour. The first real test will probably correct
  §4.
- The SQLite caveat in §3 is upstream's own statement about network file
  systems, not something reproduced here.
- DS-9 needs two machines and a disconnection, and there is no way to run it in
  CI. It is the invariant most likely to be quietly false.
- Nothing decides what happens when the store folder disappears — an unmounted
  share, a revoked grant, a user moving it. That is a real gap and it is the
  next thing this contract needs.
