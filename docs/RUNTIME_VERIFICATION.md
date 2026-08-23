# Runtime verification

## Why this exists

`scripts/trace_invariants.py` prints how many invariants the contract set
declares and how many a check claims; `config/invariant_coverage.txt` is the
ratchet that stops the second number falling. Run it for the current pair — a
figure written here would be stale within a wave, and this paragraph's argument
does not need one. Most of the unclaimed remainder are class B — decidable only
with a built browser. A browser has existed since
build #12 finished, and nothing was reading it: every module manifest still
says

```json
"verification": {"native_build": "pending", "runtime": "pending", "visual": "pending"}
```

That is accurate, and it is the gap this document closes. It defines what turns
each of those three from `pending` into `passed`, and what evidence has to exist
before anyone writes the word.

**The rule that makes this worth having:** a verification state may only be
changed by someone who ran the step and recorded the result. `passed` with no
recorded evidence is worse than `pending`, because `pending` is true.

## 1. Automated — `scripts/verify_installed_build.py`

Runs in the build workflow, immediately after the build, on the machine that
produced it. It reads the output rather than the source:

| Check | Invariant |
| --- | --- |
| `chrome.exe` and `mini_installer.exe` exist and have plausible size | native build |
| `args.gn` contains `is_official_build`, `is_debug=false`, `proprietary_codecs=true`, `ffmpeg_branding="Chrome"` | ADR 0004 |
| `args.gn` contains no sandbox- or isolation-disabling switch | SEC-1, SEC-2 |
| Windows registers no `sunshine`, `sunshine-module` or `sunshineos` URL protocol | SEC-13 |
| `chrome.exe` carries a non-zero `VERSIONINFO` resource | patch 0001, resource pipeline |
| `chrome.exe`'s application icon resource holds the image data of `downstream/assets/chrome/app/theme/chromium/win/chromium.ico` | ADR 0008 |

