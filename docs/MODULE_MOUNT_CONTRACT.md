# Module Mount — Contract

## Status and scope

Applies to Sunshine OS on the pinned Chromium revision `152.0.7977.42`. It
defines **the host port**: the whole vocabulary a module app and the shell that
hosts it exchange, and the rules that make that exchange safe to hold open.

`docs/MODULE_SHELL_CONTRACT.md` says which regions the browser owns.
`docs/MODULE_APP_GUIDE.md` says what a module app is. This document is the
seam between them, and until it existed both of those documents ended in the
same sentence — *the host port has no implementation*. It has one now:

| Half | File |
| --- | --- |
| The port itself | `chrome/browser/resources/sunshine/shell/mount_port.ts` |
| Sunshine's implementation of it | `chrome/browser/resources/sunshine/shell/mount.ts` |
| What the shell draws from it | `chrome/browser/resources/sunshine/shell/app.ts` |
| The declaration that a module is mountable | `mount.content_url` in `module.json` |

Both TypeScript files arrive in `downstream/patches/0012-sunshine-module-mount.patch`.

**§9 says what is not verified, and it is most of the runtime behaviour.** No
module declares a mount yet, so the messages below have never been exchanged.

## 1. The one structural decision

**The port carries data. It carries no capability, and it carries nothing
shaped like one.**

`docs/MODULE_APP_GUIDE.md` MA-2 states it as a rule; this document is where it
becomes a shape. The strong form is not "the shell refuses a path" — it is that
**no field on this port can hold one**:

- an identifier is matched against `IDENTIFIER`, which admits no `/` and no
  `:`, so nothing shaped like a path or a scheme survives validation;
- a label is display text, and the shell writes it with `textContent` and
  nowhere else — never as an `href`, a `src`, or markup;
- an icon is a **name from a closed set**, not an image, because an image is a
  URL;
- there is no field for a callback, a handle, a port, or a `MessagePort`,
  because `postMessage` transferables are never read.

The one URL in the whole arrangement is the module's own content URL, and it
does not cross the port at all: it comes from the registry compiled into the
binary, and the shell checks its shape before navigating to it.

### Why a frame and not a script

The alternative — a module supplying nodes, or markup, or a script the shell
runs — fails on privilege, not on taste. The shell is a `chrome://` page at
browser privilege. Module content is authored elsewhere; for the ports this
project expects, it is authored around data fetched from GitHub and
marketplaces. Anything of a module's that the shell's own document held would
hold it at browser privilege, which is the failure
`docs/SECURITY_ARCHITECTURE_CONTRACT.md` exists to prevent, and which
`docs/MODULE_SHELL_CONTRACT.md` MS-3 states for this surface specifically.

So a module renders in an iframe at a `chrome-untrusted://` origin — Chromium's
scheme, not one Sunshine registers, so SEC-13 and
`docs/decisions/0003-internal-scheme.md` are untouched — and the shell draws
only what it can validate into text.

## 2. Declaring a mount

A module becomes mountable by adding one optional block to `module.json`:

```json
"mount": { "content_url": "chrome-untrusted://sunshine-marketpick-app/" }
```

| Rule | |
| --- | --- |
| Scheme | `chrome-untrusted://` and nothing else. |
| Host | One bare label, `[a-z0-9-]`, not starting or ending with `-`. |
| Path | Exactly `/`. No query, no fragment, no deeper path. |
| Kind | Only a `surface` module may declare one. |
| Optional | A module without it is still listed in the dock. |

The last row is not a leniency. `docs/MODULE_SHELL_CONTRACT.md` §1 requires B to
list *every* module — a dock that hid what it could not mount would be a
switcher that stops working exactly when the current module is the problem. A
listed module with no mount shows the shell's empty state, which is state 09.

Enforced by `scripts/validate_first_party_modules.py` (`validate_mount`) and by
`mount_port.contentUrl()` at run time. Neither defers to the other, and
`scripts/verify_module_mount.py` fails if the two shapes disagree.

## 3. What crosses, shell to module

| Message | Fields | Meaning |
| --- | --- | --- |
| `mount` | `module`, `region`, `activeTab`, `panelRole` | Sent once, on the frame's `load`. The frame's introduction to where it is. |
| `activate` | `tab` | The user chose a tab in C. |
| `action` | `action` | The user pressed one of the module's header actions. |
| `panel` | `role` | E is now showing this role. |
| `storage-result` | `requestId`, `ok`, `error`, `documents`, `id`, `body` | The answer to exactly one `storage-request`, echoing its `requestId`. |

