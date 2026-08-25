# Project Lessons

Repository-specific memory for reducing rediscovery and repeated mistakes.

Do not copy this file into unrelated projects.

## Conflict Hotspots

### 2026-08-17 — `scripts/workspace_model.py` is now a shared dependency
Area: compile-free state models.
Evidence: `scripts/split_view_model.py` imports `NativeTab`, `canonical_uuid`,
and `WorkspaceModelError` from it. Any later split, archive, or projection model
will import the same symbols.
Impact: parallel edits to this file will collide and can silently change the
failure contract of every importer.
Recommended future behavior: treat it as a serialized hotspot. Give one Mission
Pack exclusive write ownership per wave; other packs read only.
Confidence: high.

## Build / Compile Lessons

- None recorded yet.

## UX / Runtime Lessons

### 2026-08-17 — The patch stack is WebUI, so visual verification never needed a build
Area: New Tab surface.
Evidence: all three upstream targets are configuration or WebUI resources; no
C++. Rendering the wordmark in an ordinary Chromium found a Major RTL defect
(-10.087px off centre, exactly one letter-space) that every static gate passed.
Impact: three waves reported visual verification as blocked when the only
Sunshine UI surface was renderable the whole time.
Recommended future behavior: before recording a visual gate as blocked, check
what the patch actually touches. Resource-only changes are verifiable now;
only C++ changes wait for the native build.
Confidence: high.

### 2026-08-17 — A logical property is wrong when the content never flips
Area: New Tab surface.
Evidence: `padding-inline-start` compensated the trailing letter-space in LTR and
doubled the error in RTL, because the wordmark text is always Latin LTR while the
property followed the UI direction.
Impact: silent RTL layout defect invisible to marker-based guards.
Recommended future behavior: when a downstream element must not mirror, pin its
own `direction` rather than switching to physical properties; the intent stays
readable at upstream-roll review.
Confidence: high.

## Build / Compile Lessons

### 2026-08-17 — This session cannot build Chromium, and that is not a resource limit
Area: build environment.
Evidence: the agent runs in an ephemeral cloud Linux container, not on the user's
desktop. `chromium.googlesource.com` returns CONNECT 403 on three retries and
over the git protocol; CIPD is unreachable; writable disk is empirically between
20GB and 30GB against an 80-120GB need. Only the clang CDN is reachable.
Impact: no local compile, and Windows gates could not be satisfied here even with
more disk, because a Linux build is not the product target.
Recommended future behavior: do not re-run this investigation. Route native
builds to the self-hosted Windows runner in
`.github/workflows/native-chromium-windows.yml`. Offline structural checks such
as `git apply --numstat` are the local substitute.
Confidence: high.

## Domain Risk Lessons

### 2026-08-17 — A guard that skips specifications certifies a false clean tree
Area: architecture enforcement.
Evidence: `scripts/verify_architecture.py` ignored `docs/`, so it passed for
months while `docs/SUNSHINE_OS_STAGE_1_TO_3_IMPLEMENTATION_HANDOFF.md` still
specified a wrapper-runtime process model, source layout, and start prompt that
contradicted `.ai/PROJECT_CONTEXT.md`.
Impact: a worker starting from the handoff would have rebuilt the architecture
the repository believed it had deleted, with every automated gate green.
Recommended future behavior: an architecture rule must be enforced over the
documents that direct implementation, not only over code. When a rule is added
to project context, check which file a worker would actually read first.
Confidence: high.

### 2026-08-17 — Removing an architecture is not deleting the word for it
Area: architecture enforcement.
Evidence: the same names appear in prohibitions, in the guard's marker list, in
the CI job name, and in historical reports. Deleting those would remove the
mechanism that keeps the runtime out.
Impact: an over-broad purge would silently reopen the door it was meant to close.
Recommended future behavior: separate design carried forward from rules that
forbid it. Remove precedent, specification, and API names; keep prohibitions,
guards, and immutable run history.
Confidence: high.