The version-resource row reads the binary rather than running it, and that
restriction was bought at the cost of two builds. A launch check shipped here
briefly: it first required console output that a Windows GUI subsystem binary
never writes to a redirected pipe, failing build #20 on a browser that was
fine, and then build #21 died at `lld-link: failed to write output
'./chrome_elf.dll': permission denied` because the browser that check had
started was still running and holding its own DLL open. On Windows an exit code
of 0 cannot distinguish "printed a version and exited" from "launched the
browser and the stub handed off", so there was no version of it worth keeping.

**Whether the browser starts is therefore a manual gate, not an automated
one.** That is a real limit and it is stated rather than papered over: the only
machine that can answer it is the one that is also the only CI, and a browser
started there breaks the next build.

The icon row reads the binary the same way and for the same reason. It maps
`chrome.exe` with `LOAD_LIBRARY_AS_DATAFILE` — which resolves no imports and
calls no entry point — takes the lowest-numbered `RT_GROUP_ICON`, which is the
one Windows shows for an application and which Chromium's `chrome_exe.rc`
names `IDR_MAINFRAME`, resolves each of its entries to the `RT_ICON` it points at, and
requires those images to be the images the committed `.ico` holds.

What it compares is the image payloads, not the files. An `.ico` is a directory
of byte offsets into itself; a PE holds the same header with resource ids in
place of those offsets and each image moved into a resource of its own, so
`rc.exe` necessarily rewrites the directory and a whole-file comparison would
fail on a correct build. The images themselves are copied verbatim, so they are
what survives. Comparing only the *size set* would be simpler and nearly
worthless: `scripts/verify_asset_overlay.py` requires 16, 32, 48 and 256 px
because that is the set Chromium's own `chromium.ico` carries, so the icon this
check exists to catch has the same size set as the icon it expects.

The other icons `chrome_exe.rc` declares — the app-list, incognito and document
icons — are out of scope. The overlay does not replace them, no contract here
says what they should contain, and checking them would amount to asserting that
upstream had not changed its own artwork. `mini_installer.exe` is likewise not
read here; its icon is a separate overlay file and stays with RV-11.

The registry row is the reason this runs on Windows rather than in the guard job.
SEC-13 is enforced in source by `scripts/verify_first_party_surfaces.py`; this
checks the layer where a registration would actually matter — what the operating
system believes. A source check cannot see a scheme registered by an installer.

Off Windows the registry check reports `NOT AVAILABLE` and the script exits **2**,
which is neither pass nor fail. A check that silently passes where it cannot run
produces a green result nobody earned.

`native_build: passed` requires this script to have exited 0 on the build
machine, and the run to be identifiable — workflow run number and commit.

## 2. Manual — the runtime gate

These need the browser open and a person looking. Chromium's own internal pages
are the instrument; none of this requires instrumentation Sunshine has to build.

**What order to run them in is not here.** `docs/RETURN_RUN_SHEET.md` holds the
order, what each block needs, and when a failure should end the session. It
holds no expectations — this document owns those — and rule 7 of
`scripts/verify_verification_evidence.py` keeps the two from drifting apart.

| # | Step | Expected | Invariant |
| --- | --- | --- | --- |
| RV-1 | Open `chrome://version` | The command line contains no `--no-sandbox`, no `--single-process`, no `--disable-site-isolation-trials` | SEC-1, SEC-2 |
| RV-2 | Open `chrome://sandbox` | Every renderer row reports a sandbox as active | SEC-1 |
| RV-3 | Open `chrome://process-internals` | Site isolation mode is site-per-process, and two cross-site frames occupy different processes | SEC-2 |
| RV-4 | Type `sunshine://anything` in the omnibox | Treated as a search, not a navigation — the scheme does not resolve | SEC-13 |
| RV-5 | Play an H.264/AAC video | Decodes and plays | ADR 0004 |
| RV-6 | Play a VP9 or AV1 video | Decodes and plays — the codec change must not have cost the royalty-free path | ADR 0004 |
| RV-7 | Open a new tab | The Sunshine wordmark occupies the logo slot; Chromium's own logo is absent | patch 0002 |
| RV-8 | Open a new tab on a keyless build | No infobar reports missing Google API keys | patch 0003, ADR 0005 |
| RV-9 | Search from the New Tab page | Chromium's own search handling runs; no Sunshine interposition, no forced startup URL | `verify_architecture.py` startup-URL rule, at runtime |
| RV-10 | Look at `chrome.exe` in Explorer's list view, on the taskbar, and as a pinned shortcut | The Sunshine icon reads correctly at each of the three sizes the shell asks for — not stretched, not a rescaled neighbour, not Chromium's blue sphere | ADR 0008 |
| RV-11 | Look at `mini_installer.exe` in Explorer | The Sunshine icon | ADR 0008 |
| RV-12 | Open `chrome://sunshine-security` | Exactly one of the four verdict paragraphs is visible, and it is the one the build's three booleans imply | SC-11, SEC-14, patch 0005 |
| RV-13 | Open `chrome://sunshine-document`, build a hierarchy 1 → 1.1 → 1.2 → 1.2.1 → 2, then press Next from 1.2 | 1.2.1, not 2. The contents list is the reading order, depth first | DOC contract §3 |
| RV-14 | Read a section whose HTML carries its own `<head><style>` | That styling applies and the pane *is* the document, edge to edge — not a stripped fragment inside Sunshine's own frame | DOC-1 |
| RV-15 | Read a section whose HTML contains a `<script>` that would be visible if it ran | The document renders; the script does not run | DOCA-3 |
| RV-16 | Read a section referencing a remote image | Shown as absent, and no request for it appears in DevTools' network panel | DOC-5, DOCA-4 |
| RV-17 | Store a document, navigate away, come back, and compare | Byte-identical to what was stored; no normalisation, no re-indentation, no pagination written back | DOC-4, DOCA-5 |
| RV-18 | Delete a project that had documents, then reopen the surface | The project and every document of it are gone | DOC-7, DOCA-6 |
| RV-19 | With a section open, press refresh, then download | Refresh re-reads from the store without disturbing an unsaved edit in the editor; download saves an `.html` file whose contents are the stored document | DOC-3, DOC-8 |
| RV-20 | Press the right mouse button in page content and drag left 200 px, then release; repeat dragging right; repeat with a drag of 50 px | Left goes back, right goes forward, and the short drag shows the context menu instead. Neither long drag shows a menu, and no press does both | GESTURE contract §3.2, patch 0017 |
| RV-21 | Show the bookmark bar and look at its leading edge | One Sunshine button sits there, left of the saved tab group button, tooltip "Sunshine modules". Its glyph is not the grid the tab group button uses | ADR 0014 §5, patch 0008 |
| RV-22 | Click that button, then ctrl-click it | The first opens `chrome://sunshine-modules` in the current tab; the second opens it in a new background tab. Disposition follows the modifier, as it does for every other button on this bar | ADR 0014 §2 |
| RV-23 | On `chrome://sunshine-modules`, compare the left column against `first_party/registry.json` | The same modules, the same order, and the count in the heading matches. This is the gate the sync guard cannot reach: the guard compares the patch to `first_party/`, not the running page to either | patch 0007, `verify_module_registry_sync.py` |
| RV-24 | Select each module in the left column | Its declared network, filesystem and credential values are the manifest's own words, and a value other than `deny`/`none`/no is the one that stands out | MODULE HOME §2 |
| RV-25 | Narrow the window until the bookmark bar overflows its buttons | The Sunshine button keeps its place at the leading edge and is never drawn over the button beside it | patch 0008, `GetMinimumSize()` |
| RV-26 | Install, then look at the install directory, the Start menu entry, the taskbar item and Windows' Default Apps list | All four say Sunshine. In particular the install directory is `%LOCALAPPDATA%\Sunshine\Application`, not `Chromium` — which is where a machine with real Chromium on it would have collided | ADR 0015 §1 |
| RV-27 | Open the app menu, About, and the default-browser prompt | Every one names Sunshine. About still credits **The Chromium Authors** and the copyright is unchanged — that is correct and is what patch 0010 protects | ADR 0015 §2 |
| RV-28 | With a real Chromium or Chrome also installed, install Sunshine and use both | Neither replaces the other's files or profile, and the taskbar shows them as two applications | ADR 0015 §1, §3 |
| RV-29 | After installing, look for the profile: `%LOCALAPPDATA%\Sunshine\User Data` | It exists and holds the profile. `%LOCALAPPDATA%\Chromium` is untouched — which on a machine with real Chromium is that browser's profile, and was the same directory before this change | ADR 0015 §1 |
| RV-30 | Check `HKCR` for a `chromium` and a `sunshine` key after installing | Neither is registered as a URL protocol. The empty `direct_launch_url_scheme` means the installer writes no `Software\Classes\<scheme>` entry at all | ADR 0015 §3, SEC-13 |
| RV-31 | Open `chrome://sunshine-shell` and reach all nine states in §3 of the shell contract, then reach each one back | Every state is reachable and reversible. The skeleton is the same in all of them; only content changes | MS-6, MS-8 |
| RV-32 | Narrow the window past the clamp with all four regions open | E collapses first, then C. D never goes below 480px while visible, and B never changes | MS-5 |
| RV-33 | Set a tab width in one module, switch modules, switch back; then toggle the bar and the dock and switch modules | The tab width returns per module. The bar toggle and the dock width do not change when the module does | MS-7 |
| RV-34 | Drag each splitter, release outside the window, and double-click it | Live resize with no ghost line; the width persists where the pointer left it; double-click returns the default | shell contract §4 |
| RV-35 | With a module mounted, open E, then close it, and look at the frame count in `chrome://process-internals` | Closing E destroys its frame. A module does not keep running behind a region the user has put away | MM-9 |
| RV-36 | Switch from one mounted module to another and back | The second module's frame replaces the first rather than reusing it: nothing of the first module's document survives into the second, and returning to it starts it again | MM-10 |
| RV-37 | On `chrome://sunshine-modules`, follow the link below the module list | It arrives at `chrome://sunshine-shell`. This is the only route to that surface that is not typing its address, and before patch 0013 there was none | MODULE HOME §1, patch 0013 |
| RV-38 | In the module shell, press **Register** at the foot of the dock | It arrives at the module home's registration section. Nothing is installed, nothing changes, and the section says why: a module is compiled in. The control is at the very bottom of B, below the Names toggle | MODULE SHELL §1, MH-1, patch 0014 |

