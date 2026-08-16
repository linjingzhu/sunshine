# Wave 2 — macOS Test Build Report

## Scope

Added a reproducible GitHub-hosted packaging path for unsigned Universal macOS test builds.

## Delivery

- `electron-builder` pinned in the lockfile.
- Universal DMG and ZIP packaging command.
- GitHub Actions workflow on `macos-14`.
- Tests and type checks run before packaging.
- Build artifacts retained for 14 days.
- Tester and release-signing guidance documented.

## Security posture

- Code-signing identity auto-discovery is disabled in CI to prevent ambiguous signing behavior.
- No Apple credentials or placeholder secrets are committed.
- The artifact is explicitly labeled unsigned and is not represented as production-ready.

## Release blockers

- Apple Developer ID signing and notarization.
- Product icon assets.
- Physical Intel and Apple Silicon smoke testing.
