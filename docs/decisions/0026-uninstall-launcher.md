---
doc_id: adr-0026-uninstall-launcher
version: 1.0.0
canonical_path: docs/decisions/0026-uninstall-launcher.md
updated: 2026-09-13
---

# ADR 0026: An uninstall launcher, which is almost entirely a decision not to build an uninstaller

## Status

**Accepted, and implemented by `installer/sunshine_uninstall.cpp`.** No patch:
the front-end binaries are outside Chromium's build graph (IU-1). Read against
the pinned revision `152.0.7977.42`. §6 says what is unverified.

## Context

The owner asked for an uninstall file.

**The first honest answer is that uninstalling already worked.**
`chrome/installer/setup/install_worker.cc` writes `DisplayName`,
`UninstallString` and `InstallLocation` into
`Software\Microsoft\Windows\CurrentVersion\Uninstall\Sunshine` in the 32-bit
view at install time, and Settings → Apps has been able to remove Sunshine
since the first install. `docs/INSTALLER_UI_CONTRACT.md` §6 said so —
"Not an uninstaller … Programs and Features points at upstream's own code".

What did not exist was **a file a person could double-click**. That is a real
gap and a small one, and the mistake available here was to answer it with a
program that reimplements removal.

## Decision

**Ship `sunshine-uninstall.exe`: a locator and launcher.** It reads
`UninstallString`, runs it, waits, and returns what upstream returned.

Nearly every other decision in it is a decision *not* to do something, and each
is forced by reading upstream rather than by taste.

### It draws no dialog

`chrome/installer/setup/uninstall.cc`'s `IsChromeActiveOrUserCancelled()`
launches `chrome.exe --uninstall` and reads back
`UNINSTALL_CHROME_ALIVE`, `UNINSTALL_USER_CANCEL` and
`UNINSTALL_DELETE_PROFILE`. That is a confirmation dialog, a running-browser
check and a profile-deletion choice — all upstream's, all already right, all
already translated. A dialog of ours would stand in front of that one asking a
worse version of the same question. The `.rc` declares no `DIALOGEX` at all and
the guard refuses one.

### It does not offer `--delete-profile`

The switch exists and appending it would be one line. The browser's own dialog
offers the same choice at the moment the person is deciding. Taking it earlier
would mean asking about profile data before the user has confirmed they want to
uninstall at all.

### It does not rebuild the command line

`CommandLineToArgvW` returns an argument vector, and running one means
re-quoting it — a lossy round trip through the exact syntax that must not
change. The string is split once at the program name; the remainder is passed
on as found.

## The security decision, which is the only part that could be a vulnerability

**UN-3: a command read from `HKEY_CURRENT_USER` is never run elevated.**

The per-user registration lives in a hive the unprivileged user owns. A
launcher that read a command line from there and ran it under `runas` would be
a local privilege escalation shipped with an icon and a friendly name: write
your own `UninstallString`, double-click, consent to the prompt you were
expecting anyway, and your command runs as administrator.

So the hive decides the verb. `runas` is used only for the per-machine
installation, whose command came from `HKEY_LOCAL_MACHINE` — a key an
unprivileged user cannot write. The manifest requests `asInvoker`.

**The guard checks this structurally rather than by inspection.** It requires
that `runas` appear only inside a conditional, and that the flag the
conditional tests is never assigned a bare `true`. The second half matters more
than it looks: a version where the conditional is intact and the flag is forced
would read correctly — it still names both hives, it still branches — and would
still elevate everything. A test injects exactly that.

## Consequences

- One more binary beside `sunshine-setup.exe`, about 100 KB rather than 118 MB:
  it embeds no engine.
- `docs/INSTALLER_UI_CONTRACT.md` §6 is amended rather than contradicted. It
  still says this is not an uninstaller, because it is not one.
- **It found a live regression in an existing guard.** IU-17's rule asked
  whether *any* `cl.exe` line in the build script carried `/MT`. That held
  while there was one such line; adding a second meant the setup front-end
  could have lost the flag with the check still green — reintroducing build
  #55's silent failure through a change unrelated to it. The check now reads
  one named invocation. `test_the_guard_refuses_the_line_that_shipped_build_55`
  caught it, because it injects the defect instead of asserting a pass.
- The road not taken is a Start menu shortcut created at install time. That
  needs a patch to upstream's `install_worker.cc` — an upstream file the stack
  would then own exclusively, for a shortcut.

## 6. NOT VERIFIED

**Nothing here has been run. It needs build #59 and a person.**

- **That it finds a real installation.** The registry reads are written against
  the values `install_worker.cc` writes, but no one has run this against a
  machine with Sunshine on it — **RV-62**.
- **That `runas` actually elevates and the uninstall completes.** RV-63, and it
  is the per-machine half that UN-3 exists for.
- **That a refused UAC prompt is quiet.** `ERROR_CANCELLED` is handled as "not
  a failure", the same reading IU-12 takes, and that has not been observed.
- **What it does with both a per-user and a per-machine Sunshine installed.**
  It takes the per-user one. That is a judgement, not a verified behaviour.
- That `sunshine-uninstall.exe` starts at all on a machine with no compiler.
  It is compiled `/MT` for the same reason the setup front-end is, and IU-17's
  history is that this failure is invisible until someone double-clicks —
  **RV-62 is also that check**.
