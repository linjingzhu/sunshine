---
doc_id: ai-reporting
version: 1.1.0
canonical_path: .ai/REPORTING.md
updated: 2026-08-17
---

# Formal Development Reporting

The Manager reports once per meaningful run. Worker logs are internal unless
requested.

## Operating mode: silent execution, final report

Think fully. Investigate fully. Verify fully. Report minimally.

The cost being removed is the cost of re-narrating work already done, not the
work itself. Three rules make that distinction non-negotiable:

> Suppress progress reporting, not necessary decision escalation.
> Minimize report generation, not evidence acquisition.
> Less reporting is not less verification.

Do not produce text that contributes nothing to a decision, an item of evidence,
a risk, or the result.

### Manager to user

During normal execution the count is: **progress reports 0, final report 1.**

Announcing a start, a repository read, a structure confirmation, a test run, a
passing test, a PR, a CI check, a conflict check or a merge is execution
telemetry, not communication. Do not emit it.

Escalate immediately, without waiting for the final report, when and only when:

- **A user decision is required** — no reasonable default exists.
- **A critical risk appears** — data loss, credential or secret exposure, a
  serious security problem, an irreversible change, a significant production
  regression, or possible destruction of the repository or a deployment.
- **Mission scope must change** — the approved goal, product behaviour, security
  boundary, data model, or an important external contract has to differ.

Ordinary implementation choices and internal scope adjustments are the Manager's
own to make.

### Worker to Manager

State, evidence, result. Not a narrative of the route taken.

```text
STATUS: PASS
FILES: 3
TESTS: 12/12
```

Add `BLOCKER`, `RISK`, `EVIDENCE`, `DECISION` or `ASSUMPTION` only when one
applies. The fields are not a fixed schema; return what is real. Do not repeat
context already shared or anything the Manager can read directly.

A decision, assumption or risk that affects future implementation, integration
or maintenance is never dropped to save tokens.

### Reviewer

Do not restate the implementation. Clean:

```text
STATUS: PASS
ISSUES: 0
```

Otherwise, per finding: `SEVERITY`, `LOCATION`, `ISSUE`, `EVIDENCE`.

```text
MAJOR
LOCATION: src/session.ts:84
ISSUE: malformed UUID accepted
EVIDENCE: format validation missing
```

Shorter reports, identical review depth.

### Tests and validation

```text
STATUS: PASS
TESTS: 41/41
LINT: PASS
BUILD: PASS
```

On failure, add only what diagnoses it:

```text
STATUS: FAIL
FAILED: workspace_restore_duplicate_id
EVIDENCE: duplicate runtime UUID accepted
```

Printing less of a log is not reading less of it. Investigate source, diffs,
logs, stack traces and CI output as far as the problem requires.

### What suppression may never touch

Source and diff investigation, log analysis, tests, lint, build verification,
regression validation, adversarial review, security review, PR and CI gates,
conflict checks, merge criteria, integration verification, and any tool or agent
communication the work actually needs.

> Reporting suppression MUST NOT reduce engineering rigor.

### Noise versus material history

Do not report transient execution noise: a command that succeeded on retry, an
intermediate attempt with no bearing on the result, a repeated healthy state.

Preserve in the final report: a failure that changed the design, an architecture
discovery, a security, credential or data risk, a significant regression, a
workaround, technical debt, and any decision that affects future maintenance.

### Flow

```text
Workers / Reviewers / Tests  ->  compressed result + evidence
                             ->  Primary Manager
                             ->  one human-oriented final report
```

The forbidden shape is a worker summary that the reviewer restates, the Manager
restates again, and the user receives a fourth time.

## Status vocabulary

- `COMPLETED`
- `COMPLETED_WITH_NOTES`
- `ACTION_REQUIRED`
- `FAILED`

## Chat report

Report length is proportional to mission complexity. A small task needs only:

```text
COMPLETED
- Updated: ...
- Validation: PASS
```

At minimum a final report carries the actual changes, the verification result,
and any unresolved risk. PR, commit, merge and next-step lines appear only when
they are actually needed. Do not replay the work log; stop at what the user
needs in order to decide what happens next.

For a substantial run the fuller form is available, and no section is mandatory
when it has nothing to say:

```text
DEVELOPMENT REPORT

Status:
Repository:
Repository Mode:
Integration:

Executive Summary
<what was delivered and overall result>

Delivered
- ...

Verification
- Compile:
- Tests:
- Windows Build:
- Runtime/Visual:
- Adversarial Review:
- Cross-Agent Review:
- Git Conflicts:

Problems Found & Automatically Fixed
- severity — problem → resolution

Remaining Risks
- ...

Efficiency / Meta Evaluation
- workers / mission packs
- conflict/rework observations
- token/time metrics only when reliably available
- strategy lesson, if any

Recommended Next Actions
1. ...
2. ...
3. ...
```

Do not list actions the AI could have safely completed itself.

## Persistent detailed report

When a run is substantial or creates useful engineering history, write a detailed report under:

```text
.ai/reports/YYYY-MM-DD-<short-run-name>.md
```

Keep persistent reports factual and concise.

## Truthfulness

Never claim:
- a build passed if it was not run;
- runtime/visual verification passed if the UI was not observed;
- cross-agent validation happened if only one agent family reviewed;
- exact token/cost numbers if they were not measured.

Use `NOT RUN`, `NOT AVAILABLE`, or `FALLBACK REVIEW` explicitly.
