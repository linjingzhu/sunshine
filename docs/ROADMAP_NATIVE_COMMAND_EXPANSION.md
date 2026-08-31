# Native command expansion — re-assessment and sequencing

## Status and scope

This is a re-assessment, not a design and not an implementation. It answers one
question the product owner asked twice: earlier in this project's life, with
zero native source in the tree, and again now that the security surface
(`chrome://sunshine-security`, patch `0005-sunshine-security-webui`) has a
compiled build behind it and ADR 0007's seam
(`0004-sunshine-webui-seam`) has landed, letting further WebUI surfaces plug
in without touching upstream files. No patch, code, module manifest, or
registry entry is created, changed, or proposed by this document. No product
decision is made here; every place a command's shape depends on an open P0 is
cited and left open.

**On the seam itself.** `downstream/patches/series` holds twenty-four patches today —
`0001-sunshine-branding`, `0002-sunshine-new-tab`,
`0003-sunshine-no-missing-api-key-warning`, `0004-sunshine-webui-seam`,
`0005-sunshine-security-webui`, `0006-sunshine-document-webui`,
`0007-sunshine-modules-webui`, `0008-sunshine-module-home-button`,
`0009-sunshine-windows-install-identity`, `0010-sunshine-product-strings`,
`0011-sunshine-module-shell`, `0012-sunshine-module-mount`, `0013-sunshine-module-shell-entry`, `0014-sunshine-module-registration-entry`, `0015-sunshine-shell-frame-policy`, `0016-sunshine-module-storage-port`, `0017-sunshine-mouse-gestures`, `0018-sunshine-account-surface`, `0019-sunshine-account-client-argument`, `0020-sunshine-newtab-background-format`, `0021-sunshine-newtab-background-source`,
`0022-sunshine-searchbox-state`,
`0023-sunshine-installer-install-root`, `0024-sunshine-settings-surface`. The seam
described in `docs/decisions/0007-module-contribution-seam.md` is now the
fourth of those, and the two surfaces built on it have been added behind it —
which is the seam doing exactly what the ADR said it would: a surface patch
that once edited seven upstream files now appends to a registry the seam
created, and the second such patch edits no upstream file at all.

What the seam has *not* had is a compile. Everything below is sequencing
against a mechanism verified in source and against the pinned revision, not
against a built browser; `docs/RUNTIME_VERIFICATION.md` owns that distinction
and this roadmap does not claim to close it.

## 1. The re-assessment

**The earlier answer — no, "Dev-OS"-style large module expansion is not
feasible — was correct for the state it was asked about: zero native source,
two commands with any implementation at all, both Python-side.** That state no
longer holds in the same shape, but the shape it changed into is narrower than
"now every remaining command is unblocked."

What actually changed:

- One WebUI surface (`chrome://sunshine-security`, patch `0005`) has gone from
  contract to patch. `docs/decisions/0007-module-contribution-seam.md` records
  that this single build is what let the seam be designed at all — the seam is
  an abstraction over machinery ADR 0007 says was, at the time of its writing,
  entirely unexercised.
- The seam (`0004-sunshine-webui-seam`) has now been built, dropping the
  marginal cost of a second WebUI surface from seven upstream-file edits to
  zero upstream-file edits: the security surface's own patch no longer
  touches any of the seven, only the seam's own registry files.
- **Neither change touched the command registry.** Reading every entry it held
  when this was written (section 2 below) found that not one was itself a
  WebUI-surface-shaped command — no entry navigated to a `chrome://` page.

  **That is no longer true, and this document's own §4 item 2 is why:**
  `security_center.open` was added afterwards and is the first such entry.
  `first_party/commands.json` now holds 25 commands. Section 3's
  categorisation covers the original set and is left as it was — it is a
  reading of a state, and re-numbering it would claim an analysis that was
  never done. The two things the product owner
  is watching — the seam, and the command registry — are related (a future
  surface command would use the seam) but have not yet touched each other.

So the honest re-assessment is **conditionally yes, narrower than "large
module expansion," and not yet**: the seam removes the main structural cost
that made broad WebUI-surface expansion look infeasible, but it removes it for
*surfaces*, and the registry's remaining unimplemented commands are
overwhelmingly not surface-shaped work at all. Section 3 sequences the surface
work the seam actually serves; it is two named surfaces today, not an open
field of them.

