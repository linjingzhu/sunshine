# Building the first Sunshine module program

## 0. What this is, and who it is for

Instructions for a session — Claude Code or a person — building a **new**
application that is meant to be a Sunshine module from its first commit. It is
written to be handed to a session working **inside that application's own
repository**, not inside this one.

It is not the porting guide. `docs/MODULE_PORTING_GUIDE.md` converts a finished
application and spends most of its length on deletion. This one has nothing to
delete, which changes the advice completely: everything below is about not
building the things that would have to be deleted.

**The worked case is an HTML collection** — a program that holds a set of HTML
documents and lets a person browse, read and organise them. That application is
used throughout because it is the best possible first module, and §1 says why.
Everything outside §2 applies to any first module.

Read alongside, and in this order:

| | |
| --- | --- |
| `docs/MODULE_MOUNT_CONTRACT.md` | The port. This is the one document you cannot skip. |
| `docs/MODULE_SHELL_CONTRACT.md` §1 | Which regions the browser draws. Read it before designing any navigation. |
| `docs/MODULE_APP_GUIDE.md` | The MA invariants and the directory layout. |
| `docs/SECURITY_ARCHITECTURE_CONTRACT.md` | SEC-5 to SEC-14. §7 below is the short form. |
| `docs/DESIGN_SYSTEM_CONTRACT.md` | Colour and type. §8 below is the short form. |

## 1. Why an HTML collection is the right first module

Not because it is easy. Because it exercises the whole seam and needs nothing
that does not exist yet.

**It is Stage 1 complete on day one.** Both existing port plans stall at a
capability Sunshine has not built — `docs/MARKETPICK_PORT_PLAN.md` needs a
credential broker, `docs/DEV_OS_PORT_PLAN.md` needs that plus a file broker plus
a decision about process execution. An HTML collection needs **none of them**:
its manifest declares `network: deny`, `filesystem: none`,
`credentials.direct_access: false`, and it is still a complete, usable program.
It is the only proposed module that can be finished rather than staged.

**It uses every part of the port.** A collection has items, which is C's tab
list. It has a current document, which is D's header title and path. It has an
edited-but-unsaved state, which is the dirty flag. It has two or three verbs —
add, remove, export — which is exactly `HEADER_ACTIONS_MAX`. A module that used
half the port would leave half of it unexercised, and
`docs/MODULE_MOUNT_CONTRACT.md` §9 is candid that the port has never carried a
message.

**Its hardest problem is the one Sunshine has already solved twice.** The
documents in the collection are HTML authored elsewhere. Rendering them is
exactly the problem `docs/DOCUMENT_SURFACE_CONTRACT.md` solved for the document
surface, and the answer is §3 below. Getting that answer for free is worth more
than the whole rest of the application.

**It is small enough to be finished.** Which matters, because the first module
is also the first test of the seam, and a test that takes three months tells
you about the seam three months late.

## 2. Shape on disk

The seam serves a surface the files under its own directory prefix with that
prefix removed. So the layout is not a matter of taste: it decides whether
mounting is a copy or a rewrite. `MA-8`.

Build the repository like this:

```text
sunshine-htmlbox/                  the application's own repository
  app/
    app.html                       the module UI's entry document
    app.css
    app.ts
    host.ts                        the data port -- the ONLY file that differs per host
    mount_port.ts                  copied, unchanged, from Sunshine
  content/
    app.html                       the reader frame's entry document -- see §3
    app.css
    app.ts
  host/
    sunshine_htmlbox.mojom         the browser-side interface, if it needs one
    *.cc / *.h                     its implementation
  model/                           the collection model. No browser dependency at all.
  module.json                      the manifest
  README.md
```

Mounted into Sunshine, those become:

```text
chrome/browser/resources/sunshine/htmlbox/           <- app/
chrome/browser/resources/sunshine/htmlbox_content/   <- content/
chrome/browser/ui/webui/sunshine/htmlbox/            <- host/
components/sunshine/htmlbox/                         <- model/
first_party/modules/sunshine-htmlbox/module.json     <- module.json
```

Three rules about that table, each of which has already cost this project
something:

1. **The entry document is called `app.html`, always.** `build_webui()` derives
   each resource's name from the bundle prefix and the file's path, so the
   surface directory `htmlbox` plus `app.html` becomes
   `IDR_SUNSHINE_HTMLBOX_APP_HTML`, which is the identifier the C++ names. A
   different filename means editing the mount rather than performing it.
2. **The model depends on no browser.** `components/sunshine/<name>/` may not
   depend on `//chrome` or `//content`. That one-way arrow is what lets the
   model be compiled for a different host — the iPad shell of
   `docs/decisions/0013-module-data-portability.md` — or reimplemented in
   another language, without dragging a browser behind it.
3. **`mount_port.ts` is copied, never imported.** `MA-1`: the app imports
   nothing only Sunshine provides, and a port declared in a file that reaches
   for a browser is not a port. Copy it and keep it byte-identical; a diff
   against Sunshine's copy is a five-second check and a divergence is a bug in
   waiting.

## 3. The two-frame rule, which is the whole architecture

**A collected document is never rendered in the module's own document.**

This is the single most important sentence in this guide. The HTML in the
collection was authored by someone else. It may carry script, forms, remote
image references and anything else HTML can carry. The module's own UI — its
list, its header data, its controls — must not be in the same document as any
of that.

So the application is **two** surfaces, not one:

| Surface | Origin | Holds | Reached by |
| --- | --- | --- | --- |
| The module UI | `chrome-untrusted://sunshine-htmlbox-app/` | The app's own list, controls and state. Mounted in the shell's D region. | The shell's mount port |
| The reader | `chrome-untrusted://sunshine-htmlbox-content/` | One collected document, rendered. Nothing else. | An iframe inside the module UI, one `postMessage` |

The reader is given **one string: the document body**. It is given no
identifier it could ask about, no reference to the store, and no way to name a
second document. That is `DOC-2` — *the frame receives content, never
capability* — expressed as an absence rather than as a filter, and
`chrome/browser/ui/webui/sunshine/document/sunshine_document_content_ui.h` is
the working example to copy from, comments included.

Its data source states its policy rather than inheriting it:

- `connect-src 'none'` — the reader reaches no network. A collected document
  that references a remote image shows the image as absent and **no request
  leaves the browser**, which is the behaviour the whole arrangement exists to
  produce.
- `img-src 'self' data:` and the same for media — a `data:` URL is inline
  content, not a fetch.
- `child-src 'none'` — a collected document carrying its own iframe gets an
  empty box rather than a second renderer with a different policy.
- `form-action 'none'`, `object-src 'none'`.
- `AddFrameAncestor()` naming the module UI's origin and nothing else.

**Do not skip the second surface because the first one already works.** It will
work. A collection viewer that renders documents into its own DOM is a normal
afternoon's work and it is the exact failure `docs/SECURITY_ARCHITECTURE_CONTRACT.md`
exists to prevent — with the aggravating detail that the module UI is the thing
holding the port to the shell.

## 4. What the shell draws, and what you must not

Before designing any screen, read `docs/MODULE_SHELL_CONTRACT.md` §1. The short
version, for this application:

| The application wants | Where it goes | Who draws it |
| --- | --- | --- |
| A list of collections or folders | The shell's C, as the tab list | **The shell.** You send names. |
| The current document's title | D's header title | **The shell.** You send a string. |
| Where it sits — collection, folder | D's header path | **The shell.** You send a string. |
| Unsaved edits | D's header dirty marker | **The shell.** You send a boolean. |
| Add / remove / export | D's header actions, at most three | **The shell.** You send names; it sends back which was pressed. |
| A way to reach other modules | The shell's A and B | **The shell.** You do nothing. |
| The reader, and everything around it | D's body | **You.** |
| An outline, a preview, notes | The shell's E, by role | **You** fill it; the shell switches roles. |

**Do not draw a title bar, a sidebar, a tab strip, a breadcrumb, or a
window-level menu.** Every one of those is a region the browser already draws,
and drawing your own means two of the same thing in one window. The reason it
is a rule rather than a preference is in `docs/MODULE_SHELL_CONTRACT.md` §1: A,
B and D's header carry every way *out* of a module, and a module that drew them
could omit them.

The instinct to keep them is strong and it is worth naming.
`docs/DEV_OS_PORT_PLAN.md` §2 is the case study — the shell every module now
receives is that application's own design, generalised, and keeping its
`shell()` function would have put two implementations of one design side by
side.

