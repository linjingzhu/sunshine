# Extension and MIME Type — Download Naming Contract

## Status and scope

This contract applies to Sunshine OS on the pinned Chromium revision
`152.0.7977.42` recorded in `config/chromium.version`.

**Settles:** the second clause of section 5.6.4 of
`docs/SUNSHINE_OS_STAGE_1_TO_3_IMPLEMENTATION_HANDOFF.md` — "flag extension/MIME
mismatch" — which `docs/ACCEPTANCE_SUITES.md` records as finding U7 and as the
unowned half of its §5.6 row 4.

**Decides:** that Sunshine writes no code for it, on evidence read from the
pinned sources rather than on preference.

This wave is documentation-only. It adds no downstream patch, no first-party
module, no command, and no guard. Nothing in it has been executed; see *Not
verified*.

## Boundary against `docs/DOWNLOAD_SAFETY.md`

The two documents divide at the moment a danger verdict exists.

| | `docs/DOWNLOAD_SAFETY.md` | This contract |
|---|---|---|
| Subject | `DownloadUIModel` and `DownloadDangerType` | `DownloadTargetDeterminer` and the target filename |
| Question | Once Chromium has classified a download, what may Sunshine show and do? | Before any classification exists, how is the file's name, extension and type settled, and does Sunshine take part? |
| Owns | Warning and review surfaces, provenance presentation, command dispatch, warning-event recording, and the open P0 on warn-versus-block per danger category | Extension derivation, the comparisons between extension and MIME type made during it, and the prohibition on a Sunshine mismatch signal |

The seam between them is one value: `virtual_path_.BaseName()`. It is the last
output of this contract's subject and the first argument to
`FileTypePolicies::GetFileDangerLevel`, whose result becomes the danger type
that `docs/DOWNLOAD_SAFETY.md` governs the presentation of.

Neither document adds a classifier. `docs/DOWNLOAD_SAFETY.md` states that
Chromium owns classification and command eligibility; this one states that
Chromium also owns the naming and typing that feed it. Where a rule there
already covers a case named here it is cited, not repeated. Two of its rules are
load-bearing for this contract and are not restated as new: a file must not be
classified as risky merely because it has an unfamiliar extension, and no
download URL or file metadata may be sent to a Sunshine service.

## The four type signals, and where each lives

A download carries four distinguishable statements about what it is. Any
mismatch claim is a comparison between two of them, so they have to be named
apart before anything can be said about mismatch.

