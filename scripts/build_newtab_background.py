#!/usr/bin/env python3
"""Assemble a New Tab background from a folder of frames.

A hand-run tool, like `scripts/render_app_icons.py`, and the second script in
the repository that needs Pillow. It is deliberately **not** a browser feature:

    python scripts/build_newtab_background.py frames/
    python scripts/build_newtab_background.py frames/ --fps 30 --pingpong
    python scripts/build_newtab_background.py frames/ --width 2560 --quality 78

**Sunshine cannot do this at runtime, and the reason is a contract rather than
an effort estimate.** Reading 150 files to draw a New Tab would break
`docs/PERFORMANCE_BUDGET.md` PB-4, whose zero-tolerance condition 1 admits one
file on the startup path and says "not once per window, not once per tab".
Composing frames in the browser would then need something to advance them,
which breaks NTB-3 -- the property PB-5a's amendment rests on, and the
condition under which an animated background is permitted to exist at all. So
the frames become a single self-animating file *before* they reach the install
directory, and the browser goes on doing what it is allowed to do: open one
file and let the asset animate itself.

**Ordering is the whole risk.** `frame10.png` sorts before `frame2.png` in
every lexical sort there is, so the obvious implementation produces a scrambled
animation that looks like a bad export rather than a bad sort. `ordered_frames`
sorts digit runs numerically, and `tests/test_newtab_background_builder.py`
holds it to that.

The permitted formats, the output names and the size cap are all **read from
`downstream/patches/0020-sunshine-newtab-background-format.patch`** rather than
written here. They are the browser's rules; a copy of them in this file would
be a second place to change and a first place to be wrong.
"""

from __future__ import annotations

import argparse
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]

FORMAT_PATCH = ROOT / "downstream/patches/0020-sunshine-newtab-background-format.patch"

# What Pillow is asked to write for each name the browser looks for. JPEG is
# absent on purpose: it cannot carry an animation, so a frame folder has no
# business becoming one.
ENCODERS = {
    ".webp": dict(format="WEBP"),
    ".png": dict(format="PNG"),
}

# The frame files worth picking up out of a folder that may also hold a project
# file, a thumbnail or a `.DS_Store`.
FRAME_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tif", ".tiff"}

_DIGITS = re.compile(r"(\d+)")


def natural_key(name: str) -> tuple:
    """Sort key that reads digit runs as numbers.

    `frame2` precedes `frame10`, which is the whole point. Non-digit runs are
    lowercased so a folder mixing `Frame` and `frame` does not split into two
    interleaved sequences.

    Each run becomes a **same-shaped** triple rather than a bare `int` or
    `str`. The obvious version mixes the two, and then a folder holding both
    `1.png` and `a.png` compares an `int` against a `str` and dies with a
    `TypeError` -- from a sort, on a folder a person would call ordinary.
    Digits sort ahead of text at equal position, which is only a tie-break: no
    frame sequence depends on it.
    """
    return tuple(
        (0, int(part), "") if part.isdigit() else (1, 0, part.lower())
        for part in _DIGITS.split(name)
        if part != ""
    )


def ordered_frames(paths):
    """The frame files from `paths`, in playing order."""
    frames = [p for p in paths if p.suffix.lower() in FRAME_SUFFIXES]
    return sorted(frames, key=lambda p: natural_key(p.name))


def pingpong(frames):
    """Forward, then back, with neither endpoint played twice.

    `1..N` followed by `N-1..2`. Repeating an endpoint is what makes a
    ping-pong loop visibly stutter at the turn, and it is the mistake that
    survives review because a still frame looks like a deliberate pause.
    """
    return list(frames) + list(frames[-2:0:-1])


def frame_duration_ms(fps: float) -> int:
    """Milliseconds per frame, as the formats store it.

    Both APNG and WebP hold per-frame durations in milliseconds, so 30 fps is
    33 ms and the clip runs 1% slow. That is inherent to the container rather
    than to this rounding, and it is not worth a correction that would make
    some frames 33 ms and others 34.
    """
    if fps <= 0:
        raise ValueError("fps must be positive")
    return max(1, round(1000.0 / fps))


def _read_patch_text() -> str:
    if not FORMAT_PATCH.is_file():
        raise SystemExit(f"cannot read the format patch: {FORMAT_PATCH}")
    return FORMAT_PATCH.read_text(encoding="utf-8")


def asset_names(patch_text: str | None = None) -> list[str]:
    """The file names the browser looks for, from the patch that names them.

    Read out of `kAssetFileNames[]` and nowhere else. This used to sweep every
    `FILE_PATH_LITERAL` in the patch, which was the same answer only for as
    long as the array was the patch's only path literal. The profile-first
    reader added a second one -- the `Sunshine` directory under the profile --
    and the sweep returned it as a fourth background name. Scoping to the
    array is not a narrower proxy for the old rule; it is the rule the tool
    actually meant.
    """
    text = _read_patch_text() if patch_text is None else patch_text
    block = re.search(
        r"kAssetFileNames\[\]\s*=\s*\{(.*?)\}", text, re.DOTALL
    )
    names = (
        re.findall(r'FILE_PATH_LITERAL\("([^"]+)"\)', block.group(1))
        if block
        else []
    )
    if not names:
        raise SystemExit(
            "no asset names found in kAssetFileNames in the format patch; the "
            "browser's list has moved and this tool would write a file it "
            "will not read"
        )
    return names


