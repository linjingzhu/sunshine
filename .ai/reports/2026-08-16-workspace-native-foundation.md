# Workspace Native Foundation

## Status

COMPLETED_WITH_NOTES

## Delivered

- Verified pinned Chromium 152 native tab/group/session extra-data seams.
- Removed the shadow tab/session database design conflict.
- Defined profile catalog, window-active, and tab-membership ownership.
- Added a pure catalog/membership/atomic-move model with failure injection.
- Added CI checks that fail when required pinned Chromium source seams move.
- Excluded split view, vertical tabs, archive, cross-window, and runtime UI from
  this implementation wave.

## Parallel review findings resolved

- Critical: duplicate session restore authority → Chromium is the only session owner.
- Critical: unstable SessionID/tab-index matching → durable Sunshine UUIDs ride
  in Chromium tab extra-data.
- Major: profile-wide active workspace ambiguity → active workspace is window-local.
- Major: partial grouped-tab movement → rejected until whole-group or explicit
  ungroup choice is supplied.
- Major: future/corrupt schema → preserve unknown versions; recover invalid
  membership to Default without discarding native tabs.

## Verification

- Unit/contract suite: 41 passed.
- Python compile check: passed.
- Architecture and patch-manifest checks: passed.
- Pinned source HTTP/path/symbol check: verified locally and encoded in CI.
- Chromium compile/Windows build/runtime: NOT RUN by current constraint.
- Adversarial review: three parallel read-only mission packs; one blocking
  design was revised before implementation.

## Remaining risk

The pure model is not native Chromium runtime code. Persistent command wiring,
real tab visibility projection, session/crash restore, and UI remain blocked
until a Windows Chromium build can compile and exercise the integration.
