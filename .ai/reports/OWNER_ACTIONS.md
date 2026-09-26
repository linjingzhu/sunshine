# Owner Actions

Work only the owner can do. One row per item, with a stable id and a status;
other documents cite the id and do not restate the status
(`.ai/REPORTING.md` § *Owner ledger*).

| id | Item | Status |
| --- | --- | --- |
| OA-1 | Make the repository public, so hosted runners stop being metered against a private-repository allowance | **DONE** 2026-09-26. Verified: the API reports `visibility: public`, `private: false`. |
| OA-2 | GitHub Actions permission for the repository | **DONE** 2026-09-26. Verified: a `workflow_dispatch` through the API returns `204 Workflow run has been queued`, which a disabled repository refuses. |
| OA-5 | Find out why accepted runs are never scheduled — check the account's **Settings → Billing and licensing** for a failed payment or an Actions spending limit, and **githubstatus.com** for an Actions incident | **OPEN, and measured.** Two runs dispatched at 09:22Z sat `queued` for **50 minutes with zero jobs created** and `updated_at` never moving off creation. They are not waiting for a runner; they are never expanded into jobs. A public repository has unlimited free hosted minutes, so this is not a minutes problem — but an unpaid invoice or a spending limit blocks Actions account-wide regardless of repository visibility. The proxy in the development container blocks both `githubstatus.com` and the Actions-permissions API, so neither is checkable from there. |
| OA-3 | Register and start the self-hosted runner on the Windows machine with all four labels (`self-hosted`, `Windows`, `X64`, `sunshine-chromium`) | **OPEN.** Needed only for the two dispatch-only workflows; `docs/WINDOWS_CHROMIUM_BUILD.md` § *Running a build* gives a path that needs no runner. |
| OA-4 | Run the native Windows build, then gate block F5 (RV-69 → RV-70 → RV-72 → RV-73 → RV-74 → RV-71 last) | **OPEN.** The split hover widget and link mode have never been compiled. RV-73 is the gate that can require the link mode to be withdrawn. |

**Superseded, kept so the change is legible.** This file previously said
"GitHub Actions remains disabled. Any future deployment or workflow replacement
must be chosen explicitly before claiming that new changes are published." The
owner made that choice explicitly on 2026-09-26 — the repository is public and
the workflows are restored — so the sentence is replaced rather than left to
contradict OA-1 and OA-2.
