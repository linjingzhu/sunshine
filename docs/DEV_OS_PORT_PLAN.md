# Dev OS → Sunshine module: the plan

## 0. Status

**Plan, and now a module slot.** Dev OS is registered:
`first_party/modules/sunshine-dev-os/module.json`, `status: planned` — an
architecture slot, not something shipped. It is the **first module in this
repository to declare a `mount`**, so `scripts/verify_module_mount.py` reports
`1 module(s) declare a mount` rather than zero for the first time.

Nothing Chromium-side is built: no `chrome://sunshine-dev-os` and no
`chrome-untrusted://sunshine-dev-os-app/` host exists. §6 Stage 1 is still
ahead, and §8 records what is now measured against what is still not.

Dev OS's own half — the port copy, the adapter, the mounted shell and region E —
is built and was verified against a host that is not this one. That work and its
measurements live in `linjingzhu/dev-os@docs/SUNSHINE_MODULE.md`; §7 below now
carries the answers rather than the questions.

`docs/MODULE_PORTING_GUIDE.md` is the general method.
`docs/MARKETPICK_PORT_PLAN.md` is the same method applied to a different app,
and the two are worth reading together — they fail in opposite places, which is
the most useful thing either of them shows.

## 1. What Dev OS is

As described by the owner, and since **read**: every row below was checked
against the repository at `linjingzhu/dev-os@522fcd5`, and the three corrections
are noted where they belong rather than silently applied.

| | |
| --- | --- |
| Dependencies | **Zero.** `dependencies` and `devDependencies` are both empty. No Vite, no webpack, no TypeScript, no Babel. Vanilla JS with ESM, `type: module`, read by the browser as `<script type="module">`. No transpile step. |
| "Build" | Not bundling. Its build script copies `index.html`, `server.js`, the source tree and `package.json` into a distribution directory, computes SHA-256 per file into a manifest, and a verify step checks the output against it. 52 assets today. |
| Tests | `node --test`. No external runner. |
| Server | A dependency-free `node:http` server doing two things: serving static assets, and an API — GitHub integration (settings, workspace, credentials, document editing), local draft and session storage, and session discovery and execution. |
| Rendering | **All in the browser.** No SSR; the server returns JSON and files. |
| Why the server exists | Secrets and local resources. A GitHub token must not reach the browser, and reading `~/.claude/projects/` or opening a terminal is not something a browser can do. |
| Chrome | Drawn entirely by a `shell(ctx, content)` function in its views, wrapping every page: a sidebar (brand mark, six nav items — Command Center, Projects, Decision Inbox, AI Sessions, Activity, Settings — a pending-decision badge, a sync chip, a profile button), a top bar (search with `⌘K`, sync status), and on project screens a **second sidebar** (project switcher and draft list). |
| How it renders | Template literals building HTML strings, assigned to the app node's `innerHTML`. No React, no Web Components, no shadow DOM. |
| Routing | `[data-route]` clicks set `state.route` and redraw. No History API, no hash. |

The zero-dependency count is enforced by a test, not a habit — the owner's
harness installs Chromium and Playwright *outside* the repository to keep it at
zero.

## 2. The two findings that shape everything

### Dev OS already is the shell

The layout rules Sunshine's module shell was built from are titled
`DEV OS · LAYOUT PRIMITIVE v1`. **The shell in `docs/MODULE_SHELL_CONTRACT.md`
is Dev OS's own design, generalised so every module gets it.**

So the largest deletion in this port is not a loss. Dev OS stops *drawing* the
layout it invented and starts *receiving* it — from the browser, identically,
for every module beside it. Its `shell()` function, its sidebar, its top bar and
its second sidebar are regions A, B, C and D's header, and the shell draws all
of them.

That is worth saying plainly because the instinct will be to keep them. Keeping
them is the anti-pattern in `docs/MODULE_PORTING_GUIDE.md` §9, and here it would
also mean two implementations of the same design in one window.

### Dev OS's server is not logic. It is capability.

This is where Dev OS and Marketpick diverge completely, and it is the finding
that decides whether this port is possible at all.

