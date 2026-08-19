---
doc_id: adr-0014-bookmark-bar-contribution-point
version: 1.0.0
canonical_path: docs/decisions/0014-bookmark-bar-contribution-point.md
updated: 2026-08-19
---

# ADR 0014: Putting one Sunshine button on Chromium's bookmark bar

## Status

**Accepted, and implemented by `downstream/patches/0008-sunshine-module-home-button.patch`.**
Read against the pinned revision `152.0.7977.42`. It is not compiled here; the
NOT VERIFIED section says exactly what that leaves open.

## Context

The owner asked for a button on the bookmark bar, at the leading edge, left of
the saved tab group button, that opens the module home.

That is one sentence and it crosses a boundary this project has been careful
about. Every Sunshine surface so far reaches the user by URL: it is a
`chrome://` host, registered through the seam in ADR 0007, and nothing upstream
knows it exists. A button on the bookmark bar is the opposite kind of change —
it is Sunshine appearing inside a Chromium view, in a file Chromium owns and
edits.

ADR 0007's seam does not help here and was never meant to. It removes upstream
collisions **for pages**: a `WebUIConfigMap` registration and a shared resource
bundle. A button is not a page. It registers no host and needs no resource; it
needs a place in a views hierarchy that upstream lays out by hand.

## Decision

**One button, two upstream files, no seam.**
`chrome/browser/ui/views/bookmarks/bookmark_bar_view.h` and its `.cc` are added
to the set patch 0008 owns exclusively, bringing the stack from 12 upstream
files to 14.

### 1. Why not a seam

A seam is worth building when the second contribution would collide with the
first. ADR 0007 measured that for WebUI surfaces and found the collision real:
a second surface's host constant touched all seven of the same upstream files.

Here there is no second contribution. There is one button, and there is no
queue of others behind it — the module home is the browser's own front door,
not a pattern modules will each want a copy of. Building a registry so that
future buttons could register into it would be building for a demand nobody has
expressed, and the registry itself would have to live in these same two files.
It would cost what the direct change costs and buy an abstraction nothing uses.

If a second native contribution to this bar ever arrives, that is the moment to
measure whether it collides, exactly as ADR 0007 did. Guessing now is how the
split-view model got built twice.

### 2. What the button does

It opens `chrome://sunshine-modules` through `page_navigator_->OpenURL()`, with
the disposition taken from the event flags — the same three lines
`AppsPageShortcutPressed()` already uses, so a ctrl-click opens a new tab and a
middle-click behaves the way it does everywhere else on this bar. Matching the
neighbour was the point: a button that ignored modifiers would be the one
control on the bar that does.

It does **not** call `chrome::UpdateBookmarkBarVisibilityPrefOnUserAction()`,
which the apps shortcut does. That call exists to keep the bar open after the
user has used a shortcut on it from the New Tab page, where the bar is shown
transiently. Sunshine's button has no such story, and borrowing the call would
have it quietly write a user preference nobody asked it to write.

### 3. Always present, unlike its neighbours

Everything else at this end of the bar is behind a preference: the apps
shortcut has `kShowAppsShortcutInBookmarkBar`, the managed folder appears only
under policy, the tab group bar has `kShowTabGroupsInBookmarkBar`. The Sunshine
button has none, and that is a decision rather than an omission.

A preference is a promise to honour it everywhere — the layout, the minimum
size, the context menu that offers to toggle it, and the migration for profiles
that predate it. None of that is free, and none of it was asked for. The
button is the way into the browser's own module list; a browser that hides its
front door behind a setting is answering a question nobody asked.

The cost is stated plainly: **a user who does not want this button cannot turn
it off.** If that turns out to matter, adding the preference later is additive
— a visibility check in three places that already test visibility for the
buttons beside it.

Because it is always visible, it also always contributes to `GetMinimumSize()`.
That is the unconditional line in the patch, and leaving it out is how a button
ends up drawn over its neighbour in a narrow window.

