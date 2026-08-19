# Dev OS → Sunshine module: the plan

## 0. Status

**Plan, not work.** Nothing is built. It is written from the owner's own
description of Dev OS; every claim about that application is theirs rather than
measured by me, and §8 says so again where it matters.

`docs/MODULE_PORTING_GUIDE.md` is the general method.
`docs/MARKETPICK_PORT_PLAN.md` is the same method applied to a different app,
and the two are worth reading together — they fail in opposite places, which is
the most useful thing either of them shows.

## 1. What Dev OS is

As described by the owner:

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

## 7. What has to be established before any of this

- **What Dev OS is without its three capabilities.** §6. This is the first
  question and it governs whether the port starts.
- **Whether session execution is even on the table.** It has no contract, no
  ADR and no precedent here. Ask before designing.
- **What the six screens do**, individually — which read local state, which
  call GitHub, which touch the session directory. The staging in §6 assumes a
  split it has not verified.
- **Where the `node --test` suites go.** This repository's suite is Python and
  runs no JavaScript; Chromium has WebUI browser tests that this project does
  not use. Dev OS's tests are therefore at real risk of being lost in the port,
  and losing them silently would be the worst outcome available. Decide their
  home before moving code, not after.
- **How large the view layer actually is** — 52 assets is a count of files, not
  of work.

## 8. NOT VERIFIED

- **I have not seen Dev OS.** Every fact in §1 is the owner's description,
  relayed. No file, route, view or test has been read.
- The claim in §2 that Sunshine's shell is Dev OS's design rests on the title of
  the layout rules the owner supplied, and on the regions matching. It has not
  been checked against Dev OS's code.
- The region mapping in §3 and the questions in §4 are reasoned from
  descriptions of screens, not from the screens.
- The host port that Stage 1 depends on has no implementation —
  `docs/MODULE_APP_GUIDE.md` §8 records it as an argument rather than a
  measurement.
