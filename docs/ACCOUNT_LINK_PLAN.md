# Linking a Google account at profile registration — plan

## 0. Status, and the question this answers

A plan, not a decision and not work. **It answers a standing P0.**
`docs/PROFILE_ONBOARDING_CONTRACT.md` §12 asks:

> Is a **permanently** account-free browser the product, or is local-only the
> Stage 1 state of a browser that later gains an identity?

The owner has answered the second. This document says what that costs, what the
procedure looks like, and what has to be decided before anything is written.
§9 is the decision list and §10 is what is not verified.

Everything here is built on `docs/PROFILE_ONBOARDING_CONTRACT.md` rather than
derived again. That document already ruled on this exact subject — PO-R3 lists
the preconditions for gaining an identity and PO-R8 names the shape one would
have to take — and re-deriving it would be the mistake its own §0 was written to
prevent.

## 1. Three mechanisms Chromium keeps apart, and a fourth

§4 of the onboarding contract separates what "linking Google" can mean. The
separation is the whole safety argument, so it is restated as the frame:

| | | Ruling |
| --- | --- | --- |
| **L1** | The user signs in to Google **in a tab**. Gaia cookies land in the browsing jar. The browser's identity does not change. | Permitted today (PO-R1) |
| **L2** | The **browser** holds a primary account with a refresh token in the profile's token database. This alone turns on sync-the-transport with no further opt-in. | Not available (PO-R3) |
| **L3** | **Sync-the-feature.** Upstream's own words: "there is no distinction between local data and account data … this cannot be undone." | Never implied by L2 (PO-R4) |

**What this plan proposes is none of the three.** Call it **L4**: a
*Sunshine application link* — an ordinary OAuth 2.0 authorization that Sunshine
holds as an application, the way any desktop program holds one. It uses none of
Chromium's identity machinery, and the profile remains, in Chromium's terms, a
profile with no primary account at either consent level.

That is not a technicality. It is the difference between "the browser is signed
in" and "a program on your computer has permission to talk to your Google
account", and every rule below exists to keep the second from becoming the
first.

## 2. Two things that are simply not available

**Chrome Sync is not available and will not become available.** Google restricts
Chrome-specific APIs — sync among them — to Google Chrome; a Chromium
downstream cannot obtain access. Nothing in this plan is a route to it, and
PO-R4 forbids treating an account grant as consent to it regardless. Any
roadmap item that reads "sync bookmarks/passwords/history via Google" should be
struck rather than scheduled.

**Chromium's own sign-in must stay off.** It is off by construction: with no
OAuth client configured, `CanEnableDiceForBuild()` is false, `kSigninAllowed` is
written false, and the first-run experience is skipped. PO-R2 makes that
unconditional. **L4 must not switch it on as a side effect**, which is a real
risk and §8 is how it is prevented: the credential L4 uses must never be
Chrome's `google_default_client_id`, because setting that is precisely what
re-enables Dice.

**What is available** is what any native application can have: an OAuth 2.0
client in a Google Cloud project, the OpenID Connect scopes, and whatever
product scopes the owner later justifies.

## 3. PO-R3's five preconditions, and how each is met

PO-R3 permits an identity only if all five hold at once. They are the
specification for this work.

| | Precondition | How this plan meets it |
| --- | --- | --- |
| 1 | A reviewed ADR superseding the relevant part of ADR 0002 | **ADR 0018** — not written, because it depends on §9's answers. It supersedes nothing about search providers; it narrows PO-R8's "Sunshine operates no browser-level OAuth of its own" to "…and operates an application link that is not a browser-level identity". |
| 2 | A credential story that is **Sunshine's own rather than Chrome's** | §5. A Sunshine OAuth client, public, PKCE-only, never in this repository, never Chrome's client id. |
| 3 | A user action that **names the account and its consequences before it happens** | §4 step 2. Sunshine's own consent screen renders before Google's, and says what will be requested and what it will not reach. |
| 4 | A sign-out that returns the profile to §3's state | §7. Revoke, delete, and the profile is a local-only profile again with nothing left behind. |
| 5 | A re-derivation of §5 and §6 of the onboarding contract against the revision in force | Owed at implementation time, not now. §10 records it as outstanding. |

## 4. The procedure

