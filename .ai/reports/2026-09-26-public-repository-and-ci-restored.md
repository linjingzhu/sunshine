# Public repository, and the CI that came back with it

Status: COMPLETED_WITH_NOTES
Repository: linjingzhu/sunshine
Repository Mode: protected
Integration: `stable`

## Executive summary

The owner made the repository public and said to use Actions freely. The one
reason this project's CI had been dying — an account-level hosted-runner
allowance on a *private* repository, which produced two-to-four-second jobs with
no runner, no step and no log from 2026-09-08 — does not apply to a public one.
All four workflows are restored from history, and the guard that makes a
self-hosted runner safe on a public repository is restored with them.

This reverses most of yesterday's report
(`.ai/reports/2026-09-25-policy-checker-retirement.md`), which documented the
same repository with no CI at all. Both are accurate for their day; this one is
current.

## Delivered

- Restored `architecture-guard-hosted.yml`, `architecture-guard-self-hosted.yml`,
  `native-chromium-windows.yml`, `patch-apply-hosted.yml` from
  `8db494a^` and `888d2a9^`.
- Restored `tests/test_windows_build_contract.py` from `397df8e^`: the fork-event
  list, the comment-stripping `runs_self_hosted()` predicate, the rule that no
  self-hosted workflow is reachable from `pull_request`, `pull_request_target`,
  `issue_comment` or `workflow_call`, that predicate's own injection test, and
  the two test classes the policy adoption had deleted. The file had been
  replaced with a single assertion that no workflow exists.
- Added `test_every_push_is_watched_by_something_hosted`: some hosted workflow a
  push triggers must run the test command. Written for a failure that actually
  happened — `stable` was red for a day and nothing said so.
- Restored the workflow half of `test_ci_checks_tab_and_window_extra_data_separately`.
- `.ai/reports/OWNER_ACTIONS.md` rewritten into the row-per-item shape
  `.ai/REPORTING.md` § *Owner ledger* requires; it had been prose.
- `docs/WINDOWS_CHROMIUM_BUILD.md` corrected for the second time in two days:
  both ways of starting a build, the runner's safety argument on a public
  repository, and the `queued`-run troubleshooting that is load-bearing again.

## The safety question, stated because it is the one that matters

**A self-hosted runner on a public repository is the arrangement GitHub tells
you not to make.** A fork can open a pull request that runs its own code on the
machine. What makes it safe here is that both self-hosted workflows are
`workflow_dispatch:` and nothing else, so only an account with write access can
start them — and that is enforced rather than observed:
`test_no_self_hosted_workflow_is_reachable_from_a_fork` reads `runs-on:` (not
the word appearing in a comment) and fails on any of the four fork-reachable
events. Verified now: the two self-hosted workflows are detected as such, the
two hosted ones are not, and none carries a fork-reachable trigger.

## Verification

- Compile: NOT RUN — nothing here compiles Chromium.
- Tests: 986 pass, 11 skipped. 975 before; the 11 are the restored guard.
- Guards: every `scripts/verify_*.py` and `validate_*.py`, plus
  `.ai/tools/check_policy_set.py` (7/7).
- Patch stack: all 32 patches apply to pinned `152.0.7977.42`
  (`verify_pinned_upstream.py --source github`).
- **CI itself: MEASURED, AND IT DOES NOT RUN.** The push carrying this
  (`920e5a7`) produced no workflow run, and `list_workflows` returns zero. The
  newest run in the repository is still 2026-09-24. **Making the repository
  public does not re-enable Actions** — the 2026-09-25 setting persists through
  the visibility change, so the restored workflow files currently do nothing.
  That is OA-2 and only the owner can clear it.
- Target Build / Runtime / Visual: NOT RUN.
- Cross-Agent Review: NOT AVAILABLE — one agent family.

## Remaining risks

- **The split hover widget and link mode have still never been compiled**
  (patches 0027, 0031, 0032). RV-69 to RV-74 unrun. OA-4.
- `scripts/compile_check_installer.py` still has no automated home: it needs
  mingw, which the build machine does not have, so only a hosted runner can
  install it. It has never run in CI. Wiring it into the restored hosted guard
  is worth doing and is not done here.
- The repository is public, so the patch stack, the contracts and every report
  are now readable by anyone. No secret is in the tree —
  `SUNSHINE_ACCOUNT_CLIENT_ID` arrives from the pipeline and
  `scripts/verify_account_freedom.py` refuses a literal — but the change is
  worth stating rather than assuming.
- Restoring four workflows re-creates four ways to spend the owner's machine
  and GitHub's runners. Only the two hosted ones start by themselves — and none
  of them starts at all until OA-2 is cleared.
- **The title of this report is half wrong and is left as written.** The CI is
  restored in the tree and is not running; the measurement above says so. It is
  not renamed because a report that quietly matches its own findings after the
  fact is worth less than one that shows where its author was ahead of the
  evidence.

## Owner actions

- OA-1 DONE, OA-2 to confirm on the next push, OA-3 and OA-4 open.

## Recommended next actions

1. **Clear OA-2 first, because nothing else here works until it is.** Settings →
   Actions → General → *Allow all actions and reusable workflows* → Save. Any
   push after that should produce two runs; this one produced none.
2. Start the self-hosted runner (OA-3), then dispatch **Native Chromium Windows
   Build**. That is the answer to "러너 실행" and it is meaningful again.
3. Run gate block F5 (OA-4).
