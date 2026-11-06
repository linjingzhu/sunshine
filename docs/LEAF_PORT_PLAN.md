# Leaf → Sunshine module: the plan

## 0. Status

Applies to Sunshine OS on the pinned Chromium revision `152.0.7977.42`, read
from source rather than estimated.

**Nothing is built.** Leaf has no module slot, no manifest, no host. This
document is what a port would cost and which three decisions it waits on.

The source read is `linjingzhu/html-leaf` at `c50cab2`.

## 1. What Leaf is, measured

Leaf is a visual project editor — a tree of Project → Document → Page, with
Preview / Compare / Code views, a DOM inspector, and HTML, Markdown, JSON and
PDF pages. It ships as an **Electron desktop application**.

| | Measured |
| --- | --- |
| JavaScript under `src/` | 17,637 lines |
| `src/renderer/` | 928 KB — the product |
| `src/main.js` | 84 KB — the Node side |
| `src/preload.js` | 8 KB — the bridge |
| Files importing `electron`, `fs`, `path` or `child_process` | **exactly two**: `main.js`, `preload.js` |

**That last row is the finding the whole plan rests on.** Leaf's Electron
coupling is not spread through the product; it is confined to the two files
whose job is to be the host. The renderer is already web code.

**Electron is excluded and this port is not a wrapper.**
`.ai/PROJECT_CONTEXT.md` excludes Electron, CEF, Qt WebEngine, Tauri and OS
WebView wrappers. So the port re-hosts `src/renderer/` on Sunshine's module
contribution points and replaces `main.js` with what Chromium already provides.
Nothing here proposes running Electron inside Sunshine.

## 2. The capability surface, and it is finite

`main.js` serves **60 IPC channels**. They are the complete list of what Leaf
asks a host for, and they divide cleanly:

| Cluster | Channels | Where it lands |
| --- | --- | --- |
| **Local files** — `file:*`, `project:*` | 18 | Gate 1 (§3) |
| **Cloud** — `drive:*`, `github:*` | 18 | Gate 2 (§3) |
| **Document work** — `convert:*`, `ocr:*`, `extractText:*`, `compress:*`, `pdf:*`, `fonts:download` | ~12 | **Already web.** `pdfjs-dist`, `pdf-lib` and `tesseract.js` are browser libraries; `@napi-rs/canvas` and `sharp` are Node-only stand-ins for `<canvas>`, `OffscreenCanvas` and `createImageBitmap`, which the renderer has natively |
| **Shell and window** — `clipboard:*`, `net:fetch*`, `shell:openExternal`, `window:*`, `app:*` | ~12 | Mostly web: `navigator.clipboard`, `fetch`, `window.open`, the Fullscreen API. `net:fetchPage`/`net:fetchStylesheet` become same-origin-policy questions, which `docs/HOST_ALLOWLIST_CONTRACT.md` governs |

Roughly **half the surface needs nothing that does not exist**. The other half
is two gates and they are different in kind: one is a bounded upstream change,
the other is a product decision.

## 3. The three gates

### Gate 1 — local files. Smaller than it looks, and upstream shows the way

Leaf's centre of gravity is opening and saving files. Sunshine's answer is
`docs/FILE_BROKER_CONTRACT.md`, whose structural decision is **"the user names
the place. The module names nothing."** That contract states plainly that
**nothing in it is implemented**: the validator accepts
`filesystem.access: user_selected` and no code opens a file for a module.

**The File System Access API is that principle, already shipped.**
`showOpenFilePicker`, `showSaveFilePicker` and `showDirectoryPicker` hand back
handles the *user* chose and the page never named. Read at the pin,
`third_party/blink/renderer/modules/file_system_access/window_file_system_access.idl`
exposes them on `Window` under `[SecureContext, RuntimeEnabled=FileSystemAccessLocal]`
with no scheme restriction, and `content/browser/file_system_access/file_system_access_manager_impl.cc`
gates `BindReceiver` on `network::IsOriginPotentiallyTrustworthy` alone.

One thing does block it, and exactly one.
`third_party/blink/renderer/modules/file_system_access/global_file_system_access.cc`
refuses a picker when the frame is cross-origin to the outermost main frame:

```cpp
if ((!local_frame || local_frame->IsCrossOriginToOutermostMainFrame()) &&
    !Platform::Current()->IsFilePickerAllowedForCrossOriginSubframe(
        /* origin */)) {
  exception_state.ThrowSecurityError( ... );
}
```

A module renders in an **iframe** at `chrome-untrusted://<host>/` inside the
shell (`docs/MODULE_MOUNT_CONTRACT.md` §MM-1), so it is cross-origin to the
outermost main frame and every picker throws today.

**And upstream already solves this exact shape for itself.**
`third_party/blink/public/platform/platform.h`:

```cpp
// For example, Chrome's built-in PDF viewer may be hosted in a cross-origin
// subframe. To allow this viewer to function correctly, Chrome uses this
// method to grant it access to the file picker.
virtual bool IsFilePickerAllowedForCrossOriginSubframe(
    const WebSecurityOrigin& origin) { return false; }
```

It is a virtual that **takes the origin** and defaults to false, and Chromium
overrides it to grant its own cross-origin subframe a picker. Granting it to
`chrome-untrusted://` module hosts is the same mechanism for the same problem,
scoped per origin — not an invention.

Two further conditions in the same function stay in force and both are wanted:
an origin-sandboxed document cannot show a picker, and a picker needs
**transient user activation**. The second matches the manifest's existing
`security.requires_user_activation`.

**This is a decision, not only a patch.** `FILE_BROKER_CONTRACT.md` anticipated
a broker. Satisfying its principle through the platform API instead is cheaper
and narrower, and it means the module holds handles directly rather than asking
a broker per operation. The contract has to say which of the two Sunshine is
doing before either is built.

### Gate 2 — cloud. The real blocker, and it is policy

`drive:*` (8) and `github:*` (10) are a third of the surface, and they carry
OAuth. Sunshine's account rules are narrow by decision: a single client id that
enters only as a build-pipeline secret and never the repository, scopes
**`openid` and `email` only**, and `scripts/verify_account_freedom.py` enforces
it offline. `docs/decisions/0018-sunshine-account-link.md` and
`docs/ACCOUNT_LINK_PLAN.md` hold the procedure.

Drive and GitHub need different clients and far wider scopes. **Nothing in the
current account decision permits them**, and widening it is the owner's call,
not an implementation detail. Until it is made, the honest shape is a Leaf
module whose cloud panes say they are not configured — which is also what
`docs/DEV_OS_PORT_PLAN.md` found for Dev OS's GitHub capability.

### Gate 3 — which module tier

Two exist on paper:

- **Compiled first-party surface**, the way Dev OS is going: a patch registers
  `chrome-untrusted://sunshine-leaf-app/` and the assets ride in the patch
  stack. Proven — patch 0029 does it — but it puts ~900 KB of application
  JavaScript into the downstream patch stack, and `docs/SIZE_BUDGET.md` and the
  rebase cost are what that spends.
- **Installed module tier**, `docs/decisions/0019-installed-module-tier.md`: a
  web module in a signed bundle served at `chrome-untrusted://<bundle-id>/`.
  **Decided yes, and unimplemented** — no `bundle_id` appears anywhere in the
  repository. Leaf is the first candidate large enough to justify building it.

## 4. Staging

Ordered so that each stage is useful alone and none waits on a decision the
previous one did not need.

| Stage | What | Needs |
| --- | --- | --- |
| **L0** | A manifest and a mount slot: `first_party/modules/sunshine-leaf/module.json`, `filesystem: none`, `network: deny`, cloud panes declared absent. Validates, mounts, renders the shell | Nothing new. This is the Dev OS path, already proven |
| **L1** | Port `src/renderer/` onto the mount port. Replace the ~12 document-work channels with their browser equivalents and delete `@napi-rs/canvas` and `sharp` | L0. Decides Gate 3 first, because it chooses where the assets live |
| **L2** | Gate 1: the platform override, scoped to module origins, plus the contract amendment saying broker-or-platform. Unlocks the 18 file channels — **the point at which Leaf becomes usable** | An owner decision on the contract, then a patch and a build |
| **L3** | Gate 2, or a permanent decision not to. Cloud panes either gain an account policy or stay declared-absent | An owner decision on scopes |

**L2 is the one that matters.** Leaf without local files is a viewer; with
them it is the editor it is. L0 and L1 are work; L2 is the decision.

## 5. Not verified

- **Nothing here has been run.** No manifest exists, no patch, no build.
- That the override in Gate 1 is sufficient. The pinned source says the picker
  is refused for exactly that reason and that the hook exists; whether a module
  origin passes every other check is a build-and-run question, and the `[Measure]`
  and `RuntimeEnabled` attributes on the IDL have not been traced to their
  runtime values in a Sunshine build.
- The ~12 and ~12 in §2 are read from the channel names. Each channel's body was
  not read, so a channel that looks like clipboard work and is not would move
  between rows.
- Whether `src/renderer/` has its own Node assumptions. Only `main.js` and
  `preload.js` import Node modules, which is not the same as the renderer being
  free of them — `innerHTML` was the largest mechanical change in the Dev OS
  port (`docs/DEV_OS_PORT_PLAN.md` §5) and Leaf is a DOM editor, so it will have
  more of that, not less.
- Leaf's own tests and QA scripts are Node and Electron. What replaces them in a
  module is not addressed here.
