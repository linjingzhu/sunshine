---
doc_id: ai-project-context
version: 1.0.1
canonical_path: .ai/PROJECT_CONTEXT.md
updated: 2026-09-25
---

# Sunshine OS Project Context

## Facts the checks read

```text
repository_mode: protected
base_branch: stable
merge_deploys: yes
runtime_gate: python3 scripts/verify_installed_build.py
test_command: python3 -m unittest discover -s tests -v
lint_command: python3 scripts/verify_architecture.py
build_command: pwsh -NoProfile -File scripts/build_chromium_windows.ps1
generated: gate-sheet.html via python3 scripts/build_gate_sheet.py; resource assets have generators under scripts/; inspect source-specific generation before editing
external_scripts: none
public_ids: linjingzhu/sunshine
owner_ledger: .ai/reports/OWNER_ACTIONS.md
```

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

## Platform and verification constraints

Windows is the default build and verification platform. Do not perform a macOS build unless explicitly requested. The existing product, architecture and runtime constraints above remain authoritative.

## Automation state after policy adoption (2026-09-25)

The owner requested the latest shared rules and removal/disablement of every GitHub Actions workflow across the repositories. This dated decision supersedes earlier instructions in this context that require Actions CI, Actions deployment, or workflow-driven automatic merges. Existing product constraints, local verification commands, history and owner records remain in force. Future unrelated changes use `repository_mode: protected`; this batch has explicit merge authorization.

All tracked files under .github/workflows are removed. Actions CI, releases, deployment and other workflow-based jobs no longer execute. Local checks remain available. `merge_deploys` stays conservative where external hosting has not been independently verified; a successful merge is not deployment evidence. Do not recreate or re-enable workflows without a new owner instruction.

The `merge_deploys: yes` value is a conservative assumption because non-Actions hosting connections were not inspected. For newly filled facts, `none` means no relevant mechanism was established from the inspected repository files, not an audit of external services.
