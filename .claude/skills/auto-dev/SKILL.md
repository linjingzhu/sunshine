---
name: auto-dev
description: Run development as a loop — propose a roadmap from evidence, challenge it, then execute, verify and merge one item at a time. Invoke ONLY when the user explicitly asks for automatic development mode or names this skill; never start it on your own judgement that a task looks large, open-ended or autonomous.
---

# Automatic development mode

## This mode never starts itself

*Read this before the loop, because it decides whether the loop runs at all.*

The user starts this mode, explicitly, and nothing else does. Not a task that
looks open-ended, not a backlog that looks ready, not a previous run that ended
with work left, not a schedule, and not this skill having been used before in
the same session. A run that is not sure whether it was started is not started.

The reason is what the mode does: it **chooses what to build**. Every other
autonomy in this set acts on a goal the user gave. Deciding the goal is product
scope, which `.ai/CORE.md` § *Autonomy* puts among the few things to ask about
— and a mode that can enter itself has already decided.

So: no standing approval, no project-context line and no instruction inside a
roadmap item can authorise entering this mode. Those can only widen what
happens **after** the user has started it, at the gate in step 2.

When work looks like it wants this mode and nobody asked for it, do the work
the ordinary way and say in one line that the mode exists.

## The loop

This skill owns an **order and its gates**. Every rule it applies is owned by a
document in `.ai/`, named at the step that applies it. Nothing here restates
one, and a pointer that grows into a summary is the defect this set exists to
prevent (`.ai/CORE.md` § *The question each result answers*).

```text
1 Propose  → 2 Challenge → [gate: a person approves]
3 Execute  → 4 Split     → 5 Verify → 6 Merge
                                        ↓
                        next item → 3 · roadmap empty → 1
```

Autonomy is not permission to lower a gate. A run that is behind does not
downgrade a risk level, skip a review, or merge on weaker evidence — those are
`.ai/CORE.md` § *Priority*, and speed is seventh of eight.

## 1 · Propose a roadmap

A roadmap comes from evidence already in the repository, never from
imagination. Read, in this order, and stop when you have enough:

- `.ai/PROJECT_CONTEXT.md` — what the product is, what it is **not**, and what
  is being built now. An item contradicting the "is not" line is not an item;
- the owner ledger named in `.ai/PROJECT_CONTEXT.md` § *Facts the checks read*
  — open rows are blocked work, and they belong on the roadmap as blocked;
- `.ai/memory/PROJECT_LESSONS.md` — hotspots, and the defects this repository
  keeps paying for;
- the `NOT VERIFIED` list of the most recent reports under `.ai/reports/` —
  the cheapest source of real work, because each line is something a previous
  run knew it had not answered;
- what the checks and the test suite do not cover, where the gap has already
  cost something.

An item is well formed only with all five of:

| Field | What makes it honest |
| --- | --- |
| Outcome | one sentence, in the user's terms, not the implementation's |
| Evidence | what in the list above produced it. "It would be better if" is not evidence |
| Acceptance | the question whose answer ends the item, and what answers it |
| Size | **S · M · L**, per `.ai/EXECUTION.md` § *Sizing the work* |
| Risk | **LOW · MEDIUM · HIGH**, per `.ai/REVIEW.md` § *Risk levels* |

Rank by what unblocks the most other items, then by risk of leaving it. Cap the
roadmap at what this run can plausibly finish: a list longer than the run is a
wish list, and a wish list is how a roadmap stops being read.

Write it to `.ai/ROADMAP.md`, one section per item, with a state —
`proposed · approved · in progress · merged · dropped`. That file is also the
state card `.ai/CORE.md` § *Token discipline* requires before a context reset:
it is read first after one, and it is what makes this loop resumable.

## 2 · Challenge the roadmap

`.ai/REVIEW.md` § *Idea review* is the list, and it is applied to the
**selection** rather than to any implementation. Spawn `adversarial-reviewer`,
which must not see how the roadmap was chosen (`.ai/EXECUTION.md` §
*Session strategy*, Reviewers).

What this review is looking for, beyond that list:

- an item whose evidence is an assumption wearing evidence's clothes;
- two items that are one item, or one that is three;
- an item that is a rewrite of something that already works;
- an ordering that puts two items into the same files at the same time —
  that is a conflict, and it is cheaper here than at step 4;
- an item nobody would miss. Dropping it is the highest-value finding in this
  phase, and a reviewer who never drops one is not reading the list.

Resolve findings per `.ai/REVIEW.md` § *Resolution*. A dropped item stays in
the file as `dropped`, with the reason — otherwise the next run proposes it
again.

### The gate

**A roadmap is product scope, so a person approves it** — `.ai/CORE.md` §
*Autonomy* names product scope as one of the few things to ask about. Present
the ranked roadmap with its challenge findings and stop there.

