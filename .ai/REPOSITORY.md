---
doc_id: ai-repository
version: 1.0.0
canonical_path: .ai/REPOSITORY.md
updated: 2026-08-13
---

# Repository and Merge Policy

## Repository mode

`.ai/PROJECT_CONTEXT.md` may set:

```text
repository_mode: auto | personal | protected
```

### auto

Treat the repository as **protected** when it clearly identifies the CLO/Marvelous repository, including:
- repository name exactly `Marvelous`, or
- Git remote clearly ending in/identifying `Marvelous.git`.

If that is a false positive for a personal project, set `repository_mode: personal`.

Otherwise treat it as personal.

### personal

After required quality gates pass:
- autonomous commits: allowed;
- central integration: allowed;
- merge to the configured local base branch: allowed;
- push to remote: do not assume; follow user instruction or established repository workflow.

### protected

For CLO/Marvelous or any repository explicitly marked protected:
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

## Dirty/uncertain state

Do not overwrite or discard user changes.

If the base worktree contains unrelated uncommitted changes:
- preserve them;
- use an isolated worktree/branch when possible;
- avoid destructive cleanup.

## Git objective

Optimize for **conflict prevention**, not clever conflict resolution.

Use:
- exclusive ownership,
- shared-interface sequencing,
- hotspot awareness,
- early integration,
- smaller integration waves.
