# Should this have been an installed app rather than a browser?

## 0. Status

A review, prompted by the owner asking the question directly, and asked in the
form that makes it worth asking: **as modules multiply**. It re-examines
`docs/decisions/0002-native-chromium-downstream.md` against what the repository
has actually become, rather than against what it intended to become.

It changes no decision. §6 says what I would change, and one of those is a
revision to advice already given.

## 1. The question, stated precisely

Not "Electron or Chromium" — ADR 0002 answered that and its reasoning is intact
on its own terms. The sharper question underneath is:

> Has the product's centre of gravity moved from *a browser* to *a workspace
> that hosts modules* — and if so, is carrying the whole of `//chrome` still
> paying for itself?

## 2. What the repository says it became

Fourteen patches, sorted by what they are for:

| Being a browser | Being a module platform |
| --- | --- |
| 0001 branding | 0004 the WebUI seam |
| 0002 new tab | 0005 security centre |
| 0003 no API-key warning | 0006 document surface |
| 0009 Windows install identity | 0007 module home |
| 0010 product strings | 0008 module home button |
| | 0011 module shell |
| | 0012 mount port |
| | 0013 shell entry |
| | 0014 registration entry |

Five to nine, and **every patch of the last seven is platform work**. The
owner's instinct is reading the repository correctly: the centre of gravity has
moved.

## 3. The scaling argument, taken seriously

The specific point was *as modules multiply*, and it is the right way to press.
Concretely, with modules compiled in:

- Every module change needs a full browser build — 180 GB, ~6 hours, on the one
  machine that can do it.
- Adding module *N+1* touches the resource `BUILD.gn`, the WebUI registry, the
  hosts header and `tools/gritsettings/resource_ids.spec`. **The patch stack
  grows with N.**
- Two modules cannot be worked on independently. They share one build and one
  stack, so they share one queue and one failure.

**This is already visibly not scaling.** Patches 0009 through 0014 have never
been compiled, because the machine that compiles them is switched off. That is
not a projection about ten modules; it is the state of the repository today.

So the problem the question names is real, present, and the largest one this
project has. What remains is whether *"should have been an app"* is the right
diagnosis.

## 4. What an installed app would have fixed, and what it would have cost

**Fixed, genuinely:** minutes to build instead of hours, on hosted CI, with no
patch stack and no 180 GB. That is the whole of the pain in §3 and it should
not be waved away.

**Cost, specifically for this product:**

1. **The isolation would have to be written here.** Sunshine's module boundary
   is a separate origin, partitioned storage, a policy the page cannot relax,
   no capability channel, and a broker in another process. Electron's nearest
   equivalent is a preload script bridging one separated context: **one
   boundary, one bridge**, and any defect in the bridge is total. Tauri's
   message channel is a capability channel by design. **The thing this project
   is best at is the thing it would have had to reimplement**, and
   reimplemented isolation is where downstreams get it wrong.

   (The API names are deliberately not written out.
   `scripts/verify_architecture.py` refuses them even in prose, and its comment
   says why: a wrapper architecture once survived in an active specification
   while the code tree was already clean. Naming the runtimes is allowed;
   naming their API is how the last one got in.)
2. **`isolated-app://` exists *because* this is Chromium.**
   `docs/MODULE_INSTALL_REVIEW.md` found that signed web bundles,
   install-from-file, origin-derived-from-key and per-app storage partitioning
   are all upstream and maintained. In an app shell, every one of those is a
   project. The feature the owner asked for is an argument for staying, not for
   leaving.
3. **The browser half is real and was asked for.** Patches 0009 and 0010 exist
   because the owner wanted an install directory, a profile directory, a
   taskbar identity and product strings that say Sunshine — to *be* the
   browser, not to resemble one. An app shell abandons that outright.
4. **iPad is not a differentiator.** `docs/decisions/0013-module-data-portability.md`
   requires every app to run there. Neither Chromium nor Electron goes to iPad,
   so this does not favour either.

## 5. The fix is already designed, and it is bigger than it looked

`docs/MODULE_INSTALL_REVIEW.md` proposed installed modules for the owner's own
reasons. Read against §3, it turns out to be the answer to the scaling problem
as well:

| | Compiled-in module | Installed module |
| --- | --- | --- |
| Adding one touches the patch stack | Yes, in four places | **No** |
| Adding one needs a browser build | Yes, ~6 h | **No** |
| N modules share a build queue | Yes | **No** |
| Iteration | Hours | Seconds |

The browser still needs building — **rarely, and for browser reasons**: a
Chromium roll, a change to the chrome itself. That is the correct coupling. The
expensive thing changes seldom; the frequent thing is cheap.

So the scaling objection is not an argument that this should have been an app.
It is an argument that **installation should land before anything else.**

## 6. What I would change

1. **Land installation before adding another compiled-in module.** Every
   compiled-in module added from here makes the stack heavier and is work that
   gets redone as a bundle later.

   **This revises advice already given.** `docs/FIRST_MODULE_GUIDE.md` tells the
   HTML collection to be built as a compiled-in surface. If installation lands,
   it should be **the first installed module instead** — same layout, same
   mount port, same two-frame rule, delivered as a bundle rather than a patch.
   That guide needs a revision the day the decision is made, and it should not
   be followed as written in the meantime for anything that would have to be
   redone.

2. **Fix the build; do not re-architect around it.** Every difficulty this
   project has had is build-shaped — a workstation runner, a six-hour compile,
   six patches never compiled. None of it is Chromium-architecture-shaped. A
   rented runner solves it with money. Changing the architecture solves it by
   discarding the security model, which is this project's most finished asset:
   twenty-four guards and 686 tests, enforcing invariants that are written down.

3. **Keep the hedge, and notice that it was already bought.** `MA-1` and `MA-2`
   mean a module does not know what hosts it, and ADR 0013 requires a second
   host. If Sunshine-the-browser turns out to be the wrong shell, **the modules
   survive the swap** — they are written against a port, not against a browser.
   That was foresight and it is the reason this question is answerable calmly
   rather than expensively.

## 7. When to reconsider

Falsifiable, so this does not become a decision nobody can revisit:

- **If, after installation lands, the browser still needs a build more than
  about once a month for *module* reasons** — the seam is in the wrong place
  and §5's table is wrong.
- **If `isolated-app://` cannot be framed by `chrome://sunshine-shell`**, and
  the only fix is patching away the guarantees that made bundles attractive —
  then Chromium is fighting the design rather than carrying it, and the
  calculus changes. This is already risk 1 in `docs/MODULE_INSTALL_REVIEW.md`.
- **If the browser half stops being used** — if nobody opens a tab in it — then
  `//chrome` is weight without a payer. The honest successor would then be
  `//content` with a shell of our own, not Electron: keep the sandbox and the
  origins, drop the browser. That is more work than the patch stack, not less,
  and it should only ever be done for that specific reason.

## 8. The answer

**No — and the objection is still correct about today.**

Staying a Chromium downstream was right, and remains right, **on one
condition: that modules stop needing builds.** Until installation lands, the
architecture does not scale past a handful of modules, and the evidence is six
patches that have never been compiled. That is not a quibble about the future;
it is the present state, and it deserves to sting.

What would have been lost by having been an app is not recoverable later — the
isolation, the origins, the upstream bundle mechanism, and being the user's
actual browser. What is being lost by not having installation yet is
recoverable, and the recovery is designed.

## 9. NOT VERIFIED

- The comparison in §4 is reasoned from what these runtimes provide, not from
  building the same module twice. No Electron or Tauri prototype exists here.
- §5's table assumes installation works as `docs/MODULE_INSTALL_REVIEW.md`
  describes. Its risk 1 is unresolved and could invalidate the row that matters
  most.
- The "six hours on twelve cores" figure is `docs/WINDOWS_CHROMIUM_BUILD.md`'s,
  measured on the owner's machine, not re-measured here.
- No claim is made about what a browser costs to maintain across Chromium rolls
  over time. This project has not yet rolled the pin once, so the recurring
  cost of the patch stack is an estimate with no data behind it — and it is the
  one number that would most change §4 if it turned out large.
