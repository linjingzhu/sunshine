# Porting an existing project into a Sunshine module

## 0. What this is

Instructions for an agent — Claude Code or a person — converting a finished,
working application into a Sunshine module app. It is written to be handed to a
session working **inside the application's own repository**, not inside this
one.

`docs/MODULE_APP_GUIDE.md` says how to build a module app from nothing.
`docs/MODULE_SHELL_CONTRACT.md` says what the browser provides and what it
refuses to provide. This document is the third case and the hardest one: an app
that already works, already has opinions, and already has chrome of its own.

**It does not know your application.** Every instruction below is conditional
on facts about the app that only Phase 0 can establish. An agent that skips
Phase 0 and starts editing is guessing, and the guesses will be wrong in the
places that matter — the network, the storage and the chrome.

### The one thing to understand before starting

A finished app is a *whole product*: it has a shell, navigation, a title, a
place it stores things, a server it talks to. **Porting it is mostly deletion.**
The shell, the navigation and the title now belong to the browser; what is left
is the part that was always yours. An agent that tries to keep the app intact
and wrap Sunshine around it has misunderstood the task and will produce a
module that looks foreign, cannot be switched away from cleanly, and fails the
guards.

## 1. Phase 0 — Inventory, before touching anything

Produce a file, `PORTING_INVENTORY.md`, in the app's repository. Nothing else
happens until it exists, because every later phase reads it.

Answer with **measurements, not impressions**. Where the answer is "I could not
determine this", write that; a gap named is a decision the owner can make, a gap
guessed is a defect nobody will find until the build.

| # | Question | How to answer it |
| --- | --- | --- |
| 1 | What builds it, and into what? | The build tool, its config, and the exact output — files, sizes, whether it is a single bundle or many. |
| 2 | What does it load at runtime that it did not ship? | Every URL in the built output. Fonts, CDN scripts, analytics, images, API hosts, WebSockets. **List them all; this is the question most likely to end the port.** |
| 3 | Does anything construct code at runtime? | `eval`, `new Function`, runtime template compilation, dynamic `import()` of a computed path, a CSP the app already needs to relax. |
| 4 | What chrome does it draw? | Its own title bar, top nav, sidebar, tab strip, breadcrumb, window controls, settings drawer. Name each one and where it is drawn. |
| 5 | What does it store, and where? | localStorage, IndexedDB, cookies, files, a server. For each: what, how much, and whether losing it matters. |
| 6 | What does it talk to? | Every endpoint, what it sends, and whether it authenticates. |
| 7 | What are its routes? | The full list, and which ones are "a thing you look at" versus "a thing you do". |
| 8 | What is its dependency tree? | Direct dependencies with versions, and which ones reach the network or the DOM in ways 2 and 3 cover. |
| 9 | How is it styled? | Framework, palette, whether colours are literal or tokenised, whether font sizes are px or relative. |
| 10 | What tests exist and do they pass now? | Run them. Record the number. This is the baseline the port must not silently lose. |
| 11 | **Is there a backend, and what language is it?** | A local server, a packaged runtime, a database engine, a scheduler. Name the language and how it is shipped. |

## 2. Phase 1 — Five decisions, before any code moves

These change everything downstream, and three of them are the owner's, not the
agent's — the network, the secrets, and anything that would make the manifest
claim authority. Put them in `PORTING_DECISIONS.md` with the answer and who gave it.

### 1. Identity

Module id `sunshine.<name>`, repository and directory `sunshine-<name>`, WebUI
host `sunshine-<name>`, display name in title case. The four are derivable from
each other and `scripts/validate_first_party_modules.py` enforces the id shape.

### 2. Does it need the network?

**This is the decision that can end the port**, so make it before the work, not
after. `SEC-14` forbids a Sunshine-authored web asset from loading any remote
resource. A module that needs a server needs `network.access: allowlist` in its
manifest and an argument for every host on the list.

From inventory question 2, sort every URL into:

