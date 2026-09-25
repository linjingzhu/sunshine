# Native Chromium Windows build

## Purpose

This pipeline builds the actual Chromium downstream. It does not use Electron, CEF, Qt WebEngine, Tauri, or an OS WebView.

## Required machine

**There is no runner to register any more.** Every workflow file was removed
and the repository's Actions setting was disabled on 2026-09-25 on the owner's
instruction (`.ai/reports/2026-09-25-rules-and-actions-result.md`). A build is
started by hand on the machine, as § *Running a build* describes, and the
labels this section used to ask for (`self-hosted`, `Windows`, `X64`,
`sunshine-chromium`) no longer mean anything. The machine requirements below
are unchanged: they were never about GitHub.

The machine must have:

- Windows 11 x64;
- at least 180 GB free on a persistent NTFS build volume;
- **PowerShell 7 or newer** (`pwsh`), which the build step requires and a stock Windows install does not include — `winget install Microsoft.PowerShell`;
- Visual Studio 2022 with Desktop development with C++;
- Windows 11 SDK;
- Python 3 and Git;
- Chromium `depot_tools` on `PATH`;
- long paths enabled.

GitHub-hosted Windows images ship `pwsh` preinstalled, which is why this requirement stayed invisible until the pipeline first ran on a real machine. Without it the build stops in about a minute, and the script says so by name rather than failing obscurely.

Two machine environment variables, both persistent (`setx`, or System
Properties → Environment Variables), not just set in one shell:

| Variable | Value | Why |
| --- | --- | --- |
| `SUNSHINE_CHROMIUM_WORKSPACE` | the persistent workspace, e.g. `F:\sunshine-chromium` | The script refuses to run without it. A Chromium checkout is ~100 GB and must not live anywhere that gets cleaned up. |
| `DEPOT_TOOLS_WIN_TOOLCHAIN` | `0` | Without it `gclient sync` tries to fetch a Google-internal toolchain and fails. |

## Before starting a build, read the pinned tree and run the toolchain

A build is six hours on the machine the owner also works on, so the question
worth asking before every build is *what would waste it*. Three kinds of
failure can be found in about twenty minutes, off the build machine entirely,
and the first time this was done it found three real ones.

**1. Symbols, not just paths.** The guards read the patch stack; none of them
reads Chromium's headers, so a C++ patch naming an API that does not exist at
the pin passes everything and dies in the compiler. `raw.githubusercontent.com`
is reachable from an agent session even where `chromium.googlesource.com` is
not, so any header can be read directly:

```text
curl -s https://raw.githubusercontent.com/chromium/chromium/<pin>/base/values.h
```

Before build #31 this found three in one 40-line function: `base::Value::Dict`
and `base::Value::List` are `base::DictValue` and `base::ListValue` at this
revision with no compatibility alias, and `GURL::path_piece()` does not exist
because `path()` already returns a `std::string_view`. Each would have ended
the build.

**Grep for the name, then read the whole declaration.** Build #32 died on the
same function anyway, because `base::JSONReader::Read` exists but its `options`
parameter has no default here — the name was confirmed and the signature was
not. Reading four more lines of `base/json/json_reader.h` would have caught it,
and would also have found `ReadDict()`, which is what the call should have been
in the first place. A grep answers *is it there*; only the declaration answers
*can I call it that way*.

**Also confirm the include a generated header comes from.** A `.mojom.h` is not
in the source tree and will 404; find an upstream `.cc` that uses the same
symbol and copy its include line. `new_tab_page_ui.cc` is the worked example
for `network::mojom::CSPDirectiveName`.

**2. TypeScript, actually compiled.** `tsc` type-checks the surfaces without a
Chromium checkout. Use Chromium's own settings from
`tools/typescript/tsconfig_base.json` rather than a guess — it is stricter
than the obvious defaults, in particular `noUncheckedIndexedAccess` and
`noPropertyAccessFromIndexSignature`. Stub `//resources/js/load_time_data.js`
and `/strings.m.js` through `paths`.

