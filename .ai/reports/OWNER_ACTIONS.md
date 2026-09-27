# Owner Actions

Work only the owner can do. One row per item, with a stable id and a status;
other documents cite the id and do not restate the status
(`.ai/REPORTING.md` § *Owner ledger*).

| id | Item | Status |
| --- | --- | --- |
| OA-1 | Make the repository public, so hosted runners stop being metered against a private-repository allowance | **DONE** 2026-09-26. Verified: the API reports `visibility: public`, `private: false`. |
| OA-2 | GitHub Actions permission for the repository | **DONE** 2026-09-26. Verified: a `workflow_dispatch` through the API returns `204 Workflow run has been queued`, which a disabled repository refuses. |
| OA-5 | ~~Check the account's Billing for a failed payment or an Actions spending limit~~ — **withdrawn, the diagnosis was wrong** | **WITHDRAWN** 2026-09-27. The real cause is in the tree, not the account: `stable` carries no `.github/workflows/` at all, so GitHub's workflow registry is empty (`GET /actions/workflows` returns `total_count: 0`) and nothing is scheduled. Superseded by OA-6. Nothing was ever owed on the account, and the time spent checking Billing was spent on my mistake. **The replacement diagnosis in this row is also wrong** — see OA-6: the registry is no longer empty and runs still do not appear. Both sentences are kept so the second mistake is not hidden behind the first correction. |
| OA-6 | Merge PR #64, which carries the four workflow files onto the default branch | **DONE** 2026-09-27, merge commit `d25dd65`. It did what it was for and did not fix the symptom. Verified after the merge: `GET /actions/workflows` returns `total_count: 4`, all `state=active`, including `Native Chromium Windows Build`, which was not registered before. **The merge commit produced no workflow run**, watched for ~2 minutes, although `architecture-guard-hosted.yml` has an unfiltered `push:` and `stable` is the default branch. Every repository-side explanation is now excluded; I am not naming a replacement cause, having been wrong three times. |
| OA-3 | Register and start the self-hosted runner on the Windows machine with all four labels (`self-hosted`, `Windows`, `X64`, `sunshine-chromium`) | **OPEN.** Needed only for the two dispatch-only workflows; `docs/WINDOWS_CHROMIUM_BUILD.md` § *Running a build* gives a path that needs no runner. |
| OA-4 | Run the native Windows build, then gate block F5 (RV-69 → RV-70 → RV-72 → RV-73 → RV-74 → RV-71 last) | **OPEN.** The split hover widget and link mode have never been compiled. RV-73 is the gate that can require the link mode to be withdrawn. |

**Superseded, kept so the change is legible.** This file previously said
"GitHub Actions remains disabled. Any future deployment or workflow replacement
must be chosen explicitly before claiming that new changes are published." The
owner made that choice explicitly on 2026-09-26 — the repository is public and
the workflows are restored — so the sentence is replaced rather than left to
contradict OA-1 and OA-2.
