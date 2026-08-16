# Sunshine OS session restore and profile isolation contract

Status: Stage 1 native Chromium contract  
Pinned upstream: Chromium `152.0.7977.42`

## Decision

Chromium owns browser profiles, browsing sessions, tab restore data, startup
recovery, renderer crash handling, cookies, credentials, permissions, history,
and site storage. Sunshine does not add a parallel session database or copy
profile data into its dashboard, AI context, logs, or cloud services.

This is intentionally a **zero-runtime-patch** contract while native builds are
deferred. Chromium already provides the required primitives. Runtime changes
may be proposed only after native tests demonstrate a product requirement that
cannot be met through Chromium's existing preferences and UI.

## Chromium-owned components

The pinned source must retain these ownership boundaries:

| Responsibility | Chromium source area | Contract |
|---|---|---|
| Current and last browser session | `chrome/browser/sessions/session_service.*` | Chromium records restorable windows and tabs for one regular profile. |
| Restore orchestration | `chrome/browser/sessions/session_restore.*` | Chromium reconstructs windows/tabs and may lazily create background tabs. |
| Startup decision | `chrome/browser/ui/startup/startup_browser_creator_impl.*` | Startup preference and unclean-exit state determine restore/create behavior. |
| Closed tab/window recovery | `components/sessions/` and `TabRestoreService` integrations | Chromium owns recently closed entries and their profile scope. |
| Profile lifecycle and paths | `chrome/browser/profiles/` | Each regular profile has its own persistent profile directory and keyed services. |
| Off-the-record contexts | `Profile`/`BrowserContext` off-the-record implementation | Incognito and Guest data must not be persisted as a regular restorable session. |
| Site data and secrets | Chromium storage, password manager, cookies, permissions, and OS crypt services | Sunshine consumes browser behavior, not raw stores or encryption material. |

## Clean shutdown and startup

1. A normal close must let Chromium finish its native shutdown and session
   bookkeeping. Sunshine must not kill the browser process to simulate Exit.
2. On the next clean launch, Chromium's user-visible **On startup** preference
   is authoritative:
   - open the New Tab page when that is the selected behavior;
   - restore the previous session when the user selected Continue where you
     left off;
   - open configured startup URLs when the user selected them.
3. Sunshine New Tab branding must not convert every startup into a forced
   dashboard navigation and must not overwrite restored active tabs.
4. If session data is absent, corrupt, or empty, startup fails open to one
   usable Sunshine New Tab. It must not loop, repeatedly spawn windows, or
   replace valid current tabs.

## Unclean exit and crash recovery

1. Chromium's exit-type and pending-unclean-exit state are authoritative.
2. After a whole-browser crash, the browser must use Chromium's native crash
   recovery path and recovery UI. Sunshine must not silently classify a crash
   as a clean exit or auto-confirm a recovery choice on the user's behalf.
3. Recovery is best-effort. A malformed entry must not prevent other valid
   windows and tabs from being offered/restored.
4. Restored background tabs may remain lazy/discarded until selected. Sunshine
   must not eagerly activate every renderer, autoplay media, or trigger a login
   storm merely to rebuild visual state.
5. Recovery restores navigation/session state according to Chromium semantics;
   it does not promise replay of transient page memory, unsaved application
   state, uploads, downloads, permission prompts, or completed form submission.
6. Sunshine must never resubmit a non-idempotent request or answer a permission
   prompt merely because a tab is being restored.

## Partial tab or renderer failure

- A renderer crash affects its `WebContents`, not the entire browser session.
- Other windows and tabs remain usable and are not globally reloaded.
- The failed tab uses Chromium's native crashed-tab UI and explicit reload
  action. Sunshine does not continuously auto-reload it.
- Reloading the failed tab retains its owning profile and must not open it in a
  fallback or default profile.
- A crashed tab is not duplicated in the session model. Closing it removes the
  live entry while Chromium's normal recently-closed behavior remains intact.
- A Sunshine dashboard or AI surface failure is treated like a tab/surface
  failure and must not corrupt or delete the browser's session files.

## Profile isolation

### Regular profiles

- Every regular profile has a distinct Chromium-managed profile path and
  profile-keyed services.
- Windows, tabs, session restore, history, cookies, permissions, downloads,
  extensions, passwords, and site storage must resolve through the owning
  `Profile`/`BrowserContext`.
- A restore operation receives the target `Profile`; it must never infer the
  target from the last globally active Sunshine window.
- Creating, renaming, switching, or deleting a profile uses Chromium's native
  profile lifecycle. A display name is not a filesystem identifier or an
  authorization boundary.
