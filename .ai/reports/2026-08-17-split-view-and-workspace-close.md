# Split View and Workspace Close Transaction

## Status

COMPLETED_WITH_NOTES

## Scope

Completed steps 3, 4, and 5 of the implementation sequence in
`docs/TAB_WORKSPACE_SPLIT_CONTRACT.md` as pure, compile-free models. Steps 1 and
2 were delivered by the workspace native foundation wave; step 6 remains blocked
on a dedicated Windows Chromium runner.

No downstream runtime patch was added. The patch series is unchanged.

## Delivered

- Window-scoped two-pane split model with orientation, ratio, and pane focus
  routing over durable Sunshine tab UUIDs.
- Fail-closed restore that recovers a damaged, stale, cross-workspace,
  mixed-profile, or future-schema record into the normal one-pane view without
  raising and without dropping a tab.
- `view.split.swap` implemented as position and focus only; orientation, ratio,
  and every Chromium-owned navigation field are untouched.
- Off-the-record windows keep split state in memory; nothing is persisted.
- `close_workspace_atomic`: explicit destination required, all tabs of the closed
  workspace transferred at once, no discard, no archive, exact-object rollback.
- A native group straddling two workspaces is rejected with the same explicit
  choice policy already used for partial group moves.

## Ownership boundary

The split record stores only `schema_version`, two durable tab UUIDs,
orientation, ratio, and focused pane. It stores no URL, title, navigation entry,
native `SessionID`, or `WebContents` pointer. Chromium remains the sole owner of
tab lifetime, navigation, and session restore.

Orientation is expressed as `columns` / `rows` so split-pane orientation can
never be confused with permanently excluded tab-strip orientation scope.

## Verification

- Unit/contract suite: 71 passed, up from 48.
- Architecture verifier: passed.
- Patch manifest: passed, 3 exclusive upstream targets, series unchanged.
- First-party module registry: passed.
- Python compile check: passed.
- Chromium compile: NOT RUN by the current compile-free constraint.
- Windows build: NOT RUN; no dedicated runner is available.
- Runtime/visual verification: NOT RUN; no native feature delivery is claimed.
- Adversarial review: FALLBACK REVIEW — fresh self-review only.
- Cross-agent review: NOT AVAILABLE; no opposite-family reviewer in this run.
- Git conflicts: none; one Manager-owned mission pack, no parallel writers.

## Problems found and automatically fixed

- Critical — `split_view_model` borrowed the workspace UUID validator, which
  raises `WorkspaceModelError`. `restore_layout` recovers from `SplitViewError`
  only, so a malformed persisted UUID would have escaped the fail-closed path and
  propagated into native restore. Fixed by wrapping the shared helper into the
  split error family; covered by the `not_a_uuid` restore case.
- Major — the split model accepted a pane pair mixing a regular and an
  off-the-record tab, contradicting the profile-boundary invariant. Fixed with a
  shared pane-pair check applied to both `open_split` and `restore_layout`.
- Minor — the workspace minimum-count guard in `close_workspace_atomic` was
  unreachable, because a sole workspace is already rejected for having no
  distinct destination. The dead branch was removed and the test now asserts the
  behavior that is actually guaranteed.

## Remaining risk

These are pure models, not native Chromium runtime code. Command wiring, real
pane rendering and focus, workspace projection, restart recovery, and the UX
contract in contract section 5 stay unverified until a Windows Chromium build can
compile and exercise them.

`close_workspace_atomic` returns catalog and tab state only. Window-local state —
active workspace selection and split re-resolution after a close — belongs to the
native caller and is documented but not enforced by the model.
