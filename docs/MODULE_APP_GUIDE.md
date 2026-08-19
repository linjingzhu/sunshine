# Module App — Development Guide

## 0. What it is called, and why not something new

A **module app** (모듈 앱) is a project built to mount into Sunshine OS as a
module. It is the thing a person or an agent actually develops: a repository, a
UI, a data model, a manifest.

Three words in this project already carry weight, and a module app is none of
them:

| Word | What it names | Where it is defined |
| --- | --- | --- |
| **module** | the declared unit — an id, a manifest, an entry in the registry | `first_party/modules/*/module.json`, `docs/decisions/0006-module-execution-model.md` |
| **surface** | how a module appears inside Sunshine — one privileged WebUI page | `docs/decisions/0007-module-contribution-seam.md` |
| **seam** | the contribution point a surface attaches to without touching upstream | ADR 0007 |
| **module app** | the project that becomes a module | this document |

A fourth invented word — *plugin*, *cell*, *capsule* — would have to be defined
in each of the documents above and would mean explaining, forever, how it
differs from "module". "Module app" is a compound of a word that already exists,
and the directory layout already reads that way:
`first_party/modules/sunshine-document/` is the manifest of the module that the
`sunshine-document` app becomes.

**Naming convention.** Module id `sunshine.<name>`; repository and directory
`sunshine-<name>`; WebUI host `sunshine-<name>`; display name in ordinary title
case ("Sunshine Documents"). The four are derivable from each other, and
`scripts/validate_first_party_modules.py` already enforces the id shape.

## 1. The one structural rule

**A module app never imports Sunshine.**

Everything below follows from that sentence. The app talks to a *host* through
an interface it declares itself, and Sunshine is one implementation of that
interface — not the only one, and not one the app knows the name of.

```text
        module app  (UI, data model, host interface)
             │
             │  the host port — declared by the app
             ▼
   ┌─────────┴──────────┬──────────────────┐
Sunshine WebUI      iPad shell         dev server
(Mojo + WebUI       (WKWebView +       (a stub, in the
 data source)        native bridge)     app's own repo)
```

Two reasons, and the second is the one that has already cost this project a
decision:

**It is what makes integration cheap.** ADR 0007's seam gives a surface a
directory, a resource bundle entry, and a registry line. It gives it no way to
reach into the browser. An app that assumed browser globals would have to be
rewritten at the seam; an app that goes through a port is wired at the seam.

**It is what makes the app portable, and portability is a requirement.**
`docs/decisions/0013-module-data-portability.md` records the owner's position:
every app developed here has to run on iPad. Chromium's WebUI machinery does not
go to iPad. The app's HTML, CSS, TypeScript and data model do — if, and only if,
the only thing they touch is a port the iPad shell can also implement.

### MA invariants

| ID | Invariant |
| --- | --- |
| MA-1 | The app imports nothing that only Sunshine provides. Every capability arrives through the host port the app declares. |
| MA-2 | The port is data in, data out. It carries documents, records and identifiers; never a path, a handle, a URL to navigate to, or a callback into browser internals. |
| MA-3 | The app runs against at least two hosts before it is considered done — Sunshine and one other. One host is an assumption; two is a boundary. |
| MA-4 | The manifest describes exactly the authority the app holds. Declaring authority it does not have is a defect of the same kind as exercising authority it was not given. |
| MA-5 | The app's UI resolves every colour through the host's token layer and hardcodes none. |
| MA-6 | No Sunshine-authored file in the app inserts user or project content into a privileged document as markup. |
| MA-7 | The app stores nothing outside what the host hands it, and remembers no location the host does not give it back. |
| MA-8 | The app's file layout maps one-to-one onto the seam's directories, so mounting is a copy and not a port. |

None of these is enforced by a check today. MA-4, MA-6 and MA-8 are the three a
guard could decide from source as soon as an app exists to read.

## 2. Shape on disk

The seam serves a surface **the files under its own directory prefix**, with
that prefix removed. So the app's layout is not a matter of taste: it is the
thing that decides whether mounting is a copy or a rewrite.

```text
sunshine-<name>/                 the app's own repository
  app/
    app.html                     the entry document, one per surface
    app.css
    app.ts
    host.ts                      the port: the ONLY file that differs per host
  host/
    <name>.mojom                 the Sunshine host interface, if the app needs one
    *.cc / *.h                   the browser-side implementation
  model/                         data model, no browser dependency at all
  module.json                    the manifest
```

