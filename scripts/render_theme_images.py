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

**Why the source is cropped.** The owner's folder is drawn on a square canvas
with the drawing inset inside it, and the transparent margin is part of no
icon: a bookmark bar button sizes itself to the image it is given, so shipping
the margin would draw the folder at two thirds of the slot and align it with
nothing beside it. The crop is to the alpha bounding box, and the drawing is
then centred in a square box at its own aspect ratio, which for this artwork
means it touches the left and right edges and leaves the difference above and
below.
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

SCALES = (100, 200, 300)


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
    scale = min(size / width, size / height)
    fitted = drawing.resize((max(1, round(width * scale)), max(1, round(height * scale))),
                            Image.LANCZOS)
    box = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    box.paste(fitted, ((size - fitted.width) // 2, (size - fitted.height) // 2))

    buffer = io.BytesIO()
    box.save(buffer, format="PNG", optimize=True)
    return buffer.getvalue()


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
            elif destination.read_bytes() != rendered:
                stale.append(f"{relative}: differs from a fresh render of {source.name}")
            else:
                print(f"OK   {relative} ({size}x{size})")
        else:
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(rendered)
            print(f"wrote {relative} ({size}x{size})")

    for line in stale:
        print(f"FAIL {line}", file=sys.stderr)
    return 1 if stale else 0


if __name__ == "__main__":
    raise SystemExit(main())
