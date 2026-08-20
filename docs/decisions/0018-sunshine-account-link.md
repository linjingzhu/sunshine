---
doc_id: adr-0018-sunshine-account-link
version: 1.0.0
canonical_path: docs/decisions/0018-sunshine-account-link.md
updated: 2026-08-20
---

# ADR 0018: An account link that is not a browser identity

## Status

**Accepted. Not implemented.** The plan is `docs/ACCOUNT_LINK_PLAN.md`; the rules
it must not break are `docs/PROFILE_ONBOARDING_CONTRACT.md` §4 and §5.

This ADR exists because that contract requires it to. PO-R3 permits Sunshine to
gain an identity only if five preconditions hold simultaneously, and the first
is "a reviewed ADR". This is it, and §5 below discharges the fifth as well.

## Context

`docs/PROFILE_ONBOARDING_CONTRACT.md` §12 has carried a P0 since it was written:

> Is a **permanently** account-free browser the product, or is local-only the
> Stage 1 state of a browser that later gains an identity?

**The owner has answered the second**, and then answered five further questions
that decide what the identity is. This ADR records the answer and the reasoning
that makes it safe, because the contract's own §4 is emphatic that "linking
Google" is three different mechanisms and that conflating them "is the mechanism
by which a local-only browser quietly becomes a signed-in one".

## Decision

### 1. What is being added is a fourth thing

The contract's three are L1 (a tab signs in to a Google property), L2 (the
browser holds a primary account), and L3 (sync-the-feature). **This is none of
them.**

**L4 — a Sunshine application link.** An ordinary OAuth 2.0 authorization that
Sunshine holds the way any desktop program holds one. The profile keeps no
primary account at either consent level; Chromium's identity manager is not
involved; no refresh token enters the profile's token database.

The distinction is not a technicality. It is the difference between *the browser
is signed in* and *a program on this computer has permission to talk to an
account*, and every rule below exists to stop the second becoming the first.

### 2. The five decisions

| | | |
| --- | --- | --- |
| **Optional forever** | No module and no feature may require a link. | PO-2 stays true; §3 of the contract keeps describing a complete path rather than a degraded one. |
| **Normal tab, account choice forced** | The authorization page renders in an ordinary tab with `prompt=select_account`. | Google never silently continues with whatever session is already there, so a person with several accounts cannot link one they never saw. |
| **`openid` and `email`, nothing else** | Identity only. | No Google app verification is required, and the consent screen reads as one line. |
| **Per profile** | The credential is keyed to the profile. | Matches what profile deletion must destroy, and keeps profile isolation true. |
| **Settings only** | No first-run card, no banner. | The one moment PO-6 is easiest to break is the moment a card would appear. |

### 3. What this supersedes, and what it does not

**ADR 0002 is not superseded.** PO-R3's precondition names "the relevant part of
ADR 0002", written when the expected shape of an identity was Chrome's. ADR 0002
forbids *Google Chrome proprietary* branding, API keys and internal assets, and
forbids hardcoding a public web URL as the startup page. **A Sunshine OAuth
client is none of those.** The precondition is met by showing ADR 0002 untouched
rather than by overriding it, which is the stronger of the two outcomes.

**One sentence of PO-R8 is narrowed.** It reads "Sunshine operates no
browser-level OAuth of its own", and its next sentence already anticipated this
one: *if one is ever proposed, it does not reuse the identity manager, the
profile's token database, the account reconcilor, or the profile's cookie jar;
it is a separate credential in the OS credential vault, and it grants no access
to browsing data.* **Those four prohibitions and two requirements are adopted
here unchanged.** What is narrowed is only the first sentence's "no".

**PO-R1 through PO-R7, PO-R9 and PO-R10 are untouched**, and PO-R2 in
particular remains unconditional: account consistency stays off, and no patch,
switch, flag, build argument or credential may enable it.

### 4. Why a Sunshine credential cannot re-enable Chrome's sign-in

This is the load-bearing claim, so it is a chain rather than an assurance, read
at the pinned revision:

1. `google_apis/google_api_keys.h` declares `HasAPIKeyConfigured()` and
   `HasOAuthClientConfigured()`, both of which report on the **keys baked into
   `google_apis`** — Chrome's — and both of which return false when the build
   has the dummy values, which a Sunshine build does.
2. `chrome/browser/signin/account_consistency_mode_manager.cc` makes Desktop
   Identity Consistency conditional on that predicate; its own comment is "By
   default, DICE is not enabled in builds lacking an API key".
3. The same constructor writes the result into the profile's signin-allowed
   preference, and the consistency computation returns disabled when it is false.
4. `chrome/browser/ui/startup/first_run_service.cc` reads a false signin-allowed
   preference as the enterprise `BrowserSignin=0` state and suppresses the
   first-run experience entirely.

**A Sunshine client id lives in a Sunshine constant, not in `google_apis`.** It
is invisible to steps 1 and 2, so the chain is unchanged: no Dice, no browser
sign-in, no sync, no first run. That is why L4 is safe in a way that
"configuring an API key" would not be, and it is why §5 of the plan puts the
credential under a name of its own and never Chrome's.

### 5. Precondition 5 — the re-derivation

PO-R3 also requires "a re-derivation of §5 and §6 against the revision in force
at that time". The revision in force is `152.0.7977.42`, unchanged since those
sections were derived on 2026-08-17, and §4 above re-reads the four files their
conclusions rest on. Both sections hold as written.

**When the pin moves, this precondition is owed again.** It is not discharged
once. `scripts/measure_rebase_cost.py` will say what the roll costs the patch
stack; it says nothing about whether this chain still holds, and that has to be
re-read by a person.

## Consequences

**A new obligation on a contract this ADR does not own.** PO-12 requires profile
deletion to destroy "all Sunshine metadata keyed to that profile". A credential
in the OS vault is exactly that and does not live under the profile directory,
so Chromium's own deletion will not remove it. **Deleting a profile must revoke
and delete its link**, with the same offline behaviour as unlinking: the local
delete happens whether or not the revocation reaches Google. PO-A10's fixture
list should gain a linked account.

**The guard grows rather than relaxes.** `scripts/verify_account_freedom.py`
keeps refusing every credential and every Chrome key argument, unchanged. Two
rules are added with the code: the tree still contains no credential, and the
account-link source reaches none of Chromium's identity surface.

**A build made from this repository does not offer the link.** The client id
arrives at build time from the release pipeline. That is not a limitation to be
worked around — it is the same rule every other credential already follows, and
it means the feature is *absent* in a community build rather than broken.

**The link is worth little until something uses it.** Module entitlement was the
obvious first use and "optional forever" removes it, because entitlement is a
requirement wearing another word. What is left is identity that makes something
better and nothing possible. That is a real consequence of the owner's own
answer and is recorded rather than argued with.

## NOT VERIFIED

- **No code exists**, and no OAuth client exists. No Google Cloud project has
  been created and no consent screen configured, so nothing in the plan has been
  exercised end to end.
- The chain in §4 is read from source at the pinned revision. It has not been
  observed in a running browser, and PO-A6 — the gate that would observe it — is
  `NOT RUN` along with 41 others.
- Whether Google's endpoints accept an authorization request from this browser,
  whose user agent is upstream's unmodified one, is an assumption.
- The Windows credential store has not been touched. Which API is used, and
  whether the credential survives a Windows account migration, are unexamined.
