# Sunshine OS design system, accessibility, and appearance contract

Status: Documentation only. No downstream patch is added by this wave.
Pinned upstream: Chromium `152.0.7977.42` (`config/chromium.version`)
Source section: `docs/SUNSHINE_OS_STAGE_1_TO_3_IMPLEMENTATION_HANDOFF.md` §8
Worked example: `downstream/patches/0002-sunshine-new-tab.patch`

## 0. Why this document exists

The first visual verification of the Sunshine New Tab wordmark
(`.ai/reports/2026-08-17-new-tab-wordmark-visual-verification.md`) could measure
geometry, accessibility semantics, and type scale, but recorded colour and
contrast as **not verified**. The two tokens the wordmark depends on —
`--color-new-tab-page-primary-foreground` and `--ntp-theme-text-shadow` — had no
documented contract, so there was no stated requirement to test against. A
measurement without a threshold is an observation, not a verification.

This document supplies the thresholds, the ownership rules, and an acceptance
suite that a reviewer can execute. It changes no code.

### Scope

| In scope | Out of scope |
|---|---|
| Rules for Sunshine-authored CSS in native WebUI surfaces | Chromium's own stylesheets and Views chrome |
| Rules for Sunshine-defined design tokens | A Sunshine colour palette or brand colour values |
| Contrast, forced colours, typography, direction, motion, focus | Component API design for `SunButton` and the rest of §8.1 |
| Acceptance criteria executable against a native build | Any claim that a native build exists |

Sunshine is a native downstream of open-source Chromium. Browser chrome is
Chromium Views; Sunshine product surfaces are native WebUI. There is no React
and no wrapper runtime. Nothing in this document may be implemented by adding
one.

## 1. First principle: Chromium owns colour

Chromium owns the colour pipeline, theme selection, the light/dark decision,
`prefers-contrast`, and forced-colours mode. Sunshine consumes the result. This
is not a stylistic preference; it is the only way a Sunshine surface stays
consistent with the surrounding browser chrome when the user changes theme,
installs a background image, or turns on an OS high-contrast theme — none of
which Sunshine is notified about.

The rule that follows from this, and that the rest of the document elaborates:

> A Sunshine surface never decides what colour something is. It decides which
> semantic role something has, and reads the colour for that role from Chromium.

## 2. Token ownership

### 2.1 Families

| Family | Example | Owner | Sunshine may |
|---|---|---|---|
| `--color-*` | `--color-new-tab-page-primary-foreground` | Chromium `ColorProvider`, generated from the `ColorId` enums and served to WebUI as CSS custom properties | Read only |
| `--cr-*` | shared WebUI component variables in `ui/webui/resources/cr_elements` | Chromium WebUI | Read only |
| `--ntp-*` | `--ntp-theme-text-shadow`, `--ntp-logo-margin-bottom` | Chromium New Tab Page theme code | Read only |
| CSS system colours | `Canvas`, `CanvasText`, `Highlight`, `LinkText` | User agent and operating system | Read only |
| `--sun-*` | `--sun-color-primary` (handoff §8.3) | Sunshine | Define, under §2.2 |

Sunshine must not redefine, shadow, or reassign a token from any family it does
not own. Assigning to a `--color-*`, `--cr-*`, or `--ntp-*` custom property in
Sunshine-authored CSS is a defect regardless of the value assigned.

### 2.2 When a Sunshine token is permitted at all

A `--sun-*` token is admissible only if **all five** tests pass. Each is
checkable by a reviewer against the pinned tree.

1. **No upstream equivalent.** No `--color-*`, `--cr-*`, or surface-level
   `--ntp-*` token in the pinned tree expresses the same semantic role. If one
   exists, the Sunshine token is redundant and is rejected.
2. **Semantic name.** The name states a role (`--sun-color-on-surface`), never
   an appearance (`--sun-color-warm-yellow`) and never a location
   (`--sun-color-wordmark`).