| | What to do |
| --- | --- |
| Fonts, icons, CSS, JS from a CDN | **Vendor them.** Ship the bytes. This is mechanical and always correct. |
| Images and media the app ships | Vendor them. |
| Analytics and telemetry | **Delete.** `docs/SECURITY_ARCHITECTURE_CONTRACT.md` is why; there is no version of this that survives review. |
| The app's own API | The owner's decision. Recorded, argued, and on the manifest — or the port stops here until there is an answer. |

### 3. Where does the backend go?

The first draft of this guide did not ask, because it assumed a web app that is
only a web app. **A packaged runtime does not survive the port**: a Sunshine
module is compiled into the browser (`docs/decisions/0006-module-execution-model.md`),
and a Chromium build contains no Python, no Node and no second executable.

If inventory question 11 found a backend, it has exactly three futures, and the
choice is architectural rather than a detail:

| | What it means | When it is right |
| --- | --- | --- |
| **Reimplement it** in `components/sunshine/<name>/`, behind a Mojo interface | C++ that depends on neither `//chrome` nor `//content`, per ADR 0013 §2.1. Chromium's own `//sql` is there for a database. | The default. It is the only future that is actually a module. |
| **Keep it as a companion process** the browser talks to | The module becomes a page pointed at `127.0.0.1`. | Almost never — §9 names this as the anti-pattern it is. Localhost is still network, it ships a second binary, and nothing about it is a module. |
| **Move it into the page** as TypeScript | Storage becomes browser storage; anything the backend did with credentials or cross-origin requests cannot follow. | Small backends that only shuffle local data. |

**Stage the work around what the backend does, not around its files.** A
backend that both stores data and calls an external service is two problems: the
storage half can usually be reimplemented immediately, and the external half is
blocked on decisions in §2.2 and §2.4 that are the owner's.

### 4. Whose data is it, and where does it live?

From inventory question 5. `browser`-scoped, `profile`-scoped and remote are
three different answers with three different manifests. **Sunshine holds no
filesystem path and remembers no location** — `DOC-3` and `DOC-8` in
`docs/DOCUMENT_SURFACE_CONTRACT.md` work the distinction through in full, and
the reasoning generalises to any module.

If the app currently writes files by path, that is not a detail to fix later:
it is a capability the module will not have, and the replacement has to be
designed before the code is moved.

### 5. Does anything it does need a secret?

If the app calls a service with an API key, a token or a password, **the module
will not hold it.** `docs/SECURITY_ARCHITECTURE_CONTRACT.md` SEC-7 is already
decided and already enforced by
`scripts/validate_first_party_modules.py`:

> A module never receives a credential. It requests an operation; the broker
> holds the secret.

`docs/decisions/0011-ai-credential-broker.md` shapes what such a broker would
be and is explicit that it is a proposal, not something that exists. So an app
whose function depends on a keyed external service is, today, **blocked on an
unbuilt subsystem** — and the honest plan is to stage that part out rather than
to smuggle a key into the module.

An app that already runs without its keys — in a stub, demo or offline mode —
has been handed the boundary for free. That mode is the first stage.

## 3. Phase 2 — Delete the chrome the shell now owns

This is the characteristic move of the port, and doing it early is what keeps
the rest honest: everything after this is written against the space that is
actually left.

From inventory question 4, remove from the app:

- its window title bar, its own title text, and any window controls;
- its top-level navigation between major areas — that is B, the dock;
- its own sidebar list of the current area's items — that is C, the tab list;
- its per-page header bar — that is D's header, and the shell draws it at a
  fixed 40px the module cannot change;
- its own inspector, console, preview or help drawer — that is E, one container
  with six roles the shell switches between.

**What remains is the module.** If very little remains, that is a finding worth
reporting rather than a reason to keep the chrome: it means the app was mostly
shell, and the port is mostly done.

Two traps:

**Do not reimplement the shell inside the body to "keep the look".** The point
of the shell is that every module is operated the same way. A module that draws
its own sidebar inside D has opted out of that, and `MS-1` and `MS-2` say it
may not.

