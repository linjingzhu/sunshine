---
doc_id: ai-review
version: 1.1.0
canonical_path: .ai/REVIEW.md
updated: 2026-08-23
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
- requirement coverage,
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

## Risk levels

### LOW
Examples: copy, tooltip text, isolated low-impact tests, tiny safe UI adjustment.

Default:
- implementer self-review,
- deterministic check,
- no fresh cross-agent review unless signals indicate risk.

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
- prefer opposite-family reviewer (Claude ↔ Codex).

## Cross-agent independence

Preferred:
- Claude implementation → Codex review
- Codex implementation → Claude review

If the opposite family is unavailable, spawn a fresh reviewer of the same family without the implementer's reasoning history.

## Resolution

- Critical finding → must resolve before merge.
- Major finding → resolve or provide strong evidence that it is invalid.
- Minor finding → fix when low-cost and clearly beneficial; otherwise record.
- After correction, rerun the smallest evidence that proves the fix.

Reviewer PASS alone never replaces compile/test/build/runtime evidence.

**A finding is a hypothesis with evidence attached, not a verdict.** Reproduce
every consequential finding against the tree before acting on it or relaying it
— including findings that favour caution, and including your own. A CRITICAL
has already been raised in this repository against a parser that a
higher-precedence check rejects first; relaying it unverified would have
escalated a non-issue to a merge blocker.

**Review is the only thing that has caught an unreachable feature here.** No
compiler, guard, test or build did. Weight adversarial review accordingly on any
change that adds a branch to code someone else decides whether to call.