### 2026-08-17 — A borrowed validator can silently break a fail-closed promise
Area: compile-free persistence models.
Evidence: `restore_layout` promises never to raise and recovers from
`SplitViewError`, but it reused the workspace UUID validator, which raises
`WorkspaceModelError`. A malformed persisted UUID would have escaped into native
restore instead of falling back to one pane.
Impact: the documented corruption fallback would not have run in exactly the case
it exists for.
Recommended future behavior: when a function is specified as "never raises",
wrap every borrowed helper into that module's own error family, and prove the
fallback through the public entry point rather than the strict parser.
Confidence: high.

## Strategy Observations

### 2026-08-17 — A rule stated in two documents is a rule with no owner
Area: architecture enforcement.
Evidence: the command-first rule was declared non-negotiable, but the command
list lived as prose tables in two documents. They drifted: the handoff kept a
split-view `toggle` command months after the contract replaced it with open,
swap, and close. No gate could see it.
Impact: workers reading either document would have built a different command
set, and four planned features all invoke commands.
Recommended future behavior: when a rule names a set of things, give the set one
machine-readable home and let documents reference it. Check drift in one
direction only — documents may not name what does not exist — because requiring
the reverse forces back the duplication being removed.
Confidence: high.

### 2026-08-17 — Look for enforcement that already exists before adding more
Area: architecture enforcement.
Evidence: "one authoritative implementation per command" needed no new
mechanism. Module entrypoint targets were already globally unique, so declaring
a command as a `native_command` entrypoint made the rule enforceable by reusing
the existing check.
Impact: a smaller validator and one fewer parallel registry to keep consistent.
Recommended future behavior: before writing a new guard, look for an invariant
the repository already enforces that the new rule can be expressed in terms of.
Confidence: medium.

### 2026-08-17 — Write the failure-injection test before the defensive guard
Area: model implementation.
Evidence: the workspace minimum-count guard in `close_workspace_atomic` was
unreachable; an earlier destination check already rejected the only input that
could have reached it. The test written for it failed and exposed the dead
branch.
Impact: an untestable branch reads as a safety property while guaranteeing
nothing.
Recommended future behavior: require a reaching test for each guard. If no input
reaches it, delete the guard and assert the behavior that is actually
guaranteed.
Confidence: medium.

### 2026-08-17 — Replacing an upstream element means sweeping every reference to it
Area: downstream patch stack.
Evidence: `0002-sunshine-new-tab.patch` replaced `<ntp-logo id="logo">` in the
template and changed nothing else. `app.ts` referenced the logo in four places.
One was fatal (`lit-element-invalid-interface` failed the first build that ever
reached compilation); the other three were silent -- an unused type import, an
inert allowlist that would have removed the wordmark from the accessibility tree
whenever the composebox opened, and a click metric that would have stopped
recording.
Impact: the visible failure was the least damaging of the four. Fixing only what
CI names would have shipped the other three.
Recommended future behavior: when a patch removes or renames an upstream DOM id,
element or symbol, grep the whole owning component for the old name and decide
each hit explicitly -- carry it over, or drop it on purpose. Verify against the
pinned sources, not from memory.
Confidence: high.

### 2026-08-17 — Check a token against the file that defines it, not one that uses it
Area: verification design.
Evidence: a CI step was added asserting `--color-new-tab-page-primary-foreground`
appears in `app.css`. It does not, at any revision: Chromium emits
`--color-new-tab-page-*` from the colour IDs in `chrome_color_id.h` and serves
them through `chrome://theme`. `kColorNewTabPagePrimaryForeground` exists at
152.0.7977.42, so the check would have failed the build on a valid token.
Impact: a guard that is wrong about its evidence is worse than no guard; it
spends the team's trust and pushes toward "fixing" correct code.
Recommended future behavior: before asserting a dependency exists, establish
where that kind of dependency is *defined*. Absence from a consumer is not
absence. Prove the check fails for the right reason before relying on it.
Confidence: high.

### 2026-08-17 — A build tool's summary line is not its diagnostic
Area: build pipeline.
Evidence: the first build to reach compilation ran 17.5 minutes, completed
11,820 of 66,739 steps, and reported the failure in full as `1 steps failed:
exit=1`. siso writes the failing command and compiler output to
`out/Sunshine/siso_output`, which stays on the runner. The cause was
undiagnosable from CI's only artefact until the failure path was changed to dump
that file; the very next run named the target, the file and the error.
Impact: one wasted cycle per failure, and a standing temptation to guess.
Recommended future behavior: when adopting a build tool, find out where it puts
failure detail and surface it from the failure path before the first real
failure. Treat "the log does not say why" as a defect in the pipeline.
Confidence: high.

