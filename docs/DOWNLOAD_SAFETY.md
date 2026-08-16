# Download Safety — Stage 1 Contract

## Status and scope

This document records the download-safety contract for the Chromium revision
pinned by Sunshine OS: `152.0.7977.42`.

Stage 1 is intentionally **documentation-only** while native Windows builds are
deferred. It does not add a downstream runtime patch, change Chromium danger
classification, or choose the unresolved product policy between warning with a
user override and mandatory blocking.

## Product contract

Sunshine remains a general-purpose browser. Ordinary downloads must continue to
use Chromium's normal download flow. A file must not be classified as risky
merely because it was downloaded, has an unfamiliar extension, or came from a
site Sunshine does not recognize.

When Chromium classifies a download as dangerous, suspicious, insecure, blocked,
or requiring scanning, Sunshine must preserve the corresponding Chromium warning
or review surface. The surface must:

1. identify the downloaded file;
2. explain the Chromium-provided risk or failure state;
3. retain trustworthy provenance from the `DownloadItem`, including the final
   download URL and original URL, rather than reconstructing it from page text;
4. expose only actions permitted by Chromium for that state;
5. record warning display and user action using Chromium's warning-event model;
6. never turn a normal download into an unconditional block through Sunshine
   branding or UI code.

“Provenance” in this stage means trusted download metadata available from
Chromium. It does not mean that the source is safe, that a hostname proves file
authorship, or that Sunshine has independently scanned the file.

## Pinned Chromium behavior we inherit

The following source paths are authoritative for the pinned revision:

