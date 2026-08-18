---
doc_id: security-center-open-policy-options
version: 1.0.0
canonical_path: docs/decisions/0010-security-center-open-policy-options.md
updated: 2026-08-18
---

# ADR 0010: Security Center open policy options

## Status

**Proposal — awaiting product owner decision.**

This document lays out the three P0 questions `docs/SECURITY_CENTER_CONTRACT.md`
records against itself. It does not settle any of them. Nothing here changes
the contract: SC-4, SC-5, SC-3, and SC-10 stand exactly as written until the
product owner answers, and this document names no new invariant identifier —
every SC-* and SCA-* citation below points at a rule the contract already
carries.

## Context

`docs/SECURITY_CENTER_CONTRACT.md` §"Unresolved product decisions" lists three
questions at P0 that the contract itself is not positioned to answer, because
each trades a piece of detection value against a privacy or architecture
invariant the contract also defends, and the contract's own stance is "an
implementer does not get to choose this." The `ThreatProtectionProvider`
abstraction (§"The `ThreatProtectionProvider` abstraction") is where all three
questions surface concretely: it defines the closed request shape, the closed
verdict vocabulary, and the failure behavior that a policy answer would have to
change without breaking SC-1 through SC-12.

Each section below states the tradeoff in both directions — what is gained,
what it costs, and which invariant carries that cost today — and closes with a
recommendation. The recommendation is this document's opinion, not a decision;
only the product owner can move the Status line above off "Proposal."

## Question 1 — Is origin-only egress accepted long-term?

### The rule today

The privacy contract's "Sent to a provider" list permits only scheme, host,
and port. "Never sent" states plainly that path, query, and fragment are
withheld, and that this "reduces the detection value of a path-aware
provider, and that cost is accepted deliberately rather than resolved by
sending the full URL." SC-4 forbids page content, form data, and similar
categories from leaving the browser under any verdict; it does not by itself
forbid a path, but SC-5 and the request-shape table in
"`ThreatProtectionProvider`" together make origin-only the *only* shape a
provider request may take — the Request table has no path field to populate,
so sending one is not a looser reading of the contract, it is a different
contract. SCA-4 is the acceptance criterion that would have to be rewritten if
this changed: it currently asserts the captured payload contains exactly
scheme, host, port, request reason, and contract version, "and nothing else."

### What is gained by staying origin-only

Paths and query strings are exactly the part of a URL shown, in this same
document, to "routinely carry session tokens, document identifiers, search
terms, and personal data." An origin-only request cannot leak a search query,
a document ID, a password-reset token, or a logged-in user's account path to a
third party, regardless of what the provider does with what it receives, and
regardless of whether the provider is later compromised, subpoenaed, or sold.
The privacy property holds even against a malicious or careless provider,
which is a stronger guarantee than any consent screen or contractual promise
from the provider could deliver, because it removes the data rather than
restricting its use.

### What it costs

Real phishing is frequently path-specific, not host-specific. A shared
platform — a form builder, a document host, free web hosting, a URL shortener,
a compromised page on an otherwise legitimate site — puts the malicious content
at one path while thousands of benign paths share the same origin. A
threat-protection provider that only ever sees `docs.example.com` cannot
distinguish the phishing form at `/forms/abc123` from the platform's own
marketing page at `/`, and either both are silently waved through as
`unknown`/`safe` at the origin, or the provider is reduced to a coarse
per-origin reputation source that adds little over what Safe Browsing already
does at the origin level. The contract already names this cost; it does not
currently name a mitigation.

### Options short of sending the raw path

- **Stay origin-only, permanently.** No contract change. Accepts that a
  provider adopted under this contract is, structurally, a host-reputation
  source and not a path-aware phishing detector, and that any provider whose
  product value depends on path visibility is not a fit for Sunshine.
- **A locally computed, non-reversible path signal.** For example, a salted
  hash of the path sent instead of the path itself, letting a provider that
  maintains its own hash-based blocklist match without Sunshine transmitting
  path text. This still moves data that was previously withheld, still needs a
  new field in the Request table above, and pushes the actual privacy question
  onto whether a hash of a low-entropy path (many phishing paths are short,
  templated slugs) is meaningfully different from the path itself once an
  adversary can guess-and-hash candidate strings — which for template-generated
  phishing kit paths is not hard. This would need its own accepted-risk
  analysis before it could be treated as satisfying SC-4/SC-5's spirit rather
  than evading it in form.