RV-6 is not redundant with RV-5. `ffmpeg_branding="Chrome"` changes which FFmpeg
sources are compiled, and a regression there would remove the codecs the project
had before the decision rather than the ones it added.

RV-4 is the runtime half of SEC-13 that neither the source guard nor the registry
check covers: a scheme can be registered inside the browser without touching the
registry, and the omnibox is where a user would meet it.

RV-12 through RV-19 are the first gates for a Sunshine capability rather than
for a property of the build. Everything before them asks whether Chromium
survived being patched; these ask whether the thing Sunshine added does what its
contract says. RV-14 through RV-18 map one-to-one onto DOCA-3 through DOCA-6 and
DOC-4, which the document surface contract classes as decidable only with a
browser — this document is where that debt is collected.

RV-19 is worth its place for a reason beyond the two controls. Refresh
re-reading without disturbing an unsaved edit is the observable form of a
decision that is otherwise invisible: the store's answer and the editor's
contents are different things, and a refresh that overwrote the editor would
silently discard work. Download is the only gate that exercises DOC-8 — what
comes back must be the stored document, and Sunshine must not have been offered
a destination to remember.

**RV-20 can now run, and the two things that blocked it are the two things the
patch is built out of.** This paragraph used to say the gate would not be
runnable for some time, and named both obstacles: §3.1 evaluated suppression
"once, at button press", which the browser process cannot do because it holds
no DOM to hit-test until `ContextMenuParams` arrives; and §3.3 described
deferring a context menu that, on Windows, was never raised at press.

