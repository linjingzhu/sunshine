# Omnibox Classification — Native Ownership Contract

## Status and scope

This contract applies to Sunshine OS on the pinned Chromium revision
`152.0.7977.42` recorded in `config/chromium.version`. It settles section 5.3 of
`docs/SUNSHINE_OS_STAGE_1_TO_3_IMPLEMENTATION_HANDOFF.md` (omnibox
classification) and the omnibox row of the Stage 1 feature table: URL and search
classification, Ctrl+L, paste, and Paste & Go.

This wave is **documentation-only**. It adds no downstream patch, no first-party
module, and no registered command. No build was configured, compiled, or run;
see *Evidence and what was not verified* at the end, which also records exactly
what was checked and how.

Sunshine is a native downstream of open-source Chromium. There is no wrapper
runtime, no intermediary process between the address bar and Chromium's
navigation stack, and no scripting layer in which a second interpretation of
user text could live.

Unlike the sibling contracts, the statements below about Chromium's behaviour
are not inferred from the documented architecture of the line. The classifier
sources at `refs/tags/152.0.7977.42` were fetched and read; every claim marked
**[read]** is taken from that source, and every claim that depends on runtime
provider scoring is marked **[measure]** and is stated as a test to run, not as
a fact.

## Decision

**Sunshine implements no omnibox classification, no URL fixup, no scheme
handling, and no search-versus-navigation heuristic. Stage 1 ships zero lines of
Sunshine code on this path.**

This is a **zero-runtime-patch** decision on the same grounds as
`docs/PERMISSION_POLICY.md` and `docs/BROWSER_UTILITIES_CONTRACT.md`. It is also
stronger than those two, because here a patch would not merely duplicate
Chromium — it would degrade it. Classification is the browser's single most
attacked text-parsing surface. Every heuristic below took Chromium a decade of
adversarial hardening, and each one is the reason a specific class of spoof does
not work.

Two future changes are foreseeable and are *not* authorised by this document:
registering an internal `sunshine` scheme (section 6) and surfacing commands
through the omnibox (section 11). Each requires a separate reviewed change, and
each is constrained by invariants stated here in advance.

## 1. What "no second parser" means, precisely

The handoff says classification "stays in Chromium's omnibox
`AutocompleteClassifier`". That names the wrong object, and the imprecision
matters, because it points a future reviewer at a seam that the address bar does
not use.

`AutocompleteClassifier::Classify` is a one-shot helper for callers **outside**
the omnibox — "Search for…" in a context menu, a dropped string, a text
selection — and it returns a default match and an alternate-navigation URL for
text the user is not editing **[read:
`components/omnibox/browser/autocomplete_classifier.h`]**. Typing in the address
bar does not go through it. The edit path constructs an `AutocompleteInput`
directly and runs the provider set.

The real pipeline, and the only accurate statement of the rule:

```text
user text
  │  (paste / drop only) omnibox::SanitizeTextForPaste
  ▼
AutocompleteInput::Init
  ├─ url_formatter::SegmentURL          split into scheme/user/host/port/path
  ├─ url_formatter::FixupURL            canonicalise, add default scheme
  ├─ AutocompleteSchemeClassifier       what does this browser do with a scheme?
  ├─ Parse                              → URL | QUERY | UNKNOWN | EMPTY
  └─ ShouldUpgradeToHttps               http → https for typed schemeless URLs
  ▼
AutocompleteController → providers → AutocompleteResult
  ▼
default match (+ optional alternate-nav URL)
  ▼
commit → NavigationController
```

Sunshine must not stand at any arrow. Concretely, first-party code must never:

1. construct an `AutocompleteInput` from text it has trimmed, completed,
   corrected, lower-cased, prefixed, suffixed, or joined;
2. read the input type or the result set and substitute a different destination;
3. re-order, re-score, filter, or inject matches so that the default match
   changes;
4. call a navigation API with a raw user string, bypassing the pipeline
   entirely — this is the failure mode that looks like "we just handle
   `sunshine://` ourselves" and it is prohibited by section 6;
5. hold the input while an asynchronous check runs. A blocking classifier is a
   navigation-latency regression and, per `docs/SECURITY_CENTER_CONTRACT.md`
   SC-2, a prohibited critical-path dependency.

Presentation is not parsing. Sunshine may theme the address bar through design
tokens, place it, and add invocation sources for existing native commands, under
the limits in section 9.

## 2. Implementation authority in the pinned revision

Each path below was fetched at `refs/tags/152.0.7977.42` and returned content.

