# Tab Groups, Workspaces, and Split View — Native Ownership Contract

**Status:** Implementation foundation; native runtime verification pending  
**Target:** Pinned Chromium revision in `config/chromium.version`  
**Constraint:** No Chromium compilation is required for this contract wave.

## 1. Product boundary

Sunshine does not replace Chromium's tab model. Chromium remains authoritative
for tabs, tab groups, navigation, WebContents lifetime, profile storage, and
session restore. Sunshine adds only persistent workspace membership and split
layout metadata around those native objects.

| Concept | Authority | Persistence boundary |
|---|---|---|
| Tab and active tab | Chromium `TabStripModel` | Chromium session restore |
| Tab group label, color, collapse state | Chromium `TabGroupModel` / `TabGroupVisualData` | Chromium tab-group/session state |
| Profile, cookies, site storage | Chromium `Profile` / `StoragePartition` | Profile-scoped Chromium storage |
| Workspace membership and ordering | Sunshine workspace metadata | Same profile only |
| Split panes, orientation, ratio | Sunshine window session metadata | Window/session scoped |

## 2. Non-negotiable invariants

1. A tab has exactly one native owner and at most one `workspace_id`.
2. A tab group never spans workspaces. Moving a grouped tab to another
   workspace first removes it from the source group unless the whole group is
   moved atomically.
3. A workspace never crosses a Chromium profile boundary. Moving a tab to a
   workspace in another profile is rejected; it is not implemented as a silent
   copy.
4. Switching workspaces hides inactive tabs but does not destroy their
   WebContents or navigation state.
5. A tab may occupy zero or one split pane. It cannot be rendered live in both
   panes.
6. Closing one split pane returns the survivor to the normal active view.
7. Closing a workspace requires an explicit destination or archive operation.
   Tabs are never silently discarded.
8. Invalid or stale persisted references fail closed: the normal active tab is
   shown and damaged split metadata is ignored.

## 3. Minimum persisted metadata

```json
{
  "schema_version": 1,
  "active_workspace_id": "workspace-development",
  "workspaces": [
    {
      "id": "workspace-development",
      "profile_id": "profile-default",
      "name": "Development",
      "color": "blue",
      "tab_ids": ["tab-1", "tab-2"],
      "pinned_tab_ids": ["tab-1"],
      "last_active_tab_id": "tab-2"
    }
  ],
  "split": {
    "orientation": "vertical",
    "primary_tab_id": "tab-2",
    "secondary_tab_id": "tab-3",
    "ratio": 0.5
  }
}
```

Rules:

- `schema_version` is mandatory; unknown future versions are not rewritten.
- IDs are opaque stable identifiers, never array indexes.
- `ratio` is finite and clamped to `0.25..0.75` before rendering.
- Both split tab IDs must exist, be distinct, and belong to the active
  workspace.
- `pinned_tab_ids` is an ordered subset of `tab_ids`.
- `last_active_tab_id` is either a member of `tab_ids` or omitted.

## 4. Commands

All UI entry points invoke the same command implementation.

| Command ID | Result |
|---|---|
| `tab.group.create` | Uses Chromium native tab-group APIs |
| `tab.group.ungroup` | Removes membership without closing tabs |
| `workspace.create` | Creates an empty same-profile context with a New Tab |
| `workspace.switch` | Projects the selected workspace and restores its last active tab |
| `workspace.tab.move` | Transfers membership while retaining native tab state |
| `workspace.close` | Requires destination/archive choice |
| `view.split.open` | Places two distinct active-workspace tabs in two panes |
| `view.split.swap` | Swaps pane positions without navigation or reload |
| `view.split.close` | Returns the survivor to normal view |

## 5. UX contract

- **Entry points:** tab context menu for groups/move/split; workspace switcher
  adjacent to the tab strip; split toolbar inside the active window.
- **Visible result:** workspace switching changes the visible tab set without a
  page reload; split view displays exactly two independently focusable pages.
- **Blocked behavior:** cross-profile moves and same-tab split attempts remain
  unchanged and show a concise reason.
- **Recovery:** closing a split preserves both tabs; closing a workspace asks
  where its tabs should go; invalid restored layout falls back to one pane.
- **Accessibility:** group identity uses label plus color; pane focus is visible;
  every command is keyboard reachable and exposes its disabled reason.

## 6. Implementation sequence

1. Verify native Chromium tab-group create/rename/color/collapse/restore behavior.
2. Add profile-scoped workspace metadata and switching projection.
3. Add move-tab and close-workspace transactions with rollback on failure.
4. Add two-pane split metadata and focus routing.
5. Add restart recovery and corruption fallback tests.
6. Compile and run the pinned Windows Chromium target before claiming the
   feature as shipped.

## 7. Acceptance evidence

- A native tab group survives restart with label, color, membership, and order.
- Three workspaces retain independent visible tab sets in one profile.
- Switching workspaces does not reload pages or alter cookies.
- A grouped tab move cannot create a cross-workspace group.
- Split open, resize, swap, pane close, and restart recovery preserve tab state.
- A malformed split record falls back to one pane without losing tabs.
- Incognito and Guest state is not written to persistent workspace metadata.

Until the pinned Windows build and runtime suite pass, this work is reported as
an **implementation foundation**, not a completed browser feature.
