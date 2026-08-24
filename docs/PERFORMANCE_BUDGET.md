# Sunshine OS performance budget

## Status and scope

This contract applies to Sunshine OS on the pinned Chromium revision
`152.0.7977.42` recorded in `config/chromium.version`. It settles section 9.2
(Performance checks) of
`docs/SUNSHINE_OS_STAGE_1_TO_3_IMPLEMENTATION_HANDOFF.md`.

This wave is **documentation-only**. It adds no downstream patch, no first-party
module, no registered command, and no measurement. Nothing here has been built,
launched, or timed; see *Not verified*.

| In scope | Out of scope |
|---|---|
| What Sunshine can make slower or larger in memory, and how each is measured | Chromium's own performance, which Sunshine inherits and does not budget |
| The boundary each measurement is taken at, and which upstream instrument takes it | Inventing a Sunshine measurement where an upstream one exists |
| How a baseline is obtained before a native build exists | Absolute seconds and megabytes, which do not exist until a build does |
| What is deliberately not budgeted, and what would change that | Bytes at rest — `docs/SIZE_BUDGET.md` owns those |

### The boundary with `docs/SIZE_BUDGET.md`

`docs/SIZE_BUDGET.md` governs **bytes at rest**: compressed download, installed
application bundle, first-run profile, cache after use. This document governs
**time, memory, and CPU while running**. Size is not performance. Neither
document sets a number belonging to the other: nothing here states a megabyte of
disk, and nothing there states a millisecond.

They touch at exactly one seam, and it is already drawn: a shipped panel
resource is a size line item under `docs/SIDE_PANEL_CONTRACT.md` §4.6 D7, which
counts it in installed application size; the cost of *loading* that resource at
runtime is a mount cost and belongs here. The rule that separates them is the
same one in both documents — a resource that is never mounted still occupies
disk, and a resource that is mounted in every window costs memory whatever its
size on disk.

The release configuration required by `docs/SIZE_BUDGET.md`
(`is_official_build=true`, `is_debug=false`, `is_component_build=false`) is also
the only configuration in which a performance measurement here counts. A debug
or component build measures the build system, not the product. That
configuration is stated once, there, and used here.

## 1. Principle: Sunshine inherits performance and can only regress it

Sunshine is a native downstream of Chromium. It adds no rendering engine, no
JavaScript engine, no network stack, no compositor, no process model. Page load,
script execution, painting, scrolling, sandboxing overhead, and memory per
renderer are Chromium's, unmodified, and are as fast as the pinned revision is.
A Sunshine number for any of them would be a Chromium number wearing a Sunshine
label, and would move at every upstream roll for reasons that have nothing to do
with this product.

The interesting question is therefore not *how fast is Sunshine* but **what can
Sunshine make worse**. Every budget below is a **delta**: the same Sunshine
commit, the same pinned Chromium revision, the same machine, the same fixture,
measured with the Sunshine contribution enabled and disabled. The absolute value
is context; the delta is the budget.

Restating handoff §1.1 as a measurable rule: *ordinary secure browsing must not
get slower to add a Sunshine feature.* Where a Sunshine surface is itself slow,
the cost must be confined to that surface and paid only by a user who opened it.

Handoff §9.2's own closing sentence is retained with the same force
`docs/SIZE_BUDGET.md` gives to security: **no optimisation may trade page
compatibility, a security boundary, the sandbox, or accessibility for a metric.**
A faster number bought with any of those is a failed budget, not a passed one.

## 2. How a baseline is obtained when the build does not exist

A budget with no baseline is a wish. No native build exists in this wave, so
this section is the part that makes the rest of the document real.

### 2.1 Three stages

| Stage | State | What a budget is |
|---|---|---|
| **B0** | No native build. This wave. | A named metric, a named boundary, a named paired comparison, and a stated regression condition. No number. |
| **B1** | First native build in the release configuration. | Every budget below is measured once, paired, and the result is **recorded as the baseline** in the wave report required by handoff §9.3. |
| **B2** | Every build after B1. | The recorded B1 delta is the gate. A change to it requires a recorded decision, not a re-measurement that happens to be convenient. |

Everything numeric in this document is a **target** or a
**baseline-to-be-taken**, and says which. Nothing here is a measurement.

### 2.2 The baseline is a paired build, not a downloaded browser

The comparison for every delta is the **same commit with Sunshine's
contribution disabled** — a build flag, a feature switch, or an upstream-only
build of the pinned tag from the same toolchain and the same GN arguments.

It is specifically **not** stock Google Chrome, and not a previous Sunshine
release. Stock Chrome differs in PGO profile, branding, API keys, component
updater, and field-trial state; comparing against it measures those differences
and attributes them to Sunshine. `docs/decisions/0002-native-chromium-downstream.md`
already forbids the proprietary inputs that would be needed to make that
comparison fair, which is another way of saying the comparison cannot be made.

