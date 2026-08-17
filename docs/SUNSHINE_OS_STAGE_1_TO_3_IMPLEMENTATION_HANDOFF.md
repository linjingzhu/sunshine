# Sunshine OS — Stage 1–3 Implementation Handoff Specification

**Version:** 0.1  
**Status:** Native Chromium downstream roadmap  
**Primary target:** Windows desktop, Chromium-based browser  
**Scope:** Stage 1 Browser Core → Stage 2 Daily Browser → Stage 3 Power Browser  
**Source baseline:** `SUNSHINE_OS_MASTER_SPEC_V0.2.md`

---

## 1. Implementation Contract

### 1.1 Product definition

Sunshine OS is a **browser first** personal operating environment.

The browser must remain a full, unrestricted, stable Chromium browser before it becomes a platform for personal tools. The purpose of Stage 1–3 is not to embed Sunshine Apps, AI, a dashboard, or a note system. It is to build a daily browser that earns the right to become that platform later.

> **Never compromise the browser to build the OS.**

### 1.2 Scope boundary

| Included | Explicitly excluded from Stage 1–3 |
|---|---|
| Chromium web browsing | J-OS / Book OS / MarketPick product implementation |
| Tabs, history, bookmarks, downloads | Universal Object Store |
| Profiles, security mediation, local persistence | NAS sync and cloud storage |
| Gestures, session restore, workspaces, split view | AI assistant / automation |
| Installed external web apps | `sunshine://` production App SDK |
| Command architecture | Full Three.js / spatial application UI |

### 1.3 Web App and SaaS principle

Sunshine Web Apps must be designed as products that can later operate independently as SaaS.

```text
Shared domain/API/data model
      ├─ Independent SaaS: https://j-os.app
      ├─ Independent SaaS: https://bookos.app
      └─ Sunshine integrated client: sunshine://j-os
```

Sunshine Browser may provide privileged integration later, but it must not become the only host for an app's business logic or data model.

### 1.4 Three.js / WebGL boundary

Use WebGL and Three.js as a future **Spatial UI Runtime** for Sunshine Apps, not as the browser chrome implementation.

| Layer | Technology direction |
|---|---|
| Browser chrome: tab strip, omnibox, settings, menus | Chromium Views with Sunshine Design System tokens |
| Remote web content | Chromium renderer with its normal sandbox and site isolation |
| Future canvas, reference board, graph, spatial workspaces | WebGL and Three.js inside a Sunshine native WebUI surface |
| Future rendering abstraction | `SpatialRenderer` with WebGL first and optional WebGPU path |

No Three.js dependency is required in the Stage 1–3 production bundle. Define only the future boundary in architecture documentation.

---

## 2. Technical Decisions and Validation Gates

### 2.1 Initial runtime

Sunshine is a native downstream of the open-source Chromium browser. There is no
embedding layer and no wrapper runtime. Sunshine builds Chromium's own `chrome`
target and carries its changes as a small ordered patch stack against a pinned
upstream revision. See `docs/decisions/0002-native-chromium-downstream.md`.

```text
Sunshine first-party modules   first_party/
  ↓ declared contribution points
Sunshine downstream patches    downstream/patches/
  ↓ applied to
Pinned Chromium source         config/chromium.version
  ↓ GN + Ninja
Native chrome target
```

### 2.2 Required Technology Stack

| Concern | Decision |
|---|---|
| Desktop runtime | Windows-first native Chromium `chrome` target |
| Browser engine | Chromium at the revision pinned in `config/chromium.version` |
| Language | C++ for browser code; TypeScript only inside Chromium WebUI resources |
| Browser chrome UI | Chromium Views; Sunshine surfaces use native WebUI |
| Styling | CSS variables + Sunshine tokens in WebUI; Material 3 principles |
| State | Chromium services own domain state; Sunshine stores only feature-owned metadata |
| Persistence | Chromium profile/session services; Sunshine stores only feature-owned metadata |
| Secrets | OS-backed secure storage adapter |
| Tests | Unit + integration + E2E + compatibility dogfood checklist |

### 2.3 Architecture Gate: Extension compatibility

Conduct this spike before Stage 2 is considered complete.

1. Load an unpacked extension.
2. Enable, disable, remove, and restart with the registry persisted.
3. Display declared permissions and compatibility failures.
4. Test a representative minimum set: password manager, ad blocker, developer tool.
5. Record feature gaps and decide one of the following:

| Outcome | Consequence |
|---|---|
| Required extension set works reliably | Continue Stage 2–3 on the Chromium runtime |
| Required Chrome-extension behavior is missing | Resolve the Chromium integration gap before platform/app investment |

Do not promise Chrome Web Store parity until it is demonstrated.

---

## 3. Non-Negotiable Architecture Rules

### 3.1 Process and trust model

Sunshine inherits Chromium's process model unchanged. It does not introduce a
second trust boundary, a privileged application process, or a custom bridge
between chrome and web content.

```text
Chromium browser process (trusted)
  ├─ Views browser chrome + Sunshine native WebUI
  ├─ TabStripModel / TabGroupModel / NavigationController
  ├─ Profile-keyed services: sessions, bookmarks, history, downloads, permissions
  └─ Sunshine first-party modules at declared contribution points
       ↓ Chromium Mojo interfaces and site isolation
Chromium renderer processes (untrusted web content)
```

Web content reaches Sunshine capability only through Chromium's existing
sandbox, site isolation, and permission mediation. A Sunshine module must never
expose filesystem, credential, or Sunshine metadata access to a web origin, and
must never weaken a Chromium security default to make a feature easier.

### 3.2 Command-first rule

Every user-visible action is a command identifier. UI affordances resolve a
command rather than calling browser internals directly.

`first_party/commands.json` is the authoritative list. It records, for each command, the owner, availability predicate, telemetry event, and error results this rule requires. Do not restate the list here or in a feature contract. An earlier copy in this section kept a split-view "toggle" command alive long after the split-view contract had replaced it with `view.split.open`, `view.split.swap`, and `view.split.close`; a reader could not tell which list was current.

A Sunshine-owned command is claimed by exactly one module, through a `native_command` entrypoint in that module's manifest. Chromium-owned commands such as `browser.back` carry no Sunshine implementation; Sunshine only surfaces them.

Invocation sources include toolbar, keyboard, context menu, mouse gesture, command palette, and later automation.

### 3.3 Domain ownership

Every authoritative owner below is a Chromium service. Sunshine contributes UX
and feature-owned metadata around them; it never creates a parallel owner.

| Domain | Authoritative Chromium owner | Sunshine responsibility |
|---|---|---|
| Windows | `BrowserWindow` / `Browser` | contribute chrome UI, never own window state |
| Tabs and active tab | `TabStripModel` | render/extend native tab UI |
| Navigation | `NavigationController` + omnibox `AutocompleteClassifier` | submit intent / render state |
| Session recovery | `SessionService` / `TabRestoreService` | extend native recovery UX |
| Bookmarks | `bookmarks::BookmarkModel` | list/edit UX |
| History | `history::HistoryService` | search/list UX |
| Downloads | `DownloadManager` | progress/status UX |
| Origin permissions | `HostContentSettingsMap` / permission controller | explain/change UX |
| Security events | Chromium security state + Safe Browsing when present | Security Center UX |
| Themes/preferences | `PrefService` / `ThemeService` | apply token projection |

### 3.4 Required repository layout

```text
config/
  chromium.version          pinned upstream revision
downstream/
  patches/                  ordered Sunshine patch stack + series
first_party/
  registry.json             declarative module inventory
  modules/<id>/module.json  one manifest per first-party module
scripts/                    bootstrap, build, and architecture guards
tests/                      repository contract and guard tests
docs/
  decisions/                architecture decision records
```

Chromium source itself is never vendored into this repository. Sunshine owns only
the pinned revision, the patch stack, the module registry, and its guards. A
patch must own its upstream files exclusively; `scripts/patch_manifest.py`
rejects overlapping ownership.

---

## 4. Cross-Stage Domain Model

### 4.1 Core entities

```ts
interface BrowserTab {
  id: string;
  windowId: string;
  webContentsId: number;
  profileId: string;
  url: string;
  title: string;
  faviconUrl?: string;
  isLoading: boolean;
  canGoBack: boolean;
  canGoForward: boolean;
  isPinned: boolean;
  isMuted: boolean;
  groupId?: string;
  workspaceId?: string;
  createdAt: string;
  lastActivatedAt: string;
}

interface SunshineProfile {
  id: string;
  type: "local" | "google-linked";
  displayName: string;
  avatarUrl?: string;
  googleSubjectId?: string;
  createdAt: string;
  lastUsedAt: string;
}

interface Workspace {
  id: string;
  profileId: string;
  name: string;
  color?: string;
  icon?: string;
  order: number;
  homeUrl?: string;
  createdAt: string;
  updatedAt: string;
}
```

