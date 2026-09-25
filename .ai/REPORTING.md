---
doc_id: ai-reporting
version: 1.1.0
canonical_path: .ai/REPORTING.md
updated: 2026-09-03
---

# Formal Development Reporting

The Manager reports once per meaningful run. Worker logs are internal unless requested.

## Status vocabulary

- `COMPLETED`
- `COMPLETED_WITH_NOTES`
- `ACTION_REQUIRED`
- `FAILED`

## Chat report

Keep the user-facing report compact and formal:

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
- Target Build:
- Runtime/Visual:
- Adversarial Review:
- Cross-Agent Review:
- Models: <implementer> / <reviewer>
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

Owner Actions
- <ledger row id> — <one line>, status

Recommended Next Actions
1. ...
2. ...
3. ...
```

Do not list actions the AI could have safely completed itself.

## Owner ledger

Work only the user can do — accounts, DNS, payments, external registrations,
approvals — lives in **one** file per repository, the `owner_ledger` named in
`.ai/PROJECT_CONTEXT.md` § *Facts the checks read*: one row per item,
with a stable id and a status. Reports, milestones and other documents cite
the row id; they do not restate its status. Two places that both say what the
user still has to do will disagree within a week.

## Persistent detailed report

Write one for any run that merges a pull request, changes a row in the owner
ledger, or ends `FAILED`; other runs may have one. It goes under:

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