### 2.3 What makes a baseline count

A recorded baseline is invalid unless it carries all of:

1. Sunshine commit and the `CHROMIUM_REVISION` from `config/chromium.version`;
2. OS and version, CPU architecture, RAM, and whether the machine was otherwise
   idle;
3. the GN configuration, matching `docs/SIZE_BUDGET.md`'s release configuration;
4. field-trial and feature-flag state, frozen and listed — including the two
   split flags in `chrome/browser/ui/tabs/features.h` whose defaults
   `docs/TAB_WORKSPACE_SPLIT_CONTRACT.md` §6 records as an open product
   decision;
5. the profile fixture: clean profile, or a named fixture with its tab count,
   workspace count, and workspace distribution;
6. network state: offline, or a recorded local fixture. A budget measured
   against the live web measures the web;
7. run count, and both the median and a stated high percentile. A single run is
   an anecdote;
8. the paired value from the Sunshine-disabled build, taken in the same session
   on the same machine.

A measurement reported without its pair is not a result and does not update a
baseline.

### 2.4 Tolerance is fixed before the delta is seen

A tolerance chosen after looking at the delta is not a gate. Before B1, each
budget below states its tolerance as a **shape**, not a number:

- **Zero-tolerance (pass/fail).** An invariant that is either held or violated.
  These need no baseline at all and can be implemented as browser tests the day
  the code exists.
- **Noise-floor.** The delta must be indistinguishable from zero at the
  measured run-to-run noise of the harness. The noise floor is itself measured
  at B1 by running the Sunshine-disabled build against itself with the same
  fixture and run count; that number is recorded alongside every budget it
  governs.
- **Stated fraction.** A delta permitted up to a fraction of the measured
  upstream median, where the work is genuinely new and cannot be zero. The
  fraction is proposed at B0, in this document, and confirmed or amended once at
  B1 with a recorded reason.

## 3. Chromium's own instruments — use these, invent nothing

Chromium has spent years building the measurement infrastructure for every
metric handoff §9.2 asks for. Sunshine adds one counter of its own (§4, PB-1)
and otherwise reads upstream's. Paths and names below were read from the pinned
tag on 2026-08-17.

| What §9.2 asks for | Upstream instrument at `152.0.7977.42` | Names |
|---|---|---|
| Browser launch | `components/startup_metric_utils/browser/startup_metric_utils.h` and its implementation | `Startup.BrowserMessageLoopStartTime`, `Startup.BrowserWindowDisplay`, `Startup.BrowserWindow.FirstPaint`, `Startup.BrowserMessageLoopFirstIdle` |
| First remote-content presentation | same | `Startup.FirstWebContents.NonEmptyPaint3`, `Startup.FirstWebContents.FirstContentfulPaint`, `Startup.FirstWebContents.MainNavigationStart` / `.MainNavigationFinished` |
| Cold vs warm classification | same | `Startup.Temperature` and its `.Cold` / `.Warm` / `.Lukewarm` suffixes |
| Restoration time | `chrome/browser/sessions/session_restore_stats_collector.h` | `SessionRestore.ForegroundTabFirstPaint4`, its `.NTabs` variants, and its `FinishReason` enum |
| Restore correctness after restart | `chrome/browser/sessions/session_restore.cc` | `SessionRestore.TabDiffAfterRestart.Normal`, `SessionRestore.WindowDiffAfterRestart.Normal` |
| Tab switching | `content/browser/renderer_host/visible_time_request_trigger.h` with `third_party/blink/public/common/page/content_to_visible_time_request.h` | the browser process stamps `event_start_time` when the contents is about to become visible; the compositor reports presentation. `VisibleTimeEvent::TabSwitchReason` carries `destination_is_loaded` and `had_saved_frame_at_start` |
| Memory with 10/30 tabs | `chrome/browser/metrics/process_memory_metrics_emitter.h`, over dumps from `base/trace_event/memory_dump_manager.h` | per-process browser/renderer/GPU memory |
| Tab state transitions | `chrome/browser/ui/tabs/tab_strip_model_stats_recorder.h` | active/inactive/closed transition counts, the population a discard budget is drawn from |
| Freeze and discard policy | `chrome/browser/performance_manager/policies/discard_eligibility_policy.h`, `chrome/browser/performance_manager/policies/page_discarding_helper.h`, `chrome/browser/resource_coordinator/tab_manager.h`, `chrome/browser/resource_coordinator/tab_lifecycle_unit_source.h`, `components/performance_manager/public/decorators/tab_page_decorator.h`, `components/performance_manager/public/features.h` | discard reason and eligibility, which visibility drives |
| Harness for repeatable desktop runs | `tools/perf/benchmarks/system_health.py` | `system_health.common_desktop`, `system_health.memory_desktop`; `tools/perf/benchmark.csv` also lists `memory.desktop` and `power.desktop` |
| Sunshine's own counters | `base/metrics/histogram_macros.h` | the only sanctioned way to emit one |

