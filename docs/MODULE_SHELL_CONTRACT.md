# Module Shell — Contract

## Status and scope

Applies to Sunshine OS on the pinned Chromium revision `152.0.7977.42`. It
defines the five-region shell every module app is mounted into, and — the
reason it exists — **which of those regions the browser owns and which the
module owns.**

The geometry, the nine states, the splitter behaviour, the persistence keys and
the header rules are taken from the owner's `Module shell layout rules` (DEV OS
· LAYOUT PRIMITIVE v1). This document does not invent them; it records them,
draws the ownership line the drawing implies, and states the two places where
Sunshine's existing contracts disagree with it.

`docs/MODULE_APP_GUIDE.md` is the other half: this is what the browser
provides, that is what an app brings.

## 1. The one structural decision

**The skeleton belongs to the browser. Only the content belongs to the module.**

State 09 in the source drawing says it outright — *"Skeleton never changes;
only content is empty"* — and every ownership question below follows from it.

```text
┌──────────────────────────────────────────────────────────────┐
│ A  module bar · 32px · toggle + global utilities   ← BROWSER │
├────┬───────────┬─────────────────────────┬───────────────────┤
│ B  │ C         │ D                       │ E                 │
│    │           │ ┌─────────────────────┐ │ ┌───────────────┐ │
│ do │ tab list  │ │ header 40px ←BROWSER│ │ │ container     │ │
│ ck │           │ ├─────────────────────┤ │ │      ←BROWSER │ │
│    │  frame    │ │                     │ │ ├───────────────┤ │
│ ←B │  ←BROWSER │ │  body               │ │ │ role content  │ │
│ RO │           │ │       ←MODULE       │ │ │     ←MODULE   │ │
│ WS │  content  │ │                     │ │ │               │ │
│ ER │  ←MODULE  │ └─────────────────────┘ │ └───────────────┘ │
└────┴───────────┴─────────────────────────┴───────────────────┘
```

| Region | Owner | Why it lands there |
| --- | --- | --- |
| **A** module bar | **Browser, wholly** | It exists when no module is loaded. Its toggle collapses B and C, which are not the module's to collapse. Its state is explicitly shell-global. A module that could move or remove it could hide the way out of itself. |
| **B** module dock | **Browser, wholly** | It lists *every* module. No single module can render it without knowing its siblings, and switching modules has to keep working when the current one is broken — which it cannot if the current one draws the switcher. |
| **C** tab list | **Browser frame, module content** | Width, collapse, splitter, persistence and selection rendering are the shell's; which tabs exist, their names and icons are the module's. |
| **D** body | **Browser header, module body** | The source drawing is explicit: the 40px header is *"모듈이 바꿀 수 없음"* — the module cannot change it. Everything below it is the module's. |
| **E** aux panel | **Browser container, module content** | One container, six roles, switched by the shell. What renders inside a role is the module's — and may belong to a *different* module than D's. |

### Why the line is there and not somewhere else

Three reasons, in the order they bind.

**A module must not be able to trap the user.** A, B and the D header carry
every way out: switch module, collapse, restore, open the aux panel. If a
module drew them it could omit them, and a module with a rendering bug would
take the exits with it.

**The chrome is privileged and the content is not.** This is the split
`docs/DOCUMENT_SURFACE_CONTRACT.md` §1 already makes for one surface,
generalised to all of them. The shell is a `chrome://` page at browser
privilege; module content is authored elsewhere and renders in a frame that
receives content and never capability. Putting a module's markup into the
shell's own document would run it at browser privilege, which is the failure
`docs/SECURITY_ARCHITECTURE_CONTRACT.md` exists to prevent.

**Consistency is only real if it is not voluntary.** The drawing's premise is
that *"어떤 모듈이든 같은 조작법으로 쓸 수 있습니다"* — any module, same
operation. A rule each module re-implements is a rule each module gets subtly
wrong. Regions the browser draws are identical by construction rather than by
discipline.

### What the shell does not provide