### 2026-08-17 — Verify an environment's reach per host, not once
Area: execution environment.
Evidence: `chromium.googlesource.com` is refused by egress policy (proxy
`connect_rejected`, 403 to CONNECT), which was correctly reported as blocking.
The conclusion "this session cannot read pinned upstream sources" did not follow:
`raw.githubusercontent.com` serves the same revision and is reachable. That
single fact turned an open question into a resolved one and let every
network-dependent CI check run locally while hosted runners were unavailable.
Impact: an over-broad capability claim stalls work that is actually possible.
Recommended future behavior: state blocked *hosts*, not blocked *capabilities*,
and look for another host serving the same artefact before recording a blocker.
Confidence: high.

### 2026-08-17 — Distinguish "the job failed" from "the job never ran"
Area: CI triage.
Evidence: four architecture-guard runs failed in 2-3 seconds with `runner_id: 0`,
no steps, 0 ms billable and no downloadable log, across two commits and a manual
re-run, while the self-hosted build ran normally on the same commits. That
signature is runner allocation, not a test result.
Impact: treating it as a code failure invites speculative fixes to code that was
never executed; treating it as flake invites endless re-runs.
Recommended future behavior: before diagnosing a red check, confirm it executed --
duration, assigned runner, recorded steps, billable time. Zero on all four means
the answer is outside the repository.
Confidence: high.

### 2026-08-17 — Check what the pinned revision already ships before designing it
Area: domain ownership.
Evidence: Sunshine's split-view model re-derives Chromium's native split tabs,
which exist at the pinned tag as `SplitTabVisualData`, `SplitTabData`,
`SplitTabCollection` and `MultiContentsView` -- down to the same default ratio of
0.5 and the same two orientations. The duplication was undetectable from the
repository alone, because nothing here recorded what upstream had gained.
Impact: a shipped model, a module, three registered commands and a contract all
rest on work Chromium already did. ADR 0002 says to use Chromium's tabs.
Recommended future behavior: before contracting a browser feature, retrieve the
pinned revision's own headers for it. Absence of a feature in this repository is
not evidence of absence upstream, and Chromium gains features between pins.
Confidence: high.

### 2026-08-17 — Name a field for what it does, or it will be believed
Area: command registry.
Evidence: the registry field called `guard` holds, for every Sunshine-owned
command, the model function that performs the operation -- it is called with full
execution inputs and refuses by raising. Two waves read the name and assumed a
side-effect-free predicate. One of them recorded "commands take no parameters" as
a project fact; three of the five guards already require undeclared arguments.
Impact: a palette rendering 27 rows by consulting guards would execute up to 27
operations. The mistaken fact was then propagated into a wave report.
Recommended future behavior: when a schema field is introduced, assert its
contract in the validator, not only its resolvability. `validate_commands.py`
checked that each guard resolved and was callable, which every operation also
satisfies.
Confidence: high.

### 2026-08-17 — A parallel wave is the cheapest adversarial review available here
Area: execution strategy.
Evidence: cross-agent review has been NOT AVAILABLE in every wave. Four workers
given independent contracts found, between them, three defects in already-shipped
work that Manager review had passed: the split-tabs duplication, the guard
misnaming, and a section stating no commands were registered in the same wave
that registered eleven.
Impact: the defects were found by workers reading shipped material as input to
their own task, not by anyone reviewing it.
Recommended future behavior: give each worker an explicit instruction to report
anything wrong in the repository content it reads, and treat that channel as the
review the process otherwise lacks.
Confidence: medium.

### 2026-08-17 — A guard that cannot fail is not a guard
Area: verification design.
Evidence: three tools built today each caught something on their first run only
because they were written with injected-violation tests. The design-system check
found `font-weight: 650` outside the allowed set and a fluid band the
declaration never stated. The invariant tracer caught two identifiers invented
by the Manager, and separately was found to be counting its own test fixtures as
real enforcement. The surface check was found to pass when the class it guards
was deleted, because the identifier survived in type annotations.
Impact: every one of those would have shipped as a green check asserting nothing.
Recommended future behavior: for each rule, write the input that must make it
fail before trusting the input that makes it pass. Assert definitions, not names.
Confidence: high.

