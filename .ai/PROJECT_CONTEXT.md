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

- Remove the accidental Electron runtime.
- Reuse Chromium's native browser fundamentals and security model.
- Apply Sunshine OS metadata without Google Chrome proprietary assets or services.
- Establish deterministic macOS and Windows build instructions.

## Next product slice

- Sunshine New Tab surface hosted as a native Chromium WebUI.
- Local-first dashboard data model.
- Explicit permission UX and download review.
