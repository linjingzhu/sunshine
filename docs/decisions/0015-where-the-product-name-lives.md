---
doc_id: adr-0015-where-the-product-name-lives
version: 1.0.0
canonical_path: docs/decisions/0015-where-the-product-name-lives.md
updated: 2026-08-19
---

# ADR 0015: Where the product name lives, and what was left saying Chromium

## Status

**Accepted, and implemented by**
`downstream/patches/0009-sunshine-windows-install-identity.patch` and
`downstream/patches/0010-sunshine-product-strings.patch`. Read against the
pinned revision `152.0.7977.42`. **Not built.** §6 says what that leaves open.

## Context

Patch 0001 has renamed `chrome/app/theme/chromium/BRANDING` since the first
week: `PRODUCT_FULLNAME=Sunshine OS`, and the version resource in the built
`chrome.exe` reads Sunshine. The owner then ran the browser and found it calling
itself Chromium anyway.

Both are true, and the reason is that the product name is not in one place. It
is in three, and `BRANDING` is the smallest of them.

| Where | What it decides | Was |
| --- | --- | --- |
| `chrome/app/theme/chromium/BRANDING` | the VERSIONINFO resource — file properties, the installer's publisher | already Sunshine, since patch 0001 |
| `chrome/install_static/chromium_install_modes.h` | the install directory, the user data directory, the taskbar identity, the entries in Windows' Default Apps | Chromium |
| `chrome/app/chromium_strings.grd` | every string the browser shows the user with its own name in it | Chromium, 527 lines of it |

`BRANDING` is read by the resource compiler. It is not read by the browser, and
it is not read by the installer's own view of where it lives. So renaming it
changed what Explorer's Properties dialog says and nothing the user actually
looks at.

## Decision

### 1. The Windows install identity (patch 0009)

`kProductPathName`, `base_app_name`, `base_app_id`, and the browser and PDF
ProgID prefixes and descriptions become Sunshine.

This is the change that makes the name real on Windows. It also fixes something
nobody had noticed: with `kProductPathName = L"Chromium"`, Sunshine installed
into `%LOCALAPPDATA%\Chromium\Application` and used `%LOCALAPPDATA%\Chromium\
User Data`. **On a machine that also has Chromium, that is the same directory.**
The rename separates them.

### 2. The strings (patch 0010)

527 lines of `chrome/app/chromium_strings.grd`, every one of them the product
name.

**Why the whole file rather than `IDS_PRODUCT_NAME` alone.** Chromium's branding
strings spell the product out rather than substituting it: 518 of the 762
messages carry the literal name in their body. Renaming only the two canonical
messages would have left "Set Chromium as your default browser", "Sign in to
Chromium?", "About &Chromium" and five hundred others.

**What is not renamed, and why it is a phrase rule.** Three phrases name
upstream rather than this product and must survive:

- `Chromium Authors` — the copyright and the company name. Renaming it is not
  branding, it is misattribution.
- `ChromiumOS` — a different product, and one whose renamed form ("SunshineOS")
  would collide with this project's own name for itself.
- `Not used in Chromium` — a note to developers about upstream's build.

The first attempt excluded five *messages*, chosen because their ids looked
like attribution. `scripts/verify_branding_substitution.py` rejected the result:
`ChromiumOS` and the developer note appear in dozens of messages whose ids look
like nothing in particular. **The rule is a property of the text, not of a list
of identifiers**, and the guard is what established that — before the build, not
after.

### 3. The direct-launch scheme: neither name

`direct_launch_url_scheme` was the one constant with no good rename. Setting it
to `"sunshine"` registers a `sunshine:` URL protocol with Windows —
`docs/decisions/0003-internal-scheme.md` settled that Sunshine registers no
scheme of its own, SEC-13 states it, and `scripts/verify_installed_build.py`
checks `HKCR\sunshine` on the machine for exactly this. Leaving it as
`"chromium"` means claiming a protocol named after upstream.

