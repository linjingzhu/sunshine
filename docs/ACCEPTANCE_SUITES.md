# Stage 1–3 Acceptance Suites — Coverage Index

**Status:** Index. Declares no new requirement and corrects no contract.
**Settles:** the question "which contract criteria answer a stage acceptance
item, and which items nothing answers".
**Sources:** sections 5.7, 6.8 and 7.9 of
`docs/SUNSHINE_OS_STAGE_1_TO_3_IMPLEMENTATION_HANDOFF.md`, against the
acceptance sections of the documents listed in section 2.

---

## 0. Why this document exists

The handoff states three acceptance suites in twenty-one lines of prose. Twenty-three
documents in `docs/` have since grown their own numbered criteria — the omnibox
contract has twenty-two, the command palette thirty-three, the security centre
thirteen, the design system twenty-six across two groups. None of them is
addressed to a handoff acceptance line, and no handoff acceptance line names a
contract. The result is that "is Stage 1 done?" has no answer, not because the
work is unclear but because nothing connects the question to the criteria that
would settle it.

This document is the connection and nothing else. For each acceptance item it
records which contract criteria establish it, by document and identifier, and
where nothing does it says so. It does not restate a criterion, and it does not
invent one: an item with no owning criterion is reported as uncovered, which is
the finding, not a gap in this index.

It sits beside `scripts/trace_invariants.py`, which asks the adjacent question
one level down — which of the declared contract *invariants* a test or tool
claims to enforce. No standing total is written here for that, because it moves
with every wave and a number left behind reads as a finding rather than as
prose. The tool prints both totals on every run, and
`config/invariant_coverage.txt` is the ratchet that stops the enforced one
falling: adding is free, removing has to be done on purpose. On 2026-08-17 it
stood at 38 claimed of 429 declared. This document asks the question one level
up, and reaches the same shape of answer — a small enforced fraction of a large
declared set, for the reason that baseline file gives: most of what these
contracts declare is a statement about a running browser, and no offline suite
can establish one.

---

## 1. Method

### 1.1 Verdicts

| Verdict | Meaning |
|---|---|
| **Covered** | Every behaviour the acceptance line names has at least one criterion in a contract that would fail if the behaviour were absent. |
| **Partial** | Some named behaviour has an owning criterion and some has none. The uncovered half is stated in section 6. |
| **Uncovered** | No criterion in any document in `docs/` would fail if this item failed. |
| **Unrunnable** | A criterion exists but cannot be executed, because a product decision it depends on is open or because the condition it tests cannot arise. |

"Covered" is a claim about the existence of a criterion, never about a result.
Every criterion cited below is **NOT RUN**.

### 1.2 Checkability classes

The split that decides whether a stage acceptance is a gate or an aspiration.

| Class | Meaning |
|---|---|
| **O** | Decidable against this repository today — the test suite, the guards in `scripts/`, and the pinned sources those guards already fetch. No Chromium compilation. |
| **B** | Needs a native build of the pinned revision plus an automated harness (Chromium test fixtures, a local test server, instrumentation). No person watching. |
| **H** | Needs a person: visual and assistive-technology observation, or a period of real use producing evidence no harness can synthesise. |

**No item in §5.7, §6.8 or §7.9 is class O.** Not one. The offline suite decides
preconditions — that the patch stack applies, that the command registry is
consistent, that no shadow store has been introduced, that every upstream path a
contract cites still resolves. It cannot advance a single line of a stage
acceptance suite, because every one of those lines is a statement about a
running browser. Section 8 records the criteria that *are* class O, all of them
belonging to contracts rather than to the suites, and most of them not yet wired
to anything.

The consequence, stated plainly: **Stage 1 acceptance is today an aspiration,
not a gate.** It becomes a gate on the day a native build exists, not before,
and no amount of further contract writing moves that date.

### 1.3 A regime conflict that affects every row

§5.7 and §6.8 are dogfood suites against the live public web — the handoff names
Google, Naver, ChatGPT, GitHub, Gmail, Google Drive, YouTube, Naver Blog/Cafe,
documentation sites and shopping sites. The contracts deliberately forbid that:
`docs/SECURITY_CENTER_CONTRACT.md` opens its acceptance section with "No test
may depend on a live reputation service, a real provider endpoint, or a public
website"; `docs/DOWNLOAD_SAFETY.md` and `docs/BOOKMARKS_HISTORY_CONTRACT.md`
carry the same rule.

Both regimes are right and neither substitutes for the other. A contract
criterion is deterministic and therefore cannot observe what a real site does; a
dogfood observation is real and therefore cannot be a regression gate. So a
citation in the tables below never means "running this criterion discharges the
acceptance line". It means "this criterion is the only thing in the repository
that would fail if the mechanism behind that line were broken". The dogfood pass
is still required on top, and is class H throughout.

### 1.4 Citation form

Contract criteria are cited by their stable identifier — `GA-7`, `AT-11`,
`SC-8`, `SPA-9` — because those are the ones `scripts/trace_invariants.py` can
follow. A section reference is added where it helps a reader find the text, but
the identifier is what the citation is *for*.

**The numbered acceptance criteria now have identifiers.** They did not when
this index was written: `docs/OMNIBOX_CONTRACT.md` criterion 14 was addressable
only as an ordinal in a list that renumbers whenever a criterion is inserted —
and one had already been retired in place (criterion 16) precisely to avoid
that. Each such list has since been given a per-document prefix, listed in
section 2, with **the ordinals unchanged**: criterion 14 of that document is
`OMA-14`, so every citation written against the old ordinal still resolves. The
gain is a handle that survives an insertion and that a test can name in an
`Enforces:` line. The one defect this does not repair is
`TAB_WORKSPACE_SPLIT_CONTRACT` §10, whose acceptance bullets carry no ordinal at
all; there is nothing there to prefix, and numbering them would be inventing an
order no citation currently uses.

---

## 2. Where the criteria live