### 2026-08-17 — Count what is enforced, not what is declared
Area: contract hygiene.
Evidence: twenty-nine contracts declared 142 numbered invariants against zero
enforced. Nothing was wrong with any individual document; the ratio simply
compounded, because a wave that writes a contract is faster than one that writes
a check. Ten criteria the contracts had themselves marked offline-decidable sat
unimplemented until someone measured the gap.
Impact: a declared invariant reads like a guarantee, and a set of them reads like
a verified system.
Recommended future behavior: keep the enforced count visible and ratcheted. When
a contract declares a criterion it calls offline-decidable, implementing it is
the next wave's work, not a later one's.
Confidence: high.

### 2026-08-17 — An identifier a tool cannot cite cannot be counted
Area: contract hygiene.
Evidence: criteria numbered as bare ordinals -- `12.9`, `13`, `14.9` -- have real
checks that cannot be tracked, and `PERFORMANCE_BUDGET`'s budgets P1..P6 collide
with the P0/P1/P2 priority labels every contract uses, so admitting that family
would turn every priority label into an invariant.
Impact: enforcement exists and is invisible, which is indistinguishable from
absence when planning.
Recommended future behavior: give every numbered list a stable prefix at the
moment it is created, distinct from the priority vocabulary. Renumbering later
means sweeping every cross-reference.
Confidence: high.

### 2026-08-17 — Answering a question in one document does not close it in the others
Area: process.
Evidence: three P0 decisions were answered by new contracts -- the telemetry
sink, profile onboarding ownership, the popup and permission clauses -- and all
three stayed open in `ACCEPTANCE_SUITES` and elsewhere, reading as blocking work
that was not blocked.
Impact: a stale open question costs more than an unrecorded one, because it is
planned around.
Recommended future behavior: settling a decision is two edits -- the answer, and
a strike-through in every document that asked. `docs/OPEN_DECISIONS.md` is the
index that makes the second edit findable.
Confidence: high.

## Verification Lessons

### 2026-08-21 — A green build proves the code compiles and nothing else
Area: New Tab background, patches 0020-0021.
Evidence: build #40 was green on a feature that could not serve a single byte.
`UntrustedSource::ShouldServiceRequest` is an allowlist of exact paths; the
handler branch had been written and the allowlist entry had not, so every
request was refused with `ERR_INVALID_URL` before reaching it. The handler was
unreachable code that compiled. No guard, no test and no compiler objected.
Only an adversarial review found it.
Impact: a wave reported a feature as delivered when it could not work at all,
and the next step would have been the owner testing it and seeing nothing.
Recommended future behavior: when a feature adds a *branch* to an upstream
dispatcher, find the gate that decides whether the dispatcher is reached at all
and check the branch is named there too. Treat "compiles" and "reachable" as
two separate claims.
Confidence: high.

### 2026-08-21 — A feature whose failure looks like its absence hides its own defect
Area: New Tab background.
Evidence: the contract recorded, as a known limitation, that "a rejected file is
indistinguishable from no file" — missing, oversized and wrong-format all
produce the same blank screen. That same property would have hidden the
allowlist defect above from the owner's own testing.
Impact: a documented limitation became the thing that would have concealed a
defect from the only person able to observe it.
Recommended future behavior: when absence and refusal are indistinguishable at
the surface, that is not a cosmetic gap — it is a hole in every future
diagnosis of that feature. Either make the two distinguishable, or record
explicitly that this feature cannot be debugged from the outside.
Confidence: high.

### 2026-08-21 — Check the budget you are not amending
Area: `docs/PERFORMANCE_BUDGET.md`, PB-4 and PB-5a.
Evidence: the first background design probed the filesystem three times per New
Tab. It was reasoned carefully against PB-5a — the budget being amended for it —
and never checked against PB-4 next door, whose first zero-tolerance condition
reads "not once per window, not once per tab".
Impact: a design measured against the constraint it was rewriting, and against
nothing else.
Recommended future behavior: amending one constraint is the moment to read its
neighbours. The constraint being changed is the one least likely to catch the
change.
Confidence: high.

