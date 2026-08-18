# Mouse Gestures — Native Ownership Contract

## Status and scope

This document records the mouse-gesture contract for the Chromium revision
pinned by Sunshine OS: `152.0.7977.42` (see `config/chromium.version`).

This wave is **documentation-only**. It adds no downstream patch, no gesture
recogniser, no settings entry, and no telemetry emitter. Nothing here has been
compiled, run, or observed in a native window. Every threshold below is a
declared starting value to be falsified against a native build, not a measured
result.

Sunshine is a native downstream of open-source Chromium. There is no wrapper
runtime, no injected content script, and no intermediary process between the
pointer device and Chromium's input pipeline. A gesture is therefore an
interpretation layer over events Chromium already routes, never a replacement
for that routing.

## 1. Product boundary

Chromium owns the input pipeline. Sunshine adds recognition of one specific
pointer pattern and the mapping from that pattern to an existing command
identifier. Nothing in the gesture path may originate navigation, alter event
delivery to a renderer, or reimplement a native surface.

| Concern | Authority | Sunshine's part |
|---|---|---|
| Pointer, wheel, and keyboard event capture and hit-testing | Chromium input routing to the correct `RenderWidgetHost` | Observes; never rewrites, reorders, or synthesises events |
| Delivery of mouse events to page content, and a page's ability to handle or cancel them | Chromium / Blink | Yields; a handled event ends gesture interest |
| Context menu construction, position, items, and localisation | Chromium context-menu implementation | May defer one menu for one press; never builds, edits, or reorders a menu |
| Text selection and selection-drag behaviour | Chromium / Blink | Suppresses recognition; never clears or extends a selection |
| Native drag-and-drop, including file drags and link drags | Chromium drag session | Cancels recognition when a drag session starts |
| Navigation, session history, WebContents lifetime | Chromium | Never touched directly; reached only through a command |
| Pointer-lock and fullscreen input capture | Chromium | Suppresses recognition while active |
| Recognition of the press-and-drag pattern | **Sunshine** | Gesture recogniser |
| Mapping a recognised pattern to a command identifier | **Sunshine** | Gesture binding table |
| Gesture trail rendering | **Sunshine** | Browser-chrome overlay only; never composited into page content |
| Gesture settings and gesture telemetry | **Sunshine** | Settings surface, tuning events |

The pipeline is fixed and one-directional:

```text
Pointer input → GestureRecognizer → GestureBinding → CommandService → Chromium command
```

Recognition, binding, and dispatch are three separable stages. A recogniser that
knows a command identifier, or a binding that knows a Chromium type, violates
this contract.

## 2. Non-negotiable invariants

1. A gesture never fires while the user is selecting text, and never as a result
   of a press that lands inside an existing selection.
2. A gesture never fires while a native page control is being operated, and
   never when the page has handled the originating pointer event.
3. A gesture never fires during a native drag session of any kind, including a
   file drag, and the start of a drag session cancels an in-progress gesture.
4. A gesture never fires when context-menu intent is clear. Where intent is
   ambiguous, the context menu wins.
5. A gesture resolves a command identifier and dispatches it through the same
   command service used by the toolbar, the keyboard, and the context menu. It
   must not call Chromium browser internals, navigate a `WebContents`, or
   consult navigation history directly.
6. A gesture is not permitted to reach behaviour that has no command
   identifier. A binding whose command is not registered in
   `first_party/commands.json` is a build failure, not a special case.
7. Command availability is evaluated by the command layer, not by the gesture.
   A recognised gesture whose command is unavailable performs no action and
   raises no error dialog.
8. Cancellation is total and recoverable: no command runs, no navigation
   occurs, no selection changes, the trail is removed, and — except where a
   drag session has taken ownership of the pointer — the press behaves as an
   ordinary press, including showing the context menu it would otherwise have
   shown.
9. At most one command is dispatched per button press. A press that has
   dispatched a command cannot also produce a context menu, and vice versa.
10. Gestures are an accelerator only. No command may be reachable by gesture
    alone (section 8).
11. The context menu must be evaluated on button release. On a platform where
    Chromium raises the context menu on button press, right-button gestures are
    disabled on that platform rather than suppressing a menu the user has
    already been shown.
12. Gesture state is transient. Nothing about a gesture is persisted, and no
    gesture state survives the press that created it.

## 3. Recognition state machine

States are `Idle`, `Tracking`, `Recognised`, and `Cancelled`. `Recognised` and
`Cancelled` are terminal for one press and return to `Idle` on button release.