**The shape of it in one line: the profile is finished before the account is
mentioned, and the account can be declined forever without the word "incomplete"
appearing anywhere.** That is PO-6 and PO-9, and it is also the only version
that survives PO-A5 — a machine with no network must still reach a usable
browser.

### Step 0 — the profile is created, with none of this

Unchanged from today. No network, no account, no gate. The account step is not
part of profile creation; it is something a finished profile may later be
offered.

### Step 1 — the offer

**A row in the profile's own settings, and nothing else** (D5). No card, no
banner, no first-run step. Requirements, all from existing rules:

- The absence of any prompt is itself PO-9 satisfied: a user who never opens
  settings has a fully configured browser.
- The row is reachable from settings at any time (PO-10).
- Its copy never says *incomplete*, *set up*, *finish*, or *recommended*
  (PO-6, PO-A15).

### Step 2 — Sunshine's consent screen, before Google's

This screen is precondition 3 and it is the part that cannot be skipped or
merged into Google's. It states, in the user's language:

| | |
| --- | --- |
| What is asked | The exact scopes, spelled as sentences rather than scope strings. |
| What it is **not** | It does not sign the browser in. It does not sync bookmarks, history, passwords or tabs. It does not give Sunshine your Google password. It changes nothing about the pages you visit. |
| Where it is kept | In Windows' credential store, for this profile only. |
| How to undo it | One control, in the same place, at any time. |

Google's consent screen follows. Two screens is deliberate: Google's names the
permissions, Sunshine's names the consequences, and only the second can say what
Sunshine will not do.

### Step 3 — the authorization

The documented native-application flow, and nothing clever:

| | |
| --- | --- |
| Client type | **Public client, PKCE only**, with SHA-256 challenges. No client secret ships. A secret in a program on a user's disk is not a secret, and Google's desktop client type does not expect one. |
| Redirect | **Loopback**, `http://127.0.0.1:<ephemeral port>`. The listener binds before the URL opens, accepts exactly one request, and closes. |
| Anti-forgery | `state`, generated per attempt, compared on return, single use. |
| Account choice | `prompt=select_account`, always (D2). Google must not continue silently with the session already in the tab, because a person with several accounts would never see which one was linked. |
| Refusals | `urn:ietf:wg:oauth:2.0:oob` is not used — it is retired. No embedded web view is used; Google refuses those and it would also breach PO-R7. |
| Timeout | The listener closes on a short timer whether or not anything arrives, so a cancelled sign-in leaves no socket open. |

The page renders in an ordinary tab (D2). The user's existing Google session is
reachable, and the forced account chooser is what stops that convenience from
becoming a link the user did not read.

### Step 4 — the exchange

The browser process exchanges the authorization code for tokens over the
loopback response, directly with Google. **No web content is involved at any
point.** The code arrives on a socket Sunshine opened, not from a page, and that
is what keeps PO-R7's credential rule true: nothing is promoted out of the
cookie jar, because nothing was read from it.

### Step 5 — where the credential lives

**The Windows credential store, keyed per profile.** Not the profile's token
database, not `Login Data`, not a Sunshine file. PO-R8 requires exactly this,
and it is also what makes §7 truthful — one delete, and it is gone.

Access tokens are held in memory and never written. The refresh token is the
only durable secret.

### Step 6 — what the profile shows afterwards

One row: the linked address, and a control to unlink. Nothing else changes.
No avatar in the toolbar, no account badge, no new menu.

**PO-14 stays true**: no Sunshine surface — no AI surface, no dashboard, no
workspace, no telemetry path — reads this identity to change browsing
behaviour. The link is a capability the user granted to a program, not a fact
about the browser.

### Step 7 — unlinking

1. Revoke the token at Google's revocation endpoint.
2. Delete the credential from the Windows store.
3. Discard anything derived from it.

Afterwards the profile is a local-only profile, and §3 of the onboarding
contract describes it exactly. Precondition 4, met. Unlinking must also succeed
**offline** — the revocation is attempted, and its failure does not stop the
local deletion, because a user who wants a credential gone should not need a
network to get it gone.

## 5. The credential, and why it is not in this repository

`scripts/verify_account_freedom.py` refuses any OAuth client id, secret or API
key anywhere in `first_party/`, `downstream/`, `scripts/` or `config/`, in any
encoding, and refuses the three Chrome build arguments that would configure one.
**None of that is relaxed by this plan.**

