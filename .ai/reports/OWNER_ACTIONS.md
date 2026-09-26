# Owner Actions

Work only the owner can do. One row per item, with a stable id and a status;
other documents cite the id and do not restate the status
(`.ai/REPORTING.md` § *Owner ledger*).

| id | Item | Status |
| --- | --- | --- |
| OA-1 | Make the repository public, so hosted runners stop being metered against a private-repository allowance | **DONE** 2026-09-26. Verified: the API reports `visibility: public`, `private: false`. |
| OA-2 | Re-enable GitHub Actions for the repository, disabled on 2026-09-25 | **TO CONFIRM.** The workflows are restored in the tree; the first push either produces runs or does not, and that is the only reliable test from here. |
| OA-3 | Register and start the self-hosted runner on the Windows machine with all four labels (`self-hosted`, `Windows`, `X64`, `sunshine-chromium`) | **OPEN.** Needed only for the two dispatch-only workflows; `docs/WINDOWS_CHROMIUM_BUILD.md` § *Running a build* gives a path that needs no runner. |
| OA-4 | Run the native Windows build, then gate block F5 (RV-69 → RV-70 → RV-72 → RV-73 → RV-74 → RV-71 last) | **OPEN.** The split hover widget and link mode have never been compiled. RV-73 is the gate that can require the link mode to be withdrawn. |

**Superseded, kept so the change is legible.** This file previously said
"GitHub Actions remains disabled. Any future deployment or workflow replacement
must be chosen explicitly before claiming that new changes are published." The
owner made that choice explicitly on 2026-09-26 — the repository is public and
the workflows are restored — so the sentence is replaced rather than left to
contradict OA-1 and OA-2.
