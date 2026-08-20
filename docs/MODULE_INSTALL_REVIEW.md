# Installing a module from a file — review of the proposed method

## 0. Status

A review, not a decision and not work. The owner proposed a method; this says
whether it can be built, what it costs, and what has to be decided before
anything is written. §6 is the recommendation and §7 is what is not verified.

The proposal, as given:

1. The Register button opens a dialog to find a module zip.
2. Selecting the zip installs the module into Sunshine.
3. Files the module handles are stored under Sunshine's document store, in a
   per-module directory.
4. That store lives on cloud or NAS so several devices can reach it.
5. **The point:** the user selects the zip and installation happens.

## 1. The verdict, up front

**It is buildable, and it is far closer to done than it looks — because
Chromium already ships the mechanism.** At the pinned revision `152.0.7977.42`
this project builds against, Chromium has Isolated Web Apps: an application
delivered as a **signed web bundle**, installed from a file, running at its own
origin with its own storage partition, where the origin is *derived from the
signing key*. That is the proposal, already implemented, by the upstream this
project is a downstream of.

Verified by reading the pinned tree rather than from memory:

| File at `152.0.7977.42` | What it establishes |
| --- | --- |
| `chrome/browser/web_applications/isolated_web_apps/isolated_web_app_url_info.h` | An IWA's origin is derived from a signed web bundle ID, and the ID comes from the bundle's own integrity block. |
| `components/web_package/signed_web_bundles/signed_web_bundle_id.h` | Signed bundle identity exists as a first-class type. |
| `components/web_package/web_bundle_parser.h` | The bundle format is parsed by Chromium, not by us. |
| `components/webapps/isolated_web_apps/types/source.h` | An install source is a **bundle file** or a dev-mode proxy; production mode is bundle-only. |
| `chrome/browser/web_applications/isolated_web_apps/isolated_web_app_features.h` | `IsIwaUnmanagedInstallEnabled()` — user-initiated installation, behind a feature flag plus an enterprise policy that **defaults to true**. |
| `ui/shell_dialogs/select_file_dialog.h` | The file dialog in step 1 is Chromium's, in the browser process. |

**One thing in the proposal cannot be done as stated.** An installed bundle can
carry HTML, CSS, JavaScript and assets. It cannot carry native code: loading
C++ at run time is loading a DLL, which ends the sandbox and the code-signing
story in one step. So installation gives you **web modules**, and anything that
needs a Mojo interface or a C++ model stays compiled in.

That is not a compromise so much as the shape browsers already have: built-in
surfaces and installed applications, two tiers, different powers.

## 2. Step by step

### Step 1 — the file dialog

Buildable, no new decision. `ui::SelectFileDialog` runs in the browser process
and the page asks for it through Mojo. `docs/FILE_BROKER_CONTRACT.md` already
describes this exact shape: the user picks, the browser holds the handle, the
page never receives a path. FB-9 — declaring the capability is not holding it.

### Step 2 — selecting the file installs the module

**The zip should be a signed web bundle, and that makes the feature stronger
rather than more troublesome.**

- The origin is derived from the signing key, so **a module's identity is its
  key**. A tampered bundle does not install. A second bundle cannot impersonate
  the first. Version two of a module is provably the same author as version
  one.
- Chromium performs the isolation. Sunshine writes none of it — and writing
  your own isolation is precisely where a downstream gets this wrong.
- Storage is partitioned per app by construction, which step 3 wants anyway.

The cost is that modules must be signed. For a first-party set that is **one
key, generated once**, held off the browser. It is a smaller cost than any of
the alternatives to it.

**This is the rule that changes.** `docs/decisions/0006-module-execution-model.md`
says a module is compiled in; `docs/decisions/0016-relaxations-for-porting.md`
§5 kept that with a one-line argument — *loadable modules are a supply chain,
and a supply chain is an outside.* The argument was right and it is answered
rather than overruled: a signed bundle, carrying no native code, running in
Chromium's isolation, declaring its authority before it is admitted, is a
supply chain with a signature on it. What ADR 0016 refused was an unsigned,
unbounded one.

So ADR 0006 gains a second kind of module rather than losing its rule:

| | Built-in module | Installed module |
| --- | --- | --- |
| Delivery | Compiled into the binary | Signed bundle, installed from a file |
| May contain native code | Yes | **No** |
| Reaches the browser through | A Mojo interface it declares | The mount port, and nothing else |
| Identity | The registry | Its signing key |
| Changing it needs | A build | A new bundle |

### Step 3 — a per-module directory in the document store

Right, with one correction about who enforces it.

**The module must not name the directory.** It says `write(key, bytes)` and the
browser maps that to `<store>/<module-id>/<key>`. The module never receives a
path, never learns where the store is, and cannot reach another module's
directory because it never names one. `DOC-3`, `DOC-8` and `MA-2` all survive
unchanged, and the per-module boundary is a property of the broker rather than
a rule modules are asked to respect.

**An installed module cannot be given a Sunshine Mojo interface.** A Mojo
interface is bound to a WebUI controller; an installed app is not one. So the
route is the one this project just built: **the module speaks the mount port to
the shell, and the shell — a `chrome://` page with a Mojo interface — performs
storage on its behalf.**

`docs/MODULE_MOUNT_CONTRACT.md` therefore gains a storage vocabulary, and that
is the single largest piece of work in the whole proposal. It is also the piece
that makes installed modules safe: they get data in and data out, and never a
capability, which is the sentence the port was designed around.

### Step 4 — cloud or NAS

**Decide the on-disk format before deciding the service, because the format
cannot be changed later without a migration.**

The rule: **one file per document, and no single database file on a synced or
network volume.** SQLite's own documentation is explicit that its locking is
unreliable over SMB and NFS, and the failure mode is not a lost write, it is a
corrupted database. This reverses, for the *shared* store, the `//sql`
suggestion in `docs/MARKETPICK_PORT_PLAN.md` and `docs/FIRST_MODULE_GUIDE.md`;
profile-local state can still be SQLite, because the profile is not synced.

Each document then carries its own `updated_at`, and two devices editing the
same one is resolved as last-writer-wins **with the loser kept as a visible
conflict copy**. Silent loss is the one outcome that must not be possible.

With that settled, the service:

| | What it is | For | Against |
| --- | --- | --- | --- |
| **A. A folder an existing sync client owns** — OneDrive, Google Drive, Dropbox, iCloud Drive, or a mounted NAS share | Sunshine writes ordinary files; something else syncs them | **No new code at all.** Works today, on every platform, and the owner already has one running. A NAS is reached the same way, as a mounted share | Conflicts get the sync client's semantics, which means a "conflicted copy" file rather than anything Sunshine controls. Latency is the client's |
| **B. WebDAV to the NAS** — Synology and QNAP both ship it | Sunshine speaks HTTP to the NAS | No client software, per-file granularity, works from outside the LAN, and the protocol is standard | Needs a credential, so it is blocked on the broker ADR 0011 shapes and has not been built. Needs a host allowlist, which `docs/HOST_ALLOWLIST_CONTRACT.md` now permits |
| **C. A git repository** — Gitea on the NAS, or GitHub | Documents are commits | History and conflict resolution are the *point* of it, not an afterthought. Multi-device is its native case | Bad for large binaries. Not real-time. Needs a credential, same block as B |
| **D. Sunshine's own sync service** | A server this project runs | Full control | **Rejected.** It is a product, not a feature, and it puts this project in the business of operating a server and holding other people's documents |

**Recommendation: A now, B when the credential broker exists, C for anything
worth a history.** A is available today and costs nothing; the format rule
above is what makes it safe, and it is also what lets B and C be adopted later
without a migration.

### Step 5 — the user only selects the file

Almost. **Selection should be the only thing the user *does*, and there should
still be one screen before it takes effect.**

Not friction, and not a confirmation dialog for its own sake: the screen shows
what the bundle *declares* — which hosts it may reach, whether it wants
storage, what it will be called. Installing a signed bundle without ever
showing what it asked for is a delivery mechanism for anything, and the module
home already exists to display exactly this. It is one click, and it is the
difference between a module system and an attack surface.

Everything else — unpacking, verification, origin derivation, registration,
appearing in the dock — happens without the user doing anything. That is the
part of item 5 that matters and it is achievable in full.

## 3. What it costs in rules

