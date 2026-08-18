---
doc_id: adr-0012-gesture-input-contribution-point
version: 1.0.0
canonical_path: docs/decisions/0012-gesture-input-contribution-point.md
updated: 2026-08-18
---

# ADR 0012: Where a gesture attaches, and what that costs

## Status

**Proposal — awaiting product owner decision.** This document answers one
research question — *where in Chromium's input pipeline does a Sunshine gesture
recogniser attach, and what does that cost?* — against the pinned revision
`152.0.7977.42`. It writes no patch and no code. It names two places where
`docs/GESTURE_CONTRACT.md` and the upstream source disagree and lays out the
options for each with their costs; it does not pick between them, because both
are contract amendments and the contract is the owner's.

## Context

`docs/ROADMAP_NATIVE_COMMAND_EXPANSION.md` §3.2 classifies gesture-shaped work
as needing "a deeper browser-core hook," and §5 states what is precisely
missing: a contribution-point design for native browser-process work, in the
shape of ADR 0006 or ADR 0007 but not served by either. ADR 0007's seam is a
`WebUIConfigMap` registration and a resource bundle; it removes upstream
collisions for pages. A gesture recogniser is not a page. It sees no
`chrome://` host, registers no resource, and needs nothing the seam contributes.

`docs/GESTURE_CONTRACT.md` is documentation-only and says so. Its §10 lists,
among the things it did not check, "the platform dependency in invariant 11 —
on which platforms Chromium raises the context menu on press rather than
release — has not been confirmed against the pinned source." That question is
not a detail. Invariant 11 says that where Chromium raises the menu on press,
right-button gestures are **disabled on that platform**, and
`docs/WINDOWS_CHROMIUM_BUILD.md` is the only build this project has. If the
answer had been "press," the feature would have had no platform to ship on.

So this ADR is ordered by stakes: the platform question first, then the attach
point, then what the browser process turns out not to know, then the cost.

Everything below was read from upstream at the pinned tag. Where a claim was
inferred rather than read, it is in NOT VERIFIED and nowhere else.

## 1. The platform question, settled: Windows raises the menu on release