| Document | Criteria | Identifier scheme |
|---|---|---|
| `docs/ADVANCED_TABS_CONTRACT.md` | §11, 12 items ATA-1…ATA-12; invariants AT-1…AT-14 | ATA- for §11; AT- for invariants |
| `docs/OMNIBOX_CONTRACT.md` | §13, 22 criteria OMA-1…OMA-22; rules OC-1…OC-4, OT-1…OT-6, OP-1…OP-6, OS-1…OS-10 | OMA- for §13; prefixed rules |
| `docs/TAB_LIFECYCLE_CONTRACT.md` | §13, 25 criteria TLA-1…TLA-25; invariants 1–3 | TLA- for §13; invariants still ordinals |
| `docs/COMMAND_PALETTE_CONTRACT.md` | §14, 33 criteria CPA-1…CPA-33 | CPA- |
| `docs/SIDE_PANEL_CONTRACT.md` | §12, 26 criteria SPA-1…SPA-26; detections D1…D7; eligibility E1…E8 | SPA-; D/E |
| `docs/SECURITY_CENTER_CONTRACT.md` | 13 criteria SCA-1…SCA-13; invariants SC-1…SC-12 | SCA-; SC- |
| `docs/GESTURE_CONTRACT.md` | §9, 18 criteria GA-1…GA-18 | GA- |
| `docs/BROWSER_UTILITIES_CONTRACT.md` | 22 criteria BUA-1…BUA-22 | BUA- |
| `docs/DESIGN_SYSTEM_CONTRACT.md` | §9.1 S1…S12 source checks; §9.2 R1…R14 runtime checks | S/R |
| `docs/TAB_WORKSPACE_SPLIT_CONTRACT.md` | §10, 9 **unnumbered** bullets; invariants 1–12 | invariant numbers only |
| `docs/SESSION_PROFILE_CONTRACT.md` | 14 tests SRA-1…SRA-14 in 5 groups | SRA-, numbered continuously |
| `docs/DOWNLOAD_SAFETY.md` | 8 tests DSA-1…DSA-8 | DSA- |
| `docs/BOOKMARKS_HISTORY_CONTRACT.md` | 5 groups, each **restarting at 1**: BH-A1…BH-A7, BH-B1…BH-B7, BH-C1…BH-C5, BH-D1…BH-D4, BH-E1…BH-E5 | BH- plus a group letter |
| `docs/PERMISSION_POLICY.md` | **none** — a defaults table, a roll gate, a deferred list | — |
| `docs/EXTENSION_COMPATIBILITY_GATE.md` | 12 matrix rows, 7 fixtures, GO/NO-GO conditions | row name |
| `docs/EXTENSION_MIME_CONTRACT.md` | 9 invariants XM-1…XM-9; 13 criteria XM-C1…XM-C13 | XM- |
| `docs/PERFORMANCE_BUDGET.md` | 6 budgets PB-1…PB-6, each with zero-tolerance conditions and a deferred statistical tolerance | PB-, formerly P1…P6 |

Two entries deserve attention before any of the tables below are read.
`docs/PERMISSION_POLICY.md` is the only Stage 1 contract with no acceptance
criteria at all — its roll gate verifies seven upstream default values and then
asks for a manual smoke test. And `docs/TAB_WORKSPACE_SPLIT_CONTRACT.md` §10
gives nine acceptance bullets with no numbers, so nothing in this document or
any other can cite one of them individually; it is the only list in the table
above that could not be given a prefix, because a prefix needs an ordinal to
attach to.

Every prefix in the right-hand column is distinct from every other, and from the
families `scripts/trace_invariants.py` already knows. The ordinals inside each
list were not touched by the renaming: `SIDE_PANEL_CONTRACT` §12.9 is `SPA-9`,
`COMMAND_PALETTE_CONTRACT` §14.9 is `CPA-9`, and a reference written against
either spelling reaches the same criterion. `PERFORMANCE_BUDGET` is the one
document where the old spelling is withdrawn rather than kept alongside: its
budgets read `P1`…`P6`, which no tool could distinguish from the P0/P1/P2
decision priority every contract uses, so they are `PB-1`…`PB-6` now and a bare
`P` number in that document is always a priority.

---

## 3. Stage 1 — handoff §5.7

Nine acceptance lines, plus the corpus line that governs all of them.

| ID | §5.7 item | Established by | Class | Verdict |
|---|---|---|---|---|
| A1.0 | one-day dogfood over the named site corpus | nothing; every contract suite forbids live sites (§1.3) | H | see §1.3 |
| A1.1 | login persistence | `SESSION_PROFILE_CONTRACT` SRA-9, SRA-11, SRA-13; `BOOKMARKS_HISTORY_CONTRACT` BH-D1–BH-D2 | B + H | **Partial** |
| A1.2 | tab and navigation stability | `TAB_LIFECYCLE_CONTRACT` TLA-1–TLA-25; `OMNIBOX_CONTRACT` OMA-1–OMA-14, OMA-17–OMA-19; `BOOKMARKS_HISTORY_CONTRACT` BH-C1–BH-C5 | B | **Covered** |
| A1.3 | file upload / download | download: `DOWNLOAD_SAFETY` DSA-1–DSA-8, `BROWSER_UTILITIES_CONTRACT` BUA-21, `SIDE_PANEL_CONTRACT` SPA-11–SPA-12. **upload: nothing** | B | **Partial** |
| A1.4 | media playback | **nothing** | B + H | **Uncovered** |
| A1.5 | popup flows | default only: `PERMISSION_POLICY` POPUPS row and roll gate; membership of an opened tab: `TAB_LIFECYCLE_CONTRACT` §10.2 | B | **Partial** |
| A1.6 | bookmark / history persistence | `BOOKMARKS_HISTORY_CONTRACT` BH-A1–BH-A7, BH-B1–BH-B7, BH-E1–BH-E5 | B | **Covered** |
| A1.7 | no critical crash | recovery only: `SESSION_PROFILE_CONTRACT` SRA-4–SRA-8; `TAB_LIFECYCLE_CONTRACT` TLA-7, TLA-21, TLA-22 | B + H | **Partial** |
| A1.8 | no material security regression | see §3.2 — four of the six §5.6 requirements have an owning criterion | B | **Partial** |
| A1.9 | acceptable CPU/memory during ordinary use | `PERFORMANCE_BUDGET` PB-2, PB-4, PB-5 measure the Sunshine *delta*; nothing measures the absolute experience this line names | B + H | **Uncovered** |