`region` is `body` or `panel`. D's body and E's role content are two frames of
the same module at the same content URL, told apart by this field and by
nothing else — so a module renders one document differently in each without the
registry needing a second URL for it.

## 4. What crosses, module to shell

| Message | Fields | Meaning |
| --- | --- | --- |
| `describe` | `title`, `path`, `icon`, `dirty`, `tabs`, `activeTab`, `actions` | Everything the shell draws on the module's behalf. |
| `select` | `tab` | The module moved its own selection. C follows. |
| `request-panel` | `role` | The module would like E showing a role. |
| `storage-request` | `requestId`, `op`, `id`, `title`, `body` | Ask the document store for something. `op` is `list`, `read`, `save` or `remove`. |

**`describe` is whole state, never a delta.** A delta obliges the receiver to
keep a second copy of the model in agreement with the first, and the copy is
where the two drift apart. `chrome/browser/resources/sunshine/document/host.ts`
takes the same position for the same reason.

A `describe` from the **panel** region is discarded. The header and the tab list
belong to D's module; a panel that could rewrite them would be E deciding what
D is.

## 4a. The document store, across the port

`docs/DOCUMENT_STORE_CONTRACT.md` says where documents live and what they look
like. This is how a module reaches them, and it is the **only** way: an
installed module cannot be given a Mojo interface, so the shell brokers.

**Correlation is in the message, not in the order of messages.** The module
coins a `requestId` and the shell echoes it. `postMessage` gives no ordering
guarantee worth relying on across a navigation, and a store call that resolved
the wrong promise would be a document written under another document's name.

**Every request is answered.** A request that got no reply would leave a module
waiting forever on a promise it cannot cancel, which is a worse failure than a
refusal — so a handler that throws still produces `failed`.

### The one field that reaches the filesystem

`title` **becomes the filename** — `DS-3` puts identity inside the document
precisely so that the name can be the user's to read and to change. That makes
`title` the single string a module sends that touches the disk, and it is
validated hardest: no separator, no traversal, no control character, no leading
or trailing space, not empty, and never `.` or `..`.

`documentTitle()` in `mount_port.ts` is that check, and it runs on the way in
*and* on the way out — a document in a `storage-result` whose title is not a
legal title poisons the whole result rather than being repaired, because a
repaired name is a name nobody chose.

### What it answers today

**`no-store`, always.** The store needs a directory the user has chosen and a
browser side to read it with, and neither exists. `DS-8` says the answer is a
refusal rather than a fallback into the profile, because a silent fallback is
how a person ends up with documents in two places and only one of them synced.

That is not a stub. It is the correct behaviour of an unconfigured store, and
it is the behaviour a module has to handle anyway — a user can revoke the
folder, or unmount the share, at any time.

## 5. Limits, and where each one lives

| Limit | Value | Declared in |
| --- | --- | --- |
| Header actions | `HEADER_ACTIONS_MAX` = 3 | `geometry.ts` — it is a measurement of the header |
| Tabs | `MAX_TABS` = 200 | `mount_port.ts` — it is a property of the message |
| Label length | `MAX_LABEL` = 120 | `mount_port.ts` |
| Identifier | `IDENTIFIER`, 64 characters | `mount_port.ts` |
| Icon names | `ICONS`, 8 of them | `mount_port.ts` |
| Document body | `MAX_BODY` = 4 MiB | `mount_port.ts` — a body is one `postMessage` payload, so the bound keeps one save from stalling the shell. Larger needs streaming, which is a later problem and should be solved as one rather than by raising this number |

The split is deliberate and is the same one `docs/MODULE_SHELL_CONTRACT.md`
MS-4 draws: a number that describes the *layout* belongs with the layout, and a
number that describes a *message* belongs with the message. Putting the action
cap in the port would have made the header's capacity a fact about the protocol
that the iPad shell would then have to honour for no reason of its own.

A module offering four actions has three of them drawn and is not otherwise
refused: dropping the description whole would cost the title and the tabs too.

## 6. Invariants

Class **O** is decidable offline. **B** needs the built browser.

