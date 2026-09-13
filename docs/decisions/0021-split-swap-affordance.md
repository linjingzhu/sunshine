---
doc_id: adr-0021-split-swap-affordance
version: 1.0.0
canonical_path: docs/decisions/0021-split-swap-affordance.md
updated: 2026-09-05
---

# ADR 0021: The split swap is upstream's; only the affordance is Sunshine's

## Status

**Accepted, and implemented by `downstream/patches/0027-sunshine-split-swap-button.patch`.**
Read against the pinned revision `152.0.7977.42`. It is not compiled here; the
NOT VERIFIED section says exactly what that leaves open.

## Context

The owner asked for two things: a way to swap the left and right panes of a
split, and a button for it on the central splitter.

**The first already exists, three times over.** Read-from-source at the pinned
revision:

| Existing entry point | Where |
|---|---|
| "Reverse views" menu item | `SplitTabMenuModel::CommandId::kReversePosition`, reachable from the inactive pane's mini toolbar, the toolbar button, and the tab context menu |
| Double-click on the splitter | `MultiContentsResizeArea::OnMouseReleased`, `event.GetClickCount() == 2` → `MultiContentsView::OnSwap()` |
| Double-tap on the splitter | `MultiContentsResizeArea::OnGestureEvent`, `tap_count() == 2` → the same |

`docs/TAB_WORKSPACE_SPLIT_CONTRACT.md` §4.2 had already found this: Sunshine
once registered a `split.swap` command and retired it, because the native swap
"is strictly larger than the Sunshine one was — it reorders the tab strip *and*
the view hierarchy and updates the active index, which a metadata-only swap
cannot do."

So the request is not for a capability. It is for a **visible** one. A
double-click on a ten-pixel divider is not discoverable by anyone who has not
been told, and the menu route costs two clicks and a read.

## Decision

**Add a button, add nothing else.** The button calls
`MultiContentsView::OnSwap()` — the same function the double-click reaches — so
there is exactly one swap in the product and the button is a way of seeing it,
not a second implementation of it.

Three things it deliberately does not do:

1. **It registers no command.** §4.2 retired `split.swap` and concluded "split
   view needs no Sunshine command surface". That conclusion is unchanged: a
   view affordance is not a command, `first_party/commands.json` is untouched,
   and the retirement is not being quietly reversed.
2. **It writes no split state.** Invariant 12 holds — orientation, ratio, pane
   focus and pane identity stay Chromium's, read and never mirrored. The button
   reads `MultiContentsView::GetActiveIndex()` to point its icon and stores
   nothing.
3. **It adds no string and no icon.** The tooltip and accessible name are
   `IDS_SPLIT_TAB_REVERSE_VIEWS`, the menu item's own label, already translated
   into every locale Chromium ships. The icon is the same
   `kSplitScene{Left,Right,Up,Down}` set `SplitTabMenuModel::GetReversePositionIcon`
   picks from, by the same rule. **This is the point of the design**: builds #46
   and #49 both died in a resource pipeline — a stylesheet upstream's linter
   rejected, a `.grd` upstream's XML parser could not read — and a feature that
   introduces no resource cannot fail that way.

## Amendment, 2026-09-13: the open question got its answer

This ADR left one thing open and RV-47 was written to ask it: whether a
20-pixel splitter reads as *a divider with a control on it* or as *a gap*. The
owner looked at a running build and said gap.

**So the splitter goes back to upstream's width and the affordance becomes a
dot.** `kSunshineSwapButtonSize` is 10, which is not a round number chosen for
looks — it is exactly `kHandleResizeAxisSize + kHandleResizeAxisPadding`, the
width upstream already reserves for the drag handle. The dot therefore never
becomes the widest child, `MultiContentsView::GetViewSizes()` subtracts what it
always subtracted, and **the panes give up nothing**.

