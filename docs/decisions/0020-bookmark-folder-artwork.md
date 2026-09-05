---
doc_id: adr-0020-bookmark-folder-artwork
version: 1.0.0
canonical_path: docs/decisions/0020-bookmark-folder-artwork.md
updated: 2026-09-03
---

# ADR 0020: The bookmark bar's folder mark is artwork, not a themed icon

## Status

**Accepted, and implemented by `downstream/patches/0026-sunshine-bookmark-folder-artwork.patch`
and the bookmark bar hunks of `downstream/patches/0008-sunshine-module-home-button.patch`.**
Read against the pinned revision `152.0.7977.42`. It is not compiled here; the
NOT VERIFIED section says exactly what that leaves open.

## Context

The owner asked whether the folder icons on the bookmark bar could be changed,
and then supplied the drawing: `resource/folder.png`, a 1200 px folder with a
cyan back panel, a translucent blue front panel and a lavender edge, beside
`resource/folder-reference.jpg` showing the same drawing as a reference.

The first plan was a vector icon — swap the glyph `chrome::GetBookmarkFolderIcon()`
returns for a Sunshine-owned `.icon` file, which ADR 0014 section 5 had already
named as the follow-up it deferred. That plan is wrong for *this* drawing, and
the reason is not a matter of degree.

**A `gfx::VectorIcon` is monochrome by construction.** `PaintPath()` fills
every path in one `SkColor`, and the colour is not the icon's: it is handed in
at the call site, from `kColorBookmarkFolderIcon`, which the mixer binds to
`ui::kColorIcon`. An icon file can set a path's colour with `PATH_COLOR_ARGB`,
but then it is a literal colour in a themed control — the same defect
`docs/DESIGN_SYSTEM_CONTRACT.md` rule S2 refuses in CSS, one layer down. Two
gradients and a translucent overlap cannot be said in that language at all.

So the choice was not "vector or raster". It was "this drawing or a different
drawing".

## Decision

**The drawing ships as a pre-scaled theme image, and the bookmark bar draws it
instead of the themed vector icon.**

### 1. `theme_resources.grd`, which is the mechanism that already exists

`chrome/app/theme/theme_resources.grd` is Chromium's one resource family that
is already per-scale: each `<structure type="chrome_scaled_image">` names a
file that grit reads once out of `default_100_percent/`, once out of
`default_200_percent/` and once out of `default_300_percent/`. Upstream keeps
`IDR_BOOKMARK_BAR_FOLDER_MANAGED` there, so a raster bookmark folder is not
even a novel use of it.

The patch adds one line, `IDR_SUNSHINE_BOOKMARK_FOLDER`, and the file becomes
the **28th upstream file the stack owns**. Nothing else was needed:
`bookmark_bar_view.cc` already includes grit's generated theme-resources header
-- which is why no path to it is written here; it exists only under `gen/` after
a build, and citing it would be citing a file the pinned tree does not have --
along with `ui/base/resource/resource_bundle.h`, and it already has a file-local
`GetImageSkiaNamed()` helper. No `resource_ids.spec` change either — the entry
is a `<structure>` in a static grd, which grit counts itself.

The alternative was a Sunshine-owned grd and pak, which is what ADR 0007
measured for WebUI resources and found worth building. It is not worth building
for one image: it would need an id range, a pak line, and pak loading, against
one line in a file the stack can own for the same price.

### 2. The overlay had to learn to add, not only replace

A unified diff cannot carry a PNG — ADR 0008 established that and built the
overlay for it. But ADR 0008's overlay *replaces*: rule 2 requires every
destination to exist upstream at the pinned revision, because a `shutil.copyfile`
that lands beside a renamed file is the one failure a copy has and a patch does
not.

These three images are new. `chrome/app/theme/default_100_percent/sunshine/`
does not exist upstream and should not.

**Additions are declared, not inferred.** `scripts/verify_asset_overlay.py`
carries an `ADDITIONS` table mapping each added destination to the patch that
gives it a reader, and `scripts/verify_pinned_upstream.py` now asks upstream a
different question of each kind:

| kind | upstream must | the failure it prevents |
|---|---|---|
| replacement | **have** the path | upstream renamed it; the copy lands beside the real file and the build ships Chromium's bytes under Sunshine's name |
| addition | **not have** the path | upstream grew a file of that name; the copy quietly replaces a real resource, and the `.grd` entry may now read upstream's drawing |

Recognising an addition by asking upstream instead would let a mistyped
destination — one letter out of `default_200_percent` — answer "upstream does
not have it" and be waved through, skipping the probe that exists to catch it.
Declaring turns both mistakes into failures: a typo is an undeclared file
upstream lacks, and a stale declaration is a declared file upstream has.