3. **Colour tokens are references, not literals.** A `--sun-color-*` token's
   value must be a `var()` reference to a Chromium token or a CSS system colour,
   optionally composed through `color-mix()`. A literal `#rrggbb`, `rgb()`,
   `hsl()`, `oklch()`, or named colour in a `--sun-color-*` declaration is
   rejected. Non-colour Sunshine tokens (spacing, radius, duration, weight,
   type step) may hold literals.
4. **Mode-complete by construction.** Because of (3), the token resolves
   correctly in light, dark, `prefers-contrast: more`, and
   `forced-colors: active` without Sunshine authoring a second palette. A token
   that needs a Sunshine-authored override inside a `@media (prefers-color-scheme)`
   or `@media (forced-colors)` block has failed (3) and is rejected.
5. **Declared once.** All `--sun-*` tokens are declared in a single Sunshine
   stylesheet. Declaring one inline on an element, or in a surface's own file,
   is rejected.

A token that fails any test may still be introduced, but only through a decision
record in `docs/decisions/` that states which test it fails and why the failure
is preferable to the alternative.

### 2.3 Consumption rule: fallbacks

| Token kind | Fallback in `var()` | Reason |
|---|---|---|
| Colour | **Prohibited** | A fallback colour is plausible enough to survive review while silently escaping the theme. The wordmark would look correct in the light theme and wrong in every other mode. A missing colour token must fail visibly. |
| Non-colour, with a documented upstream default | **Required**, and must equal that default | Matches the existing, correct `var(--ntp-logo-margin-bottom, 38px)`, which mirrors upstream's own declaration for `#logo`. |

The existence of every consumed colour token is proven by a source check against
the pinned tree (§9, check S1), not by a runtime fallback.

## 3. The semantic token set Sunshine surfaces may rely on

Sunshine surfaces bind to **roles**. Each role is bound to a concrete Chromium
identifier per surface. The New Tab is the only Sunshine surface that exists
today, so it is the only surface with bindings.

| Role | New Tab binding | Status |
|---|---|---|
| Primary foreground | `--color-new-tab-page-primary-foreground` | Consumed today by `#sunshineWordmark`. Existence asserted by the Sunshine patch, not yet proven against pinned source. See §10. |
| Over-image legibility treatment | `--ntp-theme-text-shadow` | Consumed today by `#sunshineWordmark`. Same status. |
| Logo/wordmark bottom spacing | `--ntp-logo-margin-bottom`, default `38px` | Proven: upstream's own `#logo` rule in the patch context declares it. |
| Secondary foreground | `--color-secondary-foreground` | Bound by patch 0004; enumerator read in `ui/color/color_id.h` at the pinned tag. |
| Surface background | `--color-dialog-background` | Bound by patch 0004. Chromium has no generic surface role; the dialog background is the nearest enumerated one and is what a WebUI page sits on. |
| Outline / divider | `--color-midground` | Bound by patch 0004. |
| Focus indicator | Unbound; expected to come from the `--cr-*` focus-outline variable used by WebUI components | Resolve from pinned source before first use. |
| Accent and on-accent | Unbound; §8.3 of the handoff names `--sun-color-primary` / `--sun-color-on-primary` as the semantic surface for the user-editable appearance model | Must be defined as references under §2.2(3). |
| Error | `--color-alert-high-severity` | Bound by patch 0004 for the one place it is currently needed — the verdict shown when the browser has no malware protection. The handoff's `--sun-color-error` remains the eventual semantic reference under §2.2(3); this is the Chromium role it will point at. |

Binding procedure for an unbound role, to be performed once the pinned tree is
available: locate the identifier in `ui/color/color_id.h`,
`chrome/browser/ui/color/chrome_color_id.h`, or the New Tab Page's own theme
code; confirm it is emitted to WebUI as a CSS custom property; record the
binding in this table. Roles are not bound by guessing at a name that follows
the pattern.

