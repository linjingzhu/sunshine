# Native Chromium Windows build

## Purpose

This pipeline builds the actual Chromium downstream. It does not use Electron, CEF, Qt WebEngine, Tauri, or an OS WebView.

## Required runner

Register a dedicated GitHub Actions self-hosted runner with all labels:

- `self-hosted`
- `Windows`
- `X64`
- `sunshine-chromium`

The machine must have:

- Windows 11 x64;
- at least 180 GB free on a persistent NTFS build volume;
- **PowerShell 7 or newer** (`pwsh`), which the build step requires and a stock Windows install does not include — `winget install Microsoft.PowerShell`;
- Visual Studio 2022 with Desktop development with C++;
- Windows 11 SDK;
- Python 3 and Git;
- Chromium `depot_tools` on `PATH`;
- long paths enabled.

GitHub-hosted Windows images ship `pwsh` preinstalled, so this requirement is invisible until the pipeline first runs on a real machine. Without it the job fails in about a minute with `pwsh: command not found`.

Set the repository Actions variable `SUNSHINE_CHROMIUM_WORKSPACE` to the persistent workspace, for example `F:\sunshine-chromium`. Do not place this checkout in an ephemeral runner directory.

The runner also needs `DEPOT_TOOLS_WIN_TOOLCHAIN=0` in the machine environment. Without it `gclient sync` tries to fetch a Google-internal toolchain and fails.

## Before dispatching a build, read the pinned tree and run the toolchain

A build is six hours on the machine the owner also works on, so the question
worth asking before every dispatch is *what would waste it*. Three kinds of
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
GitHub provides -- a cloud VM registered as a self-hosted runner, which is the
same workflow file with a different label. That is a cost decision and it is
the owner's.

### What does run on a hosted runner

**One workflow, since 2026-09-13.** There were two;
`architecture-guard-hosted.yml` was removed on the owner's instruction. It had
not been allocated a runner since **2026-09-08** — every push produced a job
that finished in two seconds with no runner assigned, no step recorded and no
log to download, and a red check that meant nothing. The cause is an
account-level Actions condition this repository cannot influence, which is the
same thing that put CI on the workstation in the first place.

**Removing it cost no coverage.** The self-hosted guard runs all twenty-nine of
its checks and one it did not (`validate_commands.py`), which is checked by
`tests/test_windows_build_contract.py`.

**One thing did go, and it is worth naming rather than discovering later.**
`scripts/compile_check_installer.py` cross-compiles the installer front-ends
with `x86_64-w64-mingw32-g++`, and the hosted guard was the only place that
could install it — the build machine has MSVC and no mingw, so the self-hosted
guard reports `NOT CHECKED` there by design. So that check now runs only where a
developer runs it. It had not in fact run in CI since it was written, because the
hosted guard was already dead by then.

**And the surviving hosted workflow is failing the same way.**
`patch-apply-hosted.yml` is subject to the identical account condition, so the
one question no offline guard can answer is currently going unanswered on every
push. It is kept rather than removed because the check is real and the failure
is not its fault; it will start working again the moment the account does.

`.github/workflows/patch-apply-hosted.yml` clones `src` alone at the pinned
revision -- one revision deep, no DEPS, no submodules -- and applies the whole
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

The clone is the job. The thing the job exists to do costs nothing, which is
the argument for running it on every push that touches a patch.

It answers the one question no offline guard can. `verify_patch_integrity.py`
checks each hunk's arithmetic, `verify_patch_references.py` replays hunks
against files the stack itself creates, and `verify_pinned_upstream.py` asks
whether cited upstream files exist -- but none of them reads an upstream file's
*contents*, because those are not in this repository. Until this job existed,
the first thing that ever read a patch against the real tree was `git apply` on
the build machine, and build #18 died there twenty minutes in.

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

Syncing Chromium clones well over a hundred dependency repositories. Anonymous requests share one server-side quota pool, and a multi-core runner exhausts it:

```
remote: RESOURCE_EXHAUSTED  subject: "shared/shared_anonymous"
remote: "Short term server-time rate limit exceeded"
fatal: The requested URL returned error: 429
```

Sign in once at <https://chromium.googlesource.com/new-password> and run the credential snippet it generates. This moves the runner out of the shared anonymous pool and is the reliable fix.

The bootstrap also bounds concurrency with `--jobs`, defaulting to 8 rather than gclient's one-job-per-core. Lower it further if an unauthenticated runner still hits 429.

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

The Chromium workspace belongs to the build, not to a person. The pipeline runs `bootstrap_chromium.py --reset`, which discards modifications to tracked upstream files so a changed patch stack does not stop the next build for manual cleanup.

