# Sunshine OS Project Context

## Product

- Desktop browser shell built with Electron, React, TypeScript, and Vite.
- Primary supported platform: Windows. Development verification currently runs in Linux CI/container environments.
- Default integration branch: `stable`.

## Current architecture

- Trusted browser chrome: sandboxed `BrowserWindow` renderer with a minimal typed preload API.
- Remote web content: separate sandboxed `WebContentsView`; Node.js is disabled and permissions/new windows are denied by default.
- Main-process commands: explicit allow-list with trusted-sender validation.
- Navigation policy: HTTPS by default; HTTP is accepted only for localhost development targets.

## Delivered waves

- Wave 0: deterministic runtime shell, design tokens, command contract, tests, and documentation baseline.
- Wave 1: one-window/one-tab browser slice with omnibox, search, back, forward, reload/stop, title/loading state, and error feedback.
- Wave 2: reproducible unsigned Universal macOS DMG/ZIP test builds through GitHub Actions.

## Next product slice

- Multi-tab lifecycle and tab recovery.
- Downloads UX and explicit permission prompts.
- Apple Developer ID signing/notarization and Windows-native packaging.