Two findings from reading that infrastructure, both of which shape the budgets
below:

- **There is no desktop startup benchmark at the pinned tag.**
  `tools/perf/benchmark.csv` lists `startup.mobile` and
  `system_health.webview_startup` and nothing else with "startup" in its name.
  Desktop startup is measured by the `Startup.*` UMA family over many real
  launches, not by a Telemetry benchmark. A Sunshine startup budget is therefore
  a UMA comparison over N paired launches (§4, PB-4). Building a Telemetry
  startup benchmark for desktop would be constructing infrastructure upstream
  deliberately does not have.
- **Tab-switch latency is already stratified upstream and must not be
  averaged.** `TabSwitchReason` records whether the destination was loaded and
  whether a saved frame existed at the start. Those two bits separate "switched
  to a live tab" from "switched to a tab Chromium had discarded and is now
  reloading". Collapsing them into one mean is the single easiest way to
  produce a workspace-switch number that blames Sunshine for Chromium correctly
  reclaiming memory (§4, PB-3).

## 4. What Sunshine can regress

Six budgets. Each states what is measured, at what boundary, against what
baseline, and what counts as a regression.

`PB-` is the prefix for this document's budgets, and the ordinals are unchanged:
the budget written `P1` through `P6` before this revision is `PB-1` through
`PB-6` now, and the sub-budgets of `PB-2` keep their letters. The rename exists
because a bare `P` number cannot be told apart from the P0/P1/P2 decision
priority every contract uses — including §9 of this document — so a budget could
not be cited durably or counted by `scripts/trace_invariants.py`. **A `P` number
in this document is always a decision priority; a budget is always `PB-`.**

Handoff §9.2 names six measurements. They are covered here as follows, so that
none is left implied:

| §9.2 measurement | Budget |
|---|---|
| Browser launch | PB-4 |
| First remote-content presentation | PB-4 |
| Tab switching | PB-3. A plain tab switch is Chromium's and is not budgeted; it is PB-3's baseline |
| Memory with 10 / 30 tabs | PB-2a and PB-4 fixture (c); panel registration memory is PB-1 / D4 |
| CPU while idle | PB-5 |
| Restoration time | PB-4 |

### PB-1 — Side panel registration and mount

**Already budgeted.** `docs/SIDE_PANEL_CONTRACT.md` §4.6 defines detections
D1–D7 and §12 criteria SPA-1 to SPA-8; those are the panel performance
contract and are not restated, renumbered, or amended here.

What this document adds is only what §4.6 defers to §9.2:

- **D1's mount counter is pass/fail at zero.** Five windows plus a thirty-tab
  restore with no panel touched must produce a mount count of zero. That is a
  correctness gate with no tolerance, needs no baseline, and is implementable as
  a browser test on the first day panel code exists. It is the cheapest budget
  in this document and the one most likely to catch a real regression.
- **D4's registration cost is statistical and needs §2.** Window-creation time
  and per-window memory with Sunshine panel registration enabled versus disabled
  is exactly the paired comparison of §2.2. Its baseline is taken at B1 and its
  tolerance is noise-floor: registration is meant to be one small object per
  entry, so any delta the harness can resolve is a finding, not a cost.
- **D4 cites "§9.2" as where its baseline is recorded.** This document is that
  place.

### PB-2 — The workspace projection and Chromium's lifecycle policy

`docs/TAB_LIFECYCLE_CONTRACT.md` §6.4 states the mechanism: Chromium decides
freezing and discarding from visibility, and Sunshine changes what is visible.
That makes the projection a lifecycle policy change whether or not it intends to
be one, in two opposite directions.

**PB-2a — Hidden-workspace tabs must actually be background tabs.**

| | |
|---|---|
| Measured | The count of tabs a window reports visible; and resident memory over a fixture of 30 tabs distributed across three workspaces, versus the same 30 tabs in one workspace |
| Boundary | Visibility as Chromium reads it for lifecycle purposes (`components/performance_manager/public/decorators/tab_page_decorator.h`, `chrome/browser/performance_manager/policies/discard_eligibility_policy.h`); memory via `chrome/browser/metrics/process_memory_metrics_emitter.h` |
| Baseline | Zero-tolerance on the count: exactly one visible tab, or exactly two while a split is open. This is `docs/TAB_LIFECYCLE_CONTRACT.md` TLA-19 and `docs/ADVANCED_TABS_CONTRACT.md` ATA-7 stated as a budget. For memory, the paired Sunshine-disabled build with the same 30 tabs |
| Regression | Any visible count other than 1 or 2. Any implementation that keeps hidden tabs marked visible to make a switch feel faster — that is trading the memory benefit of hiding for latency, and it is the failure §7.6-style "keep it warm" reasoning always produces |

