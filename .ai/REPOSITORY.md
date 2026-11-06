---
doc_id: ai-repository
version: 1.3.0
canonical_path: .ai/REPOSITORY.md
updated: 2026-11-06
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
  marked ready when its gates are green. Its title and body follow the
  repository's own conventions — its pull request template, contribution
  guide, code owners and any check that lints titles — read from the remote
  base, not from a local checkout that may be stale. What the diff cannot
  show, such as a test result or a screenshot, is written as not run, never
  invented.
- A commit touches at most twenty files, generated artefacts excluded.
  Work-in-progress checkpoints are squashed before they are pushed.
- Nothing produced by tooling — screenshots, uploads, scratch output — is
  committed outside the directory the project context names for it. A file
  that appears at the repository root with no owner is a defect.

### The local base branch is a mirror

The checkout of the base branch tracks the remote and holds nothing of its
own. Feature work happens on feature branches, so syncing it is only ever
fast-forward:

```bash
git fetch origin <base>
git switch <base>
git merge --ff-only origin/<base>
```

**A sync that cannot fast-forward stops and reports.** It does not resolve
itself. A plain `git pull` in that situation writes a merge commit recording a
divergence nobody intended, on the one branch whose history everything else is
cut from — and the commit looks deliberate afterwards. Non-fast-forward there
means something is true that the run does not yet know.

### Deleting a branch

A branch is deleted only when every one of these holds: its work is committed,
the gates it needed have passed, it is merged into its parent, and that parent
actually contains the commits — or, for a pull request merged by squash, whose
commits the parent never contains, its remote branch still holds exactly this
branch's commit, which is what `-d` then compares against.

```bash
git branch -d <branch>
```

`-d` is the check, not the convenience: it refuses a branch whose commits are
not in the history it is being deleted from. **Automation never uses `-D`** —
it deletes exactly the branch the check would have saved, and it is silent
about it. A `-d` that refuses is answering a question worth asking; the answer
is to find out why, not to reach for the capital letter.

Deleting a branch the run did not create is the user's decision, not a
cleanup.

### Cleaning up after a merge

What a run created for a piece of work — its worktree, its local branch, its
remote branch — is removed by that run once the work has merged, so the next
run does not mistake it for work in progress (`.ai/EXECUTION.md` §
*Resuming interrupted work*). Everything else it finds is listed in the report
and left alone.

Read before removing anything, and remove nothing the reading flags:

- `git status` and the commits not on the remote, in every worktree to be
  removed. Uncommitted changes or unpushed commits mean work that exists
  nowhere else: stop and report them.
- Whether the pull request merged, and whether anyone pushed to its branch
  after the merged head. Deleting the remote branch of an open pull request
  closes it.

Never removed by a cleanup: the base branch, the main worktree, the worktree
the run is standing in, a locked worktree, and anything the run did not
create.

- **Worktree** — `git worktree remove <path>` without `--force`. A refusal
  means something in it is not committed; report it rather than force it.
  Only an untracked build directory may be deleted first (`.ai/EXECUTION.md`
  § *Worktrees and branches*); a directory holding a tracked file is source,
  whatever its name.
- **Local branch** — after its worktree and before its remote branch, by
  § *Deleting a branch*. After a squash merge, `-d` accepts it only while the
  remote branch still holds the same commit; once that is gone, `-d` refuses,
  and the branch is kept and listed with its commit — never `-D`.
- **Remote branch** — last, once its pull request has merged and nobody pushed
  after the merged head.

The report names each item removed with the commit it pointed to, which is
how it comes back (`git branch <name> <commit>`, then push), and each item
kept with the reason.

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

### Paid automation

GitHub Actions or any hosted automation that can incur charges is prohibited
by default. It may run only after the owner explicitly approves the exact
workflow, repository scope, provider, expected maximum cost, and an expiry or
review date. Record that approval in the repository's owner ledger before
enabling it. A free-tier estimate is not proof that a run is cost-free; treat
uncertain billing as paid. Do not use Actions minutes, hosted runners,
artifacts, caches, Pages, packages, or third-party actions with metered usage
without this approval. A workflow must fail closed when its budget or expiry
cannot be verified.

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