**Do not delete the app's *state* along with its chrome.** Which item is
selected, which view is open, what is unsaved — the shell renders those and the
module owns them. They move to the host port; they do not disappear.

## 4. Phase 3 — The host port

The app must import nothing that only Sunshine provides (`MA-1`). Everything
crosses one interface the app declares itself, and Sunshine is one
implementation of it.

Concretely, replace direct calls with a port the app owns:

```text
app/host.ts          the interface, and the only file that differs per host
  ├── host.sunshine.ts   Sunshine's implementation
  ├── host.web.ts        a plain-browser implementation, for development
  └── host.stub.ts       an in-memory one, for tests
```

What crosses it, and nothing else: documents, records, identifiers, the tab
list, the title and path for D's header, at most three header actions, the
dirty flag, and which panel role is wanted. **No paths, no handles, no URLs to
navigate to, no callbacks into browser internals** (`MA-2`).

The shell half of that list is now written down and implemented:
`docs/MODULE_MOUNT_CONTRACT.md` names every message and
`chrome/browser/resources/sunshine/shell/mount_port.ts` is the file to copy
into the app. Copy it -- do not import it, which would be `MA-1` broken by the
very file that declares `MA-1`. §7 of that contract is the four things a module
app has to do.

Writing three implementations is not over-engineering here — it is the only way
to find out whether the boundary is real. `MA-3` asks for two hosts before the
port is considered done, and the reason is in `docs/decisions/0013-module-data-portability.md`:
the owner requires every app to run on iPad, and Chromium's WebUI machinery
does not go there. An app that reaches the port and nothing else does.

## 5. Phase 4 — Make it survive Sunshine's build

These are not style preferences. Each one has failed a real build in this
repository, and the build costs about twenty-five minutes of the owner's own
workstation.

| Rule | What it breaks |
| --- | --- |
| No remote resource, ever (`SEC-14`) | CDN links, Google Fonts, remote images, an API called at load. |
| No runtime code construction (`SEC-14`) | `eval`, `new Function`, runtime template compilers, computed dynamic import. |
| No `chrome.send`; Mojo for anything the browser must answer | Any bridge borrowed from a Chromium sample. |
| No import of `//resources/js/cr.js` | Upstream's eslint rejects it and says to use Mojo. Suppressing the rule is not the fix. |
| eslint runs *inside* the build | Interfaces use `;` between members, other type literals use `,`; no `public` modifier; `as` not `<T>`; `interface` not `type`; `T[]` not `Array<T>`; every import carries its extension. Property *names* are not checked, so `snake_case` manifest fields survive. |
| Colour comes from Chromium's tokens, no literal and no fallback | Any hardcoded palette. Map each colour to a token, or *derive* one: §2.2(3) permits `color-mix()` over a Chromium reference, so a hover wash, a dimmed rule or a tint of the accent ports without an exception. Only a literal hue needs a decision — `docs/MODULE_SHELL_CONTRACT.md` §7 is the worked example. |
| Type scale in rem: 0.6875, 0.75, 0.875, 1, 1.25, 1.5, 2 | Every px font size. `scripts/verify_design_tokens.py` fails them outright. 0.6875rem is `label-xs`, the smallest step, and is for identifiers rather than prose. |
| Motion needs a `prefers-reduced-motion` escape | Any transition or animation. |
| Files are read as UTF-8 explicitly | Tooling that reads in the locale encoding. The only CI is a Korean Windows machine. |

Do this phase **before** the first Sunshine build, not after it. A build that
fails on eslint has told you nothing you could not have learned in a minute.

## 6. Phase 5 — Manifest, registry, mount

1. Write `module.json` — schema version 2, validated by
   `scripts/validate_first_party_modules.py`. **Declare exactly the authority
   the module holds.** It is rendered to the user at
   `chrome://sunshine-modules`, so `network: deny` and `filesystem: none`
   unless Phase 1 decided otherwise, and `verification` stays `pending` until a
   gate has actually been run.
