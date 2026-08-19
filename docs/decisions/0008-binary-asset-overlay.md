# ADR 0008: Binary assets replace, they do not patch

## Status

**Accepted and implemented.** The overlay carries two files: the Windows
application icon and the installer icon.

## Context

The owner supplied artwork for the application icon and asked for it to become
the icon of `chrome.exe` and of the installer. Every Chromium modification in
this project so far has gone through the ordered patch stack in
`downstream/patches/`, so the obvious answer was a ninth patch.

A unified diff cannot carry an icon. Git can encode one — a `GIT binary patch`
section holding the file deflated and base85-encoded — and `git apply` applies
it without complaint. The problem is not git. The problem is that a binary
section has no `--- a/path` / `+++ b/path` pair, and both of the guards that
make this stack trustworthy read exactly that pair:

- `scripts/patch_manifest.py` derives ownership from `+++ b/`. A binary-only
  patch claims no targets, so it would be rejected outright as *"patch has no
  tracked targets"* — and if that check were relaxed, the patch would instead
  own nothing, and the exclusivity rule ADR 0007 just sharpened would stop
  seeing it.
- `scripts/verify_patch_integrity.py` counts hunk-header arithmetic. A binary
  section has no hunks, so there is nothing to count and nothing to verify.

So a binary patch is not merely awkward here; it is invisible to the two things
that watch the stack. Teaching both to parse `GIT binary patch` is possible, and
the cost is that the repository's most-read artifact acquires a form no reviewer
can read: an icon change would arrive as a few thousand characters of base85,
and the diff would be reviewable only by trusting whoever generated it.

There is also a difference in kind. Every existing patch is an *edit*: it finds
context in an upstream file and changes part of it, and the context is what makes
it fail loudly when upstream moves. An icon is a *replacement* — the whole file,
no context, nothing to conflict with. Expressing a replacement as a diff buys
none of the property that makes diffs worth their cost.

## Decision

**Binary assets replace whole upstream files through an overlay, not the patch
stack.** `downstream/assets/` mirrors the Chromium source tree; the mirrored path
*is* the destination, so nothing is declared twice and the two halves cannot
drift apart.

```text
downstream/assets/chrome/app/theme/chromium/win/chromium.ico
downstream/assets/chrome/installer/mini_installer/mini_installer.ico
```

`scripts/bootstrap_chromium.py` copies them into the checkout **after** every
patch has applied, and fails if a destination is not already there.

Three rules make the overlay as accountable as the stack it sits beside:

1. **A path may not be owned by both.** A patch applies first and the overlay
   copies over it, so an overlap silently discards the patch's edit — `git
   apply` succeeds, the copy succeeds, and the build ships an unchanged file.
   `scripts/verify_asset_overlay.py` refuses the overlap rather than letting the
   ordering decide it.
2. **Every destination must exist upstream at the pinned revision.**
   `scripts/verify_pinned_upstream.py` probes each one. A copy cannot fail the
   way a patch does: if upstream renames `chromium.ico`, `git apply` would
   reject a moved hunk but `shutil.copyfile` writes happily beside the real
   file, the `.rc` still names Chromium's, and the build ships Chromium's icon
   under Sunshine's name. This probe is the only thing that would notice.
3. **The bytes are checked, not the extension.** `verify_asset_overlay.py` parses
   the icon directory and requires the size set Chromium's own icons carry
   (16, 32, 48, 256). A truncated or wrongly converted `.ico` still commits and
   still ends in `.ico`; without this it fails at `rc.exe` time on the build
   runner, hours into a queue, on the machine that is also the only CI.

The size set is copied from upstream rather than chosen. Windows picks an icon
entry by exact pixel match and rescales the nearest one when there is none, so a
set that differs from upstream's changes which entry the shell picks at some DPI
settings and not others — a difference that would show up on one machine and not
the next.

## Consequences

**The icons are committed as rendered output, and the renderer is not in CI.**
`scripts/render_app_icons.py` turns `resource/icon.png` into both `.ico` files,
and it is the only script in the repository needing a third-party package —
Pillow decodes and resamples PNG, the standard library does neither. Putting it
in the guard would put a `pip install` between a clean machine and a Chromium
compile, for two files that change about as often as the product name. Instead
the output is committed, `--check` re-renders into memory and compares bytes for
whoever changes the artwork, and every guard that runs in CI is stdlib-only.

**`resource/icon.png` is the source of truth for the artwork, and it is not
itself shipped.** Nothing in the build reads it; it exists so the rendered icons
can be regenerated and so a future size can be added without asking where the
original went.

**The overlay is deliberately small and deliberately dumb.** It has no
templating, no per-platform selection, and no way to add a file upstream does
not have. Each of those is a real requirement someone will eventually bring, and
each should arrive with the case that justifies it rather than being built now
against a guess.

**Whether the icon actually reached the binaries was not knowable in source.**
The overlay is verified in source and against the pinned revision; that the
built `chrome.exe` carries it is a class-B question, decidable only from a
build. `scripts/verify_installed_build.py` now answers it for `chrome.exe`: it
maps the binary as a data file, takes the lowest-numbered `RT_GROUP_ICON` —
`IDR_MAINFRAME`, the one Windows shows for an application — and requires the
images it resolves to be the images this overlay's `.ico` holds. It compares
image payloads and not whole files, because `rc.exe` necessarily rewrites the
directory; and not the size set, because the size set was copied from upstream
and so is shared with the very icon a silent failure would ship.
`mini_installer.exe` is not read, and neither binary's *appearance* is
established by this — `docs/RUNTIME_VERIFICATION.md` RV-10 and RV-11 keep that.

## Alternatives considered

**Teach the guards `GIT binary patch`.** Keeps one mechanism instead of two.
Rejected because it makes the stack's most-read artifact partly unreadable, and
because a whole-file replacement has no context to conflict — it would keep
applying silently through an upstream restructure that a patch would have caught.

**Point Chromium's `.rc` files at Sunshine-owned icon paths via a text patch.**
This is a real option: `chrome/app/chrome_exe.rc` names
`theme\chromium\win\chromium.ico` in a normal `#else` branch, so a one-line diff
could redirect it. Rejected because the icon file still has to arrive somehow —
the redirect solves the pointer and not the payload, so it would need the overlay
anyway, plus a patch, to end up where replacing the file directly already is.

**Convert at build time from `resource/icon.png`.** Removes the committed binary
entirely. Rejected because it makes every Chromium build depend on Pillow being
installed on the build machine, and because the icon that ships would then be
whatever that machine's Pillow produced rather than something reviewed and
committed.
