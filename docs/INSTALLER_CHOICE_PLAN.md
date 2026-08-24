# User-chosen install location and executable name — Plan

## Status and scope

Applies to Sunshine OS on the pinned Chromium revision `152.0.7977.42`.

The owner has decided that the installer must let a person **choose the install
folder and the executable's name**, so that what is installed and where is
explicit rather than implied. This document is what that costs, read out of the
pinned source rather than estimated.

`docs/INSTALLER_UI_CONTRACT.md` is the contract this changes. Two of the six
decisions recorded at its head are reversed by the request:

| Decision as recorded | What is now required |
| --- | --- |
| Path — **shown, never typed** | typed |
| Name — **fixed at `Sunshine`, no control changes it** | chosen |

**Nothing here is built.** §6 is what the owner still has to decide, and §7 is
what has not been verified.

## 1. A correction to what was reported first

It was first reported that upstream supports neither. That was read off the
switch table in `chrome/installer/util/util_constants.cc`, which is complete
and which contains no install-directory switch — and it was **incomplete as an
answer**, because the switch table is not the only channel into `setup.exe`.

**Initial preferences carry an install directory.** `initial_preferences_constants.h`
declares `program_files_dir`, and `chrome/installer/util/helper.cc` reads it:

```cpp
install_path = GetCurrentInstallPathFromRegistry(system_install);
if (install_path.empty())
  install_path = GetInstallationDirFromPrefs(prefs, system_install);
if (install_path.empty())
  install_path = GetDefaultChromeInstallPathChecked(system_install);
```

So the plumbing from a preference file to the install target **already exists,
end to end.** That is a materially different starting position from "no
mechanism", and the earlier answer should not have been given from one file.

## 2. What that preference actually permits

Less than its name suggests. `GetInstallationDirFromPrefs` validates the value
against exactly two paths:

```cpp
base::FilePath expected_dir;
bool valid_program_files_path =
    (compare-equal-ignore-case with DIR_PROGRAM_FILES) ||
    (compare-equal-ignore-case with DIR_PROGRAM_FILESX86);

return valid_program_files_path
    ? expected_dir.Append(install_static::GetChromeInstallSubDirectory())
                  .Append(installer::kInstallBinaryDir)
    : base::FilePath();
```

Three consequences:

- **Only two values are accepted** — `%ProgramFiles%` and `%ProgramFiles(x86)%`.
  Anything else returns empty and silently falls back to the default.
- **Only on a system install.** The function returns early unless
  `system_install`; a per-user install ignores the preference entirely.
- **Only the root is chosen.** `<Company>\<Product><suffix>\Application` is
  appended regardless, from constants compiled into the binary.

The header says the same in one line: *"This property will only be applied on
fresh system installs."*

So this exists to pick a bitness, not a folder.

## 3. The folder — a small patch, and a real reason it is guarded

**The change is one function.** Relaxing the validation in
`GetInstallationDirFromPrefs` so an arbitrary directory is accepted makes the
existing pipeline do the rest. Sunshine would own one upstream file it does not
own today.

**But the validation is not arbitrary, and removing it removes a guarantee.**
A per-machine install writes a binary that every account on the machine runs.
Restricting the target to `%ProgramFiles%` restricts it to a directory
unprivileged users cannot write. **Install to a user-writable folder for all
users, and any unprivileged account can replace the executable that every other
account launches.** That is a privilege-escalation primitive, not an
inconvenience.

So a relaxed check needs a replacement guarantee, not a deletion:

| For | Requirement |
| --- | --- |
| Per-machine install | The chosen directory must be verified **not writable by unprivileged users**, at the moment of install, after elevation. A directory that fails is refused with the reason shown. |
| Per-user install | No hook exists at all — the preference is ignored unless `system_install`. Reaching it needs a second, separate change. |

The per-user case is the one a person is most likely to exercise and the one
with the least upstream support.

## 4. The executable name — not a small patch

`chrome.exe` is not a value. It is a compile-time constant with a family around
it, in `util_constants.cc`:

```cpp
const wchar_t kChromeExe[]           = L"chrome.exe";
const wchar_t kChromeNewExe[]        = L"new_chrome.exe";
const wchar_t kChromeOldExe[]        = L"old_chrome.exe";
const wchar_t kChromeProxyExe[]      = L"chrome_proxy.exe";
const wchar_t kChromeProxyNewExe[]   = L"new_chrome_proxy.exe";
const wchar_t kChromeProxyOldExe[]   = L"old_chrome_proxy.exe";
const wchar_t kActiveSetupExe[]      = L"chrmstp.exe";
```