def max_asset_bytes(patch_text: str | None = None) -> int:
    """The browser's size cap, from the patch that sets it."""
    text = _read_patch_text() if patch_text is None else patch_text
    match = re.search(
        r"kMaxAssetBytes\s*=\s*(\d+)u?\s*\*\s*(\d+)u?\s*\*\s*(\d+)u?", text
    )
    if not match:
        raise SystemExit(
            "kMaxAssetBytes not found in the format patch; refusing to guess a "
            "cap this tool would then measure against"
        )
    a, b, c = (int(g) for g in match.groups())
    return a * b * c


def default_output(suffix: str, patch_text: str | None = None) -> str:
    """The one name the browser reads for this suffix."""
    for name in asset_names(patch_text):
        if name.lower().endswith(suffix):
            return name
    raise SystemExit(f"the browser reads no {suffix} background")


def _load(path, width):
    from PIL import Image

    with Image.open(path) as image:
        frame = image.convert("RGBA")
        if width and frame.width != width:
            height = round(frame.height * width / frame.width)
            frame = frame.resize((width, height), Image.LANCZOS)
        return frame


def build(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Assemble a New Tab background from a folder of frames."
    )
    parser.add_argument("frames", type=Path, help="folder holding the frames")
    parser.add_argument(
        "-o", "--output", type=Path,
        help="output file; defaults to the name the browser reads for --type",
    )
    parser.add_argument(
        "--type", choices=("webp", "apng"), default="webp",
        help="webp is smaller for photographic material; apng is lossless and "
             "keeps sharp edges, text and alpha exactly (default: webp)",
    )
    parser.add_argument("--fps", type=float, default=30.0, help="frames per second")
    parser.add_argument(
        "--pingpong", action="store_true",
        help="play forward then backward, since no image format can reverse "
             "itself and the frames must carry the return trip",
    )
    parser.add_argument(
        "--width", type=int, default=0,
        help="resample to this width; the page draws the background with "
             "`size=cover`, so pixels beyond the screen are paid for and "
             "discarded",
    )
    parser.add_argument("--quality", type=int, default=80, help="WebP quality, 1-100")
    parser.add_argument(
        "--lossless", action="store_true", help="lossless WebP (much larger)"
    )
    args = parser.parse_args(argv)

    if not args.frames.is_dir():
        print(f"not a folder: {args.frames}", file=sys.stderr)
        return 2

    frames = ordered_frames(sorted(args.frames.iterdir()))
    if not frames:
        print(f"no frames in {args.frames}", file=sys.stderr)
        return 2

    suffix = ".webp" if args.type == "webp" else ".png"
    output = args.output or (ROOT / default_output(suffix))

    sequence = pingpong(frames) if args.pingpong else list(frames)
    duration = frame_duration_ms(args.fps)

    print(f"{len(frames)} frame(s) from {args.frames}")
    print(f"  order   {frames[0].name} ... {frames[-1].name}")
    if args.pingpong:
        print(f"  ping-pong  {len(frames)} -> {len(sequence)} frame(s)")
    seconds = len(sequence) * duration / 1000.0
    print(f"  {duration} ms/frame at {args.fps:g} fps -- {seconds:.2f}s per loop")

    try:
        images = [_load(path, args.width) for path in sequence]
    except ModuleNotFoundError:
        print(
            "Pillow is required and is not installed: python -m pip install Pillow",
            file=sys.stderr,
        )
        return 2

    sizes = {image.size for image in images}
    if len(sizes) != 1:
        print(
            f"the frames are not all one size: {sorted(sizes)} -- resample them "
            f"first, or pass --width to do it here",
            file=sys.stderr,
        )
        return 2
    print(f"  {images[0].width}x{images[0].height}")

    options = dict(ENCODERS[suffix])
    if suffix == ".webp":
        options.update(quality=args.quality, lossless=args.lossless)

    output.parent.mkdir(parents=True, exist_ok=True)
    images[0].save(
        output,
        save_all=True,
        append_images=images[1:],
        duration=duration,
        # The owner's decision: an animated background loops forever. Zero is
        # how both containers spell that.
        loop=0,
        **options,
    )

    written = output.stat().st_size
    cap = max_asset_bytes()
    print(f"\nWrote {output} ({written / 1024 / 1024:.1f} MB, {len(sequence)} frames)")

    if written > cap:
        print(
            f"\nThis is larger than the {cap / 1024 / 1024:.0f} MB the browser "
            f"will read, so it would be refused -- and refused silently, since "
            f"a rejected file and no file look the same on screen.\n"
            f"  --width 2560   most screens are narrower, and `size=cover` "
            f"discards the rest\n"
            f"  --quality 70   for photographic material\n"
            f"  fewer frames   a ping-pong loop already looks twice as long as "
            f"it is",
            file=sys.stderr,
        )
        return 1

    print(f"Under the browser's {cap / 1024 / 1024:.0f} MB cap.")
    print(f"Copy it beside chrome.exe, not into the versioned directory.")
    return 0


if __name__ == "__main__":
    raise SystemExit(build())
