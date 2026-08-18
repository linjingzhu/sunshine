---
doc_id: ai-project-context
version: 1.0.0
canonical_path: .ai/PROJECT_CONTEXT.md
updated: 2026-08-16
---

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
- First-party platform: declarative module registry under `first_party/`; modules are compiled Sunshine capabilities, not extensions or remotely loaded plug-ins.
- Module boundary: Chromium remains owner of browser fundamentals; modules use explicit WebUI, command, profile-service, or integration contribution points.

## Current development slice

- Brand Chromium's native New Tab WebUI as Sunshine.
- Preserve Chromium-owned search/URL handling and Most Visited data.
- Keep Stage 1 New Tab intentionally minimal and browser-first.
- Validate every downstream patch against the pinned Chromium sources.

## Active product slice

- Preserve the pending Windows native-build gate; do not claim unverified patches as shipped.
- Establish the compile-free first-party module manifest, lifecycle, security, and CI validation foundation.
- Defer runtime module adapters until the native Chromium build gate can verify them.
- Begin the compile-free A-grade productivity foundation with Chromium-owned tab groups.
- Define Sunshine workspace membership and two-pane split state around native tabs without replacing `TabStripModel`, profiles, or session restore.
- Runtime implementation order: tab-group verification → workspace metadata/switching → split view.
- Defer local-first Life Dashboard data, AI, notes, and apps to Stage 4+.

## Permanently excluded product scope

The previously evaluated feature list is capped at items 1–19. Items 20 and
later are not backlog candidates and must not be reintroduced through roadmap,
dashboard, or speculative implementation work.