Sunshine must not introduce a second name for a bound role. `--sun-color-on-surface`
may not be defined on the New Tab as an alias for
`--color-new-tab-page-primary-foreground` merely to make Sunshine CSS read
uniformly; that is a §2.2(1) failure.

## 4. Contrast

### 4.1 Measurement method

So that pass and fail are not matters of opinion:

- Contrast ratio is the WCAG 2.2 formula on sRGB relative luminance,
  `(L1 + 0.05) / (L2 + 0.05)`.
- Values are sampled from a screenshot captured in sRGB at 100% zoom and 1×
  device pixel ratio unless the check states otherwise.
- **Text colour** is the modal colour of fully-opaque glyph-interior pixels.
  Anti-aliased edge pixels are excluded; they are a rendering artefact, not the
  specified colour.
- **Background colour** is the pixel behind the glyphs that yields the *lowest*
  contrast within the text's ink bounding box, dilated by the blur radius of any
  applied text shadow. Averages are not used; a legible average with an illegible
  patch is a failure.

### 4.2 Thresholds

| Content class | Minimum ratio | Basis |
|---|---|---|
| Text below 24 CSS px, or below 18.66 CSS px at weight ≥ 700 | 4.5:1 | WCAG 2.2 AA 1.4.3 |
| Text at or above 24 CSS px, or 18.66 CSS px at weight ≥ 700 | 3:1 | WCAG 2.2 AA 1.4.3, large text |
| **Sunshine wordmark and any single-instance brand text** | **4.5:1** | Sunshine requirement, above the large-text relaxation. See §4.3. |
| Focus indicator against every colour it abuts | 3:1 | WCAG 2.2 AA 1.4.11 |
| Icon or glyph that carries meaning with no text label | 3:1 | WCAG 2.2 AA 1.4.11 |
| Boundary of a control whose shape conveys its hit area | 3:1 | WCAG 2.2 AA 1.4.11 |
| Text disabled by the user agent | No threshold | WCAG 1.4.3 exception. Disabled state must still be signalled by something other than contrast alone. |

Every threshold must hold in the light theme and in the dark theme
independently. A colour pair that passes in one and fails in the other fails.

### 4.3 Why the wordmark is held to 4.5:1

The large-text relaxation to 3:1 assumes a controlled background and a reader who
can fall back on surrounding text. Neither holds here. The wordmark is the New
Tab's only level-1 heading, it has no adjacent duplicate of its content, and it
renders over an arbitrary user-supplied background image. Holding it to the
body-text threshold costs nothing when the background is a theme colour and is
the difference between legible and not when the background is a photograph.

### 4.4 How a theme background image changes the requirement

When the surface has a background image, four things change. The threshold is
not one of them.

1. **The reference background stops being a token.** Contrast can no longer be
   computed from two token values; pixel sampling per §4.1 becomes mandatory.
2. **Worst case replaces typical case.** The sampled background is the
   lowest-contrast pixel in the dilated ink bounding box (§4.1), because a
   photograph's local extremes are what defeat legibility.
3. **A legibility treatment is mandatory.** Sunshine text rendered over a theme
   background image must consume the Chromium-supplied treatment for that
   surface — on the New Tab, `--ntp-theme-text-shadow`. Omitting it is a defect
   detectable by source inspection alone, with no build required.
4. **Failure attribution changes.** Sunshine cannot guarantee contrast against
   an image it does not control. If the threshold is missed with the treatment
   correctly applied, the defect is recorded against Chromium's treatment and
   raised as an upstream or patch-stack question. Sunshine must **not** respond
   by hardcoding a colour, adding its own scrim, or setting a background on the
   text — each of those breaks §2.2(3) or diverges from browser chrome — without
   a decision record in `docs/decisions/`.

The measurable gate over images uses a fixed test set so that runs are
comparable: solid `#FFFFFF`, solid `#000000`, solid 50% grey `#808080`, and one
high-frequency photograph. The three solids are a hard 4.5:1 gate. The
photograph's measured minimum is recorded rather than gated, because a
sufficiently adversarial image can defeat any treatment and a gate that can be
failed by choosing a different picture is not a gate.

