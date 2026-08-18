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

The last one is the reason this runs on Windows rather than in the guard job.
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
| RV-10 | Look at `chrome.exe` in Explorer, on the taskbar, and as a pinned shortcut | The Sunshine icon, at every size; Chromium's blue sphere appears nowhere | ADR 0008 |
| RV-11 | Look at `mini_installer.exe` in Explorer | The Sunshine icon | ADR 0008 |

RV-6 is not redundant with RV-5. `ffmpeg_branding="Chrome"` changes which FFmpeg
sources are compiled, and a regression there would remove the codecs the project
had before the decision rather than the ones it added.

RV-4 is the runtime half of SEC-13 that neither the source guard nor the registry
check covers: a scheme can be registered inside the browser without touching the
registry, and the omnibox is where a user would meet it.

RV-10 and RV-11 are the runtime half of the asset overlay, and they exist because
the overlay's failure mode is silence. `scripts/verify_asset_overlay.py` proves
the committed icon is a valid icon and `scripts/verify_pinned_upstream.py` proves
the destination still exists upstream, but neither can prove `rc.exe` linked it
into the executable — a build that quietly shipped Chromium's icon would pass
both. RV-10 asks for three sizes because Windows selects an icon entry by exact
pixel match: Explorer's list view, the taskbar and a pinned shortcut do not all
ask for the same one, so a single correct-looking icon is not evidence the set is
right.

## 3. Visual

| # | Step | Expected |
| --- | --- | --- |
| RVV-1 | New Tab at 533 px, 768 px and 933 px width | The wordmark scales fluidly and does not clip or wrap |
| RVV-2 | New Tab in light and dark | Both use the design-system tokens; neither hardcodes a colour |
| RVV-3 | Keyboard-only traversal of the New Tab page | Focus is visible at every stop and reaches the search field |

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
gate       RV-1..RV-11, RVV-1..RVV-3
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

- **One of fourteen gates has been run.** RV-7 is recorded above. Every other
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