### 4.2 Critical distinction

| Concept | Meaning | Storage isolation |
|---|---|---|
| Profile | Identity and browser data boundary | cookies, site storage, extension set, privacy policy |
| Workspace | Persistent work context | tabs, pinned tabs, optional appearance and home context |
| Tab group | Temporary visual/semantic organization | group label, color, member ordering |

Do not use these terms interchangeably in code or UI.

### 4.3 Persistence categories

| Category | Owner | Examples |
|---|---|---|
| Chromium-managed | Chromium profile partition | cookies, cache, localStorage, IndexedDB, service workers |
| Sunshine-managed | Sunshine metadata store | workspace catalog and Sunshine settings only; never shadow Chromium tab/session data |
| Secure | OS credential vault | OAuth refresh token, API keys, NAS credentials |

Never store secrets in the Sunshine metadata store or in web-accessible storage.

---

## 5. Stage 1 — Browser Core

### 5.1 Goal

The user can browse normal sites for one day without Chrome or Whale.

### 5.2 Stage 1 feature slices

| Slice | Required behavior | Definition of done |
|---|---|---|
| App shell | create/restore window, responsive layout | window resize never overlaps remote content |
| Profile onboarding | `Use locally` works without network; Google is optional | auth failure does not block browser launch |
| Tabs | create, select, close, reorder, duplicate, close others/right | state and active content surface stay consistent |
| Omnibox | URL/search classification, Ctrl+L, paste, Paste & Go | typed URL navigates; ordinary text searches default provider |
| Navigation | back, forward, reload/stop, home | commands mirror actual page capability |
| New Tab | simple search and frequent sites | no Life OS dashboard content |
| Bookmarks | CRUD, folders, bar, manager, search | survives restart |
| History | record/search/reopen/delete/clear | tab history and global history remain separate |
| Appearance | system/light/dark; semantic accent token | no per-component arbitrary color editing |
| Downloads baseline | download lifecycle and risky-file warning | no silent opening of risky files |
| Security baseline | sandbox, sender validation, permission mediation, window-open policy | security test checklist passes |

### 5.3 Omnibox classification contract

```text
Input                 Result
----------------------------------------------------
github.com            navigate to https://github.com
https://github.com    navigate unchanged
localhost:3000        navigate (development-safe rule)
sunshine://settings   internal route request
material design       search with configured provider
```

Classify conservatively. Invalid or ambiguous input must produce a search rather
than an unsafe inferred navigation. Classification and URL normalization stay in
Chromium's omnibox `AutocompleteClassifier`; Sunshine must not add a second
parser in front of it.

### 5.4 Tab state machine

```text
Created → Loading → Ready
                 ↘ Failed
Ready → Loading (navigation/reload)
Any non-closed state → Closing → Closed
```

Rules:

- Closing the active tab activates an adjacent non-closing tab.
- Closing the last normal tab opens a New Tab; it must not leave a dead browser surface.
- A failed navigation retains the tab and shows an error state rather than deleting its history.
- Tab and `WebContents` lifetime is controlled by Chromium `TabStripModel`; UI selection only requests activation.
- Favicon and title updates are asynchronous and must be safe for a tab closed mid-load.

### 5.5 Stage 1 module boundary

Sunshine adds no custom process bridge. A first-party module reaches browser
state only through the contribution points declared in its manifest and
documented in `docs/FIRST_PARTY_MODULE_ARCHITECTURE.md`:

```text
chromium_webui_overlay   decorate or add a native WebUI surface
command                  register a command with an availability predicate
profile_service          observe or extend a profile-keyed Chromium service
integration              observe native browser events
```

A Sunshine WebUI page communicates with the browser process over Chromium's own
Mojo interfaces. Every browser-side handler validates payload shape and the
calling WebUI origin, and no handler is reachable from ordinary web content.

### 5.6 Stage 1 security requirements

1. Deny arbitrary `window.open`; route approved popup/new-window requests through a policy handler.
2. Validate all navigation schemes. Only explicitly supported internal schemes may receive privileged handling.
3. Use a permission request handler with a default-deny policy until the user has a per-origin decision.
4. Warn before opening executable or script-like downloads; flag extension/MIME mismatch.
5. Log security-relevant download decisions with provenance and user action.
6. Separate Sunshine profile OAuth from logging into Google inside a normal browser tab.

