#!/usr/bin/env python3
"""Render the owner's artwork into Chromium's pre-scaled theme images.

`chrome/app/theme/theme_resources.grd` is the one resource family that is
*already* per-scale: each `<structure type="chrome_scaled_image">` names one
file, and grit reads it once out of `default_100_percent/`, once out of
`default_200_percent/`, and once out of `default_300_percent/`. So a raster
that a native view draws needs three files at exactly 1x, 2x and 3x of one
size, and nothing in the tree derives them from each other -- `ninja` copies
whatever bytes are there.

That is what this renders, from one source image per family, and why it exists
rather than three hand-exports: three files that must be the same drawing at
three sizes is three chances for one of them to be a different drawing. The
`grd` declares `fallback_to_low_resolution="true"`, so a missing 2x does not
fail the build -- Chrome upscales the 1x quietly and the icon is soft on every
HiDPI machine and nowhere else. A guard cannot see that. A generator can only
not cause it.

Like `scripts/render_app_icons.py`, this is a hand-run tool and the rendered
output is committed, so no build and no guard needs Pillow:

    python scripts/render_theme_images.py            # rewrite the images
    python scripts/render_theme_images.py --check    # fail if they are stale

**Why the source is cropped, and then inset again.** The owner's folder is
drawn on a square canvas with the drawing somewhere inside it, and that
margin is arbitrary -- it is whatever the export happened to leave, and a
bookmark bar button sizes itself to the image it is given, so shipping it
would draw the folder at whatever fraction of the slot the export chose. So
the crop to the alpha bounding box comes first, and it exists to throw the
unknown margin away.

`COVERAGE` then puts a *known* one back. The first version shipped the cropped
drawing at full width, which is what `BASE_DIP` means, and on the bar it read
as oversized: every other glyph beside it -- Chromium's own icons and the
favicons of ordinary bookmarks -- is drawn with padding inside its box, so an
icon that touches its edges is the one that looks wrong even though it is the
one at nominal size. The inset is in this file rather than in the patch
because it is a property of the drawing, not of the button: changing
`BASE_DIP` would move every button on the bar, and changing `COVERAGE` moves
nothing but the ink.
"""

from __future__ import annotations

import argparse
import io
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]

OVERLAY = "downstream/assets/chrome/app/theme"

# The size the 100 percent image is drawn at, in dip. 24 is not chosen: it is
# what `GetDefaultSizeOfVectorIcon` returns for the folder icon this replaces --
# the first rep of `components/vector_icons/folder_chrome_refresh_old.icon` --
# and the bookmark bar asks for no size, so it is the size the bar draws today.
# Any other value moves every button on the bar.
BASE_DIP = 24

# How much of that box the drawing is allowed to fill, as a fraction of the
# long edge. The rest is transparent margin, centred.
#
# 0.80 is the owner's call, made against the bar they were looking at. It is
# not derived from anything upstream, and it is a constant rather than a
# literal so that the next adjustment is one number in one place and the
# regenerated images follow from it.
COVERAGE = 0.80

SCALES = (100, 200, 300)

# How far a re-render may drift from the committed bytes before `--check` calls
# the images stale, as a per-channel difference out of 255.
#
# **It is not zero, and the reason is a CI failure rather than a preference.**
# `--check` compared bytes, and byte-identity across machines is a property
# Pillow does not offer: the self-hosted Windows runner re-rendered this
# artwork and produced different 48px and 72px images from the same source,
# while the 24px one matched. The committed images were not stale. The check
# was asserting something the tool cannot deliver, and it had never run
# anywhere but Linux before, so nothing had said so.
#
# What the check is for survives the change intact. It exists to catch artwork
# swapped without regenerating, a hand-edited image, and a COVERAGE or BASE_DIP
# that moved without the files following -- and every one of those moves ink by
# whole pixels, which is orders of magnitude above resampling noise. What it
# stops catching is a difference no one can see.
TOLERANCE = 8


class Family:
    """One drawing, its source, and the resource file name grit reads."""

    def __init__(self, source: str, destination: str) -> None:
        self.source = source
        self.destination = destination


