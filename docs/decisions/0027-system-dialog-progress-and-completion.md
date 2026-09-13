---
doc_id: adr-0027-system-dialog-progress-and-completion
version: 1.0.0
canonical_path: docs/decisions/0027-system-dialog-progress-and-completion.md
updated: 2026-09-13
---

# ADR 0027: The system's dialog, a progress bar that cannot lie, and a page that says what happened

## Status

**Accepted, on the owner's instruction of 2026-09-13, and implemented in
`installer/sunshine_setup.{cpp,rc}` and `installer/resource.h`.** No patch: the
front-end is outside Chromium's build graph (IU-1). §6 lists what is unverified,
which is most of it.

**This reverses `docs/INSTALLER_UI_REVIEW.md` D6.** That decision chose
Sunshine's own look for the installer. The owner has chosen the system's. It is
recorded as a reversal rather than as a refinement.

## Context

The owner asked for three things:

1. the system's default dialog rather than a drawn one;
2. a progress bar while installing;
3. a window at the end saying it finished.

**Two and three did not exist at all.** `EndDialog` closed the window and then
`RunEngine` ran with no user interface whatsoever — so after pressing Install
the person watched an empty desktop for as long as `mini_installer.exe` took,
with nothing on screen distinguishing a working install from a hung one, and
nothing at the end saying whether it had worked. That is the more serious of
the three and it was not in the contract as a gap.

## Decision

### 1. Nothing is drawn by hand (IU-19)

Removed: the banner, `DrawBanner`, `DrawButton`, the `WM_DRAWITEM` dispatch, the
`WM_CTLCOLOR*` handlers, `CreateSolidBrush`, `CurrentPalette`,
`SystemPrefersDark`, and the `wincodec.h`/`uxtheme.h` includes.

**And `SetWindowTheme(control, L"", L"")` on six checkboxes**, which is the part
worth naming. That call *strips* the theme from a real control so a hand-mixed
colour will apply to it — precisely what IU-13 asks a dialog not to do. It was
there to serve the palette. **The custom look was paying for itself with a rule
break, and both went at once.**

`IU-16` drops from two registry reads to one: the light/dark preference is
Windows' business now.

### 2. One window, three pages, engine on a thread (IU-20)

Still exactly one `DialogBoxParamW`, so IU-15's question — was the dialog shown
— keeps one answer. The pages are control groups shown and hidden.

The engine runs on a worker thread and posts its result back, because a message
loop blocked for the whole install would leave a progress bar that is a *still
image* of a progress bar, which reads as a hang and is worse than no bar.

`wWinMain`'s loop is gone with it. It used to re-enter the dialog after a
declined elevation prompt; the dialog now returns to its first page, which is
the same IU-12 behaviour without tearing the window down and rebuilding it.

### 3. The bar is a marquee and may not be anything else (IU-21)

`mini_installer.exe` reports progress to nobody. It unpacks an archive and hands
off to `setup.exe`; there is no channel, no callback and no file this program
could read a percentage from.

**So a bar that filled would be drawing a number this program invented**, and an
invented percentage is the most confident lie an installer can tell. A marquee
says "working, duration unknown", which is the true statement. The guard refuses
`PBM_SETPOS`, `PBM_DELTAPOS` and `PBM_STEPIT` by name, because replacing a
marquee with a filling bar is the kind of change that looks like an improvement.

### 4. The completion page reads the engine's code and prints it (IU-22)

The wording comes from `installer::InstallStatus` in
`chrome/installer/util/util_constants.h` — read, not remembered:
`FIRST_INSTALL_SUCCESS = 0`, `INSTALL_REPAIRED = 1`, `NEW_VERSION_UPDATED = 2`,
`EXISTING_VERSION_LAUNCHED = 3`, `HIGHER_VERSION_EXISTS = 4`,
`USER_LEVEL_INSTALL_EXISTS = 5`, `SYSTEM_LEVEL_INSTALL_EXISTS = 6`,
`INSUFFICIENT_RIGHTS = 14`, `INSTALL_DIR_IN_USE = 28`, `IN_USE_UPDATED = 30`.

**The number is printed beside the sentence.** The sentence is a reading of it,
and a reader is entitled to check a reading rather than believe it. The
process's own exit code is still the engine's, untouched, as §5 requires.

### 5. There is nothing to cancel once it starts (IU-23)

The engine is a separate process that owns the work. Escape and the title bar's
close button are ignored on the progress page rather than offering a button that
would do nothing.

## Consequences

- Sunshine's installer looks like every other installer. That is what was asked
  for.
- `installer/banner.png` and `IDR_BANNER` are unused. The file stays in the tree
  for now; the contract's NOT VERIFIED section no longer needs its aspect-ratio
  entry, which had been open since the placeholder shipped.
- **The C++ got a compiler for the first time.**
  `scripts/compile_check_installer.py` syntax-checks both front-ends with
  `x86_64-w64-mingw32-g++`. Until this change nothing outside the one Windows
  build machine could tell whether these files even parsed, and three builds
  have been lost to defects a compiler names in a second. It is not MSVC and
  does not pretend to be; it catches unclosed braces, missing names, wrong
  arities and stale includes. Two accommodations are stated in the file:
  `BCRYPT_SHA256_ALG_HANDLE` is supplied because mingw lacks it, and a stand-in
  `engine_hash.h` is generated because the real one is never committed.
- It found one warning immediately — a partially-initialised `SHELLEXECUTEINFOW`
  in the uninstall launcher, fixed to match the form `RelaunchElevated` already
  used.

## 6. NOT VERIFIED

**None of this has been run. It needs build #59 and a person, and the list is
longer than usual because the whole surface changed.**

- That the dialog opens at all — **RV-54**, which two builds have already
  failed for unrelated reasons. `ICC_PROGRESS_CLASS` is a new way to fail it:
  without that flag `msctls_progress32` is unregistered, the control fails to
  create, and `DialogBoxParamW` returns −1.
- That it looks like a Windows dialog in light *and* dark — **RV-65**. The
  palette is no longer this program's to get wrong, which is the point, but
  nobody has looked.
- That the marquee animates during a real install — **RV-66**. This is the
  thread working, observed.
- That the completion page appears and its sentence matches its code —
  **RV-67**.
- That a declined UAC prompt returns to page 1 with the choices intact — IU-12
  through a path that has never existed before.
- Whether the window should be resizable, and whether 340×210 dialog units is
  still the right size now that the banner is gone. Not considered.