Mounted, those become:

```text
chrome/browser/resources/sunshine/<name>/     ← app/
chrome/browser/ui/webui/sunshine/<name>/      ← host/
components/sunshine/<name>/                   ← model/
first_party/modules/sunshine-<name>/          ← module.json
```

**Why the file names are fixed.** `build_webui()` derives each resource's name
from the bundle prefix and the file's path, so `<name>/app.html` becomes
`IDR_SUNSHINE_<NAME>_APP_HTML` — which is the identifier the surface's C++ names
when it sets up its data source. Calling the entry document anything else means
editing the mount rather than performing it.

**The model has no browser dependency.** `components/sunshine/<name>/` may not
depend on `//chrome` or `//content`. ADR 0013 §2.1 requires the dependency to
run one way, and that one-way arrow is also what lets the model be compiled for
a different host — or reimplemented in another language — without dragging a
browser behind it.

## 3. The manifest is the app's public face

`module.json` is schema version 2, validated by
`scripts/validate_first_party_modules.py`, and listed in
`first_party/registry.json`.

It is not paperwork. **It is rendered**, to the person using the browser, at
`chrome://sunshine-modules` — the module home, contracted in
`docs/MODULE_HOME_CONTRACT.md`. The permissions column on that page is the
manifest's own words. So:

- Declare `network.access: deny` and `filesystem.access: none` unless the app
  genuinely holds more. `user_selected` means the module holds a scoped,
  expiring grant to a path a user picked; if the app only hands bytes to a
  Chromium flow and learns nothing, that is not a grant and must not be
  declared as one. `docs/DOCUMENT_SURFACE_CONTRACT.md` DOC-3 and DOC-8 work
  through this distinction in full, and the reasoning generalises.
- Leave `verification` at `pending` until a gate has actually been run.
  `pending` is not a soft failure and must never be shown or written as one.
- The registry is copied into the browser at build time and
  `scripts/verify_module_registry_sync.py` compares the two byte for byte, so a
  manifest edit that is not carried into the surface patch fails the guard
  rather than reaching a user.

## 4. What a module app may not do

These are not new rules. They are the existing contracts, collected so that an
app author does not have to discover them one build at a time.

| | Rule | Source |
| --- | --- | --- |
| 1 | No `eval`, no dynamically constructed code, no remote resource — in any web asset, ever | SEC-14 |
| 2 | No `chrome.send`. A surface that needs the browser declares a Mojo interface; `ui::MojoWebUIController` grants Mojo and denies `chrome.send` by default | ADR 0013 §2.5 |
| 3 | No import of `//resources/js/cr.js`. Chromium's own eslint rejects it and says to use Mojo instead — and suppressing that rule is not the fix | build #24 |
| 4 | No URL scheme of the app's own. Sunshine registers none | `docs/decisions/0003-internal-scheme.md`, SEC-13 |
| 5 | No navigation to a string the app accepted. A `GURL` built in place from a compile-time host constant is fine; anything assembled from input is not | OS-9 |
| 6 | No user-authored markup in the privileged document. Content that a person wrote renders in an unprivileged `chrome-untrusted://` frame that receives content and never capability | DOC-1, DOC-2 |
| 7 | No retained filesystem location. Handing bytes to a user-driven flow is not filesystem access; remembering where they went is | DOC-3, DOC-8, SEC-8 |
| 8 | No second implementation of something Chromium owns — no URL parser, no scheme table, no per-tab lifecycle store | `scripts/verify_no_interposition.py` |

Rule 6 is the one that shapes an app's architecture rather than merely
constraining it. If the app displays content a person authored, it is **two**
surfaces from the start: a privileged shell and an untrusted frame. Retrofitting
that split is a rewrite; starting with it is a directory.

## 5. UX — how it reads as part of Sunshine

Consistency here is not a style preference. A module app that looks like a
website that wandered into the browser teaches the user that Sunshine's chrome
and its content are the same kind of thing, which is exactly the confusion the
shell/frame split exists to prevent.

