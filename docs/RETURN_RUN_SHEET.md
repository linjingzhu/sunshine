# Return run sheet — the manual gates, in the order to run them

## What this is

`docs/RUNTIME_VERIFICATION.md` defines forty-three gates and says what each one
means. It does not say what order to run them in, what has to be true before
each one, or which failures should end the session. This does, and nothing
else: **every expectation stays in that document.** A sheet that restated them
would be a second version to drift, and `scripts/verify_verification_evidence.py`
rule 7 holds this file to that document's gate set rather than to a copy of it.

One gate has a PASS record. The other forty-two are `NOT RUN`, and the reason is
not that they are hard — it is that the only machine that can run them is the
one that also builds, and nobody has sat down with it. Build #33 produced an
installer that makes all but three of them runnable in one sitting.

**The artifact.** `sunshine-installer-windows-x64.exe`, 117.5 MB, from build #33
(run `32323176049`, commit `ca1f5c0`), under
`artifacts\windows-x64\` in the runner's workspace.

## 1. Two things that will ruin the session

**The build machine is the browser machine.** A running Sunshine holds
`chrome_elf.dll` open, and build #21 died at `lld-link: failed to write output
'./chrome_elf.dll': permission denied` for exactly that reason. So: **close
Sunshine before queueing a build**, and do not start a gate run while one is in
flight. This is not a precaution, it is a failure that has already happened
once.

**A gate that cannot be read is `NOT RUN`, not `PASS`.** `chrome://sandbox` and
`chrome://process-internals` are upstream debugging surfaces whose output may
have changed under the pin. If a row cannot be found, that is the result.

**There is a Korean sheet, and it is generated from this file.**
`gate-sheet.html` at the repository root carries every gate below with a
step-by-step walkthrough, a PASS/FAIL/NOT RUN control and an export box.
`scripts/build_gate_sheet.py` builds it from this document's block table and
`docs/RUNTIME_VERIFICATION.md`'s gate table, so the two cannot say different
things — and CI now regenerates it and refuses a committed copy that does not
match, which it did not do for the three releases the sheet spent silently
failing to build at all.

## 2. The order, and what each block needs

Blocks run top to bottom. Within a block the order does not matter.

| Block | Gates | Needs | Rough |
| --- | --- | --- | --- |
| **A0 — the setup window** | RV-54 first, then RV-55 | `sunshine-setup.exe`, and PowerShell open beside it in case nothing appears | 5 min |
| **A — the files, before anything is launched** | RV-11, RV-26, RV-29, RV-30, RV-28 | The installer, Explorer, `regedit` | 15 min |
| **B — the security posture, first launch** | RV-1, RV-2, RV-3, RV-4 | The browser open | 10 min |
| **C — is it Sunshine** | RV-10, RV-27, RV-12 | Launched, and pinned to the taskbar once | 10 min |
| **D — new tab** | RV-8, RV-9, RVV-1, RVV-2, RVV-3 | A window that can be resized; light and dark | 20 min |
| **E — media** | RV-5, RV-6 | Network, and one H.264/AAC and one VP9 or AV1 source | 10 min |
| **E1 — DRM** | RV-57 first, then RV-58, RV-56 last | A Netflix (or other DRM) account, and network | 10 min |
| **E2 — mouse gestures** | RV-20 | Any page with history in both directions; a link, an image and some selected text to try it on | 15 min |
| **F — bookmark bar and module home** | **RV-39 first**, then RV-41, RV-42, RV-21, RV-22, RV-23, RV-24, RV-25, RV-37, RVV-4, RVV-5, RV-40, RV-43 last | A normal browser window; `first_party/registry.json` open beside it | 35 min |
| **F1 — the bookmark bar's leading edge** | RV-48, RV-49 | A fresh profile for RV-48 | 5 min |
| **F4 — the home button** | RV-59 first, then RV-60, RV-61 | The same fresh profile as F1 | 5 min |
| **F2 — split view** | **RV-44 first**, then RV-45, RV-46, RV-47 | Two tabs, split side by side; a screenshot of build #47's split for RV-47 | 15 min |
| **F3 — a module actually mounted** | RV-50 first, then RV-51, RV-52, RV-53, RV-35, RV-36 | `chrome://sunshine-shell`; RV-35 needs `chrome://process-internals` in a second tab | 25 min |
| **G — the module shell** | RV-31, RV-32, RV-33, RV-34, RV-38 | `chrome://sunshine-shell`; a window narrow enough to hit the clamp | 30 min |
| **H — the document surface** | RV-13, RV-14, RV-15, RV-16, RV-17, RV-18, RV-19 | `chrome://sunshine-document`, DevTools open for RV-16 | 40 min |

**Why RV-56 runs last inside E1.** It is the gate everyone wants the answer
to, and it is the one that takes time to fail honestly: the CDM is fetched by
the component updater rather than compiled in, so a first play can fail while
the download is still in flight. Running `chrome://components` first means that
when RV-56 does fail, its cause is already on the sheet — a version, a
`0.0.0.0`, or no row at all — instead of being guessed at afterwards.

