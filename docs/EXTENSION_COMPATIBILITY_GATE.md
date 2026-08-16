# Extension Compatibility Architecture Gate

## Purpose

This gate prevents Sunshine OS from claiming Chrome extension compatibility merely because it is a native Chromium downstream. Compatibility is an evidence-backed product capability, not an inherited marketing claim.

The gate applies before any extension-related feature is described as implemented, supported, secure, or ready for users.

## Architecture boundary

Sunshine must use Chromium's native extension platform. It must not add a second extension runtime, permission store, updater, package format, or JavaScript bridge.

The following Chromium-owned systems remain authoritative:

- extension loading, process isolation, and service-worker lifecycle;
- Manifest V3 parsing and API availability;
- host permissions, optional permissions, and user consent;
- extension management and policy enforcement;
- content-script injection and origin isolation;
- extension storage and incognito controls;
- update verification and package signature validation;
- Safe Browsing or other upstream abuse protections when present in the build.

Any Sunshine change to these systems requires a separate security review and a native build gate.

## Compatibility claims

### Claim allowed before a native build

Only this architectural statement is allowed:

> Sunshine OS is a native Chromium downstream intended to preserve Chromium's extension architecture.

This is not evidence that a particular extension installs or works.

### Claims requiring native runtime evidence

The following claims are prohibited until the corresponding tests in this document pass on a packaged Sunshine build:

- "Supports Chrome extensions"
- "Chrome-compatible"
- "Supports Manifest V3 extensions"
- "Extensions from the Chrome Web Store work"
- "All Chrome extensions work"
- any percentage or catalog-wide compatibility claim

Compatibility must be stated by tested channel, platform, architecture, Chromium revision, and extension version.

## Supported-scope candidates

These candidates are evaluated independently. Passing one does not imply that another is supported.

### Manifest V3

The initial technical target is ordinary Manifest V3 behavior already present in the pinned Chromium revision. Sunshine must not promise every MV3 API. APIs disabled by upstream build flags, platform restrictions, enterprise policy, service availability, or product branding remain unsupported until individually verified.

Manifest V2 is outside the initial compatibility target. It must not be re-enabled through a downstream patch without a separate security and maintenance decision.

### Unpacked extensions

Developer-mode loading of a local unpacked extension may be supported for internal development after runtime verification. It is not a consumer installation channel and must not be presented as equivalent to a signed store package.

The test fixture must be owned by the repository, contain no remote code, request only the permissions needed by each test, and expose its version and source revision in the test report.

### Chrome Web Store

Chrome Web Store installation and updates are not guaranteed.

Chromium source availability does not grant Sunshine permission to use Google trademarks, Chrome branding, proprietary services, API keys, update endpoints, store integrations, or distribution agreements. Store availability may also depend on product identity, request headers, policy, terms, signing, and services not included in an open-source Chromium build.

Until legal, service, and runtime evidence exists, the product must say:

> Chrome Web Store installation has not been verified and is not a supported distribution channel.

Do not patch around store restrictions, impersonate Google Chrome, reuse Chrome identifiers, or inject credentials intended for another product.

## Security boundaries

### Permissions

- Permission prompts must be Chromium-native and show the requesting extension and affected origins accurately.
- Sunshine must not auto-grant host, private browsing, native messaging, file URL, camera, microphone, location, notification, clipboard, or debugger access.
- Optional permission grants and revocations must round-trip through Chromium's authoritative settings.
- Incognito access must remain off by default and require explicit user action.
- Uninstalling an extension must remove its active privileges without deleting unrelated user data.

### Isolation

- Content scripts must not gain browser-process or Sunshine-privileged access.
- Extension pages must retain Chromium origin and process isolation behavior.
- Sunshine internal pages must not be exposed through broad host permissions or content-script matches.
- Native messaging is excluded until host registration, executable trust, consent, and removal have a separate threat model.

### Updates and signing

- Production extensions must use a verifiable signed package and an approved update source.
- Sunshine must not silently replace, downgrade, or install extensions.
- Update failures must preserve the last verified version or disable it safely; they must not fall back to unsigned code.
- Developer-mode unpacked extensions must be visibly identified and must never be auto-updated as production packages.
- Browser binary signing and extension package signing are separate trust boundaries. Signing Sunshine does not establish trust in an extension, and signing an extension does not establish trust in Sunshine.

### Data and network behavior

- Test reports must disclose extension-requested permissions and external network destinations.
- Sync, account, telemetry, crash reporting, and store services must not be assumed to exist in Sunshine.
- A test passes only if absence of Google-specific services fails closed or degrades without exposing data.

## Test matrix

