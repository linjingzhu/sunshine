# Marketpick → Sunshine module: the plan

## 0. Status

**Plan, not work.** Nothing is built. It is written from the owner's own
description of Marketpick, and every claim about that application is theirs
rather than measured by me — §7 says what still has to be established before
the first line moves.

`docs/MODULE_PORTING_GUIDE.md` is the general method. This is that method
applied to one application, and it exists because the general one had to stay
general: Marketpick's shape decides things the guide can only pose as options.

## 1. What Marketpick is

As described by the owner:

| | |
| --- | --- |
| Build | Python + Flask, packaged with PyInstaller `onedir` into a Windows executable. |
| Runtime | Launching it starts a local web server and opens the default browser at `http://127.0.0.1:5600`. |
| UI | No framework. 8–9 independent Jinja2 templates, plus a shared `theme.css` and `theme.js` in its static directory, carrying light/dark tokens. No React, no build tooling. |
| Storage | One SQLite file, `marketpick.db`, beside the executable. No account, no cloud, no remote database. |
| Network | Marketplace APIs only — Naver Commerce API and Coupang WING. Without keys it falls back to stubs. |
| Chrome | A top navigation bar it draws itself — 홈 / 상품수집 / 상품목록 / 마켓관리 / 주문관리 / 문의관리 / 통계 / 권리보호 / 환경설정, plus a theme toggle. **Duplicated in every template**: changing the menu means editing nine files. No sidebar. |

## 2. The finding that shapes everything

**Marketpick is not a web app. It is a server with a web front end, and the
server is the part that cannot come.**

A Sunshine module is compiled into the browser — `docs/decisions/0006-module-execution-model.md`
— and a Chromium build contains no Python, no PyInstaller bundle and no second
executable. So the port is not one job but two, and they have very different
risk:

- **The front end ports cleanly.** Framework-free HTML/CSS/JS is the easiest
  possible starting point. There is no bundler to unpick, no framework runtime
  that compiles templates at run time, and nothing that has to be talked out of
  reaching a CDN.
- **The Flask layer has to be rewritten**, in C++, behind a Mojo interface.
  That is the real cost of this port and it should be named as such before it
  starts.

Everything below follows from that split.

## 3. Where each piece lands

| Marketpick today | In Sunshine | Notes |
| --- | --- | --- |
| Top nav bar, duplicated ×9 | **Deleted.** It is B and C — the dock and the tab list, which the shell draws. | The nine menu items become the module's tab list *content*, supplied once through the host port. Nine copies of chrome become zero. |
| Theme toggle | **Deleted.** | Chromium's own theming already follows the OS and the browser. `docs/MODULE_SHELL_CONTRACT.md` §7 covers the colour rules. |
| `theme.css` / `theme.js` light-dark tokens | **Deleted**, replaced by Chromium's token pipeline. | The app's tokens are the right *idea* — they are simply the wrong source. |
| 8–9 Jinja2 templates | One surface, `chrome://sunshine-marketpick`, mounted in the shell's D region. | Jinja2 renders on a server that no longer exists; the templates become static HTML plus TypeScript that fills them from the host port. |
| Flask routes | Methods on one Mojo interface. | `docs/decisions/0013-module-data-portability.md` §2.5: one named host interface per module. |
| Flask business logic | `components/sunshine/marketpick/` | C++ depending on neither `//chrome` nor `//content`, the same arrangement `components/sunshine/document/` already uses. |
| SQLite `marketpick.db` beside the exe | Chromium's `//sql`, in the profile directory. | The file stops living beside an executable, because there is no longer an executable of its own. A module holds no path — `DOC-3` and `DOC-8`. |
| Naver Commerce / Coupang WING calls | **Staged out.** See §4. | |
| API keys | **The module may not hold them.** See §4. | |
| PyInstaller, the local server, port 5600, "open the default browser" | **All gone.** | The browser *is* the executable. This is the largest single deletion and it is pure simplification. |

## 4. The two decisions that are the owner's

Both are about the marketplace integrations, and both are blocked on things
this repository has deliberately not built.

### The network