- **Path-aware egress with a stricter opt-in.** A second, explicitly
  higher-consent opt-in tier — distinct from the SC-7 opt-in that already
  gates origin-only egress — that a user affirmatively selects to trade path
  privacy for stronger phishing coverage, off by default, described in
  concrete terms ("this provider will see the exact page address you visit,
  including any part of it") rather than folded into the existing provider
  toggle. This is the only option that gives a provider real path visibility
  without silently widening what "opted in" was understood to mean at the time
  of the SC-7 consent the contract already requires.

### Recommendation

Keep origin-only egress as the default and the only tier most users ever see.
The cost the contract already accepts — reduced detection for path-specific
threats — is real, but it is a bounded, known cost, while path egress is an
unbounded one: once a path can leave the browser under some condition, every
future provider integration inherits the burden of proving its condition is
narrow enough. If path-specific detection is judged worth pursuing, it should
be the second option above (a distinct, explicitly named consent tier), never
a widening of the existing opt-in's meaning, and never a default. A locally
computed path hash is not recommended as a shortcut around that consent
question: it changes the transmitted bytes without changing the underlying
decision, and dressing that decision as already-answered by SC-4/SC-5 would be
the wrong way to reach it.

## Question 2 — What may a provider `block` verdict actually do?

### The rule today

SC-10 holds a `block` verdict at "the strongest treatment that a recorded
product policy permits, and today that is an attributed advisory beside the
Chromium rows." The verdict-meanings table under "`ThreatProtectionProvider`"
restates this identically: `block`'s permitted effect is "the strongest
treatment a recorded policy permits, which today equals `warn` with stronger
wording." SC-1 is the ceiling this can never cross in the other direction —
severity may only move in the direction Chromium already chose, or not at
all — but SC-10 is the one that currently caps how far a `block` verdict may
move *against* the user's browsing, and today it caps that at wording alone.

### What a stronger treatment would buy

An advisory beside the Chromium rows is easy to miss: it is not modal, it does
not interrupt navigation, and a user who never opens
`chrome://sunshine-security` never sees it. A provider that has identified a
URL as known-bad — not merely elevated-risk, which is what `warn` already
covers — has, in the strongest read of its own verdict, a claim comparable to
what triggers a Safe Browsing interstitial. Treating `block` identically to
`warn` in effect (only in "stronger wording") arguably wastes the one
distinction the verdict vocabulary draws between "elevated risk" and "known
bad," and a user who would have wanted to see a real interruption for a
known-bad URL gets the same easy-to-miss advisory as for a merely elevated-risk
one.

### What it costs

Every treatment stronger than an advisory is a second blocking path beside
Chromium's own, and the entire contract is organized around there being
exactly one decider. SC-1 forbids a provider from relaxing a Chromium
decision; nothing in the contract symmetrically forbids a provider from
*creating* a decision Chromium never made, and that asymmetry is exactly the
gap SC-10 exists to close from the other side. An interstitial-equivalent
triggered by a third-party provider's `block` — even one that only fires
alongside an already-clean Chromium verdict — makes Sunshine a second
authority over whether a page loads, contradicts "The one rule this document
exists to protect" ("The Security Center is a reader of Chromium security
state. It is never the decider"), and reopens SC-2's critical-path
prohibition: a provider whose `block` verdict can stop a navigation is, by
definition, now on the critical path, not advisory. A false-positive `block`
from a provider Sunshine does not control would then cost the user a working
site, with no Chromium-owned override path, since SC-9 forbids the Security
Center from performing its own security-relevant mutation and the contract
names no provider-driven proceed/undo flow.

### Options

- **Keep `block` at "advisory with stronger wording," permanently.** No
  contract change. Preserves the one-decider rule without qualification.
- **A more prominent, but still non-blocking, `block` treatment.** For
  example, a `block` advisory that also raises a passive browser-chrome
  indicator (comparable in visibility to an existing non-modal security
  indicator, not a new interstitial) so a `block` is less easily missed than a
  `warn`, while never gating the navigation itself. This stays inside SC-2 and
  SC-9 as written, and only stretches SC-10's "today that is" clause to cover
  a difference of visibility, not of authority.
- **A Chromium-owned, opt-in, per-provider blocking policy — the only path
  that could ever justify an actual navigation-time stop.** This would need to
  be an explicit, separately recorded product policy (the condition SC-10
  already names as the only route to anything stronger), gated by its own
  opt-in distinct from "provider enabled," defaulting off, and implemented so
  that the stop is attributable to a named, disableable policy rather than to
  an unconditional property of `block`. Even then it would need a Chromium-side
  proceed affordance comparable to what Safe Browsing itself offers, because a
  block with no override is a worse failure mode than the interstitials it
  would be imitating.

### Recommendation

Do not authorize any treatment that gates or delays a navigation. The
product-approved condition SC-10 leaves open should be read narrowly: a
`block` verdict may earn more visual weight than a `warn` (the second option),
but should not earn veto power over browsing, because veto power is the one
thing "The Security Center is a reader... It is never the decider" was written
to foreclose. If a genuine navigation-time stop is ever wanted for a
`block`-equivalent signal, the right home for it is Safe Browsing's own
extensible-list mechanisms or a Chromium-side policy, not a Sunshine-side
second interstitial layered beside them — because only the former keeps a
single decider.

## Question 3 — Should any strict, fail-closed policy exist?

### The rule today

SC-3 fails open unconditionally today: "Provider failure — error, timeout,
unreachable host, network disabled, provider disabled, off-the-record context,
malformed response — returns `unknown`, records one local event, and allows
normal browsing." Its final sentence already anticipates this question:
"Failing closed is permitted only under a separately recorded strict policy,
and no such policy exists today." SCA-3 is the acceptance criterion that
enumerates the failure modes this must hold for; a fail-closed policy would
need its own parallel criterion, not a silent edit to SCA-3.

### What fail-closed would buy

Fail-open means a provider that is down, slow, network-disabled, or simply
misconfigured is indistinguishable, from the user's perspective, from a
provider that checked and found nothing — both read `unknown`, both allow
normal browsing. For a context where the product has promised a specific
protection is active (for instance, a managed deployment whose policy states
that a given provider is a required control, not an optional advisory),
silent fail-open converts an outage into an invisible protection gap: the user
believes the control is running because nothing on the page says otherwise. A
scoped fail-closed policy would let such a context refuse to proceed, or at
minimum visibly flag "protection unavailable" rather than showing nothing,
when the provider it depends on cannot be reached.

### What it costs

Fail-closed is the direction SC-2 exists to prevent by default: "A slow,
hostile, or absent provider must not delay, cancel, or reorder browsing." Any
fail-closed policy necessarily puts the provider back on the critical path for
whatever it governs — a provider that can block browsing when it fails is a
provider whose reachability now gates browsing, which is precisely the
coupling SC-2 was written to rule out, and which SCA-2's timing-parity
acceptance test was written to catch. It also directly undermines SC-12,
which requires that disabling the module or every provider "leave ordinary
browsing... fully operational": a fail-closed policy scoped broadly enough
would make browsing depend on a first-party module staying reachable, which is
a materially different product than "advisory security signals with normal
browsing continuing regardless." A provider outage, a network blip, or a
misconfigured allowlist entry would now be capable of stopping browsing
entirely for whatever scope the policy covers — a considerably larger blast
radius than the advisory the rest of this contract restricts providers to.

### Options

- **No fail-closed policy, ever.** SC-3 stands as the permanent behavior for
  every context, including managed deployments. Simplest to verify, and the
  only option that keeps SC-2 and SC-12 unconditional rather than
  context-dependent.
- **A narrowly scoped, opt-in fail-closed policy for managed/enterprise
  contexts only**, activated exclusively by an explicit enterprise policy
  value (comparable to how the "Managed-policy security state" row already
  requires showing policy-sourced state as policy, never as a user choice),
  never reachable through ordinary user settings, and never the default even
  in a managed profile. This is the reading SC-3's own final sentence leaves
  room for — "a separately recorded strict policy" — and it would need SC-2 and
  SC-12 to be explicitly re-scoped ("...unless a recorded enterprise fail-closed
  policy is active for this profile") rather than silently overridden, plus a
  new SCA-level acceptance criterion verifying the failure still resolves to a
  visible, attributable state rather than an unexplained hang.
- **A visible-but-not-blocking degraded state**, short of fail-closed: on
  provider failure, still allow normal browsing exactly as SC-3 requires
  today, but let a policy-designated context surface a persistent, honest
  "protection unavailable" indicator instead of silently reading `unknown`.
  This addresses the invisible-gap problem in the fail-closed motivation above
  without touching SC-2 or SC-12 at all, because nothing about browsing is
  delayed, cancelled, or reordered — only the honesty of the Security Center's
  own display changes.

### Recommendation

Do not introduce fail-closed behavior for ordinary, consumer, non-managed
profiles under any condition — SC-2 and SC-12's guarantees are worth more than
the protection-gap problem fail-closed would solve for that population, and
SC-11's honesty requirement already gives a cheaper answer: say plainly that
protection is unavailable rather than pretend to enforce it. If a managed
context is later judged to need real fail-closed behavior, it should be the
second option — an explicit, enterprise-policy-gated exception with its own
acceptance criterion — never a change to SC-3's default. The third option (a
visible degraded state, still fail-open) is the recommended first step
regardless of what happens to the other two questions, because it improves the
exact honesty gap fail-closed is usually reached for, at no cost to SC-2 or
SC-12.

## Consequences of leaving these open

None of the three questions blocks Stage 1 work that does not touch a live
provider: the WebUI shell, the SC-11 availability read, and the event-log
scaffolding described as unbuilt in `docs/SECURITY_CENTER_CONTRACT.md`'s "Not
verified" section do not depend on any of these answers. They do block
`ThreatProtectionProvider`'s first real implementation and SCA-4 through
SCA-6, which cannot be finalized while the request shape, the verdict's
permitted effect, and the failure-mode contract remain open questions rather
than settled ones. This document does not change that: it narrows the option
space for the product owner, and nothing more.