## 2. How this was produced

Every command in `first_party/commands.json` (`scripts/validate_commands.py`
reports 24) was read against: its own manifest entry (owner, `implementation`,
`predicate`, `unavailable_reasons`, errors); `docs/OPEN_DECISIONS.md`;
`docs/SUNSHINE_OS_STAGE_1_TO_3_IMPLEMENTATION_HANDOFF.md`; and the contract
that owns its area — `docs/BROWSER_UTILITIES_CONTRACT.md`,
`docs/GESTURE_CONTRACT.md`, `docs/ADVANCED_TABS_CONTRACT.md`,
`docs/COMMAND_PALETTE_CONTRACT.md`, `docs/WORKSPACE_NATIVE_INTEGRATION_MAP.md`,
`docs/TAB_WORKSPACE_SPLIT_CONTRACT.md`. Three decision proposals —
`docs/decisions/0009-document-surface-ingress-options.md`,
`0010-security-center-open-policy-options.md`, and
`0011-ai-credential-broker.md` — were read for anything they block; only the
first two turned out to bear on this registry's near-term work.

## 3. The 24 commands, categorized

`docs/COMMAND_PALETTE_CONTRACT.md`'s own "Not verified" section already states
the split this section arrives at independently: the registry holds 20
commands owned by Chromium and 4 owned by `sunshine.workspace`. Re-deriving it
by category, rather than by owner, gives the finer breakdown the task needs.

### 3.1 Command-only, no surface — 20

Every one of these wraps behavior Chromium already fully implements. Each
needs, at most, a dispatch wire-up from the command service to an existing
Chromium entry point (`chrome_command_ids.h` IDs, `browser_commands.cc`,
`BookmarkModel`, `TabStripModel`, `TabGroupModel`) — no new WebUI, no new
persisted state, no new upstream contribution point.

| Command | Evidence |
| --- | --- |
| `browser.devtools.open` | `docs/BROWSER_UTILITIES_CONTRACT.md`: one of the utilities the contract says Sunshine "does not implement," inheriting `DevToolsWindow` unchanged |
| `browser.find.close` / `.next` / `.open` / `.previous` | Same contract: wraps `FindBarController` / `find_in_page::FindTabHelper`; "Sunshine never recomputes, rounds, caps, or estimates" match state |
| `browser.page.save` | Same contract: wraps `content::SavePackage` / `SavePackageFilePicker` |
| `browser.print` | Same contract: wraps `PrintViewManager` and Chromium's own Print Preview WebUI — the preview is Chromium's page, not a Sunshine one |
| `browser.view_source` | Same contract: the `view-source` scheme, handled by `content`, "nothing in Stage 1" for Sunshine |
| `browser.zoom.in` / `.out` / `.reset` | Same contract: wraps `zoom::ZoomController` / `content::HostZoomMap`, persisted entirely by Chromium |
| `browser.back` / `browser.forward` | Already registered, Chromium-owned; `docs/GESTURE_CONTRACT.md` §4 dispatches gestures at these two without adding a registry entry |
| `browser.reload` | Wraps Chromium's own reload/stop toggle on the active tab; no contract assigns it new behavior |
| `bookmark.toggle` | Wraps `BookmarkModel`; `implementation: null` in the manifest, no owning contract proposes anything beyond the wrap |
| `tab.close` / `tab.duplicate` / `tab.new` | `docs/ADVANCED_TABS_CONTRACT.md` §7.4: "the existing registered commands are sufficient for everything else" here |
| `tab.group.create` / `tab.group.ungroup` | Same contract §3.2: native tab groups are "complete upstream," and these "are the whole of Sunshine's interest" — the contract "adds nothing and deliberately does not restate it" |

Eleven of the twenty (the find, zoom, print, save, view-source, and devtools
entries) are the browser-utility set `docs/BROWSER_UTILITIES_CONTRACT.md`
names explicitly as already registered. None of the twenty needs a design
decision or a new contribution point; each is a registration-and-dispatch
task, most of it arguably already done at the manifest level (`implementation`
is `null` on all of them because the operation *is* the existing Chromium
command — there is nothing Sunshine-side to point `implementation` at).

### 3.2 Needs a deeper browser-core hook — 4

`workspace.close`, `workspace.create`, `workspace.switch`,
`workspace.tab.move` — every command owned by `sunshine.workspace`.

