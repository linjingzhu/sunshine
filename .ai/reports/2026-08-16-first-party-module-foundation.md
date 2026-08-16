# First-party module foundation

Status: static architecture foundation implemented; runtime loader deferred.

## Delivered

- Declarative registry and initial Sunshine New Tab manifest.
- Reusable manifest template for Dev-OS and later modules.
- Ownership, lifecycle, contribution-point, data, security, and removal contract.
- Validator for inventory, IDs, entrypoints, profile modes, privileged remote content, and verification claims.
- CI and regression-test integration.

## Evidence boundary

- This change adds no Chromium runtime patch.
- New Tab remains `prepared` with native build, runtime, and visual verification pending.
- A runtime adapter/loader is not claimed until native compilation is available.