Every runtime result records: Sunshine commit, Chromium revision, OS version, CPU architecture, build type, packaging/signing status, extension fixture/version, clean or existing profile, and test timestamp.

| Area | Required cases | Pass evidence |
|---|---|---|
| Installation | valid unpacked MV3; malformed manifest; missing resource; unsupported manifest version | Valid fixture loads; invalid fixtures fail with an actionable native error |
| Lifecycle | install; enable; disable; browser restart; update; uninstall | State transitions persist correctly and no removed code continues running |
| Service worker | startup; idle suspension; event wake-up; browser restart | Expected events run once without relying on a permanently alive background page |
| Content scripts | declared match; non-matching origin; iframe; restricted/internal page | Injection occurs only where authorized; restricted pages remain protected |
| Permissions | required; optional allow; deny; revoke; host access; incognito | Chromium-native state and prompt match actual effective access |
| UI surfaces | toolbar action; popup; options page; context menu; notifications | Surface opens, closes, scales, and exposes keyboard/accessibility behavior correctly |
| Storage | local; session; quota/error; restart; uninstall | Data follows documented lifetime and failure behavior |
| Network | permitted fetch; unpermitted origin; offline; TLS failure | Requests respect permissions and fail closed with no credential leakage |
| Security | CSP violation; remote-code attempt; cross-origin attempt; internal-page access | Chromium blocks prohibited behavior and records an inspectable failure |
| Profile modes | regular; fresh profile; multiple profiles; guest; incognito | State and permissions do not cross profile boundaries |
| Packaging | unpacked developer fixture; signed package if approved | Channel is clearly identified and signature/update behavior matches policy |
| Regression | browser update to next pinned Chromium revision | Complete matrix reruns before compatibility is carried forward |

Chrome Web Store testing, if later authorized, is a separate matrix row covering discovery, install, login dependency, update, removal, policy errors, and loss of store connectivity. A successful manual install of one extension is not sufficient evidence.

## Minimum representative MV3 fixtures

The initial suite must include small repository-owned extensions covering:

1. action popup and options page;
2. event-driven service worker;
3. content script with narrow host permissions;
4. optional host permission request and revocation;
5. declarative network request rule;
6. local/session storage lifecycle;
7. intentionally malformed manifest and prohibited remote-code cases.

Third-party extensions may supplement this suite but cannot replace controlled fixtures. Record their exact public version and do not automate access to private user accounts during compatibility testing.

## Go / no-go criteria

### GO: architecture preserved

The architecture gate passes when:

- no second extension runtime, store, updater, permission database, or custom prompt exists;
- the pinned upstream sources still own extension lifecycle and security decisions;
- static checks detect accidental enabling of Manifest V2 or auto-grant behavior;
- test fixtures and expected results are reviewable without external accounts;
- all compatibility wording remains scoped as unverified until runtime evidence exists.

This permits continued implementation and internal testing. It does not authorize a public compatibility claim.

### GO: unpacked MV3 internal support

Internal unpacked MV3 support may be marked verified only when:

- a native packaged build completes on the target platform;
- every required fixture passes the applicable matrix on a clean profile;
- permission, isolation, lifecycle, and uninstall tests pass;
- failures are documented with no security-critical open defect;
- evidence is attached to the development report.

### GO: public supported channel

A distribution channel may be publicly supported only when:

- its legal and service dependencies are approved;
- package authenticity and update provenance are verified;
- supported platforms and limitations are published;
- repeatable CI or controlled release tests cover installation and update;
- a rollback and vulnerable-extension response process exists.

### NO-GO

Development or release must stop for the affected channel if any of these occurs:

- Sunshine bypasses Chromium permission, signing, isolation, or update enforcement;
- an extension receives access not shown to or granted by the user;
- extension state crosses profile or incognito boundaries;
- removed, disabled, invalid, or unsigned code continues executing;
- a test depends on impersonating Chrome or using unauthorized Google services;
- a critical matrix result is missing, flaky, or only inferred from upstream behavior;
- a Chromium revision roll invalidates prior runtime evidence and the matrix has not been rerun.

## Evidence record

Every compatibility report must separate:

- **Inherited:** behavior documented by the pinned upstream Chromium source;
- **Statically checked:** downstream code or patch properties verified without execution;
- **Runtime verified:** observed on a named Sunshine build and platform;
- **Unsupported:** intentionally excluded or unavailable behavior;
- **Unknown:** untested behavior for which no claim is allowed.

The narrowest applicable status wins. If a feature passes unpacked testing but its store install path is unknown, report "unpacked MV3 runtime verified; Chrome Web Store unsupported," not "extension compatible."
