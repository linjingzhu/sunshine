# Sunshine OS telemetry contract

**Status:** Contract. Settles the P0 in `docs/ACCEPTANCE_SUITES.md` §9 ("what is
the telemetry and crash sink?") and the P2 in `docs/PERFORMANCE_BUDGET.md` §9
("does Sunshine emit UMA at all in shipping builds, or are these budgets
lab-only?"). Declares no command and amends no other contract's criteria.

**Settles:** whether Sunshine emits, whether it reports, what consent exists,
what an event may carry, what happens off the record, whether there is a crash
channel, what may never be measured, and what a future wave must do to add a
metric.

**Pinned upstream:** Chromium `152.0.7977.42`. Every upstream statement in §1
was read from that revision on 2026-08-17. Nothing was executed: build **NOT
RUN**, runtime **NOT RUN**, measurement **NOT AVAILABLE**.

---

## 0. Why this document exists

Twenty-six registered commands in `first_party/commands.json` each declare a
`Sunshine.Command.*` event. `docs/GESTURE_CONTRACT.md` §7 declares four more.
`docs/DOWNLOAD_SAFETY.md` DSA-6 requires warning events.
`docs/SIDE_PANEL_CONTRACT.md` D1 assumes a session histogram exists.
`docs/PERFORMANCE_BUDGET.md` §4 PB-4 proposes a paired comparison over the
`Startup.*` family. Nothing receives any of it, and
`docs/ACCEPTANCE_SUITES.md` U4 records the consequence: five of the seven Stage 2
acceptance items and four of the five Stage 3 candidates have no evidence path.

Three documents ask one question. This is the answer, and the answer is not a
sink. A sink is what you build after you have decided that a browser reports on
its user. That decision is made here first, and it is made against what the
pinned revision actually does rather than against what a Chrome-branded build
does.

---

## 1. What Chromium provides at `152.0.7977.42`

Read from the pinned tag. Nothing in this section is recalled.

### 1.1 The four pipelines

| Pipeline | Entry point | Shape of a record | Keyed to |
|---|---|---|---|
| UMA histograms | `base/metrics/histogram_macros.h`, `base/metrics/histogram_functions.h` | An aggregate bucket count over a reporting interval | Nothing. A histogram is a count per bucket |
| User actions | `base/metrics/user_metrics.h`, declared in `tools/metrics/actions/actions.xml` | A name **and a timestamp**, in sequence | The session's timeline |
| UKM | `services/metrics/public/cpp/ukm_recorder.h`, `components/ukm/ukm_recorder_impl.h`, declared in `tools/metrics/ukm/ukm.xml` | An event attached to a source id | **A URL** — see `services/metrics/public/cpp/ukm_source_id.h` |
| Crash reports | `components/crash/core/app/crash_reporter_client.h`, annotations via `components/crash/core/common/crash_key.h` | Process memory plus annotations | The crashing process |

`tools/metrics/actions/README.md` states the distinction between the first two
without ambiguity: user actions "come with only a name and a timestamp" and "are
best used when you care about a sequence — which actions happen in what order.
If you don't care about the order, you should be using histograms." That
sentence decides §5.4 of this document.

### 1.2 The three gates, all of which are already closed in a Chromium build

This is the decisive finding, and it is three independent mechanisms, not one.

| # | Gate | Where | State in a build with `is_chrome_branded = false` |
|---|---|---|---|
| G1 | Consent can never become true | `components/metrics/metrics_service_accessor.cc` | `MetricsServiceAccessor::IsMetricsReportingEnabled()` is compiled behind `#if BUILDFLAG(GOOGLE_CHROME_BRANDING)`; the `#else` branch returns false unless a test-only force flag is set. The comment on that branch reads "In non-official builds, disable metrics reporting completely." |
| G2 | There is no metrics endpoint | `components/metrics/server_urls.cc` and the public `server_urls.grd` it reads through `components/metrics/BUILD.gn` | The UMA, insecure-UMA, UKM and DWA URLs are the placeholder `-`, which the code converts to an empty `GURL`. The file's own comment: the strings "are intentionally empty to prevent Chromium forks from accidentally sending metrics to Google servers." |
| G3 | There is no crash endpoint | `components/crash/core/app/crash_reporter_client.cc` | `CrashReporterClient::GetUploadUrl()` returns the default upload URL only under `GOOGLE_CHROME_BRANDING && OFFICIAL_BUILD`, and the empty string otherwise. |

`build/config/chrome_build.gni` declares `is_chrome_branded = false` as the
default, and `scripts/build_chromium_windows.ps1` does not set it — it sets
`is_official_build=true`, which satisfies neither G1 nor G3, both of which test
branding.

The consequence is worth stating in one sentence, because it inverts the usual
framing of this question. **Sunshine does not have telemetry switched on that it
must decide whether to leave on. It has no reporting capability at all, and
acquiring one means deliberately defeating three separate upstream mechanisms,
one of which exists in the source specifically to stop forks from doing it by
accident.**

### 1.3 What is *not* gated: local recording

The gates above govern whether a log is assembled and uploaded. They do not
govern whether a histogram accumulates. A `UMA_HISTOGRAM_*` call writes into the
in-process statistics recorder and marks the histogram as UMA-targeted; whether
those samples are ever snapshotted into a log is decided by the metrics service,
which `components/metrics_services_manager/metrics_services_manager.cc` starts
only when `may_record_` is true.

Upstream also ships the local read paths, and they are the ones this contract
uses:

- `chrome/browser/ui/webui/metrics_internals/metrics_internals_ui.h` — the
  `chrome://metrics-internals` debug page.
- `components/metrics/metrics_switches.h` declares
  `--export-uma-logs-to-file=<path>`, documented as observing all UMA logs
  created during the session and exporting them on shutdown; and
  `--metrics-recording-only`, documented as enabling "the recording of metrics
  reports but disables reporting … the report is dropped rather than sent to
  the server."

So the capability Sunshine needs for §5.1 of `docs/ACCEPTANCE_SUITES.md` already
exists, on the device, with no server on the other end.

### 1.4 Off the record: UKM is gated, UMA is not

`MetricsServicesManager::UpdateUkmService()` enables UKM recording only when
`consent_given_ && listeners_active && ukm_allowed && !is_incognito`, where
`is_incognito` comes from `IsOffTheRecordSessionActive()` — declared on
`components/metrics_services_manager/metrics_services_manager_client.h`,
implemented for desktop in `chrome/browser/metrics/chrome_metrics_services_manager_client.cc`
by delegating to `chrome/browser/ui/browser_otr_state.h`. The DWA branch
immediately below applies the same test.

The UMA branch in the same function applies **no such test**. It calls
`metrics->Start()` whenever `may_record_` is true, regardless of whether an
off-the-record window is open.

This matters more than any other line in this section. A `Sunshine.Command.*`
histogram written with the ordinary macros, from the ordinary dispatcher, would
count commands invoked in an incognito window, and a reviewer who knows
Chromium's model would reasonably assume it did not. §4 rules on it.

### 1.5 What a downstream must do to add one histogram

From `tools/metrics/histograms/README.md`, read at the pinned tag:

1. An entry in a `tools/metrics/histograms/metadata/<area>/histograms.xml` file,
   ideally in the same changelist as the emitting code — the README's stated
   reason is that the reviewer's questions about the description "reveal
   problems with interpretation of the data and call for a different recording
   strategy."
2. `expires_after` is a **required** attribute. "It is never appropriate to set
   the expiry to `never` on a new histogram."
3. A named primary owner who is a person, not a mailing list of users, whose
   job includes deciding when the metric has outlived its usefulness.
4. A description understandable to someone unfamiliar with the feature, stating
   **when** it is recorded.
5. For an enumerated histogram: values from `0`, explicit numeric values, the
   "persisted to logs … should not be renumbered and numeric values should never
   be reused" comment, labels in `tools/metrics/histograms/enums.xml`.
6. Presubmit validation at `tools/metrics/histograms/PRESUBMIT.py`.
7. Review by a metrics owner, whose checklist puts "Privacy and Purpose" first
   and instructs "**Escalate if there's any doubt!**"
8. Changing what a histogram means requires a **new name**, not a redefinition
   ("Revising Histograms"); retiring one requires removing the entry and, for
   enum labels, marking them `(Obsolete)` rather than deleting them.

Points 2, 3, 7 and 8 are the parts worth copying. They are the difference
between a metrics system and a tracking system, and they are procedural rather
than technical — which is exactly why a downstream that copies only the macros
inherits none of it.

`base/metrics/histogram_macros_local.h` offers `LOCAL_HISTOGRAM_*`, which
records but is never uploaded. The README's own guidance: "We don't recommend
using local histograms outside of [local debugging]." §2.4 rules on this.

---

## 2. The ruling

### 2.1 Three forks, and what follows from each

**Fork A — emit nothing.** Delete the `telemetry` field from the registry, delete
`docs/GESTURE_CONTRACT.md` §7, and accept that every rate in handoff §6.8 and
every Stage 3 candidate degrades permanently to self-report. What follows: the
product can never answer "is the gesture false-activation rate rising?" or "did
the panel mount when nobody opened it?", and `docs/SIDE_PANEL_CONTRACT.md` D1 —
the cheapest correctness gate in the repository — cannot be written. The cost is
paid forever to avoid a risk that, per §1.2, does not exist in a build with no
endpoint.

**Fork B — emit and report.** Stand up a collection service. What follows, all of
it, none of it optional: an upload endpoint and a signing key; a client
identifier that is by construction a stable per-install pseudonym; a retention
schedule; a deletion path a user can actually invoke; a published privacy
policy; a lawful basis in every jurisdiction the browser ships to; a consent UI
and its localisation; and a downstream patch defeating G1, G2 and G3 — including
the one whose source comment says it exists to stop exactly this happening by
accident. It also makes the twenty-six command names a per-install usage stream
leaving the machine, which is the thing `docs/SESSION_PROFILE_CONTRACT.md`'s
secret boundary and `docs/OMNIBOX_CONTRACT.md` §9 spend their length preventing
one field at a time.

**Fork C — record locally, report nothing.**

### 2.2 The decision

**T1. Sunshine records. Sunshine does not report. Fork C.**

- Every `Sunshine.*` event specified anywhere in `docs/` is a histogram recorded
  into the local statistics recorder of the running browser and nowhere else.
- No Sunshine build carries a metrics upload endpoint, a crash upload endpoint,
  a client identifier promoted for reporting, or a Sunshine-operated collection
  service.
- G1, G2 and G3 are load-bearing product decisions, not incidental build state.
  A patch that sets `is_chrome_branded = true`, populates a server URL,
  overrides `GetUploadUrl()`, or ships
  `--force-enable-metrics-reporting` in a default command line is refused at
  review, not measured against a threshold.
- Evidence for `docs/ACCEPTANCE_SUITES.md` §5.1 is produced by the operator, on
  their own machine, from their own browser, by exporting their own local log.
  There is no third party in that sentence.

**The strongest argument for it, stated once.** Upstream already decided that a
fork must not report by default, implemented that decision three times over, and
wrote the reason into the source. The only thing Sunshine adds by choosing Fork C
is the *intent* — turning an inherited default into a stated boundary that a roll
gate re-checks. The only thing Fork B would add is a recipient. Every acceptance
item in the repository needs a **number**; not one of them needs the number to
leave the machine. Reporting is therefore pure cost against the acceptance
suites, and its benefit — fleet-scale data — is a benefit to a product
organisation that does not exist at Stage 3.

### 2.3 One build, not two

**T2.** There is no separate telemetry build. Recording is identical in every
Sunshine build, and the dogfood configuration differs only in the operator's
command line. A build whose instrumentation differs from the shipped one
produces evidence about a browser nobody uses.

**T3.** Emission is event-driven only. No timer, no polling, no periodic
provider, no idle sampling. This keeps `docs/PERFORMANCE_BUDGET.md` PB-5 intact:
PB-5 holds that the *existence* of a repeating Sunshine task is the regression,
and a histogram incremented on a user-initiated command is not one. It also puts
the README's "Impossible: Identify percent of browsing time a feature is in use"
permanently out of scope, which is the right answer to a question Sunshine
should not be asking.

### 2.4 UMA macros, not local histograms

The tempting move is `LOCAL_HISTOGRAM_*`: never uploaded by construction, so no
build-flag mistake can ever leak it. **Rejected.**

**T4.** Sunshine histograms use `base/metrics/histogram_macros.h` (or the
function equivalents in `base/metrics/histogram_functions.h`) and carry a full
XML declaration.

Three reasons. First, the XML apparatus — expiry, named owner, stated recording
condition, privacy-first review — *is* the protection; local histograms opt out
of all of it and get a metric with no owner and no expiry, which is how a
metrics system rots. Second, `chrome://metrics-internals` and
`--export-uma-logs-to-file` operate on UMA logs, so the evidence path of §2.2
requires UMA-flagged histograms. Third, the guarantee against accidental upload
should live in the three upstream gates — maintained upstream, re-verified at
every roll by §8.4 — and not in a macro choice that a single careless edit
reverses silently.

---

## 3. Consent

`docs/PERMISSION_POLICY.md` establishes the governing principle for this
repository: Sunshine keeps Chromium's system and "does not add a second
permission store". Applied here it produces an answer that is shorter than
expected.

### 3.1 The default

**T5. There is no Sunshine consent state, because there is no reporting state to
consent to.** Sunshine registers no preference of its own for metrics.
Chromium's own `metrics::prefs::kMetricsReportingEnabled`, declared in
`components/metrics/metrics_pref_names.h`, remains registered and remains inert:
per G1 it cannot make `IsMetricsReportingEnabled()` return true in this build.
Sunshine neither reads it, writes it, nor surfaces it.

### 3.2 The prompt: there is none, and that is the honest answer

**T6. Sunshine shows no metrics-consent prompt and ships no metrics toggle.**

A prompt asking "help improve Sunshine by sharing usage data?" when no recipient
exists is a false statement rendered in a dialog, and a toggle whose two
positions produce identical behaviour is worse than no toggle: it manufactures
the belief that the off position is protecting the user from something. If
Sunshine ever moves to Fork B, the prompt is designed then, against a real
recipient, a real retention period and a real deletion path — and it is designed
under UX review with the first-run default recorded through
`components/metrics/metrics_reporting_default_state.h`'s `OPT_IN` / `OPT_OUT`
distinction, which exists precisely so that a checkbox's default state is itself
auditable.

**T7.** Sunshine's own surfaces must not describe the browser as "collecting
anonymous usage statistics", "sending telemetry", or any equivalent. It is not
doing that, and a privacy claim that overstates what the product does is as much
a defect as one that understates it.

### 3.3 Withdrawal, and what happens to buffered events

Under Fork C the question has a mechanical answer.

**T8.** The record is process-lifetime. Sunshine persists no `Sunshine.*`
histogram to disk, writes no local metrics database, and adds nothing to the
profile directory. Browser exit is the deletion, and it is complete because
there was never a second copy.

**T9.** Export is an explicit, per-launch operator action taken on the command
line — never a setting, never a default, never a Sunshine UI affordance. An
exported log is a user-owned file governed by `docs/SESSION_PROFILE_CONTRACT.md`'s
secret boundary: it is subject to the same canary test as any Sunshine
diagnostic, and it must not be attached to a bug, a workflow artifact, or an AI
request without that test having been run.

**T10.** The withdrawal analogue for a locally-recorded histogram is closing the
browser. There is nothing else to withdraw, and this contract does not invent a
ceremony that implies otherwise.

### 3.4 If a future wave adds reporting: upstream's semantics, and their known leak

Recorded now so that a later wave does not rediscover it.
`MetricsServicesManager::UpdatePermissions()` handles a consent transition from
given to not-given by calling `Purge()` on the metrics service, `Purge()` and
`ResetClientState()` on UKM, and `Purge()` on DWA. That is the correct behaviour
and it is already implemented.

It is also incomplete, and upstream says so in a comment immediately above the
purge: a TODO referencing crbug.com/40267999 records that "there is an
additional last log that is created and stored right after this in
`UpdateRunningServices()` and is not cleaned up."

**T11.** Any future Fork B proposal must state how that last log is handled
before it is accepted. Inheriting a known gap in the withdrawal path silently is
not available.

---

## 4. Off-the-record windows

`scripts/workspace_model.py` refuses to persist a per-workspace record of the
last page read when the window is off the record, and its docstring gives the
reason: that record "is browsing history by another name."
`docs/TAB_LIFECYCLE_CONTRACT.md` §10 states the same rule for workspace and
split state. `docs/COMMAND_PALETTE_CONTRACT.md` invariant 13 states it for the
recents store.

A command histogram is the same class of data. It is weaker — no URL, no title,
no ordering — but "which browser commands this person used while in a private
window" is a description of private-window behaviour, and the argument that an
aggregate count is harmless is exactly the argument that would have kept the
last-page-read record in the incognito profile.

**T12. A `Sunshine.*` event is not recorded when the invoking window is off the
record. Not recorded — not recorded-and-withheld.**

**T13.** The gate is at the emit site, in the dispatcher, which already resolves
the invoking window's profile in order to evaluate availability. It is not at
the pipeline, because per §1.4 upstream does not gate UMA on off-the-record
state and Sunshine must not patch that behaviour for all of Chromium's
histograms in order to fix its own two dozen.

**T14.** The rule is a bright line, not a per-histogram judgement. "Which
Sunshine metrics are harmless in incognito" is a question that would be asked
again on every new metric forever, and answered slightly more permissively each
time. There is no exception process.

**The cost, stated.** Every dogfood number under-counts by exactly the operator's
off-the-record usage, and the shortfall is unknowable because measuring it is
the thing forbidden. Any claim built on these numbers — in particular
`docs/ACCEPTANCE_SUITES.md` §5.1's A3.1 falsifier, "gesture invocations
declining across the window while toolbar invocations rise" — must state this
limitation. A user who moves a workload into incognito produces the same signal
as a user who stops using the feature.

---

## 5. What a `Sunshine.Command.*` event may carry

### 5.1 The registry's privacy property, stated rather than left to chance

`first_party/commands.json` gives each of the twenty-six commands a fixed
identifier and a telemetry name derived from it — `scripts/validate_commands.py`
computes the expected name from the identifier and rejects any drift. No command
declares a parameter, and `docs/COMMAND_PALETTE_CONTRACT.md` invariant 3 forbids
any invocation source from supplying a payload.

**T15.** That is a privacy property of the design and is now a requirement of it:
**a Sunshine command event's name is a compile-time constant chosen from a closed
set of twenty-six, and its payload is not derived from any runtime value the
user produced.** The event says a command ran. It cannot say more, because there
is nothing in the command for it to say.

**T16.** A command may not acquire a parameter, an argument, a target, or a
selection payload in order to make its telemetry more informative. If a future
command genuinely needs an argument, its telemetry does not carry it — see
`docs/COMMAND_PALETTE_CONTRACT.md` §4's absolute exclusion of argument values,
which this contract adopts unchanged.

### 5.2 The permitted payload, in full

| Field | Permitted | Source |
|---|---|---|
| Command identity | Yes | The registry, at build time |
| Invocation source | Yes, from a closed set: toolbar, keyboard, menu, context menu, palette, gesture | Required by `docs/COMMAND_PALETTE_CONTRACT.md` CPA-1, which demands identical telemetry from every source "differing only in the source label" |
| Anything else | **No** | — |

**T17.** The event is recorded **once, on dispatch, by the dispatcher**, and only
when the command actually executes on a user's instruction. Two consequences,
both already required elsewhere: an unavailable command records no command event
(`docs/GESTURE_CONTRACT.md` §7 gives unavailability its own separate event
instead), and a tab or surface Sunshine creates through a command's
implementation without the user asking for it records nothing
(`docs/TAB_LIFECYCLE_CONTRACT.md` §7.4 — "telemetry counts user intent, and no
user asked for this tab"). Telemetry counts intent that became action.

**T18.** A command's failure is recorded as the **declared error token** from that
command's `errors` array in the registry, and never as a formatted message, an
exception string, a net error string, or a path. The token set is closed by the
registry, so the failure record has the same property as the success record: it
is drawn from a fixed vocabulary shipped in the binary.

### 5.3 Prohibited without exception

The prohibition list of `docs/GESTURE_CONTRACT.md` §7 applies verbatim to every
Sunshine event, command or otherwise: page content, selected text or
accessibility text; URLs, origins, hostnames, page titles, filenames; raw
pointer coordinates or paths; any identifier for the tab, workspace, profile or
window. To it this contract adds:

- any command argument, query, or user-typed string, whole or partial —
  `docs/OMNIBOX_CONTRACT.md` §9 and `docs/BROWSER_UTILITIES_CONTRACT.md` already
  forbid omnibox text and find queries specifically; this generalises it;
- a workspace name, a profile name, or a count of workspaces that would
  fingerprint a configuration;
- any value that could serve as a **join key** between two events, including a
  session nonce, a sequence number, or a monotonic counter;
- a wall-clock timestamp attached to an individual occurrence (see §5.4).

### 5.4 No user actions, and no UKM. Ever.

**T19. Sunshine records no user action.** `base::RecordAction` produces, per
`tools/metrics/actions/README.md`, "only a name and a timestamp", ordered. A
timestamped ordered stream of twenty-five command names is a reconstruction of
the session: it distinguishes reading from shopping from working, it recovers
idle periods, and it is a behavioural trace in everything but name. The
aggregate histogram is chosen *because* it discards the order. Sunshine adds no
entry to `tools/metrics/actions/actions.xml`.

**T20. Sunshine registers no UKM event and adds nothing to
`tools/metrics/ukm/ukm.xml`.** UKM keys an event to a source id, and a source id
is a URL (`services/metrics/public/cpp/ukm_source_id.h`). "This command was used
on this site" is the single record every contract in this repository is written
to prevent. There is no threshold, no aggregation, and no k-anonymity argument
that reopens this; the decision is categorical.

**T21.** The same applies to structured metrics and to any future upstream
pipeline that attaches an event to a page, a profile, or a stable client. New
pipelines arrive at rolls; the default answer is no, and the roll gate asks.

### 5.5 Shape: twenty-five names, or one enumeration

Upstream guidance points at an enumerated histogram for a closed set of
outcomes, and twenty-five separate histogram names means twenty-five XML
entries, twenty-five expiry dates and twenty-five owners for one question. One
enumerated histogram with twenty-five buckets would give the denominator for
free, make the "no parameters" property structural rather than conventional, and
cost one entry.

The registry has already shipped the twenty-five names, and
`scripts/validate_commands.py` enforces them. This document does not rename
shipped content it does not own. The conflict is recorded as P1 in §12.

**T22.** Whichever shape is chosen, the invariants of §5.1–5.4 hold unchanged.
They are properties of the payload, not of the histogram count.

---

## 6. Crash reporting

`docs/ACCEPTANCE_SUITES.md` U8 records that nothing in this repository can
observe a crash, and that `docs/EXTENSION_COMPATIBILITY_GATE.md` states crash
reporting "must not be assumed to exist".

**T23. There is no crash reporting channel. Not a separate consent, not a
separate pipeline: none.**

Four reasons, in order of weight.

1. **A crash dump is process memory.** It contains, by construction, the
   material `docs/SESSION_PROFILE_CONTRACT.md` names as canary values: URLs with
   query and fragment, form values, cookies, authorization headers. A telemetry
   contract that permits aggregate counts and forbids page titles cannot
   coherently permit a channel that ships the heap.
2. **G3 is already closed.** `CrashReporterClient::GetUploadUrl()` returns the
   empty string outside a branded official build. There is no channel to
   decide about switching off — only one to decide about building.
3. **"Separate consent" is a Sunshine invention.** Upstream deliberately fuses
   the two: the desktop consent check is
   `ChromeMetricsServiceAccessor::IsMetricsAndCrashReportingEnabled()`, one
   predicate for both, wired into the `EnabledStateProvider` of
   `components/metrics/enabled_state_provider.h`. Splitting them downstream
   creates a second consent model to maintain across every roll, in service of a
   pipeline that does not exist.
4. **Redaction is a contract, not a filter.** Shipping dumps would require a
   crash-key allowlist, a stack-sanitisation policy, and a written statement of
   what a dump may contain — a document at least as long as this one. It is
   reopenable; it is not a flag.

**T24.** Sunshine sets no crash key. `components/crash/core/common/crash_key.h`
annotations are local-only in this build, but a key set now is a key uploaded on
the day someone builds Fork B, and its author will not be in the room.

**What Sunshine keeps.** Everything local and user-visible:
`docs/SESSION_PROFILE_CONTRACT.md` SRA-1 to SRA-8 — Chromium's exit-type state,
its native crash recovery UI, its crashed-tab UI, and its per-`WebContents`
renderer crash isolation — are untouched, because none of them requires an
upload.

**What Sunshine loses, stated.** Handoff §5.7 A1.7 ("no critical crash") and
§6.8 A2.1 (crash and renderer-recovery *rate*) remain class H, evidenced by an
operator's observation over the window and nothing stronger.
`docs/ACCEPTANCE_SUITES.md` A1.7 already says a day that ends without the user
noticing a crash "is not the same statement" as no crash; that assessment stands
and this contract does not improve it. The partial mitigation available under
Fork C is that `docs/TAB_LIFECYCLE_CONTRACT.md` §11's crash, discard and freeze
counts are locally-recorded histograms like any other, so a renderer-crash
*count* is available from the local export even though a crash *report* is not.

---

## 7. What must not be measured

A closed list. Adding to it is free; removing from it is a decision someone
signs.

1. **Anything keyed to a page.** URL, origin, host, eTLD+1, title, favicon,
   filename, file path, or any hash or truncation of them. This is T20 restated
   at the payload level so that it cannot be satisfied by avoiding the UKM API
   while reintroducing the data as a histogram bucket.
2. **Anything derived from what the user typed or selected.** Omnibox text,
   find query, palette query — including bucketed length, which
   `docs/COMMAND_PALETTE_CONTRACT.md` §11.3 permits for the palette's own events
   and which this contract does not extend to command events — page selection,
   or accessibility text.
3. **Any stable or joining identifier.** Tab, window, workspace, profile,
   session, install, or device. A per-install identifier is the difference
   between a count and a cohort.
4. **Sequence and timing of individual events.** No user actions (T19), no
   ordered pairs, no inter-event durations. The one existing exception is
   `docs/GESTURE_CONTRACT.md` §7's reversal signal; see the defect in §11.3.
5. **Anything recorded off the record** (T12).
6. **Site compatibility and page behaviour.** A count of pages that rendered
   incorrectly is a count of pages the user visited. `docs/ACCEPTANCE_SUITES.md`
   A2.2 is uncovered and stays uncovered by this route.
7. **Per-origin permission decisions.** A stream of allow/deny per origin is a
   browsing profile with extra steps. `docs/PERMISSION_POLICY.md` A2.5's
   "permission friction" is not measurable this way and this contract does not
   pretend otherwise.
8. **Download identity.** Filename, path, URL, or file type of a download.
   `docs/DOWNLOAD_SAFETY.md` already forbids sending download URLs or file
   metadata to a Sunshine service; there is no service, and there is also no
   histogram bucket.
9. **Extension identity or inventory.** Which extensions are installed is a
   fingerprint.
10. **Anything about a profile other than the one that invoked the command**, and
    any count that spans profiles.
11. **Anything about the user.** No demographics, no locale-as-identity, no
    hardware inventory beyond what a paired performance comparison under
    `docs/PERFORMANCE_BUDGET.md` §2 requires and records locally.

---

## 8. How a future wave adds a metric

An unreviewed histogram is how a metrics system becomes a tracking system one
commit at a time. The gate below is the answer to that, and it is deliberately
procedural.

### 8.1 The upstream apparatus is adopted whole

Every requirement in §1.5 applies to a `Sunshine.*` histogram: XML entry in the
same change as the code, a required `expires_after` that is never `never`, a
named human owner, a description stating when it is recorded, enum discipline in
`tools/metrics/histograms/enums.xml`, presubmit, and a new name rather than a
redefinition when semantics change.

### 8.2 What Sunshine adds

**T25.** A new `Sunshine.*` metric ships only with all six of:

1. a written answer to **"what decision changes based on this number?"**, naming
   the decision and the person who makes it — the README's own test is that a
   metric neither the owner nor the team uses should be removed;
2. a named owner and an expiry no longer than one year;
3. a stated recording condition, including its behaviour off the record (which
   is T12 unless a written exception is argued and refused);
4. an explicit check against the exclusion list in §7, item by item, recorded in
   the change;
5. review by someone who is not the metric's author, whose first question is
   privacy and whose escalation path is stated in the change;
6. a declaration in Sunshine's own downstream XML, in the patch stack — never a
   bare macro call at a call site with no metadata.

**T26.** A metric is refused, not reviewed, if its bucket count is unbounded, if
any bucket is derived from user-supplied text or a visited page, if it requires
a timer or a periodic provider (T3), or if it introduces a join key (§7.3).

**T27.** The registry stays authoritative: a `Sunshine.Command.*` name exists if
and only if its command identifier exists in `first_party/commands.json`.
`scripts/validate_commands.py` already derives and enforces the name; §12 P2
proposes extending it to the XML side so the two cannot drift.

### 8.3 What a wave may not do

**T28.** No wave may add a metric by widening an existing one. Appending a bucket
to an enumerated histogram whose meaning is "which command ran" in order to also
express "on what kind of page" is a new metric wearing an approved name, and the
README's "Revising Histograms" rule already requires a new name when semantics
change.

### 8.4 Upstream-roll gate

**T29.** Every Chromium revision update re-verifies, and the roll is blocked
until each is reviewed:

| Check | Where |
|---|---|
| G1 still compiles reporting out of non-branded builds | `components/metrics/metrics_service_accessor.cc` |
| G2's public placeholder URLs are still empty | `components/metrics/server_urls.cc` and the non-internal branch of `components/metrics/BUILD.gn` |
| G3 still returns an empty upload URL outside branded official builds | `components/crash/core/app/crash_reporter_client.cc` |
| `is_chrome_branded` still defaults false and is still unset by the build scripts | `build/config/chrome_build.gni`, `scripts/build_chromium_windows.ps1` |
| UMA is still not gated on off-the-record state, so T13's emit-site gate is still required | `components/metrics_services_manager/metrics_services_manager.cc` |
| No new upstream pipeline attaches Sunshine data to a page or a client (T21) | the metrics component's public headers |
| Every Sunshine histogram's `expires_after` is still in the future | Sunshine's downstream XML |

A changed upstream default blocks the roll. The correct response is to adapt at
Chromium's integration boundary — never to layer a second Sunshine metrics
system over it, which is the failure mode
`docs/SESSION_PROFILE_CONTRACT.md` and `docs/PERMISSION_POLICY.md` both name.

---

## 9. Acceptance criteria

Runnable once a native build exists. All are **NOT RUN**.

`TA-` is the prefix for these criteria, and the ordinals are unchanged:
criterion 9 is `TA-9`. `T` remains the invariant prefix of §10; the two do not
overlap.

**Recording and non-reporting**

1. **TA-1.** With the browser running normally and a `Sunshine.Command.*`
   histogram emitting, `chrome://metrics-internals` shows the samples and no log
   is uploaded; a network capture over the session shows no request to any
   metrics or crash endpoint.
2. **TA-2.** The same session with network access disabled behaves identically,
   proving recording never depended on reachability.
3. **TA-3.** A build produced by the repository's own scripts reports
   `is_chrome_branded = false`, and the metrics server URL and crash upload URL
   resolve empty.
4. **TA-4.** No file under the profile directory grows as a result of Sunshine
   command invocation, and no Sunshine-written file anywhere contains a
   histogram sample after the browser exits (T8).

**Payload**

5. **TA-5.** Invoking `browser.back` from the toolbar, the keyboard, the palette
   and a gesture produces four records of one histogram, differing only in the
   source label (`docs/COMMAND_PALETTE_CONTRACT.md` CPA-1).
6. **TA-6.** Exactly one command event is recorded per successful dispatch, and
   zero for a dispatch refused by availability (T17).
7. **TA-7.** A failing command records its declared error token from the
   registry, and a byte inspection of the exported log finds none of the
   prohibited fields of §5.3.
8. **TA-8.** A canary run in the manner of `docs/SESSION_PROFILE_CONTRACT.md`
   SRA-13 — canary strings in a URL query, a form field, a find query, a
   palette query, a download filename and a workspace name — finds no canary in
   the exported log.

**Off the record**

9. **TA-9.** Invoking `browser.reload`, `bookmark.toggle` and `workspace.switch`
   in an off-the-record window increments no Sunshine histogram, and the same
   commands in a regular window in the same session do.
10. **TA-10.** Opening an off-the-record window does not suppress recording for
    the regular windows that remain open — the gate is per-invocation, not
    global, which is where this deliberately differs from upstream's UKM
    behaviour.

**Crash**

11. **TA-11.** A forced renderer crash produces no upload attempt and no crash
    key set by Sunshine code, while Chromium's native crashed-tab UI and the
    recovery path of `docs/SESSION_PROFILE_CONTRACT.md` SRA-4 to SRA-8 behave
    unchanged.

**Process**

12. **TA-12.** Every `Sunshine.*` histogram emitted by the binary has an XML
    entry with an owner and an unexpired `expires_after`, and every XML entry
    has an emitting call site. A histogram in one and not the other fails the
    build.
13. **TA-13.** Every `Sunshine.Command.*` name corresponds to a registered
    command identifier, and every registered command has exactly one (T27).

---

## 10. Invariant summary

T1 record, never report. T2 one build. T3 event-driven only. T4 UMA macros plus
XML. T5 no Sunshine consent state. T6 no prompt, no toggle. T7 no overstated
privacy claim. T8 process-lifetime only. T9 export is an operator action.
T10 exit is the withdrawal. T11 a future Fork B must answer the last-log gap.
T12 nothing recorded off the record. T13 gate at the emit site. T14 no exception
process. T15 fixed name, no runtime-derived payload. T16 no command acquires an
argument for telemetry's sake. T17 once, on dispatch, on execution.
T18 declared error tokens only. T19 no user actions. T20 no UKM. T21 no new
page- or client-keyed pipeline. T22 shape does not change the payload rules.
T23 no crash channel. T24 no crash keys. T25 six conditions for a new metric.
T26 categorical refusals. T27 registry authoritative. T28 no widening.
T29 roll gate.

---

## 11. Defects and corrections in shipped content

### 11.1 `docs/PERFORMANCE_BUDGET.md` §8 misreads the CI citation regex

The document states that `scripts/verify_pinned_upstream.py`'s `CITATION` regex
"matches only paths under `base`, `chrome`, `components`, `content`, `net`,
`services`, `third_party`, and `ui`", concludes that its `tools/perf/…`
citations "are therefore **not** covered by the CI existence check", and proposes
"adding `tools` to that alternation, and `.csv` to the suffix list".

Read at the current revision, the alternation is
`base|build|chrome|components|content|net|services|third_party|tools|ui` and the
suffix list is `h|cc|mojom|css|ts|html|py|csv|json|gn|gni|xml`. Both `tools` and
`csv` are already present. `tools/perf/benchmarks/system_health.py` and
`tools/perf/benchmark.csv` are both matched and both already CI-checked. The
gap described does not exist and the proposed fix is a no-op. The paragraph
should be withdrawn; the finding is otherwise harmless, since the check it
believed was missing was passing all along.

### 11.2 `docs/ACCEPTANCE_SUITES.md` U4 miscounts the download events

U4 lists "the `DOWNLOAD_SAFETY` 6 warning events" alongside the
`Sunshine.Command.*` and gesture events as "specified" events that "nothing
receives". `docs/DOWNLOAD_SAFETY.md` DSA-6 does not specify Sunshine
events: it requires that Sunshine preserve **Chromium's** warning-event model
from `chrome/browser/download/download_item_warning_data.h`, and the surrounding
contract's "future patch boundary" forbids sending download data to a Sunshine
service at all. Those events are upstream's, on upstream's pipeline, subject to
the same three gates. The correct statement is that they are recorded locally
and uploaded nowhere, exactly like Sunshine's own. Nothing is missing; one row
of U4 is over-counted.

### 11.3 `docs/GESTURE_CONTRACT.md` §7's reversal signal needs sequence data, and does not say so

`Sunshine.Gesture.Reversed` fires when a gesture-dispatched command is followed
"within the reversal window" of 2000 ms "by its inverse from any invocation
source". Producing that signal requires retaining the last dispatched command
and its time and comparing a later dispatch against it — a short-lived ordered
record of user actions, which is precisely the class of data §7's own
prohibition list and §7 of this contract otherwise exclude.

It is defensible: in memory, bounded at 2000 ms, holding a command identity and
a monotonic instant with no tab, workspace or page attached, and discarded
whether or not it fires. But it is unstated, and an implementer reading only the
prohibition list would not know it was permitted. §7.4 of this contract records
it as the one exception. `docs/GESTURE_CONTRACT.md` should state the retention
explicitly and bound it; that is its owner's edit, not this document's.

### 11.4 A cumulative histogram cannot produce the per-day series §5.1 asks for

`docs/ACCEPTANCE_SUITES.md` §5.1 requires, for A3.1, "per-day counts of
activations, cancellations by reason, and reversals", and for A3.2 "daily switch
counts". A histogram accumulates from browser launch and, under T8, dies at
exit. A single export taken at the end of a fourteen-day window yields one
cumulative total per bucket and no series at all — and if the browser was
restarted during the window, it yields the total since the last restart only.

This is a real defect in the evidence plan, and it has a cheap fix that must be
stated rather than assumed: **the operator exports at the end of each browsing
day**, and each export is the delta for that day's session. A fourteen-day
dogfood already implies restarts. The falsifiers in §5.1 that depend on a trend
across the window are only available if this is done from day one; discovering
it on day fourteen produces one number and no trend.

### 11.5 `docs/SIDE_PANEL_CONTRACT.md` D1's assumption is now discharged

D1 requires the panel mount counter to be "exposed to browser tests and recorded
as a session histogram". Under T1 that is exactly what it is: a locally recorded
histogram plus a browser-test assertion, with no reporting dependency. The
assumption `docs/PERFORMANCE_BUDGET.md` §9 P2 flagged as unanswered is answered,
and D1's pass/fail-at-zero gate — the cheapest and most valuable check in the
performance budget — is implementable on the first day panel code exists.

### 11.6 `docs/EXTENSION_COMPATIBILITY_GATE.md` is right and can now be precise

"Sync, account, telemetry, crash reporting, and store services must not be
assumed to exist in Sunshine" remains true and should not be edited. It can now
be read exactly: telemetry exists as a local recording capability and does not
exist as a service, and crash reporting does not exist at all. A gate test that
fails closed in the absence of these services is testing the right thing.

---

## 12. Open decisions for the product owner

| Priority | Decision | Required by |
|---|---|---|
| **P0** | Is Fork C accepted? Everything below assumes it. Accepting it is also a decision not to build a data pipeline at Stage 2 or 3, and that decision should be made once, in the open, rather than deferred until someone needs a number | Stage 2 exit |
| **P1** | Twenty-four histogram names or one enumerated histogram with twenty-four buckets (§5.5)? One entry, one expiry, one owner and a free denominator against twenty-four of each. Changing it means changing shipped registry content and `scripts/validate_commands.py`; keeping it means twenty-four XML entries whose expiries must be renewed together | Before the first Sunshine histogram is added |
| **P1** | Who is the named owner of the `Sunshine.*` histogram family, per T25.2? The upstream apparatus does not function without a person; "the team" is not an owner | Before the first Sunshine histogram is added |
| **P2** | Should `scripts/validate_commands.py` be extended to check the downstream histogram XML against the registry (T27), so a command and its metric cannot drift? It already derives the expected name from the identifier; the missing half is the XML side | Before the first Sunshine histogram is added |
| **P2** | Does the daily-export procedure of §11.4 become a written dogfood protocol, or does the evidence plan accept cumulative totals with no trend? This changes what A3.1 and A3.2 can falsify | Before the Stage 3 dogfood window opens |
| **P3** | Does `docs/GESTURE_CONTRACT.md` §7 adopt the explicit reversal-window retention statement of §11.3, or drop `Sunshine.Gesture.Reversed`? Dropping it removes the only available proxy for a false activation, which A2.4 depends on | Before a gesture recogniser exists |

---

## 13. Not verified

- No Chromium checkout, configuration, compilation or link of the pinned
  revision was performed. **NOT RUN.**
- No browser was launched, no histogram was observed being recorded, and no
  export was produced. **NOT RUN.**
- Every acceptance criterion in §9 is **NOT RUN**, and no number exists for any
  metric named in this document. **NOT AVAILABLE.**
- The upstream statements in §1 were read from files retrieved from the GitHub
  mirror at `152.0.7977.42` on 2026-08-17: the branding guard in
  `components/metrics/metrics_service_accessor.cc`, the placeholder URLs in
  `components/metrics/server_urls.cc` and its public GRD input selected by
  `components/metrics/BUILD.gn`, the empty upload URL in
  `components/crash/core/app/crash_reporter_client.cc`, the off-the-record
  branches in `components/metrics_services_manager/metrics_services_manager.cc`,
  the consent-withdrawal purge and its TODO in the same file, the switch
  documentation in `components/metrics/metrics_switches.h`, and the process
  requirements in `tools/metrics/histograms/README.md` and
  `tools/metrics/actions/README.md`. Their **runtime** behaviour is unverified.
- The claim that a Sunshine build is non-branded is read from the default in
  `build/config/chrome_build.gni` and from the absence of an overriding argument
  in `scripts/build_chromium_windows.ps1`. No produced binary was inspected,
  because none exists.
- No legal, regulatory, or policy review of any kind informed this document. The
  Fork B costs enumerated in §2.1 are an engineering sketch, not advice.