The Sunshine client id enters at **build time, from the release pipeline**,
under a name of its own — never `google_default_client_id`, which is Chrome's
and whose presence is what turns Dice back on. A build without it simply does
not offer the account link, which is the correct behaviour for a build anyone
can make from this tree: the feature is absent, not broken, and §1's local-only
path is untouched.

That is not a workaround. It is the same rule the repository already applies to
every other credential, extended to one more.

## 6. What the link is for

**Nothing, until something needs it** — and that is the recommendation, not an
omission. §9's D3 asks what the first use is.

The candidates, with what each would cost:

| | | |
| --- | --- | --- |
| **Identity only** | `openid email`. The account is a name for a person across devices. | Nothing sensitive is requested, no Google review is needed, and it is enough for the `device` and ownership fields `docs/DOCUMENT_STORE_CONTRACT.md` §3 already defines. |
| **Module entitlement** | Which modules this person may install. | This is what "account-based operation" most plausibly means, and it needs identity and nothing more. |
| **Drive as a document store** | `drive.file`. | **Contradicts a settled decision.** DS-1 chose "a directory the user picks, in a folder something else already syncs". Drive-as-an-API is a different design from Drive-as-a-synced-folder, and DS-2 forbids the database shape it tends toward. If this is wanted it reopens the store contract; it does not extend it. |

**Decided (D3): `openid` and `email` at launch, and nothing else.** A scope
requested before a feature needs it is a permission with no justification to
give, and Google's consent screen says so more bluntly than any reviewer would.

Under D1 the identity row is also the only row still available: entitlement is a
requirement by another name, and Drive would reopen DS-1. So the link's whole
job at launch is to name a person across devices — and if that turns out not to
be worth building, this is the section where that becomes visible rather than
the section that hides it.

## 7. What breaks if this is done carelessly

Named so that they are checked rather than discovered.

| Risk | What it looks like | What prevents it |
| --- | --- | --- |
| The link silently becomes a browser sign-in | Someone sets `google_default_client_id` to make "sign-in work", and Dice comes back with sync-the-transport behind it | §8's rule, and PO-R2 |
| The token lands in the profile | Convenience: `OSCrypt` is right there and writes into the profile directory | PO-R8; §5's store is the OS one |
| The consent screen is skipped when the user is already signed in to Google in a tab | One click links an account the user did not read about | §4 step 2 runs before Google's screen, always, regardless of session state |
| An unlinked account leaves residue | Revocation fails offline and the local delete is skipped with it | §7's ordering: local delete happens either way |
| A Sunshine surface starts reading the identity | An AI panel personalises itself; telemetry gains a stable user id | PO-14, PO-15 |
| The account becomes required | A module refuses to run unlinked, and local-only stops being complete | §9's D4 is where that is decided rather than drifted into |

## 8. What the guard must be extended to enforce

`verify_account_freedom.py` today proves three things offline. It must keep
proving all three, and gain two, on the commit that introduces the link:

| | New rule |
| --- | --- |
| PO-A16 | The tree still contains no credential and sets none of Chrome's key arguments — **unchanged**, and it must stay unchanged, so the new build argument is a different name and carries no value here. |
| PO-A17 | The account-link source reaches none of Chromium's identity surface: no `IdentityManager`, no `ProfileOAuth2TokenService`, no `signin::`, no sync service, and no read of the profile's cookie jar. |

Both are decidable from source, like PO-A1 to PO-A3 — which is what made those
the first acceptance criteria in this contract set a check could actually
decide. The guard is written with the code, not after it.

## 9. What has to be decided

Each is written with the situation that makes it a real fork, because a
decision stated only as two abstractions is one nobody can take.

**D1 is settled: the account is optional forever.**

The owner's answer, and it is the load-bearing one. No module and no feature may
require a link. PO-2 stays true, §3 of the onboarding contract keeps describing
a complete path rather than a degraded one, and `verify_account_freedom.py`'s
PO-A3 — no registered command for sign-in — needs no exception.