- Profile deletion is destructive and must retain Chromium's confirmation and
  shutdown rules. Sunshine must not delete profile directories directly.

### Incognito and Guest

- Incognito and Guest are not additional regular profiles and must not write a
  persistent restorable session into a regular profile.
- Closing the final off-the-record window ends that off-the-record session
  according to Chromium semantics.
- Regular-profile restore must not reveal the URLs, titles, form state, site
  data, or recently closed entries of an off-the-record session.
- Sunshine analytics and AI history must not recreate an off-the-record trail.

## Secret and privacy boundaries

Session restore data is sensitive browsing data even when it is not an
authentication store. URLs, titles, referrers, navigation state, and form state
may reveal secrets.

- Sunshine code must not read or parse Chromium session files directly.
- Cookies, password stores, autofill data, OAuth tokens, encryption keys, and
  OS keychain material are never copied into Sunshine configuration or session
  snapshots.
- AI features receive no ambient access to tabs, restored session contents,
  cookies, credentials, history, or another profile. Any future page sharing
  requires an explicit, scoped user action and a separate privacy contract.
- Logs and crash reports must not include full URLs with query/fragment data,
  page contents, form values, cookies, authorization headers, profile paths
  containing personal identifiers, or raw session records.
- Command-line switches, environment variables, patch files, workflow output,
  and repository documents must not contain user profile data or secrets.
- Profile isolation is not a substitute for OS account isolation or disk
  encryption. Sunshine must not claim that one local OS user is protected from
  another process with equivalent filesystem privileges.
- Sync and account backup are separate features. Local session restore must not
  silently upload session state.

## Deterministic acceptance tests

Native builds must pass the following tests before session restore or profile
isolation is marked complete.

### Clean lifecycle

1. With startup set to New Tab, open two windows and multiple tabs, exit
   normally, relaunch, and verify exactly one usable New Tab—not the old tabs.
2. With Continue where you left off selected, repeat the same setup and verify
   window count, tab order, pinned state, active tab, and navigation entries.
3. With configured startup URLs, verify those URLs open after a clean exit and
   are not replaced by a forced Sunshine dashboard.

### Whole-browser crash

4. Create a known two-window/six-tab fixture, terminate the browser abnormally,
   relaunch, and verify Chromium exposes its recovery behavior without
   Sunshine auto-confirming it.
5. Accept recovery and verify each fixture tab appears once. Corrupt one
   disposable session entry and verify valid entries remain recoverable.
6. Include a tab whose last navigation was a POST and verify recovery does not
   silently resubmit it.

### Partial failure

7. Crash one renderer with Chromium's test facilities. Verify other tabs remain
   interactive, only the failed tab shows crash UI, and it reloads only after
   explicit user action.
8. Crash a Sunshine-owned WebUI surface and verify normal web tabs and the
   profile's next-launch session remain intact.

### Isolation matrix

9. Create profiles A and B with disjoint fixture URLs, cookies, permissions,
   downloads, and recently closed tabs. Relaunch each profile and assert no
   cross-profile value appears in UI or restored state.
10. Crash while both A and B are open. Restore A and verify B's windows are not
    attached to A; then restore B independently.
11. Browse a unique fixture in Incognito and Guest, close the final window,
    restart, and verify it is absent from regular restore, history, recently
    closed UI, Sunshine analytics, and AI history.
12. Delete a disposable profile through native UI and verify another profile's
    path and data are unchanged.

### Secret leakage

13. Use canary values in a URL query, form field, cookie, password entry, and
    authorization header. Exercise clean exit, crash recovery, renderer crash,
    and diagnostic collection; assert prohibited canaries do not appear in
    Sunshine logs, exported configuration, workflow artifacts, or AI requests.
14. Verify local session recovery works with network access disabled, proving
    it does not depend on or trigger a Sunshine cloud upload.

## Upstream-roll gate

Each Chromium revision update must review changes to the source areas above and
rerun the acceptance suite. The roll is blocked if it changes profile scope,
off-the-record persistence, crash recovery consent, session-file ownership, or
secret handling until the contract is explicitly reviewed.

The correct response to an upstream change is to adapt at Chromium's supported
integration boundary. Sunshine must not introduce a shadow profile, session
database, or restore UI to preserve obsolete assumptions.

## Deferred work

- Native macOS and Windows execution of the acceptance suite
- Product copy and visual QA for Chromium's crash recovery surfaces
- Cross-device tab sync and encrypted backup policy
- User-directed export/import of Sunshine-specific settings
- AI page-sharing consent and retention policy

None of these deferred items changes Chromium's Stage 1 ownership of profiles
and browser sessions.
