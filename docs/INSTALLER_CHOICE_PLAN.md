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

**The folder half is built. The name half is not.**
`downstream/patches/0023-sunshine-installer-install-root.patch` relaxes
`GetInstallationDirFromPrefs`, and the front-end carries the root through
elevation, warns after it, and writes `program_files_dir`. §3 records what that
took. §4 — the executable's name — is untouched and is the expensive half.

§6 is the measurement, §7 records the decisions taken, and §9 is what has not
been verified.

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

A relaxed check therefore needs something in place of the guarantee it removes.
**§7 records what the owner chose: a warning rather than a refusal.** The check
still has to exist and still has to run after elevation — a writability test
performed before elevating tests the wrong token — but its outcome is a
sentence, not a stop.

**Per-user installs are out of scope by decision 1**, which is the fortunate
half: the upstream preference is ignored unless `system_install`, so the only
case with no hook at all is the case not being built. What remains is one
validation in `helper.cc`, and §6 measures that file as unchanged across two
milestones.

### Built, and what it actually took

One hunk in `helper.cc`, and it applies at the pin, at `153.0.8000.0` **and at
trunk** — checked by applying it to each. The two properties upstream's version
had that are worth keeping were kept: system installs only, and the caller
chooses the *root* while `<Company>\<Product>\Application` is still appended
from compiled-in constants. What is refused is a relative path and one reaching
through a parent — neither is a folder anyone picked from a browse dialog, and
both are how a string that was not picked arrives.

The front-end side was larger than the patch and none of it was surprising:

| | |
| --- | --- |
| The root crosses elevation as `--install-root=`, quoted | A path in an argument is still an argument. IU-8 forbids the elevated instance learning its choices from a *file*, and the boolean switch table keeps its closed-set property by not being widened to hold a payload. |
| The warning runs from the elevated continuation | The front-end relaunches *itself* elevated, so the one process with a window is also the one with the right token. That is what made §3's requirement satisfiable at all. |
| `UsersCanWrite` asks a narrower question than its name | It reads the directory's DACL and asks whether the built-in **Users** group holds write. It does not evaluate a particular token, follow group nesting, or see a share restriction. It catches the case the owner was warned about — a folder on `C:\` or a data drive — and will miss a bespoke ACL granting write to somebody else. |
| The guard changed shape rather than gaining a rule | `verify_installer_frontend.py` forbade *any* edit control, which was one check standing in for IU-4 and IU-5 together. IU-4 is reversed, so the proxy stopped expressing IU-5. It is now a count and an identity: exactly one box, and it is the install root. |

**The dialog shows the resulting path under the box**, not just the root. The
difference between the two is where every *it installed somewhere else* report
comes from.

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

## 6. Measured: what a roll costs these files

Run against the pin and two later revisions, fetching each file and **checking
the HTTP status before comparing** — the first pass did not, saved a 404 body
as content, and reported an entire file as changed.

| File | at pin | 153.0.8000.0 | main |
| --- | --- | --- | --- |
| `chrome/installer/util/helper.cc` | 225 lines | **unchanged** | **unchanged** |
| `chrome/install_static/install_util.cc` | 995 lines | **unchanged** | **unchanged** |
| `chrome/install_static/install_modes.h` | 72 lines | **unchanged** | **unchanged** |
| `chrome/installer/util/initial_preferences_constants.h` | 90 lines | **unchanged** | **unchanged** |
| `chrome/installer/setup/installer_state.cc` | 193 lines | **unchanged** | **unchanged** |
| `chrome/installer/util/util_constants.cc` | 244 lines | **deleted** | **deleted** |
| `chrome/installer/util/util_constants.h` | 277 lines | 320 lines differ | 320 lines differ |

**The last row said "—" at the pin until 2026-08-30**, which read as a file that
did not exist there. It does: 277 lines, declaring `extern const wchar_t
kChromeExe[]` while the `.cc` beside it defines the value. What happens at 153
is not a new file appearing; it is the definition moving *into* the header:

```cpp
// 152.0.7977.42 -- util_constants.h declares, util_constants.cc defines
extern const wchar_t kChromeExe[];
// 153.0.8000.0 and trunk -- the .cc is gone and the header does both
inline constexpr wchar_t kChromeExe[] = L"chrome.exe";
```

**That direction matters more than the churn does**, and §6a is why.

**The two halves of this request have opposite costs, and the measurement is
what shows it.**

**The folder half is cheap.** Every file it touches — `helper.cc` above all —
is byte-identical at the next milestone and at trunk. A patch against
`GetInstallationDirFromPrefs` applies at the next roll without a person.