| Rule | What happens |
| --- | --- |
| ADR 0006, modules are compiled in | **Amended.** Two kinds, per §2. The compiled kind is unchanged. |
| ADR 0016 §5, loadable modules are a supply chain | **Revisited, and answered rather than overruled.** Signature, no native code, declared authority, Chromium's isolation. |
| `MM-1`, a mount is `chrome-untrusted://<host>/` | **Widened** to admit the installed origin. The shape check stays; it gains a second shape. |
| The mount port | **Extended** with a storage vocabulary. The largest piece of work. |
| `MH-1`, the module home mutates nothing | **Keep it.** Install belongs to the shell's dock, which is where the Register control already is. The module home keeps reporting. |
| `MH-3`, the served registry is byte-identical to `first_party/` | **Breaks.** Once modules can be installed, the list is compiled *plus* installed. This needs its own answer and it is not a small one. |
| `SEC-13`, Sunshine registers no scheme | **Survives.** The installed origin is Chromium's, not ours. |
| `SEC-14`, no remote resource | **Survives.** A bundle is a local file. |
| `SEC-8`, filesystem access | The store folder is one user-chosen grant, which is `docs/FILE_BROKER_CONTRACT.md`'s shape exactly. |

## 4. The risks, in the order they should be resolved

1. **Can an installed app's document be framed by `chrome://sunshine-shell`?**
   Isolated Web Apps are strictly isolated and their framing policy has not
   been read. **If they cannot be embedded, the shell cannot mount them**, and
   the five-region model in `docs/MODULE_SHELL_CONTRACT.md` has to be rethought
   for installed modules — or Sunshine patches the policy, which spends exactly
   the guarantee it just bought. This decides the design and it is one
   afternoon's reading. **Do it first.**
2. **The feature and policy gating.** `IsIwaUnmanagedInstallEnabled()` is a
   flag plus a policy. Sunshine is its own build, so it can set its own
   defaults — but that is a patch to write and a decision to record.
3. **Update and uninstall are not in the proposal.** A thing that installs must
   also be removable and replaceable, and the version story is where install
   systems rot. Design it with install, not after.
4. **Key management.** Who signs, where the key lives, and what happens when it
   is lost. Not a browser problem, but a project problem, and it becomes urgent
   the first time a module ships.
5. **Conflicts.** §4's rule handles the mechanism; someone still has to decide
   what the user *sees* when two devices disagree.

## 5. What this is not

It is not a small feature. A rough shape of the phases, in dependency order and
without an estimate, because nobody has measured any of them:

1. Read the framing policy — risk 1. Everything below depends on the answer.
2. The store: the format rule from §4, a per-module namespace, and the
   file-picker grant for where it lives.
3. The mount port's storage vocabulary.
4. Install: the dialog, the bundle, the declaration screen, registration.
5. Uninstall, update, and the module home's answer to `MH-3`.

Phase 2 is worth doing whatever is decided about the rest — a compiled-in
module needs the same store, and a store that syncs is useful the day it exists.

## 6. Recommendation

**Build it, on Chromium's mechanism rather than beside it, and take the risks
in the order above.**

The proposal is right about the thing that matters: a module system nobody can
add a module to is not a module system, and the owner is describing the product
rather than a shortcut. What the review changes is three things — the bundle is
signed rather than a plain zip, installed modules are web-only, and the store's
format is decided before the service is.

The two-tier model that falls out is better than either tier alone. Marketpick
and Dev OS, which need C++ and Mojo, stay compiled in. An HTML collection, and
most of what comes after it, installs from a file.

## 7. NOT VERIFIED

- **Nothing here has been built or tried.** The Chromium facts in §1 were read
  from the pinned tree at `152.0.7977.42` today; everything about how Sunshine
  would use them is reasoning.
- **The framing question in §4 risk 1 is open and is the important one.** No
  file was read on it. A design committed before that answer is a design that
  may have to be discarded.
- No measurement supports §5's phases. They are an order, not a schedule.
- The sync options in §4 are assessed from their documented behaviour, not from
  running Sunshine against any of them. In particular, no NAS was tested, and
  the SQLite-over-network-share caveat is upstream's own statement rather than
  something reproduced here.
- Whether `IsIwaUnmanagedInstallEnabled()` can be defaulted on in a downstream
  build without other consequences has not been checked.