**Stage 1: 2 covered, 5 partial, 2 uncovered.**

### 3.1 The contested rows

**A1.1 — login persistence.** Every cookie and credential criterion in the
contract set is about *isolation and non-leakage*: profile A must not see
profile B (`SESSION_PROFILE_CONTRACT` 9), incognito must vanish
(`SESSION_PROFILE_CONTRACT` 11), canaries must not reach a Sunshine log
(`SESSION_PROFILE_CONTRACT` 13). Not one asserts the positive: that a session
logged in before a clean restart is still logged in after it. That is the
behaviour §5.7 names, and it is uncovered. The mechanism is entirely Chromium's,
which is a reason to expect it to work and not a reason to omit the check —
`SESSION_PROFILE_CONTRACT` 2 makes exactly this argument for tab order and
checks it anyway.

**A1.3 — file upload.** No document in `docs/` mentions file upload, a file
picker for upload, or drag-and-drop of a file into page content. The only nearby
text is `GESTURE_CONTRACT` GA-11, which treats a file drag as a gesture
*cancellation* case. Upload is the half of this acceptance line with no owner at
all, and it is the half that Gmail, Google Drive and the shopping sites in the
corpus exercise on the first day.

**A1.4 — media playback.** Uncovered, and the reason is now the ordinary one:
no contract states a criterion about it. The build configuration used to decide
this line in advance — `proprietary_codecs` was off, so most of the corpus could
not have played whatever a dogfood day found — and that is settled. The flag is
on, the premise for turning it on is recorded in
`docs/decisions/0004-media-codecs.md`, and the line is now evaluable. Evaluable
is not covered. See section 6, finding U1.

**A1.5 — popup flows.** `PERMISSION_POLICY` establishes the *setting* — pop-ups
default to block, Chromium's own affordance offers the exception. Nothing
establishes the *flow*: an OAuth window opening, authenticating, closing, and
the opener continuing. That flow is what "popup flows" in a one-day dogfood
means, and it involves the window-open policy of handoff §5.6.1, which no
contract implements. See finding C1.

**A1.7 — no critical crash.** The recovery path is well covered. The claim
itself is not checkable, because nothing in this repository can observe a crash:
`EXTENSION_COMPATIBILITY_GATE` states that "crash reporting … must not be
assumed to exist in Sunshine", and no contract defines a crash channel, a
severity scale, or a threshold. A day of use that ends without the user
*noticing* a crash is the current evidence, and that is not the same statement.

**A1.9 — CPU and memory.** `docs/PERFORMANCE_BUDGET.md` now settles handoff
§9.2, and it settles it by redefining every measurement as a **delta** against a
paired Sunshine-disabled build. That is the right design — Sunshine adds no
renderer and can only regress what it inherits — and it deliberately places
"Chromium's own performance" and "absolute startup seconds and memory megabytes"
out of scope until the first native build.

The consequence for this row is that §5.7's line still has no owner. "Acceptable
CPU/memory during ordinary use" is an absolute claim about what the user
experiences; a delta budget can pass in full while the absolute experience is
unacceptable, and the budget document says as much about its own scope. The gap
is now explicit and reasoned rather than accidental, which is an improvement,
but the row is still **Uncovered** and the acceptance suite still asks a
question no document answers. See finding U5.

### 3.2 A1.8 unpacked: handoff §5.6 requirement by requirement

| §5.6 | Requirement | Owning criterion | Verdict |
|---|---|---|---|
| 1 | deny arbitrary window-open; route approved requests through a policy handler | `PERMISSION_POLICY` POPUPS row — the default, not a handler | **Partial**, and contradicted; see C1 |
| 2 | validate navigation schemes; only supported internal schemes get privileged handling | `OMNIBOX_CONTRACT` OMA-8, OMA-15, and the two checks folded into OMA-16 (OS-3, OS-4, OS-6, OS-7); `SECURITY_CENTER_CONTRACT` SCA-13 | **Covered** |
| 3 | permission handler with default-deny until a per-origin decision | `PERMISSION_POLICY` defaults table and roll gate | **Partial**, and contradicted; see C2 |
| 4 | warn before executable or script-like downloads; flag extension/MIME mismatch | `DOWNLOAD_SAFETY` DSA-2, DSA-5; **mismatch flagging: nothing** | **Partial** |
| 5 | log security-relevant download decisions with provenance and user action | `DOWNLOAD_SAFETY` DSA-4, DSA-6 | **Covered** |
| 6 | separate Sunshine profile OAuth from Google login in a normal tab | **nothing** | **Uncovered** |

§5.6.6 is the sharpest hole in Stage 1. No contract owns profile onboarding at
all — not the "Use locally works without network" requirement of §5.2, not the
optional Google link, not the separation this requirement demands.
`SESSION_PROFILE_CONTRACT` covers profiles once they exist and is silent on how
one is created. See finding U2.

---

## 4. Stage 2 — handoff §6.8

Seven items. Every one of them is a **rate** — a quantity observed over seven
days — and the contract set contains no rates at all. It contains per-operation
correctness criteria, which are a different kind of statement. This mismatch,
not any individual gap, is the finding for Stage 2.

