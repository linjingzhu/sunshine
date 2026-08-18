---
doc_id: ai-manager-playbook
version: 1.0.0
canonical_path: .ai/memory/MANAGER_PLAYBOOK.md
updated: 2026-08-13
---

# Portable Manager Playbook

Purpose: carry **generalized development strategy experience** across projects without carrying project-specific code assumptions.

Keep entries short.

## Promotion rule

A lesson may be:
- `candidate` — observed but not broadly validated;
- `verified` — repeatedly useful in comparable contexts without quality regression.

Do not promote a one-project observation into a universal rule.

## Seed lessons

### MP-001 — Conflict prevention beats conflict resolution
status: verified  
scope: general

Strategy:
- establish exclusive write ownership before parallel work;
- serialize shared hotspots/interfaces;
- integrate hotspot changes early.

Reason:
Late conflict resolution creates rework, context reload, and merge risk.

### MP-002 — Reuse context, not stale sessions
status: verified  
scope: general

Strategy:
- reuse Workers for cohesive work within a run;
- end Worker contexts at run/domain boundaries;
- carry compact facts forward instead of raw reasoning history.

### MP-003 — Detect defects early
status: verified  
scope: general

Strategy:
- compile/build incrementally;
- measure late compile/build/visual discoveries as process failures;
- move verification earlier when the same defect class repeats.

## Candidate lesson template

```text
### MP-XXX — <title>
status: candidate
scope: <general / cpp / web / game / ...>

Observation:
- ...

Strategy hypothesis:
- ...

Evidence:
- comparable projects/runs: N
- quality regression: none / observed
- conflict/time/token effect: measured/unknown

Confidence:
- low / medium / high
```

When moving this playbook to a new project, preserve only reusable lessons. Project-specific paths and workarounds belong in `.ai/memory/PROJECT_LESSONS.md`.