## 5. The port, concretely

Read `docs/MODULE_MOUNT_CONTRACT.md` §3 and §4 for the full vocabulary. For
this application the traffic is small.

**On `mount`, and after every change**, send one `describe`:

```text
{ type: 'describe',
  title:  'Reading list',            // D's header
  path:   'Collections / Research',  // D's header, small mono line
  icon:   'list',                    // a name from the closed set
  dirty:  false,
  tabs:   [ {id: 'inbox',    label: 'Inbox',    icon: 'inbox'},
            {id: 'research', label: 'Research', icon: 'list'} ],
  activeTab: 'research',
  actions: [ {id: 'add', label: 'Add', icon: null} ] }
```

Whole state, never a delta — a delta obliges the shell to keep a second copy of
your model in agreement with the first, and the copy is where the two drift.

**On `activate`**, render that tab. **On `action`**, perform that verb. When
*you* move the selection — a search result opened, a document deleted — send
`select` so C follows. When you want the outline in E, send `request-panel`.

Two rules that catch people:

- **Nothing crossing the port is a location.** Not a file path, not a URL, not
  a handle. An identifier is an opaque string the module coined and the shell
  never interprets. If a design needs to send a path, the design is wrong at a
  level the port cannot fix — `MA-2`, and `DOC-3`/`DOC-8` for the storage side.
- **Validate what the host sends.** Use `hostMessage()` from the copied
  `mount_port.ts` and ignore anything that returns null. This is not suspicion
  of Sunshine; it is the reason the port exists. A module that trusts every
  host is a module that works only with the careful ones.

## 6. Where a collection lives

**Read `docs/DOCUMENT_STORE_CONTRACT.md` first; this section is older than it and is wrong where they differ.** The owner has since decided that documents live in a directory the user picks, inside a folder something else already syncs, as one readable file per document with the identity inside it. `//sql` is right for a module's *profile-local* state and wrong for anything in that store: DS-2.

What survives from this section unchanged is the interface, which is the part the app writes.

Chromium's `//sql`, in the profile directory, behind a Mojo interface the app
declares — `chrome/browser/resources/sunshine/document/host.ts` is the working
example of the page half, and
`chrome/browser/ui/webui/sunshine/document/sunshine_document.mojom` of the
declaration.

| Rule | Why |
| --- | --- |
| The module holds no path | `DOC-3`, `DOC-8`. A stored path is ambient authority over the disk arriving through the back door. |
| A document is named by an opaque id | The id means something to the store and nothing to anyone else. |
| The store returns bytes as they were stored | Nothing between the store and the reader rewrites them, so what is exported is what was imported. |
| Import is a user-chosen file, or nothing | `filesystem: none` in the manifest until `docs/FILE_BROKER_CONTRACT.md` has an implementation. Until then, accept a paste or a drop, which is content arriving rather than a location being read. |

The last row is the one design decision worth making early: **an HTML
collection that imports by reading a directory is blocked; one that imports by
receiving content is not.** Design for the second and the module ships now.

## 7. The rules that will refuse your code

Every one of these is enforced, most of them before any build:

| Rule | What it refuses |
| --- | --- |
| No remote resource, ever (`SEC-14`) | A CDN link, a web font, a remote image in your *own* UI, an API called at load. |
| No runtime code construction (`SEC-14`) | `eval`, `new Function`, a template compiler that runs in the browser, a computed dynamic import. |
| No markup assignment (`MS-3`, `MA-6`, `MM-7`) | `innerHTML`, `outerHTML`, `insertAdjacentHTML`, `srcdoc`. Build nodes; write text with `textContent`. |
| No `chrome.send` | Denied by `ui::MojoWebUIController`. Use Mojo. |
| No import of `//resources/js/cr.js` | Upstream's eslint rejects it. Suppressing the rule is not the fix. |
| eslint runs *inside* the build | Interfaces use `;` between members, other type literals use `,`; no `public` modifier; `as` not angle brackets; `T[]` not `Array<T>`; every import carries its extension. Property *names* are not checked, so `snake_case` manifest fields survive. |
| Files are read as UTF-8 explicitly | Tooling that reads in the locale encoding. One CI machine is a Korean Windows box, and this has broken a build already. |
| The manifest describes exactly the authority held | Declaring authority you do not have is a defect of the same kind as exercising authority you were not given (`MA-4`). |

