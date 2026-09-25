---
doc_id: ai-project-context
version: 1.1.1
canonical_path: .ai/PROJECT_CONTEXT.md
updated: 2026-09-03
---

# <Project> Context

> **This is a template.** Copy it to `.ai/PROJECT_CONTEXT.md`, fill it in, and
> delete every instruction line like this one. Keep `doc_id` and
> `canonical_path` as they are — the set addresses this document by them.

The only file in `.ai/` allowed to know what the project is; every other
document survives being copied elsewhere because this one exists. Keep it a
routing map a run can read in one breath.

## repository_mode

```text
repository_mode: auto | personal | protected
```

`.ai/REPOSITORY.md` § *Repository mode* reads this line and nothing else to
decide merge authority, and defines what each of the three values means. Do not
restate the definitions here — this section is the value, not the rule.

Set it deliberately. It is the one line that decides whether an agent may
complete a merge on its own.

## Facts the checks read

> One `key: value` per line, inside this one fenced block. The *project
> context* check in `.ai/tools/check_policy_set.py` refuses an instance that
> leaves a key out, leaves a `<placeholder>` in, or still carries a line from
> this template. Several entries go on one line separated by `;`. `none` is a
> value; an empty value is not.

```text
base_branch: <branch>
merge_deploys: yes | no
runtime_gate: <command that observes the running product, or none>
test_command: <command>
lint_command: <command, or none>
build_command: <command, or none>
generated: <artefact ← source : regenerate command; ...> or none
external_scripts: <host : condition under which it loads; ...> or none
public_ids: <identifiers that may be committed; ...> or none
owner_ledger: <path of the one file listing work only the user can do>
```

Who reads each fact: `merge_deploys` → `.ai/REPOSITORY.md` § *Merge and
deploy*; `runtime_gate` → `.ai/UX.md` § *Runtime/visual gate*; the three
commands → the compile and build ladder and every report; `generated` →
`.ai/CORE.md` § *Generated artefacts*; `external_scripts`, `public_ids` →
`.ai/CORE.md` § *Public identifiers and secrets*; `owner_ledger` →
`.ai/REPORTING.md` § *Owner ledger*.

## Authoritative product constraints

> What the product **is**, and what it is **not**. Write the exclusions too —
> an excluded option that is not written down gets re-proposed every few weeks.

- …

## Current architecture

> The shape a new session needs before it can act: where the source of truth
> lives, what builds what, which layer owns which decision.

- …

## Current development slice

> What is being built **now**. Keep it short enough that it is worth updating.

- …

## Permanently excluded scope

> Decisions already taken against. Naming them here is what stops them
> returning through a roadmap or a speculative implementation.

- …