### 5.7 Stage 1 acceptance suite

Dogfood for one full day with: Google, Naver, ChatGPT, GitHub, Gmail, Google Drive, YouTube, Naver Blog/Cafe, documentation sites, and standard shopping sites.

Must pass:

- login persistence;
- tab and navigation stability;
- file upload/download;
- media playback;
- popup flows;
- bookmark/history persistence;
- no critical crash;
- no material security regression;
- acceptable CPU/memory during ordinary use.

---

## 6. Stage 2 — Daily Browser

### 6.1 Goal

The user can use Sunshine as their primary browser for one week with no recurring friction that makes them reopen Chrome or Whale.

### 6.2 Mouse gesture specification

Initial bindings:

| Input | Command | Preconditions |
|---|---|---|
| Right hold + drag left | `browser.back` | active tab can go back |
| Right hold + drag right | `browser.forward` | active tab can go forward |

Pipeline:

```text
Pointer input → GestureRecognizer → GestureBinding → CommandService → Browser command
```

Implementation rules:

- Gesture code resolves commands only; it must not call Chromium browser internals directly.
- Do not trigger while selecting text, operating native page controls, dragging files, or when context-menu intent is clear.
- Cancel on insufficient distance, direction ambiguity, focus loss, or native drag start.
- The first release supports only left/right; custom multi-segment gestures are Stage 3+.
- Record gesture success, cancellation reason, and undo/immediate-reversal signal for tuning.

Settings: enabled, sensitivity, trail visibility, per-binding enablement.

### 6.3 Session restore

Chromium `SessionService` remains authoritative for window/tab order, active tab,
pinned state, current URL, navigation, and clean-shutdown recovery. Sunshine must
not persist a parallel session record. Feature-owned tab/window metadata must
round-trip through Chromium session extra-data channels.

Recovery behavior:

| Situation | Expected UX |
|---|---|
| Clean close | restore automatically based on preference |
| Unexpected termination | show `Sunshine didn't close correctly` with Restore / Start fresh |
| One tab fails restoration | restore remaining tabs; show individual failed state |
| Profile unavailable/corrupt | preserve diagnostic record; do not erase data automatically |

Never persist sensitive form content or page snapshots as Sunshine session metadata.

### 6.4 Download Manager

Required states:

```text
Queued → In progress → Completed
                     ↘ Failed / Cancelled / Blocked awaiting user decision
```

Required UI: in-progress indicator, completion, failure explanation, cancel, retry where safe, open, reveal in folder, remove history, security verdict/reason.

The user may choose to proceed with a warned risky file according to policy; Sunshine must not silently block ordinary files without a clear security requirement.

### 6.5 Permission Manager

Per origin, provide camera, microphone, location, notifications, clipboard, popups, and automatic downloads.

States: `ask`, `allow`, `block`, plus effective source (`user`, `temporary`, `policy`). Settings changes must take effect predictably and show whether page reload is required.

### 6.6 Browser utilities

Implement Find in Page, zoom/reset, print, save page, view source, inspect, and link/image context menus. Commands should remain available to command palette later even if their first UI is a menu.

### 6.7 Security Center and threat protection

Provide `sunshine://security` with unsafe-site attempts, risky downloads, extension warnings, active site permissions, certificate warnings, and recent security events.

```text
ThreatProtectionProvider.CheckUrl(url, profile_id) -> {
  verdict:   safe | warn | block | unknown
  categories: optional list
  provider:   provider identifier
  checked_at: timestamp
}
```

Chromium's own Safe Browsing remains authoritative wherever it is present in the
build. A provider is an additive signal, never a replacement for it.

Provider failure must return `unknown`, log the event, and allow normal browsing unless a separately defined strict policy applies. Third-party API details must not leak into browser-core UI or navigation logic.

### 6.8 Stage 2 acceptance suite

Use Sunshine as primary browser for seven consecutive days. Track and review:

- crash and renderer-process recovery rate;
- broken-site and login failures;
- memory growth and background CPU;
- gesture activation, cancellation, false-positive, and reversal rate;
- permission friction;
- download failure and security override rate;
- session restore failure rate.

Discovered reliability issues outrank Stage 3 novelty work.

---

## 7. Stage 3 — Power Browser

### 7.1 Goal