**The name half is already broken at the next milestone.**
`chrome/installer/util/util_constants.cc` — the file holding `kChromeExe`,
`kChromeNewExe`, `kChromeOldExe` and the proxy trio, the exact file the name
work must patch — **does not exist at 153.** The constants moved into
`util_constants.h` and changed form:

```cpp
// 152.0.7977.42
extern const wchar_t kChromeExe[];
// 153.0.8000.0 and trunk
inline constexpr wchar_t kChromeExe[] = L"chrome.exe";
```

A patch written against the pin does not fail to *merge* at the next roll. It
fails to *apply at all*, because its target is gone — and the work is redone
against a different file with a different shape. That is not churn; it is the
file being restructured under the change.

**This does not make the name work impossible.** It prices it: the patch is
rewritten at the first roll, and this measurement is one milestone of evidence
that it will be rewritten again.

## 6a. Measured: the whole blast radius, not the part that was to hand

§8.4 asked for `scripts/measure_rebase_cost.py` to be run against these files
before the name work starts. **That was the wrong tool and the ask was still
right.** The rebase-cost script applies the patch series; a file no patch names
is invisible to it, and the name change would own files no patch has ever
named. `scripts/measure_file_churn.py` is what the question needed, and it is a
script rather than another hand-made table because the row corrected above was
wrong precisely for being a thing someone did once.

All twenty-two files §4 enumerates, at the pin, at the next milestone and at
trunk:

| File | at 152.0.7977.42 | 153.0.8000.0 | main |
| --- | --- | --- | --- |
| `chrome/installer/util/util_constants.cc` | 244 lines | **deleted** | **deleted** |
| `chrome/installer/util/util_constants.h` | 277 lines | 320 lines differ | 320 lines differ |
| `chrome/installer/setup/setup_main.cc` | 1786 lines | **unchanged** | **unchanged** |
| `chrome/installer/setup/install.cc` | 608 lines | **unchanged** | **unchanged** |
| `chrome/installer/setup/install_worker.cc` | 1331 lines | 10 lines differ | 17 lines differ |
| `chrome/installer/setup/setup_util.cc` | 685 lines | **unchanged** | 5 lines differ |
| `chrome/installer/setup/installer_state.cc` | 193 lines | **unchanged** | **unchanged** |
| `chrome/installer/setup/setup_constants.cc` | 55 lines | **unchanged** | **unchanged** |
| `chrome/installer/setup/setup_install_details.cc` | 108 lines | **unchanged** | **unchanged** |
| `chrome/installer/setup/uninstall.cc` | 1243 lines | **unchanged** | 10 lines differ |
| `chrome/installer/setup/setup_singleton.cc` | 130 lines | **unchanged** | 2 lines differ |
| `chrome/installer/setup/brand_behaviors.h` | 43 lines | **unchanged** | **unchanged** |
| `chrome/installer/util/delete_old_versions.cc` | 252 lines | **unchanged** | **unchanged** |
| `chrome/installer/util/shell_util.cc` | 2547 lines | **unchanged** | **unchanged** |
| `chrome/installer/util/install_util.cc` | 620 lines | **unchanged** | **unchanged** |
| `chrome/installer/util/helper.cc` | 225 lines | **unchanged** | **unchanged** |
| `chrome/browser/shell_integration_win.cc` | 959 lines | **unchanged** | 112 lines differ |
| `chrome/install_static/install_util.cc` | 995 lines | **unchanged** | **unchanged** |
| `chrome/install_static/install_util.h` | 338 lines | **unchanged** | **unchanged** |
| `chrome/install_static/install_modes.h` | 72 lines | **unchanged** | **unchanged** |
| `chrome/install_static/install_modes.cc` | 59 lines | **unchanged** | **unchanged** |
| `chrome/install_static/product_install_details.cc` | 166 lines | **unchanged** | **unchanged** |

### What this changes about §4, and what it does not

**Two files of twenty-two move at the next milestone.** `util_constants.cc`
disappears, `util_constants.h` absorbs it, and `install_worker.cc` differs by
ten lines. Everything else — including `shell_util.cc` at 2,547 lines, which
carries ProgID and default-browser registration, and the whole of
`install_static` — is **byte-identical at 153**.

So §4's sentence *"each upstream roll re-applies these edits against code that
assumes the constants it was written with"* is not what one milestone shows. The
edits away from the constants would re-apply untouched. **The cost is not spread
across the radius; it is concentrated in the one file the change cannot
avoid**, and that file is the one under active restructuring.

**The direction of the restructuring is the finding worth the owner's
attention.** At the pin, `kChromeExe` is an `extern` declaration whose value
lives in a `.cc` — a definition in one translation unit, which is the easiest
possible thing to make a runtime value. At 153 it is `inline constexpr` in a
header, consumed at compile time by everything that includes it, including
`install_static`, whose design premise §4 already names: brand identity is a
compile-time constant. **Upstream moved further in the direction that makes a
user-typed name harder**, in one milestone, without anyone asking it to.

