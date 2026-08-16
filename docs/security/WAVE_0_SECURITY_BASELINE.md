# Wave 0 Security Baseline

- Browser windows enable `sandbox`, `contextIsolation`, and `webSecurity` and disable `nodeIntegration`.
- The preload exposes only `executeCommand`; no raw IPC object or filesystem API is exposed.
- IPC payloads and sender URLs are validated before command dispatch.
- Permission requests default to deny until the product has an origin-aware policy and consent UI.
- Unexpected top-level navigation is blocked and new-window requests are denied after safe external handoff.
- Renderer CSP is restrictive; development server allowances are explicit and must be removed from packaged production policy in a later hardening pass.

This baseline protects the trusted shell. Remote page surfaces are not implemented in Wave 0 and require a separate security review before navigation is enabled.
