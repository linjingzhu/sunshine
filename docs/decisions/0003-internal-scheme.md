# ADR 0003: No internal `sunshine` URL scheme

## Status

Accepted. Settles the P0 in section 15 of `docs/OMNIBOX_CONTRACT.md` — "is an
internal `sunshine` scheme registered at all?" — and the apparent conflict
between sections 1.2 and 6.7 of the Stage 1–3 implementation handoff. It stands
under ADR 0002 and changes nothing in it.

## Context

Two shipped documents answer the same question two ways. Handoff section 1.2
excludes the `sunshine://` production App SDK from Stage 1–3. Section 6.7
requires a `sunshine://security` surface, which `docs/SECURITY_CENTER_CONTRACT.md`
then specifies in full. Section 6 of `docs/OMNIBOX_CONTRACT.md` separates the two
meanings — a closed, compile-time set of first-party pages versus dynamically
addressed app routes — binds any future registration with OS-1 through OS-10, and
declines to authorise one. The Security Center is blocked on this answer.

The current state is worse than either reading. At the pinned revision, `sunshine`
is absent from the handled-protocol set in `chrome/browser/profiles/profile_io_data.cc`,
so the scheme classifier in `chrome/browser/autocomplete/chrome_autocomplete_scheme_classifier.cc`
falls past that check, past the custom-handler registry, past the external-protocol
block state, and finally to the OS application registry; finding nothing, it yields
no type, and `AutocompleteInput::Parse` in `components/omnibox/browser/autocomplete_input.cc`
resolves the text as `UNKNOWN`. `UNKNOWN` searches by default. Typing
`sunshine://security` therefore sends the internal route name to the configured
search provider as a query string. That is a live leak of an internal surface name
off the machine, and it exists because the scheme is unregistered, not despite it.

The same function is why this is a security decision. Its last two branches consult
the external-protocol handler and, on Windows and macOS, `GetApplicationNameForScheme`.
An OS-level registration of `sunshine:` is therefore visible to the whole machine:
every web page in every browser, every mail client, and every native application
becomes a launcher for internal Sunshine routes. `docs/OMNIBOX_CONTRACT.md` OS-3
already records this as the highest-severity mistake available on this surface, and
nothing below reopens it.

What makes Chromium's own internal scheme safe is not the string `chrome`. It is a
set of registrations and gates that are separately maintained upstream, and were
read at the pinned tag:

- `content/common/url_schemes.cc` registers it as a standard scheme with a host,
  and places it on the secure, CORS-enabled, service-worker, and default-savable
  lists — each list a deliberate decision with security consequences.
- `content/public/browser/child_process_security_policy.h` is where request access
  and commit permission per scheme are granted; the internal scheme is withheld
  from renderers hosting web content rather than being safe by construction.
- `content/public/browser/webui_config_map.h` is the registration path for internal
  pages, and it admits exactly two schemes: `AddWebUIConfig` CHECKs the config is a
  `chrome://` one, `AddUntrustedWebUIConfig` CHECKs it is `chrome-untrusted://`.
  At this revision `chrome/browser/ui/webui/chrome_web_ui_controller_factory.cc`
  has been reduced to the DevTools frontend alone; every other internal page now
  arrives through that map.
- `chrome/browser/profiles/profile_io_data.cc` lists the internal scheme as handled,
  which is what makes a typed internal URL classify as `URL` and never as a search.
- `components/omnibox/browser/builtin_provider.cc` offers completion only for
  `about:` and for the embedder's representation of it, which the Chrome client
  resolves to `chrome`, matched against the compiled host list. It has no notion of
  a second internal scheme.

Registering `sunshine` reproduces none of that. It requires a Sunshine patch in each
of those shared files, which moves ownership of a browser trust boundary from
upstream to this repository and re-pays that cost at every roll — precisely the
patch budget ADR 0002 commits to keeping small. The omnibox contract's own decision
is that Sunshine ships zero lines on the classification path; a scheme registration
breaks that for the sake of a string.

The purchase is asymmetric. OS registration buys deep links from outside the
browser. No shipped document asks for that; the only thing shaped like a requester
is the App SDK, which handoff section 1.2 excludes. Internal registration buys the
address bar reading `sunshine://` instead of `chrome://`. Against that, hosting
first-party surfaces under Chromium's existing internal scheme obtains OS-5's
no-search-fallback and OS-6's compiled-surface completion for free, from code that
already exists and that upstream keeps correct.

The remaining argument for a Sunshine scheme is that it could be restricted to
compiled-in surfaces and never admit app routes. That restriction is not
enforceable, only promised: the Sunshine-owned host table that decides which routes
resolve is the same table an App SDK would extend, and adding a route to it is a
one-line change reviewed by the same people who wrote the promise. Under Chromium's
existing internal scheme the boundary is an upstream CHECK — a scheme that cannot be
registered by a module cannot be extended by one.

## Decision

