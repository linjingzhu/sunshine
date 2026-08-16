# Sunshine OS permission policy

Status: Stage 1 native Chromium contract  
Pinned upstream: Chromium `152.0.7977.42`

## Decision

Sunshine OS keeps Chromium's native, per-origin permission system and UI. It
does not add a second permission store, replace permission prompts, auto-grant
web origins, or bypass operating-system privacy controls.

This is an intentional **zero-runtime-patch** decision. The pinned Chromium
revision already implements the Stage 1 policy below. A downstream patch that
merely restates those defaults would increase upstream-roll risk without
changing behavior.

## Stage 1 defaults

| Capability | Chromium content setting | Initial default | Sunshine behavior |
|---|---|---:|---|
| Camera | `MEDIASTREAM_CAMERA` | `ASK` | Show Chromium's native origin prompt; remember an explicit user decision according to Chromium semantics. |
| Microphone | `MEDIASTREAM_MIC` | `ASK` | Show Chromium's native origin prompt; remember an explicit user decision according to Chromium semantics. |
| Location | `GEOLOCATION` | `ASK` | Show Chromium's native origin prompt. OS-level denial remains authoritative. |
| Notifications | `NOTIFICATIONS` | `ASK` | Preserve Chromium's native permission UX, including its anti-abuse and quiet-prompt behavior. |
| Advanced clipboard access | `CLIPBOARD_READ_WRITE` | `ASK` | Prompt for advanced Async Clipboard capabilities. Chromium's separately defined sanitized-write behavior is not broadened by Sunshine. |
| Pop-ups and redirects | `POPUPS` | `BLOCK` | Block by default and expose Chromium's normal blocked-popup affordance/site exception flow. |
| Multiple automatic downloads | `AUTOMATIC_DOWNLOADS` | `ASK` | Preserve Chromium's prompt after the initial user-initiated download; do not silently allow batches. |

`ALLOW` and `BLOCK` exceptions remain scoped and stored by Chromium. Sunshine
must not translate an allow decision for one origin into a global allow, nor
share a decision between unrelated origins.

## Security boundaries

- A web page cannot grant itself a permission.
- Sunshine-owned WebUI pages receive no blanket camera, microphone, location,
  notification, clipboard, pop-up, or automatic-download exception.
- Insecure-origin restrictions and secure-context requirements remain intact.
- Operating-system camera, microphone, and location controls remain a second,
  authoritative gate.
- Incognito inheritance and persistence use Chromium's existing
  `ContentSettingsInfo` rules; Sunshine does not create a parallel profile.
- Enterprise policies, if supported later, must remain visible as managed
  policy rather than masquerading as a user choice.
- Permission prompts must remain attributable to the requesting origin. AI or
  assistant surfaces must not click, dismiss, or answer them for the user.

## Why pop-ups are `BLOCK`, not `ASK`

Chromium models pop-ups differently from camera-style permissions. Its safe
default is to block the attempted pop-up and expose a browser-owned affordance
through which the user can allow the site. Sunshine retains that UX rather
than inventing an interruptive prompt.

## Why automatic downloads are `ASK`, not globally denied

Chromium allows the first user-initiated download through its normal download
flow, then asks before a site starts multiple automatic downloads. Setting the
category globally to `BLOCK` would remove useful browser behavior and would
not be equivalent to a default-deny boundary. Sunshine therefore preserves
Chromium's `ASK` state and native batch-download prompt.

## Upstream-roll gate

Every Chromium revision update must verify these registry defaults in
`components/content_settings/core/browser/content_settings_registry.cc`:

```text
GEOLOCATION          ASK
NOTIFICATIONS        ASK
MEDIASTREAM_MIC      ASK
MEDIASTREAM_CAMERA   ASK
AUTOMATIC_DOWNLOADS  ASK
CLIPBOARD_READ_WRITE ASK
POPUPS               BLOCK
```

The roll must also smoke-test the native UI for Allow, Block, dismissal,
stored per-origin exceptions, exception removal in Site settings, and an
OS-level denial for camera or microphone. A changed upstream default blocks
the roll until it is reviewed; it must not be corrected by silently layering a
second Sunshine permission system over Chromium.

## Deferred work

- Native executable and visual prompt testing on macOS and Windows
- Accessibility and keyboard-navigation checks for permission prompts
- Permission-state indicators and revocation from Chromium Site settings
- Download danger classification, file picker, and download shelf/bubble UX
- Product policy for assistant-initiated actions that may cause a permission
  request

These are validation or later product-policy tasks. They do not justify
reimplementing Chromium's permission UI in Stage 1.
