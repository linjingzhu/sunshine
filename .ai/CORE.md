---
doc_id: ai-core
version: 1.3.0
canonical_path: .ai/CORE.md
updated: 2026-08-23
---

# Core Development Constitution

These rules are the stable quality floor. Execution strategy may adapt; these rules do not.

## Priority

1. Correctness
2. User intent and product value
3. Regression and data safety
4. UX/usability
5. Git conflict prevention
6. Delivery speed
7. Token/cost efficiency
8. Architectural elegance

Never reduce the quality floor merely to improve token, time, or worker-count metrics.

## Autonomy

Default to autonomous execution.

Do not ask the user to approve routine choices that can be resolved through:
1. repository conventions,
2. existing implementation,
3. evidence,
4. the smallest reversible safe choice.

Ask only when a decision materially changes product scope, creates irreversible external impact, requires secrets/credentials, incurs external cost, or requires accepting meaningful legal/security risk.

## Implementation

- Reuse existing architecture before adding new abstractions.
- Prefer the smallest safe diff.
- Avoid duplicate implementations and unnecessary dependencies.
- Preserve backward compatibility unless the task explicitly changes it.
- Fix confirmed task-adjacent defects when the fix is small, safe, and clearly related.
- Split unrelated discoveries into follow-up work instead of expanding scope silently.
- Never treat "code written" as "feature complete."

## Token discipline

Optimize **useful development per token**, not session count.

- Do not repeatedly rediscover the same subsystem.
- Reuse context within a run when tasks are strongly related.
- Prefer compact Mission Packets over full policy reloads.
- Prefer path/symbol/diff-focused investigation over whole-repository rereads.
- Do not duplicate the same research across workers.
- Reviewers receive requirements, diff, tests, and relevant context—not the implementer's full reasoning history.
- Do not fabricate exact token/cost metrics when tooling does not expose them.
- Default to silent execution: no progress narration, one final report. Escalate
  immediately only for a required user decision, a critical risk, or a change to
  approved scope. See `.ai/REPORTING.md`.
- Think fully, investigate fully, verify fully, report minimally. Suppressing a
  report never suppresses the evidence behind it.

## Document versioning

Policy documents carry a version; their filenames and paths do not. The rule is
**stable identity, mutable version**: a document's identity is its `doc_id` and
its canonical path, and neither moves because its contents changed.

Every policy document opens with exactly this metadata and nothing more:

```text
---
doc_id: ai-manager
version: 1.0.0
canonical_path: .ai/MANAGER.md
updated: 2026-08-17
---
```

- `doc_id` is permanent. It survives edits, rewrites, and a move. Change it only
  when the document's responsibility changes enough that it is a different
  document, which is rare enough to be worth arguing for.
- `canonical_path` is the one address other documents may use.
- `version` is `MAJOR.MINOR.PATCH`, judged by policy impact, never bumped
  mechanically:
  - **PATCH** — wording, typos, clearer examples. Behaviour is unchanged.
  - **MINOR** — a new rule or an extended behavioural contract that leaves the
    existing structure intact.
  - **MAJOR** — a break in Manager or Worker responsibility, the execution
    contract, or integration ownership. Anything an agent following the previous
    version would now get wrong.
- `updated` is the date of the last meaningful change, not of the last commit
  that touched the file.

Append-only memory (`.ai/memory/PROJECT_LESSONS.md`) and run reports
(`.ai/reports/`) carry no version. Appending a lesson is not a policy revision,
and versioning an immutable record says nothing.

### Reference stability

> Document references MUST use stable canonical paths or stable `doc_id`.
> Never reference a document by versioned filename.
> A version change MUST NOT require reference updates unless the document's
> responsibility or canonical location actually changes.

Versioned filenames — `MANAGER_v2.md`, `EXECUTION_1.3.0.md` — are prohibited.
They put the version in the one place every other document has to know, so a
version bump becomes an edit to every file that cites it.

Renaming or moving is a separate act from versioning, and never a consequence of
it. When a canonical path genuinely must change: find every existing reference
first, update `canonical_path`, keep the `doc_id`, and verify no stale reference
survives. `scripts/validate_doc_metadata.py` enforces all of this and runs in
CI, so a broken reference fails the build rather than waiting to mislead an
agent.

### Versioning is not reporting

This changes what is tracked, not what is said. The reporting contract in
`.ai/REPORTING.md` is unchanged -- one report per meaningful run, worker logs
internal -- and versioning adds nothing to it: do not announce version bumps, do
not recite metadata, and do not accumulate change logs inside the documents. Git
history is the source of truth for how a document got here; the metadata only
says where it is now.

## Build platform

- Windows is the default build platform.
- Do not perform a macOS build unless the user explicitly requests it.
- Platform analysis is allowed; actual macOS build execution is not a default action.

## Quality evidence

Whenever technically applicable, completion should be supported by deterministic evidence such as:
- compilation,
- static/type checks,
- tests,
- targeted Windows build,
- runtime verification,
- visual verification.

AI agreement is not a substitute for evidence.

**Each item above proves one claim, not the next one.** A compile proves the
code is valid, not that it is reachable; a passing guard proves the rule it
encodes, not the rule you meant; a green build proves nothing about behaviour.
State which claim the evidence supports and leave the others in NOT VERIFIED.

This is not caution for its own sake. A feature has already shipped in this
repository that compiled, passed every guard, built green, and could not serve
a single byte, because the dispatcher branch it added was never reachable.
