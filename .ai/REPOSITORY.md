---
doc_id: ai-repository
version: 1.1.0
canonical_path: .ai/REPOSITORY.md
updated: 2026-09-03
---

# Repository and Merge Policy

## Repository mode

`.ai/PROJECT_CONTEXT.md` sets the mode, and this file reads that line and
nothing else:

```text
repository_mode: auto | personal | protected
```

### auto

`auto` is a fallback, not a decision. It exists so that an unconfigured
repository fails safe, and it is expected to be replaced by an explicit value.

Treat the repository as **protected** when any of these hold:
- the remote belongs to an organisation rather than to the current user;
- the base branch is protected, or the workflow requires review before merge;
- other people's commits appear in recent history of the base branch;
- `.ai/PROJECT_CONTEXT.md` is missing, so the mode was never decided.

Otherwise treat it as personal.

Do not encode a specific organisation or repository name here. A repository
that must always be protected says so in its own `.ai/PROJECT_CONTEXT.md` with
`repository_mode: protected`; that line travels with the repository, this file
travels between them.

### personal

After required quality gates pass:
- autonomous commits: allowed;
- central integration: allowed;
- merge to the configured local base branch: allowed;
- push to remote: a feature branch and a draft pull request are allowed;
  pushing to the base branch itself is a merge, and § *Merge and deploy*
  applies.

### protected

For any repository marked protected, or resolved to protected by `auto`:
- autonomous implementation: allowed;
- feature/task commits: allowed;
- isolated branches/worktrees: allowed;
- integration branch: allowed;
- merge to the protected base branch: **not allowed without explicit user action/instruction**;
- push/PR behavior follows the repository's established workflow.

## Merge authority

Workers never own final merge authority.

The Primary Manager:
1. confirms required gates;
2. checks integration/conflict risk;
3. integrates in dependency-aware order;
4. reruns affected verification;
5. applies repository mode.

## Branch lifecycle

- One branch per pull request. When the pull request has merged — squash or
  otherwise — the branch is finished. The next piece of work starts from a
  fresh branch off the base:

  ```bash
  git fetch origin <base> && git switch -C <branch> origin/<base>
  ```

  Never rebase or merge the base into a branch whose pull request was
  squash-merged; the two histories no longer share those commits, and the
  result is a pull request that shows work already merged.
- A pull request opens as a **draft** with a Verification section, and is
  marked ready when its gates are green.
- A commit touches at most twenty files, generated artefacts excluded.
  Work-in-progress checkpoints are squashed before they are pushed.
- Nothing produced by tooling — screenshots, uploads, scratch output — is
  committed outside the directory the project context names for it. A file
  that appears at the repository root with no owner is a defect.

## Merge and deploy

`.ai/PROJECT_CONTEXT.md` § *Facts the checks read* says whether merging to the
base branch publishes (`merge_deploys: yes`). When it does:

- a change the user can see is shown to the user — a screenshot at the
  widths the product serves, or a preview — and approved **before** it merges,
  unless the project context records a standing approval;
- during an external review window the project context names (an ad network,
  a store, a certification), merges are limited to fixes;
- a merge is confirmed by the deploy's completion, looked up once, not by the
  merge itself.

When it does not, merging is the ordinary integration step and deployment is a
separate, named action.

## Dirty/uncertain state

Do not overwrite or discard user changes.

If the base worktree contains unrelated uncommitted changes:
- preserve them;
- use an isolated worktree/branch when possible;
- avoid destructive cleanup.

## Git objective

Optimize for **conflict prevention**, not clever conflict resolution. A conflict
resolved well still cost a rework cycle that a Conflict Map would have avoided.

The techniques — exclusive ownership, shared-interface sequencing, hotspot
awareness, early integration, smaller waves — are `.ai/EXECUTION.md` §
*Conflict prevention*. This file only insists that the repository is worked that
way.
