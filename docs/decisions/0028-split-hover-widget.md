---
doc_id: adr-0028-split-hover-widget
version: 1.0.0
canonical_path: docs/decisions/0028-split-hover-widget.md
updated: 2026-09-23
---

# ADR 0028: The dot becomes a widget on hover, and one of its three buttons is new behaviour

## Status

**Accepted, on the owner's instruction of 2026-09-23, and implemented by
`downstream/patches/0031-sunshine-split-link-mode.patch`,
`downstream/patches/0032-sunshine-split-hover-widget.patch` and an extension of
`downstream/patches/0027-sunshine-split-swap-button.patch`.** Read against the
pinned revision `152.0.7977.42`. **Nothing here has been compiled**, and §6
says what that leaves open — which is more than it left open for ADR 0021,
because this is a much larger change.

## Context

The owner asked for a widget that appears when the pointer is on the splitter,
carrying three things:

1. 반전 — reverse the two panes;
2. 링크 — "한쪽에서 클릭해서 들어가는 뎁스 페이지를 반대편 페이지로 여는 것";
3. 개별 탭으로 분리 — separate the split into ordinary tabs.

**Two of the three already exist upstream.** Read from source at the pin:

| Asked for | Already there |
|---|---|
| 반전 | `MultiContentsView::OnSwap()`, reached from the menu's `kReversePosition`, a double-click and a double-tap on the splitter, and — since ADR 0021 — Sunshine's dot |
| 개별 탭으로 분리 | `SplitTabMenuModel::CommandId::kExitSplit` → `TabStripModel::RemoveSplit(split_id)`, one call, and the tabs survive it |
| 링크 | **nothing** |

So the widget is an affordance for two existing actions and a home for one new
one. That division is the whole shape of this ADR: everything in §"Decision"
about 반전 and 분리 is about *reaching* upstream behaviour, and everything about
링크 is about *adding* behaviour, which is where the risk is.

**What 링크 is, precisely.** The owner's sentence defines it: a link clicked in
one pane opens in the other pane. The list stays put and the thing it opens
appears beside it. It is asymmetric — one side is the list, the other is what
the list opens — and the asymmetry is the feature, not an implementation
detail.

## Decision

### The widget is hosted by `MultiContentsView`, not by the splitter

`MultiContentsView::GetViewSizes()` reads `resize_area_->GetPreferredSize()`
and hands the panes what is left. ADR 0021's amendment is the record of what
that costs: a 20-pixel button inside the splitter doubled the splitter's width
and the panes gave up the difference, and the owner looked at it and said it
read as a gap.

A widget with three 24-pixel buttons is far wider than ten pixels, so it
**cannot** be a laid-out child of the resize area. It is a child of
`MultiContentsView`, positioned in `CalculateProposedLayout()` from its own
preferred size, centred on `resize_rect`. `GetViewSizes()` never hears about
it, so the splitter stays exactly upstream's width and the panes give up
nothing — which is the property ADR 0021's amendment bought and this change
had to keep.

ADR 0021 considered floating a view over the panes and rejected it: "costs a
custom view targeter, because views routes events by the parent's bounds and a
child drawn outside them is not hit tested". That reasoning was about a child
of the *resize area* drawn outside the resize area's bounds. A child of
`MultiContentsView` drawn inside `MultiContentsView`'s bounds needs no
targeter, and `lens_overlay_view_` is upstream's own precedent for exactly this
in exactly this function.

### The dot is the widget's resting state

While the widget is up the dot is hidden, and when it goes the dot comes back.
They are one control in two states — a mark that says *there is something
here*, and the something — rather than two controls, one of which would be
drawn underneath the other.

### Hiding is deferred, and it has to be

The widget is wider than the splitter and sits on top of it, so moving the
pointer from the splitter onto the widget **leaves the splitter**, and
`MultiContentsResizeArea::OnMouseExited` fires before the widget is entered.
Hiding on that report would make the widget vanish as the user reached for it.

Both the splitter and the widget report hover to `MultiContentsView`, which is
the only place that can see both, and the answer is acted on after 250 ms and
only if neither is under the pointer. That timer is a `base::OneShotTimer`; it
is not running at any other time, and §"Consequences" records what it cost in
`scripts/verify_no_interposition.py`.

### 링크 needs a `NavigationThrottle`, and nothing cheaper exists