**It also narrows §6.** Module *entitlement* was the most plausible first use of
the link, and entitlement means "this person may install that module", which is
a requirement by another name. Under D1 it is not available as stated. What
remains for the link to be **for** is identity that makes something *better*
and nothing *possible*: naming the person across devices, and filling the
`device` and ownership fields `docs/DOCUMENT_STORE_CONTRACT.md` §3 already
defines. D3 is where that is confirmed or replaced.

**D3 is settled: `openid` and `email`, and nothing else.**

Two things follow that are worth having written down.

- **No Google verification is required to launch.** Verification is what
  sensitive and restricted scopes trigger; an app asking only for identity does
  not. The unverified-app screen §10 warns about is therefore not on the path,
  provided the scope list stays as decided. Adding one product scope later is
  not a small edit — it is a review.
- **Drive-as-a-store stays closed.** `docs/DOCUMENT_STORE_CONTRACT.md` DS-1 —
  a directory the user picks, in a folder something else already syncs — is
  untouched, and §6's warning that Drive-as-an-API would *reopen* that contract
  rather than extend it does not need to be acted on.

**D4 is settled: the link is per profile.**

The credential is keyed to the profile in the Windows credential store, which
is what §5 already described and what makes §7's "one delete and it is gone"
literally true.

**It adds one obligation to a contract this document does not own.**
`docs/PROFILE_ONBOARDING_CONTRACT.md` PO-12 requires profile deletion to destroy
"all Sunshine metadata keyed to that profile". A credential in the OS vault is
exactly that, and it does not live under the profile directory, so Chromium's
own deletion will not remove it. **Deleting a profile must revoke and delete its
link**, on the same path and with the same offline behaviour as §7 — the local
delete happens whether or not the revocation reaches Google. That is a rule the
implementation owes, and PO-A10's fixture list should gain a linked account.

**D2 is settled: a normal tab, with account selection forced.**

The authorization page renders in an ordinary tab, and the request carries
`prompt=select_account` so that Google never silently continues with whatever
session is already there.

This is the middle of the three answers and it was chosen over both ends for a
reason worth recording. Reusing the session outright is one click, and its
failure mode is a person with several Google accounts linking the wrong one
without ever seeing which. The ephemeral partition removes that by making the
user type a password, and its failure mode is that a person plainly signed in is
asked to sign in again, which reads as a defect. Forcing the account chooser
costs one click and removes the first failure without buying the second.

PO-R7 still holds, and the reason has not changed: Sunshine reads no cookies. It
receives an authorization code on a socket it opened. The user's Google session
is the user's, used by the user, in their own tab — which is L1, and PO-R1
permits it.

**D5 is settled: settings only. No first-use card.**

Nothing appears when a new profile opens. The link lives in the profile's
settings and is found by looking for it.

This is the answer most consistent with D1. A card offering an account at first
run is a card appearing at the exact moment PO-6 is easiest to break — the
moment a user is deciding what this browser expects of them — and no wording
makes "would you like to connect an account?" fully safe from reading as
"finish setting up". The cost is real and is accepted: some users will never
learn the feature exists. Under D1 that costs them nothing they cannot do.

## 10. NOT VERIFIED

- **Nothing here is built, and no ADR exists.** PO-R3 precondition 1 is
  unwritten and precondition 5 — re-deriving §5 and §6 of the onboarding
  contract against the revision in force — has not been done.
- **No OAuth client exists.** No Google Cloud project has been created and no
  consent screen configured. **Verification is believed not to be required**,
  because D3 settled the scope at identity only and verification is what
  sensitive and restricted scopes trigger — but that is read from Google's
  published policy, not from having submitted anything, and it is the claim in
  this document most likely to be wrong in a way that costs weeks.
- **The Windows credential store has not been touched.** Which API is used, what
  it costs at profile deletion, and whether it survives a Windows account
  migration are all unexamined.
- **The claim that Chrome Sync is unavailable to a downstream is stated from
  Google's published restriction on Chrome-specific APIs, not from an attempt.**
  It should not be tested by trying.
- The loopback flow is specified from the documented native-app pattern. No part
  of it has been run against Google's endpoints from this browser, and whether
  Sunshine's user agent — upstream's, unmodified — is accepted at those
  endpoints is an assumption.
- §6's recommendation assumes module entitlement is the first real use. If it is
  not, D3's answer changes and this section is where that would have been said.