| From | Event | Condition | To |
|---|---|---|---|
| Idle | Right button pressed | No suppression condition holds (section 3.1) | Tracking |
| Idle | Right button pressed | Any suppression condition holds | Idle (ordinary press; context menu unaffected) |
| Tracking | Pointer moved | Travel and direction satisfy the activation rule | Recognised |
| Tracking | Pointer moved | Activation rule not yet satisfied | Tracking |
| Tracking | Right button released | Travel below the activation distance | Cancelled (`insufficient_distance`) |
| Tracking | Right button released | Travel sufficient, direction not resolvable | Cancelled (`direction_ambiguous`) |
| Tracking | Window or widget focus lost, pointer capture lost, another button pressed | — | Cancelled (`focus_lost`) |
| Tracking | Native drag session started | — | Cancelled (`native_drag_started`) |
| Recognised | Right button released | — | Idle, after one command dispatch |

### 3.1 Suppression conditions

Suppression is evaluated once, at button press. A suppressed press never enters
`Tracking` and is indistinguishable from a press in a build with gestures
disabled.

- Gestures disabled in settings, or the matching binding disabled.
- A text selection is in progress, or the press position lies within the current
  selection.
- The press position resolves to an editable field, a form control, a media
  element, a link, or an image — targets for which Chromium offers
  target-specific context-menu actions. This wave treats all of them as clear
  context-menu intent.
- The page handled or cancelled the originating pointer event.
- A native drag session, pointer lock, or a modal native dialog is active.
- The press did not land in web content: browser chrome, the tab strip,
  extension surfaces, and native menus are excluded.

### 3.2 Activation rule

Let `dx` and `dy` be the signed pointer travel from the press position, in
device-independent pixels.

| Property | Rule |
|---|---|
| Activation distance | `abs(dx) >= D`, where `D` is the user-set activation distance below |
| Direction resolution | `abs(dx) >= 2 * abs(dy)`; otherwise the direction is ambiguous |
| Direction | `dx < 0` is left; `dx > 0` is right |
| Time limit | None. The gesture ends when the button is released or a cancellation condition occurs |
| Re-entry | Once `Recognised`, the gesture does not revert if the pointer returns towards the origin |

`D` is a number of device-independent pixels the user sets directly. It
defaults to **200 px** and accepts any value in **[20, 600]**.

| Property | Value |
|---|---|
| Default `D` | 200 px |
| Accepted range | 20 px – 600 px |
| Out-of-range input | Clamped to the nearest bound; never rejected with an error |

**Why a number and not three named levels.** This contract first specified an
enum — low 48 px, standard 32 px, high 20 px — and the product owner reports
that 32 px was, in practice, uncomfortable to use: at that distance an ordinary
right-click that drifts a few millimetres reads as a gesture, so the menu the
user wanted is replaced by a navigation they did not. The failure is not that
32 px was the wrong constant. It is that the right constant depends on pointer
speed, screen density, and grip, and no three-value enum contains every user's
answer. A direct value moves that judgement to the person holding the mouse.

200 px is the default because it is far enough that no plausible click-drift
reaches it, which is the failure the owner actually hit. It is deliberately
much larger than the old `standard`: a threshold that is too high wastes a
deliberate movement, while one that is too low steals a context menu, and only
the second silently does the wrong thing.

The range bounds exist so the setting cannot make the feature incoherent. Below
20 px a gesture is indistinguishable from a click; above 600 px it cannot be
completed on a small window at all. Both bounds clamp rather than reject,
because a settings field that refuses a number is a worse experience than one
that quietly honours the nearest legal value.

The `2:1` direction ratio and the release-time evaluation are not tunable
without amending this document.

### 3.3 Cancellation reasons

The set is closed. A new reason requires a change to this contract, because each
reason is a telemetry enum value and a tuning signal.

| Reason | Meaning | Recovery |
|---|---|---|
| `insufficient_distance` | The button was released before the activation distance was reached | The deferred context menu is shown at the press position |
| `direction_ambiguous` | Travel was sufficient but no axis dominated | No context menu, no command; the press ends silently |
| `focus_lost` | Window, widget focus, or pointer capture was lost, or a second button was pressed | No context menu, no command |
| `native_drag_started` | Chromium began a drag session during tracking | The drag session owns the pointer and proceeds unaffected |

## 4. Bindings