Two further checks come with the table, and both are about the silent failure
rather than the loud one:

- **A declared addition no patch names is refused.** grit complains about a
  `file=` with no file; nothing complains about a file with no `file=`. An
  image the build ignores would otherwise sit in the overlay looking applied.
- **A scale set with a hole is refused.** `theme_resources.grd` declares
  `fallback_to_low_resolution="true"`, so a missing 200 percent image does not
  fail the build: Chrome upscales the 100 percent one, and the icon is soft on
  exactly the machines that have the pixels for it and nowhere else.

### 3. Three files, generated rather than exported

`scripts/render_theme_images.py` renders all three from `resource/folder.png`,
and `--check` re-renders into memory and compares bytes. Three files that must
be the same drawing at three sizes is three chances for one of them to be a
different drawing.

The base size is **24 dip, and it is not chosen**: it is what
`GetDefaultSizeOfVectorIcon()` returns for the icon being replaced — the first
rep of `components/vector_icons/folder_chrome_refresh_old.icon` — and the bar
asks for no size. Any other value moves every button on the bar.

The source is cropped to its alpha bounding box first. A bookmark bar button
sizes itself to the image it is given, so shipping the source's transparent
margin would draw the folder at two thirds of the slot and align it with
nothing beside it.

### 4. The hunks live in patch 0008, which is not where they belong

`chrome/browser/ui/views/bookmarks/bookmark_bar_view.cc` is owned exclusively
by patch 0008 under ADR 0007, so the call-site changes are in that patch and
not in 0026 — which is why a patch named for the module home button now also
carries the folder mark. `scripts/patch_manifest.py` refuses the alternative
outright, and it is right to: two patches editing one file is how a rebase
becomes a negotiation.

This is the second time the rule has placed a hunk away from its subject; the
first was the `resource_ids.spec` entry in patch 0004. It is the cost of
exclusive ownership and it is smaller than the thing it buys.

### 5. What deliberately keeps Chromium's icon

**The managed-bookmarks button.** It marks a folder the profile's policy
controls, which is a different thing to say than "this is a folder". Saying it
in the owner's artwork would say the second and lose the first.

**Both button states get the same image.** Upstream passes
`ui::kColorIconDisabled` for `STATE_DISABLED`; a raster takes no colour. The
bar's disabled cue is the label colour `ConfigureButton()` sets two lines
above, which is untouched. A faded second resource was considered and rejected
as three more PNGs for a state a bookmark folder button is essentially never
in.

## Consequences

- The stack owns **28 upstream files instead of 27**, and 26 patches instead of
  25. The new file, `chrome/app/theme/theme_resources.grd`, is a long
  alphabetically-sorted list — churn-prone in volume, but a one-line insertion
  in a sorted list is about the cheapest hunk to rebase there is.
- **The opened menu still shows Chromium's folder icon.** Clicking a folder on
  the bar drops a menu drawn by
  `chrome/browser/ui/views/bookmarks/bookmark_menu_delegate.cc` (lines 1131 and
  1195 at the pinned revision), which the stack does not own. So the bar wears
  the artwork and the menu inside it does not. Fixing that is a 29th upstream
  file and no other new mechanism — it is priced, not blocked, and it is a
  product question rather than a technical one: a native menu's icons are
  monochrome by convention, and a colour folder in one is a deliberate break
  from that rather than an oversight.
- The artwork is 89 KB of source rendered to three small PNGs; the shipped cost
  is the three, and `scripts/measure_shipped_size.py` owns the number.
- `resource/folder.png` and `resource/folder-reference.jpg` were moved there
  from the repository root, where they were uploaded, to sit beside
  `resource/icon.png` — the convention `scripts/render_app_icons.py` already
  reads from.

## NOT VERIFIED

- **Nothing here has been compiled.** The stack applies cleanly to a fresh
  checkout of the pinned revision, and the modified `theme_resources.grd`
  parses as XML — both were run. Neither is grit, and neither is a compiler.
- **Whether grit accepts the new `<structure>` is unverified.** The entry was
  written from upstream's own neighbouring entries; the images are where the
  scale directories say they should be. Only a build says yes.
- **How the drawing reads at 16 px is not known from here.** It was rendered
  and inspected at 16, 24, 32 and 48 offline, and 24 — the size the bar draws
  — holds its two panels. The bar is not a preview sheet, and RV-41 is the
  check that closes this.
- No claim is made about high-contrast or forced-colours mode. A themed vector
  icon follows those; artwork does not, and nothing here measured what that
  looks like.