`SEC-14` forbids a Sunshine-authored web asset from loading any remote
resource. Calling Naver Commerce or Coupang WING therefore needs
`network.access: allowlist` in the manifest, with a named host and an argument
for each — and the calls have to be made by the browser process, not the page.

### The keys

This one is already settled in shape, and it is stricter than it looks.
`docs/SECURITY_ARCHITECTURE_CONTRACT.md` SEC-7:

> A module never receives a credential. It requests an operation; the broker
> holds the secret.

`scripts/validate_first_party_modules.py` enforces it — `credentials.direct_access`
cannot be true. `docs/decisions/0011-ai-credential-broker.md` shapes what a
broker would be and states plainly that it is a proposal, not something that
exists.

So **Marketpick's keyed integrations are blocked on an unbuilt subsystem.**
That is not a reason to stop, because of the next paragraph.

### Marketpick already drew this line itself

The application falls back to stubs when it has no keys. **That mode is Stage 1
of the port, and it exists already.** The owner does not have to invent a
reduced version to get started, and the boundary between "works now" and "needs
a broker" is one the application already understands.

## 5. Staging

| Stage | Contents | Blocked on |
| --- | --- | --- |
| **1** | The surface, the nine tabs, the storage layer in `//sql`, the whole UI, stub data. Manifest declares `network: deny`, `filesystem: none`, `credentials.direct_access: false`. | Nothing. |
| **2** | The marketplace integrations, in the browser process, behind an allowlist. | The owner's network decision. |
| **3** | Real keys. | The credential broker, which is unbuilt and whose existence is an open decision. |

Stage 1 is a complete, usable module by itself for anyone working with data
already in the database. It is also the stage that proves the port boundary —
`MA-3` asks for a second host, and a stub-backed UI is the natural second host.

## 6. Order of work

1. **Inventory.** `docs/MODULE_PORTING_GUIDE.md` Phase 0, in Marketpick's
   repository. The owner's summary above is a description, not a measurement;
   the inventory is what the plan is executed against.
2. **Delete the nine copies of chrome first.** It is the largest deletion, it
   is unambiguous, and everything after is written against the space left. It
   also removes the maintenance problem the owner named — nine files to edit
   for one menu change — permanently, by removing the menu.
3. **Define the Mojo interface from the Flask routes**, before moving logic.
   The route list *is* the interface, and it is the artefact worth reviewing.
4. **Move the storage layer**, `//sql` behind that interface. Verify against
   the real `marketpick.db`.
5. **Port the templates**, one at a time, each one landing in the shell's D
   region with its tab in C.
6. **Then, and only then**, take Stage 2 to the owner with a concrete list of
   hosts and calls.

## 7. What has to be established before any of this

Everything in §1 came from a summary. The port is executed against the
inventory, not the summary, and these are the specific places where the
difference will matter:

- **What the nine screens actually do.** "상품수집" that fetches from a
  marketplace is Stage 2; "상품목록" that reads the database is Stage 1. The
  staging in §5 assumes that split and has not verified it.
- **How much of Flask is business logic versus glue.** The C++ rewrite is the
  cost of this port, and nobody has measured it. It may be a week or a month.
- **What the SQLite schema is**, and whether anything in it is a filesystem
  path — those cannot survive.
- **Whether any template does anything at run time that HTML cannot** — Jinja2
  is server-side, so most of it becomes static, but a template that generates
  script is a different problem (`SEC-14`).
- **Whether Marketpick has tests**, and how many pass now. That number is the
  baseline the port must not silently lose.

## 8. NOT VERIFIED

- **I have not seen Marketpick.** Every fact in §1 is the owner's description,
  relayed. No file, no route, no schema and no dependency has been read.
- The C++ rewrite in §3 is an architecture, not an estimate. Its size is
  unknown and §7 says so.
- The host port that §3 and §5 depend on has no implementation —
  `docs/MODULE_APP_GUIDE.md` §8 records it as an argument rather than a
  measurement. A Marketpick port would be its first user and should expect to
  define it.
- `//sql` is named because Chromium provides it and `components/sunshine/`
  already holds a model layer with the required dependency direction. No
  Sunshine module uses it yet.