The third row is the one that changes how you write, and it is worth being
concrete: **your own UI is affected too, not only the collected documents.** A
list built from template literals and assigned to a node is refused even when
every string in it is yours.

## 8. Colour and type

Both are narrower than they look, and one of them is narrower than this project
told people for a while.

**Colour.** Every colour resolves through Chromium's token pipeline —
`var(--color-*)`, `var(--cr-*)` — with no fallback, so a theme change reaches
the surface and a missing token fails visibly instead of silently looking
almost right. What is refused is a **literal**: `#0f62fe` names a colour rather
than deriving one, and a literal stops following dark mode, high contrast and
the user's own settings.

What is *permitted*, and what most palettes are actually made of, is
composition: `color-mix()` over a Chromium reference is explicitly allowed by
`docs/DESIGN_SYSTEM_CONTRACT.md` §2.2(3). A hover wash, a dimmed rule, a tint
of the accent — all expressible today, no exception needed.

**Type.** Sizes come from a fixed scale in `rem`: 0.6875, 0.75, 0.875, 1, 1.25,
1.5, 2. A `px` font size is refused outright, because `px` ignores the user's
browser font-size setting and breaks WCAG 1.4.4. The smallest step, `label-xs`,
is for an identifier or a path beside something it belongs to — never for
prose, and never for a control's only label.

## 9. Order of work

1. **The model first, with no browser anywhere near it.** A collection, its
   items, their ids, add and remove. Test it as plain code. This is the part
   that outlives every decision below it.
2. **The reader surface second** — §3. One frame, one message, one document
   rendered. Build it before the UI that will feed it, so the isolation is
   load-bearing from the first day rather than retrofitted around a working
   viewer.
3. **The module UI third**, mounted, sending `describe` with one tab and no
   actions. The point of this step is the *port*, not the UI: get a title into
   D's header from a message and the seam is proven.
4. **Then the list, the tabs and the actions.** Now the port is carrying
   something real, and every addition is small.
5. **Then E**, if the application wants an outline or a preview.

**Do not build the whole UI and mount it at the end.** Mounting is where every
assumption about who draws what gets tested, and an application that has drawn
its own chrome for a month will not want to hear the answer.

## 10. A checklist to hand a session

Before the first mount:

- [ ] `module.json` validates against `scripts/validate_first_party_modules.py`.
- [ ] It declares `network: deny`, `filesystem: none`,
      `credentials.direct_access: false`, `remote_content: false`.
- [ ] It declares `mount` with a `chrome-untrusted://<host>/` content URL, and
      `kind` is `surface`.
- [ ] `mount_port.ts` is byte-identical to Sunshine's copy.
- [ ] No file in the app assigns `innerHTML`, `outerHTML`, `insertAdjacentHTML`
      or `srcdoc`.
- [ ] No `px` font size anywhere; no literal colour anywhere.
- [ ] Every import carries its file extension.
- [ ] The reader surface exists, its CSP is stated rather than inherited, and
      it receives one string.
- [ ] Nothing crossing the port is a path, a URL or a handle.
- [ ] The app draws no title bar, sidebar, tab strip or breadcrumb.
- [ ] Every source file is read and written as UTF-8 explicitly.

## 11. NOT VERIFIED

- **No module has been built to this guide, including this one's worked case.**
  The HTML collection is a design, not a program; nothing in §2 has been mounted
  and nothing in §5 has been sent.
- **The mount port has never carried a message.**
  `docs/MODULE_MOUNT_CONTRACT.md` §9 says so in full. This guide tells a first
  module to be that port's first user, which means it is also the first thing
  that will find out what is wrong with it. Expect at least one correction to
  the port itself, and prefer correcting the port to working around it.
- The two-frame arrangement in §3 is the document surface's, which has itself
  never been run: patches 0006 and 0012 are both unbuilt. The CSP directives are
  read from Chromium's source at the pinned revision, not observed.
- §6 names `//sql` because Chromium provides it and `components/sunshine/`
  already holds a model layer with the required dependency direction. No
  Sunshine module uses it yet.
- The eslint rules in §7 were read from the configuration at the pinned
  revision and confirmed against patches that have built. They are not a
  substitute for running the build.
