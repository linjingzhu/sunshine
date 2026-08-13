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