| ID | §6.8 item | Established by | Class | Verdict |
|---|---|---|---|---|
| A2.1 | crash and renderer-process recovery rate | behaviour: `SESSION_PROFILE_CONTRACT` SRA-4–SRA-8; `TAB_LIFECYCLE_CONTRACT` TLA-7, TLA-21, TLA-22. **rate: nothing** | B + H | **Partial** |
| A2.2 | broken-site and login failures | **nothing** — no contract owns site compatibility | H | **Uncovered** |
| A2.3 | memory growth and background CPU | background CPU: `PERFORMANCE_BUDGET` PB-5 (zero-tolerance). memory: PB-2a, PB-4, `SIDE_PANEL_CONTRACT` D4, SPA-8. **growth over a session: nothing** | O + B | **Partial** |
| A2.4 | gesture activation, cancellation, false-positive, reversal rate | events: `GESTURE_CONTRACT` §7 and GA-17. behaviour: `GESTURE_CONTRACT` GA-1–GA-16. **thresholds: nothing** | B + H | **Partial** |
| A2.5 | permission friction | **nothing** — `PERMISSION_POLICY` has no criteria of any kind | H | **Uncovered** |
| A2.6 | download failure and security override rate | events: `DOWNLOAD_SAFETY` DSA-6. **rate: nothing** | B + H | **Partial** |
| A2.7 | session restore failure rate | behaviour: `SESSION_PROFILE_CONTRACT` 1–8, 14. **rate: nothing** | B + H | **Partial** |

**Stage 2: 0 covered, 5 partial, 2 uncovered.**

Notes on four rows.

**A2.3** improved between the drafting of this index and its completion, which
is worth recording as a method note: `docs/PERFORMANCE_BUDGET.md` landed and
took background CPU from uncovered to a zero-tolerance rule — PB-5 holds that
Sunshine's legitimate idle cost is zero, so *the existence* of a repeating
Sunshine task is the regression, not its size. That is stronger than a
threshold and it is partly class O (see §8). Memory is covered as a paired
delta. What remains uncovered is the word §6.8 actually uses: **growth**.
Nothing observes a memory series over a seven-day session, and a leak is
precisely the failure a one-shot paired measurement cannot see.

**A2.4** is the best-instrumented item in either dogfood suite, and it is still
Partial. `GESTURE_CONTRACT` §7 defines the events §6.8 asks to be counted —
activation, cancellation reason, and the undo/immediate-reversal signal that is
the only available proxy for a false positive. Everything needed to produce the
numbers is specified. What is missing is a target: no document says what
false-positive rate fails the gate, and the contract itself concedes that its
thresholds are "declared, not measured". A rate with no threshold is a report,
not a gate.

**A2.5.** Permission friction is the only §6.8 item whose feature contract
contains no acceptance criteria whatsoever. `PERMISSION_POLICY` makes a
defensible zero-patch decision and verifies seven upstream defaults at each
roll; it defines no observation of what a user experiences. Friction is also the
one quantity here that a harness genuinely cannot produce.

**A2.2.** Site compatibility has no owner anywhere in `docs/`.
`EXTENSION_COMPATIBILITY_GATE` covers breakage *caused by extensions* and
explicitly declines to cover the rest. A broken site in the §5.7 corpus
currently has no document to be filed against, which is also why A1.4 and A1.3's
upload half could remain unnoticed for as long as they have.

Stage 2 features whose acceptance §6.8 does not mention, and which are therefore
gated only by their own contracts: the Security Center
(`SECURITY_CENTER_CONTRACT` 1–13), browser utilities
(`BROWSER_UTILITIES_CONTRACT` 1–22), and the §2.3 extension architecture gate
(`EXTENSION_COMPATIBILITY_GATE` matrix and GO/NO-GO). See finding C4 for a
tension in the last of these.

---

## 5. Stage 3 — handoff §7.9

§7.9 asks for "at least three durable advantages … through real dogfooding" and
lists five candidates. The gate is therefore two statements: that three of the
five hold, and that each holding one is evidenced by use rather than by a
feature list. Handoff §12 forbids the substitution explicitly — "do not replace
measurable dogfooding with a feature-complete checklist" — which makes this the
one suite where citing contract criteria is *not* the answer, and the reason
this section is longer than the others.

| ID | §7.9 candidate | Mechanism established by | Class | Verdict |
|---|---|---|---|---|
| A3.0 | at least three durable advantages | **nothing** — "durable" is undefined, and no document selects the three | H | **Unrunnable** |
| A3.1 | gestures used repeatedly without accidental activation | `GESTURE_CONTRACT` GA-1–GA-17, §7 | B + H | **Partial** |
| A3.2 | workspaces separating Development / Research / Personal | `TAB_WORKSPACE_SPLIT_CONTRACT` §10 (bullets 2–4, 7), invariants 1–4, 7; `TAB_LIFECYCLE_CONTRACT` TLA-11, TLA-22; `ADVANCED_TABS_CONTRACT` ATA-3, ATA-5, ATA-6 | B + H | **Covered** |
| A3.3 | split view for research/implementation without tab thrash | `TAB_WORKSPACE_SPLIT_CONTRACT` §10 (split bullets 5–8), invariants 5, 6, 9–12; `TAB_LIFECYCLE_CONTRACT` TLA-19–TLA-21; `SIDE_PANEL_CONTRACT` SPA-15–SPA-16 | B + H | **Partial** |
| A3.4 | command palette faster than menus for frequent operations | `COMMAND_PALETTE_CONTRACT` CPA-12, CPA-14 (determinism), CPA-8 (frame budget). **speed: nothing** | B + H | **Uncovered** |
| A3.5 | personally designed appearance readable and consistent | `DESIGN_SYSTEM_CONTRACT` R1–R14, S1–S12; `docs/SUNSHINE_NEW_TAB_SPEC.md` verification gate; `docs/WINDOWS_CHROMIUM_BUILD.md` visual gate | O + B + H | **Covered** |

**Stage 3: 2 covered, 2 partial, 1 uncovered, 1 unrunnable.**

**A3.4 is uncovered and is the interesting one.** `COMMAND_PALETTE_CONTRACT`
establishes that the palette is *deterministic* — CPA-12 requires a
byte-identical result list for a given query across restarts and contexts,
CPA-14 requires the same command after a fixed prefix on a hundred trials. That
is a precondition for being fast, since a list that reorders cannot build muscle
memory, and the contract says so. It is not speed. No criterion measures
time-to-execute, and no document establishes the menu baseline the comparison
needs.

There is also a direct conflict with the evidence §7.9 would require.
`COMMAND_PALETTE_CONTRACT` CPA-20 requires that a byte inspection of the stored
recents value find "no timestamp, count, selection handle, or query text", and
CPA-22 requires the list to be emptied by any history clear. Frequency-of-use
data therefore cannot come from the recents store — deliberately, and correctly.
It must come from the `Sunshine.Command.*` telemetry events declared for all
twenty-four registered commands in `first_party/commands.json`. No telemetry
sink exists. See finding U4.

