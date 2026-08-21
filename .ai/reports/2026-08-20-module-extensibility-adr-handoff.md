# Module extensibility and the ADR set — session handoff

## Status

HANDOFF — analysis only. No code, contract or ADR in this repository was changed
by the session that wrote this. It exists to be read by the next session instead
of having the same investigation run again.

## Repository state at handoff

- Branch `claude/module-install-ui-0qfq9e` is at `7d0b83d`, identical to `stable`.
- An install-pipeline implementation was started in this session and then
  cancelled at the owner's instruction: commit `48ac242` was reverted off the
  branch and pull request #30 was closed. Nothing of it survives. Treat the work
  as unstarted.
- Baseline: `python -m unittest discover -s tests` reported 572 tests, all
  passing, and every offline guard passed. `verify_design_tokens.py` and
  `verify_first_party_surfaces.py` both need `raw.githubusercontent.com` and
  failed with a proxy 403 in the sandbox — an environment limit, not a defect.

## What the owner asked

> If a module has to be compiled, it has no usability. The user cannot use it.
> It should be like an extension: press a button, pick a zip file or a target
> path, and that module is installed.

and then, separately:

> The ADRs are obstructing extensibility.

## The ADR set

`docs/decisions/` holds eleven. ADR 0001 was withdrawn as an error and removed,
which is why the numbering starts at 0002.

| ADR | Subject | Status | Enforced by | Referenced by | Blocks extensibility |
| --- | --- | --- | --- | --- | --- |
| 0002 | Native Chromium downstream | Accepted | `scripts/verify_architecture.py` | 22 files | no |
| 0003 | No internal `sunshine` URL scheme | Accepted | SEC-13, `scripts/verify_first_party_surfaces.py` | 25 files | no |
| 0004 | Proprietary codecs, personal-use premise | Accepted, conditional | build flags | 16 files | no |
| 0005 | Missing-API-key warning removed | Accepted | patch 0003, `scripts/verify_account_freedom.py` | 7 files | no |
| 0006 | A module is a compiled capability | Accepted (Position A) | `scripts/validate_first_party_modules.py` | 6 files | **yes — the only one** |
| 0007 | One WebUI seam, many surfaces | Accepted | `scripts/patch_manifest.py` | 11 files | no — it *improves* it |
| 0008 | Binary assets replace, not patch | Accepted, implemented | `scripts/verify_asset_overlay.py` | 7 files | no |
| 0009 | Document surface ingress | Proposal, undecided | nothing | 6 files | no |
| 0010 | Security Center open policy | Proposal, undecided | nothing | 1 file | no |
| 0011 | AI-credential broker | Proposal, undecided | nothing | 3 files | no |
| 0012 | Gesture attach point | Proposal, undecided | nothing | 0 files | no |

Reference counts are files outside the ADR itself naming it as `ADR NNNN` or by
path, across `docs/`, `.ai/`, `scripts/`, `tests/`, `first_party/`, `downstream/`
and `config/`.

## Finding 1 — three places block a user-installable module, and only one is an ADR

1. **ADR 0006's Decision.** "A Sunshine module is a compiled capability … It is
   not a bundle the browser loads and executes."
2. **`scripts/validate_first_party_modules.py`.** `ENTRYPOINT_TYPES` is closed at
   four values — `chromium_webui`, `chromium_webui_overlay`, `native_command`,
   `profile_service`. There is no package or bundle entrypoint, so an installable
   module cannot be *declared*, let alone shipped. ADR 0006 names this as the
   mechanism that makes its position real rather than aspirational, and it is
   right: this line is the enforcement.
3. **`.ai/PROJECT_CONTEXT.md`.** "modules are compiled Sunshine capabilities, not
   extensions or remotely loaded plug-ins."

Everything else in the set is orthogonal to the question.

## Finding 2 — two ADRs are routinely mistaken for blockers and are not

**ADR 0003 does not block this.** What it forbids is *Sunshine registering a
scheme*. `chrome-untrusted://` is registered by Chromium, and it is already in
the `ALLOWED_SCHEMES` set of `scripts/verify_first_party_surfaces.py`. An
installed package served from `chrome-untrusted://sunshine-module/<id>/` leaves
ADR 0003 and SEC-13 untouched. This is also the answer to the question ADR 0006's
*Revisiting* section left open — "can a WebUI host serve bundled resources
without a registered scheme?" — and it makes the cheaper version of Position B
the one on the table.

**ADR 0007 is on extensibility's side.** It is what took the marginal cost of a
new surface from seven upstream-file edits to zero. Removing it would make
extension harder, not easier.

## Finding 3 — what to keep, supersede, and retire

**Keep, and do not delete.**