The source drawing proposes, as its own next step, standardising four body
templates — table, console, document, canvas. **The shell does not ship them,
and the owner settled that.**

They would sit in D's body, and D's body is the module's. A browser that
supplied the templates would own the shape of every module's work area, which
is the line §1 draws and the reason it is drawn there. The consistency argument
cuts the other way here too: a table layout is not an exit, so a module getting
it slightly wrong costs a little polish, while a module unable to lay out its
own work costs the module.

If four templates turn out to be worth sharing, they are a library that module
apps import — versioned with the apps, replaceable by an app that needs
something else — and not a region the shell draws. That keeps the boundary in
§1 intact.

## 2. Geometry

Machine-readable: `scripts/verify_shell_geometry.py` reads this table and the
constants in `downstream/patches/0011-sunshine-module-shell.patch` and fails if
they disagree. The names are the identifiers the patch must declare.

| Key | Value | Meaning |
| --- | --- | --- |
| `BAR_HEIGHT` | 32 | A. Fixed height, full width. The toggle is always its first item. |
| `DOCK_ICONS` | 56 | B, icons only. |
| `DOCK_EXPANDED` | 224 | B, icons with names. B has these two widths and no others; it is not draggable. |
| `TABS_DEFAULT` | 232 | C default. |
| `TABS_MIN` | 180 | C minimum. |
| `TABS_MAX` | 360 | C maximum. |
| `BODY_MIN` | 480 | D minimum. D is `flex: 1` and absorbs all remaining space. |
| `PANEL_DEFAULT` | 320 | E default. |
| `PANEL_MIN` | 280 | E minimum. |
| `PANEL_MAX` | 520 | E maximum. |
| `HEADER_HEIGHT` | 40 | D's header. Fixed; the module cannot change it. |
| `SPLITTER_VISUAL` | 4 | Drawn width of a splitter. |
| `SPLITTER_HIT` | 8 | Pointer target width of a splitter. |
| `HEADER_PAD_LEFT` | 16 | Header left padding; the body's left and right padding matches. |
| `HEADER_PAD_RIGHT` | 12 | Header right padding, because the aux toggle sits at the very end. |
| `DENSE_MIN_WIDTH` | 1440 | Below this, the four-region arrangement is not recommended. |
| `HEADER_ACTIONS_MAX` | 3 | Module actions the header will show. The aux toggle is not one of them and is always last. |
| `PANEL_ROLES` | 6 | inspector, preview, console, docs, assistant, tasks. |

**Collapse order under pressure.** When the viewport cannot satisfy the
minimums, regions yield in a fixed order: **E first, then C.** D never yields
below `BODY_MIN`, and B never yields at all. The order is the drawing's and it
is not arbitrary — E is supplementary, C is navigation, D is the work.

## 3. States

The nine states are not modes. They are the reachable combinations of four
booleans and two widths, and the shell must be able to reach all of them.

| # | Name | B | C | D | E |
| --- | --- | --- | --- | --- | --- |
| 01 | Default | 56 | 232 | flex | hidden |
| 02 | Dock expanded | 224 | 232 | flex | hidden |
| 03 | Tabs collapsed | 56 | hidden | flex | hidden |
| 04 | Full-bleed content | hidden | hidden | flex | hidden |
| 05 | Aux panel open | 56 | ≥180 | flex | 320 |
| 06 | All regions | 224 | ≥180 | flex | 320 |
| 07 | Resizing | — | drag | flex | — |
| 08 | Min-width clamp | 56 | 180 | 480 | 280 |
| 09 | Empty | 56 | 232 | flex | hidden |

State 03 hides C but keeps B, so switching modules still works with the tab
list away. State 04 is A's toggle collapsing B and C together, and it is the
only state in which the restore control moves into D's header. State 09 changes
no width at all: an empty module is empty content in an unchanged skeleton.

## 4. Splitter

| Rule | Behaviour |
| --- | --- |
| Target | 4px drawn, 8px hit area, `cursor: col-resize`. |
| Hover | Highlights over 100ms with no easing. |
| Drag | Live resize. No ghost line. |
| Clamp | Stops at the minimum and holds the cursor; below the clamp, E collapses first, then C. |
| Double-click | Returns that region to its default width. |