**3. eslint, with Chromium's own configuration.** One of two linters that run
*inside* `build_webui()`. `tools/web_dev_style/eslint.config.mjs` can be used
directly by rewriting its four plugin imports to locally installed copies of
`@typescript-eslint/eslint-plugin`, `@typescript-eslint/parser`,
`@stylistic/eslint-plugin` and `eslint-plugin-lit`. Approximating the rules by
hand is not the same thing and misses the project-specific
`no-restricted-syntax` cases.

**4. stylelint, likewise.** The CSS is linted too, by a separate `lint_css`
action, and **this is the step that failed build #31** — `no-duplicate-selectors`
on a `.tab-button` block a later patch added beside the one an earlier patch
had written. Nothing else in this project would ever have noticed: two patches
each producing a valid rule, and the defect existing only in their sum.

Use `ui/webui/resources/tools/stylelint.config_base.mjs` with its one plugin
import rewritten to a local `@stylistic/stylelint-plugin`, and run it over
**every** surface's stylesheet at once rather than the one just edited — the
build lints them as one list, and a duplicate selector is a property of a whole
file rather than of a hunk.

The lesson is more general than the rule: **a patch stack can be correct patch
by patch and wrong in its sum**, and every check here reads the *reconstructed*
file for that reason.

**5. A Lit template's `.html` is TypeScript, and a backtick in it is code.**
**This is the step that failed build #38.** Chromium preprocesses such a file
into a `.html.ts` whose entire body is one template literal, so a backtick ends
the string and `${` starts an expression. An HTML *comment* quoting an
attribute name in backticks produced `TS1005: ';' expected` in generated
`app.html.ts` — a syntax error in a file no one had written, reported at a line
that does not exist in the source anyone edited.

The signal had been there and was not read: the upstream comment that patch
replaced wrote its own binding as a backslash-escaped dollar, `\${...}`, which
is only necessary if the file is a template literal.

`scripts/verify_web_asset_security.py` refuses a backtick **inside an HTML
comment** on a line the stack adds, which is WA-1.

The scope was wrong first and is worth keeping as written. The original rule
refused a backtick on *any* added `.html` line — broader than the defect — and
it promptly blocked correct work: `${cond ? html`…`  : ''}` is how a Lit
template renders nothing, upstream's own `app.html` is built from it, and the
patch that stopped creating a background frame when no background exists could
not pass. Template syntax lives outside comments and prose lives inside them,
and only prose becomes punctuation by mistake.

**6. eslint runs on the generated TypeScript too, with Lit-specific rules.**
**This is the step that failed build #38's second attempt**, after the
backtick was fixed and `tsc` passed. Two errors, on one property:

```
app.html.ts  Missing Lit reactive property declaration for 'sunshineBackgroundPath_'
app.ts       Unnecessary 'accessor' keyword when declaring regular
             (non Lit reactive) property 'sunshineBackgroundPath_'
```

`@webui-eslint/lit-reactive-properties` holds that every property a template
reads is declared in `static get properties()`;
`@webui-eslint/lit-property-accessor` then holds that `accessor` belongs only
on a property that is. **They are one omission seen from two sides**, and
reading them as two problems is how the fix gets guessed at rather than made.
A property that never changes still needs the declaration, because the rule is
about what the template reads and not about what varies.

WA-2 holds it: a `${this.name}` binding the stack adds to a template must have
a matching declaration in the added lines of the sibling `.ts`. Bindings on
context lines are upstream's and are not checked — a rule that demanded the
stack re-declare those would fail on every patch that touches a template.

The four together took about half an hour and found four real defects across
two build attempts. A build takes six.

**Prove each harness before trusting it.** Inject a fault and check it fails.
A checker that passes because it matched no files is worse than no checker,
and both of these can do that silently — `tsc` on an empty include list and
`eslint` on a glob that matches nothing both exit 0.

None of this is a substitute for the build. It removes the failures that are
decidable without one, which is most of the ones this project has actually hit.

## Why the build is not on a GitHub-hosted runner

It was asked for, and the answer is arithmetic rather than preference.

