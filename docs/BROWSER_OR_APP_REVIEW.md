# Should this have been an installed app rather than a browser?

## 0. Status

A review, prompted by the owner asking the question directly, and asked in the
form that makes it worth asking: **as modules multiply**. It re-examines
`docs/decisions/0002-native-chromium-downstream.md` against what the repository
has actually become, rather than against what it intended to become.

**The owner answered it, and the answer is recorded here so it is not asked a
third time:** *the browser is what gets used most, so that is what it was built
on.* `docs/decisions/0002-native-chromium-downstream.md` stands, and stands for
a reason about use rather than about architecture — which is the strongest kind
of reason a product decision can have, and the one this review could not have
supplied on its own.

What follows is the analysis that was done before that answer. It is kept
because §3's objection is true regardless of the answer, §6 is work either way,
and §7 is what would make this worth asking again.

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

**This was already visibly not scaling**, and the evidence has since changed
shape rather than gone away. When this was written, patches 0009 through 0014
had never been compiled because the machine that compiles them was switched
off. Build #33 has since compiled 0009 through 0016 — in three attempts, over
about forty minutes of build machine time, on the one machine that can do it,
while the owner was at it. The objection stands on the *coupling* rather than
on the backlog: a module change still cannot be validated without that
machine.

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

The owner's own reason is the one that settles it: *the browser is what gets
used most.* A module platform hosted inside the thing a person already has open
all day is worth more than a better-built one they have to go and launch. That
is a fact about use, and no amount of build arithmetic outweighs it.

Staying a Chromium downstream was right, and remains right, **on one
condition: that modules stop needing builds.** Until installation lands, the
architecture does not scale past a handful of modules. The backlog that made
that vivid is gone — build #33 compiled it — but the coupling that produced
the backlog is not, and it is the coupling that was the argument.

What would have been lost by having been an app is not recoverable later — the
isolation, the origins, the upstream bundle mechanism, and being the user's
actual browser. What is being lost by not having installation yet is
recoverable, and the recovery is designed.

## 9. The web-app framing, and the size question

The owner returned to this with a sharper version: *should Sunshine have been a
web app you install — like the installed Claude — with the browser implemented
inside it?* And two supporting observations: **Chromium carries a lot Sunshine
does not need**, and **why is it so large?**

The second question turns out to be the one that answers the first.

### 9.1 The size, as actually measured

| | |
| --- | --- |
| `chrome.exe` | **4.1 MB** |
| `mini_installer.exe` | **117.5 MB** |
| Installed payload | **never measured** until now |

Build #33, commit `ca1f5c0`. The first number is not the browser: `chrome.exe`
is a launcher stub. The browser is `chrome.dll`, and neither it nor the resource
paks, the ICU data, the V8 snapshot, the ANGLE and SwiftShader libraries nor the
locale files had been counted by anything — while `docs/SIZE_BUDGET.md` carried
an installed-bundle threshold of 250 MB. **A threshold beside no measurement.**
`scripts/measure_shipped_size.py` now reads upstream's own shipped-file manifest
and sums the payload; build #34 is the first run.

**What those 117.5 MB are is not a feature list. It is the web platform.** Blink
implements the whole rendering and DOM surface; V8 is a multi-tier optimising
JIT; Skia is a complete 2D graphics engine; the network stack carries its own
TLS, HTTP/2 and QUIC. Every one of those exists so that an HTML file appears on
screen — which is the one thing every Sunshine module does.

### 9.2 A web app does not escape that size. It relocates it

There are two ways to be a web app on Windows, and neither is smaller:

| | |
| --- | --- |
| **Electron** | Ships Chromium, plus Node. Same engine, same order of magnitude, plus a second runtime. |
| **Tauri / WebView2** | Ships almost nothing — and renders in **Microsoft's copy of Chromium**, because WebView2 *is* Chromium. |

The second is the tempting one, and it is the worse fit here. The engine still
exists on the disk; it is simply not yours. You do not choose its version, you
cannot patch it, you cannot pin it, and its security posture is set on
Microsoft's schedule. For a product whose entire module argument is **isolating
content the user installed from somewhere else**, handing the isolation boundary
to a runtime you neither version nor patch is not a simplification.

### 9.3 Implementing the browser inside it

This has been tried by someone with far more resources than this project.
**Brave's first browser was built on Electron** — their fork was called Muon —
and they abandoned it to become a Chromium downstream, because keeping a
wrapper's security current with upstream is a race that the wrapper loses.
Sunshine would be starting that race in 2026 rather than finishing it.

Concretely, "implement the browser inside" means rebuilding, at application
privilege: per-site process isolation for the pages being rendered, the renderer
sandbox, the extension system, PDF, print, DevTools, profile management,
download protection. `scripts/verify_architecture.py` already refuses the
architecture that results — and its comment says why in one line worth keeping:
API names in prose are how a wrapper architecture survived in a spec.

### 9.4 Where the objection is right

**Chromium does carry things Sunshine may not need, and GN has flags for most
of them.** Print preview, reporting, and — the honest easy one — **the locale
paks**, of which a Chromium build ships roughly fifty when Sunshine's audience
needs two.

Two things bound how much that is worth:

- `docs/SIZE_BUDGET.md` already forecloses the largest tempting cut: *security
  features must never be traded for size.* Safe Browsing, the sandbox and site
  isolation are not on the table, and they should not be.
- Everything genuinely removable sits **outside** Blink, V8, Skia and net —
  which is where the bytes are. Trimming is a percentage, not an order of
  magnitude.

**And until build #34 nobody could say which percentage**, because the payload
had never been measured. That was the real defect behind this question, it is
now fixed, and the argument becomes arithmetic on the next build rather than
opinion.

### 9.5 The answer

**No — and this framing makes the case more strongly than the first one did.**

A web app would have paid the same bytes, given up the isolation model, handed
either the engine's version or its patching to someone else, and started a
security-currency race that the one prior attempt at this exact design lost.

What the objection correctly identifies is not the architecture. It is that this
project was carrying an unmeasured number with a threshold on it. That was true,
and it is fixed.

## 10. NOT VERIFIED

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
