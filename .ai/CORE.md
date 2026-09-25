---
doc_id: ai-core
version: 1.3.0
canonical_path: .ai/CORE.md
updated: 2026-09-19
---

# Core Development Constitution

The quality floor. Strategy adapts; these rules do not.

## Priority

1 Correctness · 2 User intent and product value · 3 Regression and data
safety · 4 UX · 5 Git conflict prevention · 6 Delivery speed · 7 Token and
cost · 8 Architectural elegance. Never lower the floor to improve a metric.

## Autonomy

Act without asking when convention, the existing implementation, evidence,
or the smallest reversible choice settles it. Ask only for: product scope,
irreversible external impact, secrets, external cost, legal or security risk.

Say at once, in the same turn: an attachment that did not reach the working
tree (ask for a path or upload; never act on what was not received); a
standing directive ("from now on", "always") — write it into
`.ai/PROJECT_CONTEXT.md` or `.ai/memory/PROJECT_LESSONS.md` now, because the
conversation does not survive a context reset.

## Implementation

Reuse before adding. Smallest safe diff. No duplicate implementations, no
needless dependencies. Keep backward compatibility unless the task changes
it. Fix small, clearly related adjacent defects; split unrelated discoveries
into follow-ups. "Code written" is not "feature complete".

### Comments

A comment earns its place by explaining what the code cannot: a non-obvious
reason, a constraint, an external contract, a hard algorithm, a trap someone
already fell into. Fix or delete a comment the change made false.

Never write the conversation into the code. Not the user's instruction, not
the Mission Packet, not what the run did or that a line changed — those belong
in the commit message and the pull request, where they can be read against the
diff. A code comment addressed to whoever asked for the change is a comment
addressed to nobody who will ever read it.

## Token discipline

Useful development per token, not session count.
- No rediscovering a subsystem; reuse context within a run; Mission Packets,
  not policy reloads; path, symbol and diff investigation, not rereads; no
  duplicated research; reviewers get requirements, diff, tests and facts, not
  the implementer's reasoning history.
- A watched event is a summary: an echo of your own action is read, not
  answered; a check-in reports only a changed state.
- The smallest query that answers: no list call when a single-item call
  carries the fact; no result the harness already had to truncate.
- Wait on events, not sleeps: one lookup after the completion signal.
- Before a context reset, write a state card (branch, open pull requests,
  unfinished items, verification commands); read it first afterwards.
- Stable prefix: same read order every run, volatile content last. Load a
  document when its trigger fires, never in case.
- Breadth-first search goes to a subagent; keep the conclusion, not the files.
- Bound the output too: the fewest facts that let the user decide, plus what
  is unverified.
- Never fabricate token or cost numbers.

## Target platform

`.ai/PROJECT_CONTEXT.md` names it. Build and verify there by default; a
secondary platform only on request; none named → ask once.

## Quality evidence

Completion rests on deterministic evidence where applicable: compile, static
and type checks, tests, the target-platform build, runtime and visual
verification. AI agreement is not evidence.

### Tests check the shape of configuration

Not today's value. A real domain, identifier or token appears in at most one
test, the deploy guard, whose name says so.

### Generated artefacts

Listed under `generated` in `.ai/PROJECT_CONTEXT.md` § *Facts the checks
read*. Each changes only with its source, by the listed command, never by
hand; a check regenerates it and compares bytes.

### Public identifiers and secrets

`public_ids` may be committed; anything that authenticates lives in the host
environment. `external_scripts` lists every third-party script and its load
condition; nothing loads by default, and an unlisted script is a defect.

### The question each result answers

*The single normative statement; every other document points here.*

Name, beside every result, the exact question it answers; it is evidence for
that question and nothing else. A compile answers "is this valid", not "does
it work" or "is it reachable"; a guard answers "does this pattern appear",
not "is the rule kept"; a green build answers "did every step exit zero", not
"the feature works". Keep a `NOT VERIFIED` list through the run and end the
report with it. A question nobody asked is not a question that passed.

## Versioning

`.ai/CHANGELOG.md` § *Document versioning* and § *Set version*. A run needs
neither.
