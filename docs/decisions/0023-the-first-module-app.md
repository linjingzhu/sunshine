---
doc_id: adr-0023-the-first-module-app
version: 1.0.0
canonical_path: docs/decisions/0023-the-first-module-app.md
updated: 2026-09-06
---

# ADR 0023: The first module app draws no data, on purpose

## Status

**Accepted, and implemented by `downstream/patches/0029-sunshine-dev-os-module-app.patch`.**
Read against the pinned revision `152.0.7977.42`. It is not compiled here; the
NOT VERIFIED section says exactly what that leaves open.

## Context

The owner asked to test attaching modules to Sunshine, today. Reading the tree
for what that would take produced a finding worth more than the patch:

**There was nothing to attach.** Six modules are registered. Four are browser
surfaces (`chrome://sunshine-document`, `-modules`, `-security`, and the new
tab overlay) and one is a service of four commands, so none of them is a thing
the shell mounts. The sixth, `sunshine.dev-os`, declared
`mount.content_url = chrome-untrusted://sunshine-dev-os-app/` — and **nothing
served that host**. The URL existed twice, in `module.json` and in the registry
baked into patch 0007, and no `AddUntrustedWebUIConfig` answered it. Mounting
it would have navigated an iframe to a host that does not exist.

That is why `docs/MODULE_MOUNT_CONTRACT.md` §9 read "the socket is built;
nothing is plugged into it", and why RV-35 and RV-36 — both of which begin
"with a module mounted" — had never been runnable.

## Decision

**Build the smallest app that makes the port carry a message, and no more.**

It speaks the four things §7 asks of a module app: it validates every inbound
message with `hostMessage()` and drops what returns null; it posts `describe`
when `mount` arrives; it renders the tab `activate` names; and it draws no tab
list, title, switcher or panel container of its own.

### It draws no data, and says so

The Dev OS manifest promises pull requests, CI and milestones read from
repositories. This frame cannot reach one: its own `module.json` declares
network access `deny`, and the data source enforces that with
`connect-src 'none';`.

So each tab states what it will show **and that it has read nothing**. Filling
the gap with plausible numbers would break `docs/DEV_OS_PORT_PLAN.md`'s own
rule, quoted from the manifest this app belongs to: *"what it could not read is
reported as unread rather than drawn as zero."* An app that violated that in
its first frame would be a poor advertisement for the rule.

**This is not a port of Dev OS.** That is `docs/DEV_OS_PORT_PLAN.md`, and it is
separate work. What this proves, if it works, is the port — not the module.

### The copy of `mount_port.ts` is guarded

§7 point 1 and MA-1 require an app to *copy* the port rather than import it: an
app that imported it from Sunshine would run only inside Sunshine, and the port
exists so the same module renders in a host Sunshine did not write.

Copying invites exactly one failure — two files drift, both keep the name, and
the shell and the app disagree about what a message is while every other check
passes. `scripts/verify_module_mount.py` now compares the copy against the
original below each file's opening block comment, byte for byte, and names the
first line that differs. Changing `MAX_TABS` in the copy alone makes it fail.

The header comment is the only part allowed to differ, because it is the part
that has to: the copy says it is a copy and names its original.

### Cost

**No new upstream file.** The whole app lands in files the stack already
creates — the seam's `RegisterWebUIConfigs()`, the resource bundle's
`static_files` and `ts_files`, the WebUI `BUILD.gn`, and the shared hosts
header. That is the seam of ADR 0007 doing what it was built for, and it is
worth saying out loud: a whole new browser surface, at a new origin, for zero
upstream ownership.

## Consequences

- **`sunshine.dev-os` moves from `planned` to `prepared`.** The baked registry
  in patch 0007 is regenerated from `first_party/` by
  `scripts/module_registry_payload.py`, because the two must stay byte-identical
  and `verify_module_registry_sync.py` fails when they are not.
- **RV-35 and RV-36 become runnable for the first time.** RV-50 to RV-53 are
  new and check the mount itself.
- The app is registered from the seam rather than discovered from the module
  registry. A registration derived from a manifest would be a second place a
  host can come from, and §1 of the mount contract puts that at exactly one:
  "the registry compiled into the binary".
- **The other five modules are still not mountable, and should not be.** Four
  are browser surfaces and one is a service. "Attach each module" is not a
  thing the shell can do to them, and a mount block added to a browser surface
  would be a second way to reach a page that already has one.

## NOT VERIFIED

- **Nothing here has been compiled, and no frame has loaded.** Every message in
  §3 and §4 remains unexchanged. RV-50 to RV-53 are unrun, and so are RV-35 and
  RV-36 which this makes runnable.
- Whether `SetupWebUIDataSource` serves this bundle's `dev_os_app/` prefix the
  way `SurfaceResources()` expects is read from the document surface's working
  precedent, not observed.
- The `AddFrameAncestor(chrome://sunshine-shell/)` pairing with the shell's own
  `child-src` is read from patch 0015, which fixed that exact mismatch once
  from the other side. Both halves have never been exercised together.