## 5. Forced colours and high contrast

In `forced-colors: active`, the user agent substitutes a user- or OS-chosen
palette for author colours. Sunshine's obligation is to stay out of the way.

### 5.1 What must remain true

| Requirement | How it is checked |
|---|---|
| Every Sunshine text element is visible and meets 4.5:1 against its own background under both a light and a dark forced-colours theme | Runtime check R5, §9 |
| No information is lost when shadows are dropped, because the user agent forces `text-shadow` and `box-shadow` to `none` | Source review plus R5 |
| No information is lost when colour is flattened, because distinct author colours may collapse to one system colour | Source review: no Sunshine surface may distinguish two states by hue alone. Restates handoff §8.2 on security verdicts and tab group identity. |
| The focus indicator remains visible | Runtime check R12, §9 |

### 5.2 What Sunshine must not do

- Must not declare `forced-color-adjust: none` anywhere. There is no Sunshine
  content whose appearance outranks a user's stated accessibility need.
- Must not author a `@media (forced-colors: active)` block that reintroduces
  non-system colours, shadows, or a Sunshine palette.
- Must not detect high contrast — by media query, by preference, or by any
  native signal — and swap in a Sunshine-authored high-contrast theme. Chromium
  and the OS own that decision.
- Must not author a `@media (prefers-contrast: more)` block that changes colour.
  Chromium's colour pipeline already responds to `prefers-contrast`; a Sunshine
  override would compete with it. Non-colour responses (increasing a border from
  1px to 2px) are permitted.
- Must not treat `forced-colors: active` as a dark theme. It is neither light nor
  dark, and both directions occur in the wild.

Note for the worked example: `#sunshineWordmark` declares
`text-shadow: var(--ntp-theme-text-shadow)`. Under forced colours the user agent
neutralises this. That is correct and requires no Sunshine change — but it does
mean the shadow cannot be the only thing making the wordmark legible in that
mode, which is what check R5 exists to prove.

## 6. Typography

### 6.1 Sunshine surfaces do not choose a typeface

A Sunshine WebUI surface must not declare `font-family`. Chromium's WebUI text
defaults supply the browser UI font and base size, and that selection is
**localised** — the family and metrics differ by UI locale. Handoff §8.2 accepts
Korean-first product copy; a Sunshine-declared Latin font stack would degrade
exactly the locale the product targets, and would desynchronise Sunshine surfaces
from the surrounding Views chrome.

The single exception is `font-family: monospace` — the generic keyword only,
never a named face — for content whose alignment carries meaning, such as a hash
or a URL fragment.

`#sunshineWordmark` already complies: it declares no `font-family` and inherits
the New Tab Page stack.

### 6.2 Type scale

Sizes are drawn from a fixed scale. Arbitrary sizes are rejected.

`label-xs` was added by `docs/decisions/0016-relaxations-for-porting.md`. The
owner's own `Module shell layout rules` specifies an 11px mono path line beside
a 14px title, and the scale had no step for it — so the module shell rendered
that line at 12px and `docs/MODULE_SHELL_CONTRACT.md` §7 recorded the
substitution as a deviation. A scale that cannot express what the project's own
design asks for is a scale with a gap, and the honest repair is a step rather
than an exception.

**The unit does not move.** The scale is in `rem` because `px` ignores the
user's browser font-size setting and breaks WCAG 1.4.4, and that is an
accessibility property rather than house style — it is outside what ADR 0016's
boundary bends. Adding a step keeps every property the scale has; permitting
`px` would keep none of them.

`label-xs` is deliberately narrow in its use column. 11px is small enough that
using it for anything a person has to *read*, rather than *identify*, is a
defect the scale cannot catch.

