---
doc_id: adr-0017-module-mount-port
version: 1.0.0
canonical_path: docs/decisions/0017-module-mount-port.md
updated: 2026-08-19
---

# ADR 0017: How a module is mounted into the shell

## Status

**Accepted, and implemented by
`downstream/patches/0012-sunshine-module-mount.patch`.** The contract is
`docs/MODULE_MOUNT_CONTRACT.md`. Not compiled; §NOT VERIFIED is exact about
what that leaves open.

## Context

Two finished applications are being converted into modules, and both port plans
end at the same sentence. `docs/MARKETPICK_PORT_PLAN.md` §8: *"The host port
that §3 and §5 depend on has no implementation."* `docs/DEV_OS_PORT_PLAN.md`
§8, verbatim the same. `docs/MODULE_APP_GUIDE.md` §8 said it a third time.

Everything else was built. The seam gives a surface a directory and a registry
line (ADR 0007). The shell draws five regions and knows how to collapse them
(`docs/MODULE_SHELL_CONTRACT.md`). The manifest says what a module may reach,
and since ADR 0016 it can say more. What was missing is the one thing in the
middle: **a module had no way to be inside the shell.** Its three content areas
held the shell's own empty text and nothing could replace it.

The owner's instruction was direct — the existing projects are about to arrive,
so finish what is unimplemented about modules. This is that thing. It is a
socket, and the arriving projects are its first plug.

## Decision

### 1. Content is a frame; everything else is data the shell draws

A module's UI renders in an `<iframe>` at a `chrome-untrusted://` origin. Its
title, path, dirty flag, tab list and header actions do **not**: they cross as
strings, are validated, and are drawn by the shell with `createElement` and
`textContent`.

This is the same split `docs/DOCUMENT_SURFACE_CONTRACT.md` already made for one
surface, generalised. The reason is privilege, not taste: the shell is a
`chrome://` page at browser privilege, and the modules this project expects
interpolate GitHub responses, marketplace responses and file contents into
their views. Anything of theirs the shell's own document held, it would hold at
browser privilege.

`chrome-untrusted://` is Chromium's scheme. Sunshine registers none, so SEC-13
and ADR 0003 are untouched, and `scripts/verify_first_party_surfaces.py`
already allows it because the document surface's reading frame uses it.

### 2. The port carries no capability, and no field could hold one

`docs/MODULE_APP_GUIDE.md` MA-2 says no path, no handle, no URL, no callback.
The port makes that structural rather than a rule to remember:

- an identifier is matched against a pattern with no `/` and no `:`;
- a label is display text, written only with `textContent`;
- an icon is **a name from a closed set**, because an image is a URL;
- transferables are never read, so a `MessagePort` cannot arrive.

The one URL is the module's content URL, and it never crosses the port: it
comes from the registry compiled into the binary, is shape-checked by the
manifest validator, and is shape-checked again by the shell before it navigates.

### 3. Whole state, never a delta

One `describe` message carries everything the shell draws for a module. A delta
would oblige the shell to keep a second copy of the module's model in agreement
with the first, and the copy is where the two drift.
`chrome/browser/resources/sunshine/document/host.ts` reached the same
conclusion for the same reason, and this is that conclusion applied to the one
port every module has.

### 4. The dock still lists every module

Only a `surface` module may declare a mount, and most modules will not have
one. They are still in B. `docs/MODULE_SHELL_CONTRACT.md` §1 requires it: a
dock that hid what it could not mount would be a switcher that stops working
exactly when the module you are in is the problem. Selecting one shows the
shell's empty state, which is state 09 and a legitimate state to be in.

### 5. Three checks on every inbound message, not one

The source must be the mounted frame's own `contentWindow`, the origin must be
the origin that frame was opened at, and the payload must validate. Any one of
the three catches the ordinary mistake. The other two are for the case where
the first was wrong — and the case where it is wrong is a `chrome://` page
listening on `window`, which hears every frame in the tab.

## Consequences

- **Both port plans are unblocked at the seam.** What they do next — the tab
  list, the header, the body — has a defined shape to target, and
  `docs/MODULE_MOUNT_CONTRACT.md` §7 is the four-point instruction for a module
  app.
- **The largest deletion in each port is now the correct one.** Marketpick's
  nine copies of its top nav and Dev OS's `shell()` function both become
  `describe` messages. Dev OS's case is the sharper one: the shell it would be
  deleting is its own design, generalised.
- Three things the shell declared and never used are now used —
  `HEADER_ACTIONS_MAX`, `#headerActions`, `#headerDirty` — and one state the
  contract requires became reachable: nothing toggled C, so state 03 could be
  entered by narrowing the window and never on purpose. That was an MS-8
  failure sitting in a shipped patch, and it is fixed here because this is the
  change that had reason to look.
- A new guard and nine new claims. `MS-4` is among them and is not new: it had
  been claimed by `scripts/verify_shell_geometry.py` since the shell landed and
  counted by nothing, because `MS` was not a family
  `scripts/trace_invariants.py` knew. That is precisely the failure that file's
  own comment warns about — an unparsed token is absent, not rejected — and it
  went unnoticed for a wave.
- **A module in E belonging to a different module than D's is not built.** The
  shell contract permits it; the shell mounts the same module in both regions.
  Recorded so it is not mistaken for a decision.

## Alternatives considered

**A module supplies nodes, and the shell adopts them.** Rejected on privilege:
adopted nodes run in the adopting document. It would also have made MS-3 a
convention rather than a fact.

**One frame for the whole shell, with the module drawing its own chrome.** This
is what both applications do today and it is what
`docs/MODULE_SHELL_CONTRACT.md` §1 exists to refuse. A module that draws the
exits can omit them.

**A Mojo interface instead of `postMessage`.** Rejected because the port must
be implementable by a host that is not Chromium — ADR 0013 requires every app
to run on iPad, and `ui::MojoWebUIController` does not go there. `postMessage`
is the one mechanism both a WebUI frame and a `WKWebView` have. Mojo remains
correct for a module's *data* interface, which is a different port and is per
module; this one is shared and must be portable.

**Sending a `dense` hint with the mount message.** Drafted and removed. It is
not in the list `docs/MODULE_PORTING_GUIDE.md` §4 says crosses the port, and a
hint sent once at mount time would have been wrong at the first resize. A
module that needs its own width uses its own frame's width.

## NOT VERIFIED

- **No module declares a mount.** Every message in the contract is
  unexchanged, and the first port to arrive should expect to find at least one
  thing wrong. This is the honest state of a socket built before its plug, and
  it is preferable to inventing a module to demonstrate it with.
- **Nothing here has been compiled.** `mount.ts` and `mount_port.ts` have never
  been through `build_webui()` or upstream's eslint. Patches 0009 through 0012
  are all unbuilt.
- MM-9 and MM-10 need the browser; they are RV-35 and RV-36 and are `NOT RUN`.
- The three checks in §5 are read from source by
  `scripts/verify_module_mount.py`. That the checks are *present* is decided;
  that they are *sufficient* is reasoning, and it has not met a hostile frame.
