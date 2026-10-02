---
doc_id: adr-0024-drm-widevine
version: 1.1.0
canonical_path: docs/decisions/0024-drm-widevine.md
updated: 2026-10-02
---

# ADR 0024: Widevine, under the same personal-use premise — and a licence that is not the same

## Status

Accepted, conditionally, on the owner's decision of 2026-09-13. The condition is
narrower than ADR 0004's and §4 says why. Read against the pinned revision
`152.0.7977.42`. **Nothing here is verified at runtime**; §6 is the list.

## Context

The owner opened Netflix on build #57 and got:

> 서비스 이용에 불편을 드려 죄송합니다
> chrome://settings/content/protectedContent에서 '사이트가 보호된 콘텐츠를 재생할 수 있음'을 선택하세요.
> 오류 코드: **M7701-1003**

The message names a setting, and the setting is not the problem. `third_party/widevine/cdm/widevine.gni`:

```gn
enable_widevine = ((is_chrome_branded || is_chrome_for_testing_branded) &&
                   !is_fuchsia) || is_android
```

Sunshine sets none of those, so `enable_widevine` is false **by derivation, not
by a choice anyone made** — the same shape as `proprietary_codecs` in ADR 0004,
found the same way, by a user-visible failure rather than by a document.

## 1. What one argument turns on

`enable_widevine=true` is a `declare_args()` value; the file's own comment says
it "can be optionally enabled in Chromium on non-Android platforms". On Windows
x64 at the pin it derives:

| Derived | Value | Why it matters |
| --- | --- | --- |
| `enable_library_cdms` | true | `toolkit_views && !is_castos` |
| `library_widevine_cdm_available` | true | `target_os == "win" && target_cpu == "x64"` |
| `enable_library_widevine_cdm` | **true** | the three above |
| `enable_widevine_cdm_component` | **true** | not a `declare_args`; derived for `is_win` |
| `bundle_widevine_cdm` | **false** | default is `… && (is_chrome_branded \|\| is_chrome_for_testing_branded)` |
| `enable_widevine_cdm_host_verification` | **false** | needs `enable_cdm_host_verification`, which needs `is_chrome_branded` |

Two of those rows are the ones that make this cheap rather than impossible.

**`bundle_widevine_cdm` stays false**, so the build does not look for a CDM
binary in the tree. `third_party/widevine/README.chromium` says "No third-party
files are checked in here", and nothing needs to be: `enable_widevine_cdm_component`
means `chrome/browser/component_updater/registration.cc` calls
`RegisterWidevineCdmComponent(cus)` — gated on `ENABLE_WIDEVINE_CDM_COMPONENT`
and on nothing else, no API key — and the CDM arrives at run time, from Google,
to the machine that asked for it.

**`enable_widevine_cdm_host_verification` stays false**, which disarms a trap
this build would otherwise have walked into. `ignore_missing_widevine_signing_cert`
defaults to `!is_official_build`, and Sunshine sets `is_official_build=true`, so
a missing Widevine signing certificate would have **failed the build** — the
comment in `widevine.gni` says so in as many words. Host verification is off
because it requires `is_chrome_branded`, so no signing action is generated and
the certificate is never looked for.

## 2. Decision

**Set `enable_widevine=true` in `scripts/build_chromium_windows.ps1`.**

Zero upstream files. Zero patches. It is a build argument, exactly like ADR
0004's pair, and it sits beside them with the premise named in the comment.

## 3. Cost

One argument, one rebuild. The media stack does not recompile the way ADR 0004's
change did — this adds the CDM host and key-system plumbing rather than changing
FFmpeg's sources.

## 4. The premise is the same sentence and it is doing more work here

ADR 0004: the owner builds Sunshine for themselves, runs it on their own
machines, and does not distribute it.

**That premise does not carry over unchanged, and this section exists so that
nobody later assumes it did.** `third_party/widevine/LICENSE`, in full:

> Google LLC and its affiliates ("Google") own all legal right, title and
> interest in and to the content decryption module software ("Software") and
> related documentation, including any intellectual property rights in the
> Software. You may not use, modify, sell, or otherwise distribute the Software
> without a separate license agreement with Google. The Software is not open
> source software.

H.264's licensing question is **about distribution**, which is why a
private-tool premise answers it. This text names **use**. So the argument that
made ADR 0004 comfortable is weaker here, and the honest statement of what was
decided is:

- what this repository turns on is **Chromium's support for a key system**,
  which is open-source code in the Chromium tree;
- the Software the licence speaks of is `widevinecdm.dll`, which this repository
  never contains, never copies and never redistributes — it is delivered by
  Google's own component updater to the owner's own machine;
- whether an owner running that delivered binary for themselves is within the
  licence is **a question for Google's terms and not for this document**, and it
  was put to the owner before the flag was set rather than after.

The owner was shown the paragraph above and said to proceed. That is the
decision, and it is recorded as a decision rather than as an analysis.

**This decision does not travel with the artifact**, and less so than ADR
0004's. Publishing a release, handing a build to a colleague, or shipping to any
third party requires revisiting this ADR *first*, and the default at that point
is off.

## 5. Alternatives considered