- **0002** is the product definition. Deleting it deletes what Sunshine is.
- **0003** rests on a live defect, not a preference: with the scheme
  unregistered, typing `sunshine://security` classifies as `UNKNOWN` and is sent
  to the configured search provider as a query, leaking an internal route name
  off the machine; registering it at the OS level makes every web page and mail
  client a launcher for internal routes.
- **0004** carries the "revisit before any build reaches a second person" clause.
  That clause is the whole document, and losing it loses the licensing record.
- **0007** and **0008** are small, enforced, and cost nothing to keep.
- **0005** costs nothing to keep.

**Supersede rather than delete — 0006.** A new ADR should replace it with two
kinds of module: a compiled capability for work that changes the browser itself,
and an installed package for everything else. Deleting 0006 instead would remove
the record of why the answer was reversed, and the same argument would be had
again from the start.

**Retire — 0012.** 561 lines, zero references, decides nothing. Fold its one
settled result into `docs/GESTURE_CONTRACT.md` and delete the file.

**Decide and compress — 0009, 0010, 0011.** Roughly 850 lines of options awaiting
a product-owner answer. None of them blocks anything technically, and together
they are the reason the decision set *feels* like a wall. 0009 is the worst of
the three: `docs/OPEN_DECISIONS.md` already records that implementation of
Reading A has started, so a question that has effectively been answered is still
filed as open.

**Mechanical consequence of any deletion.** `scripts/verify_decision_index.py`
fails the build when `docs/OPEN_DECISIONS.md` cites an ADR that does not exist,
so removing an ADR file means editing the index in the same change.

## Finding 4 — removing ADRs does not open the path

This is the part that must survive into the next session's report to the owner.

- Patches `0004-sunshine-webui-seam` and `0005-sunshine-security-webui` have
  never been compiled.
- A full build measures 6 h 31 min, on the project's only build machine, which is
  also its only CI.
- Serving an installed module still needs one compiled piece: a module host —
  the management surface, the data source that serves installed files, the file
  picker, and the installer.
- ADR 0007's sequencing rule says the seam's dependents are not built until the
  seam compiles. Writing the module host now contradicts that rule, so it needs
  the owner's explicit agreement rather than a Manager decision.

No amount of ADR editing changes any of the four.

## Recommended order

1. Write the ADR that supersedes 0006: two kinds of module, the installed one
   served from `chrome-untrusted://sunshine-module/<id>/` with no capability, no
   network, no filesystem and no credential.
2. Open `ENTRYPOINT_TYPES` for the package kind and define the package manifest.
   Reuse schema 2's `security` block and its validator rather than writing a
   second one — `docs/SECURITY_ARCHITECTURE_CONTRACT.md` section 4 names a second
   permission vocabulary as the failure this contract set is most exposed to.
3. Amend the module-boundary sentence in `.ai/PROJECT_CONTEXT.md`.
4. Delete 0012; settle and compress 0009, 0010 and 0011, editing
   `docs/OPEN_DECISIONS.md` in the same change.
5. Only with the owner's agreement, and after the build gate: the module host
   patch, once.

## Constraints the next session will hit

- `scripts/verify_no_interposition.py` scans `first_party/`, `downstream/`,
  `scripts/` and `config/` for prohibited *declared field names* — anything
  reading as pinned state, per-tab lifecycle state, a recently-closed store, a
  duplicate set, a scheme or host table, or a repeating timer. Module- and
  class-level names and dict-literal keys are collected; function locals are not.
  Two or more distinct scheme literals in one file is also a failure.
- `scripts/verify_web_asset_security.py` (SEC-14) scans `first_party/` and
  `downstream/` web assets for `eval`, `new Function`, string timers,
  `innerHTML`/`outerHTML` assignment, `document.write`, and remote URLs outside
  comments.
- A new invariant family (`MP-1` and the like) has to be registered in
  `scripts/trace_invariants.py`, and `tests/test_invariant_tracing.py` checks the
  registration. That is a decision, not a cleanup.
- `scripts/verify_stated_counts.py` checks counts stated in `docs/` prose against
  `first_party/commands.json`, `first_party/registry.json`,
  `downstream/patches/series`, the test suite and the pinned revision.
- Document metadata is required under `.ai/`, `CLAUDE.md` and `AGENTS.md` only;
  `docs/` and `.ai/reports/` are exempt.
- All work goes to `claude/module-install-ui-0qfq9e`, pushed with
  `git push -u origin <branch>`, with a draft pull request.

## How the owner wants to be talked to

Korean. Never present something unverified as verified — it is this repository's
central rule and the owner enforces it. Documents alone are not an acceptable
deliverable for a usability complaint: separate what actually runs today from
what is still waiting on the build gate, and say which is which.
