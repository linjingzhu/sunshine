# Browser Utilities — Native Ownership Contract

## Status and scope

This contract applies to Sunshine OS on the pinned Chromium revision
`152.0.7977.42` recorded in `config/chromium.version`. It covers the everyday
browser utilities required by section 6.6 of
`docs/SUNSHINE_OS_STAGE_1_TO_3_IMPLEMENTATION_HANDOFF.md`: Find in Page, zoom
and zoom reset, print, save page, view source, inspect, and the link and image
context-menu actions.

This wave is **documentation-only**. It adds no downstream patch, no first-party
module, and no registered command. Nothing here has been verified against a
native build; see *Not verified* below.

Sunshine OS is a native downstream of open-source Chromium. There is no wrapper
runtime, no embedded browser engine, and no JavaScript shim layer through which
these utilities could be re-expressed. Every utility in scope is already
implemented, localised, keyboard-accessible, and security-reviewed upstream.

## Decision

**Sunshine does not implement any of these utilities.** It inherits all seven
from the pinned revision and adds nothing to them in Stage 1.

This is an intentional **zero-runtime-patch** decision, taken on the same
grounds as `docs/PERMISSION_POLICY.md`. The pinned revision already satisfies
the whole of section 6.6. A downstream patch that restated that behaviour would
add upstream-roll cost and regression surface without changing what the user
can do.

## Ownership

| Utility | Chromium-owned component (pinned revision) | Sunshine may decorate | Sunshine must never do |
|---|---|---|---|
| Find in Page | `FindBarController` and the native find bar, driven by `find_in_page::FindTabHelper` over `WebContents::Find` / `StopFinding`; matching and highlighting performed by Blink's `TextFinder` | Theme the find bar through Sunshine design tokens once a themed-chrome patch exists; route a Sunshine invocation source (menu, gesture, later palette) into the native controller | Run its own text search over page content, extract or index page text, re-count matches, paint its own highlights, or debounce/rewrite the query before Chromium sees it |
| Zoom in, zoom out, reset zoom | `zoom::ZoomController` per `WebContents`, backed by `content::HostZoomMap`; per-host levels persisted by `ChromeZoomLevelPrefs` in the profile's partition preferences | Present the zoom level and a reset affordance in Sunshine chrome, reading `ZoomController` state through its observer | Keep a Sunshine zoom store, apply CSS or layout scaling of its own, cache a per-tab level that outlives the native one, or apply a zoom decision to an origin other than the one Chromium resolved |
| Print | `printing::PrintViewManager` and the Print Preview WebUI (`chrome://print`), with platform print dialogs and Chromium's own PDF path | Expose the existing print entry point from a Sunshine menu or later command surface | Render its own preview, serialise page content to an intermediate format, choose a printer, or pass document bytes through Sunshine-owned code or any network endpoint |
| Save page | `content::SavePackage` reached through `WebContents::SavePage` / `OnSavePage`, with `SavePackageFilePicker` and Chromium's save-page-type selection (complete, single file, HTML only) | Expose the existing entry point; surface the resulting item through the download surface defined in `docs/DOWNLOAD_SAFETY.md` | Fetch the page again to build its own archive, rewrite resource URLs, choose the save type on the user's behalf, or copy the saved bytes anywhere other than the user-chosen destination |
| View source | The `view-source` scheme handled by `content`, invoked by the native view-source command over the active `NavigationController` entry | Nothing in Stage 1 | Render source in a Sunshine WebUI page, re-fetch the document to obtain source, syntax-highlight by proxying content through first-party code, or hide the entry point |
| Inspect (developer tools) | `DevToolsWindow` over `content::DevToolsAgentHost`; availability governed by Chromium's `DeveloperToolsAvailability` policy handling | Nothing in Stage 1 | Gate, wrap, proxy, log, or disable DevTools; expose a Sunshine-owned remote-debugging channel; or make inspection conditional on a Sunshine sign-in, profile, or feature flag |
| Link context-menu actions (open in new tab, open in new window, open in incognito, copy link address, save link as) | `RenderViewContextMenu` over `RenderViewContextMenuBase`, using `content::ContextMenuParams` and the command IDs in `chrome/app/chrome_command_ids.h` | Append clearly separated Sunshine items (for example, a future move-to-workspace item) below the native items | Rebuild the menu as a Sunshine widget, remove or reorder native items, reinterpret the link target from page text or the accessibility tree, or change what "open in incognito" means |
| Image context-menu actions (open image in new tab, save image as, copy image, copy image address) | `RenderViewContextMenu` with the image members of `ContextMenuParams`; saving routed through Chromium's download pipeline | Append clearly separated Sunshine items below the native items | Decode, re-encode, resize, hash, upload, or cache image bytes; substitute a Sunshine image viewer; or resolve the image URL itself |

