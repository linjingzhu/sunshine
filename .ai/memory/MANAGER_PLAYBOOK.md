---
doc_id: ai-manager-playbook
version: 1.1.0
canonical_path: .ai/memory/MANAGER_PLAYBOOK.md
updated: 2026-09-03
---

# Portable Manager Playbook

Purpose: carry **generalized development strategy experience** across projects without carrying project-specific code assumptions.

Keep entries short.

## Promotion rule

A lesson here is one of two things, and never a third:

- `candidate` — observed, not yet broadly validated. It lives here.
- `verified` — repeatedly useful in comparable contexts without quality
  regression. **It is written into the policy set and removed from here.**

That second half is the whole point of the file. A verified lesson that stays
here becomes a second copy of a rule that already exists in `.ai/`, and the two
copies drift. When you promote, move it — do not leave a summary behind.

Do not promote a one-project observation into a universal rule.

## Current lessons

None. The three seed lessons this file shipped with — conflict prevention beats
conflict resolution, reuse context rather than stale sessions, detect defects
early — were all promoted: they are `.ai/EXECUTION.md` § *Conflict prevention*
and § *Session strategy*, `.ai/CORE.md` § *Token discipline*, and the compile
and build ladder. Keeping them here as well was the duplication this rule now
forbids.

An empty file is the honest state. Add a candidate when a run produces one.

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

When moving this playbook to a new project, preserve only reusable lessons. Project-specific paths and workarounds belong in `PROJECT_LESSONS.md`.
