# Policy-checker retirement and the build path after Actions

Status: COMPLETED_WITH_NOTES
Repository: linjingzhu/sunshine
Repository Mode: protected
Integration: `stable`

## Executive summary

`stable` was red for a day after the 2026-09-25 policy adoption (PRs #61-#63).
Eleven failures, none from the split-widget merge. Two were half-finished edges
of that adoption and are fixed. Nine were one question — the repository had two
policy-document checkers with incompatible reference conventions — and the owner
decided it: the adopted set's checker is the only one, and the older one is
retired. The tree is green again.

Separately, the same adoption removed every workflow file and disabled Actions,
so `docs/WINDOWS_CHROMIUM_BUILD.md` was largely instructions for a thing that no
longer exists. It now documents starting a build by hand, which is the path the
owner chose.

## Delivered

- `verify_pinned_upstream.OWN_PREFIXES` gained `.agents`, `.claude`, `.codex`.
  Without them a citation of `.claude/skills/auto-dev/SKILL.md` is probed
  against Chromium and reported as a contract citing a file upstream deleted.
  `tests/test_verify_pinned_upstream.py` compares that list against what git
  tracks, which is how this surfaced.
- `test_ci_checks_tab_and_window_extra_data_separately` read a workflow file
  that no longer exists. The invariant it protects is unchanged and still
  checked; the half asserting that CI ran it is gone, and the docstring now
  says so rather than dropping it quietly.
- `scripts/validate_doc_metadata.py` and `tests/test_doc_metadata.py` retired.
  `.ai/tools/check_policy_set.py` is the only policy-document checker.
- `docs/WINDOWS_CHROMIUM_BUILD.md`: § *Required machine* replaces § *Required
  runner*; § *Running a build* gives the one command and what to read at each
  failure point; § *When a job sits in `queued`* is reduced to the one part that
  survived Actions, which is that the machine still sleeps.

## What the retirement costs, stated plainly

Four repository-authored statements existed at `7fe7878` and exist nowhere in
the tree now: `MUST use stable canonical paths`, `do not announce version
bumps`, `history is the source of truth`, `MUST NOT reduce engineering rigor` —
with the three escalation exceptions (a user decision, a critical risk, a scope
change) and the silent-execution operating mode that cited them. PR #61's
report says "repository-specific guidance retained"; measured, `.ai/REPORTING.md`
went from 219 lines to 98 and the version field stayed `1.1.0`.

The retired test is what named each missing statement. The owner chose to accept
the adopted set as-is rather than restore them, so **the silent-execution
operating mode and the document versioning scheme are no longer enforced by
anything.** They are recorded in `.ai/memory/PROJECT_LESSONS.md` § *Verification
Lessons* as prose, which `.ai/EVOLUTION.md` § *Prefer a check to a sentence*
rates as the weaker form, and the entry says so.

## Verification

- Compile: NOT RUN — nothing here compiles Chromium.
- Tests: 975 pass, 11 skipped (`python3 -m unittest discover -s tests`). 989
  before, of which 14 were the retired file's.
- Guards: every `scripts/verify_*.py` and `scripts/validate_*.py` passes, plus
  `.ai/tools/check_policy_set.py` (7/7).
- Patch stack: all 32 patches apply to pinned `152.0.7977.42`
  (`verify_pinned_upstream.py --source github`).
- Target Build: NOT RUN.
- Runtime/Visual: NOT RUN.
- Cross-Agent Review: NOT AVAILABLE — one agent family.

## Remaining risks

- The split hover widget and link mode (patches 0027, 0031, 0032) are merged and
  **have never been compiled**. RV-69 to RV-74 are unrun. The dot shipped
  invisible in build #61 from exactly this state, and this change is larger.
- A hand-run build produces no run number, so `docs/RUNTIME_VERIFICATION.md` § 4
  asks for a citation that no longer exists; cite the commit sha, and
  `build_gate_sheet.py`'s `BUILD` stamp is now kept by hand.
- Artifacts live on one disk. There is no 14-day upload.
- `scripts/compile_check_installer.py` needs mingw, which the build machine does
  not have, so it runs only where a developer runs it — and it never once ran in
  CI.
- The next `adopt.py` re-sync will not know about any of this.

## Owner actions

- None new. `.ai/reports/OWNER_ACTIONS.md` is unchanged: Actions stays disabled
  by the owner's decision, and no workflow replacement is claimed.

## Recommended next actions

1. Run the build on the Windows machine: `pwsh -NoProfile -File
   scripts/build_chromium_windows.ps1`. Run
   `python3 scripts/verify_pinned_upstream.py --source github` first — it is now
   the only thing asking whether the stack fits the real tree.
2. Run gate block F5 (RV-69 → RV-70 → RV-72 → RV-73 → RV-74 → **RV-71 last**)
   from `docs/RETURN_RUN_SHEET.md`. RV-73 is the one that can require the link
   mode to be withdrawn.
3. Decide whether the four dropped policy statements are re-entered as
   repository additions to the adopted set, or stay dropped. This report is the
   record either way.
