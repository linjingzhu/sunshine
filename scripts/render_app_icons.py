#!/usr/bin/env python3
"""Render the Windows application icons from the owner's source artwork.

This is a hand-run tool, not a guard, and it is the only script in the
repository that needs a third-party package. Pillow decodes and resamples PNG;
the standard library does neither. Making the build depend on it would put a
pip install between a clean machine and a Chromium compile for the sake of two
files that change about as often as the product name, so the rendered icons are
committed and this script exists to prove where they came from.

    python scripts/render_app_icons.py            # rewrite the committed icons
    python scripts/render_app_icons.py --check     # fail if they are stale

`--check` is what makes the committed output trustworthy without running the
renderer in CI: it re-renders into memory and compares bytes. It is not wired
into the guard, because that would reintroduce the dependency it avoids; it is
for whoever changes the artwork.

The sizes are copied from Chromium's own `chromium.ico` at the pinned revision
(16, 32, 48, 256) rather than chosen. Windows picks an entry by exact match and
scales the nearest one when it cannot, so shipping a set upstream does not ship
would change which entry the shell picks at some DPI and not others.
"""

from __future__ import annotations

import argparse
import io
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]

SOURCE = "resource/icon.png"
OVERLAY = "downstream/assets"

# Every destination Chromium reads these from is a whole-file replacement, so
# the same rendering serves both. They are separate files upstream and stay
# separate here: `mini_installer.ico` is linked into a different executable, and
# a single file symlinked or shared would be a difference from upstream that
# buys nothing.
TARGETS = (
    "chrome/app/theme/chromium/win/chromium.ico",
    "chrome/installer/mini_installer/mini_installer.ico",
)

SIZES = ((16, 16), (32, 32), (48, 48), (256, 256))


def render(source: Path) -> bytes:
    try:
        from PIL import Image
    except ModuleNotFoundError:
        raise SystemExit(
            "Pillow is required to render icons: pip install Pillow\n"
            "The rendered icons are committed, so no guard and no build needs this."
        )

    art = Image.open(source).convert("RGBA")
    if art.size != (256, 256):
        raise SystemExit(f"source artwork must be 256x256, got {art.size[0]}x{art.size[1]}")

    buffer = io.BytesIO()
    art.save(buffer, format="ICO", sizes=SIZES)
    return buffer.getvalue()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true", help="compare against the committed icons")
    args = parser.parse_args()

    source = ROOT / SOURCE
    if not source.exists():
        raise SystemExit(f"source artwork not found: {SOURCE}")

    rendered = render(source)

    stale: list[str] = []
    for target in TARGETS:
        path = ROOT / OVERLAY / target
        if args.check:
            if not path.exists() or path.read_bytes() != rendered:
                stale.append(target)
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(rendered)
        print(f"wrote {OVERLAY}/{target} ({len(rendered)} bytes)")

    if args.check:
        if stale:
            print("Icons are stale; re-run scripts/render_app_icons.py:", file=sys.stderr)
            for target in stale:
                print(f"  {OVERLAY}/{target}", file=sys.stderr)
            return 1
        print(f"Rendered icons match {SOURCE} ({len(TARGETS)} file(s)).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