Marketpick's Flask layer was business logic over SQLite — rewritable in C++,
tedious but bounded. Dev OS's server is deliberately thin and exists **only
because a browser is not allowed to do three things.** You cannot rewrite a
capability; you can only be granted it.

| What the server does | Sunshine's position | Status |
| --- | --- | --- |
| Holds a GitHub token | `SEC-7`: *a module never receives a credential; it requests an operation and the broker holds the secret.* Enforced by `scripts/validate_first_party_modules.py`. | **Blocked on an unbuilt broker.** `docs/decisions/0011-ai-credential-broker.md` shapes one and states it is a proposal. |
| Reads `~/.claude/projects/` | `SEC-8`: filesystem access is `none` unless a user selection grants a scoped, expiring permission — and the validator **refuses `user_selected` today**, pending a file-broker contract. | **Blocked on a contract that does not exist.** |
| Discovers and executes sessions — opens a terminal | Nothing. No contract in this repository contemplates a module executing a process. | **Not blocked. Unspecified — which is worse.** |

The third row is the important one. A blocked capability has a known price and
a known owner. An unspecified one has neither: **letting a module start
processes is the largest capability anything in this design has ever been
offered**, and there is no ADR that says yes, no, or under what conditions.
It cannot be settled inside a port; it needs its own decision, argued on its own
terms, before any code assumes an answer.

## 3. Where each piece lands

| Dev OS today | In Sunshine | Notes |
| --- | --- | --- |
| `shell(ctx, content)` — sidebar, top bar, second sidebar | **Deleted.** A, B, C and D's header, drawn by the browser. | Its design survives; its code does not. §2. |
| Six nav items | The module's tab list — **content for C**, supplied once through the host port. | See §4 for the region question this raises. |
| Second sidebar (project switcher, draft list) | Open. See §4. | |
| Search with `⌘K`, sync chip, profile button | Open. Some of it is shell-global, some is the module's. See §4. | |
| Router — `state.route` plus redraw | **Deleted.** The shell owns navigation and tells the module which tab is active. | No History API to port, which makes this the easiest router removal possible. |
| Views built with template literals into `innerHTML` | **Rewritten** to build nodes. | The largest mechanical change in the port. §5. |
| Vanilla ESM source, no transpile | `.ts` files in the surface's directory, compiled by `build_webui()`. | Zero dependencies means nothing to vendor and no framework runtime to remove. This is the best possible starting point. |
| SHA-256 integrity manifest over 52 assets | **Deleted**, and satisfied differently. | The instinct is exactly Sunshine's — verify what shipped. Sunshine answers it with the resource bundle compiled into the binary and the patch-stack guards, so a separate manifest would be checking a copy nobody serves. |
| `node --test` suites | Open, and a real risk. §7. | |
| GitHub integration, `~/.claude/projects/`, session execution | **Staged out.** §2, §6. | |
| `server.js`, the static serving half | **Deleted.** | The resource bundle serves the surface. |

## 4. The region question this port raises first

Sunshine's B is the **module dock** — it lists modules, not one module's
sections. Dev OS's sidebar lists *its own* six areas. So the six nav items are
C, the tab list, not B.

That is straightforward. What is not:

- **The second sidebar.** Dev OS shows project switcher *and* draft list on
  project screens — two levels of navigation inside one module. The shell
  contract describes C as *"좌측 패널의 2단계"*, the left panel's second stage,
  which suggests C can carry it; whether C carries two levels or the switcher
  belongs in D's header is undecided and should be decided by looking at the
  screens, not by reading either document.
- **Search (`⌘K`).** A search across everything Dev OS knows is the module's. A
  search across the browser is the shell's. Which one this is has not been
  established.
- **Sync chip and profile button.** These look shell-global — they are about
  the browser's relationship with a remote, not about one module's content —
  but Sunshine has no such global today, and inventing one to hold Dev OS's
  chip would be letting one module shape the shell.

**Do not resolve these by making the shell more configurable.** The shell is
identical across modules by construction, which is the whole argument in
`docs/MODULE_SHELL_CONTRACT.md` §1. If Dev OS genuinely needs something the
shell does not have, that is a change to the shell contract, argued once, for
every module — not a hook.

