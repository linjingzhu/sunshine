---
doc_id: adr-0011-ai-credential-broker
version: 1.0.0
canonical_path: docs/decisions/0011-ai-credential-broker.md
updated: 2026-08-18
---

# ADR 0011: An AI-credential broker, shaped but not built

## Status

**Proposal — awaiting product owner decision.** This document designs the shape
a centralised AI-service credential broker would take if the product owner
decides Sunshine should store AI API keys centrally at all. It does not decide
that question, and nothing in it is implemented, scheduled, or authorised by
its own existence.

## Context

The product owner asked whether the browser should centrally store AI-service
API keys — the kind a module would use to call an external model provider —
and let modules use them without each module holding its own copy.

`docs/SECURITY_ARCHITECTURE_CONTRACT.md` already has a load-bearing answer to
the *shape* of that question, decided before this ADR and not reopened by it:

> SEC-7: A module never receives a credential. It requests an operation; the
> broker holds the secret.

This is not aspirational. `scripts/validate_first_party_modules.py` enforces it
today, at the manifest level, for every first-party module:
`credentials.direct_access` must be `false`, and any other value is refused
permanently. No module in this repository is allowed to declare that it holds
a credential directly, which means no module can be holding one on the day an
AI-key broker arrives — the manifest rule closed that door before the broker
existed to need it closed.

What SEC-7 does not do is say what the broker *is*. Section 5 of the same
contract sketches the shape and marks it `DEFERRED`:

> ```text
> Module → request operation → Broker → permission, scope, validation →
> resource
> ```
>
> Concrete brokers — file, GitHub, NAS, credential — are deferred with their
> subjects.

Section 6, "AI security", is also `DEFERRED`, and states two rules now because
retrofitting them later is not possible: intent and execution are separate (an
AI layer proposes, a broker decides whether to execute), and web content is
data, never instruction. Neither rule is credential-specific, and neither is
revisited here.

An AI-key broker is one of the concrete brokers section 5 named and deferred.
This ADR is what a reader of section 5 and section 6 needs before proposing
one: a design that satisfies SEC-7 exactly, without inventing a second
permission vocabulary or a second credential-storage mechanism where a working
one already exists in the tree.

**Precedent this design follows.** `docs/SECURITY_CENTER_CONTRACT.md` already
settled, for a different kind of external call, how much a Sunshine broker may
send off-device: scheme, host, and port only, no path, no query, no stable
per-user identifier (SC-4, SC-5, SC-6). That restraint was not free — SC-4's
own text accepts that origin-only egress "reduces the detection value of a
path-aware provider" and pays that cost deliberately rather than resolving it
by sending more. An AI-key broker faces the same tradeoff in a more dangerous
form, because what it protects is not an opinion about a URL but a bearer
credential, and this design inherits that restraint rather than re-deriving
it.

## Proposal

### 1. One-time key registration

The user registers a provider API key through a settings surface — a page in
the same family as `chrome://sunshine-security`, reached from browser
settings, not from any module. Registration is a conceptual flow, not an
implementation:

1. The user picks a supported provider from a fixed, Sunshine-maintained list
   (the list is data, not a module capability — a module cannot add a provider
   to it, only request a grant against an entry already on it).
2. The user pastes or enters the key. It is never echoed back in full once
   stored, the way a saved password field is never re-displayed as typed text.
3. The browser stores it (see Storage, below) and records that the key exists,
   which provider it is for, and when it was added. It does not record the key
   value anywhere but the encrypted store.
4. Nothing is granted to any module by registration alone. Registering a key
   makes it *available to be granted*; it authorises no call on its own. This
   mirrors how a saved password does not itself authorise autofill on a site
   the user has not visited — possession and authorisation stay separate acts.

Registration is a one-time act per key, and re-keying (rotation) is the same
flow: enter a new value, which replaces the stored key without touching any
grant. A grant references *the provider*, not *the key value*, which is what
makes rotation an operation on storage alone — see Consequences.

### 2. The grant model: per-module × per-provider, revocable like a permission

A grant is a triple: **(module id, provider id, host allowlist)**. It is not a
copy of the key — the module never receives one, matching SEC-7 exactly — it
is a standing authorisation the broker consults before it will act on the
module's behalf.

