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

## 3a. Risk 1, resolved: Sunshine should install bundles, not Isolated Web Apps

The first risk this review named was whether an installed app's document can be
framed by `chrome://sunshine-shell`. It was read, and the answer changes §2 for
the better.

**An Isolated Web App is placed in its own StoragePartition.**
`chrome/browser/web_applications/isolated_web_apps/isolated_web_app_url_info.h`
declares `storage_partition_config()` for the app and
`GetStoragePartitionConfigForControlledFrame()` for what an IWA embeds. The
embedding direction the API offers is **an IWA embedding others**, through a
guest view, and a plain iframe does not cross a partition boundary. So the
shell almost certainly cannot mount an IWA with an `<iframe>`, and making it do
so would mean guest views in a `chrome://` page — more machinery, and a second
mounting mechanism beside the one that already works.

**The good news is that the format and the guarantee are separable from the
hosting.** `//components/web_package` is a standalone component and it has
everything the attractive half of §2 needs, all present at `152.0.7977.42`:

| File | What it gives |
| --- | --- |
| `components/web_package/web_bundle_parser.h` | The bundle format, parsed by Chromium |
| `components/web_package/signed_web_bundles/integrity_block_parser.h` | The signature block |
| `components/web_package/signed_web_bundles/signed_web_bundle_signature_verifier.h` | **Verification. No cryptography is written here.** |
| `components/web_package/signed_web_bundles/ed25519_public_key.h` | The key type |
| `components/web_package/signed_web_bundles/signed_web_bundle_id.h` | The id derived from the key |
| `components/web_package/web_bundle_builder.h` | Building one, for the signing tool |

So the revised shape:

- the file is a **signed web bundle**, the same format, signed the same way;
- Sunshine verifies it with `//components/web_package`;
- the module is served at **`chrome-untrusted://<bundle-id>/`**, so the origin
  is still derived from the signing key — Sunshine deriving it rather than the
  browser, in one place a guard can read;
- serving is a Sunshine `URLDataSource` over the verified bundle;
- **the shell mounts it with a plain iframe, through the mount port that
  already exists**, under the framing policy
  `downstream/patches/0015-sunshine-shell-frame-policy.patch` added — which
  already derives the allowed origins from what shipped, and would derive them
  from the installed set the same way.

A detail that decides a name: `MM-1` allows a host of at most 63 characters and
a signed bundle id is 56, so the host is **the bundle id itself**, not a
readable name with the id appended. That is the right outcome rather than a
constraint to work around: a readable host would be a name the module chose,
and the id is a name its key chose.

**What is given up against a real IWA**, stated plainly:

- the dedicated StoragePartition. Installed modules would share the profile's
  partition with the shell, each with its own origin and therefore its own
  storage — weaker than an IWA, and exactly what the document surface already
  does;
- the browser enforcing the origin-to-key binding. Sunshine enforces it
  instead. That is a real transfer of responsibility and it is the one thing in
  this revision worth arguing about.

**What is gained:** the shell can actually mount them; there is one mounting
mechanism rather than two; and none of it depends on the IWA feature flag or
the enterprise policy in §1.

## 3b. The investigation ADR 0006 asked for, done

`docs/decisions/0006-module-execution-model.md` § *Revisiting* names one thing
to settle before Position B is reconsidered, on the grounds that it "may make
the question smaller":

> **can a WebUI host serve bundled resources without a registered scheme?** If
> it can, B costs an amendment to `.ai/PROJECT_CONTEXT.md` and a rescoping of
> `verify_architecture.py`, but leaves ADR 0003 untouched.

**It can, and Sunshine has already done both halves of it.** Read at
`152.0.7977.42`, and then found again in this repository's own patch stack.

### Half one — a host that is a runtime string