| Step | Size | Line height | Use |
|---|---|---|---|
| `label-xs` | 0.6875rem | 1.45 | A path, an identifier, a timestamp beside something it belongs to. Smallest size permitted anywhere. Never for prose, never for a control's only label. |
| `label-sm` | 0.75rem | 1.33 | Dense metadata |
| `label` | 0.875rem | 1.43 | Control labels, secondary rows |
| `body` | 1rem | 1.5 | Default surface text |
| `title` | 1.25rem | 1.30 | Section heading |
| `title-lg` | 1.5rem | 1.25 | Surface heading |
| `headline` | 2rem | 1.20 | Prominent single heading |
| `display` | Fluid, bounded 2rem–3.5rem | 1 | Brand lockup. At most one per surface. |

Rules:

- Font sizes are declared in `rem`, or in a `clamp()` whose bounds are in `rem`.
  A `px` font size in Sunshine CSS is a defect: it ignores the user's browser
  font-size setting and breaks WCAG 1.4.4.
- No computed size below `label-xs`.
- `!important` on a typography declaration is a defect.
- Weights are drawn from {400, 500, 600, 700}. Any other value requires evidence
  that the pinned build's UI font exposes a continuous weight axis on **every**
  supported platform and locale; otherwise the value silently snaps and the
  declaration is a lie about the rendered result. `#sunshineWordmark` currently
  declares `font-weight: 650`, which is unresolved — check R10 settles it.

`#sunshineWordmark` maps to `display`: `clamp(2rem, 6vw, 3.5rem)` with
`line-height: 1`.

### 6.3 Bounding a fluid size

A `clamp()` font size is admissible only when all four hold:

1. Minimum and maximum are both expressed in `rem`. A viewport-unit bound is
   unbounded with respect to the user's font-size setting.
2. The preferred term may use `vw` or `vi`, and nothing else.
3. `max / min ≤ 2`. A wider range means one declaration is serving two different
   roles and should be two steps.
4. The fluid band — the viewport widths between which the preferred term sits
   strictly inside the bounds — must overlap the supported range of 360 to 1920
   CSS px. A clamp whose band falls entirely outside that range is a constant
   written as a function, and must be replaced by the constant.

The band must be stated where the declaration lives, so a reviewer does not have
to derive it. For the wordmark: `clamp(2rem, 6vw, 3.5rem)` is fluid between
approximately 533 px and 933 px, pinned to 2rem below and 3.5rem above,
`max / min = 1.75`. It passes all four.

## 7. Direction and right-to-left

### 7.1 The measured defect

The wordmark uses `letter-spacing: 0.18em`, which appends a trailing space after
the final glyph, and cancelled it with `padding-inline-start: 0.18em` so the
lockup sits optically centred. In an RTL UI locale the logical property mirrored
to the right-hand side while the Latin glyphs did not mirror. The compensation
moved to the same side as the trailing space and doubled the error instead of
cancelling it. Measured at 56px type: **-10.087 px**, exactly one letter-space.
The fix was `direction: ltr` on the element, declaring that the lockup is a Latin
run; the measured offset became -0.009 px, matching LTR.

### 7.2 The rule

> A direction-sensitive property and the content it acts on must resolve in the
> same direction. Any element whose text does not mirror — a non-translated
> Latin lockup, a code sample, a version string — must declare `direction`
> explicitly on that same element before any logical property is applied to it.

Corollaries, each independently checkable:

- Logical properties (`padding-inline-*`, `margin-inline-*`, `inset-inline-*`,
  `border-inline-*`, `text-align: start | end`) remain the default choice for
  translated content. This rule does not license a return to physical properties;
  the fix is to state the direction, not to abandon logical properties. The
  physical-padding variant measured identically and was rejected because the
  logical form survives an upstream style review better.
- Non-translated content must not inherit its direction from the UI locale. If
  the string is the same in every locale, the direction must be too.
- Any centred text with non-zero `letter-spacing` must cancel the trailing space,
  and the cancellation must be on the inline-start side of the element's **own**
  declared direction. With the direction declared, this is deterministic.
- The set of non-translated lockups is enumerated in this document so a source
  check can verify each one declares `direction`. Today that set is exactly one:
  `#sunshineWordmark`.