| | This build needs | A GitHub-hosted standard runner offers |
| --- | --- | --- |
| Free disk | 180 GB | 36 GB after deleting the image's unused toolchains, measured |
| Cores | 12, for the six-hour figure below | 4 |
| Wall clock | ~6 h at 12 cores, so ~18 h at 4 | 6 h, a hard per-job ceiling |

Larger runners would close the first two rows and are configured in
**organisation** settings; this repository belongs to a personal account, so
there is no place to enable them. Nothing here is tunable: two of the three
rows are out by more than an order of magnitude, and the third is a limit the
job cannot ask to have raised.

A hosted compile therefore needs a machine this project rents rather than one
GitHub provides. That was a cost decision and the owner has now made a larger
one: **there is no CI at all.**

### What used to run on a hosted runner, and what replaced it

**Nothing runs on GitHub any more.** Three workflow files were removed and the
repository's Actions setting was disabled on 2026-09-25
(`.ai/reports/2026-09-25-rules-and-actions-result.md`). The history below is
kept because it is why, and because one of the three was doing something no
other check does.

Hosted Actions had already stopped working on **2026-09-08**: every push
produced a job that finished in two to four seconds with no runner assigned, no
step recorded and no log to download, and a red check that meant nothing. The
cause was an account-level condition this repository cannot influence.
`architecture-guard-hosted.yml` was removed for it on 2026-09-13; the other two
were removed with Actions itself twelve days later.

**Two checks lost their only automated home, and both are worth naming rather
than discovering later:**

- `scripts/compile_check_installer.py` cross-compiles the installer front-ends
  with `x86_64-w64-mingw32-g++`. The build machine has MSVC and no mingw, so
  the self-hosted guard reported `NOT CHECKED` there by design and the hosted
  guard was the only place that could install it. It runs only where a
  developer runs it now — and in fact it never once ran in CI, because the
  hosted guard was already dead when it was written.
- `patch-apply-hosted.yml` answered the one question no offline guard can:
  whether the stack applies to the real upstream tree. **That question now has
  a better answer than the workflow was giving it**, and it is the reason
  removing the workflow cost nothing: `python3
  scripts/verify_pinned_upstream.py --source github` fetches each upstream file
  the stack touches from the mirror and applies the whole series, in about a
  minute, from any development session. Run it before every build; the
  workflow's own last successful run was 2026-09-06.

For the record of what that workflow did: it cloned `src` alone at the pinned
revision -- one revision deep, no DEPS, no submodules -- and applied the whole
stack to it. Every upstream file the stack touches is under `chrome/` or
`tools/`, so the dependency tree a compile would need is never fetched.

Measured on run 1, `5899580`:

| | |
| --- | --- |
| `src` at `152.0.7977.42` | 6.8 GB, 497,194 files |
| Clone | 5 min 50 s |
| Applying all thirteen patches | under one second |
| Whole job | 6 min 53 s |
| Free disk left | 29 GB |

The clone was the job. The thing the job existed to do cost nothing, which was
the argument for running it on every push that touched a patch.

It answered the one question no offline guard can. `verify_patch_integrity.py`
checks each hunk's arithmetic, `verify_patch_references.py` replays hunks
against files the stack itself creates, and `verify_pinned_upstream.py` asks
whether cited upstream files exist -- but none of them reads an upstream file's
*contents*, because those are not in this repository. Until this job existed,
the first thing that ever read a patch against the real tree was `git apply` on
the build machine, and build #18 died there twenty minutes in. That is the
failure `verify_pinned_upstream.py --source github` now stands in front of, and
the only thing lost with the workflow is that nobody is made to run it.

**It is not a build and does not stand in for one.** A stack that applies can
still fail on eslint, on `gn`, or in the compiler. What it removes is the class
of failure that used to cost a whole build slot to discover.

### What run 1 established

Patches 0009 to 0013 had never touched a real Chromium tree. They apply.