| Concern | Chromium source |
|---|---|
| Input segmentation, fixup, type decision, HTTPS default-scheme upgrade | [`components/omnibox/browser/autocomplete_input.cc`](https://github.com/chromium/chromium/blob/152.0.7977.42/components/omnibox/browser/autocomplete_input.cc) |
| One-shot classification for non-omnibox callers | [`components/omnibox/browser/autocomplete_classifier.h`](https://github.com/chromium/chromium/blob/152.0.7977.42/components/omnibox/browser/autocomplete_classifier.h) |
| Provider orchestration and result assembly | [`components/omnibox/browser/autocomplete_controller.h`](https://github.com/chromium/chromium/blob/152.0.7977.42/components/omnibox/browser/autocomplete_controller.h) |
| Default match, alternate-nav URL, Paste & Go | [`chrome/browser/ui/omnibox/omnibox_edit_model.h`](https://github.com/chromium/chromium/blob/152.0.7977.42/chrome/browser/ui/omnibox/omnibox_edit_model.h) |
| Paste sanitisation, `javascript` stripping, copy adjustment | [`components/omnibox/browser/omnibox_text_util.h`](https://github.com/chromium/chromium/blob/152.0.7977.42/components/omnibox/browser/omnibox_text_util.h) |
| Which schemes this browser treats as navigable | [`chrome/browser/autocomplete/chrome_autocomplete_scheme_classifier.cc`](https://github.com/chromium/chromium/blob/152.0.7977.42/chrome/browser/autocomplete/chrome_autocomplete_scheme_classifier.cc) |
| The handled-protocol set that decision reads | [`chrome/browser/profiles/profile_io_data.cc`](https://github.com/chromium/chromium/blob/152.0.7977.42/chrome/browser/profiles/profile_io_data.cc) |
| Standard/savable/referrer scheme registration | [`chrome/common/chrome_content_client.cc`](https://github.com/chromium/chromium/blob/152.0.7977.42/chrome/common/chrome_content_client.cc) |
| Internal-page completion (`chrome://…`) | [`components/omnibox/browser/builtin_provider.cc`](https://github.com/chromium/chromium/blob/152.0.7977.42/components/omnibox/browser/builtin_provider.cc) |
| Host fixup and canonicalisation helpers | [`components/url_formatter/url_fixer.cc`](https://github.com/chromium/chromium/blob/152.0.7977.42/components/url_formatter/url_fixer.cc) |
| IDN display and homograph spoof checks | [`components/url_formatter/spoof_checks/idn_spoof_checker.h`](https://github.com/chromium/chromium/blob/152.0.7977.42/components/url_formatter/spoof_checks/idn_spoof_checker.h) |
| Post-classification HTTPS upgrade and fallback | [`chrome/browser/ssl/https_upgrades_interceptor.cc`](https://github.com/chromium/chromium/blob/152.0.7977.42/chrome/browser/ssl/https_upgrades_interceptor.cc) |
| Open-tab matching behind "switch to this tab" | [`components/omnibox/browser/tab_matcher.h`](https://github.com/chromium/chromium/blob/152.0.7977.42/components/omnibox/browser/tab_matcher.h) |
| Embedder wiring of the omnibox to the browser | [`chrome/browser/ui/omnibox/chrome_omnibox_client.cc`](https://github.com/chromium/chromium/blob/152.0.7977.42/chrome/browser/ui/omnibox/chrome_omnibox_client.cc) |
| WebUI host registration | [`chrome/browser/ui/webui/chrome_web_ui_controller_factory.cc`](https://github.com/chromium/chromium/blob/152.0.7977.42/chrome/browser/ui/webui/chrome_web_ui_controller_factory.cc), [`content/public/browser/webui_config_map.h`](https://github.com/chromium/chromium/blob/152.0.7977.42/content/public/browser/webui_config_map.h) |
| Process-level scheme access control | [`content/public/browser/child_process_security_policy.h`](https://github.com/chromium/chromium/blob/152.0.7977.42/content/public/browser/child_process_security_policy.h) |

These are evidence, not an instruction to modify them. Note that the omnibox
edit model and view now live under `chrome/browser/ui/omnibox/`, not under
`components/omnibox/browser/`; an upstream reorganisation has already moved
them. That is the normal condition of this surface and the reason section 13
makes the path table a roll gate.

## 3. The classification table, corrected

The handoff's table has one column for "Result" and therefore conflates three
different things: the **input type** (a pure function of the text, decided by
`Parse`), the **default match** (decided by provider scoring against
profile state), and the **committed URL** (decided after navigation begins).
They differ, and every real defect below is a place where they differ.

`URL`, `QUERY`, `UNKNOWN` are the input types. Roughly: `URL` means "navigate
unless a provider outscores it", `QUERY` means "search, and do not offer
navigation", `UNKNOWN` means "search by default, but keep a navigation match
available and offer the accidental-search correction".

| Input | Type **[read]** | Deciding rule in `Parse` **[read]** | Correction to the handoff |
|---|---|---|---|
| `github.com` | `URL` | Known registry → `URL`; fixup yields `http://github.com/`, then `ShouldUpgradeToHttps` rewrites the scheme to `https` because the user typed no scheme, the host is unique, and no port was given | The handoff says "navigate to `https://github.com`". The classified URL is `https://github.com/` only because of the default-scheme upgrade, and that upgrade has documented exclusions. The committed URL may still be `http` after upgrade fallback. Sunshine must never hard-prefix `https://` to make the table true. |
| `https://github.com` | `URL` | Explicit scheme | "Navigate unchanged" is false as written: the URL is canonicalised (empty path becomes `/`, host lower-cased, IDN converted, escapes normalised). The correct requirement is *no host, port, path, or query substitution* — not byte identity. |
| `localhost:3000` | `URL` | `has_known_tld \|\| DomainIs("localhost") \|\| has_port()` | Not a "development-safe rule" that Sunshine adds. It is inherited, and it is far broader than localhost: **any** host with a port classifies as `URL`. See section 5. |
| `intranet-host:8080` | `URL` | Same clause — the port alone decides | Missing from the handoff. It is the same rule as the previous row and it is the one with security consequences. |
| `sunshine://settings` | `UNKNOWN` today, therefore a **search** | Unknown scheme → `GetInputTypeForScheme` → not a handled protocol → external-protocol block state → no registered handler → falls through to `UNKNOWN` | The handoff's "internal route request" describes a browser that does not exist at Stage 1. Registering the scheme is what makes the row true, and section 1.2 of the handoff excludes the `sunshine://` App SDK from Stage 1–3. See section 6. |
| `material design` | `QUERY` | Space in the host → invalid hostname → `QUERY` | Correct, but "search with configured provider" is only guaranteed for `QUERY`. It is *not* guaranteed for every plain-looking phrase; see the next two rows. |
| `wiki` | `UNKNOWN` | No scheme, no port, no username, no known registry | The handoff's table implies single words search. They search *by default*, but a navigation match stays available and history/shortcut learning can promote it. The table is not a universal truth; it is the cold-profile behaviour. |
| `who.int` | `URL` | Known registry | The "valid URL and plausible search term" case the handoff never states. Type is `URL`; whether Enter navigates still depends on scoring. See section 7. |
| `foo.xxx` (unknown TLD) | `UNKNOWN` | No known registry, no other URL signal | Deliberately ambiguous upstream: an unknown-TLD host and a dotted identifier such as a preference name are indistinguishable, so Chromium searches and lets the user correct it. |
| `user@example.com` | `UNKNOWN` | Username present and no desired TLD → treated as more likely an address than an authentication attempt | Missing from the handoff. |
| `github.com@evil.example` | `UNKNOWN` | Same username clause. The host is `evil.example`, not `github.com` | The canonical omnibox phishing input. Sunshine must never "read" the leading label as the destination, and must never render it as the origin. |
| `github.com@evil.example` + Ctrl+Enter | `URL` | A non-empty desired TLD skips the username clause; the known registry then decides | Verified and non-obvious: the desired-TLD accelerator makes a userinfo input navigable. Sunshine must not add an affordance that supplies a desired TLD implicitly. |
| `1.2.3.4` | `URL` | IPv4 with four typed components | Missing from the handoff. |
| `3232235521`, `13.5/7.25` | `QUERY` / `QUERY` | Fewer than four typed IPv4 components, absent a scheme or trailing slash | Missing. These are the "looks like an IP but is not" defences. |
| `0.0.0.0` | `URL` | Explicit four-component exception to the zero-first-octet rule | Missing. |
| `[::1]:8080` | `URL` | IPv6 literals are treated as certain navigations | Missing. |
| `example.com/path with space` | `URL` | More than one non-host component, or a trailing slash, forces `URL` | Missing; explains why intranet paths work without a known registry. |
| `javascript:alert(1)` | scheme-dependent | A `javascript` input whose remainder is unlikely to be code returns `UNKNOWN`; otherwise the scheme classifier reports `URL` | The required *outcome* is that no omnibox input ever executes script in the current page. That is a navigation-stack guarantee, not a classification one. **[measure]** |
| `data:text/html,…` | `URL` | `data` is in the handled-protocol set | Classifying as `URL` does not mean the navigation commits; top-level `data:` navigation is separately restricted. **[measure]** |
| `view-source:https://example.com` | `URL` | `view-source` is explicitly listed by the scheme classifier | Same split: classification permits it, later navigation policy may not. **[measure]** |
| `file:///C:/` | `URL` on desktop | `file` handled explicitly, and rejected only on mobile builds | Missing. Sunshine adds no restriction here; `docs/BROWSER_UTILITIES_CONTRACT.md` already forbids interposing on local content. |
| `chrome://settings` | `URL` | `chrome` is in the handled-protocol set | Internal pages remain reachable. Sunshine must not hide, rename, or intercept them. |
| `аpple.com` (Cyrillic first letter) | `URL` | Registry lookup succeeds on the punycode host | Display, not classification, is the defence: the IDN spoof checker decides whether the host renders as Unicode or punycode. Sunshine must never re-render a host. See section 9. |

Where a measured result on the pinned build contradicts a row above, **the build
is right and this table is corrected**. That direction is the whole point: this
table is a description of inherited behaviour, and a description that disagrees
with the thing it describes is a documentation bug, never a licence to patch.

## 4. "Classify conservatively", made testable

The handoff's rule — *"Invalid or ambiguous input must produce a search rather
than an unsafe inferred navigation"* — cannot be a Sunshine implementation
requirement. To force a search, Sunshine would have to decide what "ambiguous"
means and override the result, which is the second parser the same paragraph
forbids. As written the sentence is also a rough restatement of what `UNKNOWN`
already does, so it belongs in the acceptance suite, not the specification.

It is replaced by four rules that a test can fail.

| ID | Rule |
|---|---|
| OC-1 | **Commit equals disclosure.** The destination reached on commit is the destination shown as the selected match at the moment of commit. If no match is shown — Paste & Go, a drop, a gesture, an automation entry point — the invoking surface must disclose which of "navigate" or "search" it will perform before it acts. |
| OC-2 | **No Sunshine influence on type or default.** For every input in the corpus of section 3, the input type and the default match are identical with all Sunshine modules enabled and with all of them disabled. This is falsifiable and is the operational meaning of "no second parser". |
| OC-3 | **Ambiguity keeps its escape hatch.** Where Chromium searches an `UNKNOWN` input, the navigation match and the accidental-search correction affordance remain reachable. Sunshine must not remove, collapse, or auto-dismiss them, and must not act on the alternate-navigation URL by itself. |
| OC-4 | **No inference from anything but the text.** Classification input is the text, the caret, the desired TLD from an explicit accelerator, and the profile state Chromium already consults. Never page content, referrer, clipboard contents the user did not paste, prior tab, workspace, or a Sunshine-held history. |

OC-1 is the load-bearing one. An address bar is trustworthy because the user can
see the destination before committing to it; every omnibox phishing technique is
an attack on the gap between what was shown and what was reached.

## 5. Host-with-port and the development-safe rule

Verified rule: after scheme, username, IP-literal and hostname-validity handling,
an input navigates if the host has a known registry, **or** the host is
`localhost`, **or** the input has a port. `.example`, `.test`, `.local` and
`.internal` navigate when they carry at least one subdomain.

Consequences that the handoff's one-line "development-safe rule" hides:

1. The rule is not localhost-specific. `build-box:8080` and `10.0.0.7:3000`
   navigate for the same reason `localhost:3000` does.
2. HTTPS default-scheme upgrade is **skipped** for IP addresses, for non-unique
   hostnames, and whenever an explicit port is present **[read]**. Local
   development over plain HTTP therefore keeps working without any Sunshine
   involvement, and Sunshine must not "help" by forcing `https`.
3. Sunshine must not disable the HTTPS upgrade globally in order to make some
   development case convenient. That trades every user's transport security for
   a developer's convenience, and the developer case already works.
4. Sunshine must not maintain a development-host allowlist, a "trusted local
   hosts" preference, or a port heuristic. Any such list is both a second parser
   and a durable record of the user's private network — prohibited by section 12
   and by the privacy posture of `docs/SECURITY_CENTER_CONTRACT.md`.

The residual risk is stated rather than hidden: because a port makes any
single-label host navigable, a typo can send a request to an internal service.
That is inherited, deliberate, and cheaper than the alternative — a Sunshine
allowlist would have to learn which hosts are internal, which is exactly the
data this product does not collect.

## 6. The `sunshine` internal scheme

### 6.1 Stage 1 truth

No `sunshine` scheme exists in the pinned revision. Typing `sunshine://settings`
today produces an `UNKNOWN` input and therefore a **search** — and, worse, a
search whose query string is the internal route name, sent to the configured
search provider. The handoff's table row is aspirational, the Stage 1 acceptance
suite would fail it as written, and no surface named "settings" is planned for
Stage 1 in any case.

Stage 1's correct behaviour is the search. This document does not authorise
registering the scheme.

### 6.2 Two different things called `sunshine://`

Section 1.2 of the handoff excludes the "`sunshine://` production App SDK" from
Stage 1–3, while section 6.7 requires `sunshine://security` in Stage 2 and
`docs/SECURITY_CENTER_CONTRACT.md` already specifies it. These are not in
conflict once separated:

- **Internal surfaces** — a small, closed, compile-time set of first-party WebUI
  pages, enumerated in source, shipped with the binary. In scope from Stage 2.
- **App routes** — third-party or dynamically installed Sunshine Apps addressed
  by scheme. Excluded from Stage 1–3, and excluded by this contract as well.

A registration that admits a route not present in the compiled set is an App SDK
in disguise and is out of scope.

### 6.3 Invariants for any future registration

A scheme is a trust boundary. The following bind the change that registers one;
a registration that cannot satisfy all of them must not land.

| ID | Invariant |
|---|---|
| OS-1 | The scheme is registered as a standard, **WebUI-only** scheme with the same properties Chromium gives its own internal scheme: not web-safe, not a savable scheme, not a referrer scheme, not an extension scheme. Renderers hosting web content must never be granted request access to it. |
| OS-2 | Navigation to the scheme is **browser-initiated only**. A link, a form, `window.open`, a script navigation, a meta refresh, a server redirect, a `fetch`/XHR/WebSocket request, a worker import, a stylesheet or image reference, or any subframe or embed from web content must fail, and must fail without a user-visible prompt that could be mistaken for consent. |
| OS-3 | The Sunshine installer must **not** register the scheme with the operating system as an external protocol handler, and no Sunshine code may add it to the browser's own external-protocol allowances. Verified mechanism: the scheme classifier consults the external-protocol handler and the OS application registry, so an OS registration would turn every web page in every browser on the machine into a launcher for internal Sunshine routes. This is the single highest-severity mistake available on this surface. |
| OS-4 | The scheme must not be obtainable through `registerProtocolHandler()`, and must not be added to any custom-handler allowlist. |
| OS-5 | An unknown host on the scheme yields a **local error page**. It must never fall back to a search, because that transmits internal route names to a third-party search provider, and it must never fall back to a different internal surface. |
| OS-6 | Completion for the scheme, if offered, enumerates the compiled surface list only, exactly as internal-page completion does today. It must never complete from history, from typed text supplied by a page, or from a remote list. |
| OS-7 | The internal surfaces are privileged WebUI and inherit `docs/SECURITY_CENTER_CONTRACT.md` SC-8 and the DevTools consequences in `docs/BROWSER_UTILITIES_CONTRACT.md`: no remote content, no secrets, no client-side enforcement. Reaching such a page must never by itself grant a capability. |
| OS-8 | Every privileged action on those pages is executed by a registered command with a browser-side availability check. Arriving at a route is navigation, not authorisation. |
| OS-9 | No first-party WebUI page, Mojo handler, or module may accept a string and navigate the browser to it. Text submitted from a Sunshine surface takes the same classification path as typed text, and every handler validates its calling WebUI origin per section 5.5 of the handoff. |
| OS-10 | If any invariant above cannot be met, the surface is reached through an internal page under Chromium's existing internal scheme instead. Product branding is not a reason to open a new trust boundary. |

## 7. Valid URL and plausible search term

Some inputs are simultaneously a well-formed URL and an ordinary thing to search
for: `who.int`, `bit.ly`, `wiki`, a bare product name that is also a registered
domain. The handoff does not mention this class at all.

Chromium resolves it in two stages: `Parse` decides the type from the text alone,
then providers score. The second stage reads profile state — typed history,
shortcuts, bookmarks, the default search provider's suggestions. **The same text
can therefore yield different default matches for two users, or for the same
user on two days.** This is the largest defect in the handoff's table: it is
written as a total function of the input, and it is not one.

Contract:

1. Sunshine does not adjudicate this class. There is no Sunshine tie-break, no
   "prefer search for short inputs", no domain allowlist, no per-user override.
2. Sunshine must not learn from it. No first-party module may record which way an
   ambiguous input resolved, or use such a record to bias a later result. The
   learning that exists is Chromium's, stored in the profile, deleted by
   Chromium's own clearing flows per `docs/BOOKMARKS_HISTORY_CONTRACT.md`.
3. Acceptance tests for this class assert **type**, which is deterministic, and
   assert *stability* of the default match — that it is unchanged by enabling
   Sunshine — rather than asserting a specific match, which is profile-dependent.
4. OC-3 applies: whichever way it resolves, the other option stays one keystroke
   away.

## 8. Paste, Paste & Go, and drop

Verified paste sanitisation **[read:
`components/omnibox/browser/omnibox_text_util.h`]**:

- leading and trailing whitespace is stripped;
- internal whitespace runs **without** CR/LF are preserved, and their presence is
  itself a signal that the input is a search;
- internal whitespace runs **containing** CR/LF are collapsed — to a single space
  when other internal whitespace exists, and removed entirely when it does not,
  because a line-broken URL is the likely case;
- leading `javascript` schemas are stripped from the result.

The third bullet is security-relevant and unmentioned in the handoff: a URL
broken across lines by a mail client is rejoined into a single navigable URL
before classification. That is correct and useful, and it means the text
classified is not always the text on the clipboard.

Rules:

| ID | Rule |
|---|---|
| OP-1 | Paste & Go is Chromium's. Sunshine adds no clipboard reader, no pre-parse, no unwrapper for tracking or redirect URLs, and no "clean up this link" transformation. |
| OP-2 | Paste & Go commits without a visible match list, so OC-1 is satisfied by the invoking affordance itself: it must state whether it will navigate or search, as the native menu item does. Sunshine must not add an affordance that omits that distinction. |
| OP-3 | Paste & Go must not be bound to a bare mouse gesture or to any input that can fire without the user having seen the target. `docs/GESTURE_CONTRACT.md` maps gestures to command identifiers only; a gesture that navigates to unseen clipboard content is prohibited. |
| OP-4 | A drop onto the address bar is classified like typed text. Text dropped **from web content** must never navigate without an explicit user commit. |
| OP-5 | Paste & Go is a browser-chrome action on a user gesture. It must never become a path by which a page observes the clipboard; the web clipboard capability keeps the `ASK` default in `docs/PERMISSION_POLICY.md`. |
| OP-6 | Copy from the address bar keeps Chromium's behaviour, including re-attaching an elided scheme so the copied text is a complete URL. Sunshine must not shorten, prettify, or append tracking parameters to copied text. |

## 9. Security boundary

The address bar is the only place in the product where the user learns which
origin they are talking to. An omnibox that guesses navigation is a phishing
surface; an omnibox that renders an origin loosely is a worse one.

**Permitted**

- Theming the address bar with Sunshine design tokens, subject to
  `docs/DESIGN_SYSTEM_CONTRACT.md`, provided the security chip, the warning and
  danger states, and their contrast are at least as legible as the native ones.
- Placing it, sizing it, and adding invocation sources for existing native
  commands.
- Reading its state to render Sunshine chrome — for example, showing which
  workspace the active tab belongs to beside it.
- Focusing it from a Sunshine surface, leaving it empty for the user to type.

**Not permitted**

- Rendering a Sunshine-computed version of the URL, the origin, or the host —
  no "friendly" names, no de-emphasised registrable domain, no host shortening,
  no re-rendering of an internationalised host. Unicode-versus-punycode display
  is decided by Chromium's spoof checker and displayed verbatim.
- Eliding more than Chromium elides, or restoring what it elides on hover in a
  way that differs from native behaviour.
- Writing text into the address bar in response to anything a web page did, or
  pre-filling it with a destination the user did not ask for.
- Any Sunshine-computed security indicator on or adjacent to it. Security state
  comes from Chromium's security-state helper; `docs/SECURITY_CENTER_CONTRACT.md`
  SC-5 already forbids provider data reaching the omnibox, and this contract
  extends that to every Sunshine-derived signal.
- Suppressing, delaying, or re-styling an interstitial, a certificate warning, or
  a downgraded security state so that the address bar looks calmer than the
  navigation is.
- Any handler that accepts a URL or a text string from a WebUI page and
  navigates — see OS-9.
- Auto-committing on any signal other than an explicit user commit: no
  navigate-on-idle, no navigate-on-blur, no navigate-on-first-suggestion.
- Emitting the text. No telemetry event, log line, crash key, workspace record,
  session record, or diagnostic file may contain omnibox text, a partial query,
  a suggestion string, or a classification result. Command telemetry records
  that a command ran, never its input.

## 10. Interaction with tabs, workspaces, and split view

The result list can contain an **open-tab match** — "switch to this tab" — built
from the browser's open-tab matcher, which enumerates the tabs of the current
profile **[read: `components/omnibox/browser/tab_matcher.h`]**. Sunshine's
workspace model hides the tabs of inactive workspaces without destroying them
(`docs/TAB_WORKSPACE_SPLIT_CONTRACT.md`, invariant 4). Those two facts collide,
and no existing document resolves the collision.

| ID | Rule |
|---|---|
| OT-1 | An open-tab match for a tab in a non-active workspace must not silently activate a hidden tab. Committing it performs the workspace switch first — the same user-visible transition `workspace.switch` produces — and then activates the tab. One commit, one visible outcome. |
| OT-2 | Such a match must be visually attributable to its workspace before commit, so that OC-1 holds: the user sees that committing changes workspace. |
| OT-3 | Sunshine must not filter tabs out of the matcher to avoid OT-1. A user who has the page open should be offered it; hiding matches by workspace makes the omnibox lie about the browser's state. |
| OT-4 | An open-tab match for a tab occupying a split pane focuses that pane. It does not dissolve the split, does not swap panes, and does not re-navigate the pane. |
| OT-5 | Cross-profile matches do not exist: the matcher is profile-scoped, and a workspace never crosses a profile boundary. Sunshine must not join tab lists across profiles to enrich the result set. |
| OT-6 | Omnibox edit state is per tab and is saved and restored across tab switches by Chromium. A workspace switch must not carry one workspace's in-progress text into another, and must not persist that text to workspace or session metadata. |

## 11. The omnibox is not the command palette

Section 7.8 of the handoff introduces a command palette in Stage 3. It is a
separate surface. If commands are ever surfaced through the address bar, the
distinction that keeps this contract intact is:

- a second **parser** is prohibited — Sunshine must not interpret the text;
- a second **provider** is the only permitted mechanism — a native autocomplete
  provider that receives the already-parsed input and contributes matches.

Even then: such a provider must never change the default match for an input
Chromium typed as `URL`, must never outscore a navigation the user has typed in
full, and must contribute only commands already registered in
`first_party/commands.json`. No such provider exists, and none is authorised
here. Until one is reviewed, typing a command name searches, which is correct.

## 12. Prohibited duplicate state

Sunshine code must not introduce:

- a URL parser, scheme table, host validator, TLD list, IDN renderer, or fixup
  routine of its own;
- a Sunshine autocomplete index, typed-URL store, query history, suggestion
  cache, or "recently searched" list;
- a development-host allowlist, internal-network map, or port heuristic;
- a record of how an ambiguous input resolved, or any store that biases a later
  classification;
- an omnibox-text field in workspace metadata, session metadata, module state,
  telemetry, or crash reports;
- a navigation entry point that accepts a raw string from a WebUI surface, a
  module, or automation without classification.

Transient state is permitted only while a Sunshine surface is open, must be
invalidated by native observers, and must never become a source of truth.

## 13. Acceptance criteria

Runnable once a native build exists. Most of them pass on an unmodified pinned
build; that is the point — they test that Sunshine has *not* interposed itself.

**Classification corpus**

1. Every input in section 3 is classified on the pinned build and its input type
   recorded. Each row either matches or this document is corrected in the same
   change. The corpus is a checked-in fixture, not a prose table.
2. The full corpus is re-run with all Sunshine modules disabled. Input type and
   default match are identical in both runs (OC-2).
3. `github.com` produces a classified URL of `https://github.com/`; an
   http-only host reached the same way still loads, demonstrating that the
   upgrade retains its fallback and that Sunshine adds no forced scheme.
4. `https://github.com` commits to that origin and path with no host, port, path
   or query substitution; canonicalisation alone is accepted.
5. `localhost:3000` and a single-label host with a port both navigate over HTTP
   without a Sunshine allowlist present anywhere in the build.
6. `github.com@evil.example` searches by default; the offered navigation match,
   and the committed navigation if chosen, target `evil.example`, and the address
   bar shows `evil.example` as the origin. With the desired-TLD accelerator it
   navigates, and still shows `evil.example`.
7. An internationalised host that trips the spoof checker displays exactly what
   Chromium chooses to display, with no Sunshine transformation of the host
   string in the address bar, the tab title, or any Sunshine surface.
8. No omnibox input executes script in the current page's context, and no
   omnibox input reaches an internal surface that a browser-initiated navigation
   would not reach.

**Disclosure**

9. For 50 randomly drawn corpus inputs, the destination reached on Enter equals
   the destination shown as the selected match immediately before Enter (OC-1).
10. For an `UNKNOWN` input that searches, the navigation match and the
    accidental-search correction are both present and functional (OC-3).

**Paste and drop**

11. A URL broken across three lines on the clipboard is pasted and navigates to
    the rejoined URL; the clipboard content itself is unmodified.
12. Clipboard text beginning with a `javascript` schema, pasted and committed,
    navigates or searches but never executes.
13. Paste & Go invoked from every Sunshine-added surface states in advance
    whether it will navigate or search (OP-2), and no Sunshine gesture binding
    resolves to it (OP-3).
14. Text dragged from a web page onto the address bar never commits without an
    explicit user action.

**Internal scheme**

15. On a build without the scheme registered, `sunshine://security` searches —
    and this is recorded as the expected Stage 1 result, not a defect.
16. On any build where the scheme is registered: a page link, a script
    navigation, a redirect, a subframe, a `fetch`, and `window.open` to the
    scheme all fail (OS-2); the installer has registered no OS-level handler for
    it (OS-3); an unknown host yields a local error page and no network request
    to the search provider (OS-5); completion offers only compiled surfaces
    (OS-6).

**Tabs and workspaces**

17. A URL open in a tab of a non-active workspace produces an open-tab match
    labelled with that workspace; committing it switches workspace and activates
    the tab, with no duplicate tab created (OT-1, OT-2).
18. A URL open in a split pane focuses that pane; the split survives, panes are
    not swapped, and the pane does not reload (OT-4).
19. Typing into the address bar, switching workspace, and switching back
    restores the per-tab edit state; the text appears in no persisted Sunshine
    file (OT-6).

**Non-interposition**

20. A build-wide search of first-party sources finds no URL parser, TLD list,
    scheme table, or host validator, and no navigation call taking an
    unclassified string.
21. After a session exercising the whole corpus, no Sunshine-written file,
    preference, telemetry payload, or crash key contains any omnibox text.

**Roll gate**

22. At each upstream roll the paths in section 2 still exist or their
    replacements are identified — this surface has already moved once — and
    criteria 1–21 are re-run. A changed upstream classification blocks the roll
    for review; it is never corrected by adding a Sunshine rule.

## 14. Evidence and what was not verified

What was done: the classifier sources listed in section 2 were fetched over
HTTPS from the Chromium mirror at `refs/tags/152.0.7977.42` and read. Every
claim marked **[read]** — the type decision, the port and localhost clause, the
RFC 6761 special TLDs, the IPv4 component rules, the username clauses, the
desired-TLD interaction, the HTTPS-upgrade exclusions, the handled-protocol set,
the external-protocol path, and the paste-sanitisation semantics — comes from
that source text.

What was **NOT RUN**:

- no Chromium checkout, configuration, compilation, or link;
- no launch of any Sunshine or Chromium binary on any platform;
- no execution of any acceptance criterion in section 13;
- no visual, accessibility, localisation, keyboard, or theming verification of
  the address bar in any state;
- no measurement of any behaviour marked **[measure]**: provider scoring,
  default-match selection, navigation-stack blocking of `javascript`, `data`, or
  `view-source` inputs, or open-tab match behaviour;
- no downstream patch, first-party module, or command-registry change.

`NOT AVAILABLE`: no native build of the pinned revision exists in this
repository, so nothing above could be observed rather than read.

Any claim that Sunshine's omnibox behaves as described is unsupported until a
native build exists and criteria 1–22 have been run and recorded.

## 15. Decisions required from the product owner

| Priority | Decision | Required by |
|---|---|---|
| P0 | Is an internal `sunshine` scheme registered at all, or do first-party surfaces live under Chromium's existing internal scheme? OS-10 makes this a security decision, not a branding one. | before the Security Center surface lands |
| P1 | On committing an open-tab match for a hidden workspace, is the workspace switch automatic (OT-1) or must the user confirm it? | Stage 3 workspace wave |
| P1 | Is the default search provider chosen by the user at onboarding, or left at Chromium's locale-derived default? ADR 0002 forbids hardcoding one; it does not say who chooses. | Stage 1 onboarding |
| P2 | May commands ever appear in the omnibox as a provider (section 11), or is the palette the only command surface? | Stage 3 palette wave |

## 16. Completion gate

This contract is complete when reviewed. Section 5.3 of the handoff is complete
when the corpus fixture exists, criteria 1–21 have passed on a native pinned
build, and the roll gate in criterion 22 has run at least once. No part of it is
complete by virtue of Sunshine having written code, because the correct amount
of Sunshine code on this path is none.
