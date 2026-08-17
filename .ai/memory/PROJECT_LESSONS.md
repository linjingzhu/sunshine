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
