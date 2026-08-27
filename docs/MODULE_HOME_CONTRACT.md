# Module Home — Contract

## Status and scope

Applies to Sunshine OS on the pinned Chromium revision `152.0.7977.42`. It
defines `chrome://sunshine-modules`: the page that says what this browser is
made of, and the bookmark bar button that opens it.

It is the fourth surface on the seam in
`docs/decisions/0007-module-contribution-seam.md` and the first one reachable
from Chromium's own chrome rather than only by URL —
`docs/decisions/0014-bookmark-bar-contribution-point.md` covers that half.

## 1. The one structural decision

**This page reports; it does not administer.**

It looks like the Chrome Web Store developer dashboard because the owner asked
for that layout, and the resemblance is where the similarity stops. That
dashboard manages things that can be installed, removed and configured at
runtime. Sunshine's modules are compiled in: the registry is fixed when the
browser is built, and there is nothing on this page to enable, disable, remove,
reorder, or grant.

That is not a limitation to be worked around later. It follows from ADR 0006 —
modules are not separately loadable code — and a control that implied otherwise
would be lying about the browser it is part of. The single action the page
offers is *reload the registry*, and the honest thing about it is that it
re-reads a constant.

### Going somewhere is not administering something

The page carries one link, added by
`downstream/patches/0013-sunshine-module-shell-entry.patch`: **Open the module
shell.** It exists because `chrome://sunshine-shell` had no route to it at all
— it is in the omnibox's host list and nowhere else, so a person had to know
the address of a surface the browser ships. A feature nobody can reach is
unfinished, not minimal.

It does not weaken MH-1. Navigating to another Sunshine surface installs
nothing, removes nothing, enables nothing and grants nothing; the registry is
the same constant before and after. And it does not weaken MH-4: the link is
written out in `app.html` with a fixed address, so no registry value reaches
the page as markup and none could.

**It links to the shell, not to a module.** The shell is not in the module
list, because it is not a module — it is what a module is mounted into, and
putting it among the modules would make the page disagree with the registry
about how many there are (MH-5). When a module declares a mount, the route to
*it* is the shell's dock, which is the shell's job and not this page's.

### The registration section, and why it is prose

`downstream/patches/0014-sunshine-module-registration-entry.patch` adds a
section to the overview, `#registration`, and makes it the destination of the
**Register** control at the foot of the module shell's dock.

The owner asked for a button that registers a module. **There is no such act to
perform.** A module is compiled in, so registration is four things that happen
before this browser exists: a manifest is written, the manifest is validated,
the browser is built, and the module is then in the list. A button that
appeared to do it at run time would be the exact failure §1 names — a control
lying about the browser it is part of.

So the control exists and goes somewhere, and the somewhere says what
registration is. That is a real gap closed: nothing in the browser previously
answered *how does a module come to be here*, and the question is the first one
a person asks after seeing a list of five.

The section is written out in `app.html` rather than built by `app.ts`. Nothing
in it comes from the registry, so **MH-4 is untouched by construction** rather
than by care, and it mutates nothing, so MH-1 holds as well.

Its last paragraph states the trade rather than hiding it: adding a module
needs a build, and what that buys is that no module ever arrived later from
somewhere else. `docs/decisions/0016-relaxations-for-porting.md` §5 kept that
rule for the same reason and said so in one line — *loadable modules are a
supply chain, and a supply chain is an outside.*

## 2. Invariants

Class **O** is decidable offline. **B** needs the built browser.

| ID | Invariant | Class |
| --- | --- | --- |
| MH-1 | The page mutates nothing. No control on it installs, removes, enables, disables, reorders, or changes the permission of any module. | O |
| MH-2 | The page reports the manifest's own words. A permission, status, or verification state is shown as the value `first_party/` holds; the page computes no verdict of its own. | O |
| MH-3 | The registry the page is served is byte-identical to `first_party/`. A module declared there and absent here, or the reverse, is a build failure and not a display bug. | O |
| MH-4 | No module data reaches the page as markup. Every value is placed as text; nothing on this surface assigns markup from the registry. | O |
| MH-5 | The list and the count agree, and both agree with the registry order. What the left column shows is the registry, in the registry's order, in full. | B |
| MH-6 | `pending` is reported as unrun, never as passed and never as failed. A verification state the gates have not decided must not be shown as a decision. | B |
| MH-7 | A module's description is carried in the manifest in **both** Korean and English, and the page shows one of them with a control that switches. Neither is derived from the other, and a module declaring only one is refused. | O |

MH-1, MH-2 and MH-4 are decidable from the patch source. MH-3 is enforced by
`scripts/verify_module_registry_sync.py`, which is the only one of these with a
check today.

### Why MH-3 needs a guard and the others do not

`first_party/` is on this side of the patch stack and the browser is built from
a Chromium checkout; nothing carries a directory of JSON files across that gap.
So the registry is baked into
`downstream/patches/0007-sunshine-modules-webui.patch` as a string literal, and
a copy is a thing that drifts.

Drift here is worse than drift in a document. Every other guard in this project
protects a claim made in prose; this one protects the claim a *surface* makes to
the person using the browser. A module added to `first_party/` and not to the
patch is a module the module home says does not exist — and the module home is
precisely where someone would go to check.