| Concern | Chromium source | Inherited behavior |
|---|---|---|
| Download metadata and risk abstraction | [`chrome/browser/download/download_ui_model.h`](https://github.com/chromium/chromium/blob/152.0.7977.42/chrome/browser/download/download_ui_model.h) | Exposes `IsDangerous()`, `IsMalicious()`, `IsInsecure()`, `GetDangerType()`, `GetURL()`, `GetOriginalURL()`, and `HasUserGesture()` to native download UI. |
| Warning/review content and allowed actions | [`chrome/browser/ui/download/download_bubble_security_view_info.cc`](https://github.com/chromium/chromium/blob/152.0.7977.42/chrome/browser/ui/download/download_bubble_security_view_info.cc) | Maps download state and danger type to warning summaries, learn-more behavior, progress, and state-specific actions such as discard, keep, review, or scan. Dangerous and suspicious paths are intentionally not identical. |
| Native download-row presentation | [`chrome/browser/ui/views/download/bubble/download_bubble_row_view.cc`](https://github.com/chromium/chromium/blob/152.0.7977.42/chrome/browser/ui/views/download/bubble/download_bubble_row_view.cc) | Shows file name and status; opens the security subpage when `has_subpage()` is true; routes button presses through `DownloadCommands`; and records that dangerous warnings were displayed. |
| Warning-event semantics | [`chrome/browser/download/download_item_warning_data.h`](https://github.com/chromium/chromium/blob/152.0.7977.42/chrome/browser/download/download_item_warning_data.h) | Distinguishes warning surfaces and actions including shown, proceed, discard, keep, cancel, scan, and learn-more. The comments explicitly distinguish a warning bypass from deletion and from opening another review surface. |
| Command dispatch | [`chrome/browser/download/download_commands.cc`](https://github.com/chromium/chromium/blob/152.0.7977.42/chrome/browser/download/download_commands.cc) | Defers command enablement and execution to `DownloadUIModel`; downstream UI must not bypass those checks. |
| Target determination and platform protection integration | [`chrome/browser/download/chrome_download_manager_delegate.cc`](https://github.com/chromium/chromium/blob/152.0.7977.42/chrome/browser/download/chrome_download_manager_delegate.cc) | Integrates download target determination, insecure-download handling, Safe Browsing build flags, enterprise policy, quarantine, and platform-specific behavior. |

This division is important: Sunshine UI must not create a second, divergent
danger classifier. Chromium owns classification and command eligibility;
Sunshine may later add clearer presentation of provenance to the existing
warning/review surface.

## Neutral warning and review rules

- **Normal:** preserve the standard Chromium flow. Do not add a confirmation
  dialog or silent block.
- **Suspicious or insecure:** show Chromium's warning/review state and its
  enabled actions. Do not upgrade it to “malware” in Sunshine copy.
- **Dangerous or malicious:** preserve Chromium's stronger warning treatment,
  security subpage, and allowed actions.
- **Blocked by policy or terminal failure:** do not offer an override that
  Chromium has disabled.
- **Scanning required or underway:** preserve scan state and do not imply a
  safe result before Chromium reports one.
- **Provenance unavailable or invalid:** display an explicit neutral unknown
  state in a future UI rather than guessing a domain.
- **Redirects:** provenance presentation must distinguish original and final
  URL when they differ; it must not hide the redirect chain behind a single
  unsupported attribution claim.

## Unresolved P0 decision

The product still needs one explicit decision for each Chromium danger category:

- allow only after warning/review and deliberate user confirmation; or
- block with no user override.

No Stage 1 code may select that policy by changing command enablement, executing
`KEEP` automatically, removing an existing override, or introducing a new
blocklist. Until the decision is recorded, Chromium's pinned default behavior is
the baseline.

## Future patch boundary

The smallest acceptable follow-up patch should be presentation-only and should
target the existing native security subpage or download row. It may display a
sanitized origin derived from `DownloadUIModel::GetURL()` and
`GetOriginalURL()` for non-normal states. It must not:

- alter `DownloadDangerType`;
- modify Safe Browsing verdicts;
- enable a disabled `DownloadCommands` action;
- auto-execute keep, discard, open, or scan;
- replace localized Chromium warning text with an unlocalized string;
- send download URLs or file metadata to a Sunshine service.

The implementation must include localized strings and accessibility text. A
runtime patch is not accepted until it applies to the pinned source and a native
build plus UI tests can run.

## Deterministic acceptance tests for the future implementation

Use Chromium test fixtures or a local test server; tests must not depend on a
live reputation service or public website.

1. **Normal file regression**
   - Given a `NOT_DANGEROUS` download, the standard row and standard actions are
     unchanged.
   - No Sunshine warning, review step, or block appears.

2. **Danger classification preservation**
   - Parameterize representative dangerous, suspicious, insecure, blocked, and
     scan-required danger types.
   - Assert the downstream presentation does not mutate `GetDangerType()` and
     does not change `DownloadCommands::IsCommandEnabled()` results.

3. **Security subpage routing**
   - Given a model whose Chromium security info reports `HasSubpage()`, clicking
     the download row opens the security subpage rather than the file.
   - Given a normal model with no subpage, ordinary open behavior remains.

4. **Provenance values**
   - Same original and final HTTPS URL: show one sanitized origin.
   - Redirected URL: expose original and final origins without claiming either
     is the file author.
   - Credentials, path, query, and fragment: never render these as provenance.
   - Invalid, opaque, `data:`, or missing URL: render the localized unknown
     state.
   - Internationalized hostname: use Chromium URL formatting and spoof checks;
     do not hand-roll Unicode conversion.

5. **Action safety**
   - A disabled keep/open/scan action remains absent or disabled.
   - Merely opening or dismissing the warning does not execute any terminal
     action.
   - A user action is passed through `DownloadCommands`, not directly to the
     `DownloadItem`.

6. **Warning telemetry contract**
   - Showing a dangerous warning records `SHOWN` on the correct surface once.
   - Proceed, discard, keep, cancel, scan, and learn-more record their matching
     existing Chromium action without introducing URLs or filenames into the
     event payload.

7. **Accessibility and localization**
   - Provenance is included in the accessible name or description of the
     warning/review content.
   - Labels are localized and remain usable at 200% zoom, narrow width, light
     theme, dark theme, keyboard-only navigation, and screen-reader focus.

8. **Patch and build gate**
   - The complete downstream patch series applies in order to
     `refs/tags/152.0.7977.42`.
   - Native Chromium compilation and the relevant unit/browser/view tests pass.
   - Manual verification confirms normal downloads are not silently blocked.

## Completion gate

Stage 1 is complete when this contract is reviewed. Runtime implementation
remains incomplete until the P0 category policy is decided, a patch is tested
against the pinned Chromium source, and native visual/interaction verification
passes.