### 2026-08-22 — Derive from the pinned source; do not assert from memory
Area: background caching, iframe sizing.
Evidence: two questions were settled by reading upstream rather than reasoning.
`UntrustedSource::AllowCaching()` returns false, so the backend sets
`Cache-Control: no-cache` with no validator and the asset is re-read on every
New Tab. `iframe.css` sizes ntp-iframe's inner frame with `height: inherit` and
`width: inherit`, so a host positioned with `inset: 0` alone computes `auto`,
and an iframe being a replaced element falls back to 300x150 — which is why the
background rendered in a corner while `cover` was correct all along.
Impact: both were about to be answered with plausible reasoning that would have
been wrong, and the second had already been shipped as a defect.
Recommended future behavior: when the proxy blocks `chromium.googlesource.com`,
`raw.githubusercontent.com/chromium/chromium/<tag>/<path>` reaches the same
file. Read it. A derivation from source is a strong claim; a derivation from
memory is a guess wearing its clothes.
Confidence: high.

### 2026-08-22 — In a patch stack, read every patch that touches a file
Area: `mount_port.ts`, patches 0012 and 0016.
Evidence: the port's message vocabulary was extracted from the patch that
*creates* the file (0012) and reported as seven messages. Patch 0016 extends the
same file with the document-store port, making it nine. The error reached a
document written to be handed to another session.
Impact: a downstream session would have been told the storage port does not
exist.
Recommended future behavior: `patch_manifest.py` already reports how many
created files are "extended by a later patch". When reading a definition out of
the stack, enumerate every patch section naming that path, not the first.
Confidence: high.

## Strategy Observations

### 2026-08-21 — A value stated twice is a value that will drift
Area: `scripts/build_gate_sheet.py`.
Evidence: the build stamp existed in the page header and again, hardcoded,
inside the export text the owner copies back. The second copy went two builds
stale unnoticed, so a returned result would have named the wrong binary while
looking like a good result.
Impact: near-miss on the one output a verification sheet must never produce —
a result about an unknown build.
Recommended future behavior: single-source the value and add a check that
refuses a second spelling. This repository already had the same lesson for
documents ("a rule stated in two documents is a rule with no owner"); it applies
to generated artefacts identically.
Confidence: high.

### 2026-08-21 — Instructions written from the contract describe a screen that does not exist
Area: `gate-sheet.html`, document-surface gates RV-15..RV-19.
Evidence: five rows came back blank. The walkthroughs had been written from
`docs/DOCUMENT_SURFACE_CONTRACT.md` and told the owner to build a hierarchy by
indentation; the page builds it with an `Inside` parent selector. The owner
said plainly, twice, that they could not follow them.
Impact: five gates unrunnable, and the cause was the instructions rather than
the build.
Recommended future behavior: write a runtime walkthrough from the patch that
creates the surface, not from the contract that specifies it. The contract is
exact for its author and opaque to whoever holds the mouse. "I do not
understand this" is a defect report about the writing.
Confidence: high.

### 2026-08-22 — Re-reading a recorded rationale can void it
Area: `docs/PERFORMANCE_BUDGET.md` PB-5a, video exclusion.
Evidence: the exclusion rested on three grounds. On being re-read for an
amendment, two did not survive: the "codec-licensing question" was a real
decision about H.264 written as a claim about video as such (ADR 0004 leaves
proprietary codecs off, and VP9/AV1/Opus are royalty-free), and the audio track
"that must be proven silent" is proven silent by `muted`. Only the decode
pipeline stood.
Impact: a decision had been carrying two reasons that were not reasons, and
would have kept carrying them.
Recommended future behavior: when reversing or amending a recorded decision,
re-read its stated grounds one at a time and mark which survive. Keep the table
in the document. A record that quietly drops its own reasoning is worth less
than one that shows where it was wrong.
Outcome: the amendment was withdrawn the next day — the owner cancelled the
capability as unnecessary, before any code was written. The corrections were
kept anyway, because the section would otherwise still read as three reasons
when it only ever had one. **A decision that does not need its cost estimate is
not repaired by fixing the estimate**, and that is the sharper half of this
lesson: the work of re-deriving the grounds was right, and it changed nothing
about the answer.
Confidence: high.