## 5. `innerHTML` is the largest mechanical change

Every view builds an HTML string from template literals and assigns it. In
Sunshine that collides with the rule directly: `MS-3` says no module content
reaches the shell's document as markup, and the surfaces already built construct
nodes with `createElement` and `textContent` for exactly this reason.

Two things follow.

**It is not made safe by the frame.** Module content renders in an unprivileged
frame, so an assignment there is not the catastrophe it would be in the shell.
But Dev OS's strings interpolate GitHub data, file contents and session output —
values it does not author. That is an injection in the frame, which is a smaller
blast radius and still a defect.

**The rewrite is mechanical but not small.** Every view is affected. It should
be done view by view, each one landing complete, rather than as one pass —
partly to keep the diff reviewable, and partly because the first two or three
will teach the shape the rest should follow.

## 6. Staging

| Stage | Contents | Blocked on |
| --- | --- | --- |
| **1** | The surface, the six tabs, the views rewritten to build nodes, everything that reads data already local and non-secret. Manifest declares `network: deny`, `filesystem: none`, `credentials.direct_access: false`. | Nothing. |
| **2** | GitHub integration. | The credential broker — unbuilt, and whose existence is itself an open decision. |
| **3** | Reading `~/.claude/projects/`. | A file-broker contract, which does not exist; `user_selected` is refused today. |
| **4** | Session discovery and execution. | **A decision nobody has framed yet.** §2. |

Unlike Marketpick, Dev OS **does not already have a mode that fits Stage 1**.
Marketpick falls back to stubs without keys; Dev OS's value is substantially the
integrations. So Stage 1 here is a real question rather than a free starting
point: *what is Dev OS with no GitHub, no session directory and no terminal?*

If the answer is "not much", that is a finding, and it should be reported rather
than worked around. It would mean Dev OS is not a module yet — it is an
application waiting on three capabilities Sunshine has not decided to grant, and
the honest next step is to decide those, in that order, rather than to port a
shell around an empty middle.

## 7. What had to be established, answered

Every question below was open when this plan was written. Each is now answered
from Dev OS's code rather than from its description; the measurements are in
`linjingzhu/dev-os@docs/SUNSHINE_MODULE.md`.

### "What is Dev OS without its three capabilities?"

The plan called this the first question, said it governs whether the port
starts, and guessed the answer might be *"not much"*.

**Measured with no GitHub token, no transcript directory and no terminal: all
six screens render, every empty state is a sentence rather than a blank, and
every asserted value is masked** — digits to `n`, letters to `x`, shape kept.
That is not a degraded mode built for this question; it is what Dev OS's
`src/mask.js` and its "degradation is a value" rule already do.

So the answer is neither "not much" nor "everything". It is **a working shell
that asserts no facts**, which makes Stage 1 a real starting point and still
worth less to a user than Stage 2.

### "What the six screens do, individually"

The staging in §6 assumed a split it had not verified. This is the split:

| Screen | GitHub | `~/.claude/projects/` | Terminal | Local only |
| --- | --- | --- | --- | --- |
| Command Center | workspace sync | — | — | decisions, deferrals |
| Projects | workspace sync | — | — | drafts |
| Project | workspace sync, idea history, **Projects boards**, policy-doc read/propose | discovered sessions | — | drafts, deferrals |
| Decision Inbox | labelled issues | — | — | resolutions, deferrals |
| AI Sessions | — | discovery | **launch** | stored sessions |
| Activity | — | — | — | **entirely** |
| Settings | credential state | — | — | — |

**This is worse for Stage 1 than the plan assumed, and in a direction that
matters.** When §6 was written, two screens needed nothing at all. Both have
since gained a GitHub source: the Decision Inbox reads `needs-decision` issues,
and the Project screen reads Projects (v2) boards over GraphQL. The staging is
unchanged — those reads degrade like every other one — but "Dev OS without
GitHub" is now a smaller product than it was, not a larger one.

### "Where do the `node --test` suites go?"

**1,449 tests across 43 files**, zero dependencies, plain ESM under
`node --test`. They do not depend on Dev OS's server or on a DOM: pure modules
with injected clocks, injected `fetch` and injected readers.

