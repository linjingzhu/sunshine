# Security Center and Threat Protection — Contract

## Status and scope

This contract applies to Sunshine OS on the pinned Chromium revision
`152.0.7977.42`. It defines the `chrome://sunshine-security` surface and the
threat-protection provider abstraction referenced in section 6.7 of the Stage
1–3 implementation handoff.

**Route.** Earlier drafts of this contract, and section 6.7 of the handoff,
placed the centre on a Sunshine-owned URL scheme.
`docs/decisions/0003-internal-scheme.md` settles that Sunshine registers no URL
scheme at all — not internally and not with any operating system. First-party
surfaces are internal pages under Chromium's existing internal scheme,
contributed as WebUI configs through
[`content/public/browser/webui_config_map.h`](https://github.com/chromium/chromium/blob/152.0.7977.42/content/public/browser/webui_config_map.h),
and the Security Center is reached at `chrome://sunshine-security`. This is a
route change, not a privilege change: every invariant below stands as written,
and SC-8 in particular is strengthened rather than relaxed, because the boundary
that withholds the scheme from web renderers is now upstream's to maintain
rather than Sunshine's to re-create. The Security Center therefore needs a host,
a WebUI config, and a module manifest — no scheme work, no shared-component
patch, and no new trust boundary.

A bare `security` host is rejected:
[`chrome/common/webui_url_constants.h`](https://github.com/chromium/chromium/blob/152.0.7977.42/chrome/common/webui_url_constants.h)
already spends that word on a settings sub-page (`kSecuritySubPage`), and two
security surfaces a user cannot tell apart is the failure mode this page can
least afford. At the pinned revision that header contains no `sunshine` host, so
`sunshine-security` collides with nothing there today **[read]**. The absence is
a fact about one revision, not a property of the name: the implementing wave
re-checks it at every upstream roll, per acceptance criterion SCA-13.

This wave is intentionally **documentation-only**. It adds no downstream patch,
no WebUI resource, and no provider implementation. Nothing here has been
compiled, run, or seen. See "Not verified" at the end of this document.

Sunshine is a native downstream of open-source Chromium. There is no wrapper
runtime and no second browser embedded in the product. The Security Center is a
first-party module under `docs/FIRST_PARTY_MODULE_ARCHITECTURE.md` and inherits
every rule in that document, including profile-keyed state, default-off network
access, and the prohibition on a privileged WebUI rendering remote content.

The handoff sketched the provider as a TypeScript interface. That framing is not
carried over: Sunshine has no scripting runtime in the browser process, so the
abstraction below is described in language-neutral terms and would be realised
as a C++ interface with a WebUI presentation layer.

## The one rule this document exists to protect

**The Security Center is a reader of Chromium security state. It is never the
decider.**

Chromium decides whether a site is blocked, whether a certificate is
acceptable, whether a download is dangerous, whether an extension is disabled,
and whether an origin holds a permission. Sunshine gathers those decisions into
one page, explains them, and may add a clearly attributed third-party signal
beside them. Sunshine does not compute, override, soften, or pre-empt any of
them.

## Ownership of every displayed signal

Each row is a signal the Security Center may show. The authoritative source
column names the component that decides; Sunshine renders what it reports.

| Signal shown in the centre | Authoritative Chromium source | Sunshine responsibility |
|---|---|---|
| Unsafe-site attempt (phishing, malware, unwanted software) | Safe Browsing subsystem and its blocking interstitial, where the pinned build enables it | Read the outcome after Chromium has acted. Never re-derive the verdict, never suppress the interstitial, never navigate past it. |
| Safe Browsing availability itself | The pinned build's Safe Browsing configuration and the user's Safe Browsing preference | State plainly whether the protection is present and enabled. Never imply protection Sunshine cannot demonstrate. |
| Certificate and TLS warnings | Certificate verification and the SSL error handler, surfaced through the interstitial and the page's visible security state | Present the Chromium-reported error identity. Never offer a proceed path Chromium has not enabled, and never re-classify an error. |
| Per-tab security level (secure, neutral, dangerous, form-warning) | Chromium's security-state helper for the tab's primary page | Read only. The centre must not compute a level from the URL string. |
| Mixed and insecure content | Chromium content-security and mixed-content handling | Read only. |
| Risky or blocked download | `DownloadItem` danger type and the download warning-event model; see `docs/DOWNLOAD_SAFETY.md` | Link to the existing Chromium warning or review surface. Never restate a danger type in stronger words, never enable a disabled action, never keep a second danger classifier. |
| Extension warning, disable reason, or blocklist state | Chromium extension registry, extension preferences, and extension management/policy | Read the Chromium-reported reason. Never install, enable, disable, or allowlist an extension from this page without going through Chromium's own extension flow; see `docs/EXTENSION_COMPATIBILITY_GATE.md`. |
| Active site permissions per origin | `HostContentSettingsMap` and the permission controller; see `docs/PERMISSION_POLICY.md` | List effective state and its source (user, temporary, policy). Changes are made through Chromium's Site settings, not through a Sunshine permission store. |
| Managed-policy security state | Chromium enterprise policy | Show it as managed policy. Never present a policy value as a user choice. |
| Third-party provider signal | Not Chromium. A Sunshine-configured `ThreatProtectionProvider` | Additive advisory only, always attributed to the named provider, always separable from the Chromium rows. |
| Recent security events | Derived from the rows above, after Chromium has decided | A Sunshine-owned, profile-keyed log of references. It is not a second source of truth. |

Where a Sunshine row and live Chromium state disagree, Chromium wins and the row
is shown as stale or dropped. The centre must never be the reason a user
believes a site is safe.

## Non-negotiable invariants

Each invariant carries an identifier so a reviewer, a test, or an upstream-roll
checklist can cite it.

| ID | Invariant |
|---|---|
| SC-1 | A provider verdict must never relax a Chromium decision. A provider `safe` cannot dismiss an interstitial, downgrade a security level, clear a certificate warning, re-enable an extension, or make a dangerous download ordinary. Severity may only move in the direction Chromium already chose, or not at all. |
| SC-2 | A provider must never sit on the critical path of a navigation, a download, or a commit. Checks are asynchronous and advisory. A slow, hostile, or absent provider must not delay, cancel, or reorder browsing. |
| SC-3 | Provider failure — error, timeout, unreachable host, network disabled, provider disabled, off-the-record context, malformed response — returns `unknown`, records one local event, and allows normal browsing. `unknown` means "no signal", never "suspicious". Failing closed is permitted only under a separately recorded strict policy, and no such policy exists today. |
| SC-4 | No page content, DOM, form data, form values, credentials, cookies, tokens, request bodies, screenshots, or page text may leave the browser for any provider, under any verdict, in any diagnostic mode. |
| SC-5 | Third-party provider details must not leak into navigation logic or browser-core UI. Only the closed verdict vocabulary in this document crosses the boundary. Provider status codes, error strings, response bodies, headers, endpoints, and category names must not be rendered raw, must not reach Chromium's interstitials, omnibox, security chip, tab strip, or download UI, and must not appear in any navigation decision. |
| SC-6 | The stable profile identifier is an in-process routing parameter only. It must never be transmitted. A stable per-user identifier attached to per-URL checks converts threat protection into a browsing-history feed, which is exactly what this contract forbids. |
| SC-7 | Provider network access is off by default, requires a host allowlist and a user-visible purpose, and requires an explicit user opt-in per profile. Turning it off must fully stop the outbound traffic, not merely hide the UI. |
| SC-8 | `chrome://sunshine-security` is a privileged WebUI. It must not load, embed, frame, or execute remote content, and it must not render provider-supplied markup, scripts, images, or links. Provider identity is shown as a locally held, locally localised name mapped from a configured provider identifier. **Restated, not withdrawn:** this invariant named the surface under a Sunshine-owned scheme until `docs/decisions/0003-internal-scheme.md`. Only the route changed. The privileged-WebUI framing the invariant depends on is unaffected — it comes from the page being registered through the content-layer WebUI config map and from renderers hosting web content being denied the scheme by [`content/public/browser/child_process_security_policy.h`](https://github.com/chromium/chromium/blob/152.0.7977.42/content/public/browser/child_process_security_policy.h), neither of which was ever a consequence of the string `sunshine`. The untrusted internal scheme, which is likewise available without a new scheme registration, is not a route to relax this invariant: a Security Center that renders provider-supplied markup in an untrusted frame is prohibited here exactly as it was before. |
| SC-9 | The centre performs no security-relevant mutation of its own. Enabling, disabling, granting, revoking, keeping, discarding, or proceeding is executed by the Chromium flow that owns it. The page routes the user there. |
| SC-10 | A provider `block` verdict may only produce the strongest treatment that a recorded product policy permits, and today that is an attributed advisory beside the Chromium rows. Sunshine must not introduce a browser-wide blocklist, a second interstitial, or a silent navigation cancellation as a side effect of adopting a provider. |
| SC-11 | The centre must never claim protection it cannot demonstrate. If Safe Browsing is absent from the build or disabled by the user, the page says so; it does not present a provider as its replacement. |
| SC-12 | Disabling the Security Center module, or every provider, must leave ordinary browsing and every Chromium security surface fully operational. |

## The `ThreatProtectionProvider` abstraction

A provider is a named, replaceable source of an advisory opinion about a URL. It
is not a policy engine, it holds no browser state, and it cannot call back into
navigation.

### Request

| Field | Type | Rule |
|---|---|---|
| URL under assessment | Chromium-canonicalised URL, reduced per the privacy contract below | Sunshine reduces it before the provider is reached. The provider never receives the unreduced URL. |
| Request reason | Closed enumeration: navigation observed, download observed, user-requested re-check | No referrer, no tab identity, no window identity, no session identity. |
| Browsing-context handle | In-process only | Selects settings, consent, and cache scope. Never transmitted. See SC-6. |
| Deadline | Duration | Expiry yields `unknown`. A provider cannot extend it. |

### Response

| Field | Type | Rule |
|---|---|---|
| Verdict | Closed enumeration: `safe`, `warn`, `block`, `unknown` | Any unrecognised value is treated as `unknown` and logged as a provider contract violation. |
| Categories | Optional list drawn from a Sunshine-owned closed vocabulary | Provider-specific category names are mapped locally to that vocabulary; unmapped categories are dropped, never displayed. |
| Provider identity | Stable configured identifier | Displayed through a local, localised name. Never a provider-supplied display string. |
| Checked at | Timestamp | Used to age out and to label the row. A future or absent timestamp yields `unknown`. |
| Validity period | Optional duration | Bounds the in-memory cache. Absent means the Sunshine default. |

### Verdict meanings

| Verdict | Meaning | Permitted effect |
|---|---|---|
| `safe` | The provider knows of no threat | None. It changes no Chromium state and removes no warning. See SC-1. |
| `warn` | The provider asserts elevated risk | An attributed advisory in the Sunshine surface, and a Security Center event. |
| `block` | The provider asserts a known-bad URL | The strongest treatment a recorded policy permits, which today equals `warn` with stronger wording. See SC-10. |
| `unknown` | No usable answer | None. Normal browsing continues. See SC-3. |

Nothing in the response may be a URL, a redirect target, a script, an HTML
fragment, an executable action, or an instruction to the browser.

## Privacy contract

### Sent to a provider

Only the following, and only after an explicit per-profile opt-in:

- the scheme, host, and port of the URL under assessment;
- the closed request-reason enumeration;
- the protocol version of this contract.

### Never sent

- The URL path, query, or fragment. Paths and query strings routinely carry
  session tokens, document identifiers, search terms, and personal data. This
  boundary reduces the detection value of a path-aware provider, and that cost
  is accepted deliberately rather than resolved by sending the full URL.
- URL credentials, in any form.
- Page content, form data, form values, credentials, cookies, storage, request
  bodies, or page titles.
- Any stable user, device, installation, or profile identifier.
- Referrer, tab, window, workspace, session, or navigation-chain data.
- Downloaded file bytes, file names, or file hashes. Download safety is
  Chromium's, under `docs/DOWNLOAD_SAFETY.md`.
- Anything at all from an off-the-record or Guest context.
- Anything at all when the provider is disabled or the user has not opted in.

### Visible to and controllable by the user

| The user can | Requirement |
|---|---|
| See which providers exist, whether each is enabled, and the exact host it contacts | Named on the page and in settings, not only in a policy document. |
| See what a provider receives | Stated in plain terms on the surface, matching the list above. |
| Turn each provider off | Off by default. Turning it off stops outbound requests and clears its cached verdicts. |
| Turn the event log off | The centre must remain usable, showing live Chromium state only. |
| Clear the event log immediately | Independent of the browsing-data flow. |
| See when a signal is Sunshine's rather than Chromium's | Every provider row is attributed. An unattributed provider row is a defect. |

Provider configuration must never be a hidden default that a user cannot inspect
or reverse.

## Event log retention

| Property | Rule |
|---|---|
| Scope | One log per regular profile, keyed to that profile. No global log, no cross-profile log, no cross-device sync. |
| Row content | Event kind, the origin as formatted by Chromium's URL formatting, the Chromium-reported reason identity, the timestamp, and — for provider rows — the provider identifier and mapped categories. |
| Never stored | Full URLs with path, query, or fragment; URL credentials; page content; form data; file bytes; file names; provider response bodies. |
| Lifetime | A rolling window bounded by both age and count: no row older than 30 days, and a fixed maximum row count per profile, whichever bound is reached first. Age-out is unconditional and does not depend on the page being opened. |
| Relationship to Chromium | References only. A row that no longer matches live Chromium state is stale and must not be presented as current. Deleting a row never deletes Chromium state. |
| Access | Local to the browser process and the privileged WebUI. Not readable by a web origin, an extension, or a remote service. |

### What deleting browsing data must also delete

Clearing browsing data for a time range must delete every Security Center event
whose timestamp falls in that range, in the same operation, without requiring
the page to be open. In addition:

| The user deletes | The Security Center must also delete |
|---|---|
| History for a URL or host | Every event referencing that origin, and every cached provider verdict for it. |
| Download history | Every download-derived event, including its warning and override rows. |
| Site data or settings for an origin | Every permission-derived event for that origin, and its cached verdicts. |
| Any time range | Every event in the range, of every kind, plus provider verdicts cached within it. |
| The profile | The entire log and cache, with the profile directory. |

A deletion must never leave a residual Sunshine row that reconstructs deleted
browsing activity. If the log cannot be deleted, the deletion is reported as
failed rather than reported as complete.

## Off-the-record behaviour

Incognito and Guest contexts are opt-in for first-party modules and require
dedicated native tests. Until those exist, the Security Center's behaviour is:

| Aspect | Off-the-record and Guest rule |
|---|---|
| Provider network calls | Not made. Every check resolves to `unknown` locally. |
| Event log | Nothing is written, to any store, for any duration beyond the session. |
| Regular-profile log | Never receives an off-the-record event, and is never mutated from an off-the-record context. |
| Historic view | Not shown. The surface presents live Chromium security state for the current session only, and says why history is absent. |
| Verdict cache | In memory, scoped to the off-the-record context, discarded when it ends. Never shared with, seeded from, or written to a regular profile. |
| Session end | Closing the last off-the-record window discards all of the above. |
| Chromium protections | Unchanged. Safe Browsing, certificate validation, and permission mediation behave exactly as Chromium defines for these contexts. |

## Command surface

Every user-visible action resolves a registered command; the page must not call
browser internals directly. `first_party/commands.json` is the authoritative
list, and this document names no command that is not in it.

Of the registered commands, the Security Center would surface only
`browser.back` to leave a flagged page, `browser.reload` to re-evaluate one,
`tab.close` to close a flagged tab, and `tab.new` to open the surface's
starting point.

Every other action this page implies — opening Site settings for an origin,
opening the download review surface, opening the extensions page, clearing the
event log, re-running a provider check, and opening the centre itself —
currently has no registered command. Those commands must be registered, owned,
and given availability predicates and error results before any UI is written.
They must not be invented in presentation code, and they must not be exercised
by calling Chromium internals to avoid registering them.

## Acceptance criteria, checkable once a native build exists

Use Chromium test fixtures and a local test server. No test may depend on a live
reputation service, a real provider endpoint, or a public website.

`SCA-` is the prefix for these criteria, and the ordinals are unchanged:
criterion 13 is `SCA-13`. `SC-` remains the prefix for the invariants each
criterion cites; the two do not overlap.

1. **SCA-1. Chromium block is never relaxed.** With an interstitial-triggering
   fixture and a stubbed provider returning `safe`, the interstitial is shown,
   the navigation does not commit, and no proceed affordance is added. Repeat
   for a certificate error and for a dangerous download. (SC-1)
2. **SCA-2. Provider is off the critical path.** With a provider stubbed to hang
   past its deadline, navigation start-to-commit timing is statistically
   unchanged against a no-provider baseline, and no navigation is cancelled.
   (SC-2)
3. **SCA-3. Failure returns `unknown` and browsing continues.** Parameterise
   error, timeout, unreachable host, malformed body, unrecognised verdict value,
   absent timestamp, and future timestamp. Each yields `unknown`, records
   exactly one local event, and leaves the page loading normally. (SC-3)
4. **SCA-4. Egress is exactly the allowed fields.** Capture the outbound request
   at a local endpoint for a URL carrying credentials, a path, a query string,
   and a fragment. Assert the payload contains scheme, host, port, request
   reason, and contract version, and nothing else. Assert no stable identifier
   is present across two checks from the same profile. (SC-4, SC-5, SC-6)
5. **SCA-5. Default off.** On a fresh profile, no provider request is emitted
   during a scripted browsing session. After opt-in, requests appear. After
   opt-out, they stop and cached verdicts are cleared. (SC-7)
6. **SCA-6. Provider strings never reach browser-core UI.** With a provider
   returning hostile strings — markup, a script fragment, a URL, an over-long
   category — assert nothing is rendered raw, the unmapped category is dropped,
   and the omnibox, security chip, interstitials, and download UI are
   byte-identical to the no-provider baseline. (SC-5, SC-8)
7. **SCA-7. Read-only surface.** Assert the page changes no content setting, no
   extension state, and no download command enablement; and that a permission or
   extension change made through Chromium's own UI is reflected on the page.
   (SC-9)
8. **SCA-8. Availability honesty.** With Safe Browsing absent from the build,
   and again with it present but disabled by preference, the page states the
   real status and does not present a provider as equivalent protection. (SC-11)
9. **SCA-9. Retention and deletion.** Seed events across several days and
   origins. Assert age-out at the 30-day bound and at the row-count bound;
   assert a time-range clear removes exactly the in-range rows without the page
   being open; assert per-URL history deletion, download-history deletion, and
   per-origin site-data deletion each remove their derived rows and cached
   verdicts; assert profile deletion removes the store from disk.
10. **SCA-10. Off-the-record isolation.** In Incognito and Guest: assert zero
    provider requests, zero writes to any store, no historic view, and that the
    regular-profile log is unchanged. Assert the off-the-record cache does not
    survive the last window closing.
11. **SCA-11. Module removal.** With the module disabled, ordinary browsing,
    Chromium interstitials, download warnings, permission prompts, and extension
    warnings all behave as on stock Chromium. (SC-12)
12. **SCA-12. Patch and build gate.** The eventual downstream patch series
    applies in order to `refs/tags/152.0.7977.42`, native compilation succeeds,
    and the relevant unit, browser, and view tests pass. The privileged WebUI is
    confirmed to load no remote resource.
13. **SCA-13. Route, host, and the absence of a scheme.** The centre is
    reachable at `chrome://sunshine-security` and nowhere else. Assert that the
    build registers no Sunshine URL scheme — the standard, secure, savable,
    referrer, CORS-enabled, service-worker, empty-document and handled-protocol
    registrations carry no `sunshine` entry — that the installer registers no
    Sunshine protocol with the operating system on any platform, and that the
    host does not collide with any host in the compiled internal-page list at
    the revision under test. Re-run the collision half at every upstream roll,
    since it is a fact about a revision rather than about the name.
    (`docs/decisions/0003-internal-scheme.md`, `docs/OMNIBOX_CONTRACT.md` OS-3)

## Unresolved product decisions

These must be answered by the product owner before implementation, not chosen by
an implementer.

| Priority | Question |
|---|---|
| P0 | What is a provider `block` verdict actually allowed to do? This document holds it at an attributed advisory. Any stronger treatment is a second blocking path and needs an explicit decision, recorded the way the download danger-category decision must be. |
| P0 | Is origin-only egress accepted, given that it reduces detection for path-specific threats such as a phishing page hosted on a shared platform? The alternative is sending paths, which this contract currently forbids. |
| P1 | Which threat provider and commercial licensing model applies? This is already open as a P1 in the handoff, required by the Stage 2 security release. |
| P1 | Should any strict, fail-closed policy exist at all, and if so for which contexts? SC-3 fails open until this is answered. |
| P2 | Is 30 days the right event-log window, and what is the row-count bound? |

## Not verified

Nothing in this document has been executed. Specifically:

- No native Chromium build was produced or run.
- No `chrome://sunshine-security` surface exists; no WebUI resource, WebUI
  config registration, C++ interface, or provider implementation has been
  written. The host is specified here and is registered nowhere.
- The two upstream facts this document reads at the pinned tag — that
  `chrome/common/webui_url_constants.h` defines `kSecuritySubPage` as `security`
  and contains no `sunshine` host — were read from the source at
  `refs/tags/152.0.7977.42` over HTTPS. They were not observed in a running
  binary, and no build was produced in which to observe them: `NOT AVAILABLE`.
- No provider was contacted, stubbed, or measured. No egress capture was taken.
- No visual, accessibility, keyboard-navigation, localisation, or screen-reader
  verification was performed.
- The Chromium ownership table describes the architectural division of
  responsibility at the pinned revision. It has not been confirmed against a
  running binary, and the presence of Safe Browsing in a given Sunshine build
  configuration has not been established.
- The acceptance criteria above are unrun.

This contract is complete when reviewed. The feature remains `planned` under the
first-party module lifecycle: not `prepared`, because no manifest or static gate
exists yet, and certainly not `runtime_verified`.
