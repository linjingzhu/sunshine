# Command registry

## Status

COMPLETED

## Why this first

Handoff section 3.2 makes the command-first rule non-negotiable: every
user-visible action is a command with one authoritative implementation, an
availability predicate, a telemetry event, and an error result.

Nothing executable enforced it. Command identifiers existed only as prose tables
in two documents, and those tables had already drifted: the handoff still listed
a split-view `toggle` command that the split-view contract had replaced with
open, swap, and close. Nothing could detect that.

Four of the remaining Stage 2-3 contract gaps — gestures, browser utilities,
side panel, command palette — all invoke commands. Building them before the
registry would have let each invent its own notion of what a command is.

## Delivered

- `first_party/commands.json`: 16 commands across five surfaces, each with
  owner, availability predicate, telemetry event, and error results.
- `scripts/validate_commands.py`, wired into CI.
- Module manifests for `sunshine.workspace` and `sunshine.split_view`, which
  already had models but no declared identity.
- Command ownership recorded in the module architecture document; the handoff's
  duplicated list replaced by a pointer to the registry.

## What the validator enforces

Ownership reuses machinery that already existed. A Sunshine command is claimed
through a `native_command` entrypoint, and the module validator already rejects
duplicate entrypoint targets across the registry — so "one authoritative
implementation" became enforceable without new mechanism. A Chromium-owned
command must not be claimed by any module.

Guards are executable. Where a Sunshine model already enforces a command's
availability, the entry names that callable and validation imports it, so five
commands are bound to `move_tabs_atomic`, `close_workspace_atomic`,
`open_split`, `swap_panes`, and `close_pane`. A guard that stops resolving fails
the build.

Telemetry names are derived from the identifier rather than written by hand, so
that pair cannot drift.

Documentation is checked in one direction only: a document may not name a
command that does not exist. The reverse — requiring every command to appear in
prose — would force back the duplicated lists this registry replaces. The
registry entry is the command's documentation.

## Drift found and removed

The handoff listed a split-view `toggle` command with no counterpart in the
split-view contract, the split model, or any test. It was a survivor of the
earlier list, and it named behaviour that was never defined. The list is gone;
the registry is now the single source.

The check was verified by reintroducing the stale identifier into a document and
confirming the validator fails.

## Verification

- Unit/contract suite: 104 passed, up from 92.
- Command registry: 16 commands.
- Module registry: 3 modules, up from 1.
- Architecture verifier, patch manifest, Python compile: passed.
- Native compile, Windows build, runtime: NOT RUN; unchanged by this work.
- Adversarial review: FALLBACK REVIEW - fresh self-review only.
- Cross-agent review: NOT AVAILABLE.

## Remaining risk

The registry describes commands; it does not dispatch them. Eleven of sixteen
carry no guard because the behaviour they name is Chromium's or is not modelled
yet. Nothing yet proves a command's declared errors match what its guard raises,
which is the natural next tightening.