**Sunshine registers no URL scheme. First-party surfaces are internal pages under
Chromium's existing internal scheme.**

- Add no `sunshine` entry to the standard, secure, savable, referrer, CORS-enabled,
  service-worker, empty-document, or handled-protocol registrations, and add no
  Sunshine scheme constant to `chrome/common/chrome_content_client.cc`.
- Contribute first-party surfaces as WebUI configs through the content-layer config
  map, and register their hosts in the compiled host list so the built-in completion
  provider and the internal-pages index find them without a Sunshine change to
  either.
- The Security Center is reached at `chrome://sunshine-security`. The wave that
  implements it verifies the host does not collide with the compiled host list at
  the pinned revision. A bare `security` host is rejected: `chrome/common/webui_url_constants.h`
  already uses that word for a settings sub-page, and two surfaces a user cannot tell
  apart is the failure mode a security page can least afford.
- Any future surface that must render content Sunshine does not compile uses the
  untrusted internal scheme, which is likewise available without a new scheme. It is
  not a route to relax `docs/SECURITY_CENTER_CONTRACT.md` SC-8.
- The Sunshine installer registers no `sunshine:` protocol with any operating
  system, on any platform, in any packaging format. No Sunshine code adds the string
  to a custom-handler allowlist or obtains it through `registerProtocolHandler()`.
  This holds unconditionally and is not contingent on the rest of this decision.
- OS-1 through OS-10 stay in force as the preconditions on any reversal. This ADR
  does not weaken them; it records that OS-10's fallback is now the chosen state
  rather than the failure state.
- The `sunshine://…` spellings in the handoff, `docs/SECURITY_CENTER_CONTRACT.md`,
  `docs/OMNIBOX_CONTRACT.md`, `docs/SIDE_PANEL_CONTRACT.md`, and
  `docs/BROWSER_UTILITIES_CONTRACT.md` are corrected by the waves that own those
  documents. This ADR edits none of them.

## Consequences

- The Security Center is unblocked. It needs a host, a WebUI config, and a
  first-party module manifest — no scheme work, no shared-component patch, and no
  new trust boundary. `first_party/modules/sunshine-new-tab/module.json` already
  targets an internal Chromium page, so this is the repository's existing practice
  made explicit rather than a new one.
- The `sunshine://security` string in the handoff and in the Security Center
  contract is not implementable as written and must be renamed. Nothing user-visible
  is lost except the brand in the address bar, which OS-10 already ruled is not a
  reason to open a trust boundary.
- The leak described above stops being reachable by the intended route, because the
  surface no longer has a `sunshine://` spelling to type. It is not fixed in
  general: any unregistered scheme a user types still searches, and Sunshine must
  not add a rule to prevent that. OMA-15 of `docs/OMNIBOX_CONTRACT.md`
  remains the correct expectation, and OMA-16 becomes unreachable rather than
  passing.
- Sunshine pages sit in the same namespace as Chromium's, so host names must be
  disambiguated by prefix and re-checked at every upstream roll for collision with
  newly added upstream hosts. This is the cost of the decision and it is small.
- Internal pages remain privileged. Arriving at one grants nothing: every privileged
  action goes through a registered command with a browser-side availability check,
  per OS-7 and OS-8 and `first_party/commands.json`.
- OS-1 needed a factual correction in its own document, and has it. It required
  the scheme be registered with "the same properties Chromium gives its own
  internal scheme: not web-safe, not a savable scheme". Those two clauses
  disagree: `content/common/url_schemes.cc` lists the internal scheme among the
  default savable schemes. The intent — withhold it from web renderers — was
  right; the savable clause was not a property of the scheme it cited. `.ai`-side
  note for anyone re-reading this ADR: the correction is already in
  `docs/OMNIBOX_CONTRACT.md`, which now states the properties as read and keeps
  the withdrawn clause visible. No further action.
- Reversal is possible but expensive by design. It requires a superseding ADR, the
  shared-component patches enumerated above, and evidence for OS-1 through OS-9 on a
  native build. Reversal for branding alone is refused in advance.
- Nothing here has been executed. No Chromium checkout, build, or run: `NOT RUN`.
  No native binary of the pinned revision exists in this repository: `NOT AVAILABLE`.
  Every Chromium claim above was read from the sources at the pinned tag and is
  cited by path.

## Open questions

| Priority | Question |
|---|---|
| P1 | Does Sunshine intend to ship a third-party App SDK addressed by scheme at all? This ADR is unaffected either way — privileged first-party surfaces must not share a namespace with third-party routes even if an SDK exists — but the answer decides whether a separate, much larger scheme decision is ever needed. Default if unanswered: no. |
| P1 | Is `chrome://sunshine-security` acceptable as the user-visible route, or has the product committed the `sunshine://security` string anywhere external? If it has, the commitment is withdrawn rather than the decision. |
| P2 | Should Sunshine internal hosts carry a common prefix as a rule, so upstream collision is structurally unlikely rather than checked per surface at each roll? |