These are not surface-shaped: nothing about them opens a page. They need
state Chromium does not have on its own — a workspace catalog and a per-tab,
per-window workspace assignment — carried through mechanisms
`docs/WORKSPACE_NATIVE_INTEGRATION_MAP.md` already identifies as the only
legitimate carriers: `SessionTab::extra_data` / `SessionWindow::extra_data`
via `components/sessions/core/session_service_commands.h`, observed through
`TabStripModelObserver`, with `TabStripModel` and `TabGroupModel` remaining
Chromium's. Two of the four (`workspace.close`, `workspace.tab.move`) already
carry a placeholder `implementation` pointing at
`scripts.workspace_model:*` — Python, not native, and exactly the two
non-native implementations the project's earlier feasibility read found. The
other two (`workspace.create`, `workspace.switch`) have `implementation: null`
still.

What is precisely missing, per task instruction 4 (naming the gap, not
proposing a fix): `docs/FIRST_PARTY_MODULE_ARCHITECTURE.md`'s four
contribution points — WebUI surface, native command, profile service,
integration surface — cover reaching profile-scoped Chromium service state and
dispatching a command. None of them is "own a field inside Chromium's own
persisted tab/window session `extra_data`," which is what
`sunshine_tab_uuid` / `sunshine_workspace_uuid` require, and none of them is
"contribute a piece of native (non-WebUI) browser chrome," which a workspace
switcher plausibly needs if it is not going to be a WebUI popup. ADR 0007's
seam is a WebUI-only answer — it removes upstream collisions for a
`WebUIConfigMap` registration, not for a `TabStripModelObserver` hook or a
session-command extension. Workspace commands need their own contribution-point
design (an ADR in the shape of 0006/0007, but for native browser-process state
and, if a non-WebUI switcher is wanted, native browser-chrome UI) before any
of the four can be called more than a Python placeholder. This document does
not propose that design.

### 3.3 Blocked on an open product decision — 0 of the 24

No command currently in `first_party/commands.json` is blocked on a P0 or P1
in `docs/OPEN_DECISIONS.md`. This is a finding, not an assumption: every P0 in
that index names something other than one of these 24 entries — extension
compatibility, download-warning behavior, profile deletion policy, the
document surface's ingress path, Security Center's provider-egress policy,
first-run suppression, telemetry reporting, the Chromium roll cadence,
distribution timing. The workspace commands in 3.2 are shaped, but not
stopped, by a P1: "Can a workspace span multiple windows in v1?"
(`docs/OPEN_DECISIONS.md` P1, sourced from handoff §11, which the index notes
"gates three other answers"). `docs/OPEN_DECISIONS.md`'s own P1 heading —
"shapes the work, does not stop it" — is why this stays out of the blocked
category rather than in it: nothing in the workspace commands' manifest
entries or owning contracts is withheld pending that answer, only their final
cross-window shape is.

### 3.4 WebUI-surface shaped — 0 of the 24

This is the load-bearing finding of this re-assessment, so it is stated
plainly: **no command in `first_party/commands.json` is itself a
WebUI-surface-shaped command.** Nothing in the registry navigates to a
`chrome://` or `chrome-untrusted://` route. The pages this project has
actually built or contracted — `chrome://sunshine-security` (patch `0005`,
contracted in `docs/SECURITY_CENTER_CONTRACT.md`) and
`chrome://sunshine-document` (contracted in `docs/DOCUMENT_SURFACE_CONTRACT.md`,
"the first test of whether [the] seam is worth having" per ADR 0007) — are
reached by direct navigation to their host, the same way `chrome://settings`
is; neither has, or per its contract needs, a command-palette entry the way
`browser.print` does. Confirming this was not a guess: `first_party/registry.json`
lists five modules (`sunshine.document`, `sunshine.modules`,
`sunshine.new_tab`, `sunshine.security`, `sunshine.workspace`), none of which
declares a command entrypoint.

`sunshine.security` was absent when this was written, and this document said so
— "the security surface that already compiled has no module manifest entry at
all yet, a gap distinct from and prior to the command-registry question." That
gap closed when `chrome://sunshine-modules` was built: a page whose whole job is
to list what this browser contains cannot omit a surface the browser ships, so
`sunshine.security` and `sunshine.modules` were both given manifests. The
conclusion below is unchanged — five surface modules with no command
entrypoints is still not a queue of commands waiting on the seam.