| Signal | Where it is read at the pinned revision | Who controls it |
|---|---|---|
| **Declared type** — the `Content-Type` header as received | `DownloadItem::GetOriginalMimeType()`, [`components/download/public/common/download_item.h`](https://github.com/chromium/chromium/blob/152.0.7977.42/components/download/public/common/download_item.h) | the server |
| **Effective type** — the declared type after network-layer sniffing | `DownloadItem::GetMimeType()`, same header; the target determiner names its local copy `sniffed_mime_type` | the server, plus the first `net::kMaxBytesToSniff` (1024) bytes, and only where [`net/base/mime_sniffer.h`](https://github.com/chromium/chromium/blob/152.0.7977.42/net/base/mime_sniffer.h)'s `ShouldSniffMimeType` allows it — that function checks the `nosniff` header, which the server also sets |
| **Extension** — of the candidate target path | `virtual_path_.Extension()` and `.BaseName()` in [`chrome/browser/download/download_target_determiner.cc`](https://github.com/chromium/chromium/blob/152.0.7977.42/chrome/browser/download/download_target_determiner.cc), derived from the URL, the `Content-Disposition` filename, a page-supplied suggested name, or a browser-extension override | the server and the page, with a browser extension able to override |
| **Path-derived type** — the MIME type implied by the final local file name | `ChromeDownloadManagerDelegate::GetFileMimeType`, [`chrome/browser/download/chrome_download_manager_delegate.cc`](https://github.com/chromium/chromium/blob/152.0.7977.42/chrome/browser/download/chrome_download_manager_delegate.cc), over `net::GetMimeTypeFromFile` in [`net/base/mime_util.h`](https://github.com/chromium/chromium/blob/152.0.7977.42/net/base/mime_util.h) | the filename Chromium has just settled on |

The header documents the second and first as distinct on purpose: `GetMimeType()`
is "effective MIME type of downloaded content" and `GetOriginalMimeType()` is the
"Content-Type header value from HTTP response", which "may be different from
`GetMimeType()` if a different effective MIME type was chosen after MIME
sniffing".

## What Chromium already compares

Five comparisons, all inside target determination, all at the pinned revision.

| # | Comparison | Where | What it does |
|---|---|---|---|
| 1 | extension against the **effective type** | `DownloadTargetDeterminer::GenerateFileName()` calls `net::GenerateFileName(..., should_replace_extension)` ([`net/base/filename_util.h`](https://github.com/chromium/chromium/blob/152.0.7977.42/net/base/filename_util.h)), which reaches `EnsureSafeExtension` and `GetCorrectedExtensionUnsafe` in [`net/base/filename_util_internal.cc`](https://github.com/chromium/chromium/blob/152.0.7977.42/net/base/filename_util_internal.cc) | If the extension is absent from `net::GetExtensionsForMimeType(effective type)` — and the final component of a double extension is too — the extension is **replaced** with `GetPreferredExtensionForMimeType`. Chromium does not flag the mismatch; it removes it. |
| 2 | **effective type against declared type**, literally | `GenerateFileName()`: `sniffed_mime_type == "text/plain" && GetOriginalMimeType() != "text/plain"` | Detects the `nosniff` and plain-text-family case (csv and similar) and prefers the URL-derived extension instead of rewriting everything to `.txt`. |
| 3 | a browser extension's suggested extension against the current one | the file-local `GenerateSafeFileName` helper in `download_target_determiner.cc`, called from `NotifyExtensionsDone` and, on Windows, after filename sanitisation | Passes the MIME type with `ignore_extension` set only when the two differ, "so that it does not force the filename to have an extension or generate a different one" when they agree. |
| 4 | **path-derived type** against what the browser can render | `DownloadTargetDeterminer::DetermineIfHandledSafelyHelper`, over `blink::IsSupportedMimeType` and the plugin service | Sets `is_filetype_handled_safely_`. This is a capability question, not a safety verdict. |
| 5 | the **corrected** basename against the file-type policy | `DownloadTargetDeterminer::GetDangerLevel()` calls `FileTypePolicies::GetFileDangerLevel(virtual_path_.BaseName(), ...)`, [`components/safe_browsing/content/common/file_type_policies.h`](https://github.com/chromium/chromium/blob/152.0.7977.42/components/safe_browsing/content/common/file_type_policies.h) | Produces the danger level that becomes `DOWNLOAD_DANGER_TYPE_DANGEROUS_FILE`. |

### The ordering is the point

`STATE_GENERATE_TARGET_PATH` precedes `STATE_CHECK_VISITED_REFERRER_BEFORE` in
the state enumeration in
[`chrome/browser/download/download_target_determiner.h`](https://github.com/chromium/chromium/blob/152.0.7977.42/chrome/browser/download/download_target_determiner.h),
and `GetDangerLevel` runs in the later one. So comparison 1 has already
rewritten the extension by the time comparison 5 classifies it.

Chromium's answer to extension/MIME mismatch is therefore not a warning and not
a verdict. It is a **reconciliation performed before classification**, whose
output is the input to classification. A file served as an executable type under
a `.txt` URL is not flagged as inconsistent; it is renamed to the executable
extension and then classified as a dangerous file type by the ordinary path.
That is strictly stronger than flagging, because the corrected extension also
governs the OS shell association, the auto-open preference, and the quarantine
attributes — none of which a flag would reach.

### There is nowhere to put a mismatch verdict

Two facts read from the pinned sources close the question of adding one.

- [`components/download/public/common/download_danger_type.h`](https://github.com/chromium/chromium/blob/152.0.7977.42/components/download/public/common/download_danger_type.h)
  enumerates twenty-six values covering dangerous files, URLs, content, hosts,
  unwanted software, policy allowlisting, five scanning states and four
  enterprise blocking states. None of them is a type mismatch. The enumeration is
  persisted to logs, is mirrored in a generated Java enum, and its comments
  forbid renumbering — it is not a place a downstream adds a member.
- `FileTypePolicies` has **no MIME-typed API at all**. Every entry point —
  `IsArchiveFile`, `IsCheckedBinaryFile`, `IsAllowedToOpenAutomatically`,
  `GetFileDangerLevel`, `PingSettingForFile`, `PolicyForFile`, `SettingsForFile`,
  `GetMaxFileSizeToAnalyze` — takes a `base::FilePath` or an extension string.
  The table it reads, `components/safe_browsing/content/resources/download_file_types.asciipb`,
  is keyed on extensions. Correspondingly,
  [`chrome/browser/safe_browsing/download_protection/check_client_download_request.cc`](https://github.com/chromium/chromium/blob/152.0.7977.42/chrome/browser/safe_browsing/download_protection/check_client_download_request.cc)
  contains no MIME-type reference.

A Sunshine mismatch signal would therefore need its own extension-to-type table
to be evaluated against. That is a second file-type policy, which is the
duplicated-`SplitTabCollection` defect committed in the one place in this product
where being wrong has a consequence.

## The residual set

Comparison 1 is guarded. Each guard leaves a case where extension and effective
type still disagree after target determination. This is the complete list, in the
order the code applies it, and it is the only set a Sunshine mismatch flag could
ever fire on.

| | Condition | Chromium's reason |
|---|---|---|
| **r1** | the effective type is empty | nothing to compare against |
| **r2** | a page- or extension-supplied `suggested_filename` exists | the name was chosen deliberately by something other than the server's headers |
| **r3** | `Content-Disposition` carries a `filename` | stated in the source as "Trust content disposition header filename attribute" |
| **r4** | `FileTypePolicies::IsCheckedBinaryFile` is true for the generated name | stated in the source: do not replace the extension when Safe Browsing considers it unsafe — "just let safe browsing scan the generated file" |
| **r5** | effective type is `text/plain` and the declared type is not | the `nosniff` and csv case; comparison 2 |
| **r6** | the effective type has no preferred extension — `application/octet-stream` is the common instance | there is no better extension to offer |
| **r7** | the extension is already among the valid extensions for the effective type, including the final component of a double extension | avoids renaming `foo.jpg` to `foo.jpeg` or `foo.tar.gz` to `foo.gz` |

**r7 is not a mismatch** — it is the code declining a cosmetic rename. **r1 and
r6** are the absence of a comparable signal, not a disagreement. **r4** is a
deliberate preservation in the safe direction: the dangerous extension is kept
precisely so the dangerous-file path and the content check both see it.

That leaves **r2, r3 and r5** as the real residual, and all three are cases where
Chromium has decided that a name chosen by something other than the header is
more trustworthy than the header.

## Decision

**Sunshine implements nothing for handoff §5.6.4's mismatch clause.** It writes
no comparison, no signal, no flag, no table, and no surface. The requirement is
satisfied by the pinned revision, and satisfied more strongly than the clause
asks.

This is an intentional **zero-runtime-patch** decision on the same grounds as
`docs/PERMISSION_POLICY.md` and `docs/BROWSER_UTILITIES_CONTRACT.md`. Four
reasons, in descending strength.

1. **The risk the clause is reaching for is already measured directly.** The
   extension is what the operating system acts on when the file is opened, and
   Chromium's danger classification is keyed on the extension after correction.
   The dangerous condition is therefore "the extension is dangerous", not "the
   extension disagrees with a header". The former is evaluated on every download
   by comparison 5; the latter is a lossy proxy for it. Replacing a direct
   measurement with a proxy is a regression even when the proxy is cheap.

2. **A warning over the residual set would be noise.** r2, r3 and r5 arise
   overwhelmingly from ordinary server misconfiguration — a static host serving
   everything as `application/octet-stream`, a CMS emitting a `Content-Type` that
   does not match the file it attached. A warning that fires on those and not on
   the attacker is the failure mode `docs/DOWNLOAD_SAFETY.md` already prohibits
   in its product contract, and it trains users to dismiss the warnings that
   matter.

3. **Both sides of the comparison are attacker-controlled.** In r2 and r3 the
   filename and the `Content-Type` come from the same response, written by the
   same party. An attacker who wants the file called `invoice.pdf` sets both
   consistently and produces no mismatch at all. The only input not fully under
   the attacker's control is the sniffed content — and `ShouldSniffMimeType`
   honours `nosniff`, which the attacker also sets, over at most 1024 bytes, in a
   sniffer whose own header asks that it not be widened. The signal can be
   suppressed and induced at will by the party it is meant to detect.

4. **The one case worth catching is already caught, and better.** A real
   executable delivered under a benign declared type is r4, and Chromium's answer
   there is stronger than a warning: keep the dangerous extension, and let the
   content check run against it.

## Security boundary

A mismatch value is a function of the `Content-Type` header, the
`Content-Disposition` header, the URL, and up to 1024 bytes of the body. Three of
the four are set by the server outright and the fourth is suppressible by a
header the server also sets. **Any mismatch signal is attacker-influenced in both
directions**: an attacker can cause it to appear on a benign file and cause it to
vanish on a malicious one.

That fixes what such a signal may be used for, if a later wave ever computes one.

**It may not:**

- set, raise, lower, or annotate a `DownloadDangerType`;
- change what `DownloadCommands` permits — already prohibited by
  `docs/DOWNLOAD_SAFETY.md`'s patch boundary, restated here only to name the
  instance;
- block, cancel, delay, quarantine, rename, or auto-discard a download;
- gate opening a file, or alter an auto-open preference;
- become an input to, or a verdict from, a `ThreatProtectionProvider`. SC-2 keeps
  every provider off the critical path of a download and SC-10 holds a provider
  `block` at an attributed advisory; a mismatch routed through the provider
  abstraction would be exactly the second blocking path both invariants exist to
  prevent, and would arrive there wearing Chromium's authority rather than its
  own;
- leave the machine. `docs/DOWNLOAD_SAFETY.md` already forbids a Sunshine service
  receiving download URLs or file metadata; the extension, both MIME strings and
  the filename are file metadata, and `docs/SECURITY_CENTER_CONTRACT.md`'s egress
  list does not contain any of them;
- be recomputed from the file's bytes by first-party code. Reading the payload to
  sniff it would put a Sunshine module in the download data path, which
  `docs/BROWSER_UTILITIES_CONTRACT.md` invariant 12 and `docs/DOWNLOAD_SAFETY.md`
  both forbid for the adjacent surfaces.

**It may, in principle:** be counted. A boolean histogram of how often a
correction occurred, carrying no URL, no filename, no extension and no MIME
string, is compatible with `docs/TELEMETRY_CONTRACT.md`'s record-and-do-not-report
position. Nothing in Stage 1 computes it and this contract does not ask for it;
the possibility is recorded so that a future wave that wants the number knows the
only shape it may take.

## Interaction with the adjacent contracts

**`docs/PERMISSION_POLICY.md`.** Its inherited-behaviour stance is the same
argument applied to content settings, and its *Deferred work* list names
"download danger classification, file picker, and download shelf/bubble UX". This
contract answers the naming-and-typing part of that line for Stage 1 and leaves
the rest where it sits. One consequence has to be stated because it is an easy
mistake: the `AUTOMATIC_DOWNLOADS` setting is `ASK` and governs *how many*
downloads a site may start, never *what type*. Wiring a type or mismatch signal
into that category would give a Chromium content setting a meaning its own
registry does not give it, which is the second-permission-system failure that
contract prohibits.

**`docs/SECURITY_CENTER_CONTRACT.md`.** The threat-provider abstraction is
advisory, asynchronous, off the critical path, and may only move severity in the
direction Chromium already chose (SC-1, SC-2). A mismatch is not a provider
verdict, must not be modelled as one, and must not be sent to one. The centre may
display Chromium-reported download events under its existing rules; it gains no
new event kind from this contract and no new row type.

**`docs/ACCEPTANCE_SUITES.md`.** Its §5.6 row 4 records the mismatch half as owned
by "nothing" and finding U7 states the same. On the evidence above the correct
verdict for that half is covered by inheritance, by the same mechanism that made
§5.6.1 and §5.6.3 withdrawals rather than gaps. Correcting that row is the index's
to make, not this document's.

## Invariants

Each is falsifiable — the first four against this repository's sources today, the
rest once a native build exists.

| | Invariant |
|---|---|
| **XM-1** | Sunshine performs no comparison between a download's file extension and any MIME type. No first-party mismatch predicate, field, enum member, stored flag, or derived boolean exists. |
| **XM-2** | Sunshine holds no file-type policy of its own: no extension table, no MIME table, no extension-to-danger map, no list of executable or script-like extensions. `FileTypePolicies` at the pinned revision is the only such table in the product. |
| **XM-3** | The download filename is whatever `DownloadTargetDeterminer` produced. Sunshine never renames a download, never appends, strips or corrects an extension, and never re-runs the correction under its own conditions. |
| **XM-4** | No first-party code calls `net::SniffMimeType`, `net::SniffMimeTypeFromLocalData`, `net::GetMimeTypeFromFile`, `net::GetMimeTypeFromExtension`, `net::GetPreferredExtensionForMimeType`, `net::GetExtensionsForMimeType`, `net::EnsureSafeExtension`, or any equivalent of its own, and no first-party module reads the bytes of a download. |
| **XM-5** | No mismatch-derived signal sets, raises, lowers, or annotates a `DownloadDangerType`, changes `DownloadCommands` enablement, or blocks, delays, renames or auto-discards a download. |
| **XM-6** | A mismatch is never a threat-provider input or verdict and never produces a second blocking path beside Chromium's (SC-2, SC-10). |
| **XM-7** | The declared type, the effective type, the sniffed bytes, the extension and the filename never leave the machine — not to a Sunshine service, not to a provider, not in any telemetry payload. |
| **XM-8** | Any type a Sunshine download surface displays is one Chromium already holds on the item. Sunshine computes no type for display and shows no consistency claim about one. |
| **XM-9** | The `AUTOMATIC_DOWNLOADS` content setting keeps Chromium's meaning. No type, extension, or mismatch signal is wired into it or into any other content setting. |

## Command registration

This contract registers no command and proposes none. A mismatch is not a user
action, has no availability predicate, and has nothing to dispatch to;
`first_party/commands.json` remains the only authoritative list and this document
names no identifier that is not in it.

## Acceptance criteria

Classes follow `docs/ACCEPTANCE_SUITES.md` §1.2: **O** is decidable against this
repository today with no Chromium compilation; **B** needs a native build of the
pinned revision and an automated harness. There are no class **H** criteria here —
nothing in this contract is a judgement about appearance.

Like the criteria in `docs/BROWSER_UTILITIES_CONTRACT.md`, most of these test that
Sunshine has *not* interposed itself. All of them should pass on an unmodified
pinned build, and that is the point.

| | Class | Criterion |
|---|---|---|
| **XM-C1** | O | No Sunshine-authored source declares an extension list, a MIME table, a mismatch field, or an extension-to-danger mapping. Decidable over the same corpus `scripts/verify_no_interposition.py` already searches — `first_party`, the added lines of `downstream` patches, `scripts`, `config` — by the same field-extraction method. Enforces XM-1, XM-2. |
| **XM-C2** | O | No Sunshine-authored source names any of the symbols listed in XM-4. Enforces XM-4, source half. |
| **XM-C3** | O | `first_party/commands.json` registers no download command and declares no download surface. True at the state of this wave: twenty-four commands over the surfaces `bookmark`, `browser`, `tab`, `workspace`. |
| **XM-C4** | O | Roll gate. At each upstream revision change, the five guards in `GenerateFileName()` (r2–r6), the two in `GetCorrectedExtensionUnsafe()` (r7), and `GetDangerLevel()`'s use of `virtual_path_.BaseName()` still exist, and `STATE_GENERATE_TARGET_PATH` still precedes `STATE_CHECK_VISITED_REFERRER_BEFORE`. Reachable by the mechanism `scripts/verify_pinned_upstream.py` already uses for seams; today that script checks only that the cited paths resolve. |
| **XM-C5** | B | **Normal-file regression.** A download whose extension already matches its declared type completes through the standard flow with no Sunshine surface, no extra record, and no rename. |
| **XM-C6** | B | **Correction case.** Served with a type whose preferred extension differs from the URL's, with no `Content-Disposition` filename, no suggested name, and a generated name that is not a checked binary: the saved file carries Chromium's corrected extension, and any Sunshine surface displays that name verbatim. |
| **XM-C7** | B | **Preservation case (r4).** A file named `.exe` in the URL but served as `text/plain`: the name keeps `.exe`, the danger level is computed from `.exe`, and no first-party code participated. |
| **XM-C8** | B | **Trusted-name case (r3).** `Content-Disposition: attachment; filename="a.pdf"` with an executable `Content-Type`: the file is saved as `a.pdf`, Sunshine adds no warning, and the resulting danger type equals that of a paired Sunshine-disabled build. |
| **XM-C9** | B | **Nosniff case (r5).** With `X-Content-Type-Options: nosniff` present, the final name and danger type are identical with and without Sunshine surfaces open. |
| **XM-C10** | B | **Double extension (r7).** `foo.tar.gz` served as its archive type retains `foo.tar.gz`. |
| **XM-C11** | B | **Differential.** Over a parameterised matrix of URL extension, `Content-Type`, `Content-Disposition`, `nosniff`, and body prefix, the final filename, the `DownloadDangerType`, and every `DownloadCommands::IsCommandEnabled()` result are identical between a Sunshine build and a paired Sunshine-disabled build of the same revision. This is the criterion that would fail if any of XM-1, XM-3 or XM-5 were violated anywhere. |
| **XM-C12** | B | **No bytes read.** File-access tracing across a download of each residual case shows no first-party module opening the intermediate `.crdownload` file or the final file. Enforces XM-4, runtime half. |
| **XM-C13** | B | **No egress.** With the Security Center enabled and a provider stubbed to record everything it receives, no request carries a filename, an extension, or a MIME string, and no provider is consulted about the download at all. Enforces XM-6, XM-7. |

Tests must use Chromium fixtures or a local test server. No criterion here may be
established against a public website or a live reputation service, consistent
with `docs/DOWNLOAD_SAFETY.md` and `docs/SECURITY_CENTER_CONTRACT.md`.

`scripts/trace_invariants.py` will not count the `XM` family until `XM` is added
to its `FAMILIES` tuple. That is a one-line tooling change this wave did not make,
and it is recorded below rather than left to be discovered.

## Open questions for the owner

| Priority | Question |
|---|---|
| P1 | Should XM-C1, XM-C2 and XM-C4 be implemented as guards? They are the class-O half of this contract and the same shape as the ten checks `docs/ACCEPTANCE_SUITES.md` §8 records as the highest-value work available before a build exists. XM-C4 is the one with a shelf life: the reconciliation guards it names are ordinary implementation detail upstream, and if one is reordered or removed, this contract's central claim silently stops being true. |
| P1 | The **first** clause of handoff §5.6.4 — "warn before opening executable or script-like downloads" — is mapped by `docs/ACCEPTANCE_SUITES.md` to `DOWNLOAD_SAFETY` criteria 2 and 5, which are about classification preservation and action safety and say nothing about opening. Upstream, opening is governed by `FileTypePolicies::IsAllowedToOpenAutomatically` and `DownloadPrefs::IsAutoOpenEnabled`, which no contract names. This document does not claim that clause; someone should decide whether it is a second uncovered half or is inherited in the same way this one is. |
| P2 | Add `XM` to `scripts/trace_invariants.py`'s `FAMILIES`, so XM-1 to XM-9 are countable rather than joining the "enforced but uncounted" set `config/invariant_coverage.txt` already complains about. |

## Not verified

- No Chromium checkout, configuration, compilation or link was performed.
  **NOT RUN.**
- No Sunshine or Chromium binary was launched on any platform.
  **NOT AVAILABLE.**
- No criterion in this document was executed. XM-C1 to XM-C4 are decidable today
  but no guard implements them, so their status is **NOT RUN**, not "passing".
  XM-C5 to XM-C13 require a native build. **NOT RUN.**
- No visual, accessibility, localisation or keyboard verification of any download
  surface. **NOT RUN.**
- Every statement about Chromium above is read from the pinned sources at
  `refs/tags/152.0.7977.42` through the paths cited, which
  `scripts/verify_pinned_upstream.py` checks on every CI run. They are claims
  about that source, not about the behaviour of any build. The residual set r1–r7
  is derived from the guards as written; it was not exercised against a running
  browser, and a case reachable by a path other than `GenerateFileName()` would
  not appear in it.
- The count in XM-C3 is read from `first_party/commands.json` at the state of this
  wave.
- No contract was edited, no criterion renumbered, no command registered, and no
  patch, module or guard changed by this wave.

## Completion gate

This contract is complete when reviewed. Handoff §5.6.4's mismatch clause is
complete when XM-C1 to XM-C4 are wired to guards and XM-C5 to XM-C13 have been
run and recorded on a native pinned build. Until then the clause is satisfied by
inheritance and unverified by execution, which is a different statement from
satisfied and verified, and this document does not conflate them.
