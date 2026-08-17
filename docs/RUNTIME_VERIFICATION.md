# Runtime verification

## Why this exists

The contract set declares 418 invariants and enforces 33. Most of the remainder
are class B — decidable only with a built browser. A browser has existed since
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
| R1 | Open `chrome://version` | The command line contains no `--no-sandbox`, no `--single-process`, no `--disable-site-isolation-trials` | SEC-1, SEC-2 |
| R2 | Open `chrome://sandbox` | Every renderer row reports a sandbox as active | SEC-1 |
| R3 | Open `chrome://process-internals` | Site isolation mode is site-per-process, and two cross-site frames occupy different processes | SEC-2 |
| R4 | Type `sunshine://anything` in the omnibox | Treated as a search, not a navigation — the scheme does not resolve | SEC-13 |
| R5 | Play an H.264/AAC video | Decodes and plays | ADR 0004 |
| R6 | Play a VP9 or AV1 video | Decodes and plays — the codec change must not have cost the royalty-free path | ADR 0004 |
| R7 | Open a new tab | The Sunshine wordmark occupies the logo slot; Chromium's own logo is absent | patch 0002 |
| R8 | Open a new tab on a keyless build | No infobar reports missing Google API keys | patch 0003, ADR 0005 |
| R9 | Search from the New Tab page | Chromium's own search handling runs; no Sunshine interposition, no forced startup URL | `verify_architecture.py` startup-URL rule, at runtime |

R6 is not redundant with R5. `ffmpeg_branding="Chrome"` changes which FFmpeg
sources are compiled, and a regression there would remove the codecs the project
had before the decision rather than the ones it added.

R4 is the runtime half of SEC-13 that neither the source guard nor the registry
check covers: a scheme can be registered inside the browser without touching the
registry, and the omnibox is where a user would meet it.

## 3. Visual

| # | Step | Expected |
| --- | --- | --- |
| V1 | New Tab at 533 px, 768 px and 933 px width | The wordmark scales fluidly and does not clip or wrap |
| V2 | New Tab in light and dark | Both use the design-system tokens; neither hardcodes a colour |
| V3 | Keyboard-only traversal of the New Tab page | Focus is visible at every stop and reaches the search field |

`docs/DESIGN_SYSTEM_CONTRACT.md` owns the token rules; V2 checks that the built
page actually resolves them, which `scripts/verify_design_tokens.py` cannot do
from source.

## 4. Recording the result

Evidence lives with the run, not in prose. For each gate record:

```text
gate       R1..R9, V1..V3
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

## 6. NOT VERIFIED

- **Nothing in section 2 or 3 has been run.** Build #12 produced an installer
  that nobody executed; builds #15 and #16 succeeded and nobody has launched
  either.
- The gates are specified against Chromium's internal pages at the pinned
  revision. `chrome://sandbox` and `chrome://process-internals` are debugging
  surfaces whose output format upstream may change without notice; a gate that
  cannot be read means `NOT RUN`, not `PASS`.
- No automated driver runs section 2. Doing so would need a browser automation
  dependency, and `scripts/verify_architecture.py` currently rejects the
  `package.json` any such toolchain would bring. That is a real constraint, not
  an oversight — see `docs/decisions/0006-module-execution-model.md` for the
  same tension in its larger form.