Both were resolved by reading the pinned source rather than by deciding
anything. `context_menu_on_mouse_up` defaults to `BUILDFLAG(IS_WIN)` and
`WebFrameWidgetImpl::HandleMouseUp` raises the menu when it is set, so on
Sunshine's platform the menu request arrives *after* the release — carrying
Chromium's own hit test of what is under the pointer. Patch 0017 decides there:
one moment, one outcome, and the suppression list answered with the browser's
own data instead of a second hit test. Nothing is deferred, because nothing was
raised early.

The 200 px threshold this gate tests is the number the owner chose after 32 px
proved uncomfortable, and the gate is where that choice becomes falsifiable
rather than a constant in prose.

RV-10 and RV-11 are the runtime half of the asset overlay, and they exist because
the overlay's failure mode is silence. `scripts/verify_asset_overlay.py` proves
the committed icon is a valid icon and `scripts/verify_pinned_upstream.py` proves
the destination still exists upstream, and neither can prove `rc.exe` linked it
into the executable.

**Half of RV-10 is now automated, and it is worth being exact about which half.**
Section 1's icon row answers *presence*: the image data in `chrome.exe`'s
application icon resource is the image data of the committed `.ico`, so a build
that shipped Chromium's blue sphere fails on the build machine rather than
waiting for someone to look. RV-11 has no such row — `mini_installer.exe` is not
read — so it remains wholly manual.

What is left to RV-10 is *appearance*, which no resource comparison reaches. The
automated row compares bytes, and bytes are identical to themselves whether the
artwork is right or wrong; it also says nothing about which entry the shell
actually asks for. Windows selects an icon entry by exact pixel match and
rescales the nearest one when there is none, so Explorer's list view, the
taskbar and a pinned shortcut do not all ask for the same size, and a shortcut
can carry an icon of its own regardless of what the binary holds. Looking at
three sizes and finding all three crisp is the observation that establishes the
set is right and reaching the shell, and it is not something section 1 can do.

## 3. Visual

| # | Step | Expected |
| --- | --- | --- |
| RVV-1 | New Tab at 533 px, 768 px and 933 px width | The wordmark scales fluidly and does not clip or wrap |
| RVV-2 | New Tab in light and dark | Both use the design-system tokens; neither hardcodes a colour |
| RVV-3 | Keyboard-only traversal of the New Tab page | Focus is visible at every stop and reaches the search field |
| RVV-4 | The bookmark bar's Sunshine button in light and dark | The glyph resolves `kColorBookmarkButtonIcon` in both, the same as the overflow button beside it; it is never a fixed colour that survives the theme change |
| RVV-5 | Keyboard-only traversal of the bookmark bar | The Sunshine button is the first stop, matching where it is drawn — the child order in `Init()` is the focus order |

`docs/DESIGN_SYSTEM_CONTRACT.md` owns the token rules; RVV-2 checks that the built
page actually resolves them, which `scripts/verify_design_tokens.py` cannot do
from source.

### Why the gates are prefixed

They used a bare `R` series and a bare `V` series for one night.
`docs/DESIGN_SYSTEM_CONTRACT.md` numbers its own rules in the `R` series, `R` is
a family `scripts/trace_invariants.py` knows, and the tracer promptly reported
this document's gates as declared by both — so an `Enforces:` line naming one of
them named two different rules at once. The `V` series failed the opposite way:
`V` belongs to no family, so those gates could never be claimed by any check at
all. One series resolved to the wrong document and the other was invisible.