The plan is right that they are at real risk — this repository's suite is Python
and runs no JavaScript. But **they need a JavaScript runner, not a port**, and
deciding their home before moving code remains the right order. This is the one
question that is still open.

### "How large is the view layer actually?"

52 assets was a count of files. Measured: `src/views/*.js` is **2,746 lines**
across 11 files, `src/*.js` is 5,258, `server.js` is 1,485.

`innerHTML` is assigned in exactly **two** places — the render entry point, and
region E's own panel element. The views build strings and return them; they
touch no document, which is why the tests can run them without one. So the
`MS-3` rewrite is 2,746 lines of string building to convert, behind a call site
that does not change.

### "Whether session execution is even on the table"

Still unasked. It has no contract, no ADR and no precedent here, and §6 Stage 4
still says so.

## 8. NOT VERIFIED

The three items this section carried first — that Dev OS had not been seen, that
the shell-is-Dev-OS claim rested on a title, and that the region mapping was
reasoned from descriptions — are settled. What replaces them is narrower and
all of it is Chromium-side.

- **No Chromium host exists.** `chrome://sunshine-dev-os` and
  `chrome-untrusted://sunshine-dev-os-app/` are declared in the manifest and
  registered nowhere. The comparable work is
  `downstream/patches/0006-sunshine-document-webui.patch`.
- **The port copy is a translation, not the file.** Dev OS carries
  `src/host/mount-port.js` — this repository's `mount_port.ts` rewritten as
  dependency-free ESM, with every constant pinned by test to the value
  `docs/MODULE_MOUNT_CONTRACT.md` states in prose. `docs/FIRST_MODULE_GUIDE.md`
  §10 asks for a byte-identical `mount_port.ts`. Which of the two rules governs
  a module that ships no TypeScript is undecided.
- **Dev OS breaks three of `docs/FIRST_MODULE_GUIDE.md` §7's rules today.**
  Measured, and the counts matter less than their shape:

  **Markup** (`MS-3`, `MA-6`, `MM-7`) — `innerHTML` in two places, `srcdoc` in
  three files. The second is the hard one: the idea-history reader's isolation
  *is* a sandboxed `srcdoc` (`sandbox=""` plus `default-src 'none'`), so this is
  a replacement of the isolation mechanism rather than a conversion of it.

  **Type** (`docs/DESIGN_SYSTEM_CONTRACT.md` §6.2) — **241** `px` font sizes
  counting the `font:` shorthands, of which **184 (76%) are below `label-xs`**,
  the 0.6875rem floor: fifty at 8px, eighty-one at 9px, fifty-two at 10px.
  Three quarters of Dev OS's type is under the smallest step the scale has, and
  §6.2 says "No computed size below `label-xs`" while ADR 0016 closed the unit
  question — "permitting `px` would keep none of [the scale's properties]". So
  this is a visual redesign and not a token swap: raising 8px and 9px to 11px
  moves every card height, column width and line break, including the layout
  measured against `docs/MODULE_SHELL_CONTRACT.md` §2's widths. `label-xs` is
  also "never for prose, never for a control's only label", which is exactly
  what Dev OS's 8-9px is for.

  **Colour** (§3) — 204 literals over 109 distinct values, and a fact that
  comes before the count: §3 says the New Tab "is the only surface with
  bindings", and binding a role means locating the identifier in
  `ui/color/color_id.h` in the pinned tree, with "Roles are not bound by
  guessing at a name that follows the pattern". Dev OS is a new surface, so it
  has **no bindings at all**, and accent/on-accent and focus are unbound even
  for the New Tab.

  **So the colour work cannot finish before the Chromium host above exists.**
  Of the three, markup is the only large one that is not blocked on this side.
- **The manifest is a second copy.** `first_party/modules/sunshine-dev-os/module.json`
  is what this repository's validators read; `linjingzhu/dev-os@sunshine/module.json`
  is the module author's. Nothing compares them, which is the same shape of
  liability the mount port has and without the test that answers it there.
- **`status` is `planned` and every `verification` field is `pending`**, which
  is accurate: nothing has been built, run or looked at in Chromium.
