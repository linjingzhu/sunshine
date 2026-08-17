# ADR 0005: The missing-API-key warning, and what it was warning about

## Status

Accepted. The infobar is removed. Whether to configure an API key on the
owner's machine is left open below, and it is a real question, not a formality.

## Context

The first build produced by this pipeline shows an infobar on every launch:

> Google API 키가 누락되었습니다. Chromium의 일부 기능이 사용 중지됩니다.

Upstream at the pinned revision, `chrome/browser/ui/startup/infobar_utils.cc`:

```cpp
if (!google_apis::HasAPIKeyConfigured()) {
  GoogleApiKeysInfoBarDelegate::Create(infobar_manager);
}
```

Sunshine configures no key, so the condition is permanently true.

This is not a defect that appeared — it is a criterion that was already being
violated. `docs/PROFILE_ONBOARDING_CONTRACT.md` **PO-A15** requires that no
product surface describe local-only operation as an error, a warning, or an
incomplete setup. The infobar does all three, on every launch, in the browser's
most prominent transient surface.

The message is aimed at a Chromium developer who forgot to configure keys, for
whom "missing" is accurate. For Sunshine the keyless build is the product:
`scripts/verify_account_freedom.py` enforces PO-A1 through PO-A3 precisely so
that no key can arrive by accident. Presenting the intended state as a fault is
the false alarm PO-A15 names.

## Decision

**Remove the infobar** — `downstream/patches/0003-sunshine-no-missing-api-key-warning.patch`.

**Do not add a key to the repository.** PO-A1 forbids an OAuth client id,
client secret, or API key in `first_party/`, `downstream/`, `scripts/`, or
`config/`, in any encoding, and nothing here changes that.

The patch touches no protected area. `verify_account_freedom.py` guards
`chrome/browser/signin/`, `components/signin/`,
`chrome/browser/ui/startup/first_run`, `chrome/browser/sync/`,
`components/sync/` and `google_apis/`; `infobar_utils.cc` is none of them, and
the upstream chain that produces a keyless, sign-in-free, first-run-free build
is untouched.

## Consequences

**The warning is removed. What it warned about is not.** Upstream's own header
is the authority, `google_apis/google_api_keys.h`:

> These functions enable you to retrieve keys to use for Google APIs such as
> Translate and Safe Browsing.
>
> If some of the parameters mentioned above are not provided, Chromium will
> still build and run, but services that require them may fail to work without
> warning. They should do so gracefully, similar to what would happen when a
> network connection is unavailable.

So the affected set includes **Safe Browsing** and **Translate**, and the
failure mode is a service behaving as though the network were down.

**Safe Browsing is the one that matters.** A browser in daily use without
malware and phishing lookups is a real reduction in protection, and it is
not something the removal of an infobar should be allowed to obscure. Which
parts of Standard Protection degrade, and whether any local-only protection
survives, is **NOT VERIFIED** — it cannot be established from source reading
alone and needs the built browser.

**`docs/SECURITY_CENTER_CONTRACT.md` is affected.** It describes provider
verdicts layered beside Chromium's own blocking path. That path is weaker than
the document assumes while no key is configured.

## Decided: no API key is configured

The owner's decision, taken with the consequence stated: **do not set
`GOOGLE_API_KEY`.** Sunshine runs without Safe Browsing.

That is a real reduction in protection, not a formality, and it is recorded here
rather than softened. It is also consistent with what the rest of this
repository already enforces — a build that reaches no Google service for
identity, and now reaches none for reputation either. Reversing it needs no code
change: setting the variable on the machine is enough, and the distinction below
is what makes that safe to do later.

The distinction that made the decision answerable:

| Variable | Restores | Enables sign-in? |
| --- | --- | --- |
| `GOOGLE_API_KEY` | Safe Browsing, Translate, and the other keyed services | **No** |
| `GOOGLE_DEFAULT_CLIENT_ID` / `_SECRET` | OAuth | **Yes** — breaks the chain |

`HasAPIKeyConfigured()` and `HasOAuthClientConfigured()` are separate
predicates. Only the OAuth client feeds `CanEnableDiceForBuild()`, so setting
the API key alone restores the keyed services while leaving the account-free
guarantee exactly as it is. Setting the client id or secret would not.

If it is ever set, it must be **machine-local** — an environment variable on the
build or run machine, never a file in this repository, so PO-A1 continues to
hold as written. Upstream states environment overrides are ignored for official
Google Chrome builds; Sunshine is not branded, so they should apply here, which
is **NOT VERIFIED** until tried.

## What this obliges

Two things follow, and neither is optional now that the answer is no.

**`docs/SECURITY_CENTER_CONTRACT.md` already anticipated this, and now owns it
permanently.** SC-11 requires the centre to say so when Safe Browsing is absent
from the build, and never to present a provider as its replacement; SCA-8 is the
acceptance criterion for exactly that state; its ownership table already reads
"where the pinned build enables it", and its NOT VERIFIED list already records
that Safe Browsing's presence in a Sunshine build was never established.

What changes is that the absent branch is no longer a contingency the contract
covered defensively — it is the shipping configuration. The Security Center is
not an additional layer over a baseline; for malware and phishing it is the only
layer there is, and SC-11's honesty requirement is doing more work than its
author expected.

**A distribution decision inherits this one.** ADR 0004 already requires
revisiting before any build reaches a second person. This is the second item on
that list: shipping a browser with no Safe Browsing to someone who did not
choose it is a different act from running one yourself.

The fact lives here, in the contract set, rather than in an infobar the user
cannot act on.