- Every Sunshine surface must be inspected in an RTL UI locale before it is
  reported as complete. RTL is not a late-stage localisation pass; it is a
  rendering mode that changes geometry.

Threshold: optical centre offset ≤ 1 CSS px in both directions, and the LTR and
RTL offsets must agree within 0.5 CSS px. The known-good measurement is 0.009 px
and the known defect was 10.087 px, so the threshold discriminates without being
brittle about sub-pixel rounding.

## 8. Motion and focus

### 8.1 Reduced motion

Under `prefers-reduced-motion: reduce`:

- Every Sunshine-authored `animation` and `transition` must be either removed or
  reduced to an opacity or colour change of at most 200 ms.
- No `translate`, `scale`, `rotate`, parallax, or auto-playing loop, at any
  amplitude.
- `scroll-behavior: smooth` must be overridden to `auto`.
- Motion must never be the sole indication of a state change, in either mode. A
  state that is only distinguishable while animating is undetectable under
  reduce and unrecorded by a screenshot.

Checkable form: every `animation` or `transition` declaration in Sunshine CSS
must have a corresponding declaration inside a
`@media (prefers-reduced-motion: reduce)` block that neutralises it. The New Tab
patch currently declares no motion, so it passes trivially — the rule exists
before the first animation is written, not after.

### 8.2 Focus visibility

- Never `outline: none` or `outline: 0` without a replacement indicator in the
  same rule that is at least as visible. Removing the indicator and relying on a
  background change is not a replacement.
- The indicator is driven by `:focus-visible`, not `:focus`, so that pointer
  users are not shown a ring the keyboard user needs.
- Minimum thickness 2 CSS px, contrast at least 3:1 against every colour it
  abuts (§4.2). Over a theme background image, "every colour it abuts" is
  evaluated by worst-case pixel sampling per §4.1.
- The indicator colour comes from Chromium's WebUI focus token, not from a
  Sunshine literal. See §3 for the binding status of that role.
- Positive `tabindex` is prohibited. Focus order is DOM order.
- Non-interactive elements must not be focusable. `#sunshineWordmark` is a
  heading, not a control: it has no `tabindex` and declares `user-select: none`,
  and must not acquire either an event handler or focusability.
- The focus indicator must survive forced colours (§5.1), which follows from the
  prohibition on `forced-color-adjust: none`.

## 9. Acceptance criteria

Two groups. Group S runs against the source tree with no build. Group R requires
a native `chrome` build at `152.0.7977.42` and does not exist yet.

### 9.1 Group S — source checks, executable today

Each is a pass/fail check over Sunshine-authored CSS in the patch stack.

| ID | Check | Fails when |
|---|---|---|
| S1 | Token provenance | Any `--color-*`, `--cr-*`, or `--ntp-*` identifier consumed by Sunshine CSS is absent from the pinned tree. Requires the pinned checkout; see §10. |
| S2 | No literal colours | A `color`, `background-color`, `border-color`, `outline-color`, `fill`, or `stroke` declaration in Sunshine CSS contains `#`, `rgb(`, `hsl(`, `oklch(`, or a named colour. |
| S3 | No token reassignment | Sunshine CSS assigns to a `--color-*`, `--cr-*`, or `--ntp-*` custom property. |
| S4 | Fallback discipline | A `var()` on a colour token supplies a fallback, or a non-colour token's fallback differs from its documented upstream default. |
| S5 | No typeface declaration | A `font-family` appears in Sunshine surface CSS with any value other than the bare keyword `monospace`. |
| S6 | Type scale conformance | A `font-size` is in `px`, is below 0.6875rem, is off the §6.2 scale, or carries `!important`. |
| S7 | Clamp bounding | A `clamp()` font size violates any of the four conditions in §6.3, or its fluid band is not stated at the declaration. |
| S8 | Weight resolvability | A `font-weight` outside {400, 500, 600, 700} without a recorded R10 result. **Currently failing:** `font-weight: 650`. |
| S9 | Direction declared | An element in the §7.2 lockup set applies a logical inline property without declaring `direction` on the same element. |
| S10 | No forced-colour override | `forced-color-adjust` appears anywhere, or a `@media (forced-colors: active)` or `@media (prefers-contrast: more)` block changes a colour. |
| S11 | Reduced-motion counterpart | An `animation` or `transition` has no neutralising declaration under `prefers-reduced-motion: reduce`. |
| S12 | Focus not suppressed | `outline: none` or `outline: 0` without a replacement indicator in the same rule; or any `tabindex` greater than 0. |
| S13 | No duplicate selector | A rule Sunshine adds to an upstream stylesheet repeats a selector that stylesheet already declares. Requires the pinned tree; see §10. |