It also confirmed a count that had only ever been asserted.
`scripts/patch_manifest.py` reports 16 upstream files exclusively owned by the
stack; after applying, `git status` in the checkout listed exactly those 16 as
modified, plus the four Sunshine directories the stack creates and nothing
else. The manifest's model of what this project touches upstream is now
git's answer as well as its own.

## Authenticate to googlesource before the first sync

Syncing Chromium clones well over a hundred dependency repositories. Anonymous requests share one server-side quota pool, and a multi-core machine exhausts it:

```
remote: RESOURCE_EXHAUSTED  subject: "shared/shared_anonymous"
remote: "Short term server-time rate limit exceeded"
fatal: The requested URL returned error: 429
```

Sign in once at <https://chromium.googlesource.com/new-password> and run the credential snippet it generates. This moves the machine out of the shared anonymous pool and is the reliable fix.

The bootstrap also bounds concurrency with `--jobs`, defaulting to 8 rather than gclient's one-job-per-core. Lower it further if an unauthenticated machine still hits 429.

An interrupted sync resumes: everything already fetched stays in the workspace. Delete `_bad_scm` between attempts if it accumulates; gclient moves conflicting directories there when a clone fails partway.

A dependency left half-cloned by an interrupted sync will not reconcile itself — the next run stops with `Unrecognized error, please merge or rebase manually`. The pipeline passes `--force --reset` to gclient for exactly this, since the pinned revision always wins in a build-owned workspace. If a dependency is damaged beyond that, delete its directory under `src/third_party/` and sync again; gclient re-clones it.

## Profile-guided optimisation

`is_official_build=true` enables PGO, and GN generation fails without the profile it expects:

```
Command: .../tools/update_pgo_profiles.py --target win64 get_profile_path
Returned 1.
```

gclient does not fetch those profiles unless asked, so the bootstrap sets `checkout_pgo_profiles` in the solution spec and writes the spec on every run — an existing workspace picks the change up on its next sync. Setting `chrome_pgo_phase=0` would also silence the error, at the cost of quietly weakening the release configuration this repository pins; that is not the trade made here.

## Workspace ownership

The Chromium workspace belongs to the build, not to a person. The build script runs `bootstrap_chromium.py --reset`, which discards modifications to tracked upstream files so a changed patch stack does not stop the next build for manual cleanup.

`--reset` never touches untracked files, so `out/Sunshine` survives and the incremental build is preserved. Running the bootstrap without `--reset` keeps the protective default and refuses to discard anything.

Do not use this workspace for manual Chromium edits you want to keep.

## Sharing the machine

`autoninja` schedules roughly core count plus two jobs, which leaves a workstation unusable for the length of a build. `scripts/build_chromium_windows.ps1` takes `-NinjaJobs <n>`, also readable from `SUNSHINE_NINJA_JOBS`, that caps it.

Leave it unset on a dedicated build machine. On a machine that is also in daily use, keep two to four threads free — on 12 cores, `8` keeps the desktop responsive and costs roughly half again the compile time. Starting the build at below-normal priority helps further.

## The machine must not sleep during a build

**Nothing keeps it awake.** A build holds no power request of its own, so on an
idle desktop a six-hour compile is interrupted by the desktop. On mains power:

```powershell
powercfg /change standby-timeout-ac 0
powercfg /change hibernate-timeout-ac 0
powercfg /requests
```

The last command shows what is currently holding the machine awake, and is
worth reading before and after.

**This section used to be six times this length**, and the rest of it was about
a queue that no longer exists: how to tell a `queued` run from a sleeping
runner, that GitHub cancels a run after 24 hours in `queued` (build #48, run
`33401443955`, cancelled three seconds past the day mark with nobody
cancelling it), how to restart `Runner.Listener`, and a correction to a
`svc.cmd` invocation this document had guessed at from the wrong platform's
documentation. With Actions disabled and every workflow removed there is no
queue, no runner process and no service. A build now either runs in the shell
you started it in or it does not, which removes the entire class of failure
that paragraph existed for — and removes the 24-hour deadline with it.

The one thing that carried over is above: the machine still sleeps, and a hand-
started build is just as vulnerable to it as a queued one was.

## Running a build