The user-visible consequence is accepted and already stated in
`docs/TAB_LIFECYCLE_CONTRACT.md` §6.4.2: returning to a long-hidden workspace
may reload tabs. That is native behaviour and is not a Sunshine regression.

**PB-2b — Both split panes must be genuinely visible.**

| | |
|---|---|
| Measured | The rate of a timer and of an animation in the **unfocused** pane, and the absence of any freeze or discard transition for a tab in an open split |
| Boundary | Blink's throttling of a hidden or occluded contents, and Chromium's discard eligibility for the same |
| Baseline | Zero-tolerance. The unfocused pane runs at the same rate as the focused one. This is `docs/TAB_LIFECYCLE_CONTRACT.md` TLA-19 and §9's row stating that a frozen or discarded paned tab "must not happen while the split is open" |
| Regression | Any throttling of the unfocused pane, any freeze or discard of a paned tab, any handling of such an event by dissolving the split instead of fixing the visibility |

This budget exists because the failure is user-visible in the worst way: a pane
the user is watching stops updating. It is a scheduling consequence of a layout
decision, which is why it is a performance budget and not only a correctness
rule.

**PB-2c — Discard behaviour must not drift.**

| | |
|---|---|
| Measured | Counts of freeze and discard events over a fixed browsing fixture, and the reason recorded for each |
| Boundary | `chrome/browser/performance_manager/policies/page_discarding_helper.h` and the eligibility policy beside it |
| Baseline | The paired Sunshine-disabled build over the same fixture, with all tabs in one workspace. Target: the only difference is the increase attributable to hidden workspaces in PB-2a |
| Regression | Any Sunshine code that exempts a tab from discard, forces one, or second-guesses a decision — prohibited outright by `docs/TAB_LIFECYCLE_CONTRACT.md` §2 — and any discard count that changes for a reason the workspace distribution does not explain |

### PB-3 — Workspace switch latency

| | |
|---|---|
| Measured | Time from `workspace.switch` dispatch to the first presented frame of the destination tab |
| Boundary | Chromium's content-to-visible instrument (`content/browser/renderer_host/visible_time_request_trigger.h`). A workspace switch ends in a tab activation, so it is measured as a tab switch and by no Sunshine-authored timer |
| Baseline | The same instrument for a plain tab activation, in the same window, on the same build, in the same session. The delta is the projection |
| Tolerance | Stated fraction, proposed at B0 as noise-floor and confirmed at B1: the projection is a pass over the tabs of one window with no I/O, no service lookup, and no navigation, so it should not be resolvable against a tab switch |

Reported in two populations, never one, per §3: switches where
`destination_is_loaded` is true, and switches where it is false. The second
population is a reload of a discarded tab, which is Chromium doing what PB-2a
asked it to do.

Zero-tolerance conditions attached to this budget, each of which is a
correctness invariant elsewhere and a latency defect here:

1. **No persistent write during a switch.** `docs/TAB_LIFECYCLE_CONTRACT.md`
   invariant 3 permits Sunshine session-extra-data writes only at tab insertion
   and at membership change. A write on activation would emit a session command
   on every switch — a durability risk in a file Sunshine is least entitled to
   churn, and a latency cost on the critical path.
2. **Zero tab moves.** `docs/TAB_WORKSPACE_SPLIT_CONTRACT.md` invariant 11: the
   projection hides and shows, it never reorders. A reordering projection does
   not merely cost time; `TabStripModel::MoveTabToIndexImpl` dissolves every
   split it steps through, so a "clustering" optimisation would silently destroy
   user layout. This budget is therefore also a data-loss gate, and it is
   pass/fail: `docs/TAB_WORKSPACE_SPLIT_CONTRACT.md` acceptance already requires
   a session that switches workspaces repeatedly to perform zero moves.
3. **No reload caused by the switch.** Switching away and back must not reload a
   crashed tab or a tab Chromium did not discard
   (`docs/TAB_LIFECYCLE_CONTRACT.md` TLA-22).
4. **Exactly one activation change** per switch, observable once.

### PB-4 — Startup and session restore

This is the path Chromium has spent years optimising and the one Sunshine adds
work to. Sunshine's additions on it are: reading `sunshine_tab_uuid` and
`sunshine_workspace_uuid` from tab session extra-data, reading the active
workspace and per-workspace last-active-tab record from window session
extra-data, reading the profile-scoped workspace catalog once, and building the
projection.

| | |
|---|---|
| Measured | `Startup.BrowserWindowDisplay`, `Startup.BrowserWindow.FirstPaint`, `Startup.FirstWebContents.NonEmptyPaint3`, `Startup.FirstWebContents.FirstContentfulPaint`, and `SessionRestore.ForegroundTabFirstPaint4` |
| Boundary | Upstream's own recorders only. Sunshine starts no stopwatch of its own on this path; `components/startup_metric_utils/browser/startup_metric_utils.h` already stamps every event §9.2 names |
| Baseline | Paired Sunshine-disabled build, same fixture, N launches, **cold and warm reported separately** using `Startup.Temperature`. A sample that mixes temperatures measures the disk cache |
| Fixtures | (a) clean profile, startup set to New Tab; (b) 30-tab restore, all tabs in one workspace; (c) 30-tab restore, 5 tabs in the active workspace and 25 hidden across two others. Fixture (c) is the Sunshine-specific one and the only place the projection's cost is visible |
| Tolerance | Stated fraction, proposed at B0 as noise-floor for (a) and (b). Fixture (c) may differ from (b) only by the projection pass |