The guard compares bytes, against a canonical form defined once in
`scripts/module_registry_payload.py`. Byte equality is deliberately stricter
than JSON equivalence: a hand-edit that reformats but does not change meaning
still fails, because the alternative is a comparison with opinions about which
differences matter.

**What the guard cannot reach** is whether the running page shows what it was
served. That is RV-23, and it is manual.

### Why MH-4, given that the registry is first-party

Nothing in `first_party/` is attacker-controlled today, so an `innerHTML` on
this page would not be a vulnerability this week. MH-4 exists because that
sentence has a date on it. This is a privileged page; the registry is the one
piece of data on it that names things a person wrote; and the cost of building
every node with `textContent` while the data is trusted is zero, against an
audit of every assignment if it ever stops being.

### The description, in two languages — MH-7

**Decided by the owner: Korean and English, switchable on the page.** Not
derived from the browser's UI locale.

That settles a question the seam would otherwise have answered badly. A page
following the UI locale would show a Korean reader nothing when a module
declared only English, and the failure would look like a module with no
description rather than a locale with no translation.

**The manifest gains one field, and it is an object rather than a string:**

```json
"description": {
  "ko": "이 모듈이 무엇을 하는지, 한 문단.",
  "en": "What this module does, in one paragraph."
}
```

| Rule | |
| --- | --- |
| Both keys required | A module with one language is refused by `scripts/validate_first_party_modules.py`. Half a translation is how a switch turns into a blank. |
| Plain text | No markup. The page writes it with `textContent`, as it does every other manifest value. |
| Bounded | **400 characters per language**, refused above it. This row used to say "the same limit as any other display string this page draws". There was no such limit — the page draws `display_name`, ids and manifest words with no bound on any of them — so the row pointed at nothing. The number is set in `scripts/validate_first_party_modules.py` and named here. |
| Not localisation infrastructure | This is data in a manifest, not a Chromium string resource. It does not enter `.grd`. |

**The switch is the page's, and it is one control rather than one per module.**
A reader picks a language, not a language per row.

**Why both are required rather than one plus a fallback.** A fallback makes the
missing translation invisible: the switch appears to work while one language
quietly shows the other's text. Refusing at validation makes an untranslated
module a build failure, which is the only moment anyone is in a position to
write the missing paragraph.

**Built.** The field is in all five manifests and in
`first_party/templates/module.example.json`;
`scripts/validate_first_party_modules.py` requires exactly the two languages,
non-empty, under the limit and free of markup, with seven tests including the
one-language case the rule exists for; `downstream/patches/0007-sunshine-modules-webui.patch`
draws the paragraph and the switch.

Three details of the implementation are decisions rather than mechanics:

- **The switch is in the detail pane, beside the paragraph**, and is absent
  from the overview. A control that acts on nothing visible is a control that
  looks broken.
- **The choice is held in memory and written nowhere.** A remembered preference
  would be the first thing this page ever wrote, and MH-1's whole subject is
  that it writes nothing. The cost is that the choice resets when the page
  does, which is the right way round for a page whose job is to report.
- **Markup is refused even though it is inert.** Every value here is placed
  with `textContent` (MH-4), so a tag would render as text. It is refused
  because a description carrying markup is one somebody wrote expecting it to
  render, and this is a privileged surface.

**Not seen.** No build contains it yet — #47 predates it — so the switch has
never been clicked.


## 3. Acceptance criteria

1. **MHA-1.** No Sunshine-authored file on this surface assigns markup from
   registry data. (MH-4) — O
2. **MHA-2.** The registry baked into patch 0007 equals the canonical form
   computed from `first_party/`. (MH-3) — O
3. **MHA-3.** The page offers no control that writes: no form submission, no
   Mojo interface, no `chrome.send`. (MH-1) — O
4. **MHA-4.** Every module in `first_party/registry.json` appears in the left
   column, in that order, and the heading count matches. (MH-5) — B
5. **MHA-5.** A module whose manifest says `pending` shows `pending`. (MH-6, MH-2) — B

MHA-2 is enforced. MHA-1 and MHA-3 are decidable from the patch and are not
enforced yet; MHA-3 is close to free, because the surface is a plain
`content::WebUIController` with no interface to grant.

## 4. NOT VERIFIED

- **Nothing here has been compiled or run.** The patch applies cleanly to a
  fresh checkout of the pinned revision; that proves placement, not that it
  builds and not that it renders.
- MHA-1 and MHA-3 have no check. They are asserted by reading patch 0007.
- The layout is derived from wireframes the owner reviewed, not from a running
  page. No claim is made that it looks the same built.
- No claim is made about what the page does with a registry larger than a
  screenful; there are five modules and no scrolling behaviour has been
  designed for more.
- **The shell link has not been followed.** The surface it points at compiles
  as of build #33, but nobody has clicked the link, and what a person would
  arrive at is a skeleton with no module mounted in it.
- **The Register control has not been pressed.** Neither the dock's anchor nor
  the section it points at has been rendered by a browser. RV-38 is the gate.