**S13 is the one criterion here that is not Sunshine's rule.** Every other row
states something this project decided. S13 states something *Chromium* decided:
its WebUI build lints Sunshine's CSS with its own stylelint config, and
`no-duplicate-selectors` is in it.

It is here because its absence cost a build. Patch `0022` added a second
`#inputWrapper { }` to `ntp_searchbox.css` on purpose — so that no upstream line
was edited and the hunk survived a roll — and native build #46 failed in twenty
seconds on that rule. Everything this repository owns had passed first: S1
through S12, the twenty-seven architecture guards, and `verify_pinned_upstream`,
which proves the patch applies to the real pinned tree. **Each answered the
question it was asked, and none of them was asked whether Chromium would accept
the result.**

The row is deliberately narrow. It is one stylelint rule checked against the
pinned file, not a local stylelint run, and it claims nothing about the other
rules in that config. Widening it means running stylelint, which needs the
checkout — §10.

### 9.2 Group R — runtime checks, require a native build

Run on the pinned build. Unless stated, at 1200×700, 100% zoom, en-US.

| ID | Check | Method | Pass condition |
|---|---|---|---|
| R1 | Wordmark contrast, light theme, no background image | Sample per §4.1 | ≥ 4.5:1 |
| R2 | Wordmark contrast, dark theme, no background image | Sample per §4.1 | ≥ 4.5:1 |
| R3 | Wordmark contrast over solid backgrounds | Set the theme background image to solid `#FFFFFF`, `#000000`, and `#808080` in turn; sample per §4.1 with `--ntp-theme-text-shadow` applied | ≥ 4.5:1 for each of the three |
| R4 | Wordmark contrast over a photograph | Set a high-frequency photographic background; sample per §4.1 | Treatment present and measured minimum recorded. No threshold; see §4.4. |
| R5 | Forced colours | Enable an OS high-contrast theme, once light and once dark | Wordmark visible; ≥ 4.5:1 against its own background in both; computed `text-shadow` is `none` |
| R6 | Increased contrast | Enable the OS increased-contrast setting | R1 and R2 still pass; no Sunshine-authored colour differs from the R1/R2 run |
| R7 | Reflow | 200% and 400% zoom at 1280×1024 | No horizontal scrollbar attributable to the wordmark; no clipping; no overlap with the searchbox or Most Visited |
| R8 | User font size | Set the browser font size to its largest setting | Wordmark grows, proving the `rem` bounds are live rather than `px` in disguise |
| R9 | Direction | Measure optical centre at 360, 800, and 1920 px widths in both `dir=ltr` and `dir=rtl` | \|offset\| ≤ 1 CSS px in each case, and \|LTR − RTL\| ≤ 0.5 CSS px at each width |
| R10 | Weight resolvability | Render the wordmark at weights 600, 650, and 700 and diff the rasters, on each supported platform and in en-US and ko-KR | 650 differs from both neighbours, or the declaration is replaced by the nearest resolvable weight |
| R11 | Inherited typeface | Read computed `font-family` on the wordmark in en-US and ko-KR | Equals the WebUI default for that locale, and differs between locales wherever Chromium's localised font resource differs |
| R12 | Focus | Tab through the New Tab surface | The wordmark never receives focus; every focusable control shows a `:focus-visible` indicator ≥ 2 CSS px at ≥ 3:1 against every abutting colour, in both normal and forced-colours mode |
| R13 | Reduced motion | Enable the OS reduce-motion setting | No Sunshine-authored motion occurs |
| R14 | Rem anchoring | Read the computed base font size and the element it is set on | Confirms whether `rem` tracks Chromium's localised base size; see §10 |