That is evidence about a trend from a single step, which is the weakest kind of
evidence about a trend. It is recorded as one measurement, and
`scripts/measure_file_churn.py executable-name` re-runs it at the next roll.

**No decision is made here.** §8.3 is the owner's and this only prices it.

## 7. What the owner decided

| | Question | Decision |
| --- | --- | --- |
| 1 | Folder choice on per-user installs? | **No.** Per-machine only — which is exactly where the upstream hook already works, so the one case with no support is the one not needed. |
| 2 | Unsafe folder: refuse or warn? | **Warn**, and proceed. |
| 3 | Executable name | **Build-time default, user input overrides.** `sunshine.exe` for everyone who does not type anything. |
| 4 | Roll cost | **Measured.** §6. |

**Decision 1 removes the hardest part of the folder work.** §3 named the
per-user case as having no upstream hook at all; it is now out of scope, and
what remains is one validation in a file that has not changed in two
milestones.

**Decision 2 is an accepted risk, and this is what it accepts.** The
`%ProgramFiles%` restriction is what makes a per-machine install a binary
unprivileged users cannot replace. A warning does not restore that; it moves
the decision to a person who is, at that moment, being asked to judge Windows
directory permissions from a dialog. If they proceed into a user-writable
folder, **any unprivileged account on that machine can replace the executable
every other account launches** — including accounts that never saw the warning.

That is recorded here as accepted rather than argued again. Two things follow
from accepting it, and both are cheap:

- the warning must name the consequence, not the condition. "This folder can be
  modified by other users of this computer, who could replace Sunshine" is the
  sentence; "this location is not recommended" is not.
- the check itself still has to exist and run **after elevation**, because a
  writability test performed before elevating tests the wrong token.

**Decision 3 is the cheaper half of what was asked for.** The default costs one
branding change; the override costs §4 and §6. The default is also what every
install that nobody customises will show, which is the population the clarity
was for.

## 8. What the owner still has to decide

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
4. ~~**Roll cost.** `scripts/measure_rebase_cost.py` exists and has never been
   run against these files. It should be, before the name work starts rather
   than after.~~ **Measured — §6a.** The tool named here was the wrong one and
   the ask was right; `scripts/measure_file_churn.py` answers it. Two of
   twenty-two files move at the next milestone, the cost is concentrated in
   `util_constants.*` rather than spread, and upstream has moved the constant
   *further* toward compile time in the one milestone measured. The question
   left for the owner is 3, not this.

## 9. NOT VERIFIED

- **Nothing here has been run.** The folder half is built and compiles in CI as
  part of the stack, but no installer produced from it has been executed and no
  person has typed a path into the box.

  **This bullet said "Nothing is built, and nothing has been compiled" until
  2026-08-30**, and the bullet under it said the relaxed-validation patch had
  not been written. `downstream/patches/0023-sunshine-installer-install-root.patch`
  had existed for three days by then, applies at the pin, at `153.0.8000.0` and
  at trunk, and §3's *Built, and what it actually took* describes it in detail
  — in this same document. **A NOT VERIFIED section that disclaims work the
  document elsewhere reports as done is worse than one that is silent**, because
  it is the section a careful reader trusts most.

  This is the second time in this document set. `docs/INSTALLER_UI_CONTRACT.md`
  said "No implementation exists" while `installer/sunshine_setup.cpp` held 948
  lines. Nothing caught either: no guard reads a document's account of its own
  status, and the obvious rule — refuse a sentence that says a named patch is
  unwritten — would have caught neither, because neither sentence named one.
  What is enforced instead is the form that makes such a sentence checkable at
  all: `scripts/verify_stated_counts.py` now refuses a sentence saying a patch
  in `downstream/patches/series` does not exist, and refuses "nothing is built"
  in a document that elsewhere heads a section *Built* — which is this one. It
  catches two of the four; `docs/INSTALLER_UI_CONTRACT.md` §10 says which two
  it does not and why widening it would be worse.
- **The name half of §4 is unwritten and unmeasured.** Nothing in the tree
  implements a chosen executable name, and the blast radius below is a reading
  rather than a diff.
- **The blast radius in §4 is enumerated from constant declarations and their
  documented roles, not from call-site analysis.** The true set of places that
  assume `chrome.exe` is a literal is at least the list given and may be larger.
- **No per-user hook has been looked for beyond `GetInstallationDirFromPrefs`.**
  There may be another route; none was found in `helper.cc`.
- **The privilege-escalation reasoning in §3 is architectural, not
  demonstrated.** No exploit was constructed and none is needed to justify
  keeping the guarantee.
