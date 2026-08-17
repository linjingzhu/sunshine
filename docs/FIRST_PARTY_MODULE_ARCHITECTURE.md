# Sunshine first-party module architecture

## Decision

Sunshine is a modular native Chromium downstream. A first-party module is a
Sunshine-owned capability compiled and signed with the browser. It is not an
extension, a remotely downloaded plug-in, or an embedded second browser.

The boundary keeps Sunshine features independently owned, reviewable,
switchable, and removable while Chromium continues to own tabs, navigation,
profiles, history, downloads, permissions, renderer isolation, and sandboxing.

## Layers

1. **Chromium core** — authoritative browser services and security boundaries.
2. **Sunshine module registry** — declarative inventory under `first_party/`.
3. **Native adapters** — future minimal C++/WebUI integration points.
4. **First-party modules** — Sunshine surfaces, services, and integrations.

Modules depend inward through declared capabilities. Chromium core never
depends on a Sunshine module, and modules cannot depend directly on another
module's private implementation.

## Initial contribution points

| Contribution | Purpose | Chromium remains owner of |
|---|---|---|
| WebUI surface | New Tab, settings page, or module-owned page | navigation, WebUI security, profile routing |
| Native command | User-invoked browser action | command dispatch and active browser context |
| Profile service | Profile-scoped module state | profile lifecycle and off-the-record boundaries |
| Integration surface | Mediated connection to another first-party product | authentication, consent, network policy |

Arbitrary binary loading, remote JavaScript, extension API impersonation, and a
general in-process plug-in ABI are excluded. The first implementation is a
compile-time registry with feature-controlled activation, not an unsafe dynamic
plug-in host.

## Command ownership

`first_party/commands.json` is the authoritative command list. Each entry names
an owner, an availability predicate, a telemetry event, and its error results.

A Sunshine-owned command is claimed by declaring a `native_command` entrypoint
whose target is the command id. Entrypoint targets are already globally unique
across the module registry, so that declaration is what makes "one authoritative
implementation" enforceable rather than aspirational: a second module claiming
the same command fails validation.

Chromium-owned commands such as `browser.back` appear in the registry but must
not be declared by any module. Sunshine surfaces them; it does not implement
them.

Where a Sunshine model already enforces a command's availability, the entry
carries a `guard` naming that callable, and validation imports it. A guard that
stops resolving fails the build rather than silently becoming prose.

## Manifest contract

Every registered module declares a stable `sunshine.*` ID, ownership, lifecycle,
entrypoints, capabilities, data access, security boundaries, and verification
status. The registry rejects duplicate IDs and routes, unregistered manifests,
path traversal, privileged remote content, invalid profile modes, and runtime
claims without native evidence.

## Data and security rules

- Module state is profile-keyed unless a narrower tab/window lifetime is declared.
- Incognito and Guest are opt-in and require dedicated native tests.
- A privileged WebUI cannot render remote content.
- Network access is default-off and later requires a host allowlist and user-visible purpose.
- Modules use Chromium service APIs and never open Chromium databases directly.
- Cross-module communication uses versioned public contracts.
- Disabling a module must leave ordinary browsing operational.

## Lifecycle

`planned → prepared → runtime_verified`

- **planned:** architecture or product slot only; not shipped.
- **prepared:** manifest/static gates exist; native execution is unverified.
- **runtime_verified:** native build and runtime evidence pass. User-facing
  completion additionally requires visual evidence.

The current Sunshine New Tab is `prepared`, not complete, because the pinned
Chromium downstream has not yet been compiled and run.

## Adding Dev-OS or another module

1. Copy `first_party/templates/module.example.json` into a unique module folder.
2. Define the smallest WebUI, command, service, or integration entrypoint.
3. Declare only required capabilities and data; keep network off by default.
4. Register the manifest in `first_party/registry.json`.
5. Run the validator and repository tests.
6. Implement the minimal Chromium adapter in an isolated downstream patch.
7. Compile Chromium and test regular/profile/off-the-record boundaries.
8. Mark runtime evidence passed only after exercising the produced browser.

Dev-OS should begin as a user-opened integration surface. It receives no ambient
tab content and performs no GitHub action without explicit user intent. Being
first-party does not justify permanent residency or browser-wide credentials.

## Completion boundary

The registry, validator, CI gate, and initial manifest are a static foundation.
The runtime adapter/loader is intentionally deferred until native compilation is
available.