The practical consequence: **the seam does not have twenty-some
WebUI-surface-shaped commands waiting to be unblocked by it.** It has exactly
the two named surfaces above, neither of which is a "command" in the registry
sense, plus — per `docs/BROWSER_UTILITIES_CONTRACT.md`'s own precedent for
how a utility earns a registry entry — a small, separate follow-on step of
giving each surface a command-palette entry point once it has a module. Section
4 sequences that real, smaller set of work; it does not force three items out
of a registry category that in fact holds none.

## 4. Sequencing the actual WebUI-surface-shaped work

The sequence below assumes the seam described in
`docs/decisions/0007-module-contribution-seam.md` exists once it lands, per
this document's opening caveat. It is an order, not a timeline, ranked by: not
blocked on an open P0 first; smallest genuine increment over what `0005`
already proved second; the handoff's own wave priorities third
(`docs/SUNSHINE_OS_STAGE_1_TO_3_IMPLEMENTATION_HANDOFF.md` §10 places Security
Center at wave 7 and command palette/workspaces at wave 9 — document surface
is not in that table at all, being contracted after the handoff was written).

1. **Register `chrome://sunshine-security` as a first-party module. — Done.**
   `first_party/modules/sunshine-security/module.json` declares `sunshine.security`
   with a `native_command` entrypoint, and `first_party/registry.json` carries
   it. Original text follows.

   Smallest possible increment: the WebUI itself is already patched (`0005`);
   what is missing is a `module.json` for it and an entry in
   `first_party/registry.json`, in the same shape as the existing
   `sunshine.new_tab` and `sunshine.workspace` entries. Not blocked: ADR
   0010's own "Consequences of leaving these open" section states plainly that
   none of its three P0 questions "blocks Stage 1 work that does not touch a
   live provider: the WebUI shell, the SC-11 availability read, and the
   event-log scaffolding... do not depend on any of these answers." Those
   three P0s (origin-only egress, what a `block` verdict may do, whether any
   fail-closed policy should exist — all in
   `docs/decisions/0010-security-center-open-policy-options.md`) only block
   `ThreatProtectionProvider`'s *first real implementation*, which is a later,
   separable step this item does not require.

2. **Give the Security Center a command-registry entry. — Done.**
   `security_center.open`, owned by `sunshine.security`, which declares the
   matching `native_command` entrypoint. The surface is `security_center`
   rather than the `security` this item first suggested: `security` collides
   with the module manifest's own `security` block, and the doc scanner in
   `scripts/validate_commands.py` correctly read five existing prose mentions
   of manifest fields — `security.network.access` and its neighbours — as
   references to commands that do not exist. The collision was found by
   declaring the surface and watching the guard fail, which is the cheapest
   place to find it. Original text follows.

   Once (1) lands, add
   a command (for example, an `security.open`-shaped id — naming it is a
   registry decision this document does not make) that navigates to the
   surface, following exactly the precedent
   `docs/BROWSER_UTILITIES_CONTRACT.md` already set for its eleven utilities:
   "the correct Stage 1 output... is this document and a later
   command-registry entry per utility." This is the smallest possible
   genuinely-new registry addition — one `chromium`- or `sunshine`-owned
   command whose entire `implementation` is "navigate to an already-existing
   host" — and it is what would finally put a WebUI-surface-shaped entry into
   `first_party/commands.json` for the first time. Not blocked by anything
   beyond (1) landing.