| Input | Command | Availability owner |
|---|---|---|
| Right button held, drag left | `browser.back` | Command layer: the active tab has a previous navigation entry |
| Right button held, drag right | `browser.forward` | Command layer: the active tab has a forward navigation entry |

That is the complete binding set for this wave. Both commands are Chromium-owned
and already registered, so no registry entry is added here.

Out of scope, explicitly:

- Multi-segment gestures (for example down-then-right), gesture alphabets, and
  user-defined paths. These are Stage 3 or later.
- Vertical and diagonal single-segment gestures.
- Rocker gestures, wheel gestures, and any binding using a button other than the
  right button.
- User-editable bindings. This wave offers enablement per binding only
  (section 6), not remapping.

A future wave that adds a binding must add it to this table, must name an
already-registered command, and must extend section 8 with that command's
non-gesture routes before the binding ships.

## 5. Settings surface

| Key | Type | Default | Effect |
|---|---|---|---|
| `gestures.enabled` | boolean | `true` | Master switch. When `false`, no press enters `Tracking` and no gesture telemetry is recorded |
| `gestures.activation_distance` | integer, device-independent pixels | `200` | The activation distance `D` in section 3.2. Accepts 20–600; a value outside that range is clamped to the nearest bound, not refused |
| `gestures.trail.visible` | boolean | `true` | Whether the recognition trail is drawn. Purely presentational; it does not affect recognition, thresholds, or dispatch |
| `gestures.binding.back.enabled` | boolean | `true` | Enables the drag-left binding |
| `gestures.binding.forward.enabled` | boolean | `true` | Enables the drag-right binding |

Rules:

- Settings are profile-scoped and take effect on the next press; no restart.
- Disabling every binding is equivalent to `gestures.enabled = false` for
  recognition purposes, and must not leave a press behaving unusually.
- The trail is browser-chrome UI. It is never drawn into page content, never
  captured in a page screenshot, and never visible to a web origin.

## 6. Command resolution

- A binding yields a command identifier and nothing else. It carries no
  arguments, no target selection, and no fallback behaviour.
- Dispatch goes through the same command service as every other invocation
  source. The gesture is a source label, not a separate code path.
- If the command's availability predicate is false, nothing happens: no
  navigation, no error dialog, no audible feedback. The attempt is recorded
  (section 7) so that a binding users repeatedly trigger without effect becomes
  visible.
- The gesture layer does not undo, retry, or queue commands.

## 7. Telemetry

Gesture telemetry exists to tune thresholds and to detect false activations. It
is separate from the per-command events already declared in the command
registry; a gesture-dispatched command records its registry event through the
normal dispatch path, and the gesture events below must not be used to count
command executions.

| Event | Recorded when | Payload |
|---|---|---|
| `Sunshine.Gesture.Activated` | A gesture reaches `Recognised` | Binding identity (`back_left` or `forward_right`); bucketed travel distance; bucketed duration |
| `Sunshine.Gesture.Cancelled` | A gesture reaches `Cancelled` | Cancellation reason, from the closed set in section 3.3; bucketed travel distance |
| `Sunshine.Gesture.Unavailable` | A recognised gesture's command was unavailable | Binding identity |
| `Sunshine.Gesture.Reversed` | A gesture-dispatched command is followed, within the reversal window, by its inverse from any invocation source | Binding identity; whether the reversal itself was a gesture |

The reversal window is 2000 ms from dispatch. A reversal is the strongest
available proxy for a false activation: it means the user did not want what the
gesture did. A rising reversal rate is grounds for raising `D`.

Prohibited in every gesture event, without exception:

- page content, selected text, or accessibility text;
- URLs, origins, hostnames, page titles, or filenames;
- raw pointer coordinates, pointer paths, or screen positions;
- any identifier for the tab, workspace, profile, or window.

Suppressed presses (section 3.1) record nothing. A press that never became a
gesture is not gesture data, and recording it would require knowing what the
user pressed on.

## 8. Accessibility

A gesture is an accelerator. It is never the only route to a command, and it is
never the fastest route by so much that the alternatives are decorative.

| Command | Non-gesture routes that must remain present |
|---|---|
| `browser.back` | Toolbar back control; keyboard shortcut; context-menu entry where Chromium provides one |
| `browser.forward` | Toolbar forward control; keyboard shortcut; context-menu entry where Chromium provides one |

Further requirements:

- Disabling gestures must not remove or disable any other route to a command.
- The trail conveys no information that is not otherwise available; nothing
  depends on perceiving it, and it is not the only feedback that a command ran.