```text
Module → "call provider P with this request" → Broker
Broker  → checks: does (module, P) have a live grant?
        → checks: is the target host in P's declared allowlist?
        → if both hold: broker attaches the credential, makes the call,
          returns the provider's response to the module
        → if either fails: refusal, no call made
```

The module's manifest declares which providers it *wants* to call — the same
place `security.credentials` already lives, extended in spirit the way
`security.network.allow` already extends `security.network.access` (schema
change is explicitly out of scope; see below). The grant itself is a user
decision, presented like any other permission: which module, which provider,
revoke individually. Revoking one grant does not touch the stored key or any
other module's grant against the same provider — this is the "independently
revocable" property the product owner asked for, and it is what makes the
model closer to a capability grant than to a shared secret.

**The module never sees the key, in either direction.** It sends the broker a
request (prompt, parameters, target endpoint within the allowlisted host); it
receives back the provider's response (completion, embedding, whatever the
call produces) or a refusal. There is no code path by which the raw credential
value crosses into module-reachable memory, storage, or logs. This is not a
new invariant — it is SEC-7, applied to one more resource class the way it is
already applied to every credential the module security contract covers.

### 3. Storage: reuse OSCrypt, and accept its ceiling honestly

**Recommendation: store AI keys the same way Chromium already stores saved
passwords and cookies — through OSCrypt**, the platform-backed encryption
Chromium ships and Sunshine inherits as a native downstream. This repository
has already paid once for building a parallel implementation of something
Chromium owned (the Sunshine split-view model, retired in
`docs/TAB_WORKSPACE_SPLIT_CONTRACT.md` after
`docs/decisions/0002-native-chromium-downstream.md` had already forbidden
exactly that shape). Inventing a second at-rest encryption scheme for one more
category of secret would be the same mistake at the layer that can least
afford a second implementation of "how do we keep a secret."

**What this means, stated rather than hidden:** OSCrypt's protection is tied
to OS-level user-account protection — on the platforms Chromium ships for, the
key material is ultimately reachable by anything running as the same OS user
that unlocked the profile. That is exactly the threat ceiling saved passwords
already live under today. Storing AI keys the same way does not lower that
ceiling and does not raise it — **the AI-key store inherits precisely the
same exposure a compromised user account already has against every saved
password and cookie in the browser.** A privilege escalation or malware
foothold that can already read Chromium's password store gains AI keys too,
at no additional cost to the attacker.

This is a real limitation and this ADR names it rather than presenting
centralisation as costless. See *Blast radius*, below, for what follows from
it once keys are aggregated rather than scattered.

### 4. Egress scoping: reuse the module network allowlist, do not build a second one

SEC-6 already states the rule this broker needs: *"Module network access is
`deny` unless an allowlist of concrete hosts is granted. Wildcards are not
hosts."* A granted AI-provider call is network access like any other, and it
gets no exemption from that rule.

Concretely: a grant for (module, provider) is only usable against the exact
host(s) the provider's own allowlist declares — e.g. a grant for provider
`anthropic` authorises calls to `api.anthropic.com` and nothing else, the same
way a module's `network.allow` list today would (once `allowlist` access is
itself unblocked, which it is not yet — schema 2 refuses `allowlist` "until a
host-allowlist contract exists," and this ADR does not change that). A module
cannot use a valid grant to reach a host the provider allowlist does not name,
even a different endpoint operated by the same company, without that host
being added to the declared list the same way any other module host addition
would be reviewed.

This is a second application of the existing mechanism, not a second
mechanism. A future AI-key broker's manifest surface should extend
`security.network` the way it already exists, not define a parallel
`security.ai_providers.hosts` field that means the same thing in different
words.

### 5. Logging: mirror SC-4/SC-5's restraint exactly

What the broker must never log:

- **Prompt content.** The text sent to the provider, in any form — full,
  truncated, hashed for "debugging," or reconstructed from a cache. This is
  the direct analogue of SC-4's prohibition on page content, form data, and
  request bodies leaving the browser for a threat-protection provider; here
  the same content is *leaving the device for the AI provider by design*, but
  it must never *also* land in a local or remote Sunshine log. A log entry
  that captured what the user asked an AI model is a second copy of
  potentially sensitive data with a longer retention story than the user
  agreed to.
