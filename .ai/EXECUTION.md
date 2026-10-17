---
doc_id: ai-execution
version: 1.3.0
canonical_path: .ai/EXECUTION.md
updated: 2026-09-26
---

# Execution, Mission Packs, and Sessions

## Core model

```text
Run
→ Primary Manager
→ Atomic Tasks
→ Mission Packs
→ Workers
→ Integration Waves
→ Review
→ Result
```

A Task is not automatically a Session.

## Sizing the work

Before deciding how many Workers, decide whether the question arises. Size the
task first, because the cost of planning a small change is paid whether or not
the plan was needed.

| Size | What it is | What it gets |
| --- | --- | --- |
| **S** | one clear change in one place | the Manager does it directly. No plan, no Packet, no subagent — the cheapest verification that answers the question, and nothing else |
| **M** | an ordinary feature across a few files | find the existing implementation first, split into Packets only where work is genuinely independent, build and test, independent review |
| **L** | several subsystems, or a change to a shared interface | explore, then plan, then implement; parallelise only independent Packs; strengthen regression cover; a Conflict Map before any of it |

Getting this wrong is expensive in both directions. Planning an **S** burns a
run's budget producing structure nobody reads. Treating an **L** as **M**
skips the Conflict Map, and the cost arrives later as a merge.

When the size is not obvious, it is **M**.

### The size was a hypothesis

It was judged before the work began, which is when the least was known. Work
that outgrows its size is normal; continuing at the old size is the defect.

A Worker whose Pack turns out larger than its packet — a shared interface it
must change, a subsystem the Conflict Map did not name, an assumption that was
wrong — **stops and returns to the Manager** rather than widening the change
alone. It returns four things and nothing else:

```text
FOUND      what is affected that the packet did not name
WRONG      the assumption that failed, and how it was found
RISK       what breaks if this is built at the original size
NEEDS      the ownership, tool or decision the new size requires
```

The Manager re-sizes and reassigns; **S → M → L** is an ordinary outcome, not a
failure of the estimate. A Worker that widens its own ownership instead has
taken a decision the Conflict Map exists to make
(§ *Conflict prevention*), and the cost arrives as a merge.

The same applies to the Manager's own work: an **S** that has grown a second
file and a third question is an **M** that skipped its plan.

## Resuming interrupted work

A run that finds a feature already in progress continues it. It does not start
it again, and this is where an agent most easily destroys work that was not
its own.

First establish which of two states this is:

- **New** — no branch, no worktree, nothing in progress for this feature.
- **Resuming** — a branch, a worktree, or uncommitted changes for it exist.

Read the state before deciding: current branch, `git status`, the diff,
which files changed, whether the build and tests currently pass. That reading
is what tells you which ladder rungs (§ *Compile and build ladder*) are already
behind you.

When resuming:

- keep the existing branch and worktree; do not create a second one;
- do not switch away from the feature branch mid-work;
- do not reset, delete or overwrite changes already made;
- do not redo implementation that is already done and passing;
- change existing work only where it conflicts with the current requirement,
  and only as far as that conflict reaches;
- continue from the first rung not yet passed, not from the beginning.

`.ai/REPOSITORY.md` § *Branch lifecycle* owns what a branch may do; this
section owns only the question of whether a run is starting or continuing.

## Session strategy

*Single source for whether a piece of work gets a new Worker or reuses one.
`.ai/MANAGER.md` § 6 owns how many Workers result from it.*

### Manager
- one primary Manager context per run where practical;
- ends when the run is complete.

Replace a Manager session at a **task boundary**, never on a clock: a finished
subtask, a commit, the handover from implementing to reviewing, a context grown
too large to reason in, or a run whose earlier assumption keeps producing the
same wrong judgement (`.ai/LOOP.md` § *Signs the loop is not converging*).
Replacing one mid-implementation costs the reading that produced the current
state.

The branch and the worktree outlive the session. A replacement continues in the
same one — it does not create a second (§ *Resuming interrupted work*) — and
reads the state card `.ai/CORE.md` § *Token discipline* requires before the
handover.

### Workers
Reuse a Worker within the run for strongly related work.
Create a new Worker when:
- a substantial independent subsystem can progress in parallel;
- context is meaningfully different;
- isolation reduces conflict;
- a specialized role is needed.

Do not spawn a new Worker for:
- copy changes,
- one tooltip,
- lint cleanup,
- a tiny validation,
- a single small test,
- a small follow-up in the same subsystem.

### Reviewers
Prefer fresh context.
Reviewer context should contain only:
- requirement/acceptance criteria,
- relevant architecture facts,
- diff/changed files,
- tests/build evidence,
- review rules.

Do not inherit the implementer's reasoning history.

## Worktrees and branches

When supported, use isolated worktrees/branches for independent Mission Packs.

Rules:
- one write owner per path/symbol at a time;
- Workers do not merge each other;
- Workers do not casually edit outside ownership;
- shared/hotspot changes are serialized or assigned to one Pack;
- a generated artefact (`.ai/PROJECT_CONTEXT.md` § *Facts the checks read*,
  `generated`) has one owner: the integration branch. Packs edit sources
  only; regeneration happens once, at integration, by the listed command.
  Two branches that each regenerate the same file will each delete the
  other's version;
- Manager owns integration order;
- **each worktree builds into its own directory.** Two worktrees sharing one
  build output overwrite each other's artefacts, and the failure looks like a
  source defect in whichever built second. A compiler cache may be shared —
  it is keyed by content, which is the difference. An inactive worktree's
  build directory may be deleted to reclaim space; nothing committed depends
  on it.

## Mission Packet template

The Manager should give each Worker a compact packet like:

```text
MISSION
<name>

GOAL
<one concise outcome>

OWNERSHIP
- writable paths/symbols

READ-ONLY CONTEXT
- relevant paths/symbols

DO NOT MODIFY
- explicit conflict boundaries when useful

TASKS
1. ...
2. ...

POLICY
- autonomous implementation
- smallest safe change
- verification on the primary target platform only
- sources only; do not regenerate artefacts
- no merge
- self-review and self-fix

UX CONTRACT
<include only when relevant>

VERIFY
- cheapest meaningful checks
- affected compile
- relevant tests

DONE WHEN
- acceptance criteria met
- ownership respected
- verification passed
- no unresolved major self-review finding

RETURN INSTEAD IF
- the work does not fit this ownership: report FOUND / WRONG / RISK / NEEDS
  (§ *Sizing the work*) rather than widening it
- a named tool is unavailable (`.ai/HARNESS.md` § *Tools a Mission Packet may
  assume*)
```

Workers should not be told to read the full `.ai` folder.

## Compile and build ladder

*Single source. `.ai/MANAGER.md` § 7 owns where the wave boundaries fall; which
gate fires at each one is here.*

Use the cheapest meaningful gate early:

```text
Edit
→ static/lint/type check where useful

Atomic Task boundary
→ targeted verification

Mission Pack boundary
→ affected compile

Integration wave
→ affected build for the primary target platform

Run boundary
→ final target-platform verification/build when justified
```

Do not let multiple substantial Packs accumulate without compilation when compilation is feasible.

## Conflict prevention

*Single source. `.ai/MANAGER.md` § 4 obliges the Manager to run this before
assigning ownership; the procedure is here.*

Before parallel work:
1. identify overlapping files/symbols;
2. identify shared interfaces;
3. consult known hotspots in Project Lessons;
4. serialize conflicting work or combine it into one Mission Pack;
5. define integration order.

Before integration, simulate/check merge conflict risk using available Git tooling or a temporary integration worktree when useful.

Track conflict count and resolution effort as a development-efficiency signal.