Zero-tolerance conditions:

1. **No file Sunshine opens on the startup path other than the workspace
   catalog, read once per profile.** Not once per window, not once per tab.
   Sunshine does not read Chromium session files at all —
   `docs/SESSION_PROFILE_CONTRACT.md` prohibits it, and the extra-data channel
   in `components/sessions/core/session_types.h` is the supported seam.
2. **Projection cost is O(restored tabs)** with no per-tab I/O, no per-tab
   profile-keyed service lookup, and no navigation.
3. **No cost that scales with anything else.** History size, bookmark count,
   download count, and the contents of inactive workspaces must not appear in
   startup cost. `docs/SIDE_PANEL_CONTRACT.md` §4.2 rule 8 states the same shape
   for panel registration.
4. **Hidden workspaces do not create renderers.** Restoring fixture (c) must not
   produce 30 live renderers. This is PB-2a measured on the startup path, and it
   is the largest single memory number Sunshine can move.
5. **No synchronous wait** introduced before first window paint, and no work
   deferred into an idle-load of content a user did not open —
   `docs/SIDE_PANEL_CONTRACT.md` §4.3 names every disguise that failure wears.

The open P1 in `docs/TAB_LIFECYCLE_CONTRACT.md` §14 — on return to a workspace,
restore only the last active tab or all previously loaded tabs — sets both the
restore time in this budget and the memory number in PB-2a. It is a product
decision with a measured consequence, and it should be taken before B1 rather
than discovered by it.

### PB-5 — Idle cost

Sunshine's legitimate idle cost is zero. It runs no timer, no poll, no
background refresh, no idle-triggered work: `docs/SIDE_PANEL_CONTRACT.md` §4.3
and §11 prohibit prewarming and idle loading, `docs/ADVANCED_TABS_CONTRACT.md`
prohibits timed and idle-triggered duplicate scanning, and
`docs/TAB_LIFECYCLE_CONTRACT.md` §5.1 prohibits an automatic refresh timer.

| | |
|---|---|
| Measured | Wakeups and CPU over a fixed idle interval with a 10-tab and a 30-tab fixture, browser focused and unfocused |
| Boundary | OS process accounting, paired against the Sunshine-disabled build; `power.desktop` in `tools/perf/benchmark.csv` is the upstream harness if a repeatable one is wanted |
| Baseline | Zero-tolerance in principle: any Sunshine-owned repeating task is a defect regardless of its measured cost |
| Regression | The existence of the task, not its size |

The cheap form of this budget is a source-level assertion that no Sunshine-owned
repeating timer or idle task exists. It is stricter than a CPU measurement, it
does not need a baseline, and it can be written before a native build exists.

#### PB-5a — The one thing that may animate, and why it is not an exception

**Amended by the owner** to permit an animated New Tab background. The
amendment is written as a boundary rather than a carve-out, because a budget
that gains its first "except" stops being a budget.

**What PB-5 is actually about is work that continues when nobody is looking.**
Every prohibition above shares that shape: a timer fires in a background tab, a
poll runs in a minimised window, a prewarm loads a panel no one opened, an idle
callback runs precisely because the user has stopped. None of them can be seen
at the moment they cost something, which is why their existence rather than
their size is the regression — nobody is present to judge the size.

An animation of a surface the user is looking at is not that. It costs while it
is watched, it stops when it is not, and it is absent unless someone asked for
it. Those three properties are the boundary, and all three are required
together:

| | Required of any Sunshine-permitted animation |
| --- | --- |
| **1. Visible-only** | It runs only while its surface is the visible tab in a non-occluded window. Hidden, occluded, background-tab and minimised states run nothing. |
| **2. Opt-in** | It does not exist unless the user supplied the asset. A build with none configured has PB-5's original idle cost, unchanged and still zero. |
| **3. Self-contained** | The animation is carried by the asset. Sunshine owns no timer, no frame callback, and no repeating task driving it. |

**Only the New Tab background qualifies today**, and only through the user's own
image. No other surface gains an animation by this amendment, and one that
wanted it would need its own row here rather than an appeal to this one.

**Video is excluded, by the owner's decision: it is not needed.** The animated
image formats do what this feature is for.