Together with the existing New Tab verification gate
(`docs/SUNSHINE_NEW_TAB_SPEC.md`), Group R covers default size, narrow width,
200% zoom, light theme, and dark theme.

### 9.3 Not verified

Nothing in this document has been verified at runtime. Specifically:

- No native Chromium build has been produced. Group R has not been run, in whole
  or in part.
- Check S1 has not been run: this session has no pinned Chromium checkout, so no
  token identifier has been proven to exist upstream.
- The two colour tokens in §3 are asserted only by the Sunshine patch itself.
  Nothing in this repository independently confirms
  `--color-new-tab-page-primary-foreground` or `--ntp-theme-text-shadow` exist at
  `152.0.7977.42`, or that they carry the semantics assumed here.
- No contrast ratio has been measured, in any mode, against any background.
- Checks S2 through S12 are specified but not yet implemented as an automated
  gate. S8 is stated as currently failing on inspection of the patch, not on a
  tool's output.
- The type scale in §6.2 has not been reconciled against Chromium's own WebUI
  text defaults at the pinned revision.
- No claim is made that patch `0002` applies to real upstream sources. That
  remains owned by the CI architecture guard.
- **S13 covers one stylelint rule, not the config.** Chromium's
  `stylelint.config_base.mjs` holds more rules than `no-duplicate-selectors`,
  and the next one Sunshine breaks will be found the same way #46's was — by a
  build. The only check that would answer the general question is running
  stylelint itself, which needs the pinned checkout.

## 10. Values only the pinned Chromium source can supply

These are open and must be resolved from the pinned tree before the affected
rules can be enforced. Each is a gap in this contract, not a decision deferred by
preference.

| Open item | Why it matters | Where to resolve it |
|---|---|---|
| Existence and semantics of `--color-new-tab-page-primary-foreground` | The wordmark's only colour source; S1 and R1/R2 depend on it | `ui/color/color_id.h`, `chrome/browser/ui/color/chrome_color_id.h`, and the WebUI colour-token generation |
| Existence, value shape, and trigger condition of `--ntp-theme-text-shadow` | §4.4 makes it mandatory over background images; whether it resolves to `none` without an image determines whether R1/R2 and R3 are the same measurement | New Tab Page theme code in `chrome/browser/resources/new_tab_page/` |
| Concrete identifiers for the unbound roles in §3 | Secondary foreground, surface background, outline, focus indicator, accent, error are all unbound; guessing at names that fit the pattern is prohibited | Same colour-ID sources |
| Element carrying Chromium's localised WebUI base font size | If the base size is set on `body` rather than the root, `rem` does not track it and the §6.2 scale must be restated in `em` on the surface container | Chromium's WebUI text defaults stylesheet; empirically, check R14 |
| Whether the WebUI UI font exposes a continuous weight axis per platform and locale | Decides whether `font-weight: 650` is meaningful or inert (S8, R10) | Platform font resources at the pinned revision |
| Chromium's behaviour for New Tab background images under `forced-colors: active` | Determines whether R5 must be run with a background image set as well as without | Forced-colours handling in the New Tab Page and Blink |

## 11. Change control

This contract is amended by editing this file. A rule may be relaxed only
through a decision record in `docs/decisions/` that names the rule, the surface
that could not meet it, and what was tried. A Sunshine surface that cannot meet a
rule is not evidence that the rule is wrong.

Until a native build at `152.0.7977.42` exists and Group R has been run, work
governed by this document is reported as a **documentation contract**, not a
verified appearance guarantee.