- **The response content**, for the same reason, symmetrically.
- **The key value**, under any circumstance, including an error path. A
  broker that logs a credential on failure because the failure path was
  written less carefully than the success path is a known failure shape and
  is excluded by construction, not by review diligence.

What the broker may log, matching the metadata SC-4/SC-5 already allow through
for threat-protection egress:

- timestamp of the call;
- which module made the request and which provider it targeted;
- byte count of the request and of the response (not their content);
- outcome: succeeded, refused (and which check refused it — no grant, host
  not allowlisted, rate limit, provider error), or provider-side error code.

This is deliberately the same shape as SC-4/SC-5's "closed vocabulary" —
metadata that lets an owner audit *that a module called a provider N times
today* without ever letting that log reconstruct *what was asked*. A log that
can answer "did module X call provider Y" but never "what did module X ask
provider Y" is the property being designed for here, and it is the same
property the Security Center's event log already has toward browsing history:
references to what happened, never a second copy of the content.

### 6. Rate and spend limiting as broker-level defense in depth

A grant scopes *which* provider a module may call and *at which host*; it does
not by itself bound *how much*. A module that is compromised but still
correctly scoped — its grant is real, its allowlist is correct, no key has
leaked — can still exhaust a user's provider quota or run up billable usage
simply by calling a lot, faster than a human would notice. Stealing the key is
not the only way to turn a grant into cost.

The broker should therefore enforce, independent of and in addition to the
grant/allowlist check:

- a rate limit per (module, provider) grant — calls per minute/hour, sized so
  ordinary use is unaffected and abuse is bounded quickly;
- an optional user-configured spend or call-volume ceiling per grant, past
  which the broker refuses further calls until the user raises it;
- visibility of both, on the same settings surface where the grant itself is
  managed, so "how much can this module do to my bill" is not a hidden
  default — the same disclosure discipline SC-7's "user-visible purpose"
  requirement already establishes for provider network access elsewhere in
  this project.

This is defense in depth specifically because it protects against a threat
the grant model does not: a module that never touches the raw key at all, and
therefore never has anything to steal, but still has an unmetered ability to
spend through it.

### 7. Blast radius: name the tradeoff, do not sell centralisation as free

Centralising keys behind one broker makes rotation and revocation easier: one
place to change a key, one place to see and cut every grant against it,
instead of hunting through however many sites and modules independently held
a copy. That is real, and it is the whole argument for doing this at all.

**It is also, honestly, the other half of the same coin.** Under the
scattered status quo, a stolen browser profile yields whatever AI keys
happened to be entered into whatever sites the user used directly — a subset,
often a small one, of the provider accounts the user actually has. Under a
centralised broker, a stolen profile — meaning the same OSCrypt-protected
store already discussed in *Storage*, above — yields **every AI provider key
the user has ever registered, in one extraction**, regardless of which
modules were ever granted access to which of them. Registration and grant are
separate acts, but theft of the underlying store does not respect that
separation: the store holds the keys, not the grants, and an attacker reading
the store reads all of them at once.

Centralisation therefore trades a diffuse, inconsistent exposure (whatever was
scattered, easy to forget, hard to rotate) for a concentrated one (everything,
in a single well-known store, easy to rotate but a single high-value target).
This is not a reason not to build it — the scattered status quo is not
actually safer, it is only less legible, and rotation/revocation ease is a
genuine security property, not just a convenience one. But it is not a pure
win, and the product owner should decide with this tradeoff stated plainly,
not discover it after the fact.

## Out of scope

This ADR is a design proposal for a shape. It does not include, and none of
the following is authorised by this document:

- **The broker implementation.** No process architecture, Mojo interface,
  C++ class, or storage code. Section 5 of the security contract keeps its
  `DEFERRED` status; this ADR is the design that status was waiting on, not
  the thing that closes it.
- **The manifest schema extension.** Schema 2 (`first_party/modules/*/module.json`)
  is unchanged. Whatever field eventually expresses a module's declared
  provider grants is future schema work, reviewed and validated the way
  schema 2 itself was — this document only argues it should extend
  `security.network`/`security.credentials` rather than invent a parallel
  vocabulary, per SEC-4's rule against a Sunshine-owned capability namespace
  and per ADR 0006's warning against a second permission vocabulary in the
  security layer.