Making the first of those a runtime value chosen per install reaches:

| Reached | Why |
| --- | --- |
| **The update swap** | An update installs `new_chrome.exe` and renames it over `chrome.exe`. Both names are literals; a renamed install updates into a file nobody launches. |
| **The proxy trio** | `chrome_proxy.exe` carries the same three-name swap and is what shortcuts and default-browser registration point at. |
| **Shortcut creation, ProgID, default-browser registration** | Every one records a path ending in the executable's name. |
| **`install_static`** | A deliberately tiny, dependency-light library read during earliest startup and by the crash handler, whose whole design is that brand identity is a compile-time constant. |
| **Active Setup** | `chrmstp.exe`, run per user on first sign-in. |

**None of this is impossible. All of it is Sunshine's to maintain afterwards.**
Each upstream roll re-applies these edits against code that assumes the
constants it was written with.

**And the identity question is separate from the naming question.** The install
directory, the registry path and the policy path all derive from
`kCompanyPathName` and `kProductPathName` through `AppendChromeInstallSubDirectory`,
compiled in — including a `if constexpr (*kCompanyPathName)` branch, which is
identity resolved by the *compiler*. Two installs that differ only in a
user-typed executable name still share one registry identity, so the second
install is not a second install: it is the first one, found and updated in
place.

## 5. What this costs the contract

| Invariant | Effect |
| --- | --- |
| **IU-1** — front-end owns zero upstream files | **Broken.** At minimum `helper.cc`; for the name, `util_constants.cc` and everything above. |
| **IU-2** — the engine is `mini_installer.exe` as upstream built it | **Broken** for the name. The engine's own constants change. |
| **IU-3** — every choice is a key or switch upstream already defines | **Broken.** `program_files_dir` exists but not with these semantics; no name key exists at all. |
| **IU-4** — location displayed, never accepted as input | **Reversed by decision.** |
| **IU-5** — no control changes the product name or its directory | **Reversed by decision.** |
| **IU-15** — every path to the engine passes through the dialog | Unaffected. |
| **IU-16** — one read about the machine before consent | **At risk.** Validating a chosen directory means reading the filesystem before the user has agreed to anything. Checking writability of a folder they typed is a read they asked for, which is arguably a different thing — but the rule as written admits exactly one read, and this would be a second. |

The structural sentence at the head of the contract — *"the front-end asks
questions and phrases a request; it does not install anything"* — survives the
folder change and does not survive the name change. Once Sunshine's own
constants decide what the engine writes, the front-end is no longer only asking.

## 6. What the owner still has to decide

1. **Per-user installs.** The upstream hook is system-install only. Is a chosen
   folder required for per-user too, or is per-machine enough?
2. **Refusing an unsafe folder.** For a per-machine install into a user-writable
   directory: refuse, or warn and proceed? Refusing is the only answer that
   keeps the guarantee the current validation provides.
3. **The name, given §4.** The stated goal is that a person sees clearly what is
   installed. A build-time rename to `sunshine.exe` delivers that for every
   install, costs one branding change rather than a maintained fork of the
   update path, and cannot be typed wrong. A user-typed name delivers the same
   clarity only to the person who typed it, and only until the first update.
   **This is the one place where what was asked for and what was wanted may come
   apart**, and it is the owner's to settle.
4. **Roll cost.** `scripts/measure_rebase_cost.py` exists and has never been run
   against these files. It should be, before the name work starts rather than
   after.

## 7. NOT VERIFIED

- **Nothing is built, and nothing has been compiled.** Every claim here is read
  from the pinned source.
- **The relaxed-validation patch has not been written or applied**, so "one
  function" is a reading of `helper.cc`, not a measured diff.
- **The blast radius in §4 is enumerated from constant declarations and their
  documented roles, not from call-site analysis.** The true set of places that
  assume `chrome.exe` is a literal is at least the list given and may be larger.
- **No per-user hook has been looked for beyond `GetInstallationDirFromPrefs`.**
  There may be another route; none was found in `helper.cc`.
- **The privilege-escalation reasoning in §3 is architectural, not
  demonstrated.** No exploit was constructed and none is needed to justify
  keeping the guarantee.