| Read | What it establishes |
| --- | --- |
| `content/public/browser/webui_config.h` | `WebUIConfig(std::string_view scheme, std::string_view host)`. The host is a **constructor argument**, not a compile-time constant, and `CreateWebUIController(web_ui, url)` receives the URL. |
| `content/public/browser/webui_config_map.h` | `AddUntrustedWebUIConfig()` is an instance method on a singleton, keyed by `url::Origin`, with a matching `RemoveConfig(url)`. Registration is one call per origin and it is reversible. |
| `downstream/patches/0006-sunshine-document-webui.patch` | Sunshine already calls it: `map.AddUntrustedWebUIConfig(std::make_unique<SunshineDocumentContentUIConfig>())`, and the patch's own comment records that a `chrome-untrusted://` surface "costs no fifth upstream file and no second registration point". |

**No scheme is registered anywhere in that.** `chrome-untrusted://` is
Chromium's, already there, and ADR 0003's "no `sunshine://` scheme" is untouched
— which is exactly the outcome ADR 0006 hoped for.

### Half two — bytes decided at request time

`WebUIDataSource` serves compiled-in grit resources, which is not what a bundle
needs. `URLDataSource` is the other one:

| Read | What it establishes |
| --- | --- |
| `content/public/browser/url_data_source.h` | `GetSource()` returns a runtime string; `StartDataRequest(url, …, GotDataCallback)` answers with `base::RefCountedMemory` **computed when the request arrives**; `URLDataSource::Add(browser_context, source)` attaches it per profile. |
| `downstream/patches/0021-sunshine-newtab-background-source.patch` | Sunshine already does this too — `UntrustedSource::StartDataRequest` gains a branch that reads a file off disk, off the UI thread, and answers with its bytes. |

### Half three, which was not asked about but decides whether it is usable

A `chrome-untrusted://` page defaults to `frame-ancestors 'none'` and would
refuse the shell's iframe outright. `downstream/patches/0006` already solves it:
`source->AddFrameAncestor(GURL(chrome::kChromeUISunshineDocumentURL))`, and its
comment records that `WebUIDataSourceImpl::AddFrameAncestor()` CHECKs the
argument is a `chrome://` or `chrome-untrusted://` origin, "so this cannot be
widened to a website by mistake."

### What this does and does not settle

**Settled:** the mechanism ADR 0006 asked about exists, needs no scheme, and is
in use in this repository twice over. The question is smaller than it was, in
the specific way ADR 0006 predicted.

**Not settled, and this is the load-bearing gap:** every registration Sunshine
performs today happens at startup, in `RegisterWebUIConfigs`. That
`AddUntrustedWebUIConfig` may be called **after** startup — when a bundle is
installed — is read off the API's shape (a singleton with `Add` and a matching
`Remove`) and from nothing else. No caller doing it late was found, and none was
looked for beyond the files above. **A design that installs modules at runtime
rests entirely on that, and it is an inference.**

Also unread: whether a 56-character bundle id is acceptable to Chromium as a
host — MM-1's 63-character limit is Sunshine's own rule, not Chromium's — and
everything in §7 remains as it was.

## 4. The remaining risks, in the order they should be resolved

1. **Confirm the framing conclusion above against a running browser.** The
   StoragePartition facts were read; that a plain iframe cannot cross a
   partition was reasoned from the shape of the API rather than from the code
   that enforces it. The revision in §3a makes the question moot rather than
   answered — which is a better place to be, but not the same place.
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

- **Nothing here has been built or tried.** The Chromium facts in §1 and §3a
  were read from the pinned tree at `152.0.7977.42`; everything about how
  Sunshine would use them is reasoning.
- **§3a's conclusion rests on one unread step.** That an IWA has its own
  StoragePartition is verified. That a plain iframe cannot host a document in
  another partition is the standard model and is consistent with the API only
  offering the guest-view direction, but the enforcing code was not read.
- No measurement supports §5's phases. They are an order, not a schedule.
- The sync options in §4 are assessed from their documented behaviour, not from
  running Sunshine against any of them. In particular, no NAS was tested, and
  the SQLite-over-network-share caveat is upstream's own statement rather than
  something reproduced here.
- Whether `IsIwaUnmanagedInstallEnabled()` can be defaulted on in a downstream
  build without other consequences has not been checked.