### 5.1 What would count as dogfooding evidence

§7.9 evidence is class H by construction. That does not make it unspecifiable.
For each candidate: the instrument, the window, the artifact, and the falsifier.
None of these is a requirement — the product owner sets them — but an evidence
claim that supplies less than this is a checklist wearing a dogfood label.

**Common preconditions.** A named build; Sunshine used as the primary browser
for the whole window by the person making the claim; a stated window of at least
fourteen consecutive days for Stage 3 (§7.9's "durable" cannot mean the seven
days §6.8 already spent); and a telemetry sink capable of retaining the
`Sunshine.Command.*` and gesture events for the window. Absent the sink, every
row below degrades to a self-report, which is admissible evidence of preference
and is not evidence of an advantage.

**A3.1 — gestures.** Instrument: the `GESTURE_CONTRACT` §7 events. Artifact:
per-day counts of activations, cancellations by reason, and reversals within the
contract's reversal window, alongside toolbar and keyboard invocations of
`browser.back` and `browser.forward` for the same period. Falsifier: a reversal
rate above the threshold the owner sets, or gesture invocations declining across
the window while toolbar invocations of the same commands rise — the user
quietly stopping.

**A3.2 — workspaces.** Instrument: `workspace.switch`, `workspace.create`,
`workspace.close` and `workspace.tab.move` telemetry. Artifact: three or more
workspaces alive for the whole window, daily switch counts, and the tab
population of each at the start and end. Falsifier: the user collapsing to one
workspace, or a workspace that is created and never switched to again — a
feature used once is not a durable advantage.

**A3.3 — split view.** "Tab thrash" is the undefined term and is the whole
claim. A workable operationalisation: tab activations per minute inside sessions
with a split open, against the same rate outside them, over the window.
Instrument: activation tracing on the build; there is no Sunshine-owned split
command to count, because `TAB_WORKSPACE_SPLIT_CONTRACT` §4.2 retired them and
Chromium owns splits at the pinned revision. Falsifier: no difference between
the two rates, or splits opened and dissolved within a threshold duration.

**A3.4 — palette speed.** Needs two things nothing currently supplies: a fixed
set of frequent operations named in advance from the twenty-four registered
commands, and a timed comparison — time from intent to completed execution, via
the palette and via the equivalent menu path, at least twenty trials each by the
same operator on the same build. Plus, from telemetry over the window, the share
of those operations actually invoked through the palette. Falsifier: no timing
advantage, or a timing advantage the user does not take up.

**A3.5 — appearance.** Instrument: `DESIGN_SYSTEM_CONTRACT` R1–R14 recorded on
the named build, plus the `docs/SUNSHINE_NEW_TAB_SPEC.md` gate and the visual
gate in `docs/WINDOWS_CHROMIUM_BUILD.md`. Artifact: the recorded contrast
measurements, the R4 photographic-background minimum, and the count of
appearance defects raised during the window. Falsifier: any R-group check
failing, or the user reverting to a stock appearance. Note that S8 is recorded
as *currently failing* in the contract, on inspection rather than tooling — an
appearance claim made while a declared source check is known to fail is not
available.

**What does not count**, for any row: a feature-complete checklist (handoff
§12); a single session or a demonstration; a screenshot; passing the contract
criteria — those establish that the mechanism works, which §7.9 assumes rather
than asks about.

---

## 6. The uncovered set

The most valuable lines in this document. Each is a requirement the handoff
states as acceptance and no document in `docs/` would fail on.

**U1 — media playback is uncovered, and the reason has changed.**
`scripts/build_chromium_windows.ps1` writes `proprietary_codecs=true` and
`ffmpeg_branding="Chrome"` into the GN args, so the H.264 and AAC paths are
compiled in and the §5.7 media corpus is decodable. Neither value is Chromium's
default — `proprietary_codecs` derives from `is_chrome_branded`, which Sunshine
does not set — so the flag had to be turned on deliberately. It was, under the
personal-use premise recorded in `docs/decisions/0004-media-codecs.md`, and
`docs/WINDOWS_CHROMIUM_BUILD.md` now carries a Media codecs section stating the
same configuration and the same premise.

This finding used to read the other way round, and the correction is worth
recording rather than overwriting. It said the script wrote
`proprietary_codecs=false` and `ffmpeg_branding="Chromium"`, that H.264 and AAC
were therefore not compiled in, and that no document recorded the choice. All of
that was true when it was written, and it is what caused the ADR to be written.
The ADR then changed the flags and this paragraph was not changed with them, so
an index whose subject is stale citations went on asserting a build
configuration the repository had already replaced.

The verdict is what does **not** change. A1.4 is still **Uncovered**, now for an
ordinary reason instead of a hidden one: no contract in `docs/` states a
criterion about media playback, so nothing in this repository would fail if
media stopped playing. An ADR is a decision, not a criterion — it records why a
flag is set and it never observes a video. The line moved from *predetermined to
fail* to *evaluable*, which is a real gain and is not coverage. **NOT RUN**: no
build exists in which to confirm that the compiled paths decode.

**U2 — profile onboarding has no contract.** Handoff §5.2 requires "Use locally"
to work without network with Google optional, and §5.6.6 requires Sunshine
profile OAuth to be separated from logging into Google in an ordinary tab.
`SESSION_PROFILE_CONTRACT` governs profiles that already exist and never
addresses their creation. Nothing owns the onboarding flow, the local-only path,
the optional link, or the separation. This is a Stage 1 security requirement
with no owning document.

**U3 — file upload has no contract.** Section 3.1, A1.3.

**U4 — answered by `docs/TELEMETRY_CONTRACT.md`: Sunshine records, and does not
report.** The events are specified — `Sunshine.Command.*` on all twenty-four
registered commands and the `GESTURE_CONTRACT` §7 set. (This finding originally
counted the `DOWNLOAD_SAFETY` warning events too; those are Chromium's
`DownloadItemWarningData` events on Chromium's own pipeline, and that contract
forbids sending download data to a Sunshine service at all.)

