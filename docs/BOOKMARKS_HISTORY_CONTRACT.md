# Bookmarks and History — Native Persistence Contract

## Status and scope

This contract applies to Sunshine OS on the pinned Chromium revision
`152.0.7977.42`. It defines the native ownership, persistence, privacy, and
acceptance requirements for bookmarks, global browsing history, per-tab
navigation history, and recently closed tab restoration.

Sunshine must use Chromium's profile-keyed services and storage. It must not
create a second Sunshine bookmarks database, history database, visit counter,
favicon store, or recently-closed store.

## Four related but distinct models

| User concept | Native owner | Lifetime and purpose |
|---|---|---|
| Back/forward within one tab | `content::NavigationController` owned by the tab's primary `WebContents` | Session history for that tab. It drives back and forward navigation; it is not the global history database. |
| Global browsing history | `history::HistoryService` and `HistoryBackend`, profile-keyed through `HistoryServiceFactory` | Records visited URLs, visit times, titles, favicons, and related history data in the profile history database. Supports search and deletion across tabs and restarts. |
| Bookmarks | `bookmarks::BookmarkModel`, profile-keyed through `BookmarkModelFactory`, persisted by `BookmarkStorage` | User-curated URL and folder tree. Supports local-or-syncable and, when available, account bookmark roots. |
| Recently closed tabs/windows | `sessions::TabRestoreService` | Reopen-closed-tab/window state. This is separate from both a tab's current back/forward list and global visit history. |

Deleting global history must not be implemented by editing a live tab's
`NavigationController`. Closing a tab must not delete its visits from global
history. Bookmarking a URL must not fabricate a history visit. Reopening a
closed tab must use the native tab-restore/session service rather than guessing
from the most recent history row.

## Pinned Chromium ownership and storage

The following pinned source paths are the implementation authority:

