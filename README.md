# AI Engineering Manager MD Kit

A lightweight repository policy kit for using **Claude Code** and **Codex** as an autonomous AI development team.

The kit is intentionally Markdown-first. It does not require a custom orchestrator service.

## Install

Unzip/copy this package into the **repository root**, then commit the policy files before starting parallel work or worktrees.

```text
your-repo/
├─ CLAUDE.md
├─ AGENTS.md
├─ AI_DEVELOPMENT_MANUAL.html
└─ .ai/
   ├─ CORE.md
   ├─ MANAGER.md
   ├─ EXECUTION.md
   ├─ REVIEW.md
   ├─ UX.md
   ├─ REPOSITORY.md
   ├─ REPORTING.md
   ├─ PROJECT_CONTEXT.md
   ├─ memory/
   │  ├─ MANAGER_PLAYBOOK.md
   │  └─ PROJECT_LESSONS.md
   └─ reports/
```

## How it works

- `CLAUDE.md` is the Claude Code entry point.
- `AGENTS.md` is the Codex entry point.
- The main session acts as the **Primary Engineering Manager**.
- The Manager creates compact **Mission Packets** for workers instead of making every worker reread the whole `.ai` folder.
- Related tasks are grouped into Mission Packs to reuse context.
- Worker count is dynamic, based on useful parallelism rather than a fixed number.
- Workers do not merge each other. The Manager owns central integration.
- Git conflict risk, compilation, tests, Windows build, runtime/visual UX, and adversarial review are checked as early as practical.
- Personal repositories may auto-merge after required gates pass.
- CLO/Marvelous repositories are treated as protected and are not auto-merged to the protected base.
- Run results are summarized in a formal Development Report.
- Project-specific lessons and portable Manager strategy lessons are kept separately.

## Important

Do **not** instruct every worker to read every policy file. The main Manager reads the core policy once per run and passes only a compact Mission Packet to workers.

Read `AI_DEVELOPMENT_MANUAL.html` for the full operating manual.
