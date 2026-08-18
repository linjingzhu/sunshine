# Profile Onboarding — Creation, Local-Only Operation, and the Account Boundary

**Status:** Documentation-only wave. No downstream patch, no first-party module,
no registered command.
**Target:** Pinned Chromium revision in `config/chromium.version` (`152.0.7977.42`).
**Settles:** the `Profile onboarding` row of section 5.2 of
`docs/SUNSHINE_OS_STAGE_1_TO_3_IMPLEMENTATION_HANDOFF.md` — "`Use locally` works
without network; Google is optional", "auth failure does not block browser
launch" — and requirement 6 of section 5.6, "separate Sunshine profile OAuth
from logging into Google inside a normal browser tab". Both are recorded as
having no owning contract by `docs/ACCEPTANCE_SUITES.md` finding U2 and by the
P0 in its section 9.

**Ownership boundary.** `docs/SESSION_PROFILE_CONTRACT.md` owns a profile's
steady state: isolation, session restore, crash recovery, off-the-record scope,
secret handling. This document owns the two ends that contract does not reach —
how a profile comes into existence and what happens when it is destroyed — plus
the account link, which exists at neither end but changes the meaning of both.
Where the two appear to disagree, `docs/SESSION_PROFILE_CONTRACT.md` wins and
the disagreement is a defect in this document. Sections 7 and 9 record the two
places they touch.

---

## 0. Evidence basis

Every statement below about upstream behaviour was read from the pinned tag over
the GitHub raw mirror on 2026-08-17, file by file. Statements are labelled:

- **read-from-source** — taken from a file fetched at `152.0.7977.42`;
- **NOT LOCATED** — searched for at the pinned tag and not found in the files
  read; absence is not proven, only unlocated;
- **NOT RUN** / **NOT AVAILABLE** — a measurement that has not been taken.

No Chromium build was compiled, no browser was launched, no profile was created
or deleted, no sign-in was attempted, and no screenshot was taken for this
document: build **NOT RUN**, runtime **NOT RUN**, visual **NOT RUN**.

Section 5.2 gives this slice one line of requirement and one line of
definition-of-done, and section 5.6.6 gives it one sentence. None of the three
names a mechanism. The method used here was to establish what the pinned
revision already ships for profile creation, first run, sign-in, sync and
deletion **before** specifying anything, on the precedent of
`docs/TAB_WORKSPACE_SPLIT_CONTRACT.md` §0, where a Sunshine split-view model was
found to have re-derived an upstream collection because nobody checked first.
Doing so changed the answer: see §2.

---

## 1. What the pinned revision already provides

All read-from-source.

