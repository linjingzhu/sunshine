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

## 2. The order, and what each block needs

Blocks run top to bottom. Within a block the order does not matter.

| Block | Gates | Needs | Rough |
| --- | --- | --- | --- |
| **A — the files, before anything is launched** | RV-11, RV-26, RV-29, RV-30, RV-28 | The installer, Explorer, `regedit` | 15 min |
| **B — the security posture, first launch** | RV-1, RV-2, RV-3, RV-4 | The browser open | 10 min |
| **C — is it Sunshine** | RV-10, RV-27, RV-12 | Launched, and pinned to the taskbar once | 10 min |
| **D — new tab** | RV-8, RV-9, RVV-1, RVV-2, RVV-3 | A window that can be resized; light and dark | 20 min |
| **E — media** | RV-5, RV-6 | Network, and one H.264/AAC and one VP9 or AV1 source | 10 min |
| **E2 — mouse gestures** | RV-20 | Any page with history in both directions; a link, an image and some selected text to try it on | 15 min |
| **F — bookmark bar and module home** | RV-21, RV-22, RV-23, RV-24, RV-25, RV-37, RVV-4, RVV-5 | The bookmark bar shown; `first_party/registry.json` open beside it | 25 min |
| **G — the module shell** | RV-31, RV-32, RV-33, RV-34, RV-38 | `chrome://sunshine-shell`; a window narrow enough to hit the clamp | 30 min |
| **H — the document surface** | RV-13, RV-14, RV-15, RV-16, RV-17, RV-18, RV-19 | `chrome://sunshine-document`, DevTools open for RV-16 | 40 min |

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

**RV-20 used to be a third.** Patch 0017 implements the gesture recogniser, so
block E2 above is now runnable — but only from a build that contains it, which
build #33 does not. Run it from build #34 or later, and nowhere else.

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