The tokens are deliberately not repeated in this paragraph. `declared()` counts
an identifier wherever it appears, including inside a note explaining that it
was withdrawn, so spelling them out here would re-create the collision the
paragraph is about.

`RV` and `RVV` are registered families, and `docs/ACCEPTANCE_SUITES.md` §2
already stated the rule this broke: every prefix must be distinct from every
other and from the families the tracer knows.

## 4. Recording the result

Evidence lives with the run, not in prose. For each gate record:

```text
gate       RV-1..RV-38, RVV-1..RVV-5
result     PASS | FAIL | NOT RUN
build      workflow run number and commit sha
observed   what was actually seen, when it was not simply the expected text
```

A manifest's `verification` field may be advanced only when every gate for that
module is `PASS`. `scripts/validate_first_party_modules.py` already refuses
`status: runtime_verified` unless `native_build` and `runtime` are both
`passed`, so the manifest cannot claim more than the evidence supports.

## 5. What has been run

**Section 1 has.** Build #16 (run `32045348048`, commit `900d747`) is the first
run of `scripts/verify_installed_build.py` against real output, and it exited 0
on the build machine. Every check in section 1 therefore passed on the artifact,
including the two that cannot be answered anywhere else: the configuration GN
actually used carries ADR 0004's codec arguments and no sandbox- or
isolation-disabling switch, and Windows registers no Sunshine URL protocol.
SECA-11 is the first class-B acceptance criterion in this contract set to be
decided against a real build rather than specified.

**No manifest verification state is advanced by that**, and the distinction
matters. `verification.native_build` is a claim about a *module*, not about the
build: `sunshine-new-tab` has a patch in the stack and `sunshine-workspace` has
none, so a single build result cannot discharge both. Advancing either field
needs a decision about what `native_build` asserts for a module with no native
code yet, which is a product question rather than an evidence question.

**Build #27 compiled the module home and the bookmark bar button.** Run
`32252703932`, commit `8a30d5a`: `Build Succeeded: 1161 steps` in 23m10s, and
`mini_installer.exe` was produced. That is the first native build containing
patches 0007 and 0008, so it is the first evidence that the fourth surface
compiles, that one grd can serve four surfaces, and that the bookmark bar
change is valid against the pinned `bookmark_bar_view.cc`. Every prior claim
about those patches was `git apply` succeeding, which is placement and not a
compiler.

**The same run failed its verification step, on the icon.**
`verify_installed_build.py` reported `chrome.exe` carrying no `RT_GROUP_ICON`.
That is either a real finding — the application icon never reached the binary,
which would also mean RV-10 fails — or a defect in the check, whose ctypes
enumeration had never executed anywhere until that run. It could not tell those
apart, so it said the stronger thing, and saying the stronger thing was wrong.

The check reads `RT_VERSION` as a control before concluding anything:
`check_version_resource` reads chrome.exe's VERSIONINFO through `version.dll`
and passes, so a resource enumeration that cannot see `RT_VERSION` is not
reading the binary and must say so about itself rather than about the build.

**Build #28 answered it: the control passed and the icon was still not found**
— `chrome.exe carries RT_VERSION but no RT_GROUP_ICON`. Which narrowed the
question to one place, and the answer was in `chrome/app/chrome_exe.rc`.

That file writes `IDR_MAINFRAME ICON "theme\chromium\win\chromium.ico"`, and
`IDR_MAINFRAME` is defined in none of the three headers it includes —
`chrome_exe_resource.h` holds only Visual Studio's APSTUDIO boilerplate. **An
undefined identifier in a `.rc` file is a string resource name.** So every icon
in chrome.exe is named, not numbered, and the reader kept only the integer
names, on a written assumption that "this project's icons do not" use strings.
It dropped all of them, then reported the browser as having no application
icon.

Two pure functions now carry the parts that were wrong, and both are tested off
Windows: `resource_name()` applies the `MAKEINTRESOURCE` overload instead of
discarding half of it, and `application_icon_name()` implements the rule
`chrome_exe.rc` states — "the lowest ID … and its resource name should be
alphabetically less than the name of any other icon resource" — where `min()`
over integers had implemented only the first half.

**Build #29 passed it.** Run `32258004069`, commit `edf6636`:

```text
PASS  chrome.exe carries the Sunshine icon -- application icon is group
      IDR_MAINFRAME; 16px, 32px, 48px, 256px match ADR 0008
Built browser matches the contracts.
```

Two things are now established that were not before. **`rc.exe` did link
Sunshine's icon** — all four images in the binary are byte-identical to the
committed `.ico`, so the asset overlay reaches the artifact and ADR 0008's gap
is closed on the automated side. And the group it found is named
`IDR_MAINFRAME`, a *string*, which is the same fact that had made the check
report nothing for two builds.

So both earlier failures were the check's, not the build's. The icon had been
correct since it was committed; nothing about the browser changed between #28
and #29.

This is also the first run in which `scripts/verify_installed_build.py` exits 0
against a build containing the module home and the bookmark bar button.

**RV-10 is still NOT RUN and none of this touches it.** Bytes are identical to
themselves whether the artwork is right or wrong, and Windows picks an entry by
exact pixel match and caches what it picked — so whether the icon *looks*
correct in Explorer's list view, on the taskbar and as a pinned shortcut is an
observation only a person can make. RV-11 gains nothing here at all:
`mini_installer.exe` carries a separate overlay file that no check reads.

**Build #33 compiled patches 0009 to 0016, all eight of them for the first
time.** Run `32323176049`, commit `ca1f5c0`: `Build Succeeded: 1194 steps` in
20m42s, `verify_installed_build.py` exited 0, and `mini_installer.exe` is
117.5 MB.

That is the largest first-compile surface this project has had — the Windows
install identity, 527 lines of renamed product strings, the module shell, the
mount port and its storage vocabulary, the shell's framing policy, and two
entry points — and with it, roughly 1,300 lines of TypeScript that upstream's
eslint and stylelint had never seen.

**It took three attempts and the two failures are worth keeping.** #31 died on
`stylelint`, `no-duplicate-selectors`: patch 0011 wrote a `.tab-button` rule and
patch 0012 wrote a second one beside it, each correct alone and wrong in sum.
#32 died on `clang`: `base::JSONReader::Read` exists but its `options`
parameter has no default here, and the symbol had been confirmed without the
signature being read. Both classes are now in
`docs/WINDOWS_CHROMIUM_BUILD.md`'s pre-build section, with the harnesses that
decide them off the build machine.

**What this does and does not establish.** It establishes that the stack
compiles, that four surfaces plus the shell share one grd, that the framing
policy in patch 0015 is valid C++ against the pinned tree, and that the
artifact still carries the Sunshine icon and registers no scheme. It
establishes **nothing about behaviour**: no gate below is discharged by a
compile, and the shell has still never been opened.

**What it unlocks is the owner's.** `mini_installer.exe` from this build is the
first installer containing the rename, the shell, the dock and the mount port,
so RV-26 to RV-30, RV-31 to RV-34, RV-35 to RV-37 and RV-38 are now *runnable*
rather than blocked. They need a person, and they are the whole of what stands
between this stack and evidence.

**Build #37 is the first compile of the gesture recogniser, the account
surface and the installer front-end.** Run `32437521316`, commit `8c5f64b`:
`Build Succeeded: 1708 steps` in 36m25s, and every step of the job passed.
Patches 0017, 0018 and 0019 and the whole of `installer/` had never been through
a compiler before this run — every claim about them was `git apply` succeeding
and a guard reading source, which is placement and vocabulary, not a compiler.

**It was an incremental build, and that belongs in the record.** The ninja
summary reads `local:1708 remote:0 cache:0 skip:84272`: 84,272 steps were
already up to date on a warm workspace and 1,708 ran. So 36 minutes is not
evidence that a clean Sunshine build takes 36 minutes, and nothing here says the
tree builds from scratch. What it does establish is that the 1,708 steps that
*did* run — the ones this stack changed — compile and link.

`verify_installed_build.py` passed every check on the artifact, including the
four that only a real build can answer: the GN configuration carries ADR 0004's
codec arguments, no sandbox- or isolation-disabling switch is present (SEC-1,
SEC-2), Windows registers none of the three Sunshine schemes (SEC-13), and
`chrome.exe` carries version `152.0.7977.42` and the Sunshine icon group at all
four sizes ADR 0008 requires.