**The exclusion was briefly lifted and then withdrawn, and the reasons are
worth keeping straight.** While the amendment was being written, two of the
three grounds originally recorded here did not survive re-reading: the
"codec-licensing question" was a real decision about H.264 written as a claim
about video as such (`docs/decisions/0004-media-codecs.md` leaves proprietary
codecs off, and VP9, AV1 and Opus, which ship, are royalty-free), and an audio
track is proven silent by `muted`. **Only the third ground stands** — a media
pipeline and a video decoder instance per New Tab, which no image needs and
which nothing has measured.

Neither of those corrections is a reason to reopen this. The capability was
cancelled because it is not needed, which is a decision that does not depend on
what it would have cost. What the corrections prevent is this section being
re-read later as three reasons when it only ever had one.

**No code was written.** No format detection, no serving path, no media
element.

**What stays forbidden, and is not weakened.** Property 3 is the load-bearing
one. `scripts/verify_no_interposition.py` continues to reject
`animation-iteration-count: infinite` in Sunshine-authored CSS, and that
prohibition is *not* relaxed here: a CSS animation Sunshine writes is Sunshine
deciding to animate forever, which is a repeating task it owns. An image that
loops is the user's asset animating itself, and Sunshine's own source contains
no repetition at all. The guard is unchanged because the permitted feature does
not need the forbidden spelling — **if an implementation ever finds that it
does, that is evidence it has left this boundary, not a reason to widen the
guard.**

| | |
|---|---|
| Measured | PB-5's idle fixture, twice: once with no background asset configured, once with an animated one, in each case with the New Tab hidden behind another tab |
| Baseline | The no-asset run must equal PB-5's original zero. The hidden-tab run with an asset configured must equal the no-asset run |
| Regression | An animated asset that costs anything while its surface is not visible, or any Sunshine-owned timer or frame callback found driving it |

Both are pass/fail invariants of the kind §7 describes, not statistical deltas:
neither needs B1, and the second is decidable the first time anyone opens a
second tab.

#### PB-5b — The clock, which is the second thing that may repeat

**Amended by the owner** to permit a clock on the New Tab. It gets its own row
because PB-5a says it must: *"No other surface gains an animation by this
amendment, and one that wanted it would need its own row here rather than an
appeal to this one."*

**PB-5a cannot cover this, and the reason is structural rather than
procedural.** Its third property is that the asset carries the animation and
Sunshine owns no timer. A clock has no asset. There is nothing for the
repetition to live in except Sunshine's own code, so the property is not
merely unmet — it is inapplicable.

**There is also no spelling that avoids the timer, and that was checked before
this row was written.** A `setTimeout` that re-arms itself is a repeating task
wearing a permitted name; `scripts/verify_no_interposition.py` says in its own
comment that it cannot tell the two apart, and PB-5a's closing paragraph says
that needing the forbidden spelling is evidence of having left the boundary
rather than a reason to widen the guard. So the honest move is a row, not a
`setTimeout`.

| | Required of the clock |
| --- | --- |
| **1. Visible-only** | It runs only while the New Tab is the visible tab in a non-occluded window. Hidden, occluded, background-tab and minimised states run nothing. Identical to PB-5a's first property, and for the same reason. |
| **2. One wakeup per displayed change** | Minutes, not seconds, and aligned to the minute boundary. A clock showing minutes that wakes every second is fifty-nine wakeups spent to display nothing new. |
| **3. Bounded and cancelled** | Exactly one timer, cancelled by every path out — hidden, and torn down. Nothing else in Sunshine may repeat by appeal to this row. |

**Unlike PB-5a's first property, this one is not about focus.** The clock keeps
running while the window is unfocused, because that is when it is most likely
to be read: `docs/NEWTAB_BACKGROUND_CONTRACT.md` §3a rests the page after focus
leaves, and a clock that vanished at that moment would be a clock that hides
whenever you glance at it. Visible and unfocused is watched; hidden is not.

| | |
|---|---|
| Measured | PB-5's idle fixture with the New Tab visible and unfocused, and again with it hidden behind another tab |
| Baseline | The hidden run must equal PB-5's original zero. The visible run may exceed it by one wakeup per minute and by nothing else |
| Regression | Any wakeup while the surface is hidden; any rate above one per minute; any second repeating task added under this row |

**What this costs, stated rather than absorbed.** PB-5's own words are
"Sunshine's legitimate idle cost is zero" and "the existence of the task, not
its size". That sentence is no longer true without qualification, and this row
is the qualification. One wakeup per minute on one visible surface is the whole
of it, and the third property exists so that the next feature wanting a timer
has to come back here rather than point at this one.

### PB-6 — Sunshine WebUI surfaces

A Sunshine-contributed panel or WebUI surface has its own render cost once it
exists. At B0 no such surface exists, so this budget is a placeholder with a
stated trigger rather than a metric: **when the first Sunshine WebUI surface is
built, it gains a row here** covering its mount-to-first-paint time and its
memory while mounted, measured against the panel-registration baseline of PB-1.