### 2026-08-22 — Cancelling a queued job discards the wait without shortening it
Area: self-hosted native build runner.
Evidence: across 44 runs, four sat queued for hours because the runner was off.
Run #17 waited 13 h 34 m, was picked up unchanged when the runner returned, and
succeeded in 26 minutes. Runs #30, #36 and #43 were cancelled after 9 h 27 m,
7 h 33 m and 1 h — in two cases a new run was dispatched within five seconds,
into the same empty queue.
Impact: three build slots produced nothing, and the reflex that produced them
looks like action.
Recommended future behavior: a job queued against an absent self-hosted runner
is not stuck, it is waiting; GitHub cancels it only at 24 h. Check the run
history before re-dispatching, and say plainly that the machine is the blocker.
Confidence: high.

### 2026-08-21 — Verify a reviewer's claim before relaying it
Area: adversarial review of patch 0019.
Evidence: a reviewer raised a CRITICAL — `+++ a/` in a patch header defeats
PO-A2's parser. Checking it directly showed `verify_patch_integrity` rejects
that header shape outright, so CI stops it before PO-A2 is reached. The severity
was wrong.
Impact: relaying it unchecked would have escalated a non-issue to the owner as
a merge blocker.
Recommended future behavior: a reviewer finding is a hypothesis with evidence
attached, not a verdict. Reproduce the consequential ones against the tree
before passing them on — including when they favour caution, and including your
own earlier statements.
Confidence: high.

### 2026-08-22 — Write the test for the rule; it will find the bug you did not write it for
Area: `scripts/build_newtab_background.py`.
Evidence: tests were written for natural frame ordering (`frame10` after
`frame2`). One of them — a folder holding both `1.png` and `a.png` — failed with
`TypeError: '<' not supported between instances of 'int' and 'str'`, because the
sort key mixed bare ints and strs. An ordinary folder would have crashed the
tool.
Impact: a crash found before first use, in code that had been reviewed by eye
and looked correct.
Recommended future behavior: this repository already records "write the
failure-injection test before the defensive guard". The same holds for ordinary
logic: tests written to pin an intended property routinely fail for a different
reason, and that reason is usually the real defect.
Confidence: high.

### 2026-08-22 — Ask when the scope of an irreversible instruction is ambiguous
Area: PB-5a amendment.
Evidence: the owner wrote "계약파기" — two words. It could have meant voiding
PB-5a's video exclusion, voiding PB-5a entirely, discarding the background
contract, or ending the discussion. Three of the four would have deleted
governing documents.
Impact: none, because the four readings were put to the owner with their
consequences and the narrowest was chosen.
Recommended future behavior: brevity is not authorisation for the largest
reading. When an instruction is short, irreversible and admits several scopes,
enumerate the scopes with what each destroys and let the owner pick. This is the
narrow exception to acting without asking.
Confidence: high.

### 2026-08-24 — A guard that greps a patch reads the patch's comments too
Area: `scripts/verify_newtab_background.py`, NTB-13.
Evidence: the check requires that `[has-user-input_]` appearing in
`ntp_searchbox.css` be matched by `reflect: true` in `ntp_searchbox.ts`. Its
membership test ran over the raw added lines, and the stylesheet's own comment
explains the rule by naming `[has-user-input_]`. The test that deletes the CSS
rule and keeps the reflection therefore passed the guard: the prose satisfied
it. Found by writing that test, not by reading the check.
Impact: none shipped; the check strips comments before the membership tests.
Recommended future behavior: every text-membership guard over a patch decides
first whether it is reading code or reading prose. This repository already had
`without_comments()` for exactly this and it was not reached for. Note the
second trap: `without_comments()` also strips from `//` to end of line, which
would eat `url(//resources/...)` — a CSS guard needs the `/* */`-only form.
Confidence: high.