**Why A0 exists and comes before A.** Every gate in A is about a machine that
has been installed onto, and the way it gets installed is `sunshine-setup.exe`.
Two builds in a row shipped a setup that opened nothing at all — #55 for a
missing C runtime, #56 for a stack overflow — and both times the session was
spent on the browser's gates while the one binary the owner actually
double-clicked was the broken one. A0 asks the only question that has to be
answered before any of this starts: **did a window appear.** If it did not, the
exit code says which of the two failures it was, and RV-54 says how to read it
rather than leaving the reader to guess from silence.

**Why RV-39 comes first inside F.** Every other gate in this section was
written against "the bookmark bar shown", and that was the section's stated
precondition rather than one of its gates — so nothing checked it. On
2026-08-31 the owner reported that `Ctrl+Shift+B` does nothing in a normal
window on build #47, which if true makes the precondition unobtainable and
turns eight gates into NOT RUNs that read as a scheduling problem rather than
as a finding. RV-39 asks the question by both routes, and which of the two
fails says where the fault is: a greyed-out menu item means the command is
disabled, and a working menu item with a dead key means the key never arrived.

**Why A comes before B.** Every gate in A is about files and registry keys that
launching cannot change, and three of them (RV-26, RV-29, RV-30) are the ones a
machine with real Chromium on it would fail loudest — the install directory
collision, the profile collision, the protocol registration. Answering them
while nothing is running keeps the answer unambiguous.

**RV-28 is conditional.** It needs a real Chromium or Chrome installed on the
same machine. If there is none, the result is `NOT RUN`. It is the only gate in
A that cannot be forced.

## 3. When to stop

| If this fails | Then |
| --- | --- |
| RV-1, RV-2 or RV-3 | **Stop the session.** The sandbox or the isolation posture is wrong, and every gate below it is being run against a browser whose security model is not the one the contracts describe. Nothing downstream is worth recording. |
| RV-26, RV-29 or RV-30 | Finish block A, then stop. These are installer identity, they are ADR 0015's whole subject, and a failure means the installer has to be rebuilt before the rest is worth running. |
| Anything else | Record it and carry on. One surface failing says nothing about the next. |

## 4. Two gates that cannot be run, and why

Stated here so they are not discovered at the end of a long evening.

| Gate | Why not |
| --- | --- |
| RV-35 | **No module declares a mount.** `scripts/verify_module_mount.py` reports `0 module(s) declare a mount`, so there is no frame to open E on and none to destroy. |
| RV-36 | The same cause. Switching between two mounted modules needs two mounted modules. |

**RV-20 used to be a third, and is now simply runnable.** Patch 0017 implements
the gesture recogniser and **build #37 (run `32437521316`, commit `8c5f64b`)
compiled it** — the first build that contains it. Run block E2 from that
installer or a later one, and from nowhere else. The account surface from
patches 0018 and 0019 is in the same binary, but it has no gate yet: the page
only reports whether this build has an OAuth client, and this one does not.

RV-35 and RV-36 are the mount lifecycle, which is the part of the shell the
whole module seam exists for. They are blocked on there being something to
mount — which is the first installed module, or a first-party surface module
that declares one. **That is the strongest argument available for doing the
install work next**: it is not only a feature, it is what makes two shipped
invariants checkable at all.

RV-31 to RV-34 and RV-38 are *not* blocked by this. The shell draws an explicit
empty state for a module that declares no mount, and the states, the clamp, the
per-module persistence and the splitter are all shell behaviour rather than
module behaviour.

## 5. Writing the result down

Section 4 of `docs/RUNTIME_VERIFICATION.md` owns the record shape. Use it
literally — `scripts/verify_verification_evidence.py` parses these:

```text
gate       RV-26
result     PASS
build      #33, run 32323176049, commit ca1f5c0
observed   %LOCALAPPDATA%\Sunshine\Application
```

Two rules that the guard enforces and that are easy to get wrong: a `PASS` with
no `build` line is rejected, and two records for one gate with different results
are rejected as contradictory. `observed` is only needed when what was seen was
not simply the expected text — which in practice means: fill it in for every
FAIL, and for any PASS that took a second look.

Records go in section 5 of that document. **Do not advance any module
manifest's `verification` fields from this run**; section 5 already explains
why a build result does not discharge a per-module claim, and that question is
still open.

## 6. NOT VERIFIED

- **This sheet's time estimates are guesses.** No block has been run once, so
  they are derived from how many things each gate asks a person to look at, not
  from measurement.
- The block order is an argument, not a result. Blocks D through H are
  independent of each other; only A before B, and the stop rules, are load
  bearing.
- Whether the installer from build #33 installs at all is itself unverified.
  `scripts/verify_installed_build.py` read the binary; nobody has run the
  installer.
