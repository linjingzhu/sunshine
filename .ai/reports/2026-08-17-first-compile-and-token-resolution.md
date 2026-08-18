# First compile, the defect it exposed, and the token question closed

## Status

COMPLETED_WITH_NOTES

## Scope

Diagnose the first Chromium build to reach compilation, fix what it found, and
resolve the New Tab colour-token question left open by the Stage 2 wave.

## What happened

Build run 10 was the first to get past source acquisition and configuration.
It compiled for 17m28s and completed 11,820 of 66,739 steps before one step
failed. The log recorded the whole failure as `1 steps failed: exit=1`.

siso writes the failing command and its compiler output to
`out/Sunshine/siso_output` rather than stdout, and that file stays on the
runner. So the first real compile failure was undiagnosable from the only
artefact CI produces. The failure path now dumps it; run 11 named the target,
the file and the error on its next attempt, three minutes later.

## The defect

`//chrome/browser/resources/new_tab_page:lint_ts`:

    app.ts 181:5  error  Id 'logo' is listed in the interface definition for
    AppElement, but no element with that ID was found in the template file
    'app.html.ts'   @webui-eslint/lit-element-invalid-interface

`0002-sunshine-new-tab.patch` replaced `<ntp-logo id="logo">` in the template
and stopped there. `app.ts` referenced the logo in four places:

| reference | consequence if left |
| --- | --- |
| `logo: LogoElement` in the `$` interface | build failure -- the one that surfaced |
| `import type {LogoElement}` | unused import, rejected under `noUnusedLocals` |
| `'#logo'` in `COMPOSEBOX_INERT_ALLOWLIST` | wordmark goes inert, and out of the accessibility tree, whenever the composebox opens |
| `case $$(this, 'ntp-logo')` | `NtpElement.LOGO` silently stops recording |

The visible one was the least damaging. The wordmark occupies the logo slot and
inherits its behaviour, so the allowlist entry and the click metric now point at
`#sunshineWordmark`, and the two dead references are gone.

The patch was regenerated from a real diff against the pinned sources rather
than hand-edited. It applies to pristine 152.0.7977.42 with no residual logo
reference.

## The token question, closed

The Stage 2 wave found that `--color-new-tab-page-primary-foreground` and
`--ntp-theme-text-shadow` appear in the patch only on added lines, and added a
CI step requiring both to appear in upstream's `app.css`.

That step was wrong, and this is the run that would have proven it.
`--color-new-tab-page-primary-foreground` appears nowhere in `app.css` at any
revision, because `--color-new-tab-page-*` tokens are not declared in
stylesheets: Chromium emits them from the colour IDs in `chrome_color_id.h` and
serves them through `chrome://theme`. `kColorNewTabPagePrimaryForeground` is
defined at the pinned tag. The wordmark's colour is sound, and the check would
have failed the build on a valid token.

The naming transform was confirmed against three controls whose tokens `app.css`
does use -- `SecondaryForeground`, `MostVisitedForeground`,
`AttributionForeground`.

Each token is now checked against the source that defines it:
`--ntp-theme-text-shadow` against `app.css`, which declares it, and the colour
against the colour ID.

## Consolidation

The token check was wrong partly because it was bash inside a workflow, where
nothing could test it. Three steps -- seams, tokens, patch application -- are now
one tested implementation, `scripts/verify_pinned_upstream.py`, which CI calls.
Its tests assert that it fails for the right reason, not merely that it passes.

`--source github` reads the same revision from the GitHub mirror, for
environments whose egress policy blocks the authoritative host. CI runs the
default, and a test pins that.

## Verification

- Unit/contract suite: 120 passed, up from 109.
- Architecture verifier, command registry (27), module registry (3): passed.
- Patch manifest: 4 exclusive upstream targets, up from 3.
- Pinned upstream check, run here against 152.0.7977.42 via the mirror: all
  seven seams, both tokens, and both patches pass.
- Native compile: IN PROGRESS at time of writing (run 12, commit 6aa75ff).
- Runtime, visual, installer: NOT RUN.
- Adversarial review: FALLBACK REVIEW -- Manager only.
- Cross-agent review: NOT AVAILABLE.

## Blocked, and not by this work

GitHub-hosted runners have failed to allocate for every architecture-guard run
since 07:13Z: four attempts across two commits, each 2-3 seconds, `runner_id: 0`,
no steps, no log, 0 ms billable. The job dies before checkout, so no file in the
repository is read. The workflow YAML parses and yields 13 steps, and the 11
preceding runs all passed in 16-90s.

The self-hosted Windows build runs normally on the same commits, and self-hosted
minutes are the ones that do not draw on the hosted allowance. This points at the
account's Actions minutes or spending limit for private repositories, which only
the owner can change. Recorded on PR #20; not re-run further, since three
identical zero-duration failures are not a flake.

Every network-dependent check the guard performs was run locally instead, via
the mirror, and passes.

## Open

Unchanged from the Stage 2 wave: the five product decisions for the owner, the
deferred `security.*` commands and context-menu commands, the `browser.reload`
ambiguity, and the unstated "commands take no parameters" assumption.

`font-weight: 650` on the wordmark remains unverified against a variable font;
it is settled by runtime verification, which has not run.
