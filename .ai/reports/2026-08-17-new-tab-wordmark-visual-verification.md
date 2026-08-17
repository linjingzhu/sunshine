# Sunshine New Tab wordmark — defect fixes and first visual verification

## Status

COMPLETED_WITH_NOTES

## Why this was possible without a Chromium build

The Sunshine patch stack touches three upstream files and none of them is C++:
`chrome/app/theme/chromium/BRANDING` is plain configuration, and
`new_tab_page/app.css` plus `app.html` are WebUI resources. The wordmark is
therefore renderable in an ordinary Chromium without compiling the downstream.

Earlier reports recorded runtime and visual verification as blocked. That was
correct for the browser as a product and wrong for this surface.

## Defects found and fixed

- **Major — the wordmark ignored Chromium's logo visibility state.** The patch
  replaced `<ntp-logo ... ?hidden="${!this.logoEnabled_}">` with an
  unconditional element, so the wordmark stayed on screen when Chromium said the
  logo was off. The binding is restored on the wordmark.
- **Minor — the wordmark froze the theme-controlled spacing.** It hardcoded
  `margin-bottom: 38px` while the slot it replaced reads
  `var(--ntp-logo-margin-bottom, 38px)`. It now reads the same variable.
- **Major — the wordmark was off-centre in RTL locales.** Measured at
  **-10.087px** at 56px type, exactly one letter-space. `padding-inline-start`
  compensates the trailing letter-space in LTR, but flips to the right edge in an
  RTL UI and doubles the error instead. Adding `direction: ltr` states that the
  wordmark is a Latin lockup and keeps the compensation on the left. Both a
  physical-padding variant and this one measured identical, and the logical
  property was kept because it survives an upstream style review better.

The upstream `#logo` rule was deliberately left in place. It belongs to Chromium,
and deleting it would widen the patch's upstream footprint for no behaviour
change.

## Measured evidence

Rendered in the pre-installed Chromium 141 at 1200x700 unless noted.

| Property | Result |
|---|---|
| Optical centre, LTR | -0.009px |
| Optical centre, RTL | -0.009px (was -10.087px) |
| `hidden` attribute | `display: none`, no client rects |
| Accessibility tree | `heading "Sunshine OS" [level=1]: SUNSHINE`, exactly one level-1 heading |
| `margin-bottom` | 38px through the `--ntp-logo-margin-bottom` fallback |
| Type scale | 32px at 360px viewport, 48px at 800px, 56px at 1920px |

`clamp(2rem, 6vw, 3.5rem)` is fluid only between roughly 533px and 933px of
viewport width and is pinned to its floor or ceiling outside that band. That is
characterised behaviour, not a defect.

## New offline gate

`git apply --numstat` rejects a hunk header that miscounts its body, with no
network access. CI already applies the stack against real pinned upstream, but
only over the network. `tests/test_patch_structure.py` now runs the offline
structural check and carries a deliberately corrupted patch to prove the check
fails when it should.

## Not verified

- Colour and contrast. `--color-new-tab-page-primary-foreground` and
  `--ntp-theme-text-shadow` come from Chromium's colour pipeline; the harness
  substitutes stand-in values, so no colour conclusion is claimed.
- Typeface and whether `font-weight: 650` resolves on a variable font. The patch
  declares no `font-family` and inherits the New Tab Page's own stack, which is
  not present in the harness.
- Integration with the real searchbox and Most Visited layout.
- Behaviour on Chromium 152. The pinned target is 152; the available browser
  is 141.
- That the patch applies to real upstream sources. Unchanged from before: the CI
  architecture guard owns that check, and this session cannot reach the upstream
  host.

## Verification

- Unit/contract suite: 81 passed, up from 80.
- Architecture verifier, patch manifest, module registry, Python compile: passed.
- Patch hunk arithmetic: passed offline; upstream apply pending CI.
- Chromium compile, Windows build: NOT RUN.
- Adversarial review: FALLBACK REVIEW — fresh self-review only.
- Cross-agent review: NOT AVAILABLE.