Two constraints already bind it and are not restated: the panel must be usable
at the minimum panel width (`docs/SIDE_PANEL_CONTRACT.md` §7), and the command
palette's responsiveness with a hung renderer is already an acceptance criterion
in `docs/COMMAND_PALETTE_CONTRACT.md`.

## 5. The measurement contract

| Requirement | Rule |
|---|---|
| Configuration | The release configuration of `docs/SIZE_BUDGET.md`. Debug and component builds do not produce a result |
| Pairing | Every result carries its Sunshine-disabled pair from the same session (§2.2) |
| Runs | A stated N, with median and a stated high percentile. Never a single run |
| Stratification | Cold and warm startup separately; loaded and discarded tab switches separately |
| Provenance | Everything in §2.3 |
| Reporting | Into the wave report required by handoff §9.3, which already requires tests run and results. A performance result is a test result |
| Claims | A budget with no recorded measurement is reported as **NOT RUN**, never as passing |

## 6. Deliberately not budgeted

Silence here would be read as oversight by a later wave. It is not.

| Not budgeted | Why | What would change that |
|---|---|---|
| Page load, script execution, layout, paint, compositing, network | Blink, V8, and the network stack are unmodified. A Sunshine number would be a Chromium number that drifts at every roll, and would invite "optimising" upstream code the patch budget in `docs/decisions/0002-native-chromium-downstream.md` forbids touching | Sunshine patching any renderer or network path |
| Speedometer, JetStream, MotionMark, and every content benchmark | Same reason. Publishing a score would claim credit or accept blame for work that is not Sunshine's | The same |
| Absolute startup seconds and memory megabytes | No build exists. A number invented now is a wish (§2.1). They arrive at B1 as recorded baselines | Reaching B1 |
| Installer size, bundle size, profile size, cache growth | `docs/SIZE_BUDGET.md`. Duplicating them here would create two owners for one number | Nothing. The seam named under *Status and scope* is the only crossing |
| Extension performance | `docs/EXTENSION_COMPATIBILITY_GATE.md` owns extension behaviour. An extension's cost is the extension's, and Sunshine neither privileges nor throttles it | Sunshine changing extension dispatch, which it does not |
| GPU time, frame rate, and battery | Sunshine adds no continuous animation and no rendering. `docs/DESIGN_SYSTEM_CONTRACT.md` already bounds motion. `power.desktop` exists upstream if this becomes real | Any Sunshine surface that animates continuously or composites its own layer |
| Chromium's own UI responsiveness — tab strip, omnibox dropdown, menus | Unmodified surfaces. Sunshine registers commands; it does not repaint them | A downstream patch to a Chromium view |
| Cross-window and multi-profile scaling | `docs/WORKSPACE_NATIVE_INTEGRATION_MAP.md` fixes the MVP at one profile and one window. The five-window case that matters is already fixed by `docs/SIDE_PANEL_CONTRACT.md` §4.6 D1 | The open P1 on workspaces spanning windows |
| Speed of `scripts/workspace_model.py` | It is a design model and a test fixture, not shipping code. Its runtime says nothing about the browser | It never ships; nothing changes this |
| A performance dashboard or continuous perf bot | Premature before B1, and standing infrastructure for a product with no build is cost without signal. §5's wave report is the recording mechanism until then | Enough B2 history to make a trend meaningful |

## 7. Gating and the upstream roll

Two classes of gate, and they behave differently:

- **Pass/fail invariants** — PB-1's D1 mount counter at zero, PB-2a's
  visible-tab count, PB-2b's unfocused-pane rate, PB-3's zero writes and zero
  moves, PB-4's file-read and scaling rules, PB-5's absence of a repeating task,
  PB-5a's two runs — no-asset idle equal to zero, and hidden-tab idle equal to
  the no-asset run.
  These need no baseline, fail CI outright, and are implementable as browser
  tests as soon as the code exists. They are the majority of this document on
  purpose.
- **Statistical deltas** — PB-1's D4, PB-2a's and PB-2c's counts, PB-3's
  latency, PB-4's startup and restore times. These require B1 and the provenance
  of §2.3.

At an upstream roll, **baselines are re-taken, not carried**. A roll moves the
absolute number for reasons that are upstream's; the Sunshine *delta* is the
thing that must hold. A roll that changes an absolute number is an upstream
finding to be understood and, if necessary, raised upstream — not something
Sunshine compensates for with a downstream patch. This is the same response
`docs/SIDE_PANEL_CONTRACT.md` §4.6 D6 and `docs/SESSION_PROFILE_CONTRACT.md`'s
roll gate already require, and it applies to performance for the same reason:
compensating downstream creates a second owner of upstream behaviour.

## 8. Corrections and gaps in shipped documents