`--reset` never touches untracked files, so `out/Sunshine` survives and the incremental build is preserved. Running the bootstrap without `--reset` keeps the protective default and refuses to discard anything.

Do not use this workspace for manual Chromium edits you want to keep.

## Sharing the machine

`autoninja` schedules roughly core count plus two jobs, which leaves a workstation unusable for the length of a build. The workflow takes an optional **Parallel compile jobs** input, forwarded as `SUNSHINE_NINJA_JOBS`, that caps it.

Leave it blank on a dedicated runner. On a machine that is also in daily use, keep two to four threads free — on a 12-core runner, `8` keeps the desktop responsive and costs roughly half again the compile time. Running the runner process at below-normal priority helps further.

## When a job sits in `queued`

A run that shows `queued` with no `Set up job` line has not reached a machine.
Nothing is wrong with the workflow: GitHub has no runner to give it. The usual
cause is that the machine slept — the runner is a process, and a sleeping
Windows box runs no processes.

This happened for seven hours on 2026-08-18, with run `32049595199` waiting the
whole time, so it is written down rather than rediscovered.

**A queued run is not kept forever, and this section used to imply it was.**
GitHub cancels a workflow run that has sat in `queued` for **24 hours**. Run
`33401443955` — build #48 — was queued at 14:14:09Z on 2026-08-31 and its
`updated_at` moved for the first time at 14:14:12Z the next day, three seconds
past the day mark, with conclusion `cancelled`. Nobody cancelled it.

That matters because the advice everywhere else here is *wait, do not
re-dispatch* — which is right, and `docs/RUNTIME_VERIFICATION.md` records run
#17 waiting 13 h 34 m and then succeeding. **The waiting advice holds only
inside the 24-hour window.** Past it the run is gone and a new dispatch is the
only option, so a build queued against a runner that will not be woken before
tomorrow is a build that has to be dispatched again anyway.

**Diagnose first.** In an elevated PowerShell:

```powershell
Get-Service "actions.runner.*" | Select-Object Name, Status
Get-Process Runner.Listener -ErrorAction SilentlyContinue
```

- A service listed and `Running`, or a `Runner.Listener` process: the runner is
  alive and the problem is elsewhere — check the queued run's labels against the
  runner's.
- A service listed and `Stopped`: `Start-Service <name>`.
- Neither: the runner was running interactively in a window that has since
  closed. Start it from its own directory, `C:\actions-runner`, with `.\run.cmd`.

**Then fix the cause rather than the symptom.** An interactive runner dies with
its window and with every sign-out. Installing it as a service survives both,
and is a change to the machine — take it deliberately.

**This section named `svc.cmd install` and `svc.cmd start` until 2026-09-01,
and neither exists on the runner machine.** Both returned
`CommandNotFoundException` from `C:\actions-runner`. `svc.sh` is the runner's
Linux and macOS service script; the Windows package has no `svc.cmd` to match
it, and the instruction was written from the wrong platform's documentation.

**What is verified is `run.cmd`**, which is what the paragraph above already
says and what brings the runner back now. For the service, look before typing:

```powershell
cd C:\actions-runner
Get-ChildItem -Filter *.cmd | Select-Object Name
.\config.cmd --help
```

On the Windows runner a service is installed by `config.cmd` when the runner is
configured, not by a separate script afterwards, so an interactively-configured
runner is re-configured rather than upgraded in place — which needs a
registration token from the repository's Actions settings and is a decision
about the machine rather than a command to paste. **The exact invocation is
deliberately not written here**, because the last time this document guessed at
one it sent someone to a command that does not exist, and `config.cmd --help`
on the machine is a better source than this file.

**A service still does not survive sleep.** Nothing in the runner keeps a
machine awake, so a build queued overnight needs the machine configured not to
sleep on mains power:

```powershell
powercfg /change standby-timeout-ac 0
powercfg /change hibernate-timeout-ac 0
powercfg /requests
```

The last command shows what is currently holding the machine awake, which is
worth reading before and after: a build holds nothing, so without these settings
a six-hour compile on an idle desktop will be interrupted by the desktop.

**Confirm.** The repository's Actions settings list the runner as `Idle` when it
is connected, and a queued run starts within about thirty seconds of that. Do
not treat the service starting as confirmation — confirm from the queued run
moving.

## Workflow

Run **Native Chromium Windows Build** manually after a downstream patch PR is merged:

1. validate the runner and disk;
2. fetch/sync pinned Chromium;
3. apply the ordered Sunshine patch stack;
4. generate an optimized non-component Release build;
5. build `chrome` and `mini_installer`;
6. upload the unsigned installer and JSON size report for 14 days.

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