One command, in **PowerShell 7**, from the repository checkout on the build
machine:

```powershell
pwsh -NoProfile -File scripts/build_chromium_windows.ps1
```

That is `build_command` in `.ai/PROJECT_CONTEXT.md` § *Facts the checks read*,
and it is the whole of it. The script does what the workflow used to do, in the
same order, because the workflow only ever called it:

1. validate PowerShell, Windows, the workspace variable and the free disk;
2. fetch/sync pinned Chromium;
3. apply the ordered Sunshine patch stack;
4. generate an optimized non-component Release build;
5. build `chrome` and `mini_installer`;
6. write the unsigned installer and the JSON size report under `artifacts/`.

Two things the workflow gave for free and a hand-run build does not:

- **The artifacts are only on that machine.** There is no 14-day upload any
  more. `artifacts/` is gitignored, so the installer has to be copied somewhere
  deliberately or it exists on one disk.
- **Nothing records that the build happened.** A run number used to be the name
  everything else cited — `docs/RUNTIME_VERIFICATION.md` § 4 asks for "workflow
  run number and commit sha" beside every gate result. With no run number,
  **cite the commit sha**, and `scripts/build_gate_sheet.py`'s `BUILD` stamp is
  now a number someone has to keep by hand.

Useful parameters, both also readable from the environment:

| Parameter | When |
| --- | --- |
| `-NinjaJobs <n>` | The machine is also being worked on. `autoninja` otherwise schedules roughly core count plus two and leaves nothing for interactive use. |
| `-Workspace <path>` | Overrides `SUNSHINE_CHROMIUM_WORKSPACE` for one run. |

`SUNSHINE_ACCOUNT_CLIENT_ID` is read from the environment on purpose and never
passed on the command line, where Windows shows it to every process that can
enumerate them. Empty is the normal case.

### If it fails, read these in this order

1. **Before the compile starts** — the script's own `throw`. It names the
   requirement (PowerShell version, Windows, workspace, free disk) rather than
   failing obscurely, so the message is the answer.
2. **During `git apply`** — the patch stack does not fit the pinned tree. Do not
   debug this on the build machine: `python3 scripts/verify_pinned_upstream.py
   --source github` answers the same question in about a minute from anywhere,
   and § *Why the build is not on a GitHub-hosted runner* explains why that is
   now the only thing asking it.
3. **In `gn gen`** — a `BUILD.gn` edit in the stack. `gn` failures name the file
   and line.
4. **In the compiler** — the first real compile of the change. **This is the
   failure mode with no offline substitute**: nothing in this repository
   compiles Chromium, and every guard here reads the patch rather than the
   result.

## Security and distribution

The artifact is an unsigned internal test build. It is not a public release and must not be represented as code-signed or trusted by Windows SmartScreen.

## Remaining visual gate

After installation, verify:

- the omnibox and tabs remain visible;
- New Tab shows SUNSHINE, search, and frequent sites;
- search and direct URL navigation work;
- light and dark themes;
- narrow window and 200% page zoom;
- no overlap, clipped focus ring, or unreadable foreground.

## Media codecs

`scripts/build_chromium_windows.ps1` sets `proprietary_codecs=true` and
`ffmpeg_branding="Chrome"`, so the build decodes H.264 and AAC.

Neither is Chromium's default. `proprietary_codecs` derives from
`is_chrome_branded`, which Sunshine does not set, so an unmodified build cannot
play most web video — a Stage 1 acceptance item was determined by a build flag no
document mentioned until `docs/ACCEPTANCE_SUITES.md` traced it here.

Turning it on is a licensing decision, not an engineering one, and it is
recorded in `docs/decisions/0004-media-codecs.md` under an explicit
**personal-use premise**: the owner builds Sunshine for themselves and does not
distribute it. Read that ADR before changing the flag in either direction.

**The decision does not travel with the artifact.** An installer produced under
it is not licensed for redistribution by virtue of having been built. Before
publishing a release or handing a build to anyone else, revisit the ADR; the
honest default at that point is to turn the flag back off unless a licence has
been obtained.