### 2026-08-24 — Chromium lints Sunshine's CSS, and nothing here ran that lint
Area: `downstream/patches/0022-sunshine-searchbox-state.patch`, native build #46.
Evidence: the patch declared `#inputWrapper` a second time in
`ntp_searchbox.css` — deliberately, so no upstream line was edited and the hunk
survived a roll. Twenty-seven architecture guards passed. S1 through S12 passed.
`verify_pinned_upstream` proved the patch applies to the real pinned tree, and
it was applied by hand at the pin, at 153.0.8000.0 and at trunk. Build #46 then
failed in twenty seconds: `Unexpected duplicate selector "#inputWrapper", first
used at line 84  no-duplicate-selectors`, from
`ui/webui/resources/tools/stylelint.config_base.mjs`, which Chromium runs over
every preprocessed WebUI stylesheet.
Impact: one build lost, after a ten-hour queue wait on the owner's workstation —
which is what the cost of this class of miss actually looks like here.
Recommended future behavior: `git apply` answers *will this patch land*; it does
not answer *will Chromium accept what it lands*. Any patch touching a WebUI
resource folder is subject to Chromium's own lint and build actions, and those
are a second acceptance test nothing in this repository was running. S13 in
`docs/DESIGN_SYSTEM_CONTRACT.md` now covers `no-duplicate-selectors`; the rest
of that config is still unchecked and will be found the same way.
Confidence: high.

### 2026-08-24 — Roll-friendliness and upstream's linter can pull opposite ways
Area: the same patch.
Evidence: adding a declaration to upstream's `#inputWrapper` rule needs ten
lines of context to reach it, and at trunk a `border` declaration has moved out
of that rule into an `::after` — so the hunk conflicts. Declaring the selector a
second time avoids the conflict and breaks the linter. The two constraints had
no overlap for the feature as designed.
Impact: the 150ms fade was dropped. The state distinction the owner asked for is
unaffected; only the decoration went.
Recommended future behavior: when the roll-safe shape and the lint-safe shape
disagree, check first whether the thing forcing the conflict was asked for. Here
it was not — the fade was added unprompted — and removing it satisfied both
constraints exactly. Reach for a synthetic selector to slip past a linter only
after that question has been answered, and preferably not then.
Confidence: high.

### 2026-08-25 — Nothing checks whether a contract is right about its own implementation status
Area: `docs/INSTALLER_UI_CONTRACT.md`.
Evidence: its Status block said **"No implementation exists"** while
`installer/sunshine_setup.cpp` held 948 lines, `verify_installer_frontend.py`
read it on every CI run, and build #47 produced a 117.8 MB `sunshine-setup.exe`
from it. Found by reading the document during a roadmap briefing, not by any
guard. Twenty-seven guards check what the code does; none checks what a document
claims the code *is*.
Impact: a briefing nearly reported the installer front-end as unbuilt work.
Recommended future behavior: when a contract's status line is load-bearing —
"not built", "nothing exists", "decided, not built" — check it against the tree
before repeating it, and update it in the same change that makes it false. No
guard is proposed: the checkable form of this rule would grep prose, and
`LESSONS_FROM_PRACTICE` 14 is about what that does to prose. The cheap defence
is that whoever lands the implementation edits the status line, and the cheap
detection is a periodic read.
Confidence: high.

### 2026-08-25 — A command surface name can collide with the manifest schema
Area: `first_party/commands.json`, `scripts/validate_commands.py`.
Evidence: declaring `security` as a command surface made the doc scanner read
five existing prose mentions of module-manifest fields —
`security.network.access`, `security.credentials`,
`security.filesystem.access`, `security.ai_providers.hosts`, `security.network`
— as references to commands that do not exist, and the guard failed. The
manifest's own `security` block owns that namespace in prose. Renaming the
surface to `security_center` cleared it with no change to the guard.
Impact: none shipped; found in the first run after declaring the surface.
Recommended future behavior: before adding a command surface, grep the docs for
backticked tokens beginning with that word. The guard finds this for free, so
the real lesson is to declare the surface early and let it fail rather than
writing the whole entry first. Do not weaken the scanner to fit a name — the
collision is real, and a reader hits it too.
Confidence: high.

## Recording rule

Add only concise, evidence-backed facts such as:

```text
### 2026-XX-XX — <lesson>
Area:
Evidence:
Impact:
Recommended future behavior:
Confidence:
```

Prefer facts that can change future Mission Packing, verification timing, or conflict prevention.

Remove/replace stale lessons when repository reality changes.