**Chromium raises the web-content context menu on button *release* on Windows,
and on button *press* on macOS and Linux.** The dependency is a single declared
default in
[`third_party/blink/public/common/web_preferences/web_preferences.h`](https://github.com/chromium/chromium/blob/152.0.7977.42/third_party/blink/public/common/web_preferences/web_preferences.h):

```cpp
bool context_menu_on_mouse_up = BUILDFLAG(IS_WIN);
```

and the two branches it selects are in
[`third_party/blink/renderer/core/frame/web_frame_widget_impl.cc`](https://github.com/chromium/chromium/blob/152.0.7977.42/third_party/blink/renderer/core/frame/web_frame_widget_impl.cc).
In `WebFrameWidgetImpl::HandleMouseDown`:

```cpp
  // Dispatch the contextmenu event regardless of if the click was swallowed.
  if (!GetPage()->GetSettings().GetShowContextMenuOnMouseUp()) {
#if BUILDFLAG(IS_MAC)
    ...
#else
    if (event.button == WebMouseEvent::Button::kRight)
      MouseContextMenu(event);
#endif
  }
```

and in `WebFrameWidgetImpl::HandleMouseUp`:

```cpp
  if (GetPage()->GetSettings().GetShowContextMenuOnMouseUp()) {
    // Dispatch the contextmenu event regardless of if the click was swallowed.
    // On Mac/Linux, we handle it on mouse down, not up.
    if (event.button == WebMouseEvent::Button::kRight)
      MouseContextMenu(event);
  }
```

The preference reaches Blink's `Settings` through one line of
`WebViewImpl::ApplyWebPreferences` in
[`third_party/blink/renderer/core/exported/web_view_impl.cc`](https://github.com/chromium/chromium/blob/152.0.7977.42/third_party/blink/renderer/core/exported/web_view_impl.cc):
`settings->SetShowContextMenuOnMouseUp(prefs.context_menu_on_mouse_up);`.
Neither
[`content/browser/renderer_host/render_view_host_impl.cc`](https://github.com/chromium/chromium/blob/152.0.7977.42/content/browser/renderer_host/render_view_host_impl.cc)
nor
[`chrome/browser/chrome_content_browser_client.cc`](https://github.com/chromium/chromium/blob/152.0.7977.42/chrome/browser/chrome_content_browser_client.cc)
contains the field name at all, so nothing between the declared default and
Blink changes it.

**Consequences, stated plainly because this is the finding the task was
weighted on:**

- Invariant 11's disabling clause **does not fire on Windows**. Right-button
  gestures are available on the only platform Sunshine builds for. The feature
  is not blocked.
- Invariant 11's disabling clause **does fire on macOS and Linux**, and
  `docs/CHROMIUM_MACOS_BUILD.md` means macOS is not hypothetical. A Sunshine
  gesture recogniser is a Windows-only capability until either the contract
  amends invariant 11 or somebody designs deferral against a menu that has
  already been raised. This ADR does not design that; §6 explains why the
  attempt is disproportionate.
- The §3.3 recovery "the deferred context menu is shown at the press position"
  is, on Windows, **not a deferral at all**. Nothing was raised at press, so a
  gesture cancelled with `insufficient_distance` needs no restoration
  machinery: Blink fires `contextmenu` on the release that ended it, and
  Sunshine simply does not suppress. Invariant 8's "including showing the
  context menu it would otherwise have shown" is satisfied by inaction, which
  is the strongest form of satisfying it. The word "deferred" in §3.3 describes
  a mechanism that Windows does not require, and on macOS/Linux describes one
  that invariant 11 has already ruled out. It is accurate about neither.

What *is* needed on Windows is the mirror: **suppression**. Blink dispatches
`contextmenu` on right-button release unconditionally — the comment above the
branch says "regardless of if the click was swallowed" — so a press that
dispatched a command would also raise a menu, and invariant 9 forbids that.
Section 3 names the supported API for suppressing it without building one.

## 2. The attach point

### 2.1 What the pipeline actually is

The path an OS mouse event takes to the renderer, at the pinned tag:

```text
aura window target
  → RenderWidgetHostViewEventHandler::OnMouseEvent          (content/browser, internal)
  → input::RenderWidgetHostInputEventRouter::RouteMouseEvent (components/input, internal)
      hit-tests, picks the target widget
  → RenderWidgetHostImpl::ForwardMouseEventWithLatencyInfo  (content/browser, internal)
      runs MouseEventCallbacks; any true returns early
  → input::RenderInputRouter::DispatchInputEventWithLatencyInfo
      → OnInputDispatchedToRendererResult → InputEventObserver::OnInputEvent
  → InputRouterImpl::SendMouseEvent → renderer
  ... later, asynchronously ...
  → RenderInputRouter ack path → InputEventObserver::OnInputEventAck
```

Three points in that chain matter to `docs/GESTURE_CONTRACT.md`.

**Routing happens before forwarding.** In
[`content/browser/renderer_host/render_widget_host_view_event_handler.cc`](https://github.com/chromium/chromium/blob/152.0.7977.42/content/browser/renderer_host/render_widget_host_view_event_handler.cc)
the view forwards to the router with itself as *root*:

```cpp
      if (ShouldRouteEvents()) {
        host_->delegate()->GetInputEventRouter()->RouteMouseEvent(
            host_view_, &mouse_event, *event->latency());
      } else {
        ProcessMouseEvent(mouse_event, *event->latency());
      }
```

and `input::RenderWidgetHostInputEventRouter::RouteMouseEvent` hit-tests to the
widget that owns the pixel. Everything downstream — including every observer
hook Sunshine can attach — therefore runs on the **target** widget, not the root
one. A recogniser attached only to the primary main frame's
`RenderWidgetHost` does not see a press that lands on a cross-origin iframe.
This is a real gap, not a theoretical one: an ad frame is exactly where a user's
right-drag lands by accident.

**The renderer's verdict arrives later, and out of band.** `OnInputEvent` fires
in the browser's forwarding call stack; `OnInputEventAck` carries
`blink::mojom::InputEventResultState` and arrives when the renderer replies.
Invariant 2 ("never when the page has handled the originating pointer event")
therefore has to be evaluated against a fact that may not have arrived yet at
the moment the gesture is decided. §4 takes this up.

**Consumption is possible and Sunshine must decline it.** `ForwardMouseEvent`
runs registered callbacks first, and a `true` return causes an early `return`
before dispatch. §1 of the contract assigns Sunshine "Observes; never rewrites,
reorders, or synthesises events," and swallowing a right-button release would
also mean the page never sees `mouseup`/`pointerup` for a press it did see —
leaving Blink's own pressed-button state inconsistent, which is a page-visible
defect and not Sunshine's to introduce.

### 2.2 The candidates, and which are supported embedder surface

| Symbol | Header | Public? | Verdict |
|---|---|---|---|
| `RenderWidgetHost::AddInputEventObserver` / `InputEventObserver::OnInputEvent`, `OnInputEventAck` | `content/public/browser/render_widget_host.h` | **yes** | **the attach point** |
| `RenderWidgetHost::AddMouseEventCallback` | `content/public/browser/render_widget_host.h` | **yes** | can consume; deliberately not used |
| `WebContentsDelegate::HandleContextMenu` | `content/public/browser/web_contents_delegate.h` | **yes** | the suppression point (§3) |
| `WebContentsDelegate::ContentsMouseEvent` | `content/public/browser/web_contents_delegate.h` | **yes** | `void`; no renderer verdict; supplement only |
| `WebContentsObserver::RenderFrameCreated`, `RenderFrameHostChanged` | `content/public/browser/web_contents_observer.h` | **yes** | attach/re-attach lifetime |
| `RenderWidgetHostView::GetSelectedText` | `content/public/browser/render_widget_host_view.h` | **yes** | partial answer to §3.1's selection rule |
| `RenderWidgetHostViewBase` | `content/browser/renderer_host/render_widget_host_view_base.h` | no | internal; not needed |
| `input::RenderWidgetHostInputEventRouter` | `components/input/render_widget_host_input_event_router.h` | no (`COMPONENT_EXPORT(INPUT)`) | internal; not needed |
| `input::RenderInputRouterDelegate` | `components/input/render_input_router_delegate.h` | no | internal; not needed |
| `chrome/browser/ui/views/` mouse handling (`ContentsWebView`, `views::View::OnMouseEvent`) | — | chrome-internal | sees browser chrome, not web content |

**The recommended attach point is `RenderWidgetHost::InputEventObserver`**, on
every `RenderWidgetHost` a tab owns, added and removed across frame swaps
through `WebContentsObserver`. Its declaration, quoted from
[`content/public/browser/render_widget_host.h`](https://github.com/chromium/chromium/blob/152.0.7977.42/content/public/browser/render_widget_host.h):

```cpp
  // Observer for WebInputEvents.
  class InputEventObserver {
   public:
    using InputEventSource = input::InputEventSource;
    virtual ~InputEventObserver() = default;

    // Called when an input event is received. `source` indicates whether the
    // event was received from the browser or Viz process.
    virtual void OnInputEvent(const RenderWidgetHost& host,
                              const blink::WebInputEvent& event,
                              InputEventSource source) {}
    virtual void OnInputEventAck(const RenderWidgetHost&,
                                 blink::mojom::InputEventResultSource source,
                                 blink::mojom::InputEventResultState state,
                                 const blink::WebInputEvent&) {}
    ...
  };

  // Add/remove an input event observer.
  virtual void AddInputEventObserver(InputEventObserver* observer) = 0;
  virtual void RemoveInputEventObserver(InputEventObserver* observer) = 0;
```

It is chosen over `AddMouseEventCallback` for one reason and it is the contract's
reason, not an aesthetic one: `MouseEventCallback` is
`base::RepeatingCallback<bool(const blink::WebMouseEvent&)>` and its whole
purpose is to answer "should this event stop here." A recogniser that holds that
power has to be trusted never to use it, whereas an observer cannot use it at
all. `docs/GESTURE_CONTRACT.md` §1 assigns delivery to Chromium; the API that
cannot alter delivery is the API that matches. `InputEventObserver` is also the
only one of the two that carries `OnInputEventAck`, which invariant 2 requires
regardless.

Chromium's own embedder code shows both uses.
[`chrome/browser/safe_browsing/user_interaction_observer.cc`](https://github.com/chromium/chromium/blob/152.0.7977.42/chrome/browser/safe_browsing/user_interaction_observer.cc)
takes the callback and says why in a comment:

```cpp
  // Pass a callback to the RenderWidgetHost instead of implementing
  // WebContentsObserver::DidGetUserInteraction(). The reason for this is that
  // RenderWidgetHost handles keyboard events earlier and the callback can
  // indicate that it wants the key press to be ignored.
  // (DidGetUserInteraction() can only observe and not cancel the event.)
```

It wants to cancel. Sunshine does not, and the same file is the precedent for
the lifetime handling either shape needs — it re-attaches in
`RenderFrameHostChanged` and detaches in `WebContentsDestroyed`. It also
attaches to `GetPrimaryMainFrame()->GetRenderWidgetHost()` only, which is the
subframe gap of §2.1 present in shipping Chromium code.

## 3. Does a supported embedder API exist? Yes — but not the one to look for

**There is no `PreHandleMouseEvent`.** `content::WebContentsDelegate` at the
pinned tag offers `PreHandleKeyboardEvent`, `HandleKeyboardEvent` and
`PreHandleGestureEvent`, and the last takes a `blink::WebGestureEvent` — a
touch-derived gesture, produced after the touches have been through the
renderer, per its own comment. Nothing on that interface is a mouse
pre-handler. The only mouse member is:

```cpp
  // Notification that a mouse `event` was dispatched to the WebContents's view.
  virtual void ContentsMouseEvent(WebContents* source, const ui::Event& event) {
  }
```

— `void`, therefore incapable of expressing a decision, and carrying a
`ui::Event` rather than the blink event the rest of the pipeline reasons about.
`Browser` already overrides it. It is a supplement, not an attach point.

**So the answer is yes, assembled from three public pieces rather than one.**
`AddInputEventObserver` sees the events and the renderer's verdict;
`WebContentsObserver` supplies the lifetime; `HandleContextMenu` supplies
suppression. All three are in `content/public/`, which is the supported
embedder surface ADR 0002 cares about. **No `content/browser/` or
`components/input/` internal header is required by this design.** That is the
load-bearing result of this ADR, and it is why the file count in §6 is as low
as it is.

### 3.1 Suppression, without building a menu

`docs/GESTURE_CONTRACT.md` §1 forbids Sunshine building, editing, or reordering
a context menu. The suppression point does not require any of that. In
[`content/browser/web_contents/web_contents_impl.cc`](https://github.com/chromium/chromium/blob/152.0.7977.42/content/browser/web_contents/web_contents_impl.cc):

```cpp
  // Allow WebContentsDelegates to handle the context menu operation first.
  if (delegate_ &&
      delegate_->HandleContextMenu(render_frame_host, context_menu_params)) {
    return;
  }

  render_view_host_delegate_view_->ShowContextMenu(render_frame_host,
                                                   context_menu_params);
```

Returning `true` means the menu is never built. Chromium's own menu
construction — `ChromeWebContentsViewDelegateViews::ShowContextMenu` and its
`BuildMenuAsync` — is not reached, not subclassed, and not touched. Suppression
is a `return true`; permission is a `return false`. The default in
[`content/public/browser/web_contents_delegate.cc`](https://github.com/chromium/chromium/blob/152.0.7977.42/content/public/browser/web_contents_delegate.cc)
is `return false`, and `Browser` does not override it today, so the override is
additive rather than a change of behaviour for any existing path.

The ordering works out, and it works out because of §1's finding. On Windows the
menu request originates in Blink's `HandleMouseUp`, so it can only reach
`HandleContextMenu` *after* the browser forwarded that release — which is when
the recogniser already decided. Sunshine never has to answer "should this menu
appear" before it knows. The decision is a single boolean read of transient
per-press state, which invariant 12 already requires to exist and to die with
the press.

## 4. What the browser process does not know at press time

This is the second finding, and unlike §1 it goes against the contract.

**§3.1 states "Suppression is evaluated once, at button press," and most of its
list is not evaluable there.** The suppression conditions and what the browser
process can actually answer at `kMouseDown`:

| §3.1 condition | Browser-side answer at press |
|---|---|
| Gestures or the binding disabled in settings | yes — a `PrefService` read |
| Press did not land in web content | yes — the event reached a web-content `RenderWidgetHost` at all |
| Pointer lock active | yes — `WebContentsDelegate::RequestPointerLock` / `LostPointerLock` are observable |
| Native drag session active | partly — `PreHandleDragUpdate`, `PreHandleDragExit`, `HandleDragEnded` exist on the delegate; see NOT VERIFIED |
| A text selection is in progress | partly — `RenderWidgetHostView::GetSelectedText()` says whether one exists |
| The press position lies within the selection | **no** — no public selection geometry was found |
| Press resolves to a link, image, media element, form control, editable field | **no** — the browser process does not hit-test into the page |
| The page handled or cancelled the originating pointer event | **not yet** — the `kMouseDown` ack has not necessarily arrived |

The last two rows are the problem. The browser process holds no DOM. The one
place it is handed a description of what a press landed on is
`ContextMenuParams`, and on Windows that arrives at release. Its base,
[`blink::UntrustworthyContextMenuParams`](https://github.com/chromium/chromium/blob/152.0.7977.42/third_party/blink/public/common/context_menu_data/untrustworthy_context_menu_params.h),
carries exactly the fields §3.1 enumerates — `media_type`, `link_url`,
`src_url`, `selection_text`, `is_editable`, `form_control_type`, `x`, `y`, and
`source_type` — and `content::ContextMenuParams` adds `page_url`, `frame_url`,
`frame_origin` and `is_subframe`, with a security note stating that
`RenderFrameHostImpl` validates and sanitises the untrustworthy half before the
browser sees it.

Two ways out. Both are contract amendments; neither is chosen here.

**Option A — evaluate suppression at release.** Tracking starts on any
right-button press in web content; the target-shaped conditions are evaluated
when `HandleContextMenu` delivers `ContextMenuParams`, before deciding whether
to suppress or dispatch. Cost: §3.1's "evaluated once, at button press" becomes
"evaluated at press for what is knowable there, and at release for what is not,"
and its promise that a suppressed press is "indistinguishable from a press in a
build with gestures disabled" weakens to *observably* indistinguishable — the
recogniser did run, it just produced nothing. The one user-visible leak is the
trail (§5): a press over a link would draw one before turning out to be
suppressed. That is a presentational defect with a presentational fix (do not
draw until the outcome is decided, or accept it), and §5 already declares the
trail purely presentational. Behaviour under GA-1, GA-5, GA-7 and GA-9 is
unchanged, because all four are stated as outcomes at release.

**Option B — keep press-time evaluation, narrow §3.1.** Drop the conditions the
browser cannot answer at press and say so in the contract. Cost: GA-9 becomes
unenforceable as written — a right-drag beginning on a link would be recognised
and would navigate — which is the failure the activation-distance rewrite in
§3.2 was already reacting to, arriving by a different route. This is the cheaper
code and the worse product.

**Recommendation: Option A.** It costs a sentence in §3.1 and preserves every
acceptance criterion; Option B costs a sentence in §3.1 and gives up GA-9. But
§3.1 is contract text and this ADR does not edit it.

Invariant 2's "the page has handled the originating pointer event" is the same
shape and lands the same way. `OnInputEventAck` gives
`blink::mojom::InputEventResultState` for the press; it arrives asynchronously,
and a busy main thread can delay it past the release. Under Option A the
recogniser can wait for it, because it is not deciding anything until release
anyway. Under Option B it would have to guess. This is a second, independent
argument for A.

One security note, cited rather than invented: everything in `ContextMenuParams`
originates in a renderer. SEC-3 says Sunshine treats renderer-supplied data as
untrusted input, never as an authorisation, an identity, or a path. A gesture
uses these fields only to *refuse* to act, never to widen what it does, which is
the direction SEC-3 permits. No gesture path reads a URL, and §7's prohibition
list already forbids one reaching telemetry.

## 5. The pref

`docs/GESTURE_CONTRACT.md` §5 declares five profile-scoped keys —
`gestures.enabled`, `gestures.activation_distance`, `gestures.trail.visible`,
`gestures.binding.back.enabled`, `gestures.binding.forward.enabled`. Chromium's
`PrefService` is the correct and only carrier: profile-scoped, no restart, which
is exactly §5's stated rule.

The registration function is `RegisterProfilePrefs` in
[`chrome/browser/prefs/browser_prefs.cc`](https://github.com/chromium/chromium/blob/152.0.7977.42/chrome/browser/prefs/browser_prefs.cc):

```cpp
void RegisterProfilePrefs(user_prefs::PrefRegistrySyncable* registry,
                          const std::string& locale) {
  TRACE_EVENT0("browser", "chrome::RegisterProfilePrefs");
  // User prefs. Please keep this list alphabetized.
  AccessibilityLabelsService::RegisterProfilePrefs(registry);
  ...
```

It is a list of one-line calls into other components, alphabetised. The shape a
Sunshine addition takes is therefore already fixed by the file: one call to a
Sunshine-owned `RegisterProfilePrefs(registry)`, with every key name, default and
range living in a Sunshine-owned file. §3.2's clamp — 20 to 600, clamped never
refused — is a read-side clamp in the Sunshine accessor, not a registry
constraint, because a pref set out of range by policy or by hand must still
produce a working browser rather than a refused value.

This is the cheapest of the seven edits in §6: additive, one line, in a function
whose whole content is such lines, with a conflict surface of the two
alphabetical neighbours.

## 6. Cost across upstream rolls

**Seven upstream files, for recognition, dispatch, prefs and telemetry.**

| Upstream file | Edit | Kind | Roll exposure |
|---|---|---|---|
| `chrome/browser/ui/tab_helpers.cc` | one call in `TabHelpers::AttachTabHelpers` | additive line in a list | low — appending to a long sequence of `CreateForWebContents` calls |
| `chrome/browser/ui/BUILD.gn` | one `deps` entry on a Sunshine-owned target | additive line | low |
| `chrome/browser/prefs/browser_prefs.cc` | one call in `RegisterProfilePrefs` | additive line in a list | low |
| `chrome/browser/ui/browser.h` | declare `HandleContextMenu` override | new member in an existing override block | **medium** — `Browser` is heavily edited |
| `chrome/browser/ui/browser.cc` | define it, delegating to the Sunshine helper | new method | **medium** — same |
| `tools/metrics/histograms/metadata/<area>/histograms.xml` | the four §7 histograms | additive | low, but presubmit-gated |
| `tools/metrics/histograms/enums.xml` | the §3.3 cancellation-reason enum | additive, append-only by upstream rule | low |

Everything else — the recogniser, the binding table, the pref accessor, the
command dispatch — lives in files Sunshine creates under
`chrome/browser/ui/sunshine/gestures/`, which upstream does not have and cannot
conflict with. That is the same argument ADR 0007 used to narrow
`scripts/patch_manifest.py`'s exclusivity rule to upstream paths, and it applies
here unchanged; no further narrowing is needed.

**Not counted, because not designed here:** the recognition trail (§5,
`gestures.trail.visible`) and the settings UI for the §5 keys. The trail is
browser-chrome UI that must never composite into page content, which is a
views-layer question about the browser window, not about the input pipeline;
the settings UI is a surface question ADR 0007's seam may or may not serve.
Both are separable — recognition and dispatch are testable without either — and
counting them here would be inventing a number for work this ADR did not do.

### Comparison with ADR 0007

The counts match at seven and the comparison is still not flattering to a naive
reading, in both directions.

ADR 0007's seven were `resource_ids.spec`, `chrome_paks.gni`,
`webui_url_constants.h`/`.cc`, `chrome_web_ui_configs.cc` and two `BUILD.gn`s —
and the ADR's own "What was actually built" section records that only three of
them became generic, leaving a second surface costing four upstream edits rather
than the zero its fallback predicted. The seven were expensive because they
recur: every new surface met them again.

The gesture seven are a different shape. Five of them are one-line additive
entries into functions and files that are, structurally, lists — and a second
gesture binding costs **none** of them, because §4's binding table is Sunshine
data, not an upstream registration. There is no per-binding resource id, no
per-binding grd, no per-binding host constant. The marginal cost of the second
gesture is zero upstream files without needing a seam to make it so.

The honest counterweight, and it is real: `chrome/browser/ui/browser.h` and
`chrome/browser/ui/browser.cc` are worse rebase targets than any of ADR 0007's seven except
`resource_ids.spec`. An override added to `Browser` sits in a class upstream
edits constantly. Two mitigations, both available and neither free: keep the
override body to a single delegated call so a rebase conflict is resolved by
re-placing one line; or move suppression to
`ChromeWebContentsViewDelegateViews::ShowContextMenu`, which is a quieter file
but is chrome-internal view plumbing rather than the `content/public/`-blessed
delegate hook, trading roll risk for correctness risk. The first is
recommended.

What breaks at a roll, ranked:

1. **A signature change to `InputEventObserver`.** It is `content/public/`, so
   upstream changes it with the compiler's help across all embedders, and the
   break is a compile error naming the line. Recoverable in an afternoon.
2. **`Browser` gaining or losing members around the override.** Ordinary
   three-way merge noise; the failure mode is a conflict, not silence.
3. **The routing shape changing.** `components/input/` was carved out of
   `content/browser/renderer_host/` recently enough that its files still carry
   2024 and 2025 copyright headers. This design touches none of it, which is
   precisely why a churn there costs Sunshine nothing.
4. **`context_menu_on_mouse_up` changing meaning or going away.** This is the
   one that fails quietly: a right-drag would start producing a menu *and* a
   navigation with no compile error anywhere. GA-4 is the criterion that
   catches it, and it needs a running browser to run. That argues for GA-4
   being in the first runtime-verification pass after every roll, not for any
   change to this design.

## 7. What this ADR does not decide

Two owner calls, both contract amendments to `docs/GESTURE_CONTRACT.md`:

1. **§3.1's evaluation point.** Option A (evaluate the target-shaped conditions
   at release, from `ContextMenuParams`) or Option B (narrow §3.1 to what the
   browser knows at press, losing GA-9). §4 recommends A and does not choose.
2. **What §3.3 and invariant 11 should say now that §1's finding is in.** The
   word "deferred" describes a mechanism Windows does not need and macOS/Linux
   are not allowed to use. Rewording is not a behaviour change on Windows; it
   is a change to what the contract claims about itself, and the contract's
   author should make it.

Neither is blocking. A Windows-only recogniser built to Option A satisfies every
§9 criterion as written; the amendments make the document agree with the build
rather than permitting it.

## NOT VERIFIED

Nothing here has been compiled, run, or observed. Beyond that, specifically:

- **Nothing was built.** No patch exists, no source file was written, and no
  Chromium build was configured. `docs/GESTURE_CONTRACT.md` §10 remains
  accurate in full except for the platform dependency, which §1 above closes
  from source and which that contract is not edited by this ADR to record.
- **The seven-file count is a design estimate, not a measurement.** It was
  derived by reading each named upstream file and confirming the function or
  target that would receive the edit exists at the pinned tag. It has not been
  produced by applying a patch, and `scripts/patch_manifest.py` has not been run
  against a series containing one.
- **Whether `WebContentsDelegate::PreHandleDragUpdate` / `PreHandleDragExit` /
  `HandleDragEnded` cover a drag session the *page* initiates** — as opposed to
  an external drag entering the window — was not established. Their comment in
  `web_contents_delegate.h` reads "Allows delegates to handle mouse drag events
  before sending to the renderer," which does not settle it. Invariant 3 and the
  `native_drag_started` cancellation reason depend on the answer.
- **No public API for selection *geometry* was found**, so §3.1's "the press
  position lies within the current selection" has no browser-side answer that
  was read. `RenderWidgetHostView::GetSelectedText()` answers only whether a
  selection exists. Whether `ContextMenuParams::selection_text` under Option A
  is a sufficient substitute is a product judgement nobody has made.
- **Aura event targeting for `WebContentsViewAura::OnMouseEvent`** — whether it
  observes every web-content mouse event or only those the
  `RenderWidgetHostViewAura` child window does not take — was not traced. The
  §2.2 table records `ContentsMouseEvent` as a supplement on that basis and
  nothing in the recommended design depends on it.
- **The subframe gap is described, not measured.** That routing selects the
  target widget was read from
  `render_widget_host_view_event_handler.cc`; that a main-frame-only observer
  consequently misses an OOPIF-targeted press follows from it, but was not
  confirmed by observation, and how often a real right-drag begins over a
  cross-origin frame is unknown.
- **The `tools/metrics/` edits were not opened.** `docs/TELEMETRY_CONTRACT.md`
  §5 names the requirements and the presubmit at
  `tools/metrics/histograms/PRESUBMIT.py`; the specific `metadata/<area>/`
  directory a `Sunshine.Gesture.*` family belongs in was not chosen, and the
  P3 in that contract's own open list — whether §7 keeps
  `Sunshine.Gesture.Reversed` at all — is unresolved and would change the
  histogram set.
- **`context_menu_on_mouse_up` was checked against the two places that compute
  web preferences** (`render_view_host_impl.cc` and
  `chrome_content_browser_client.cc`, neither of which contains the field) and
  against its declaration and its single application site. An exhaustive search
  of every override path — enterprise policy, feature flags, WebUI-specific
  preference overrides — was not performed.
- **The trail and the settings surface are unexamined**, and §6 excludes them
  from the count for that reason rather than because they are free.
