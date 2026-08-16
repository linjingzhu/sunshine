# Sunshine OS Project Context

## Authoritative product constraints

- Sunshine OS is a browser first. Unrestricted ordinary web browsing is the primary product surface.
- The runtime is a native downstream of the open-source Chromium browser.
- Electron, CEF, Qt WebEngine, Tauri, and OS WebView wrappers are excluded.
- Chromium owns tabs, omnibox, navigation, history, downloads, renderer isolation, and permissions.
- Sunshine features are downstream Chromium changes kept as a small, reviewable patch stack.
- Default integration branch: `stable`.

## Current architecture

- Upstream: pinned Chromium revision declared in `config/chromium.version`.
- Downstream: ordered patches in `downstream/patches/series`.
- Bootstrap: `scripts/bootstrap_chromium.py` checks out Chromium and applies the patch stack.
- Build: GN generates Ninja files; Ninja builds the native `chrome` target.
- Start surface: Chromium's native New Tab Page. Sunshine never hardcodes Google as the startup URL.

## Current development slice

- Brand Chromium's native New Tab WebUI as Sunshine.
- Preserve Chromium-owned search/URL handling and Most Visited data.
- Keep Stage 1 New Tab intentionally minimal and browser-first.
- Validate every downstream patch against the pinned Chromium sources.

## Next product slice

- Produce and smoke-test a native Chromium build on Windows.
- Continue Stage 1 fundamentals only after the New Tab patch is build-verified.
- Defer local-first Life Dashboard data, AI, notes, and apps to Stage 4+.
