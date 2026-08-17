# Project Lessons

Repository-specific memory for reducing rediscovery and repeated mistakes.

Do not copy this file into unrelated projects.

## Conflict Hotspots

### 2026-08-17 — `scripts/workspace_model.py` is now a shared dependency
Area: compile-free state models.
Evidence: `scripts/split_view_model.py` imports `NativeTab`, `canonical_uuid`,
and `WorkspaceModelError` from it. Any later split, archive, or projection model
will import the same symbols.
Impact: parallel edits to this file will collide and can silently change the
failure contract of every importer.
Recommended future behavior: treat it as a serialized hotspot. Give one Mission
Pack exclusive write ownership per wave; other packs read only.
Confidence: high.

## Build / Compile Lessons

- None recorded yet.

## UX / Runtime Lessons

- None recorded yet.

## Domain Risk Lessons

### 2026-08-17 — A borrowed validator can silently break a fail-closed promise
Area: compile-free persistence models.
Evidence: `restore_layout` promises never to raise and recovers from
`SplitViewError`, but it reused the workspace UUID validator, which raises
`WorkspaceModelError`. A malformed persisted UUID would have escaped into native
restore instead of falling back to one pane.
Impact: the documented corruption fallback would not have run in exactly the case
it exists for.
Recommended future behavior: when a function is specified as "never raises",
wrap every borrowed helper into that module's own error family, and prove the
fallback through the public entry point rather than the strict parser.
Confidence: high.

## Strategy Observations

### 2026-08-17 — Write the failure-injection test before the defensive guard
Area: model implementation.
Evidence: the workspace minimum-count guard in `close_workspace_atomic` was
unreachable; an earlier destination check already rejected the only input that
could have reached it. The test written for it failed and exposed the dead
branch.
Impact: an untestable branch reads as a safety property while guaranteeing
nothing.
Recommended future behavior: require a reaching test for each guard. If no input
reaches it, delete the guard and assert the behavior that is actually
guaranteed.
Confidence: medium.

## Recording rule

Add only concise, evidence-backed facts such as:

```text
### 2026-XX-XX — <lesson>
Area:
Evidence:
Impact:
Recommended future behavior:
Confidence:
```

Prefer facts that can change future Mission Packing, verification timing, or conflict prevention.

Remove/replace stale lessons when repository reality changes.
