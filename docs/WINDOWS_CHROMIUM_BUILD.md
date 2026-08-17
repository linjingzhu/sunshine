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
