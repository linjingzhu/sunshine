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
- Visual Studio 2022 with Desktop development with C++;
- Windows 11 SDK;
- Python 3 and Git;
- Chromium `depot_tools` on `PATH`;
- long paths enabled.

Set the repository Actions variable `SUNSHINE_CHROMIUM_WORKSPACE` to the persistent workspace, for example `F:\sunshine-chromium`. Do not place this checkout in an ephemeral runner directory.

The runner also needs `DEPOT_TOOLS_WIN_TOOLCHAIN=0` in the machine environment. Without it `gclient sync` tries to fetch a Google-internal toolchain and fails.

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