- Recognition thresholds must be reachable by users with reduced pointer
  precision. A user-set activation distance serves that need better than a
  fixed enum did, but only if the range reaches far enough down: 20 px is the
  lower bound for this reason, not merely as a nominal floor.
- Gesture recognition must not interfere with assistive-technology pointer
  emulation; where such input is indistinguishable from a drag, the suppression
  conditions in section 3.1 apply unchanged.

## 9. Acceptance criteria

Checkable once a native build exists. Each is written to be falsifiable by
observation, on web content served from a local test server.

`GA-` is the prefix for these criteria, and the ordinals are unchanged:
criterion 9 is `GA-9`, so a citation written before this revision still resolves.
The §2 invariants are numbered separately and are cited as invariants.

1. **GA-1. Ordinary right-click is unchanged.** Right press and release with no
   movement shows the Chromium context menu at the press position, with the
   same items as a build without gestures. No navigation occurs.
2. **GA-2. Back gesture.** Right press, drag left beyond `D`, release: the
   active tab navigates back exactly once, no context menu appears, and the
   resulting history state is identical to using the toolbar back control.
3. **GA-3. Forward gesture.** The mirror of GA-2, with drag right.
4. **GA-4. One outcome per press.** No press produces both a navigation and a
   context menu, and no press produces two navigations.
5. **GA-5. Below threshold.** Right press, drag left by less than `D`, release:
   the context menu appears and no navigation occurs.
6. **GA-6. Ambiguous direction.** Right press, drag diagonally so that
   `abs(dx) < 2 * abs(dy)`, release: no navigation, no context menu.
7. **GA-7. Selection is protected.** With text selected, right-pressing inside
   the selection and dragging left leaves the selection intact, produces no
   navigation, and shows the context menu on release.
8. **GA-8. Selection in progress.** A left-button selection drag is unaffected
   by any concurrent gesture state, and pressing the right button during it
   produces no navigation.
9. **GA-9. Page control.** A right-press-drag beginning on a form control, link,
   image, media element, or editable field produces no navigation.
10. **GA-10. Page-handled events.** On a page that cancels the originating
    pointer event, no gesture is recognised.
11. **GA-11. File drag.** Dragging a file over and into the window is
    unaffected, and a drag session started during tracking cancels the gesture
    with no navigation.
12. **GA-12. Focus loss.** Losing window focus mid-gesture cancels it; releasing
    the button afterwards produces neither navigation nor context menu.
13. **GA-13. Unavailable command.** At the first entry of session history, the
    back gesture produces no navigation, no dialog, and no audible feedback, and
    records exactly one unavailable event.
14. **GA-14. Settings.** With gestures disabled, or with the back binding
    disabled, behaviour is byte-for-byte the ordinary right-click path;
    setting `gestures.activation_distance` changes the measured activation
    distance to that value, and a value outside 20-600 is clamped rather than
    refused (section 3.2).
15. **GA-15. Trail.** Disabling the trail changes nothing except the trail;
    recognition and dispatch are unaffected, and the trail never appears in
    captured page content.
16. **GA-16. No direct internals.** The dispatched command is the same
    identifier the toolbar dispatches, observed through the command layer, not a
    separate navigation call.
17. **GA-17. Telemetry hygiene.** Recorded events contain none of the prohibited
    fields in section 7, and suppressed presses record nothing.
18. **GA-18. Accessibility.** Every command in section 8 remains reachable by
    keyboard and by toolbar with gestures disabled.

## 10. Not verified

Nothing in this document has been executed. Specifically, the following are
open and must not be reported as done:

- No downstream patch exists. No Chromium build was configured, compiled, or
  run, and no gesture code exists in this repository.
- The thresholds in section 3.2 are declared, not measured. No tuning data
  exists because no telemetry emitter exists.
- The suppression list in section 3.1 has not been checked against the pinned
  revision's actual event handling; whether a given target reports its pointer
  event as handled is an empirical question this wave did not ask.
- The platform dependency in invariant 11 — on which platforms Chromium raises
  the context menu on press rather than release — has not been confirmed against
  the pinned source.
- No visual verification of the trail, at any zoom level, theme, or display
  scale, has been performed.
- The acceptance criteria in section 9 have been written, not run.

Until a patch applies to `refs/tags/152.0.7977.42`, a native build compiles, and
the criteria in section 9 pass on that build, this work is reported as a
**contract**, not a browser feature.
