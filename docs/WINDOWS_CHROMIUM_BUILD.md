# Native Chromium Windows build

## Purpose

This pipeline builds the actual Chromium downstream. It does not use Electron, CEF, Qt WebEngine, Tauri, or an OS WebView.

## Required machine, and the runner on it

**Two days changed this section twice, so it says where it stands.** Every
workflow was deleted and Actions disabled on 2026-09-25
(`.ai/reports/2026-09-25-rules-and-actions-result.md`); the repository went
**public** on 2026-09-26 and the workflows were restored, because the one
reason they had died — an account-level runner allowance on a private
repository — does not apply to a public one. Both ways of starting a build now
work, and § *Running a build* gives each.

For the workflow path, register a dedicated self-hosted runner with all four
labels — `self-hosted`, `Windows`, `X64`, `sunshine-chromium` — from the
repository's Settings → Actions → Runners.

**A self-hosted runner on a public repository is the one arrangement GitHub
tells you not to make**, because a fork can open a pull request that runs its
own code on your machine. What makes it safe here is that both self-hosted
workflows are `workflow_dispatch:` and nothing else, so only someone with write
access can start them. That is not a convention — `tests/test_windows_build_contract.py`
fails if any workflow that runs on the physical machine becomes reachable from
`pull_request`, `pull_request_target`, `issue_comment` or `workflow_call`, and
the check reads `runs-on:` rather than the word appearing in a comment.

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
GitHub provides. That remains a cost decision and it is the owner's.

### What runs on a hosted runner, and the two weeks it did not

Two workflows, both `ubuntu-latest`, both triggered by `push`:
`architecture-guard-hosted.yml` runs the test command and every guard, and
`patch-apply-hosted.yml` applies the stack to a real Chromium checkout. They
are the only automatic CI here — the self-hosted pair is dispatch-only, so
nothing else watches a push.

**They were dead for two and a half weeks and the reason is worth keeping.**
From **2026-09-08** every push produced a job that finished in two to four
seconds with no runner assigned, no step recorded and no log to download, and a
red check that meant nothing: an account-level allowance on a private
repository, which this project could not influence from inside.
`architecture-guard-hosted.yml` was removed for it on 2026-09-13 and the rest
went with Actions itself on 2026-09-25. **The repository became public on
2026-09-26, hosted runners stopped being metered, and all of them came back.**

What that fortnight cost, now that it is over:

- **`stable` was red for a full day** (2026-09-25) and nothing said so, because
  the only thing that could have said so had been deleted. That is the failure
  `tests/test_windows_build_contract.py` § `test_every_push_is_watched_by_something_hosted`
  now exists to prevent.
- **`scripts/compile_check_installer.py` still has no automated home.** It
  cross-compiles the installer front-ends with `x86_64-w64-mingw32-g++`; the
  build machine has MSVC and no mingw, so the self-hosted guard reports
  `NOT CHECKED` there by design and only a hosted runner can install it. It has
  never once run in CI — the hosted guard was already dead when it was written
  — and wiring it into the restored hosted guard is worth doing and is not done
  here.

`patch-apply-hosted.yml` answers the one question no offline guard can: whether
the stack applies to the real upstream tree. **It also has a cheaper answer
that does not need a runner at all**, found while it was dead: `python3
scripts/verify_pinned_upstream.py --source github` fetches each upstream file
the stack touches from the mirror and applies the whole series, in about a
minute, from any development session. Run that before a build rather than
waiting on a push; the
  workflow's last successful run before the outage was 2026-09-06.

What it does: it clones `src` alone at the pinned
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
the build machine, and build #18 died there twenty minutes in. That is the
failure both this workflow and `verify_pinned_upstream.py --source github` now
stand in front of -- the workflow on every push, the command whenever someone
chooses to ask.

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

It holds for both ways of starting a build: a hand-started compile is exactly
as vulnerable to the desktop sleeping as a dispatched one.

### When a dispatched run sits in `queued`

A run showing `queued` with no `Set up job` line has not reached a machine.
Nothing is wrong with the workflow — there is no runner to give it, and the
usual cause is that the machine slept, because a runner is a process and a
sleeping Windows box runs none.

**A queued run is not kept forever, but 24 hours is not a deadline you can set
a watch by.** This paragraph said GitHub cancels a run that has sat in `queued`
for 24 hours, and both halves of that are now measured:

| Observation | Queued for | Outcome |
| --- | --- | --- |
| Build #48, run `33401443955`, queued 14:14:09Z | 24 h 0 m 3 s | `cancelled`, with nobody cancelling it |
| Runs `36232595361` and `36232575600`, dispatched 2026-09-26 09:22Z | **26.1 h and counting** | still `queued`, zero jobs, `updated_at` never off creation |

The second was watched deliberately across the mark, at 24 h 05 m and again at
26 h 06 m. So the cancellation is real but its timing is not a guarantee in
either direction, and a plan that plays chicken with the deadline — *it will be
cancelled by morning anyway, so re-dispatch now* — is reasoning from a number
this repository has now seen broken.

The standing advice is unchanged and does not depend on the number: **wait, do
not re-dispatch.** Run #17 waited 13 h 34 m and then succeeded. Re-dispatching
buys nothing when the queue is the problem, because the new run joins the same
queue — which is exactly what the two runs above are demonstrating.

Diagnose before fixing, in an elevated PowerShell:

```powershell
Get-Service "actions.runner.*" | Select-Object Name, Status
Get-Process Runner.Listener -ErrorAction SilentlyContinue
```

- Listed and `Running`, or a `Runner.Listener` process: the runner is alive;
  check the queued run's labels against the runner's.
- Listed and `Stopped`: `Start-Service <name>`.
- Neither: it was running interactively in a window that has closed. Start it
  from its own directory, `C:\actions-runner`, with `.\run.cmd`.

**An interactive runner dies with its window and with every sign-out.**
Installing it as a service survives both and is a change to the machine, so
take it deliberately. On Windows the service is installed by `config.cmd` when
the runner is configured, not by a separate script afterwards — **this document
once said `svc.cmd install`, which does not exist on Windows at all** (`svc.sh`
is the Linux and macOS script) and sent someone to a `CommandNotFoundException`.
The exact invocation is deliberately not written here; `config.cmd --help` on
the machine is a better source than this file.

**Confirm from the run, not from the service.** Settings → Actions → Runners
lists the runner as `Idle` when it is connected, and a queued run starts within
about thirty seconds of that.

## Running a build

**Two ways, and they run the same thing.** The workflow only ever called the
script, so the difference is who starts it and where the log goes.

### Dispatch the workflow — the default

Actions → **Native Chromium Windows Build** → Run workflow. It needs the
self-hosted runner connected (§ *Required machine, and the runner on it*), and
it is the default because the log is kept, the run has a number other documents
can cite, and the installer is reported by path rather than by whoever was
watching the shell.

Optional input **Parallel compile jobs** → forwarded as `SUNSHINE_NINJA_JOBS`.
Leave it blank on a dedicated machine; set `8` on a 12-core machine that is
also in daily use.

### Run the script directly — when the runner is not up

One command, in **PowerShell 7**, from the repository checkout:

```powershell
pwsh -NoProfile -File scripts/build_chromium_windows.ps1
```

That is `build_command` in `.ai/PROJECT_CONTEXT.md` § *Facts the checks read*.
It needs no runner, no Actions and no network beyond what the sync itself
needs, which makes it the path that still works when everything else is
broken — the state this repository was in for a day.

Either way the script does the same six things in the same order:

1. validate PowerShell, Windows, the workspace variable and the free disk;
2. fetch/sync pinned Chromium;
3. apply the ordered Sunshine patch stack;
4. generate an optimized non-component Release build;
5. build `chrome` and `mini_installer`;
6. write the unsigned installer and the JSON size report under `artifacts/`.

**What the direct run does not give you**, and why the workflow is the default:

- **Nothing records that the build happened.** `docs/RUNTIME_VERIFICATION.md`
  § 4 asks for "workflow run number and commit sha" beside every gate result.
  A hand-started build has no run number, so **cite the commit sha** and treat
  `scripts/build_gate_sheet.py`'s `BUILD` stamp as a number kept by hand.
- **The log lives in your shell.** Close the window and the compiler
  diagnostic goes with it.

Neither path uploads the installer, and that is on purpose rather than a gap:
the runner *is* the owner's machine, so `artifacts/` is already where the
installer needs to be. Sending it to GitHub storage and pulling it back to the
machine that produced it is a round trip with no delivery, and
`tests/test_windows_build_contract.py` holds that rule.

Script parameters, both also readable from the environment:

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