| Document | Finding |
|---|---|
| `docs/SIDE_PANEL_CONTRACT.md` §4.6 D4 and SPA-8 | Both defer their baseline to "§9.2", which says only "set initial budgets during implementation and refine after baseline profiling" — a pointer to an instruction, not to a place. This document is the place. When that contract is next revised, the pointer should read `docs/PERFORMANCE_BUDGET.md`. No behaviour changes; only the reference resolves |
| Handoff §9.2, "first remote-content presentation" | Names no instrument, and at the pinned tag there are several that could be meant. §3 resolves it to `Startup.FirstWebContents.NonEmptyPaint3` and `.FirstContentfulPaint` |
| Handoff §9.2, "memory with 10/30 tabs" | Does not state the workspace distribution, which is the only variable that makes the number Sunshine's rather than Chromium's. PB-2a and PB-4 fixture (c) supply it |
| Handoff §9.2, "browser launch" | Does not distinguish cold from warm. `Startup.Temperature` exists at the pinned tag precisely because the distinction changes the number more than any product decision would |
| `docs/SIZE_BUDGET.md` and the handoff | The size baseline is to be established by "the first native macOS release build"; the handoff's primary target is Windows desktop. Two documents, two reference platforms. This document does not choose; §9 raises it |
| `scripts/verify_pinned_upstream.py` | ~~Its `CITATION` regex does not match `tools/...` or `.csv`, so the `tools/perf/...` citations in §3 are not CI-checked.~~ **Fixed.** This was true when written and was the finding that prompted the fix: the regex now covers `tools` and `build`, and the `csv`, `json`, `gn`, `gni` and `xml` suffixes. Every path this document cites is CI-checked at the pinned revision |

## 9. Open decisions for the product owner

| Priority | Decision | Required by |
|---|---|---|
| P1 | Is a statistical budget a hard CI gate or an investigation threshold? `docs/SIZE_BUDGET.md` chose investigation thresholds explicitly; consistency argues for the same here, but the pass/fail invariants of §7 are hard gates either way. Answering this decides what B1 turns on | Before B1 |
| P1 | Which platform is the reference for B1? `docs/SIZE_BUDGET.md` names the first native macOS release build; the handoff targets Windows desktop. A baseline on one platform does not gate the other | Before B1 |
| P1 | On return to a workspace whose tabs were discarded, restore only the last active tab or all previously loaded ones? Already open as P1 in `docs/TAB_LIFECYCLE_CONTRACT.md` §14; it sets the PB-4 restore number and the PB-2a memory number | Stage 3 workspace release |
| P2 | Does Sunshine emit UMA at all in shipping builds, or are these budgets lab-only? `docs/SIDE_PANEL_CONTRACT.md` §4.6 D1 assumes a session histogram exists; `docs/SESSION_PROFILE_CONTRACT.md` constrains what any telemetry may contain. The two are compatible, but the question has not been answered | Before the first Sunshine histogram is added |
| P2 | Is the Sunshine feature-flag set frozen for a measurement run, and which upstream defaults does Sunshine change? The two split flags in `chrome/browser/ui/tabs/features.h` are already open in `docs/TAB_WORKSPACE_SPLIT_CONTRACT.md` §9, and `kVerticalTabsLaunch` is an inherited default per `docs/WORKSPACE_NATIVE_INTEGRATION_MAP.md`. Each changes the baseline | Before B1 |

## 10. Not verified

- No Chromium checkout, configuration, compilation, or link of the pinned
  revision was performed. **NOT RUN.**
- No Sunshine or Chromium binary was launched on any platform. **NOT RUN.**
- No performance, memory, CPU, latency, or startup measurement of any kind
  exists. Every budget in §4 is a procedure and a comparison; not one is a
  number. **NOT AVAILABLE.**
- No baseline has been taken. B1 has not occurred, and no tolerance in §2.4 has
  been resolved to a value.
- The upstream paths in §3 were confirmed to exist at
  `refs/tags/152.0.7977.42` by retrieving each from the GitHub mirror on
  2026-08-17, and the histogram names, the `Startup.Temperature` enumeration,
  the `SessionRestore.ForegroundTabFirstPaint4` finish-reason enumeration, the
  `VisibleTimeEvent::TabSwitchReason` fields, and the benchmark names in
  `tools/perf/benchmark.csv` were read from those files. Their **runtime**
  behaviour is unverified: no code was executed and no histogram was observed
  being emitted.
- The absence of a desktop startup benchmark at the pinned tag is read from
  `tools/perf/benchmark.csv`, which is an autogenerated file; it is evidence
  about that revision only.
- No command was registered and none is proposed by name here.
  `first_party/commands.json` remains the only authoritative list.
- No downstream patch, first-party module manifest, or command-registry change
  accompanies this document.

## 11. Completion gate

This contract is complete when reviewed. Handoff section 9.2 is complete when a
native build exists in the release configuration, every pass/fail invariant in
§7 is implemented as a test and passing, B1 has been taken and recorded for
every statistical budget in §4 with the provenance of §2.3, and the tolerances
of §2.4 have been resolved to values with recorded reasons.