**Leave it off; watch DRM video in another browser.** Costs nothing and was
offered first. Rejected by the owner, who wants Sunshine to be the browser they
actually use.

**Copy `widevinecdm.dll` out of an installed Chrome.** Rejected here, not
merely unchosen. It reaches the same running state while doing the one thing the
licence text names first — copying the Software — and it puts a binary of
unknown provenance beside `chrome.exe` with no updater behind it, so it also
goes stale and silently stops working. Naming it as refused is the point: it is
what a search will suggest.

**`bundle_widevine_cdm=true`.** Requires the CDM under `widevine_root`, which
would mean checking a proprietary binary into this repository. Refused for the
same reason, more so.

## 6. NOT VERIFIED

**Nothing below has been observed. All of it needs build #58 and a person.**

- **That the component updater actually fetches the CDM.** This is the whole
  mechanism and it is the part a source reading cannot settle. The registration
  is unconditional given the build flag; whether Google's service serves a CDM
  to a browser calling itself Sunshine, with no API key and an unbranded user
  agent, is an empirical question. **RV-56 is that question** and it is the gate
  that decides whether this ADR worked.
- **How long it takes.** Component fetch is not synchronous with the first
  playback attempt. A first Netflix load may still fail and succeed on a retry
  minutes later; RV-56 says to wait and retry before recording FAIL.
- **That `chrome://components` lists it.** The expected row is *Widevine Content
  Decryption Module*, and its version reading `0.0.0.0` means registered but not
  yet downloaded — which is a different result from absent and RV-57 separates
  them.
- ~~**Whether `chrome://settings/content/protectedContent` exists and is on.**~~
  **Settled from source on 2026-10-02 — see §7.** It is allowed by default and
  no Sunshine patch touches it, so it cannot be the cause. Checking it is
  still worth one look as RV-58, but it is no longer a candidate.
- **Any interaction with the sandbox.** The CDM runs in its own utility process.
  `docs/SECURITY_INVARIANTS.md`'s guarantees are about the renderer, and whether
  a CDM process changes anything they claim has not been examined.

## 7. Addendum, 2026-10-02 — four candidates removed from source

The owner reported a Netflix playback error again. Before asking them for
anything, four of the possible causes were checked against the pinned revision
and **all four are ruled out**. They are written down because each is what a
search would suggest first, and re-deriving them costs a session each time.

| Candidate | Verdict | Evidence at `152.0.7977.42` |
| --- | --- | --- |
| The build argument was never applied | **Ruled out** | `scripts/build_chromium_windows.ps1` carries `enable_widevine=true`, and build #62's commit `663db5d` already contained it |
| Codecs are missing | **Ruled out** | the same file carries `proprietary_codecs=true` and `ffmpeg_branding="Chrome"` |
| Registration is gated on branding or an API key | **Ruled out** | `chrome/browser/component_updater/registration.cc` calls `RegisterWidevineCdmComponent(cus)` under `BUILDFLAG(ENABLE_WIDEVINE_CDM_COMPONENT)` and nothing else; the function body in `widevine_cdm_component_installer.cc` is three lines — construct the policy, `Register` — with no early return, no brand check and no key |
| The update endpoint is brand-gated | **Ruled out** | `components/component_updater/component_updater_url_constants.cc` hard-codes `https://update.googleapis.com/service/update2/json`, overridable only by `--component-updater=url-source=`. No branding appears in the file |

**And the setting the error message named is allowed by default.**
`components/content_settings/core/browser/content_settings_registry.cc`
registers `ContentSettingsType::PROTECTED_MEDIA_IDENTIFIER` with a default of
`CONTENT_SETTING_ALLOW` and lists `PLATFORM_WINDOWS` among its platforms. §Context
said "the message names a setting, and the setting is not the problem" as a
reading; this is that reading checked. Separately, **no patch in the stack of 32
touches Chromium's settings WebUI, media stack, CDM or component updater** — so
the page is upstream's, unmodified.

### What is left, and the one check that separates it

Everything remaining is downstream of the build, which is where §6 always said
the answer would be. **RV-57 is the whole diagnosis and it takes one page load.**
`chrome://components`, row *Widevine Content Decryption Module*:

| What the row shows | What it means | Next |
| --- | --- | --- |
| **No row at all** | the running build does not carry `ENABLE_WIDEVINE_CDM_COMPONENT` | The installed binary predates the flag. The last successful build is **#62, 2026-09-13**; the error in §Context was first seen on **#57**. Install a #62-or-later artifact, or build |
| Version **`0.0.0.0`** | registered, never fetched — the component updater is failing, not the build | Press *Check for update* on the row. If it stays `0.0.0.0`, this is precisely the empirical question §6 named: whether Google's service serves a CDM to an unbranded browser |
| A real version | the CDM is present and the fault is elsewhere — output protection, or Netflix's own side | Record the error code and read it against the CDM version |

Then RV-56, **with its retry**: the component fetch is not synchronous with the
first playback attempt, so a first failure followed by a later success is a PASS
and recording FAIL without waiting answers a different question.

**The error code matters and is not recorded here**, because this addendum was
written without it. `M7701-1003` is the code §Context saw and it points at the
protected-content setting, which the table above removes. A different code points
somewhere else, so the code is the first thing to capture on the next attempt.