| ID | Invariant | Class |
| --- | --- | --- |
| MM-1 | A mount declaration is `chrome-untrusted://<host>/` and nothing else. The manifest check and the run-time check accept the same set. | O |
| MM-2 | Only a `surface` module declares a mount. A module without one is still listed in the dock. | O |
| MM-3 | `mount_port.ts` imports nothing. It is the file a second host copies, and a port that reaches for a browser is not a port. | O |
| MM-4 | Every message name is in a closed set declared in `mount_port.ts`, and §3 and §4 name the same sets. | O |
| MM-5 | No field on the port carries a path, a URL, a handle, a callback or an image. Identifiers are constrained so that none can. | O |
| MM-6 | The shell accepts a message only when its source is the mounted frame's own window, its origin is the origin that frame was opened at, and its payload validates. All three, independently. | O |
| MM-7 | Nothing a module sends reaches the shell's document except as `textContent`. Module markup renders only inside the frame. | O |
| MM-8 | A `describe` from the `panel` region changes nothing about D's header or C's list. | O |
| MM-9 | Closing E destroys its frame. A module does not keep running behind a hidden region. | B |
| MM-10 | Switching modules replaces the frame rather than reusing it, so no state of the previous module survives into the next. | B |
| MM-11 | The shell's data source names the origins it may frame, derived from the compiled registry. A declared mount whose origin is not named is a frame that never loads. | O |

`scripts/verify_module_mount.py` decides MM-1 through MM-8 and MM-11, and
claims them. MM-9 and MM-10 need the browser; they are RV-35 and RV-36.

**MM-11 exists because its absence is invisible.** A WebUI data source forbids
every frame by default — `URLDataSource::GetContentSecurityPolicy()` returns
`child-src 'none';` — so a shell that named no origin compiles, passes every
other check here, and produces a mount point whose frame silently never loads.
`downstream/patches/0011-sunshine-module-shell.patch` shipped exactly that;
`downstream/patches/0015-sunshine-shell-frame-policy.patch` repaired it. The
document surface had already met this and named its one origin literally, which
is the part that did not get carried across.

## 7. What a module app must do

Copy `mount_port.ts` into the app — do not import it from Sunshine, which is
MA-1 — and:

1. listen for `message`, validate with `hostMessage()`, ignore anything that
   returns null;
2. post a `describe` as soon as the `mount` message arrives, and again whenever
   the title, path, dirty flag, tab list or actions change;
3. render the tab the `activate` message names, and post `select` when the
   module moves its own selection;
4. never draw a tab list, a title bar, a switcher or a panel container of its
   own. Those are regions A, B, C and D's header, and
   `docs/MODULE_SHELL_CONTRACT.md` §1 gives them to the browser.

Point 4 is the largest deletion in most ports and it is the one that will feel
wrong. `docs/DEV_OS_PORT_PLAN.md` §2 is the worked case: the shell every module
now receives is Dev OS's own design, and keeping a second implementation of it
inside one module would put two of the same thing in one window.

## 8. Where this disagrees with nothing

This contract adds no exception to any existing one, which is worth stating
because most seams here have needed one:

- **SEC-13 / ADR 0003** — Sunshine registers no scheme. `chrome-untrusted://`
  is Chromium's, already listed in `scripts/verify_first_party_surfaces.py`.
- **SEC-14** — the frame loads no remote resource. Its content URL is a
  resource bundle compiled into the binary.
- **OS-9** — nothing is navigated to from an accepted string. The one URL is
  from the compiled-in registry, and it is shape-checked anyway.
- **DOC-2** — the frame receives content, never capability. The port is the
  general form of the rule the document surface made for itself.
- **MA-2** — no path, no handle, no URL, no callback. §1.

## 9. NOT VERIFIED

- **No module declares a mount.** The socket is built; nothing is plugged into
  it. Every message in §3 and §4 is therefore unexchanged, and the first port to
  arrive should expect to find at least one thing here wrong.
- **One thing here was already wrong and is fixed.** Until patch 0015 the shell
  named no framable origin, so its default `child-src 'none';` would have
  blocked every mounted frame — the port could not have carried a message even
  with a module plugged in. It was found by reading the document surface's C++
  beside the shell's, not by any check, which is why MM-11 now exists.
- **Nothing here has been built.** The patch applies to a fresh checkout of the
  pinned revision. That is placement, not behaviour, and no native build has
  compiled `mount.ts` or `mount_port.ts`.
- MM-9 and MM-10 need the browser and are unrun.
- **A module in E belonging to a different module than D's is not
  implemented.** `docs/MODULE_SHELL_CONTRACT.md` §1 permits it; the shell mounts
  the same module in both regions and there is no message that would say
  otherwise. Naming it so it is not mistaken for a decision.
- The `dense` hint was drafted onto the `mount` message and removed before
  landing: it is not in the list of what
  `docs/MODULE_PORTING_GUIDE.md` §4 says crosses the port, and a hint sent once
  at mount time would have been wrong at the first resize.
