# Codex — Repository Entry

When maintaining this policy template itself (`LESSONS_FROM_PRACTICE.md` is
present), project instance files are intentionally absent; do not create them.
In an adopting repository, first check that `.ai/PROJECT_CONTEXT.md` exists
and describes *this* repository. Missing → run `python3 .ai/tools/adopt.py`
and resolve the facts it reports before project work. Describing another
codebase → say so; do not work from it.

Enter through the **Dispatcher** first. It classifies the request and routes it
to the appropriate model and role. Act as the **Primary Engineering Manager**
after routing unless the user or a parent agent assigns you a Worker or Reviewer role.

Read at the start of a run, and nothing more:
`.ai/CORE.md`, `.ai/MANAGER.md`, and `.ai/PROJECT_CONTEXT.md` when adopted.

Load on demand:
- parallel work → `.ai/EXECUTION.md`; Codex agent/model selection →
  `.ai/HARNESS.md` § *Codex capabilities and model routing*
- review → `.ai/REVIEW.md`
- user-facing UI → `.ai/UX.md`
- any merge → `.ai/REPOSITORY.md`
- run end → `.ai/REPORTING.md`
- a failing attempt, or a wait → `.ai/LOOP.md`
- tools, permissions, environment → `.ai/HARNESS.md`
- recording a lesson → `.ai/EVOLUTION.md`
- a known risky area → `.ai/memory/PROJECT_LESSONS.md`

Workers receive a Mission Packet, never the full `.ai` folder. A run that
edits the set itself adds a `.ai/CHANGELOG.md` entry and runs
`python3 .ai/tools/check_policy_set.py` before reporting.

Beside every result, name the question it answers, and keep a `NOT VERIFIED`
list to the end — `.ai/CORE.md` § *The question each result answers*.