Sunshine has at least three personal advantages compelling enough that the user intentionally keeps it open rather than Chrome or Whale.

### 7.2 Delivery order

1. Command palette and tab search foundation.
2. Workspaces and clear information model.
3. Advanced tab actions using Chromium's horizontal tab strip.
4. Split view.
5. Side panel.
6. Profile isolation UX and installed web app flows.
7. Duplicate detection after measurement validates need.

### 7.3 Workspace contract

A workspace is a **persistent work context**, not an account and not merely a temporary window group.

Initial examples: Personal, Work, Development, Research, Shopping.

Each stores its own tab membership/order, pinned tabs, optional home URL, and optional appearance preference. Workspace switching changes the active context without mixing profile storage.

| Operation | Expected behavior |
|---|---|
| Create workspace | create empty context with a New Tab |
| Switch workspace | hide inactive workspace tabs; restore last active tab |
| Move tab | transfer tab membership; retain its web contents/session |
| Close workspace | require a destination workspace and move all tabs atomically; never silently lose tabs |
| Restart | restore last workspace and preserve all workspace metadata |

### 7.4 Advanced tabs

Required: pin/unpin, native tab groups, tab search, recently closed, and duplicate detection. The initial Sunshine scope keeps Chromium's horizontal tab strip.

### 7.5 Split View

Support two panes first: horizontal/vertical layouts, drag resize, swap panes, close a pane.

Rules:

- Each pane contains one actual tab; a tab cannot be live in two panes simultaneously.
- Closing a split pane returns the surviving tab to normal active view.
- On small window widths, present a deterministic fallback rather than a cramped unusable split.
- Split state is session metadata, not a new profile or workspace.

### 7.6 Side panel

Initial panel modules: tabs, bookmarks, history, downloads. Later AI/apps are explicitly deferred. Panels are lazy-mounted and must not force background loading on every browser window.

### 7.7 Profiles and installed web apps

Profiles isolate cookies, site storage, extension set, history policy, and settings policy.

Installed external web apps are still normal websites with a browser-managed launch experience. They must be clearly distinguished from future `sunshine://` native apps.

### 7.8 Command palette

`Ctrl+K` opens Browser commands only in Stage 3. It supports fuzzy search, keyboard navigation, disabled-state explanation, and recently executed commands. Commands must execute through the same `CommandService` used by toolbar and gestures.

### 7.9 Stage 3 acceptance suite

Demonstrate at least three durable advantages through real dogfooding. Candidate evidence:

- mouse gestures used repeatedly without accidental activation;
- workspaces used to separate Development, Research, and Personal contexts;
- split view used for research/implementation without tab thrash;
- command palette faster than menus for frequent operations;
- personally designed appearance remains readable and consistent.

---

## 8. Design System and UX Requirements

### 8.1 Sunshine Design System

Use Material 3 principles through Sunshine-owned tokens and components. Do not make raw third-party component APIs the product-wide UI API.

```text
Material principles → Sunshine tokens → Sunshine components → Browser features
```

Minimum components: `SunButton`, `SunIconButton`, `SunMenu`, `SunDialog`, `SunTextField`, `SunTooltip`, `SunSwitch`, `SunListRow`.

### 8.2 Accessibility and interaction

- Keyboard-accessible browser chrome and visible focus states.
- Tooltips for icon-only browser controls.
- Do not rely solely on color for security verdicts or tab group identification.
- Korean-first product copy is acceptable; implementation identifiers remain English.
- Loading, offline, empty, error, permission, and blocked states require deliberate UI—not console-only errors.

### 8.3 Appearance model

Users edit semantic values: mode, accent, surface style, contrast, preset. The system owns derived accessible colors.

```css
--sun-color-primary
--sun-color-on-primary
--sun-color-surface
--sun-color-on-surface
--sun-color-outline
--sun-color-error
```

---

## 9. Testing and Quality Gates

### 9.1 Required tests by feature

| Area | Unit | Integration | E2E |
|---|---|---|---|
| Navigation classification | yes | yes | representative URLs/searches |
| Tab lifecycle | yes | native `TabStripModel` integration | create/select/close/restart |
| Bookmarks/history | yes | repository persistence | create/search/reopen/restart |
| Downloads | yes | lifecycle/policy | completed/failed/warned flow |
| Permissions | yes | origin policy | allow/block/reload behavior |
| Session restore | yes | persistence/recovery | clean/crash-like scenarios |
| Gesture recognition | yes | command dispatch | valid/cancelled gesture flows |
| Workspaces/split | yes | session serialization | switch/move/restore layout |
| Module boundary | yes | WebUI origin/payload rejection | untrusted page cannot reach privileged API |

