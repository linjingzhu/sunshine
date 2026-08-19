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

### 3. What deliberately still says Chromium

Two constants in `chrome/install_static/chromium_install_modes.h` were left
alone on purpose.

**`direct_launch_url_scheme = "chromium"`.** Renaming this to `"sunshine"`
would register a `sunshine:` URL protocol with Windows —
`docs/decisions/0003-internal-scheme.md` settled that Sunshine registers no
scheme of its own, SEC-13 states it, and `scripts/verify_installed_build.py`
checks `HKCR\sunshine` on the machine for exactly this. The rename would have
turned a green check red, and the check would have been right. Leaving it means
Sunshine claims a scheme named after upstream, which is its own small
dishonesty; both are recorded rather than one being quietly preferred.

**`kSafeBrowsingName = "chromium"`.** This identifies the client to Google's
Safe Browsing service. ADR 0005 records that no API key is configured, so the
browser never reaches that service and the string is never sent. Renaming it
would be a change with no observable effect and a non-zero chance of one.

The Active Setup GUID and the toast activator CLSID are also unchanged, so they
still collide with a real Chromium install. With the install directories now
separate, that collision is narrow — Active Setup and toast activation — and
inventing GUIDs is a change this ADR does not need to make to answer the
question it was opened for.

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

- **Nothing here has been built.** Both patches apply cleanly to a fresh
  checkout of the pinned revision — that was run — but `git apply` does not
  tell you that grit still parses the grd, or that the installer places files
  where the new constants say.
- Whether the browser now *calls itself* Sunshine is RV-26 and RV-27, and both
  are NOT RUN. The guard proves the patch says Sunshine; only running the
  browser proves the browser does.
- No claim is made about the macOS or Linux name. `MAC_BUNDLE_ID` was set by
  patch 0001 and neither platform is built here.