| Concern | Upstream owner | What it already does |
|---|---|---|
| Profile creation, loading, paths | [`chrome/browser/profiles/profile_manager.h`](https://github.com/chromium/chromium/blob/152.0.7977.42/chrome/browser/profiles/profile_manager.h) | Asynchronous creation of an additional profile, path allocation, load-without-create, and access to the attributes storage and the deletion helper. |
| Profile roster and display data | [`chrome/browser/profiles/profile_attributes_storage.h`](https://github.com/chromium/chromium/blob/152.0.7977.42/chrome/browser/profiles/profile_attributes_storage.h), [`chrome/browser/profiles/profile_attributes_entry.h`](https://github.com/chromium/chromium/blob/152.0.7977.42/chrome/browser/profiles/profile_attributes_entry.h) | Name, avatar, ephemeral flag, and per-profile management state, held outside the profile directory in Local State. |
| Profile picker and creation entry points | [`chrome/browser/ui/profiles/profile_picker.h`](https://github.com/chromium/chromium/blob/152.0.7977.42/chrome/browser/ui/profiles/profile_picker.h) | A window with eighteen enumerated entry points, including startup, "manage profiles" and "add new profile"; the sign-in, reauth and *signed-out post-identity* sub-flows; and the first-run parameterisation. |
| Naming and finalising a new profile | [`chrome/browser/ui/profiles/profile_customization_util.h`](https://github.com/chromium/chromium/blob/152.0.7977.42/chrome/browser/ui/profiles/profile_customization_util.h), [`chrome/browser/ui/webui/signin/profile_customization_ui.h`](https://github.com/chromium/chromium/blob/152.0.7977.42/chrome/browser/ui/webui/signin/profile_customization_ui.h) | Finalising setup with a name, and the customisation surface that collects one. |
| First-run detection | [`chrome/browser/first_run/first_run.h`](https://github.com/chromium/chromium/blob/152.0.7977.42/chrome/browser/first_run/first_run.h) | A sentinel file decides "is this the first run"; creation, read, and creation-time query. |
| First-run experience | [`chrome/browser/ui/startup/first_run_service.h`](https://github.com/chromium/chromium/blob/152.0.7977.42/chrome/browser/ui/startup/first_run_service.h), [`chrome/browser/ui/startup/first_run_service.cc`](https://github.com/chromium/chromium/blob/152.0.7977.42/chrome/browser/ui/startup/first_run_service.cc) | Decides whether to open a first run at all, opens it in the picker window, records four exit statuses, and writes a local-state "finished" flag. |
| First-run content | [`chrome/browser/ui/webui/intro/intro_ui.cc`](https://github.com/chromium/chromium/blob/152.0.7977.42/chrome/browser/ui/webui/intro/intro_ui.cc), [`chrome/browser/ui/webui/intro/intro_handler.h`](https://github.com/chromium/chromium/blob/152.0.7977.42/chrome/browser/ui/webui/intro/intro_handler.h) | The intro page and its handler, which exposes exactly four user actions: continue **with** an account, continue **without** an account, set as default browser, skip default browser. |
| Browser identity | [`components/signin/public/identity_manager/identity_manager.h`](https://github.com/chromium/chromium/blob/152.0.7977.42/components/signin/public/identity_manager/identity_manager.h), [`components/signin/public/base/consent_level.h`](https://github.com/chromium/chromium/blob/152.0.7977.42/components/signin/public/base/consent_level.h) | The primary account and its two consent levels. |
| Whether a web sign-in reaches the browser | [`chrome/browser/signin/account_consistency_mode_manager.h`](https://github.com/chromium/chromium/blob/152.0.7977.42/chrome/browser/signin/account_consistency_mode_manager.h), [`components/signin/public/base/account_consistency_method.h`](https://github.com/chromium/chromium/blob/152.0.7977.42/components/signin/public/base/account_consistency_method.h) | Per-profile account-consistency mode: disabled, mirror, or Dice. Computed once and fixed for the profile's lifetime. |
| The web-to-browser bridge itself | [`chrome/browser/signin/dice_response_handler.h`](https://github.com/chromium/chromium/blob/152.0.7977.42/chrome/browser/signin/dice_response_handler.h), [`components/signin/core/browser/signin_header_helper.h`](https://github.com/chromium/chromium/blob/152.0.7977.42/components/signin/core/browser/signin_header_helper.h) | Request/response headers on Google navigations, and the handler that exchanges an authorization code from a *web page* for a browser refresh token. |
| Keeping cookie jar and browser account agreed | [`components/signin/core/browser/account_reconcilor.h`](https://github.com/chromium/chromium/blob/152.0.7977.42/components/signin/core/browser/account_reconcilor.h) | Reconciles the browser's accounts with the Gaia cookies in the profile's jar. |
| Token storage | [`components/signin/internal/identity_manager/mutable_profile_oauth2_token_service_delegate.h`](https://github.com/chromium/chromium/blob/152.0.7977.42/components/signin/internal/identity_manager/mutable_profile_oauth2_token_service_delegate.h), [`components/signin/public/webdata/token_service_table.h`](https://github.com/chromium/chromium/blob/152.0.7977.42/components/signin/public/webdata/token_service_table.h) | Refresh tokens live in the profile's web-data database, encrypted, with re-encryption and per-account revocation. |
| Sync opt-in | [`components/sync/service/sync_service.h`](https://github.com/chromium/chromium/blob/152.0.7977.42/components/sync/service/sync_service.h), [`chrome/browser/ui/webui/signin/turn_sync_on_helper.h`](https://github.com/chromium/chromium/blob/152.0.7977.42/chrome/browser/ui/webui/signin/turn_sync_on_helper.h) | Two distinct modes — transport and feature — and the flow that turns the second on. |
| Profile deletion | [`chrome/browser/profiles/delete_profile_helper.h`](https://github.com/chromium/chromium/blob/152.0.7977.42/chrome/browser/profiles/delete_profile_helper.h), [`chrome/browser/profiles/delete_profile_helper.cc`](https://github.com/chromium/chromium/blob/152.0.7977.42/chrome/browser/profiles/delete_profile_helper.cc) | A five-stage lifecycle with two startup fail-safes; documented in the class comment at the pinned tag. |

**Sunshine writes none of it.** There is no onboarding feature to build. What
follows is a set of rules over machinery that already exists, which is the
expected outcome under `docs/decisions/0002-native-chromium-downstream.md` and
the same outcome `docs/BROWSER_UTILITIES_CONTRACT.md` and
`docs/ADVANCED_TABS_CONTRACT.md` reached independently for their sections.

---

## 2. The finding that decides this document

Checking upstream first changed the question. Handoff §5.2 asks for a local-only
path "with Google optional". At the pinned revision, in a build Sunshine is
permitted to produce, the Google option **does not exist to be optional**.

The chain, all read-from-source:

1. `docs/decisions/0002-native-chromium-downstream.md` forbids Google Chrome
   proprietary API keys. A Sunshine build therefore has no OAuth client id or
   secret configured; [`google_apis/google_api_keys.h`](https://github.com/chromium/chromium/blob/152.0.7977.42/google_apis/google_api_keys.h)
   exposes the predicate for exactly this state and documents that the
   unconfigured build gets a dummy value.
2. [`chrome/browser/signin/account_consistency_mode_manager.cc`](https://github.com/chromium/chromium/blob/152.0.7977.42/chrome/browser/signin/account_consistency_mode_manager.cc)
   makes Desktop Identity Consistency conditional on that predicate — its own
   comment is "By default, DICE is not enabled in builds lacking an API key" —
   and logs a warning once when it is absent.
3. The same file's constructor writes the result into the profile's
   signin-allowed preference, and its consistency computation returns
   **disabled** when that preference is false.
4. `chrome/browser/ui/startup/first_run_service.cc` treats a false
   signin-allowed preference as the enterprise `BrowserSignin=0` state — its
   comment says so — and returns a policy effect that **suppresses the entire
   first-run experience**, marking it finished with the "skipped by policies"
   reason.

So in a keyless Sunshine build: no Dice, no browser sign-in, no sync, and no
first-run experience — not because Sunshine suppressed them but because the
build lacks the credential upstream requires, and upstream degrades to exactly
the state this product wants. The local-only browser is the **default and only**
state, obtained by building honestly rather than by writing code.

Two consequences follow immediately and are binding.

- **Local-only cannot be described as a deferral or a mode.** It is the product.
  §3 says what that costs and what must still work.
- **"Auth failure does not block browser launch"** — the §5.2
  definition-of-done — is satisfied vacuously, because there is no auth path to
  fail. It is therefore not evidence of anything, and §10 replaces it with a
  criterion that can fail.

Two limits on the above, stated rather than hidden. The ordering between the
consistency manager writing the preference and the first-run service reading it
is a keyed-service construction-order question that cannot be settled without a
build: **NOT RUN**. And the sign-in surfaces that consult the same preference
outside these two files were not exhaustively enumerated: **NOT LOCATED**. §10
turns both into criteria rather than assumptions.

---

## 3. Local-only is a complete path

### 3.1 What must work with no account, ever, and no network at profile creation

A profile that has never been signed in is not a degraded profile. All of the
following must be fully functional in it, and each is owned by a contract that
already assumes no account:

- browsing, navigation, downloads, permissions, and the whole of Stage 1's
  feature set;
- bookmarks and history, including their persistence across restart — the
  local-or-syncable roots in `docs/BOOKMARKS_HISTORY_CONTRACT.md` are the
  storage that does not require an account;
- passwords, addresses and payment data saved **to the profile**;
- session restore, crash recovery, and profile isolation per
  `docs/SESSION_PROFILE_CONTRACT.md`;
- workspaces, tab groups, split view, side panel, and the command palette;
- profile creation, naming, switching and deletion themselves.

Creating a profile must not require, wait on, or retry a network request. This
document requires it; the upstream creation, customisation and attributes paths
read for §1 contain no network dependency, but that is an observation about the
files read, not a proof, and it is a criterion in §10 rather than a claim here.

### 3.2 What local-only costs

Stated plainly, because a contract that only lists what works is marketing:

- **No sync of anything.** No cross-device tabs, bookmarks, history, passwords,
  addresses, settings, themes, extensions, or saved tab groups.
- **No account password or passkey sharing.** Credentials saved in this profile
  stay in this profile on this device. A password saved on a phone does not
  appear here.
- **No account-backed backup or restore.** A lost or wiped device is a lost
  profile. `docs/SESSION_PROFILE_CONTRACT.md` already states that local session
  restore must not silently upload; this states the other half of the bargain,
  which is that nothing else does either.
- **No account bookmark roots.** `docs/BOOKMARKS_HISTORY_CONTRACT.md` describes
  the optional account roots; in a local-only browser they are never populated.
- **No cross-device threat-protection or reputation state** beyond whatever
  `docs/SECURITY_CENTER_CONTRACT.md` provides locally.

None of these is a defect, and none may be presented in product surfaces as a
problem to be fixed by signing in — see PO-6.

### 3.3 What local-only does *not* cost

The single most likely misreading of §5.2 is that "use locally" means "not
logged in to websites". It does not. Website login — Gmail, GitHub, a bank — is
ordinary cookie and credential behaviour in the profile's storage and is
entirely unaffected. The §5.7 dogfood line "login persistence" is about that,
not about browser sign-in, and `docs/ACCEPTANCE_SUITES.md` A1.1 cites it to the
session and bookmark contracts for that reason.

---

## 4. The optional Google link: three different things, ruled separately

The phrase "Google is optional" conflates three mechanisms that Chromium keeps
distinct. Conflating them is the mechanism by which a local-only browser
quietly becomes a signed-in one, so they are separated here and each is ruled.

| # | Mechanism | What it actually is | Where it lives |
|---|---|---|---|
| L1 | **Web sign-in** | The user signs in to a Google property in a tab. Gaia cookies are set in the profile's cookie jar. Nothing about the browser's identity changes. | Ordinary web content |
| L2 | **Browser sign-in** | The browser holds a primary account at the signin consent level, with a refresh token in the profile's token database. `components/sync/service/sync_service.h` states that this alone enables **sync-the-transport**, "with no further opt-in required". | Identity manager |
| L3 | **Sync-the-feature** | Explicit opt-in on top of L2. The same file states that in this mode "there is no distinction between local data and account data — when turning on Sync, everything is merged together, and this cannot be undone." | Sync service |

Read-from-source, all three.

### 4.1 Rulings

**PO-R1 — L1 is permitted and is not a browser sign-in.** A user signing in to a
Google website is browsing. Sunshine neither blocks it nor treats it as an
account link.

**PO-R2 — L1 must never be adopted into L2.** The adoption mechanism is Dice:
`chrome/browser/signin/dice_response_handler.h` exchanges an authorization code
obtained from a *web page* for a browser refresh token, and
`components/signin/core/browser/signin_header_helper.h` is what attaches and
parses the headers that carry it. In a Sunshine build that mechanism is off by
construction (§2). It must stay off: no patch, switch, feature flag, build
argument, embedded credential, or test-only escape hatch may enable account
consistency in a shipped build. The manager exposes a testing setter that
ignores the missing OAuth client; using it outside a test is prohibited.

**PO-R3 — L2 is not available in Stage 1, and if it ever becomes available it is
explicit, per-profile, and revocable.** Preconditions on any future reversal, all
of which must hold simultaneously: a reviewed ADR superseding the relevant part
of `docs/decisions/0002-native-chromium-downstream.md`; a credential story that
is Sunshine's own rather than Chrome's; a user action that names the account and
its consequences before it happens; a sign-out that returns the profile to the
state described in §3; and a re-derivation of §5 and §6 against the revision in
force at that time.

**PO-R4 — L3 is never implied by L2.** Because L2 silently enables
sync-the-transport, and because L3 is documented upstream as an irreversible
merge of local and account data, an L2 grant may never be treated as consent to
L3. If L2 ever exists, the transport-mode data types active under it are
themselves a decision requiring the owner, not an implementation detail.

**PO-R5 — the ADR 0002 analogue holds.** ADR 0002 forbids hardcoding a search
provider, including Google, as a startup or search URL. The identical rule
applies here and is stricter: Sunshine hardcodes no account, no account domain,
no OAuth client id or secret, no Gaia endpoint override, and no default identity
of any kind. A build that ships a credential enabling sign-in is a violation of
ADR 0002 and of this contract independently. `docs/EXTENSION_COMPATIBILITY_GATE.md`
already forbids impersonating Chrome or injecting credentials intended for
another product; PO-R5 is that rule applied to browser identity.

**PO-R6 — the search provider question is not answered by adding an onboarding
step.** `docs/OMNIBOX_CONTRACT.md` §15 asks whether the default search provider
is chosen by the user at onboarding or left at Chromium's locale-derived
default, and assigns it to Stage 1 onboarding. This document's answer for the
onboarding surface: **Sunshine adds no provider-choice step and hardcodes no
provider.** Whether a choice screen appears is upstream and region-driven —
`components/search_engines/search_engine_choice/search_engine_choice_service.h`
carries the region and completion state, and the intro page reads a
choice-region signal only to select a layout variant. The choice surface itself
is not part of the intro WebUI and was **NOT LOCATED** at the pinned tag in the
files read. Consequence, given §2: where no choice screen is shown, the provider
is Chromium's locale-derived default, which satisfies ADR 0002. The omnibox side
of that question remains `docs/OMNIBOX_CONTRACT.md`'s.

---

## 5. §5.6.6 — the OAuth separation boundary

Handoff §5.6.6 asks for "Sunshine profile OAuth" to be separated from "logging
into Google inside a normal browser tab". Stated as a boundary over what may be
shared, which is the only form in which it can be tested:

**PO-R7 — three things must never be shared between a browser-level identity and
web content.**

| Must never be shared | Meaning |
|---|---|
| A **credential** | No refresh token, access token, authorization code, bound-session key, or device-bound credential held for a browser-level identity may be readable by, injected into, or derived from web content — and no credential obtained by web content may be promoted into the browser's token database. The promotion path is precisely the Dice handler of PO-R2. |
| A **cookie jar** | A browser-level identity must not authenticate using the cookies of the profile's ordinary browsing jar, and must not write into it. Gaia cookies in a tab are web state; the browser's account is not. |
| A **storage partition** | Any Sunshine-owned authenticated surface must not execute in, or read from, the storage partition used for ordinary web content in the same profile. |

**PO-R8 — Sunshine operates no browser-level OAuth of its own.** There is no
Sunshine account in Stage 1–3. If one is ever proposed, it does not reuse the
identity manager, the profile's token database, the account reconcilor, or the
profile's cookie jar; it is a separate credential in the OS credential vault
named by handoff §4.3, and it grants no access to browsing data.

**PO-R9 — the §4.3 "Secure / OAuth refresh token" row does not describe the
browser's account.** Browser refresh tokens are owned by Chromium's token
service and stored in the profile's web-data database
(`components/signin/internal/identity_manager/mutable_profile_oauth2_token_service_delegate.h`).
Sunshine must not copy, mirror, export, or re-store them anywhere, which
`docs/SESSION_PROFILE_CONTRACT.md` already forbids under its secret boundaries.
§9 records this as a defect in the handoff.

**PO-R10 — no Sunshine surface reads identity state to change browsing
behaviour.** No AI surface, dashboard, workspace, side panel, or telemetry path
may read the primary account, its email, its gaia id, its hosted-domain, or the
profile's Gaia cookies. This extends `docs/SESSION_PROFILE_CONTRACT.md`'s rule
that AI features receive no ambient access to profile data, to identity
specifically.

**The boundary is enforceable only while account consistency is disabled.** This
must be said, because it is the honest form of PO-R7: under Dice, a shared
cookie jar between browser account and web sign-in is not a leak, it is the
*design*. There is no configuration of an account-consistent browser that
satisfies PO-R7. That is an additional, independent reason PO-R2 is
unconditional.

---

## 6. First run: what is asked, in what order, and what dismissal yields

### 6.1 Upstream behaviour, read-from-source

- Whether a first run happens at all is decided by the sentinel file
  (`chrome/browser/first_run/first_run.h`), a command-line suppression switch,
  the profile being regular rather than off-the-record or guest, and a
  local-state "finished" flag.
- Policy-shaped conditions suppress it entirely and mark it finished: promotions
  disabled, sync disallowed, forced sign-in, or sign-in not allowed. **The
  keyless Sunshine build lands in the last of these (§2).**
- A profile that already has a primary account skips it.
- The intro handler exposes four actions and no others: continue with an
  account, continue without an account, set as default browser, skip default
  browser. The page's resources name three subpages in this order: the sign-in
  card, the default-browser promo, and a finish/"start browsing" step. The
  ordering is read from the resource grouping, not from a state machine;
  the state machine itself was **NOT LOCATED**.
- Four exit statuses are recorded. Reaching the end of the flow marks it
  finished and proceeds. Closing the window is treated as intent to quit the
  application, and the interrupted task does not resume. Bypassing the flow —
  opening a browser window another way — marks it finished but does not resume.
  Exiting before the consent step leaves it unfinished, and it is offered again
  at the next startup.

### 6.2 Rules

**PO-R11 — nothing in the first run may be non-dismissable.** Every step must
have a visible decline that is not a trap: no forced sign-in, no forced default
browser, no step whose only affordance is to accept, and no re-prompt on the
next launch of a step the user declined. Upstream provides "continue without an
account" and "skip default browser"; Sunshine must not remove either, reorder
them behind acceptance, or make either the visually recessive path in a way that
`docs/UX`-owned surfaces would call a dark pattern. Where the first run does not
run at all (§2), this rule has nothing to act on and remains in force for any
future build in which it does.

**PO-R12 — a user who dismisses everything gets a complete browser.** The
outcome of declining every step is: one local profile, no account, Chromium's
locale-derived default search provider, Sunshine's New Tab per
`docs/SUNSHINE_NEW_TAB_SPEC.md`, the startup behaviour
`docs/SESSION_PROFILE_CONTRACT.md` specifies, and no unresolved configuration
that a later surface nags about. Nothing may be left in a "setup incomplete"
state, and no surface may display a persistent setup reminder.

**PO-R13 — the first run must not be the only place a decision can be made.**
Anything the first run offers must remain reachable afterwards from settings, so
that dismissal is cheap. A first run that asks nothing is acceptable under
PO-R12; a first run that asks something *once only* is not.

**PO-R14 — the first run is never a Sunshine-authored replacement.** Sunshine
does not add a second onboarding surface beside Chromium's, does not gate the
first browser window behind a Sunshine screen, and registers no command for
onboarding: the twenty-four commands in `first_party/commands.json` contain none
for profile creation, sign-in, or deletion, and this document adds none. If
first-run product copy is ever required it arrives as a reviewed native WebUI
change under ADR 0002, not as an interstitial.

### 6.3 Profile creation after the first run

Creating a second or later profile is the same ruling: an account is not
required, the picker's "add new profile" path must reach a usable local profile,
and the profile's name and avatar are local display data —
`docs/SESSION_PROFILE_CONTRACT.md` already states that a display name is not a
filesystem identifier or an authorization boundary. Sunshine must not
pre-populate a name from an account, and must not make naming mandatory.

---

## 7. Profile deletion and what it must destroy

### 7.1 Upstream lifecycle, read-from-source

`chrome/browser/profiles/delete_profile_helper.h` documents five stages —
scheduling, marking, cleanup, orphaning, disk deletion — plus two startup
fail-safes that nuke ephemeral profiles and directories recorded in a
deleted-profiles preference. The implementation additionally, at the pinned tag:

- clears the primary account **before** removing browsing data, explicitly so
  that the deletion does not propagate to other devices through sync;
- removes the profile's browsing data immediately rather than waiting for
  shutdown, because "we promised that the user's data would be removed";
- removes the profile from the attributes storage;
- in the ephemeral-cleanup fail-safe specifically — not on the user-initiated
  path read here — also removes the profile from the last-active list and
  deletes its web-app shortcuts on a separate task runner;
- deletes the directory immediately if the profile was never loaded, and
  otherwise on the **next startup**, to avoid file locks;
- ensures another profile exists before the last one is deleted.

### 7.2 Rules

**PO-R15 — Sunshine deletes nothing itself.** Deletion goes through the upstream
helper, with its confirmation and shutdown rules intact. Sunshine must not
remove a profile directory, edit the attributes storage, or clear the
deleted-profiles preference. This restates
`docs/SESSION_PROFILE_CONTRACT.md`'s profile-deletion rule, from the destruction
side, and does not weaken it.

**PO-R16 — deletion must destroy every Sunshine-owned trace of the profile.**
The workspace catalog and any other Sunshine metadata keyed to the deleted
profile are removed in the same operation. A workspace, a pinned surface, a
recently-executed-command list, or any cached label that outlives the profile it
described is a leak of a deleted profile into a surviving one, and is prohibited.
Sunshine metadata is keyed by profile precisely so this is possible.

**PO-R17 — deletion may not be presented as instantaneous or as secure
erasure.** Two upstream facts make the stronger claim false: the directory of a
loaded profile survives until the next startup, and the profile's directory
basename remains in Local State until cleanup succeeds. Neither is a defect —
both exist to survive a crash — but product copy that says "permanently deleted"
without qualification would be untrue, and no Sunshine surface may claim
overwriting, shredding, or unrecoverable erasure of disk contents.
`docs/SESSION_PROFILE_CONTRACT.md` already refuses the adjacent claim about OS
isolation and disk encryption; this is the same refusal.

**PO-R18 — deletion order is not Sunshine's to change.** In particular the
sign-out-before-wipe ordering exists for a specific reason recorded upstream. If
L2 ever exists (PO-R3), reordering or skipping that step would turn a local
deletion into a remote one.

**PO-R19 — deleting a profile must never delete or damage another.** Including
the case where the deleted profile is the last one, where upstream creates a
replacement. `docs/SESSION_PROFILE_CONTRACT.md` SRA-12 already tests the
neighbouring-profile half; §10 adds the last-profile half.

---

## 8. Invariants

| ID | Invariant |
|---|---|
| PO-1 | Sunshine ships no onboarding, sign-in, sync, or profile-deletion implementation. Every behaviour in this document is upstream's, constrained by rules. |
| PO-2 | A profile can be created, named, used, and deleted with no account and no network. |
| PO-3 | Account consistency is disabled in every shipped Sunshine build. No patch, flag, switch, or embedded credential enables it. |
| PO-4 | A Google sign-in performed in a tab never becomes a browser-level identity. |
| PO-5 | Browser sign-in is not consent to sync-the-feature, and sync-the-feature is never enabled without an explicit, separately-stated user action. |
| PO-6 | No Sunshine surface presents local-only operation as an error, a warning, an incomplete setup, or a state to be resolved by signing in. |
| PO-7 | No credential, cookie jar, or storage partition is shared between a browser-level identity and web content. |
| PO-8 | Sunshine hardcodes no account, account domain, OAuth client credential, or identity endpoint. |
| PO-9 | Every first-run step is dismissable, and dismissing all of them yields a fully configured browser. |
| PO-10 | Anything the first run offers stays reachable from settings afterwards. |
| PO-11 | Sunshine registers no command and adds no interstitial for onboarding. |
| PO-12 | Profile deletion runs through Chromium's helper, in Chromium's order, and additionally destroys all Sunshine metadata keyed to that profile. |
| PO-13 | No Sunshine surface claims secure or instantaneous erasure on profile deletion. |
| PO-14 | No Sunshine surface, including AI and telemetry paths, reads primary-account identity or Gaia cookie state. |
| PO-15 | Nothing in onboarding writes a user identifier, account address, or profile path containing one into logs, crash reports, exported configuration, or workflow artifacts. |

---

## 9. Defects found in shipped content

**D1 — handoff §5.2's "Google is optional" is not achievable as written, and its
definition-of-done cannot fail.** In a build permitted by ADR 0002 there is no
Google option (§2), so "optional" overstates what exists, and "auth failure does
not block browser launch" is vacuous because no auth is attempted. This document
supersedes both halves: §3 and §4 for the requirement, §10 for a
definition-of-done that can fail.

**D2 — handoff §4.3 assigns "OAuth refresh token" to a Sunshine-owned OS
credential vault.** Read against §5.6.6 this is a contradiction: the browser's
refresh tokens are Chromium's and live in the profile's encrypted web-data
database. The row can only legitimately describe a future Sunshine-service
credential. PO-R9 states the correct division; the handoff row should be
narrowed by whoever owns it.

**D3 — `docs/ACCEPTANCE_SUITES.md` finding U2 and the section 9 P0 are now
answered.** §3.2 of that document records handoff §5.6.6 as **Uncovered** with
"nothing" as its owning criterion. This document is the owner; the row and the
P0 should be updated by the wave that owns that index. This document does not
edit it.

**D4 — "login persistence" in handoff §5.7 is ambiguous and has been read both
ways.** It means website login, not browser sign-in (§3.3). Left unqualified it
invites an implementer to satisfy a dogfood line by enabling sign-in, which
PO-R2 forbids.

**D5 — `docs/SESSION_PROFILE_CONTRACT.md` states a profile-deletion rule while
declaring itself the steady-state contract.** Not a contradiction, but the
boundary is now: that document's rule stands, and §7 here extends it with the
lifecycle, the Sunshine-metadata obligation, and the claims that may not be
made. If the two ever diverge, that document wins.

**D6 — no document previously stated what local-only costs.** `docs/SESSION_PROFILE_CONTRACT.md`
defers "cross-device tab sync and encrypted backup policy" without saying that
their absence is the shipped state rather than a gap. §3.2 states the cost.

---

## 10. Acceptance criteria

Classes follow `docs/ACCEPTANCE_SUITES.md` §1.2: **O** decidable against this
repository today, **B** needs a native build and a harness, **H** needs a person.
Every criterion below is **NOT RUN**, and every one that is not class O is
**NOT AVAILABLE** until a native build exists.

| ID | Criterion | Class |
|---|---|---|
| PO-A1 | No file in `first_party/`, `downstream/`, `scripts/`, or `config/` contains an OAuth client id, client secret, or Google API key, in any encoding. | O |
| PO-A2 | The patch stack contains no change to the account-consistency, identity-manager, Dice-handler, sync-service, or first-run-service source areas. | O |
| PO-A3 | `first_party/commands.json` registers no command for profile creation, sign-in, sync, or profile deletion. | O |
| PO-A4 | Every upstream path cited by this document resolves at the pinned revision. | O |
| PO-A5 | On a clean user-data directory with no network interface available, the browser launches, creates a profile, and reaches a usable New Tab with no error surface, no retry loop, and no blocking dialog. | B |
| PO-A6 | In a build produced by this repository's pipeline, the profile's account-consistency method is *disabled* and the profile has no primary account at either consent level, on first launch and after a restart. | B |
| PO-A7 | Sign in to a Google property in an ordinary tab, restart, and assert the browser still has no primary account at either consent level, that no refresh token exists in the profile's token storage, and that no identity is shown in any browser surface. | B |
| PO-A8 | Assert the sync service reports no primary account and is not active, in both transport and feature senses, with no user action having been taken to disable it. | B |
| PO-A9 | Create a second profile through the picker without an account. Assert it is usable, isolated per `docs/SESSION_PROFILE_CONTRACT.md` SRA-9, and that its creation issued no network request. | B |
| PO-A10 | Delete a profile that has fixture bookmarks, history, cookies, a saved password, a workspace, and a downloaded file. Assert: the surviving profile is untouched; every Sunshine metadata record keyed to the deleted profile is gone; the profile is absent from the picker and the last-active list; and after the next restart its directory is absent from disk. | B |
| PO-A11 | Delete the last remaining profile. Assert a usable replacement profile exists, the browser remains launchable, and no data from the deleted profile appears in it. | B |
| PO-A12 | Interrupt a deletion by terminating the browser between marking and disk deletion. Assert the next startup completes the deletion and that the partially deleted profile is not offered as usable. | B |
| PO-A13 | With canary values in an account-shaped fixture (an email-like string in a profile name, a fixture Gaia cookie), exercise creation, first run, and deletion; assert no canary appears in logs, crash reports, exported configuration, or workflow artifacts. | B |
| PO-A14 | Walk the first run, where one is shown, declining every step. Assert each step had a visible decline, that the end state matches PO-R12, that no step reappears on the next launch, and that every declined option is reachable from settings. | H |
| PO-A15 | Confirm no product surface describes local-only operation as an error, a warning, or an incomplete setup, and that no surface claims permanent or secure erasure on deletion. | H |

PO-A1 through PO-A4 are class O and are the first criteria in this contract set
addressed to onboarding that could run today; `docs/ACCEPTANCE_SUITES.md` §1.2
records that no line of any stage acceptance suite is class O. None of them is
wired to a check in `scripts/` by this wave, and doing so is the natural next
piece of work.

---

## 11. Upstream-roll gate

Each Chromium revision update must re-read the source areas in §1 and re-run
this suite. The roll is **blocked** pending explicit review if the new revision
changes any of:

- the condition under which account consistency is enabled, or the predicate on
  a configured OAuth client;
- the relationship between the signin-allowed preference and whether a first run
  is shown;
- what browser sign-in enables without further opt-in;
- the set of first-run steps, their dismissability, or their exit statuses;
- the profile-deletion lifecycle, its ordering, or its fail-safes;
- where refresh tokens are stored, or what may read them.

The correct response to an upstream change is to adapt at Chromium's supported
integration boundary. Sunshine must not introduce a parallel identity, a
Sunshine-owned onboarding flow, or a second deletion path to preserve an
obsolete assumption here — the failure mode `docs/TAB_WORKSPACE_SPLIT_CONTRACT.md`
§0 records.

---

## 12. Open questions for the product owner

| Priority | Question | Required by |
|---|---|---|
| P0 | Is a **permanently** account-free browser the product, or is local-only the Stage 1 state of a browser that later gains an identity? §2 shows the first is what a permitted build produces today; §4 PO-R3 lists what the second would cost. Everything about deletion ordering, the OAuth boundary, and first-run copy depends on the answer. | Stage 1 security release |
| P0 | Given that the keyless build suppresses the first-run experience entirely, is **no first run** acceptable? A user then never sees a default-browser prompt or any welcome. PO-R12 makes that state complete and legitimate; whether it is desirable is a product call. | Stage 1 exit |
| P1 | Does profile deletion have a **backup or export** obligation before it destroys? The handoff already carries a P0 on default data-deletion and backup policy; §7 here specifies destruction and deliberately specifies no export, which `docs/SESSION_PROFILE_CONTRACT.md` also defers. | before persistence release |
| P1 | Is the **profile display name** allowed to be an email address or other personal identifier? PO-15 forbids it reaching logs; whether the field should be constrained at entry is a UX decision. | Stage 3 profile release |
| P2 | Should Sunshine ship its own **local-only backup** (an encrypted local export) as the honest substitute for the sync that §3.2 says it does not have? Out of scope here; it would need its own contract. | Stage 3 |
