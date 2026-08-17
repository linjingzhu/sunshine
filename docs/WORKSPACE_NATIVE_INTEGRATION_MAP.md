# Workspace Native Integration Map

**Status:** pinned-source verified design; runtime patch blocked until Windows build access  
**Pinned target:** `152.0.7977.42`

## Single ownership model

- Chromium `SessionService` remains the sole owner of tab/window restoration.
- Sunshine must not persist a parallel list of tab URLs, pinned state, ordering,
  navigation, or live group IDs.
- The profile-scoped workspace catalog stores only workspace UUID, name, color,
  and order.
- Each native tab carries `sunshine_tab_uuid` and `sunshine_workspace_uuid`
  through Chromium session tab `extra_data`.
- The active workspace is window-local and must use Chromium window session
  `extra_data`; it is not a profile-global active selection.
- The same record carries each workspace's last active tab for that window, as a
  durable Sunshine tab UUID. `workspace.switch` is specified to restore it, and
  until `scripts/workspace_model.py` gained `WindowWorkspaceState` nothing stored
  it -- the behaviour was specified with no owner. It is window-local for the
  same reason the active workspace is: the catalog is profile-wide, so two
  windows showing one workspace would overwrite each other. It is a pointer into
  Chromium's tabs, not a copy of them; when it does not resolve, or resolves to a
  tab that has since changed workspace, Chromium's own restored active tab wins.
  Off-the-record windows persist none of it, because a per-workspace record of
  the last page read is browsing history by another name.

## Upstream ownership points to verify at the pinned tag

| Responsibility | Expected upstream path/symbol |
|---|---|
| Window tab owner | `chrome/browser/ui/tabs/tab_strip_model.{h,cc}` / `TabStripModel` |
| Native groups | `chrome/browser/ui/tabs/tab_group_model.{h,cc}` |
| Group visuals | `components/tab_groups/tab_group_visual_data.{h,cc}` |
| Live observation | `chrome/browser/ui/tabs/tab_strip_model_observer.h` |
| Tab session identity | `components/sessions/content/session_tab_helper.{h,cc}` |
| Session records | `components/sessions/core/session_types.h` / `SessionTab::extra_data` |
| Extra-data commands | `components/sessions/core/session_service_commands.{h,cc}` |
| Last-session restore | `chrome/browser/sessions/session_restore.cc` |
| Recently closed restore | `components/sessions/core/tab_restore_service.{h,cc}` |

`SessionID`, tab index, URL/title, `WebContents*`, and native group ID are
forbidden as durable Sunshine keys. Chromium remaps native group IDs during
restore, and session IDs are not guaranteed durable across sessions.

The listed paths and the following symbols were verified against the official
Gitiles tag `152.0.7977.42` on 2026-08-16:

- `class TabStripModel`
- `class TabGroupModel`
- `TabStripModelObserver::OnTabStripModelChanged`
- `SessionTab::extra_data`
- `SessionWindow::extra_data`
- `CreateAddTabExtraDataCommand`
- `CreateAddWindowExtraDataCommand`

## Compile-free boundary

Allowed now:

- catalog parser and corruption policy;
- pure membership projection from restored tab extra-data;
- duplicate UUID detection;
- atomic transaction/failure-injection tests;
- exact pinned-source symbol verification.

Blocked until a native Windows build can be compiled and exercised:

- filtering/hiding entries inside `TabStripModel`;
- persistent session command wiring;
- actual cross-workspace native tab/group moves;
- workspace close/archive;
- recently-closed and crash-restore integration;
- user-facing runtime completion claims.

## MVP scope decision

The first runtime experiment is one regular profile and one browser window.
Incognito and Guest are memory-only. Cross-window adoption is rejected in this
wave. Split view and vertical tabs remain out of scope.
