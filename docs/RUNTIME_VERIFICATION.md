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
| RV-20 | Press the right mouse button in page content and drag left 200 px, then release; repeat dragging right; repeat with a drag of 50 px | Left goes back, right goes forward, and the short drag shows the context menu instead. **Cannot run: no gesture recogniser exists** — see below | GESTURE contract §3.2 |
| RV-21 | Show the bookmark bar and look at its leading edge | One Sunshine button sits there, left of the saved tab group button, tooltip "Sunshine modules". Its glyph is not the grid the tab group button uses | ADR 0014 §5, patch 0008 |
| RV-22 | Click that button, then ctrl-click it | The first opens `chrome://sunshine-modules` in the current tab; the second opens it in a new background tab. Disposition follows the modifier, as it does for every other button on this bar | ADR 0014 §2 |
| RV-23 | On `chrome://sunshine-modules`, compare the left column against `first_party/registry.json` | The same modules, the same order, and the count in the heading matches. This is the gate the sync guard cannot reach: the guard compares the patch to `first_party/`, not the running page to either | patch 0007, `verify_module_registry_sync.py` |
| RV-24 | Select each module in the left column | Its declared network, filesystem and credential values are the manifest's own words, and a value other than `deny`/`none`/no is the one that stands out | MODULE HOME §2 |
| RV-25 | Narrow the window until the bookmark bar overflows its buttons | The Sunshine button keeps its place at the leading edge and is never drawn over the button beside it | patch 0008, `GetMinimumSize()` |

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

**RV-20 cannot run, and will not be able to for some time.** There is no gesture
recogniser: `downstream/patches/series` contains no gesture patch and
`first_party/commands.json` registers no gesture command, so the 200 px
threshold this gate tests exists only in `docs/GESTURE_CONTRACT.md`. It is
written now because the gate is what makes the specification concrete — 200 px
is the number the owner chose after 32 px proved uncomfortable, and a gate is
where that choice becomes falsifiable rather than a constant in prose. Two
things block the recogniser, both recorded in
`docs/decisions/0012-gesture-input-contribution-point.md` and both needing an
owner's decision rather than an implementer's: §3.1 evaluates suppression "once,
at button press", which the browser process cannot do because it holds no DOM to
hit-test against until `ContextMenuParams` arrives at release; and §3.3 describes
deferring a context menu that, on Windows, was never raised at press.

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
gate       RV-1..RV-25, RVV-1..RVV-5
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

**RV-10 is still NOT RUN and this does not touch it.** Whether the icon in the
binary is Sunshine's is what the next run decides; whether it *looks* right at
three sizes is a person's job either way.

### Evidence

```text
gate       RV-7
result     PASS
build      run 32005990080, commit 6aa75ff
observed   the owner ran the installer from build #12 and reports the Sunshine
           wordmark in the New Tab logo slot
```

That is the whole of it, and the scope is the point. Build #12 was commit
`6aa75ff`, "Finish replacing ntp-logo" — the change that completed the wordmark
— so RV-7 is exactly the gate it can discharge.

It cannot discharge the two gates that look adjacent. `6aa75ff` precedes both
`803befe`, which enabled the codecs, and `77e4fb2`, which removed the infobar,
so **RV-5, RV-6 and RV-8 remain NOT RUN**: the binary that was launched did not
contain the code those gates are about. The first build that contains all three
is #15.

## 6. NOT VERIFIED

- **One of twenty-three gates has been run.** RV-7 is recorded above. Every other
  gate in sections 2 and 3 is `NOT RUN`: builds #15 and #16 succeeded and
  neither has been launched, so the codec, infobar, sandbox, isolation, scheme
  and visual gates are all still specification.
- The gates are specified against Chromium's internal pages at the pinned
  revision. `chrome://sandbox` and `chrome://process-internals` are debugging
  surfaces whose output format upstream may change without notice; a gate that
  cannot be read means `NOT RUN`, not `PASS`.
- No automated driver runs section 2. Doing so would need a browser automation
  dependency, and `scripts/verify_architecture.py` currently rejects the
  `package.json` any such toolchain would bring. That is a real constraint, not
  an oversight — see `docs/decisions/0006-module-execution-model.md` for the
  same tension in its larger form.