**Upstream supports a third answer, and it is the right one here.** The value
is set to the empty string. `chrome/install_static/install_modes_unittest.cc`
states the contract in as many words — *"Every mode must specify a direct launch
URL scheme; empty string is okay"* — and two shipped modes already use it:
Google Chrome's secondary install modes and Chrome for Testing.
`chrome/installer/setup/uninstall.cc` shows what it means, guarding its
`Software\Classes\<scheme>` cleanup with a non-empty check: **an empty value
means no scheme is registered at all.**

So Sunshine registers nothing, which is what ADR 0003 requires, rather than
choosing between a forbidden name and a borrowed one. This was found because
the owner asked for *every* name to be Sunshine; the honest answer to that
question turned out to be "this one is not a name, it is a registration, and
Sunshine makes none".

**`kSafeBrowsingName` is now `"sunshine"`.** It identifies the client to
Google's Safe Browsing service, and ADR 0005 records that no API key is
configured, so it is never sent. That makes the change free — and it means that
if a key is ever configured, the browser introduces itself as what it is rather
than as upstream.

The Active Setup GUID and the toast activator CLSID are unchanged, so they still
collide with a real Chromium install. With the install directories now separate
that collision is narrow — Active Setup and toast activation — and inventing
GUIDs is a change this ADR does not need to make.

**What is left saying Chromium in that file** is its copyright header, its
comments, and the `CHROMIUM_INDEX` enumerator, which
`chrome/installer/util/prebuild/create_string_rc` requires to stay in sync with
upstream's own indices. None of those is a name anyone sees; renaming an
enumerator would be renaming code.

## Consequences

- The stack owns 16 upstream files, up from 14. `chromium_strings.grd` is the
  most churn-prone file it has ever owned: a release that adds one branded
  string adds a conflict.
- That cost is bounded by the guard rather than by care.
  `verify_branding_substitution.py` proves the patch is the rename and nothing
  else, from the patch alone and offline, so regenerating it after a rebase is
  mechanical: `verify_branding_substitution.rename()` is the single definition
  of the rule, and the same function checks the result.
- A user upgrading from an earlier Sunshine build gets a **new profile**: the
  user data directory moved from `%LOCALAPPDATA%\Chromium\User Data` to
  `%LOCALAPPDATA%\Sunshine\User Data`. Nothing migrates it. For a browser with
  one user and no released version this is the right time to pay that, and it
  is the last time it is free.

## NOT VERIFIED

- **Both patches compile.** Build #33 (commit `ca1f5c0`) is the first native
  build containing them, and `verify_installed_build.py` passed on its
  artifact. That decides nothing about what a person sees: RV-26 to RV-30 need
  the installer run, and this build produced the first installer that has the
  rename in it. What follows was written before that build and is otherwise
  unchanged.

  Both patches apply cleanly to a fresh
  checkout of the pinned revision — that was run — but `git apply` does not
  tell you that grit still parses the grd, or that the installer places files
  where the new constants say.
- Whether the browser now *calls itself* Sunshine is RV-26 and RV-27, and both
  are NOT RUN. The guard proves the patch says Sunshine; only running the
  browser proves the browser does.
- No claim is made about the macOS or Linux name. `MAC_BUNDLE_ID` was set by
  patch 0001 and neither platform is built here.
- **The binaries keep upstream's file names.** `chrome.exe`, `chrome.dll`,
  `chrome_elf.dll` and `chrome_proxy.exe` are unchanged, and `chrome` is the
  codebase's name for them rather than a brand — Google Chrome ships
  `chrome.exe` too. Renaming them reaches GN output names, the mini_installer
  archive, the DLL that `chrome_elf` is loaded by name, and the constants in
  `chrome/common/chrome_constants.cc`; it is a large change with a real chance
  of a broken link, and the names appear only in Task Manager and the install
  folder. Recorded as a decision, not an oversight.
