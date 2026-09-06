---
doc_id: adr-0022-no-tab-groups-on-the-bookmark-bar
version: 1.0.0
canonical_path: docs/decisions/0022-no-tab-groups-on-the-bookmark-bar.md
updated: 2026-09-06
---

# ADR 0022: The saved tab group button is off by default

## Status

**Accepted, and implemented by `downstream/patches/0028-sunshine-no-tab-groups-on-bookmark-bar.patch`.**
Read against the pinned revision `152.0.7977.42`. It is not compiled here; the
NOT VERIFIED section says exactly what that leaves open.

## Context

The owner pointed at the bookmark bar's leading edge — the Sunshine module home
button, and beside it the grid glyph of Chromium's saved tab group bar — and
asked for the second one to go.

**There is already a switch.** Read-from-source at the pin: the bookmark bar's
own context menu carries `IDC_BOOKMARK_BAR_TOGGLE_SHOW_TAB_GROUPS`, labelled
`IDS_BOOKMARK_BAR_SHOW_TAB_GROUPS` ("Show tab groups"), and toggling it writes
the syncable boolean `bookmark_bar.show_tab_groups`.
`chrome::ShouldShowTabGroupsInBookmarkBar()` reads it and
`BookmarkBarView::OnTabGroupsVisibilityPrefChanged()` acts on it. So the button
can be hidden today, on the build the owner already has, with no patch at all.

What that switch cannot do is make it Sunshine's default, which is what the ask
means: not "hide it on my machine" but "this product does not have it".

## Decision

**Change the registered default from `true` to `false`, and change nothing
else.** One token in
`components/bookmarks/browser/bookmark_utils.cc::RegisterProfilePrefs`, which
becomes the 32nd upstream file the stack owns.

### Why the default, and not the view

Three routes were priced:

| Route | Cost | Why not |
|---|---|---|
| Stop creating `saved_tab_group_bar_` in `BookmarkBarView::Init()` | 0 new files — patch 0008 already owns that file | `OnTabGroupsVisibilityPrefChanged()` holds `DCHECK(saved_tab_group_bar_)` and is reached whenever the pref changes. A null bar there is a debug crash |
| Force `SetVisible(false)` at both call sites | 0 new files | The context menu item would still toggle a pref that no longer does anything. A dead control is worse than a visible button |
| **Move the registered default** | 1 upstream file | Chosen |

### Why not `SetDefaultPrefValue()` from Sunshine's own registration

`chrome/browser/prefs/browser_prefs.cc` is already owned, and it already calls
`sunshine::RegisterProfilePrefs(registry)`. Overriding the default there would
have cost no new file at all.

It would also have crashed. `SetDefaultPrefValue()` requires the pref to be
registered already, and `bookmarks::RegisterProfilePrefs()` is not called from
`chrome::RegisterProfilePrefs` — it is called by
`BookmarkModelFactory::RegisterProfilePrefs()`, through the keyed-service
registration pass, which is a different pass. The pref would not have existed
yet.

**This is recorded because the cheap route was tempting and the reason it fails
is invisible in the diff.** Nothing in `browser_prefs.cc` shows that bookmarks
registers elsewhere; it took reading the factory to find out.

## Consequences

- **The user's switch still works.** Only the default moves. "Show tab groups"
  stays in the context menu, unchecked, and turning it on brings the button
  back. RV-49 exists to catch the day that stops being true.
- **A profile that already stored a value keeps it.** The pref is written only
  when toggled, so a profile that never touched it picks up the new default —
  including the owner's existing profile. A profile that toggled it on keeps
  its own `true`, which is correct and is why RV-48 says to use a fresh
  profile.
- **The pref is syncable.** On a signed-in profile the stored value travels;
  the default does not. Sunshine has no sign-in today, so this is a note rather
  than a caveat.
- Tab groups themselves are untouched. This is the bookmark bar's button, not
  the feature: `tab_groups::prefs::RegisterProfilePrefs` and everything behind
  it are unchanged, and tab groups keep working in the tab strip.

## NOT VERIFIED

- **Nothing here has been compiled**, and nobody has seen the bar without the
  button. RV-21, RV-48 and RV-49 are the runtime checks and all three are unrun.
- That the owner's existing profile has no stored value for this pref is
  inferred from "the pref is written only on toggle", not read off their
  profile. If the button survives on their machine, that inference is where to
  look first.