2. Add it to `first_party/registry.json`.
3. The baked copy the browser is served is compared byte for byte by
   `scripts/verify_module_registry_sync.py`, so a manifest edit that does not
   reach the surface patch fails the guard rather than the user.
4. Lay the files out so mounting is a copy, not an edit —
   `docs/MODULE_APP_GUIDE.md` §2 gives the mapping, and the entry document must
   be `app.html` because `build_webui()` derives the resource id from its path.

## 7. Definition of done

1. `PORTING_INVENTORY.md` and `PORTING_DECISIONS.md` exist and are current.
2. The app builds with no remote resource and no runtime code construction.
3. The app draws none of A, B, C's frame, D's header, or E's container.
4. Every capability crosses the host port, and a second host implementation
   exists or the reason it cannot is written down.
5. The manifest validates, is registered, and claims no authority the module
   does not hold.
6. The test count from inventory question 10 is met or beaten, and any test
   deleted is named with a reason.
7. Sunshine's own guard suite passes: `python3 scripts/compile_check.py` and
   the rest, plus `python3 -m unittest discover -s tests`.
8. Gates for the module exist in `docs/RUNTIME_VERIFICATION.md`, honestly
   marked `NOT RUN`.

## 8. How to run the work

- **Push early and often.** A branch that exists is a branch someone can look
  at; work that lives only in a session is work that can be lost.
- **Do not ask the owner what you can measure.** Phase 0 exists so that
  questions to the owner are decisions, not lookups.
- **Do ask about the three in Phase 1 that are the owner's** — the API, the
  data, and anything that would make the manifest claim authority.
- **Report what failed, with the output.** A port that says "done" and means
  "compiles" is worse than one that says which four things do not work yet.
- **Never weaken a guard to pass it.** If a guard is wrong, say why it is wrong
  and fix the guard on its own terms, with a test that proves the new rule
  still rejects what the old one rejected. This repository has done that twice
  and both times the guard was broader than the invariant it enforced; neither
  time was the fix to delete the check.
- **Do not add upstream files.** A surface costs zero of them
  (`docs/decisions/0007-module-contribution-seam.md`), and a port that starts
  editing Chromium has taken a wrong turn several steps earlier.

## 9. Anti-patterns

| Pattern | Why it fails |
| --- | --- |
| Wrapping the whole app in an iframe and calling it a module | The shell regions stay the app's, so nothing is consistent and nothing is switchable. Also hides the remote resources rather than removing them. |
| Keeping the app's chrome "for now" | There is no later. The layout is written against the space that is left, so leaving the chrome means writing the layout twice. |
| Porting the network calls last | It is the decision most likely to stop the port. Making it last means finding out after the work. |
| Relaxing the CSP to make the build pass | The CSP is the reason a module is safe to mount. A module that needs it relaxed is a module that has not been ported. |
| Copying a Chromium sample's `chrome.send` bridge | Denied by `ui::MojoWebUIController` and by review. |
| Declaring `filesystem: user_selected` because a picker is convenient | Declaring authority you do not have is as much a defect as exercising authority you were not given. |

## 10. NOT VERIFIED

- **No project has been ported with this guide.** It is derived from building
  the shell and the surfaces in this repository, not from a completed port, so
  the phase order is reasoned rather than measured.
- **The host port exists and has never carried a message.**
  `docs/MODULE_MOUNT_CONTRACT.md` defines it and
  `downstream/patches/0012-sunshine-module-mount.patch` implements the shell's
  half, so Phase 3 now has a shape to target rather than one to invent. But no
  module declares a mount, nothing has been built, and the first port to arrive
  is still the port that finds out what is wrong with it.
- The eslint rules in §5 were read from the configuration at the pinned
  revision and confirmed against patches that have built. They are not a
  substitute for running the build.
- Nothing here is specific to any particular application. Where an instruction
  seems not to fit, the inventory is the thing to trust.
