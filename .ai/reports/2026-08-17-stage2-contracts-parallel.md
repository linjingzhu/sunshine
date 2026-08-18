# Stage 2 contracts — parallel wave

## Status

COMPLETED_WITH_NOTES

## Scope

Four workers in parallel, one new document each, closing the Stage 2-3
contract gaps that had no native ownership contract. Documentation only; no
downstream runtime patch.

## Conflict control

Each worker owned exactly one new file. The command registry, tests, scripts,
and workflows were Manager-owned and untouched by workers. Where a contract
needed a command that did not exist, workers were instructed to propose it in
their report rather than name it in prose — the command validator fails the
build on an unregistered identifier, so four workers inventing commands in
parallel would have collided at integration. No conflicts occurred.

## Delivered

- `docs/GESTURE_CONTRACT.md` — mouse gestures.
- `docs/BROWSER_UTILITIES_CONTRACT.md` — find, zoom, print, save, view source,
  developer tools, context-menu actions.
- `docs/SECURITY_CENTER_CONTRACT.md` — `sunshine://security` and the threat
  provider abstraction.
- `docs/DESIGN_SYSTEM_CONTRACT.md` — tokens, contrast, typography, direction,
  motion, focus.
- Eleven Chromium-owned commands registered; registry 16 -> 27.
- A CI check that the New Tab colour tokens exist at the pinned revision.

## What the workers corrected in the source requirements

Each contract improved on the handoff rather than restating it.

**Gestures.** The handoff listed suppression conditions without saying when
they are tested, which makes behaviour depend on mid-drag state changes and is
not falsifiable. Suppression is now evaluated once, at button press. The
context menu is deferred rather than destroyed, which is what makes
"cancellation is recoverable" observable. The cancellation reason set is closed,
because those values are telemetry enums and an open set drifts.

**Browser utilities.** The strongest form of this contract is that Sunshine
writes no code, and it argues that explicitly: the requirement is already met,
each utility is a security boundary, and a patch would cost every upstream roll
forever without differentiating anything.

**Security Center.** The handoff's own interface sketch passed a profile
identifier into each URL check. A stable per-user identifier attached to
per-URL lookups is a browsing-history feed whatever the intent. The identifier
is now in-process only, and egress is limited to scheme, host, and port. The
detection cost of excluding path and query is recorded as deliberate rather
than resolved by sending more.

**Design system.** The wordmark's colour tokens are used without a fallback,
deliberately — a fallback colour would look right in light mode and silently
escape the theme everywhere else. That makes their existence load-bearing.

## Defect found in shipped work

`--color-new-tab-page-primary-foreground` and `--ntp-theme-text-shadow` appear
in `0002-sunshine-new-tab.patch` only on added lines. Nothing in the repository
proves they exist upstream. By contrast `--ntp-logo-margin-bottom` is proven,
because upstream's own `#logo` rule sits in the patch context.

If either token is absent, the declaration is invalid and the wordmark silently
loses its colour or shadow. Today's visual verification could not have caught
this: the harness supplied both tokens itself.

CI now fetches the pinned stylesheet and requires upstream to use both. On
failure it prints the colour tokens upstream does define, so the failure names
its own fix. This mirrors the existing check on pinned C++ symbols.

The answer is not yet known — this session cannot reach the upstream host, so
CI is the first run that can decide it.

## Command registration

Eleven Chromium-owned commands from the browser-utilities contract were
registered. All carry `guard: null`, which the validator requires of a
Chromium-owned command.

Two proposals were declined for now:

- The six `security.*` commands. The Security Center has two open P0 product
  decisions, including what a `block` verdict is permitted to do. Registering
  commands for a surface whose behaviour is undecided would fix an interface
  ahead of the decision that shapes it.
- Link and image context-menu actions. They need a context target that a
  palette invocation cannot supply, so a registered identifier would either
  need parameters the registry has no schema for, or would act on the wrong
  thing. The worker recommended against, and that recommendation is accepted.

## Criticism of the command registry, from the workers

Both are valid and neither is addressed in this wave.

- `browser.reload` folds stop-loading into reload. Acceptable for a toolbar
  button with visible state; ambiguous for a gesture binding, which has no way
  to show the user which of the two will happen.
- Commands take no parameters. This is currently an unstated assumption, and it
  is what makes the context-menu actions unregistrable.

## Verification

- Unit/contract suite: 109 passed, up from 108.
- Command registry: 27 commands, up from 16.
- Architecture verifier, module registry, patch manifest: passed.
- Upstream token check: NOT RUN here; requires CI network access.
- Native compile, Windows build, runtime, visual: NOT RUN.
- Adversarial review: FALLBACK REVIEW — Manager review of worker output; no
  independent reviewer.
- Cross-agent review: NOT AVAILABLE.

## Open product decisions for the owner

1. What a `block` verdict from a threat provider may do. Left at an attributed
   advisory; anything stronger is a second blocking path.
2. Whether origin-only egress is accepted, given it reduces detection for
   path-specific threats and constrains which providers are compatible.
3. Whether any fail-closed strict policy should exist, and where.
4. Security Center event retention, currently proposed at 30 days.
5. `font-weight: 650` on the wordmark is outside the statically resolvable set
   and unverified against a variable font. Recorded as an open defect settled by
   runtime verification.