An `<a href>` followed in the same frame never reaches the `WebContentsDelegate`
hook that opens a URL from a tab: that hook sees the navigations that ask for a
different target. This is why upstream's own "Open link in split view" is a
*context menu item* — the user has told the browser, before the navigation
exists, that this one goes elsewhere — and why the owner's request cannot be
written the same way. The only place the browser is asked about a same-frame
link before it commits is the navigation throttle list.

`sunshine::SplitLinkNavigationThrottle` is registered with one line in
`chrome/browser/chrome_content_browser_client_navigation_throttles.cc`.

### The conditions on that throttle are the security argument

The feature moves a navigation from the tab that asked for it into a tab that
did not. **Without conditions, a page could assign to its own location from a
timer and write into the other half of the user's split whenever it liked, from
a tab the user is not even looking at.** The throttle is created only for a
navigation that is all of:

- in the **primary main frame** — not a subframe, not a prerender;
- **renderer-initiated** — the omnibox, a bookmark and a restored session stay
  where the browser put them;
- `PAGE_TRANSITION_LINK` — which scripted assignment and form submission are
  not;
- carrying a **user gesture** — which a timer does not have;
- **cross-document** — an in-page anchor stays in the page;
- **http or https**.

and only when the mode is switched on for that tab. Every one of these is load
bearing and none is an optimisation.

### The mode is per-tab state that expires by itself

`sunshine::SplitLinkMode` is a `content::WebContentsUserData` on the anchor
tab, holding a weak pointer to the destination. **It is not a split model**:
it stores no ratio, no layout, no visual data, no pane identity. Invariant 12
of `docs/TAB_WORKSPACE_SPLIT_CONTRACT.md` is untouched.

Asked for a destination, it checks that the two tabs still agree on a split id
through `tabs::TabInterface::GetSplit()`. Close the split, drag a half out,
replace one half — the two stop agreeing and the mode reports no destination.
**Stale state is inert, so nothing has to clean it up**, and no observer, no
registry and no teardown hook was added.

**One anchor per split.** Switching the mode on for a pane switches it off for
the other. Both halves pointing at each other would send a link clicked on
either side to the other, so the first click on a depth page would turn the
depth page into the list.

### Three buttons, three strings and three icons, all upstream's

| Button | Action | String | Icon |
|---|---|---|---|
| 반전 | `MultiContentsView::OnSwap()` | `IDS_SPLIT_TAB_REVERSE_VIEWS` | `kSplitScene{Left,Right,Up,Down}Icon`, by `SplitTabMenuModel::GetReversePositionIcon`'s own rule |
| 링크 | `SplitLinkMode::Enable`/`Disable` | `IDS_CONTENT_CONTEXT_OPENLINK{LEFT,RIGHT,TOP,BOTTOM}VIEW`, by `GetOpenLinkInSplitStringAndIcon`'s own rule | `vector_icons::kLinkIcon` |
| 분리 | `TabStripModel::RemoveSplit(split_id)` | `IDS_SPLIT_TAB_SEPARATE_VIEWS` | `kOpenInFullIcon` |

**No new string and no new icon**, which is ADR 0021's rule and it is kept for
ADR 0021's reason: builds #46 and #49 both died in a resource pipeline, and a
feature that introduces no resource cannot fail that way.

The one thing this costs is that the 링크 button's tooltip names the action in
both states. Upstream has "Open link in the right view" and has nothing for
stopping, and Sunshine's own strings file is the command registry's — a label
naming no command fails `scripts/validate_commands.py`. So **on is drawn, not
described**: the button is filled while the mode is on. For a control that only
exists while hovered, a state visible without a second hover is the right trade
anyway.

## Consequences

### Cost: four upstream files, 32 owned becomes 36

`multi_contents_view.h`, `multi_contents_view.cc`,
`chrome_content_browser_client_navigation_throttles.cc` and
`chrome/browser/BUILD.gn`. Four created files join them, in
`chrome/browser/ui/sunshine/`, under a new `split_link` target in a BUILD.gn
that patch 0017 created — so the link mode adds no GN file of its own and
depends on no part of `//chrome/browser/ui`, which is the rule that directory
exists to keep.

`multi_contents_view.cc` returns to the stack after ADR 0021's amendment
removed it. The reason is different this time and worth naming: 0021 needed it
to keep an icon pointing the right way, and dropped it when the icon went. This
needs it because the widget has to be a child of that view to stay off the
splitter's preferred size.