### 9.2 Performance checks

Set initial budgets during implementation and refine after baseline profiling. At minimum, measure browser launch, first remote-content presentation, tab switching, memory with 10/30 tabs, CPU while idle, and restoration time.

No optimization should break page compatibility or security boundaries merely to improve a synthetic metric.

### 9.3 Required reporting for each implementation wave

Every implementation handoff reports:

1. Scope completed and changed files.
2. Commands/services added or altered.
3. Tests run and results.
4. Manual compatibility scenarios tested.
5. Known limitations and deferred decisions.
6. Security implications and any policy change.

---

## 10. Suggested Implementation Waves

Waves 0–2 are already satisfied by the native downstream: Chromium supplies
windows, tabs, the omnibox, and navigation on the first successful build. The
remaining waves are Sunshine work on top of that.

| Wave | Deliverable | Gate |
|---|---|---|
| 0 | Pinned upstream, patch stack, module registry, architecture guards | guards and contract tests pass |
| 1 | Native Windows `chrome` build on a dedicated runner | build produces a runnable installer |
| 2 | Sunshine New Tab and branding verified at runtime | visual verification against the spec |
| 3 | Profiles, onboarding, bookmarks, history, New Tab, persistence | restart persistence passes |
| 4 | Download baseline, permissions, secure window-open policy | download/permission flows pass |
| 5 | Stage 1 dogfood and extension spike | architecture gate decision recorded |
| 6 | Gestures, session restore, Download Manager, utilities | daily-use UX validation begins |
| 7 | Security Center and threat provider abstraction | provider failure does not break navigation |
| 8 | Stage 2 seven-day dogfood fixes | reliability gate passes |
| 9 | Command palette, workspaces, advanced tabs | context switching works after restart |
| 10 | Split view, side panel, profiles/web apps | Stage 3 dogfood starts |
| 11 | Performance and polish based on real usage | three durable advantages demonstrated |

Do not start a later wave while a previous security or reliability gate is knowingly failing.

---

## 11. Decisions Required From Product Owner

These decisions should be answered before or at the named gate; they are not implementation details Codex should silently invent.

| Priority | Decision | Required by |
|---|---|---|
| P0 | Is partial extension compatibility acceptable for v1? | Stage 1 architecture gate |
| P0 | What is the default profile/data deletion and backup policy? | before persistence release |
| P0 | What behavior is allowed for a warned dangerous download: warn/allow, warn/block, or policy-dependent? | Stage 1 download release |
| P1 | Can a workspace span multiple windows in v1? | Stage 3 workspace design |
| P1 | Which threat provider and commercial licensing model applies? | Stage 2 security release |
| P1 | Should installed web apps open in dedicated windows, tabs, or both? | Stage 3 web app release |

---

## 12. Explicit Non-Goals for Codex

- Do not claim universal Chrome extension support.
- Do not put arbitrary remote page data into Sunshine's metadata database.
- Do not expose filesystem or credential APIs to remote content.
- Do not implement Three.js browser chrome or a 3D New Tab dashboard.
- Do not add Stage 4 app runtime, NAS sync, Universal Object Store, or AI features while Stage 1–3 gates remain open.
- Do not replace measurable dogfooding with a feature-complete checklist.

---

## 13. Start Prompt

```text
You are implementing Sunshine OS Stage 1–3 as a native downstream of the
open-source Chromium browser. There is no wrapper runtime. Sunshine builds
Chromium's own chrome target and ships changes as a small ordered patch stack
against the revision pinned in config/chromium.version.

Read this document and .ai/PROJECT_CONTEXT.md before changing code. Treat
Browser First as the highest product rule: ordinary secure web browsing must
never be degraded to add Sunshine features. Chromium keeps ownership of tabs,
omnibox, navigation, history, downloads, permissions, profiles, renderer
isolation, and the sandbox.

Take one wave at a time. Inspect the repository and the native contracts under
docs/ before proposing a change. Do not implement later stages or invent product
decisions marked P0/P1.

For every wave: implement only its approved scope, run the repository guards and
tests, report files and commands changed, compatibility scenarios, security
impact, and blockers. Never claim a native build, runtime, or visual result that
was not actually observed.
```