“Decorate” means presentation and invocation only: theming, placement, an
additional entry point, or an appended and visually separated menu item. It
never means intercepting the action, transforming its input, or observing its
payload.

## Implementation authority in the pinned revision

| Concern | Chromium source |
|---|---|
| Find bar lifecycle and request routing | [`chrome/browser/ui/find_bar/find_bar_controller.h`](https://github.com/chromium/chromium/blob/152.0.7977.42/chrome/browser/ui/find_bar/find_bar_controller.h) |
| Per-tab find state, request IDs, match ordinal and count | [`components/find_in_page/find_tab_helper.h`](https://github.com/chromium/chromium/blob/152.0.7977.42/components/find_in_page/find_tab_helper.h) |
| Find and stop-find entry points on web contents | [`content/public/browser/web_contents.h`](https://github.com/chromium/chromium/blob/152.0.7977.42/content/public/browser/web_contents.h) |
| Match finding, active-match selection, highlighting | [`third_party/blink/renderer/core/editing/finder/text_finder.h`](https://github.com/chromium/chromium/blob/152.0.7977.42/third_party/blink/renderer/core/editing/finder/text_finder.h) |
| Per-contents zoom control and observation | [`components/zoom/zoom_controller.h`](https://github.com/chromium/chromium/blob/152.0.7977.42/components/zoom/zoom_controller.h) |
| Host-keyed zoom level storage and defaults | [`content/public/browser/host_zoom_map.h`](https://github.com/chromium/chromium/blob/152.0.7977.42/content/public/browser/host_zoom_map.h) |
| Zoom-level persistence in profile preferences | [`chrome/browser/ui/zoom/chrome_zoom_level_prefs.h`](https://github.com/chromium/chromium/blob/152.0.7977.42/chrome/browser/ui/zoom/chrome_zoom_level_prefs.h) |
| Print initiation and preview lifecycle | [`chrome/browser/printing/print_view_manager.h`](https://github.com/chromium/chromium/blob/152.0.7977.42/chrome/browser/printing/print_view_manager.h) |
| Print Preview WebUI | [`chrome/browser/ui/webui/print_preview/print_preview_ui.h`](https://github.com/chromium/chromium/blob/152.0.7977.42/chrome/browser/ui/webui/print_preview/print_preview_ui.h) |
| Complete-page serialisation and resource collection | [`content/browser/download/save_package.h`](https://github.com/chromium/chromium/blob/152.0.7977.42/content/browser/download/save_package.h) |
| Save destination and save-type selection | [`chrome/browser/download/save_package_file_picker.h`](https://github.com/chromium/chromium/blob/152.0.7977.42/chrome/browser/download/save_package_file_picker.h) |
| View-source and inspect browser commands | [`chrome/browser/ui/browser_commands.cc`](https://github.com/chromium/chromium/blob/152.0.7977.42/chrome/browser/ui/browser_commands.cc) |
| Developer tools window and agent attachment | [`chrome/browser/devtools/devtools_window.h`](https://github.com/chromium/chromium/blob/152.0.7977.42/chrome/browser/devtools/devtools_window.h) |
| Developer tools availability policy | [`chrome/browser/policy/developer_tools_policy_handler.h`](https://github.com/chromium/chromium/blob/152.0.7977.42/chrome/browser/policy/developer_tools_policy_handler.h) |
| Page, link, and image context menu construction | [`chrome/browser/renderer_context_menu/render_view_context_menu.h`](https://github.com/chromium/chromium/blob/152.0.7977.42/chrome/browser/renderer_context_menu/render_view_context_menu.h) |
| Context-menu parameters supplied by the renderer | [`content/public/browser/context_menu_params.h`](https://github.com/chromium/chromium/blob/152.0.7977.42/content/public/browser/context_menu_params.h) |

These paths are the contract's evidence, not an instruction to modify them. An
upstream roll that moves or renames any of them requires this table to be
re-checked; it does not by itself require a Sunshine change.

## Why no downstream patch is warranted

The argument is the same shape as the permission-policy argument, applied to
seven utilities rather than seven content settings.

1. **The requirement is already met.** Section 6.6 asks for these utilities to
   exist and work. On the pinned revision they exist, work, are localised into
   every Chromium locale, are keyboard reachable, and are exposed to platform
   accessibility. A patch cannot improve a requirement that is already
   satisfied; it can only risk it.
2. **Each of them is a security boundary.** Save page, print, and the image
   actions read document bytes. View source and inspect expose renderer state.
   Link actions decide which profile and which storage partition a navigation
   lands in. Interposing first-party code on any of these paths creates a new
   place for a same-origin or cross-profile mistake to occur, with no
   compensating user benefit.
3. **The correctness bar is high and largely invisible.** Find in Page must
   handle bidirectional text, composed characters, shadow DOM, `contenteditable`,
   scrolled and clipped subtrees, cross-frame ordering, and incremental
   re-search during load. Zoom must interact correctly with device scale
   factor, per-origin storage, and full-screen. Reimplementing any part of this
   would look complete in a demonstration and be wrong in production.
4. **The cost is paid at every roll, forever.** A patch against
   `RenderViewContextMenu` or the find bar touches files that change frequently
   upstream. `docs/decisions/0002-native-chromium-downstream.md` commits
   Sunshine to a small, defensible patch series; spending patch budget on
   behaviour we already have is the clearest possible misuse of it.
5. **There is no product differentiator here.** Sunshine's claimed advantages
   are workspaces, split view, gestures, and the command surface. None of them
   requires owning how a page is printed or how a match is highlighted.

The correct Stage 1 output for section 6.6 is therefore this document and a
later command-registry entry per utility, so that the same action is reachable
from a menu, a keyboard binding, and eventually the palette through one
dispatch path — not seven new implementations.

## Invariants

These hold for any current or future Sunshine surface. Each is falsifiable at
runtime once a native build exists.

### Find in Page

1. Match counting and the current-match ordinal come from Chromium's find
   pipeline and are displayed verbatim. Sunshine never recomputes, rounds,
   caps, or estimates them.
2. Highlight rendering — all-match highlighting and the distinct active match —
   remains Blink's. Sunshine adds no overlay, no scroll marker, and no
   selection of its own.
3. Find-next and find-previous ordering, wrap-around, and case and diacritic
   handling are whatever the pinned revision does. Sunshine does not add
   options to that surface.
4. Find state is per-`WebContents`. Switching tabs, switching workspaces, or
   entering a split does not transplant one tab's find session onto another.
5. The query is not persisted by Sunshine, not written to workspace or session
   metadata, and not sent anywhere.

### Zoom

6. Zoom level is set through the native zoom controller and persists per origin
   through Chromium's own settings and profile preferences. Sunshine keeps no
   parallel zoom map and performs no zoom persistence of its own.
7. Reset zoom returns the origin to Chromium's default level for that profile —
   it is not implemented as "set 100%" against a Sunshine-held baseline.
8. A zoom change made through a Sunshine affordance and one made through the
   native menu or keyboard are indistinguishable in stored state.
9. Zoom applied to one origin never propagates to an unrelated origin, and
   never crosses a profile or incognito boundary.

### Print and save

10. Print always opens Chromium's own preview and platform dialogs. Sunshine
    provides no alternative preview and no "quick print" that bypasses them.
11. Save page always uses Chromium's file picker and save-page types. Sunshine
    does not preselect a type or a directory on the user's behalf.
12. Document content never passes through Sunshine-owned code. No first-party
    module reads the serialised page, the print document, the generated PDF, or
    the saved resources — in memory, on disk, or over the network.
13. A saved page appears in the native download model and is subject to
    `docs/DOWNLOAD_SAFETY.md`; Sunshine adds no second record of it.
14. Neither utility is available in a context where Chromium disables it, and
    neither is disabled in a context where Chromium allows it.

### View source and inspect

15. View source and inspect remain reachable from the native context menu and
    the native menu structure in every window type where the pinned revision
    offers them.
16. Neither is gated behind a Sunshine surface, workspace, split state, sign-in,
    onboarding step, or feature flag. If a Sunshine surface fails to load, both
    remain usable.
17. View source shows the document Chromium already holds. Sunshine never
    triggers a second network fetch to produce it.
18. Sunshine never suppresses, filters, or annotates a DevTools console
    message, network entry, or issue.

### Context menus

19. The page, link, and image context menus are the native menus. Sunshine does
    not replace them with a first-party widget.
20. Native items are neither removed nor reordered. Any Sunshine item is
    appended after a separator and is visibly attributable to Sunshine.
21. A Sunshine item obeys the same enablement rules the native menu would apply
    to an equivalent action, and shows its disabled reason rather than silently
    doing nothing.
22. The link or image target used by any Sunshine item comes from the native
    context-menu parameters, never from page text, the DOM, or a screenshot.

## Developer-tools policy

Inspect stays available. Sunshine ships the pinned revision's DevTools and does
not restrict it by default. Where an environment restricts it, the restriction
is Chromium's enterprise `DeveloperToolsAvailability` handling and is reported
as managed policy, not as a Sunshine product choice.

The consequence must be stated plainly, because it constrains design rather
than code:

- **Sunshine-owned WebUI surfaces are inspectable.** The New Tab surface, any
  `sunshine://` page, and the workspace and split chrome that Chromium renders
  as WebUI can be opened in DevTools by the user, exactly as `chrome://`
  surfaces can. Sunshine will not patch DevTools to hide them.
- **Therefore no Sunshine surface may hold a secret.** No API key, service
  credential, signed token, or internal endpoint may exist in first-party WebUI
  source, bundled assets, generated markup, or client-side storage. Anything a
  Sunshine surface can read, the user can read.
- **Therefore no Sunshine surface may rely on client-side enforcement.** Any
  guard that matters — a permission check, an availability predicate, a
  destructive-action confirmation — must be enforced where the command is
  executed, not in the WebUI that invokes it. A user editing state through the
  DevTools console must not be able to obtain an outcome the command layer
  would refuse.
- **Inspectability is a test surface, not a support surface.** Sunshine
  documentation may point at DevTools for diagnosis; it must not require the
  user to open DevTools for any normal task.

Sunshine must not add a remote-debugging endpoint, a persistent DevTools
protocol client, or any automation attachment to `DevToolsAgentHost` as part of
this or any adjacent feature.

## Interaction with split view

`view.split.open` places two distinct tabs of the active workspace into two
independently focusable panes, each backed by one real `WebContents`
(`docs/TAB_WORKSPACE_SPLIT_CONTRACT.md`, sections 2 and 5). Every utility in
this contract is therefore already correctly scoped, because each is bound to a
`WebContents` rather than to a window.

| Utility | Scope in a split | Note |
|---|---|---|
| Find in Page | Focused pane only | Each pane keeps its own find session; a second pane's matches are neither counted nor highlighted by the first pane's search. |
| Zoom and reset zoom | Focused pane only | Both panes may show the same origin at once; because zoom is stored per origin, a change in one pane is expected to be reflected in the other. That is Chromium's behaviour and must not be "fixed" by Sunshine. |
| Print | Focused pane only | Sunshine must never compose a single print job from both panes. |
| Save page | Focused pane only | One invocation saves one document. |
| View source | Focused pane only | Where Chromium opens view-source in a new tab, that tab joins the active workspace under normal tab rules and does not enter a pane implicitly. |
| Inspect | Focused pane only | Inspect targets the pane whose contents were right-clicked, not the pane that most recently had focus. |
| Link and image context-menu actions | The pane containing the click | Context-menu parameters already identify the originating frame; Sunshine must not retarget them to the other pane. |

Additional rules:

- Pane focus is the only input to "which pane" for keyboard and menu
  invocations. Pointer position is not a substitute; an invocation from a menu
  opened over an unfocused pane targets the pane the menu belongs to.
- `view.split.swap` exchanges pane positions without navigation or reload and
  therefore must not clear a pane's find session or zoom level.
- `view.split.close` returns the survivor to the normal view with its find and
  zoom state intact.
- A tab that opens in a new tab as a result of one of these actions follows
  normal workspace membership rules; it does not silently replace a pane.

## Command registration is deferred

Section 6.6 requires these actions to be reachable from the command palette
later, and section 4 of the handoff requires every user-visible action to be a
registered command with one implementation, an availability predicate, a
telemetry event, and error results.

No command identifier exists yet for any utility in this contract, and this
document deliberately names none. `first_party/commands.json` is the only
authoritative list; a document that invented identifiers ahead of the registry
would recreate exactly the drift that registry exists to prevent. Registration
is a separate, reviewed change.

When those commands are registered they must be `chromium`-owned, carry no
Sunshine guard, and dispatch to the existing native implementation. Registering
them adds an invocation route; it does not transfer ownership of any behaviour
described above.

## Prohibited duplicate state

Sunshine code must not introduce:

- a text index, extracted page text, or search cache derived from page content;
- a Sunshine zoom store, per-tab zoom cache, or zoom entry in workspace or
  session metadata;
- a print or save queue, spool directory, temporary archive, or generated PDF
  held by first-party code;
- a copy of view-source output or of any DevTools message;
- a context-menu model built from anything other than native context-menu
  parameters;
- telemetry containing a find query, a printed or saved document's content, a
  file path chosen by the user, an inspected URL, or a link or image URL.

Transient state is permitted only while a Sunshine surface is open, must be
invalidated by native observers, and must never become a source of truth or a
recovery path.

## Acceptance criteria

These are checkable at runtime once a native build exists. They test that
Sunshine has *not* interposed itself; all of them should pass on an unmodified
pinned build, and that is the point.

**Find in Page**

1. On a fixture page with a known number of matches, including matches inside
   an iframe, a scrolled container, and a `contenteditable` region, the
   displayed count and ordinal equal Chromium's reported values exactly.
2. Find-next past the last match wraps to the first, and the active-match
   highlight is the native one; no additional highlight layer is present.
3. Two tabs each run a different query concurrently; switching between them,
   and switching workspaces, preserves each session independently.
4. The query does not appear in any Sunshine-written file, preference, or
   telemetry payload after the find bar is closed.

**Zoom**

5. Zoom an origin in one tab; open the same origin in a second tab in the same
   profile; the second tab shows the same level without Sunshine involvement.
6. Restart cleanly; the per-origin level persists, and it is present in the
   profile's native preference storage and in no Sunshine-owned file.
7. Reset zoom returns the origin to the profile default; a subsequent query of
   the native zoom controller reports the default level.
8. The same origin zoomed in a regular profile shows the default level in
   incognito and in a second profile.

**Print and save**

9. Invoking print opens Chromium's preview; cancelling leaves no Sunshine
   artefact and no download record.
10. Saving a complete page produces the native directory-plus-file result, the
    item appears once in the native download model, and no first-party module
    has opened the saved files.
11. A page that Chromium refuses to save or print behaves identically with and
    without Sunshine surfaces open.
12. Process and file-access tracing during a print and a save shows no
    first-party module in the document data path.

**View source and inspect**

13. View source and inspect are present and enabled in the page context menu in
    a normal window, an incognito window, a split pane, and a window whose
    Sunshine chrome has been forced into a failure state.
14. View source produces no additional network request for an already-loaded
    document.
15. Inspect opens DevTools attached to the right target for each pane of a
    split and for a subframe.
16. Opening DevTools on a Sunshine WebUI surface succeeds; a scan of that
    surface's shipped source and client-side storage finds no credential,
    token, or private endpoint.
17. Mutating that surface's client-side state through the DevTools console
    cannot produce a command outcome the command layer would refuse.

**Context menus**

18. The link and image context menus contain the pinned revision's native items,
    in native order, with no removals.
19. Copy link address yields the exact target URL from native context-menu
    parameters, including for a redirecting or percent-encoded link.
20. Open link in incognito lands in an off-the-record context with no regular
    profile history or storage written.
21. Save image and save link route through the native download pipeline and are
    subject to `docs/DOWNLOAD_SAFETY.md`; no image bytes pass through
    first-party code.

**Roll gate**

22. At each upstream roll, the source paths in *Implementation authority* still
    exist or their replacements are identified, and criteria 1–21 are re-run.
    A changed upstream behaviour blocks the roll for review; it is not
    corrected by layering a Sunshine implementation over Chromium.

## Not verified

Nothing in this document has been executed. Specifically, this wave includes:

- no Chromium checkout, configuration, compilation, or link of the pinned
  revision;
- no launch of a Sunshine or Chromium binary on any platform;
- no runtime execution of any acceptance criterion above;
- no visual, accessibility, localisation, or keyboard verification of the find
  bar, print preview, save picker, view-source output, DevTools, or context
  menus;
- no confirmation that the cited source paths exist at
  `refs/tags/152.0.7977.42`; they are stated from the documented architecture of
  the pinned line and must be checked when a checkout is first available;
- no downstream patch, no first-party module, and no command-registry change.

Any claim that these utilities work in Sunshine is unsupported until a native
build exists and criteria 1–22 have been run and recorded.

## Completion gate

This contract is complete when reviewed. Section 6.6 is complete when the
utilities have been exercised on a native pinned build, the commands that route
to them have been registered and dispatch through the single command service,
and the acceptance criteria above have passed on the supported desktop
platforms.