3. **Build the Document Surface under Reading A (authored/pasted content).**
   Larger than (1)–(2) because the shell doesn't exist yet, but still the
   smallest shape available for a *second* surface: one privileged shell plus
   one `chrome-untrusted://` content frame, both mechanisms Chromium already
   owns per `docs/DOCUMENT_SURFACE_CONTRACT.md` §1's diagram — Sunshine
   builds neither the scheme nor the isolation, only the pages either side of
   it. `docs/decisions/0009-document-surface-ingress-options.md` states
   Reading A's "first deliverable" is "the surface... nothing is blocked," in
   contrast to Reading B, whose first deliverable is a file-broker contract
   that does not exist. **This is still formally blocked today**, and stays
   that way until the product owner acts: the choice between Reading A and
   Reading B is recorded as an open P0 in `docs/OPEN_DECISIONS.md` ("How does
   content reach the document surface... Blocks: the first document
   surface"), and ADR 0009's Reading-A recommendation is explicitly "a
   recommendation, not the decision the P0... is waiting on." This document
   does not resolve that P0; it only confirms that once resolved in favor of
   Reading A, nothing else stands between the seam and the surface.

No fourth item is offered. Beyond these three, the next WebUI-surface-shaped
work is Document Surface Reading B (blocked on the not-yet-designed
file-broker contract ADR 0009 describes) or a surface this repository has not
yet named anywhere — and inventing one here would be exactly the "large
module expansion" speculation this re-assessment exists to hold to evidence.

### All three are done, and a fourth surface arrived from outside this sequence

**Item 3 was the one this document called formally blocked**, on the P0 asking
how content reaches the document surface. The owner answered Reading A on
2026-08-27 and `0006-sunshine-document-webui` is in the stack. Items 1 and 2
are done as marked above.

Two surfaces have since landed that this sequence did not predict:
`chrome://sunshine-account` (`0018`) and `chrome://sunshine-settings` (`0024`).
**Neither invalidates the paragraph above** — it declined to *invent* a fourth
surface, and both of these were named by a contract before they were built,
which is the distinction it was drawing. What it does mean is that the sentence
"no fourth item is offered" describes the moment this section was written and
no longer describes the repository.

**What the sequence never covered is the part that is now the largest unblocked
piece of work**: the twenty commands in §3.1 are registered and unreachable.
There is no dispatch from a command identifier to a Chromium entry point and no
surface that lists one. `docs/COMMAND_PALETTE_CONTRACT.md` is documentation-only
and adds no patch, and it calls itself the executable test of §3.2's
command-first rule — a rule nothing has yet tested, because nothing invokes a
command by identifier except the two gestures bound in
`docs/GESTURE_CONTRACT.md` §4.

## 5. What is missing, precisely, for the categories this document does not solve

Per task instruction 4, these are named, not designed.

**Needs a deeper browser-core hook (workspace.create / workspace.switch /
workspace.close / workspace.tab.move):** a contribution-point design — its own
ADR, in the shape of ADR 0006 (module execution model) or ADR 0007 (the WebUI
seam) but for (a) Sunshine-owned fields inside Chromium's native
`SessionTab`/`SessionWindow` `extra_data`, reached through
`session_service_commands.h`, and (b) native (non-WebUI) browser-chrome
contribution, if a workspace switcher is not built as a WebUI surface. Neither
is one of `docs/FIRST_PARTY_MODULE_ARCHITECTURE.md`'s four current
contribution points. This roadmap does not propose which shape that design
should take.

**Document Surface (blocking the only surface-shaped work item 4 could not
mark ready):** the single open P0 in
`docs/decisions/0009-document-surface-ingress-options.md` / `docs/OPEN_DECISIONS.md`
— Reading A (authored/pasted) or Reading B (file import) as the surface's
first ingress path. Not this document's decision to make.

**Security Center's provider integration (not blocking module registration or
a command entry, per item 1 above, but blocking the live
`ThreatProtectionProvider`):** the three P0s in
`docs/decisions/0010-security-center-open-policy-options.md` — origin-only
egress permanence, the ceiling on a `block` verdict's effect, and whether any
fail-closed policy should ever exist. All three are argued both ways in that
ADR and none is decided by it.

**Everything gated behind AI features generally:** `docs/decisions/0011-ai-credential-broker.md`
designs a credential-broker shape but explicitly does not authorize building
it, and the handoff (§12) forbids AI features while the Stage 1–3 gates
remain open. No command in the current registry depends on it; it is named
here only because the task instructions called it out as a document to check
for blockers, and it was checked and found to block nothing in the 24.

## 6. Not verified

Nothing in this document has been compiled, run, or observed beyond what the
verification commands below actually executed. In particular: whether the
ADR 0007 seam, once built, actually behaves as designed (its own "NOT
VERIFIED" section says the same); whether `chrome://sunshine-security` has
ever really compiled in a build, which this repository's tracked history
cannot confirm one way or the other; and every acceptance criterion cited
above by reference (`BUA-*`, `SC-*`, `DOC-*`) remains exactly as unverified as
its owning contract already states.
