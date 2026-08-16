# Stage 1 contracts and patch integrity report

Status: contracts and validation infrastructure completed; runtime changes intentionally deferred.

## Parallel work

- Download safety contract: Chromium-owned classification, warning surfaces, command eligibility, and telemetry preserved.
- Permission policy contract: Chromium-owned per-origin ASK/ALLOW/BLOCK behavior and OS gates preserved.
- Adversarial audit: native runtime changes blocked until a Windows build can be verified.
- Manager integration: exclusive patch ownership manifest and status-overclaim tests.

## Integrity gates

The repository now rejects:

- duplicate series entries;
- non-contiguous or unordered patch numbering;
- path traversal in patch names or targets;
- missing or unlisted patch files;
- patches without tracked upstream targets;
- multiple patches owning the same upstream file;
- early download or permission runtime patches;
- status reports that omit pending native verification.

CI derives pinned upstream files from the actual patch manifest instead of a hardcoded list.

## Verification

- Python compile check: pass.
- Architecture verifier: pass.
- Patch manifest: 3 exclusive upstream targets.
- Repository unit tests: 21/21 pass.
- Native compile/runtime/visual: deferred by product owner.