The resolution is that the numbers the acceptance suites need never have to
leave the machine. Three independent upstream gates are already closed in a
build that is not Chrome-branded, which Sunshine's is not: reporting is disabled
outright in non-official builds, the server URLs are deliberately empty to stop
forks sending metrics to Google, and the crash upload URL is empty on the same
condition. So histograms are recorded in-process and read through upstream's own
tools; there is no consent state because there is no reporting state.

That closes the question `PERFORMANCE_BUDGET` §9 and `SIDE_PANEL_CONTRACT` D1
were both waiting on. It does not make the §6.8 rates automatic: a recorded
histogram still has to be exported per browsing day rather than once at the end,
and off-the-record activity is deliberately not recorded at all, so dogfood
counts under-report by an unknowable amount.

**U5 — the performance budget is a delta budget, and the acceptance suites ask
absolute questions.** `docs/PERFORMANCE_BUDGET.md` settles handoff §9.2 with six
budgets and a baseline procedure, and explicitly scopes out Chromium's inherited
performance and all absolute numbers until the first native build. Every one of
its budgets answers "did Sunshine make this worse?". Both §5.7's "acceptable
CPU/memory during ordinary use" and §6.8's "memory growth" ask a different
question — "is this good enough, and does it stay good enough?" — which no
document answers and which the budget document, on its own stated boundary, is
not the place to answer. Two sub-gaps follow: no absolute acceptability
threshold for A1.9, and no long-session memory series for A2.3. This is now a
scope seam between two well-formed documents rather than an omission, but the
acceptance line is unowned either way.

**U6 — nothing owns site compatibility.** Section 4, A2.2.

**U7 — extension/MIME mismatch flagging is unowned.** Handoff §5.6.4 names it;
`DOWNLOAD_SAFETY` covers danger-type preservation, routing, provenance and
action safety, and never mentions mismatch.

**U8 — no crash channel, so "no critical crash" is unobservable.** Section 3.1,
A1.7.

**U9 — no definition of "durable", and no selection of the three advantages.**
Section 5, A3.0. Five candidates for three slots and no document picks; the
claim cannot be assembled, let alone evidenced.

---

## 7. Contradictions and unwithdrawn text

Found while indexing. Each is between documents, or between a document and the
repository; none is a defect this index may fix.

**C1 — handoff §5.6.1 versus `docs/PERMISSION_POLICY.md`.** §5.6.1 requires
Sunshine to "route approved popup/new-window requests through a policy handler".
`PERMISSION_POLICY` makes an explicit zero-runtime-patch decision, inherits
Chromium's block-by-default and its own exception affordance, and forbids
"silently layering a second Sunshine permission system over Chromium". The
contract is almost certainly right. But §5.6.1 has not been *withdrawn* the way
§5.3's scheme row and §7.3's pinned-tabs clause were withdrawn in place, so a
reader of the handoff still sees a Sunshine handler required at a Stage 1
security gate.

**C2 — handoff §5.6.3 versus the same document.** §5.6.3 requires "a default-deny
policy until the user has a per-origin decision". Six of the seven categories in
`PERMISSION_POLICY`'s table are `ASK`, not deny, and the contract argues at
length why `ASK` for automatic downloads and `BLOCK` for pop-ups are the correct
readings. Again persuasive, again not marked as a correction of §5.6.3.

**C3 — handoff §7.3 and §4.2 versus AT-1.** Both handoff passages describe a
workspace as storing "pinned tabs". `ADVANCED_TABS_CONTRACT` AT-1 withdraws that
clause outright, and records the withdrawal in its §9. This one is settled in
the right place; it is listed only because the handoff text still reads the old
way and this index cites both documents.

**C4 — handoff §2.3.4 versus `docs/EXTENSION_COMPATIBILITY_GATE.md`.** §2.3
requires the extension spike to test "a representative minimum set: password
manager, ad blocker, developer tool". The gate requires repository-owned
controlled fixtures, states that third-party extensions "cannot replace" them,
and forbids automating access to private user accounts during compatibility
testing. A password manager exercised without an account tests installation, not
the behaviour §2.3 cares about. The gate's rule is the safer one; §2.3's fourth
step needs restating in terms of it.

**C5 — `docs/COMMAND_PALETTE_CONTRACT.md` §15 misstates the registry.** It
refers to "the 27 registered commands" and to "the 21 Chromium-owned commands".
`first_party/commands.json` holds twenty-four commands: twenty owned by
`chromium` and four by `sunshine.workspace`. Checkable offline in seconds, and
load-bearing, because §15 uses the count to state how many commands lack the
reason-token sets §4 requires.

**C6 — `docs/DESIGN_SYSTEM_CONTRACT.md` §9.3 understates what is reachable.** It
records S1 as unrunnable because "this session has no pinned Chromium checkout".
`scripts/verify_pinned_upstream.py` already fetches pinned sources over HTTPS and
checks every upstream path the contracts cite, on every CI run, without a
checkout. S1 is reachable today by the same mechanism. The same applies to the
host-collision half of `SECURITY_CENTER_CONTRACT` 13.

**C7 — two acceptance criteria depend on an open product decision.**
`ADVANCED_TABS_CONTRACT` ATA-9 reads "produces the workspace outcome chosen in
Q3", and Q3 is unanswered; `TAB_LIFECYCLE_CONTRACT` TLA-8 offers two acceptable
outcomes for the same question. Both are **Unrunnable** until Q3 is settled, in
the same sense as `OMNIBOX_CONTRACT` OMA-16 — which is permanently unreachable
by design under ADR 0003 and correctly says so. The contract set has three
criteria that can never pass in their current state; only one of them says so.

**C8 — the suites' evidence regime contradicts the contracts' test regime.**
Section 1.3. Not resolvable by either side; it needs a stated rule about what
each may be cited for.