### 4. Two untranslated strings

The tooltip and the accessible name are `u"Sunshine modules"` — literals, not
`IDS_` constants.

An `IDS_` constant means owning `chrome/app/generated_resources.grd`. That file
is among the most-edited in Chromium, this stack rebases onto a new tag by
hand, and it would be owned for two strings. The trade is deliberate and it has
a real cost: **this button does not translate.** In a browser whose owner works
in Korean, that is worth naming rather than burying — it is a defect with a
known fix, not a design.

The fix, when the stack has a reason to own a string table anyway, is to move
these two into it. Until then a literal that is honestly one language beats a
resource id that pretends to be many.

### 5. A borrowed glyph

The icon is `kWebAssetIcon`, and it is borrowed rather than designed.

The natural choice was `kGridViewIcon` — Material's grid, which reads as "a set
of things". It was rejected on adjacency: at the pinned revision that is
exactly the icon the saved tab group button uses, and the saved tab group
button is the one immediately to the right. Two adjacent buttons sharing a
glyph is a worse failure than a glyph that means little.

`kListAltIcon` was rejected for the same class of reason — it is Chromium's
reading list icon, live in the app menu and the side panel of the same window.

`kWebAssetIcon` appears nowhere on the browser frame; its single use at the
pinned revision is the app menu's "Name window" item. So nothing it sits beside
already means something else, and the glyph itself — a window with a block in
it — reads acceptably as a component.

**What would be better** is a Sunshine-owned `.icon`, and the reason it is not
in this patch is not that it was overlooked. It costs a third upstream file
(`chrome/app/vector_icons/BUILD.gn`), and a vector icon is written in a DSL
that nothing in this environment can compile. The one machine that could
compile it is also the only CI and the owner's own workstation, so a malformed
glyph costs a multi-hour build. Borrowing an icon that provably exists is the
cheaper first move; drawing one is a follow-up with a build behind it.

### 6. Leading edge means first child

`Init()` adds the button before `apps_page_shortcut_`, and `Layout()` places it
before everything else. Both, because the comment already in `Init()` says why:
child order is also focus order. A button drawn first and added last would be
reached last by the keyboard, which is the kind of defect that only shows up
for the people who would notice it most.

It is deliberately **not** given `VIEW_ID_BOOKMARK_BAR_ELEMENT`. That id marks
a view this bar treats as one of its bookmark elements, for its context menu
and its drag handling. This button is neither, and borrowing the id to look
native would enlist it in behaviour it cannot honour.

## Consequences

- The stack owns 14 upstream files instead of 12. Both new ones are in
  `chrome/browser/ui/views/`, which is more churn-prone than most of what the
  stack already owns, so this is the patch most likely to conflict on the next
  Chromium tag.
- `chrome://sunshine-modules` now has two ways in — the button and the URL —
  and the URL was already offered by the omnibox through
  `kSunshineWebUIHosts`. Neither is privileged over the other.
- The button cannot be hidden, does not translate, and wears a borrowed glyph.
  All three are recorded above with what fixing them would cost.

## NOT VERIFIED

- **Nothing here has been compiled.** The patch applies cleanly to a fresh
  checkout of the pinned revision — that was run — but `git apply` proves
  placement, not that the result builds. Every symbol used (`ShortcutButton`,
  `kWebAssetIcon`, `kColorBookmarkButtonIcon`,
  `ui::GetDefaultDisabledIconFromImageModel`, `page_navigator_`) was read at
  the pinned revision, and `kWebAssetIcon` was confirmed by finding an existing
  upstream use of it; none of that is a compiler.
- Whether the button is *visible in the right place* is RV-21, and whether it
  survives a narrow window is RV-25. Both are manual and both are NOT RUN.
- No claim is made about how the button behaves in a window with no bookmark
  bar shown, beyond the fact that the bar draws nothing when it is hidden.
