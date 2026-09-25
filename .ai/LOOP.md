---
doc_id: ai-loop
version: 1.0.0
canonical_path: .ai/LOOP.md
updated: 2026-09-03
---

# The Working Loop

*The attempt budget and the non-convergence signs below are paid for:
`LESSONS_FROM_PRACTICE.md` entries 12, 15 and 21. The rest is convention.*

`.ai/EXECUTION.md` § *Compile and build ladder* is the outer rhythm — task,
Mission Pack, wave, run. This file is what happens inside a single attempt, and
when to stop attempting.

## The unit loop

One attempt is four steps, in order, every time:

1. **Orient** — read the thing you are about to change, and the gate that
   decides whether your change is reached at all (`LESSONS_FROM_PRACTICE.md`
   entry 1).
2. **Act** — the smallest reversible change that could settle the question.
3. **Verify** — run the cheapest check that answers *the question you actually
   have*, and write down which question that was.
4. **Record** — the result, and what it did not answer.

Step 4 is the one that gets dropped under time pressure, and dropping it is what
turns three attempts into the same attempt three times.

## Attempt budget

- **The same failure twice means the diagnosis is wrong**, not the parameter.
  Change what you believe before you change another value. Retrying with a new
  argument is a new attempt only if a new belief produced the argument.
- **Three attempts on one failure ends the attempt.** Stop, and report what was
  tried and what each attempt ruled out. A list of ruled-out causes is worth
  more to whoever picks it up than a fourth guess.
- **Never repeat an action whose result you did not read.** Re-running a command
  because the output was long is how a run spends a budget learning nothing.

## Signs the loop is not converging

Any one of these ends the current attempt and starts a fresh diagnosis:

- the same error text after a change that should have altered it;
- the diff grows while the failure stays the same size;
- an edit undoes an edit made earlier in the same run;
- the verification target moves toward something easier to satisfy;
- the explanation needs a new assumption each time it is challenged.

The last one is the earliest signal and the easiest to miss from inside.

## Waiting is not looping

A wait spends turns without producing a belief. `.ai/CORE.md` §
*Token discipline* holds the rule: one lookup after a completion signal, not a
polling loop. Where the harness can schedule a later check, schedule it and end
the turn; where it cannot, say what is blocking and who can unblock it, then
stop. Cancelling and re-dispatching a queued job discards the wait without
shortening it (`LESSONS_FROM_PRACTICE.md` entry 12).

## Stop conditions

A run ends in exactly one of three states, and says which:

1. **Done** — acceptance criteria met, each with the question its evidence
   answered, and a `NOT VERIFIED` list of what is still open.
2. **Blocked** — a decision, a credential, or an access the run cannot obtain.
   Name what is needed and from whom, in one sentence.
3. **Budget spent** — the attempt budget above, with the ruled-out causes.

Going quiet is not one of them. Neither is a summary that reports the work done
without saying which of the three states it ended in.
