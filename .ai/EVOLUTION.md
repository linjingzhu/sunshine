---
doc_id: ai-evolution
version: 1.0.0
canonical_path: .ai/EVOLUTION.md
updated: 2026-09-03
---

# How the Set Improves Itself

*The recording triggers and the pruning rule are new convention; the "prefer a
check" rule is paid for — `LESSONS_FROM_PRACTICE.md` entries 6, 14 and 15.*

`.ai/MANAGER.md` § 12 owns the Manager's duty to meta-evaluate a run and the
metrics it records. This file owns what happens to what that evaluation finds.

A methodology that only accumulates is a methodology nobody rereads. This file
is the loop that keeps it worth reading: what a run must record, where each kind
of record goes, how a record becomes a rule, and when a rule is removed.

## When a run must record a lesson

Recording is not "if something interesting happened". These five are
obligations, and each is cheap to notice at the moment it occurs:

1. **A defect got past a gate.** Name the gate and the question it was actually
   answering.
2. **A gate fired on something correct.** A false positive teaches contributors
   to work around the check, which is worse than not having it.
3. **A rule was ambiguous at the moment of use.** If a run had to guess what a
   policy meant, the next run will guess differently.
4. **Something was rediscovered.** The second time a run reads the same
   subsystem to learn the same fact, the fact belongs in project memory.
5. **A number moved.** A metric that changed after a strategy change is the only
   evidence a strategy change works.

A run that hits none of these records nothing. That is a normal outcome and
better than a lesson invented to fill the section.

## Where each kind of record goes

| What it is | Where it lives |
| --- | --- |
| A fact about *this* repository — a hotspot, a build quirk, a path that lies | `.ai/memory/PROJECT_LESSONS.md` |
| A strategy that might generalise, not yet validated | `.ai/memory/MANAGER_PLAYBOOK.md`, as `candidate` |
| A defect generalised, stripped of its project, that cost something | `LESSONS_FROM_PRACTICE.md` |
| A rule that now binds every run | the owning `.ai/` document, and a `.ai/CHANGELOG.md` entry |

`.ai/memory/MANAGER_PLAYBOOK.md` § *Promotion rule* governs the move from the
second row to the fourth, and requires that the copy left behind is deleted.

## Prefer a check to a sentence

A lesson written as prose lasts until the next person has a reason to ignore it.
The strongest form of a lesson is a check that fails, and the second strongest
is a lesson that says which check it is waiting for.

- If the lesson can be expressed over **structure** — a file, a field, a
  heading, a reference, a byte comparison — write the check and let the prose
  be its docstring.
- If it can only be expressed as a phrase to grep for, it is not yet a rule
  (`LESSONS_FROM_PRACTICE.md` entry 14). Leave it as a lesson and say so.
- A new check ships with a test that makes it fail on purpose, or it is not
  known to work (entry 15).

`.ai/tools/README.md` § *What they do not answer* is where each check's blind
spot is written down. A check added without its blind spot recorded is a rule
that will be over-trusted.

## Pruning

An entry is removed by the run that discovers it is stale, in that run's change:

- its evidence no longer holds — the file moved, the quirk was fixed upstream;
- it was promoted into policy, and this is the copy left behind;
- it has never once changed a decision, and the reason is that it was always
  obvious.

An append-only memory that nobody prunes stops being read, and an unread memory
is indistinguishable from no memory while still costing tokens to load.