FAMILIES = (
    Family("resource/folder.png", "sunshine/bookmark_folder.png"),
)


def render(source: Path, size: int) -> bytes:
    try:
        from PIL import Image
    except ModuleNotFoundError:
        raise SystemExit(
            "Pillow is required to render theme images: pip install Pillow\n"
            "The rendered images are committed, so no guard and no build needs this.")

    art = Image.open(source).convert("RGBA")
    bounds = art.getchannel("A").getbbox()
    if bounds is None:
        raise SystemExit(f"{source} is entirely transparent")
    drawing = art.crop(bounds)

    width, height = drawing.size
    scale = min(size / width, size / height) * COVERAGE
    fitted = drawing.resize((max(1, round(width * scale)), max(1, round(height * scale))),
                            Image.LANCZOS)
    box = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    box.paste(fitted, ((size - fitted.width) // 2, (size - fitted.height) // 2))

    buffer = io.BytesIO()
    box.save(buffer, format="PNG", optimize=True)
    return buffer.getvalue()


def difference(committed: bytes, rendered: bytes) -> tuple[int, str]:
    """(worst per-channel difference, reason it cannot be compared at all).

    Alpha is compared on its own and colour is compared composited over black,
    because a fully transparent pixel's colour channels are not defined: two
    encoders may write anything under `alpha == 0` and the drawings are still
    the same drawing. Comparing raw RGBA would report those as differences of
    up to 255 and turn this check into noise.
    """

    from PIL import Image, ImageChops

    first = Image.open(io.BytesIO(committed)).convert("RGBA")
    second = Image.open(io.BytesIO(rendered)).convert("RGBA")
    if first.size != second.size:
        return 255, f"is {first.size[0]}x{first.size[1]}, a fresh render is {second.size[0]}x{second.size[1]}"

    def flattened(image):
        black = Image.new("RGBA", image.size, (0, 0, 0, 255))
        return Image.alpha_composite(black, image).convert("RGB")

    worst = 0
    for pair in ((flattened(first), flattened(second)),
                 (first.getchannel("A"), second.getchannel("A"))):
        diff = ImageChops.difference(*pair)
        for channel in diff.split():
            worst = max(worst, channel.getextrema()[1])
    return worst, ""


def targets(root: Path = ROOT) -> list[tuple[Path, Path, int]]:
    """(source, destination, pixel size) for every image this tool owns."""

    out: list[tuple[Path, Path, int]] = []
    for family in FAMILIES:
        for scale in SCALES:
            destination = root / OVERLAY / f"default_{scale}_percent" / family.destination
            out.append((root / family.source, destination, BASE_DIP * scale // 100))
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true",
                        help="compare against the committed images instead of writing")
    args = parser.parse_args()

    stale: list[str] = []
    for source, destination, size in targets():
        if not source.is_file():
            print(f"missing source: {source}", file=sys.stderr)
            return 1
        rendered = render(source, size)
        relative = destination.relative_to(ROOT).as_posix()
        if args.check:
            if not destination.is_file():
                stale.append(f"{relative}: not committed")
                continue
            committed = destination.read_bytes()
            if committed == rendered:
                print(f"OK   {relative} ({size}x{size}) byte-identical")
                continue
            worst, why = difference(committed, rendered)
            if why:
                stale.append(f"{relative}: {why}")
            elif worst > TOLERANCE:
                stale.append(
                    f"{relative}: differs from a fresh render of {source.name} "
                    f"by {worst}/255, over the {TOLERANCE} this tool allows for "
                    "one machine's resampler against another's")
            else:
                # Named rather than silent: a reader who sees this wants to know
                # the images were re-encoded somewhere else, not that a check
                # was skipped.
                print(f"OK   {relative} ({size}x{size}) within {worst}/255")
        else:
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(rendered)
            print(f"wrote {relative} ({size}x{size})")

    for line in stale:
        print(f"FAIL {line}", file=sys.stderr)
    return 1 if stale else 0


if __name__ == "__main__":
    raise SystemExit(main())