**C9 — `docs/PERFORMANCE_BUDGET.md` settles handoff §9.2 but not §5.7 or §6.8,
and no document says so.** The budget document claims §9.2 in its scope line and
discharges it well. §5.7's "acceptable CPU/memory" and §6.8's "memory growth and
background CPU" read as if §9.2 covered them, and they are not the same
question: §9.2 asks what to measure, the budget answers with deltas, and the
acceptance suites ask for an absolute verdict the budget explicitly declines to
give. Whoever next revises the handoff should either point those two lines at
the budget's zero-tolerance conditions — which would make them checkable and
narrower than they read today — or state the absolute threshold separately. See
U5.

---

## 8. What is checkable offline today

The repository holds the regression suite under `tests/`, the guards in
`scripts/` that `.github/workflows/architecture-guard-self-hosted.yml` runs, and
the pinned sources those guards already fetch. Neither the suite nor the guard
list is enumerated here: both grow every wave, and the workflow is the one list
that cannot fall behind, because it is the thing that runs them. On 2026-08-17
`python -m unittest discover -s tests` reported 418 tests.

**What they establish:** that the patch stack applies to the pinned revision and
owns its files exclusively; that the module and command registries are
internally consistent; that no excluded runtime has returned; that the native
seams and New Tab tokens the design depends on still exist upstream; that every
upstream path cited by any contract resolves at `152.0.7977.42`; and that
enforcement claimed by a test is not silently removed.

**What they do not establish:** any line of §5.7, §6.8 or §7.9. Not one.

Some *contract* criteria are nevertheless class O, and none of them is currently
wired to a test. In rough order of cost:

| Criterion | Why it is offline-decidable | Status |
|---|---|---|
| `OMNIBOX_CONTRACT` OMA-20 | a source search of first-party sources for a URL parser, TLD list, scheme table or host validator | **implemented** — `scripts/verify_no_interposition.py` |
| `TAB_LIFECYCLE_CONTRACT` TLA-2 | a source search for a stored per-tab lifecycle flag | not implemented |
| `ADVANCED_TABS_CONTRACT` ATA-10, source half | no pinned flag, recently-closed entry, duplicate set or canonical-URL table in any Sunshine-owned file | not implemented |
| `SIDE_PANEL_CONTRACT` SPA-9 | no Sunshine entry registered for the bookmarks or history panel ids — decidable against `first_party/registry.json` | **implemented** — `scripts/verify_first_party_surfaces.py` |
| `COMMAND_PALETTE_CONTRACT` CPA-9, declared half | the reason-token sets exist or do not, against `first_party/commands.json` | **implemented** — `scripts/verify_first_party_surfaces.py`; 22 of 24 entries declare an empty set, `workspace.close` and `workspace.tab.move` do not |
| `DESIGN_SYSTEM_CONTRACT` S2–S12 | pattern checks over Sunshine-authored CSS in the patch stack | **implemented** — `tests/test_design_tokens.py`; S8 failed on first run and is fixed |
| `DESIGN_SYSTEM_CONTRACT` S1 | token existence against pinned sources, by the mechanism `verify_pinned_upstream` already uses | **implemented** — `tests/test_design_tokens.py` |
| `SECURITY_CENTER_CONTRACT` SCA-13, collision half | no first-party internal host collides with a compiled upstream host at the pinned revision | **implemented** — `scripts/verify_first_party_surfaces.py` |
| `TAB_LIFECYCLE_CONTRACT` §15 storage decision | the per-workspace last-active-tab decision is absent from `scripts/workspace_model.py` | **implemented and checked** — `WindowWorkspaceState` stores it in window session extra-data as a pointer into Chromium's tabs, memory-only off the record |
| `PERFORMANCE_BUDGET` PB-5, cheap form | a source assertion that no Sunshine-owned repeating timer or idle task exists; the contract states it needs no baseline and no build | **implemented** — `scripts/verify_no_interposition.py` |

Ten cheap gates, all of them non-interposition checks — the class of criterion
that fails when Sunshine has built something Chromium already owns, which is
this project's characteristic failure mode. They are the highest-value work
available before a build exists, and they are worth more than another contract.

**Eight of the ten are implemented**, across `scripts/verify_no_interposition.py`,
`scripts/verify_design_tokens.py` and `scripts/verify_first_party_surfaces.py`.
The design-system check found two real defects on its first run —
`font-weight: 650` outside the allowed set with no R10 result recorded, and a
fluid band the declaration never stated — and both are fixed.

The two that are **not** implemented are `TAB_LIFECYCLE_CONTRACT` TLA-2 and
`ADVANCED_TABS_CONTRACT` ATA-10: no check claims either identifier. This
paragraph read "all ten are now implemented" until
`scripts/verify_acceptance_claims.py` compared the Status column against what
`scripts/trace_invariants.py` actually records, and disagreed with it in both
directions at once — seven rows understated, the summary overstated.

Two groups used to be enforced but uncounted, because they had no stable
identifier: the ordinal criteria above, and `PERFORMANCE_BUDGET`'s P1..P6, which
collided with the P0/P1/P2 priority labels every contract uses. Both now have
prefixes — §2 lists them, and the budgets are `PB-1`…`PB-6` — so a check of one
of them has something durable to claim. Declaring an identifier does not enforce
it: the claim still has to be written into the check that performs the work.
That step has since been taken — `scripts/verify_first_party_surfaces.py` names
SPA-9, CPA-9 and SCA-13 in its own `Enforces:` lines, which is why
`scripts/trace_invariants.py` counts them and why the Status column above can
say so.

Everything else divides as follows. Class **B** — the great majority: every
criterion in `TAB_LIFECYCLE_CONTRACT` §13, `OMNIBOX_CONTRACT` §13,
`BROWSER_UTILITIES_CONTRACT`, `SESSION_PROFILE_CONTRACT`,
`BOOKMARKS_HISTORY_CONTRACT`, `DOWNLOAD_SAFETY`, `SECURITY_CENTER_CONTRACT`,
`GESTURE_CONTRACT` GA-1–GA-14 and GA-16–GA-17, `SIDE_PANEL_CONTRACT`
SPA-1–SPA-18, `COMMAND_PALETTE_CONTRACT` CPA-1–CPA-26 and CPA-32–CPA-33, and
the `TAB_WORKSPACE_SPLIT`
and `ADVANCED_TABS` evidence bullets.

