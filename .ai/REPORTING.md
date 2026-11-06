---
doc_id: ai-reporting
version: 1.2.0
canonical_path: .ai/REPORTING.md
updated: 2026-11-02
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

Requirements Checklist
<link to the checklist page, or the full table when there is no page>

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

## Requirements checklist

From the user's first request in a conversation, the Manager keeps one
checklist of everything the user has asked for, and keeps it current until the
conversation ends. A request answered in prose and then lost in the scrollback
is the failure this prevents: the user should never have to re-read the
conversation to learn what is done, what is waiting on them, and what was
dropped.

It belongs to the user's conversation, not to a Manager context: a Manager
that takes over after a context reset continues the same checklist, at the same
address and with the same numbers — its address, or the full table when it
has no page, is part of the state card (`.ai/CORE.md` § *Token discipline*).

It is a table with these four columns, in this order:

| No. | Requirement | Needs confirmation | Status |
|---|---|---|---|
| 1 | <the request, in the user's words or a one-line faithful paraphrase> | <the decision the user must take before it can finish, or `—`> | <status> |

- **No.** is assigned in the order the requests arrive and never reused or
  renumbered. A request split into parts gets sub-numbers (`3.1`, `3.2`).
- **Needs confirmation** names the decision, not a reminder to "check". A
  decision taken moves into the requirement's row as its answer, dated.
  Anything § *Owner ledger* covers — accounts, DNS, payments, external
  registrations, approvals — stays in the ledger: the cell names the ledger
  row id instead of restating the item.
- **Status** is one of `open`, `in progress`, `waiting on user`, `done`,
  `dropped`. `done` carries its evidence in the same cell — the merged pull
  request, the verification that ran, or the reply that answered a question —
  and `dropped` carries the reason and who decided it. A row is `done` only on
  that evidence, by § *Truthfulness*. A row held up by a ledger item is
  `waiting on user` and names the row id; how far that item has got is said in
  the ledger only.

The column headers and status values are written in the language the user
writes in, translated with the meanings above; the requirement and
confirmation cells too.

Where it lives: when the harness can publish a page the user opens outside the
terminal (an artifact), the checklist is that page — one per conversation,
updated in place at the same address, never a new page per update — and a
reply that changes a row links to it. With no such page, the full table is
part of every reply that adds or changes a row, the chat report included.
Either way it is updated before that reply is sent.

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