There are two splitters: C|D and D|E. **There is none at A or at B** — B has two
widths and no third.

## 5. Persistence

| Rule | Behaviour |
| --- | --- |
| Scope | Per module. Switching modules restores each one's own last state. |
| Keys | `dock`, `tabs.visible`, `tabs.width`, `panel.open`, `panel.role`, `panel.width`, `activeTab`. |
| Global | A's toggle and whether the dock is expanded are shell-wide, not per module. |
| Reset | Right-click a module → reset layout → defaults. |

`dock` and A's toggle are global while everything else is per-module, and that
asymmetry is deliberate: the dock and the bar are the browser's furniture, so
they should not rearrange themselves as the user moves between modules.

## 6. Invariants

Class **O** is decidable offline. **B** needs the built browser.

| ID | Invariant | Class |
| --- | --- | --- |
| MS-1 | A and B render from shell state alone. No module supplies their content, and no module can hide, move or resize them. | O |
| MS-2 | The D header is drawn by the shell. A module contributes a title, a path, an icon and at most `HEADER_ACTIONS_MAX` actions, and nothing else about it. | O |
| MS-3 | No module content reaches the shell's own document as markup. Content regions are frames. | O |
| MS-4 | Every width in §2 comes from one declared constant. A literal width in a rule or a stylesheet is a defect even when the number is right. | O |
| MS-5 | D is never narrower than `BODY_MIN` while it is visible. Under pressure E collapses, then C. | B |
| MS-6 | The skeleton is identical across modules and across states. Only content changes. | B |
| MS-7 | Layout state restores per module, and A's toggle and the dock width do not. | B |
| MS-8 | Every state in §3 is reachable, and every one of them is reachable back. | B |

MS-4 is the one with a check today: `scripts/verify_shell_geometry.py` compares
§2 against the patch.

## 7. Where this disagrees with Sunshine's existing contracts

Two, and both are the owner's to settle. The shell is built to Sunshine's side
of each, so that it passes the guards that already exist; the drawing's values
are recorded here so that the choice stays visible rather than being lost in a
stylesheet.

**Colour.** The drawing names hex values — `#0f62fe` focus, `#4589ff` selection
and active splitter, `#393939` separators and selected background, `#f4f4f4`
selected foreground, `#6f6f6f` secondary text, `rgba(141,141,141,.12)` hover.
That is IBM Carbon's palette. `docs/DESIGN_SYSTEM_CONTRACT.md` §2.1 and §2.3
require every colour to resolve through Chromium's own pipeline with no
fallback, so that a theme change reaches the surface and a missing token fails
visibly. The shell therefore uses tokens, and looks like the drawing only to
the extent the active theme resembles Carbon.

To follow the drawing exactly, the design-system contract has to change first —
and the cost is not the hex values, it is that a hardcoded palette stops
following the user's theme, including dark mode and high contrast.

**Type.** The drawing specifies `14px/600` for the header title and `11px mono`
for the path. The design system's scale is in rem, with 0.75 as its smallest
step, and `scripts/verify_design_tokens.py` fails a `px` font size outright.
The shell uses `0.875rem` and `0.75rem`, which are the nearest steps — 14px and
12px at the default root size. **The path text is therefore 12px, not 11px.**

## 8. NOT VERIFIED

- **Nothing here has been built into a running browser.** The patch applies to
  a fresh checkout of the pinned revision; that is placement, not behaviour.
- **No module is mounted in it.** The content regions render the shell's own
  empty states, because the host port in `docs/MODULE_APP_GUIDE.md` §1 has no
  implementation yet. So MS-3 is satisfied trivially — there is no module
  content to keep out of the document — and it will need re-checking when there
  is.
- MS-5 through MS-8 need the browser and a person. They are RV-31 to RV-34.
- The nine states were transcribed from the drawing by reading it. No automated
  check compares this document to that PDF, and none can.