### Two guards were narrowed, and both were broader than their invariants

**OS-9.** `scripts/verify_no_interposition.py` refuses navigation symbols in
Sunshine-authored text. OS-9 forbids *accepting a string and navigating to it*.
A `NavigationThrottle` is handed a navigation the browser already started and
already classified; the URL is the one the renderer was going to, and no text
crossed from a surface into the browser. §6 of `docs/OMNIBOX_CONTRACT.md`
records the second exemption, and `tests/test_no_interposition.py` pins every
shape it still rejects — the same load under another name, the same name
outside a throttle, and every other navigation symbol even inside one.

**PB-5.** The field rule rejected any field whose name contained `timer`, while
the symbol list next to it says in as many words that one-shot is legitimate.
The rule is now narrowed by the **declared type**, so renaming a
`base::RepeatingTimer` cannot buy the allowance and a `base::OneShotTimer` does
not have to be named dishonestly to keep it.

Both narrowings follow the precedent patch 0008 set and
`docs/ACCOUNT_LINK_PLAN.md` §9 restated: a security check broader than its
invariant is narrowed *with a test for every shape it still rejects*, and the
invariant is not touched.

### One test fixture was brittle and this is what found it

`tests/test_gesture_bindings.py`'s browser-ui-dependency fixture *inserted* a
line into a created file, shifting every line after it, so any later patch with
a hunk past that point stopped applying and the guard raised instead of
failing. The sibling fixture two tests above it documents the rule it broke.
Patch 0031 is the first patch to touch the end of that file, which is why this
surfaced now. The fixture replaces in place instead.

### The deferred-runtime allow-list gained two patches and lost a forbidden name

`tests/test_tab_workspace_split_contract.py` allowed exactly one patch to name
`split`, and forbade `RemoveSplit` in it. Three patches name it now, and
`RemoveSplit` is what 분리 *is*. What the rule protects — that Sunshine keeps no
split model of its own — is unchanged, and the forbidden list still holds every
part of one: `SplitTabVisualData(`, `split_ratio`, `SetSplitRatio`,
`UpdateSplitRatio`, `UpdateSplitLayout`, `AddToNewSplit`, and
`ReverseTabsInSplit` behind `OnSwap()`'s back.

### The stacked layout is handled and still unreachable

`kSplitViewHorizontal` is `FEATURE_DISABLED_BY_DEFAULT` at the pin, so
`SplitTabLayout::kStacked` cannot occur. The widget transposes its layout and
picks up/down icons and top/bottom strings anyway, for ADR 0021's reason: the
code path exists upstream and half-handling a layout is a defect waiting for
the day the flag flips.

## Alternatives rejected

**A menu on the splitter instead of a widget.** `SplitTabMenuModel` already
exists and would have cost almost nothing. It was rejected because the owner
asked for a widget on hover, and because a menu is two interactions for a
control the pointer is already touching.

**Making 링크 symmetric.** Both halves opening each other's links reads as
tidier and is worse: the first click on a depth page turns the depth page into
the list, which is the opposite of what the arrangement is for.

**Doing the destination load synchronously inside the throttle.** Rejected for
`GlicNavigationThrottle`'s reason — it posts its own navigation rather than
starting one from inside a throttle check. Ours is posted too.

**Naming the state on the split rather than on the tab.** A `SplitTabId`-keyed
map would need an observer to know when the split ends. A `WebContentsUserData`
plus a `GetSplit()` comparison needs nothing: the state answers "no
destination" the moment the arrangement stops being true.

## NOT VERIFIED

- **Nothing here has been compiled.** No native build has run since this was
  written, and this is a much larger change than the dot — which shipped
  invisible in build #61 for a mistake a compiler would never have caught.
  Expect more than one build round.
- **Nobody has seen the widget.** Whether it is the right size, whether 250 ms
  is the right delay, whether it blocks enough of the splitter to make dragging
  annoying, and whether the filled link button reads as *on* are all questions
  a running build answers.
- **The link mode has never intercepted a navigation.** The condition list is
  read from `content::NavigationHandle` at the pin, not observed. RV-69 to
  RV-74 are the runtime checks and all six are unrun.
- The claim that the widget does not widen the splitter is read from
  `GetViewSizes()` and `CalculateProposedLayout()`, not measured.