**The installer front-end compiled and produced an artifact.**
`sunshine_setup.cpp` built clean, and `build_installer_frontend.ps1` wrote
`sunshine-setup.exe` at 117.8 MB with the engine's SHA-256 recorded as
`b93caab68e5e8d88ebe0c84d027794f6bb5989efa60a22c8d52184cb8c8828bd`. That is the
front-end carrying the engine it hashes, which is the arrangement
`docs/INSTALLER_UI_CONTRACT.md` requires; it is **not** evidence that the
installer's dialog appears or behaves, because nothing launched it.

**The payload was measured for the first time: 419.5 MB across 255 files.**
`measure_shipped_size.py` ran against real build output and the number is over
`docs/SIZE_BUDGET.md`'s own 250 MB investigation threshold, with `chrome.dll`
alone accounting for 283.6 MB of it. The breakdown is recorded in that document
rather than duplicated here.

**What it unlocks.** `mini_installer.exe` from this build is the first installer
containing the gesture recogniser and the account surface, so **RV-20 is now
runnable** — patch 0017 is in the binary and the gesture is dispatchable. It
needs a person with a page that has history in both directions, and it is the
first gate the gesture work can be judged by.

**What it does not establish.** No behaviour. The gestures have never been
performed, the account page has never been opened, the installer dialog has
never been shown, and no gate in section 2 or 3 is discharged by a build
succeeding.

**Build #40 compiled the New Tab background.** Run `32445665066`, commit
`6b86cc7`: patches 0002, 0020 and 0021 through the compiler for the first time,
all eight job steps green. The payload is unchanged at 419.5 MB across 255
files — which is the correct result and worth saying, because it is the
measurement that shows the feature ships nothing by itself. **The asset is not
in the build; it is a file the owner places afterwards.**

**It took three attempts, and both failures were the same kind of thing.** #38
died in `tsc` on a backtick inside an HTML comment: `app.html` is preprocessed
into a TypeScript template literal, where a backtick ends the string. #39 died
in `eslint` because a property the template binds had no declaration in
`static get properties()`, which made `lit-reactive-properties` and
`lit-property-accessor` fire together — one omission seen from two sides. Both
are now checks rather than notes, WA-1 and WA-2, and both are recorded in
`docs/WINDOWS_CHROMIUM_BUILD.md` as items 5 and 6.

Neither is a defect a compiler would have caught, and that is the general
point: **the New Tab page's source is generated before it is compiled**, so it
is judged by two toolchains this repository had no checks for until now.

**Nothing here is behaviour.** No background has been placed or displayed, and
`docs/NEWTAB_BACKGROUND_CONTRACT.md` §5 still holds in full.

**Build #41 compiled what four adversarial reviews changed.** Run
`32477837656`, commit `779ef04`, all eight steps green. That covers the
once-per-process availability probe, the warm call in `Browser`'s constructor,
the newly owned `new_tab_page_ui.cc`, the allowlist entry that the serving path
had been missing, and the page's conditional frame.

**The middle item is why this build's green means less than it looks.** Build
#40 was also green, on a feature that could not serve a single byte: the
allowlist rejected every request before the handler ran. A compile proves the
code is valid C++ and nothing about whether the browser does the thing. Every
gate below is still `NOT RUN`.

### Evidence

```text
gate       RV-7
result     PASS
build      run 32005990080, commit 6aa75ff
observed   the owner ran the installer from build #12 and reports the Sunshine
           wordmark in the New Tab logo slot
```

**Build #41 was run by the owner, and twenty-six gates passed.** Run
`32477837656`, commit `779ef04`. Before this, one gate of forty-three had ever
been run.

```text
PASS     RV-1, RV-2, RV-3, RV-4, RV-5, RV-6, RV-8, RV-9, RV-10, RV-11,
         RV-12, RV-21, RV-22, RV-24, RV-25, RV-27, RV-28, RV-32, RV-33,
         RV-34, RV-37, RV-38, RVV-1, RVV-2, RVV-3, RVV-4
FAIL     RV-20, RV-26, RV-29, RV-31, RVV-5
NOT RUN  RV-13, RV-14, RV-23, RV-30
BLANK    RV-15, RV-16, RV-17, RV-18, RV-19
```

**Block B passed entire — RV-1 through RV-4.** The sandbox is active, site
isolation is site-per-process, no isolation-disabling switch is on the command
line, and no Sunshine scheme resolves. Those are the four gates whose failure
ends a session, and they are the strongest result in this document: the
security posture is what the contracts describe, observed rather than argued.