Class **H** — needs a person at a screen: `DESIGN_SYSTEM_CONTRACT` R1–R14; the
`docs/SUNSHINE_NEW_TAB_SPEC.md` verification gate; the visual gate in
`docs/WINDOWS_CHROMIUM_BUILD.md`; `DOWNLOAD_SAFETY` DSA-7;
`COMMAND_PALETTE_CONTRACT` CPA-18 and CPA-27–CPA-31; `SIDE_PANEL_CONTRACT`
SPA-19–SPA-23; `GESTURE_CONTRACT` GA-15 and GA-18; the `PERMISSION_POLICY`
roll-gate smoke test;
and the UI-surfaces row of the extension matrix.

A qualification on that class: several are stated as human observations but are
mechanisable once a build exists, through Chromium's browser tests and
accessibility APIs — screen-reader announcement checks, forced-colours contrast
sampling, focus-order assertions. The genuinely irreducible H items are the
appearance judgements (R4's photographic background has no threshold by
design), and the whole of §5.7, §6.8 and §7.9. That is the honest boundary of
automation for this project.

---

## 9. Open questions for the product owner

Distinct from the P0/P1 questions already open in handoff §11 and in the
individual contracts; each of these blocks the *acceptance* rather than the
implementation.

| Priority | Question | Blocks |
|---|---|---|
| ~~P0~~ | ~~Is `proprietary_codecs=false` an intended product decision?~~ **Settled by `docs/decisions/0004-media-codecs.md`**: enabled under a personal-use premise, so A1.4 becomes evaluable. The premise, not convenience, is what makes it permissible, and it must be revisited before any distribution. | settled |
| P0 | Are §5.7 and §6.8 gates or reports? Handoff §10 forbids starting a wave while a gate knowingly fails, but two Stage 1 items and three Stage 2 items have no criterion, so the gate cannot currently be evaluated either way. | Stage 1 exit |
| ~~P0~~ | ~~Who owns profile onboarding and the §5.6.6 OAuth separation?~~ **Answered** by `docs/PROFILE_ONBOARDING_CONTRACT.md`: a keyless build has no Dice, no browser sign-in and no first-run experience, so local-only is what the build produces rather than a mode it implements. | settled |
| ~~P0~~ | ~~What is the telemetry and crash sink?~~ **Answered** by `docs/TELEMETRY_CONTRACT.md`: Sunshine records and does not report. Three upstream gates are already closed in a non-branded build, so the numbers the suites need never leave the machine. This also closes `docs/PERFORMANCE_BUDGET.md` §9's version of the question and `SIDE_PANEL_CONTRACT` D1's assumption. | settled |
| ~~P0~~ | ~~Does §5.6.1's policy handler survive `PERMISSION_POLICY`?~~ **Settled: both §5.6.1 and §5.6.3 are withdrawn in place**, as §5.3's row was. Chromium already blocks popups without a user gesture, and default-deny denies before the user is asked — which removes the very decision the clause says they should have. | settled |
| P1 | Is there an **absolute** acceptability threshold for CPU and memory, and a long-session memory-growth observation? `docs/PERFORMANCE_BUDGET.md` answers §9.2 with deltas and scopes both out by design, leaving A1.9 uncovered and A2.3 partial. | Stage 1 exit |
| P1 | Which three of the five §7.9 candidates are the claim, and what makes an advantage "durable"? | Stage 3 exit |
| P1 | May a live-web dogfood observation be cited as evidence for a contract criterion that forbids live sites, and vice versa? See §1.3 and C8. | all stages |
| P1 | Who owns site compatibility, and where is a broken site filed? | Stage 2 |
| ~~P2~~ | ~~Should the numbered acceptance criteria be given stable identifier prefixes?~~ **Taken.** Every ordinal list in §2 carries a per-document prefix, with the ordinals unchanged so existing citations still resolve, and `PERFORMANCE_BUDGET`'s budgets are `PB-1`…`PB-6` rather than `P1`…`P6`. `TAB_WORKSPACE_SPLIT_CONTRACT` §10's unnumbered bullets are the one list left without a handle. | settled |

Two questions already open elsewhere are load-bearing here and are not restated
as new: `ADVANCED_TABS_CONTRACT` Q3, which leaves two acceptance criteria
unrunnable (C7), and the handoff §11 P0 on warned dangerous downloads, which
`DOWNLOAD_SAFETY` records as blocking its own runtime implementation.

---

## 10. Not verified

- No Chromium checkout, configuration, compilation or link was performed.
  **NOT RUN.**
- No Sunshine or Chromium binary was launched on any platform. **NOT AVAILABLE.**
- No acceptance criterion of any contract was executed, and no item of §5.7,
  §6.8 or §7.9 was exercised. **NOT RUN.**
- No visual, accessibility, localisation, keyboard or screen-reader check was
  performed. **NOT RUN.**
- The codec configuration in U1 is read from the GN args in
  `scripts/build_chromium_windows.ps1`, from `docs/decisions/0004-media-codecs.md`
  and from the Media codecs section of `docs/WINDOWS_CHROMIUM_BUILD.md`. That the
  compiled H.264 and AAC paths decode any particular site's media is inferred
  from the configuration and was not observed. **NOT RUN.**
- The verdicts in sections 3, 4 and 5 are claims about which criteria exist in
  `docs/`, verified by reading the documents listed in section 2 at the state
  of this wave. They are not claims about any behaviour of any build.
- The counts in C5 are read from `first_party/commands.json` and are current as
  of this wave; they will need re-reading whenever the registry changes.
- `docs/PERFORMANCE_BUDGET.md` was added to the repository while this index was
  being written, and rows A1.9, A2.3, U4, U5 and C9 were revised against it
  before completion. Its own measurements are **NOT RUN** and no baseline has
  been taken, so no verdict here rests on a performance result.
- No contract was edited, no criterion was added or renumbered, no command was
  registered, and no patch, module or guard was changed by this wave.