**Colour.** Every colour comes from the host's token layer. Inside Sunshine that
is Chromium's own pipeline through `chrome://theme/colors.css`, and
`docs/DESIGN_SYSTEM_CONTRACT.md` §2.1 and §2.3 forbid both a hardcoded value and
a fallback — a token that stops existing must fail visibly rather than silently
escape the theme. Five roles are proven in the stack today:
`--color-dialog-background`, `--color-primary-foreground`,
`--color-secondary-foreground`, `--color-midground`,
`--color-alert-high-severity`. Prefer them; a sixth is a decision, not a
convenience.

**Type.** Six steps, in rem: 0.75, 0.875, 1, 1.25, 1.5, 2.
`scripts/verify_design_tokens.py` fails anything else, in px, or with
`!important`. This is checked on the patch, so an off-scale size is a build
failure and not a review note.

**Layout.** Two columns, full height. The left column is **the list of the
things this app owns** — not a menu of settings, and not a category tree
invented to fill it. The right column is the thing itself, edge to edge. Where
the right column shows an artifact the user brought in, the pane *is* that
artifact rather than a rendering of parts of it.

**Controls over content.** Actions that operate on what is displayed float at
the top-right of the content, translucent, rather than occupying a toolbar that
pushes the content down.

**Honesty in state.** Show the state the data actually holds. `pending` reads as
unrun, never as passed and never as failed. A page that reports must not offer
a control that implies it can administer.

**Keyboard.** Focus order follows draw order. In a views hierarchy that means
child order matches visual order; in a document it means the DOM order is the
reading order. A control drawn first and added last is reached last, and that is
a defect for exactly the people most likely to notice it.

**Pointer.** Gesture activation distance is `gestures.activation_distance`,
default **200 px**, range 20–600, clamped rather than refused. An app does not
implement its own gesture threshold.

## 6. Facts about the build, so the first one is not a surprise

Every item here cost this project a build.

- **eslint runs as part of the build**, not only in presubmit —
  `build_webui()` enables type-aware checks by default. What actually bites:
  interfaces use `;` between members (there is an override; other type literals
  use `,`); no `public` modifier; `as` for assertions, never `<T>`; `interface`
  over `type`; `T[]` over `Array<T>` for simple types; every import carries its
  file extension. Property *names* are not subject to the naming rule, so a
  manifest's `snake_case` fields survive as declared.
- **`-Wunsafe-buffer-usage` is an error** under `/WX`. Pointer arithmetic on a
  `const char*` will not compile; use `substr` and friends.
- **Patches are generated, never hand-edited.** A hunk header states how many
  lines its body holds, and `scripts/verify_patch_integrity.py` checks all four
  numbers. Produce the patch with `git diff` from a real tree.
- **Non-ASCII in a patch is fine; reading it in the locale encoding is not.**
  The only CI is a Korean Windows machine, so every file read passes
  `encoding="utf-8"` explicitly, and a test refuses new ones that do not.
- **A resource name in a `.rc` file may be a string.** An identifier that no
  included header defines is a string name, not an integer id — which is why
  every icon in `chrome/app/chrome_exe.rc` is named rather than numbered.

## 7. Definition of done

1. The manifest validates, is listed in `first_party/registry.json`, and the
   baked copy matches it byte for byte.
2. The app compiles into Sunshine, and the surface loads.
3. The app runs against a second host, or the reason it cannot yet is written
   down. (MA-3)
4. Runtime gates exist for it in `docs/RUNTIME_VERIFICATION.md`, and their state
   is recorded honestly — `NOT RUN` until someone runs them.
5. Nothing in §4 is violated, and where the app comes close to one of those
   lines, the document says where the line is rather than leaving it to be
   rediscovered.

## 8. NOT VERIFIED

- **No module app has been built to this guide.** `sunshine-document` and
  `sunshine-modules` were built inside this repository and then described here;
  the layout in §2 is derived from where their files ended up, not from a
  project that started outside and mounted successfully.
- **The second host does not exist.** MA-3 asks for one and none is available:
  ADR 0013 records the iPad position, and no shell implements it. Until one
  does, the port boundary is an argument rather than a measurement.
- No check enforces any MA invariant. §1 says which three could be decided from
  source once there is an app to read.
- The eslint rules in §6 were read from the configuration at the pinned revision
  and confirmed against patches that have built. They are not a substitute for
  running the build.