- **The settings UI.** No mockup, no page route, no WebUI config. "A settings
  surface" above is a conceptual placement, not a `chrome://` host proposal —
  that belongs with the WebUI seam work in `docs/decisions/0007-module-contribution-seam.md`
  when and if this is built.
- **Which providers are supported**, and any commercial or licensing question
  about them. Out of scope the same way `docs/SECURITY_CENTER_CONTRACT.md`
  leaves "which threat provider" as an open P1.
- **Whether AI features are built at all.** `docs/SUNSHINE_OS_STAGE_1_TO_3_IMPLEMENTATION_HANDOFF.md`
  line 697 forbids adding AI features while the Stage 1–3 gates remain open.
  This ADR does not reopen that gate; it exists so that if and when the gate
  opens, the credential question does not have to be designed from nothing
  under schedule pressure.

## Consequences, if this proposal is later adopted

- SEC-7 continues to hold by construction, the same way it holds today: no
  manifest field this design implies would let a module declare
  `credentials.direct_access: true`, and the existing validator's refusal of
  any value but `false` does not need to change for this to work.
- Key rotation becomes an operation on the store alone. Because a grant
  references the provider, not a copy of the key, replacing a stored key
  during registration re-keys every module holding a grant against that
  provider without touching a single grant record.
- Revocation becomes independently scoped by construction: revoking
  (module A, provider P) leaves (module B, provider P) and every grant module
  A holds against other providers untouched, because the grant is the unit of
  revocation, not the key.
- Every AI-provider call a module makes becomes visible on the same kind of
  surface `chrome://sunshine-security` already establishes for other
  security-relevant activity — an audit point that scattered per-site keys
  never had, and that a user could not get today even if they wanted it.
- The threat model gains a new single point of concentrated value — the key
  store — which did not exist as a single object before. Whatever operational
  posture already protects the OSCrypt-backed password store (the same OS
  account boundary, no more and no less) becomes the operative posture for
  every configured AI key too, per *Storage* and *Blast radius* above.
- Nothing here is buildable yet. This ADR unblocks a future schema and broker
  proposal from having to re-derive the shape; it does not unblock the Stage
  gate that presently forbids building it.

## Alternatives considered

**Per-site keys, status quo, no broker at all.** Rejected as the long-term
answer because it is exactly the scattered, hard-to-rotate, hard-to-audit
state *Blast radius* describes as the cost being traded away — not because it
is unsafe on its own terms. It remains available by doing nothing, and is the
correct interim state while AI features remain out of scope entirely.

**A per-module credential store instead of a broker (SEC-7 relaxed).**
Rejected outright, not weighed against the broker on convenience grounds.
SEC-7 is enforced today at the manifest level for every existing credential
class; carving out an exception for AI keys specifically would mean two
credential models in the same manifest, one of which a compromised renderer
could reach directly. This is precisely the "second permission vocabulary"
failure ADR 0006 warns the security layer is "most exposed to," applied to
storage instead of permissions.

**A new, Sunshine-authored encryption scheme for AI keys specifically.**
Rejected for the same reason a Sunshine split-view model was retired in favour
of Chromium's native one: OSCrypt is a reviewed, platform-integrated
implementation this project already ships and already trusts for a more
sensitive class of secret (saved passwords). `docs/SECURITY_ARCHITECTURE_CONTRACT.md`
section 11 already lists "a cryptographic algorithm" among the non-goals for
this project, for exactly this reason.

**A new host-allowlist mechanism scoped only to AI providers.** Rejected in
favour of extending SEC-6's existing module network allowlist. A second
allowlist mechanism next to the first is the same kind of duplication ADR
0007 found expensive when two WebUI surfaces both tried to touch the same
seven upstream files independently — here the risk is a security check that
exists twice, in two places a reviewer has to remember to keep in agreement,
rather than an upstream patch collision, but the shape of the mistake is the
same.

**Full URL / path-aware egress to providers, rather than host-only scoping
under the grant.** Not proposed. `docs/SECURITY_CENTER_CONTRACT.md`'s SC-4/SC-6
already made this call for a different broker and accepted the detection cost
deliberately; nothing about AI-provider traffic makes the argument for sending
more identifying detail stronger, and a credential-bearing call is a higher
consequence context to be sending extra detail from, not a lower one.