**The icon had to go for the width to.** A 16-pixel split-scene arrow needs a
20-pixel button; at 10 it would have been mush. The mark is now drawn the way
`MultiContentsResizeHandle` draws itself — `views::CreateRoundedRectBackground`
with the same `kColorSidePanelHoverResizeAreaHandle` token and a radius of half
the side, which is a circle. Nothing is painted by hand.

**And the direction went with it, which is the part worth reading twice.** The
arrow pointed at the side the active pane would travel to, and keeping it
correct is the only reason this patch ever touched
`chrome/browser/ui/views/frame/multi_contents_view.cc` — two hunks calling
`UpdateSunshineSwapButton()` from the two places `active_index_` moves. **A dot
has no direction, so the function, both call sites and the whole file section
are gone.** The stack owns one fewer upstream file: 33 becomes 32.

What is lost: the affordance no longer says *which way* the swap will go. It
says *there is a swap here*, and the tooltip names it. That is a real
reduction, it was the owner's call, and RV-47 is rewritten to check the new
answer rather than to keep asking the old question.

The tooltip is unchanged and was never missing — `IDS_SPLIT_TAB_REVERSE_VIEWS`,
the menu item's own string, since the first version.

## Consequences

### The splitter is twenty pixels wide, not ten

`MultiContentsView::GetViewSizes()` reads `resize_area_->GetPreferredSize()` and
gives the panes what is left, so widening the splitter is a supported change
rather than an overlap: the panes shrink by the difference and nothing overlaps
anything. Upstream reserves ten pixels (a four-pixel handle plus six of
padding); a 20 px button needs twenty.

Ten pixels of content, on a 1920 px window, is half of one percent. The
alternative — floating the button over the panes, outside the splitter's bounds
— buys those ten pixels back and costs a custom view targeter, because views
routes events by the parent's bounds and a child drawn outside them is not hit
tested. That is a real mechanism to get wrong for half a percent.

### The button is always visible; the drag handle is not

Upstream paints the drag handle only on hover or focus
(`MultiContentsResizeHandle::UpdateVisibility` toggles the *layer*, so the
handle occupies layout space either way). The button does not follow that rule,
and that is deliberate: an affordance that appears only once the pointer is
already on the divider solves nothing for a user who does not know the divider
does anything. Discoverability is the entire feature.

### The icon has to be corrected when the active pane moves

It shows which way the *active* pane would travel, which is what the menu item's
icon shows. `active_index_` moves in exactly two places —
`MultiContentsView::SwapContentsInSplitView()` and
`MultiContentsView::SetActiveIndex()` — and both now call
`MultiContentsResizeArea::UpdateSunshineSwapButton()`. That is the third upstream
file this costs, and it is worth one file: without it the icon is confidently
wrong half the time, which is worse than having no icon.

### Cost

Three upstream files, taking the stack from 28 owned to 31:
`multi_contents_resize_area.h`, `multi_contents_resize_area.cc`, and
`multi_contents_view.cc`.

### The stacked layout is handled but unreachable

`kSplitViewHorizontal` is `FEATURE_DISABLED_BY_DEFAULT` at the pin
(`docs/TAB_WORKSPACE_SPLIT_CONTRACT.md` §6), so `SplitTabLayout::kStacked` cannot
occur and "좌우 반전" is the only case a user can reach. The up/down icons and
the transposed layout are written anyway, because the code path exists upstream
and a Sunshine change that only half-handles a layout is a defect waiting for
the day that flag flips.

## NOT VERIFIED

- **Nothing here has been compiled.** No native build has run since this was
  written.
- **Nobody has seen the button.** Whether 20 px reads as a divider with a
  control on it or as a gap, whether the button crowds the drag handle, and
  whether the icon direction is legible at a glance are all questions a
  screenshot answers and a patch does not. RV-44 to RV-47 are the runtime
  checks and all four are unrun.
- The claim that the panes simply shrink by ten pixels is read from
  `GetViewSizes()` and `CalculateProposedLayout()`, not observed.
