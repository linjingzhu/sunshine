# Wave 1 — Browser Slice Delivery Report

## Scope

Implemented the first usable Sunshine OS product slice: a one-window, one-tab browser with a trusted chrome renderer and isolated remote web-content renderer.

## User-visible behavior

- Enter a domain, HTTPS URL, localhost URL, or search phrase in the omnibox.
- Navigate backward and forward, reload a page, or stop an in-flight load.
- See current page title, loading state, address, HTTPS indicator, and navigation errors.
- Press `Ctrl+L` or `Cmd+L` to focus and select the omnibox.
- Unsupported multi-tab and menu actions remain visibly disabled rather than failing silently.

## Security boundaries

- Remote pages run in a `WebContentsView` with Node.js disabled, context isolation, sandboxing, and web security enabled.
- Popups and new windows are denied.
- Permission requests are denied by default until a product permission UX exists.
- Main-process commands use an allow-list and validate the trusted sender origin.
- Navigation defaults to HTTPS; plaintext HTTP is restricted to local development.

## Verification

- TypeScript renderer and main/preload checks: pass.
- Vitest: 2 files, 11 tests: pass.
- Vite production renderer build: pass.
- TypeScript main/preload production emit: pass.
- Interactive window capture: not available in the headless root container; Electron correctly refused root execution without disabling its sandbox. The sandbox was not bypassed.

## Risks and follow-up

- Windows-native runtime and packaging must be verified on a Windows runner before release.
- Permission and download workflows intentionally remain unavailable until their dedicated UX and policies are implemented.
- The production trusted renderer still uses the `file:` protocol; migrate it to a privileged custom app protocol in a later hardening wave.
