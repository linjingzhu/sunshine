# ADR 0002: Native Chromium downstream

## Status

Accepted. This is the first standing architecture decision; ADR 0001 was withdrawn as an error and removed, so the numbering starts here.

## Context

Sunshine OS is browser-first. A wrapper runtime that recreates browser chrome around an embedded page cannot deliver a full, unrestricted browser. It produced platform composition defects and left browser fundamentals to be reimplemented in application code.

## Decision

Build Sunshine OS as a downstream of the open-source Chromium browser.

- Build Chromium's native `chrome` target.
- Keep the upstream revision pinned.
- Maintain Sunshine changes as a small ordered patch stack.
- Use Chromium's existing tabs, omnibox, navigation, history, downloads, permissions, profiles, renderer isolation, and sandbox.
- Add Sunshine product surfaces through native Chromium WebUI and Views integration.
- Do not add Electron, CEF, Qt WebEngine, Tauri, or platform WebView wrappers.
- Do not use Google Chrome proprietary branding, API keys, or `src-internal` assets.

## Startup policy

The first window opens Chromium's native New Tab Page. A public web URL, including Google, must never be hardcoded as the Sunshine startup page. The later Sunshine dashboard will replace the New Tab Page through a reviewed native WebUI change.

## Consequences

- The source checkout and build are far larger than an application-level project; see `docs/SIZE_BUDGET.md`.
- macOS builds require Xcode and the Chromium toolchain; Windows builds require Visual Studio and at least 100 GB of local free space.
- Upstream security updates must be tracked continuously.
- Browser fundamentals no longer need to be recreated in application code.
