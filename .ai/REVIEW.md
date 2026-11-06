---
doc_id: ai-review
version: 1.3.0
canonical_path: .ai/REVIEW.md
updated: 2026-11-06
---

# Adversarial Review Policy

Review should try to disprove correctness, not confirm the implementer's confidence.

## Idea review

Challenge:
- necessity,
- simpler alternatives,
- hidden workflow cost,
- architecture mismatch,
- performance/maintenance cost,
- misuse potential,
- regression risk,
- UX discoverability.

## Implementation review

Inspect:
- requirement coverage — the request split into its parts, each traced to the
  diff,
- features, options or abstractions nobody asked for,
- dead, unreachable or unused code the change added or left behind,
- wrong assumptions,
- error/empty/invalid states,
- lifecycle/stale state,
- concurrency where relevant,
- persistence/serialization compatibility,
- resource/performance issues,
- regression impact,
- missing tests,
- user-visible failure/recovery,
- UX contract compliance.

Findings require concrete evidence.

## What a reviewer must not raise

The list above is what makes a review worth commissioning. This one is what
makes it worth reading. A review that reports everything gets skimmed, and a
skimmed review is a gate that passes without asking.

Do not raise, unless the requirement says otherwise:

- style preference, and formatting the project has not made a rule;
- optional renames;
- refactoring nobody asked for;
- hypothetical future problems with no path from this diff;
- defensive code for conditions the types or the callers already exclude;
- anything phrased as "consider" — either it is a defect or it is not.

Two of these are worth naming as a pair. **Unrequested refactoring** raised as
a finding invites the implementer to widen the change, which is the scope rule
in `.ai/CORE.md` § *Implementation* broken by the reviewer rather than the
author. **Speculative defensive code** turns a review into a source of the
unnecessary complexity it exists to catch.

A reviewer who finds nothing reportable returns that, and a run that treats an
empty review as a failed review will get a padded one next time.

## Risk levels

### LOW
Examples: copy, tooltip text, isolated low-impact tests, tiny safe UI adjustment.

Default:
- implementer self-review,
- deterministic check,
- no fresh cross-agent review unless a risk signal appears.

A risk signal moves a LOW change to MEDIUM. Any one of these is one:
- the diff reaches an area the HIGH list below names;
- it touches a hotspot `.ai/memory/PROJECT_LESSONS.md` records;
- a test had to change for the change to pass;
- the deterministic check could not run, or answered a weaker question than
  the one the change raises;
- the self-review found something it did not expect.

### MEDIUM
Examples: normal feature spanning multiple files, typical UI + logic changes.

Default:
- independent adversarial review, preferably batched by cohesive Mission Pack or integration wave.

### HIGH
Examples:
- architecture,
- persistence/serialization,
- concurrency,
- migration,
- public/shared interfaces,
- data-loss risk,
- major workflow changes,
- large cross-cutting feature.

Default:
- fresh adversarial challenge before implementation when valuable;
- fresh final review before merge;
- prefer a reviewer that is a different model from the implementer.

## Cross-agent independence

*Single source, including the fallback. `.ai/MANAGER.md` § 9 points here.*

Preferred: the reviewer is a **different model** from the implementer — a
different vendor, or a different model of the same vendor — in a fresh context.
The report names both models (`.ai/REPORTING.md` § *Chat report*, the
`Models` line); an unnamed reviewer is not an independent one.

If no other model is available, spawn a fresh reviewer of the same model
without the implementer's reasoning history and label the result
`FALLBACK REVIEW`. A fresh context of the same model is distance, not
independence, and the report must not present it as the latter.

## Resolution

- Critical finding → must resolve before merge.
- Major finding → resolve or provide strong evidence that it is invalid.
- Minor finding → fix when low-cost and clearly beneficial; otherwise record.
- After correction, rerun the smallest evidence that proves the fix.

Reviewer PASS alone never replaces compile/test/build/runtime evidence.