| Concern | Chromium source | Contract evidence |
|---|---|---|
| Per-tab session history | [`content/public/browser/navigation_controller.h`](https://github.com/chromium/chromium/blob/152.0.7977.42/content/public/browser/navigation_controller.h) | Chromium describes the primary `NavigationController` as the user-visible back-forward list associated with a `WebContents`. |
| History service construction and profile path | [`chrome/browser/history/history_service_factory.cc`](https://github.com/chromium/chromium/blob/152.0.7977.42/chrome/browser/history/history_service_factory.cc) | Constructs one profile-keyed `HistoryService` and initializes it with database parameters derived from the browser context path. Access respects the preference disabling saved browser history. |
| History API | [`components/history/core/browser/history_service.h`](https://github.com/chromium/chromium/blob/152.0.7977.42/components/history/core/browser/history_service.h) | Defines the service that records page titles, visit times, favicons, and downloads, and owns query and deletion operations. `Init()` receives the directory used to store history files. |
| History persistence backend | [`components/history/core/browser/history_backend.cc`](https://github.com/chromium/chromium/blob/152.0.7977.42/components/history/core/browser/history_backend.cc) | Owns the history database components for URLs, visits, downloads, visited links, and most-visited segments. The backend guards against two instances using the same storage path concurrently. |
| Bookmark service construction | [`chrome/browser/bookmarks/bookmark_model_factory.cc`](https://github.com/chromium/chromium/blob/152.0.7977.42/chrome/browser/bookmarks/bookmark_model_factory.cc) | Creates the profile-keyed `BookmarkModel`, loads it from `profile->GetPath()`, and connects native undo and sync services. |
| Bookmark CRUD model | [`components/bookmarks/browser/bookmark_model.h`](https://github.com/chromium/chromium/blob/152.0.7977.42/components/bookmarks/browser/bookmark_model.h) | Owns permanent roots, URL/folder nodes, mutation, lookup, ordering, observation, and undo-facing behavior. It distinguishes local-or-syncable roots from optional account roots. |
| Bookmark serialization | [`components/bookmarks/browser/bookmark_storage.cc`](https://github.com/chromium/chromium/blob/152.0.7977.42/components/bookmarks/browser/bookmark_storage.cc) | Serializes the native bookmark model, writes profile storage, and maintains a startup backup for local-or-syncable bookmarks. |
| Recently closed restoration | [`chrome/browser/sessions/tab_restore_service_factory.cc`](https://github.com/chromium/chromium/blob/152.0.7977.42/chrome/browser/sessions/tab_restore_service_factory.cc) | Creates the profile-keyed native `TabRestoreService`; construction explicitly rejects off-the-record profiles. |

The exact on-disk representation is a Chromium implementation detail. Sunshine
must address data through native services, not open, parse, mutate, or lock the
profile files directly. This preserves migrations, atomic writes, backups,
encryption hooks, sync metadata, observers, and undo behavior.

## Product behavior

### Bookmarks

- Create a bookmark for the current canonical URL with an editable title and a
  chosen native bookmark folder.
- Read and render the native tree without flattening folders or merging local
  and account roots into an indistinguishable store.
- Update title, URL, parent folder, and position through `BookmarkModel` APIs.
- Delete through the native model, preserving Chromium undo behavior where the
  surface supports it.
- Search the native model by title and URL. Results must identify their folder
  context and storage scope when ambiguity matters.
- Reopening a bookmark performs a normal navigation. It does not mark the URL
  visited until Chromium's normal navigation/history pipeline records a visit.
- Bookmark state and edits must survive a clean browser restart in the same
  regular profile.

### Global history

- Query `HistoryService` asynchronously for visited URLs using Chromium's
  native matching, time range, ordering, and result limits.
- A result represents recorded visits, not a bookmark and not merely an entry
  that remains in a currently open tab's back/forward list.
- Opening a history result performs a normal navigation in the selected tab or
  a new tab according to the user's command.
- Delete one selected URL/visit scope through the native history deletion API.
- Clear a chosen time range through the native browsing-data/history path. Do
  not emulate range deletion by repeatedly editing visible search results.
- Deletion and clearing must update observers and all native history surfaces;
  no Sunshine cache may resurrect removed records.
- History written in a regular profile must survive a clean browser restart
  unless it was deleted, expired, disabled by policy/preferences, or removed by
  the user through another native Chromium surface.

### Tab navigation and reopen

- Back and forward use the active tab's primary `NavigationController`.
- Creating or switching tabs never substitutes another tab's navigation list.
- Reload does not create a Sunshine history record; Chromium determines visit
  semantics.
- Reopen closed tab/window uses `TabRestoreService`, retaining the native tab
  navigation stack where Chromium has preserved it.
- “Recently visited” and “recently closed” must remain separate labels and data
  sources in the UI.

## Privacy and profile boundaries

### Regular profiles

- Every read and mutation is scoped to the active `Profile`/browser context.
- Never mix results, node identifiers, service pointers, or caches between
  profiles.
- Managed preferences and service availability are authoritative. If saving
  history is disabled, Sunshine must not recreate it elsewhere.

### Incognito / off-the-record

- Incognito navigation must not be written into the regular profile's global
  history by Sunshine.
- Sunshine must not create a private-history fallback, analytics log, recent
  URL list, search index, or crash-recovery database containing incognito
  visits.
- Recently closed persistence must not be added for off-the-record profiles;
  the pinned native tab-restore factory explicitly constructs only for original
  profiles.
- Bookmark commands in an incognito window, if exposed by native Chromium, must
  use the appropriate regular-profile bookmark service and clearly follow
  Chromium's behavior. Sunshine must not silently establish a separate
  incognito bookmark store.
- Closing the last incognito window must leave no Sunshine-owned copy of its
  URLs, titles, queries, thumbnails, or navigation stacks.

### Guest and managed contexts

- Guest behavior follows Chromium's selected profile service routing and
  enterprise policy. Sunshine must not infer persistence from UI appearance.
- Account bookmark roots are optional. The UI must tolerate them being absent
  and must not copy account bookmarks into local storage to compensate.
- Sync is not required for local persistence. When sync is enabled, native sync
  metadata and conflict behavior remain owned by Chromium.

## Prohibited duplicate state

Sunshine code must not introduce any of the following:

- `sunshine_history`, `sunshine_bookmarks`, or equivalent SQLite/JSON/IndexedDB
  stores;
- a second visit counter or “most visited” model;
- a shadow bookmark tree used as writable truth;
- a background export of URLs, titles, folders, or visit times to an AI or
  Sunshine service;
- direct writes to Chromium profile database or bookmark files;
- local-storage mirroring in New Tab WebUI;
- optimistic UI records that remain after a native mutation fails.

A transient view model is allowed only while a surface is open. It must be
invalidated by native observers, contain the minimum fields required for
rendering, never become a recovery source, and never cross profile boundaries.

## Deterministic acceptance tests

All tests use a temporary Chromium profile and local test-server URLs. They must
not depend on live websites or synchronization services.

### Bookmark CRUD and search

1. **BH-A1.** Create two folders and bookmarks with duplicate titles but
   different URLs.
2. **BH-A2.** Verify both native nodes, parent folders, URLs, titles, and
   ordering.
3. **BH-A3.** Rename one bookmark, change its URL, move it across folders, and
   reorder it.
4. **BH-A4.** Search separately by old title, new title, hostname, and URL
   fragment; verify only native matching results and correct folder context.
5. **BH-A5.** Delete one bookmark and verify native observers update the
   surface.
6. **BH-A6.** Exercise native undo if the implemented surface advertises undo.
7. **BH-A7.** Restart the browser and verify the final tree exactly once—no
   duplicates and no deleted node resurrection.

### Global history CRUD, search, and clear

1. **BH-B1.** Navigate two tabs through distinct local URLs with controlled
   titles and timestamps; include two visits to one URL.
2. **BH-B2.** Verify the active tab's back/forward list contains only its own
   navigation entries while global history contains visits from both tabs.
3. **BH-B3.** Search by title and URL with a bounded time range and
   deterministic order.
4. **BH-B4.** Open a result and verify normal navigation without a duplicate
   Sunshine-generated visit.
5. **BH-B5.** Delete the selected URL/visit scope through the native API; verify
   observers and a fresh query no longer return the deleted scope.
6. **BH-B6.** Clear a controlled time range; verify records outside the range
   remain.
7. **BH-B7.** Restart and verify remaining history persists and deleted/cleared
   records do not return.

### Back, forward, and recently closed

1. **BH-C1.** Navigate A → B → C in one tab and X → Y in a second tab.
2. **BH-C2.** Verify back/forward act only on the active tab and do not rewrite
   global history directly.
3. **BH-C3.** Close the A/B/C tab, invoke native reopen-closed, and verify its
   navigation stack is restored.
4. **BH-C4.** Clear global history and verify the expected native behavior of
   the current live tab stack separately; never claim that clearing history is
   equivalent to erasing the tab's in-memory navigation controller.
5. **BH-C5.** Restart and test native session-restore behavior under the
   configured startup preference separately from global history persistence.

### Privacy and isolation

1. **BH-D1.** Create bookmark/history fixtures in Profile A and different
   fixtures in Profile B; verify no cross-profile results or mutations.
2. **BH-D2.** Visit unique URLs in incognito, close all incognito windows, and
   verify they are absent from regular history, recently closed persistence, New
   Tab data, and any Sunshine-owned files.
3. **BH-D3.** Disable history saving using the supported preference/policy and
   verify Sunshine does not create a fallback record.
4. **BH-D4.** Run with no account bookmark roots and verify local bookmarks
   remain fully functional without synthetic account nodes.

### Storage and failure safety

1. **BH-E1.** Assert the implementation references native
   factories/models/services and adds no independent persistence dependency or
   schema.
2. **BH-E2.** Simulate native mutation failure or service unavailability; the UI
   reports failure and removes optimistic transient state.
3. **BH-E3.** Cleanly restart after queued writes and verify persistence.
4. **BH-E4.** Terminate during a bookmark write in a test fixture and verify
   Chromium's supported recovery behavior without reading backup files directly.
5. **BH-E5.** Run Chromium's relevant bookmark, history, session,
   profile-isolation, and browser tests for the pinned revision.

## Completion gate

This contract is complete when reviewed. Product implementation is not complete
until the pinned native Chromium build passes the deterministic tests above on
the supported desktop platforms and manual verification confirms that regular,
incognito, guest, and multiple-profile boundaries match native Chromium
behavior.