**Two failures may be the sheet's fault rather than the build's.** RV-26 and
RV-29 are about install identity, and the sheet asserted
`%LOCALAPPDATA%\Sunshine\Application` unconditionally — but
`installer/sunshine_setup.cpp` chooses `FOLDERID_ProgramFiles` when the user
installs for all users, which the installer offers by design. A machine-wide
install would fail a gate written only for the per-user case. Which happened is
not yet known.

**The five BLANK rows are a defect in the sheet, not a result.** The owner
could not follow them. The document-surface instructions had been written from
the contract rather than from the page — they described building a hierarchy by
indentation, and the page builds it with an `Inside` selector — so they
described a screen that does not exist. Rewritten from the patch.

**No observations accompany any of this.** The sheet was returned as a saved
page, and a browser does not serialise typed text, so the results survived and
the notes did not. For the five failures that leaves the result without the
evidence, which is why none of them is diagnosed here.

**Build #42 is the merge, and it is the build the retest runs against.** Run
`32497978899`, commit `da64842` on `stable`, all eight steps green in 42
minutes. It carries nothing #41 did not, except the corrected gate sheet — the
merge added no code.

**Saying which build a result came from is the whole value of a result.** The
sheet's stamp read `#41 (779ef04)` while the browser being tested would be
#42, and a sheet that names the wrong build turns every row it collects into a
result about an unknown binary. The stamp is now `#42 (da64842)`.

**None of the five failures is fixed in #42.** RV-20, RV-31 and RVV-5 have had
no diagnosis and therefore no change; a second failure from them is expected,
not new information. RV-26 and RV-29 may pass, and if they do it is because the
sheet was corrected, not because the installer was.

**Build #44 is the one the retest runs against, and it carries the first
behaviour change since the sheet was written.** Run `32514342627`, commit
`377f9c5` on `stable`, eight steps green in 35 minutes. It contains the New Tab
background's `height`/`width` fix and the 100 MB cap; everything else is
unchanged from #42.

**So UG-3 is now a real gate rather than a known failure.** On #42 the
background frame was the replaced element's 300x150 default in a corner of the
window, because `iframe.css` sizes it with `width: inherit` from a host that
computed `auto`. Whether it fills the window in #44 is the one question this
build was made to answer, and nobody has looked yet.

**The sheet sat queued for six hours and fifty-three minutes before it could be
built at all.** The self-hosted runner was off; the job was not lost and was
picked up unchanged when it returned. Recorded because three earlier runs in
the same state were cancelled and re-dispatched, which discarded the wait
without shortening it -- run #17 waited 13h34m and then succeeded.

That is the whole of it, and the scope is the point. Build #12 was commit
`6aa75ff`, "Finish replacing ntp-logo" — the change that completed the wordmark
— so RV-7 is exactly the gate it can discharge.

It cannot discharge the two gates that look adjacent. `6aa75ff` precedes both
`803befe`, which enabled the codecs, and `77e4fb2`, which removed the infobar,
so **RV-5, RV-6 and RV-8 remain NOT RUN**: the binary that was launched did not
contain the code those gates are about. The first build that contains all three
is #15.

## 6. NOT VERIFIED

- **One of forty-three gates has been run.** RV-7 is recorded above. Every other
  gate in sections 2 and 3 is `NOT RUN`, so the codec, infobar, sandbox,
  isolation, scheme and visual gates are all still specification. What has
  changed since that sentence was first written is only the excuse: build #33
  produced an installer, so all but three of the remaining gates are runnable
  in one sitting and `docs/RETURN_RUN_SHEET.md` says in what order. The three
  that were not runnable were RV-20, RV-35 and RV-36; patch 0017 removes RV-20
  from that list, and that document says why the other two remain.
- The gates are specified against Chromium's internal pages at the pinned
  revision. `chrome://sandbox` and `chrome://process-internals` are debugging
  surfaces whose output format upstream may change without notice; a gate that
  cannot be read means `NOT RUN`, not `PASS`.
- No automated driver runs section 2. Doing so would need a browser automation
  dependency, and `scripts/verify_architecture.py` currently rejects the
  `package.json` any such toolchain would bring. That is a real constraint, not
  an oversight — see `docs/decisions/0006-module-execution-model.md` for the
  same tension in its larger form.