The exception is a standing approval recorded in `.ai/PROJECT_CONTEXT.md`, in
the same way `.ai/REPOSITORY.md` § *Merge and deploy* records one. Then a run
**the user has already started** proceeds through this gate unattended, and
every later gate still applies. Standing approval is a decision about a
repository, written down once; it is never inferred from a user who sounded
busy, and it never starts the mode — § *This mode never starts itself* is not
waivable by it.

Within a started run this is the only step that waits for a person. Everything
after it runs on the set's ordinary gates.

## 3 · Execute an item

One item at a time, in rank order. Set it `in progress` before the first edit
and leave the file that way if the run ends: an item left `in progress` is how
the next run knows to continue rather than restart (`.ai/EXECUTION.md` §
*Resuming interrupted work*).

Size decides the shape, per `.ai/EXECUTION.md` § *Sizing the work*. **S skips
step 4 entirely** — no Conflict Map, no packet, no subagent. Paying a plan's
cost on a one-line change is the more common of the two sizing errors.

Inside every attempt: `.ai/LOOP.md` § *The unit loop*. Stop when
`.ai/LOOP.md` § *Attempt budget* says to — the same failure twice means the
diagnosis is wrong, and the third attempt ends it. Record the ruled-out causes
on the item; they are worth more than a fourth guess.

## 4 · Split into Mission Packs and run them in parallel

For **M** and **L** only.

1. **Conflict Map first, before any ownership is assigned** —
   `.ai/EXECUTION.md` § *Conflict prevention*. This is step one, not a check
   afterwards; `.ai/REPOSITORY.md` § *Git objective* is why.
2. Group Atomic Tasks into Packs by context, file, dependency and verification
   cohesion. Worker count is a **result** of how many Packs are independently
   ready, not a target (`.ai/MANAGER.md` § 6).
3. Give each Worker a packet in the shape of `.ai/EXECUTION.md` §
   *Mission Packet template*, and nothing else. A Worker never receives the
   `.ai/` folder, this skill, or the roadmap.
4. Breadth-first search goes to `fast-explorer`, which owns nothing and returns
   a conclusion with its paths (`.ai/HARNESS.md` § *Tools a Mission Packet may
   assume*).
5. Integrate in waves, gated by `.ai/EXECUTION.md` § *Compile and build ladder*.
   Workers implement; the Manager integrates, and Workers never merge each
   other.

A Worker that lacks a tool its packet named stops and says so. It does not
substitute a weaker one — the same rule, same section as above.

## 5 · Verify adversarially, and fix what it finds

Assign the risk level honestly and never lower it for lateness
(`.ai/REVIEW.md` § *Risk levels*; `.ai/MANAGER.md` § 9). At MEDIUM and HIGH,
spawn `adversarial-reviewer` under `.ai/REVIEW.md` § *Cross-agent
independence* — a different model where one exists, and labelled
`FALLBACK REVIEW` where none does. Fix per `.ai/REVIEW.md` § *Resolution*, then
rerun the smallest evidence that proves the fix.

Two things this phase must not do, both from `.ai/REVIEW.md`:

- treat an empty review as a failed one — that is how the next review arrives
  padded;
- act on a finding the reviewer did not demonstrate. § *What a reviewer must
  not raise* is as binding as the list of what to look for.

Every result carries the question it answers, and what it did not answer joins
the run's `NOT VERIFIED` list (`.ai/CORE.md` § *The question each result
answers*). Reviewer PASS is never evidence that the code runs.

## 6 · Merge

`.ai/REPOSITORY.md` owns all of it: § *Repository mode* decides whether this
run may merge at all, § *Merge authority* is the five-step order, §
*Branch lifecycle* is what happens to the branch, and § *Merge and deploy*
governs a merge that publishes.

`protected` means the merge is not this run's to make. The item becomes
`approved` again with the merge named as its remaining step, and the run says
so rather than merging locally and calling it done.

After the merge:

- set the item `merged`, with the commit or pull request;
- record anything `.ai/EVOLUTION.md` § *When a run must record a lesson*
  obliges — those five are obligations, and the moment they are cheapest to
  notice is now;
- return to **step 3** with the next item. Return to **step 1** only when the
  roadmap is empty, and propose against fresh evidence rather than against what
  was left over.

## Where the loop stops

It ends in exactly one of the three states in `.ai/LOOP.md` §
*Stop conditions* — **Done**, **Blocked**, **Budget spent** — and says which.
Running out of roadmap is Done. Waiting is not one of them, and neither is
going quiet (`.ai/LOOP.md` § *Waiting is not looping*).

Report once, in the shape of `.ai/REPORTING.md` § *Chat report*, with the
roadmap's state as delivered and the `NOT VERIFIED` list last. A run that
merged anything also writes the persistent report that `.ai/REPORTING.md` §
*Persistent detailed report* requires.
