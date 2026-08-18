#!/usr/bin/env python3
"""Check the binary asset overlay that sits beside the patch stack.

Why an overlay exists at all is `docs/decisions/0008-binary-asset-overlay.md`.
The short of it: a unified diff cannot carry an icon. `git` can encode one, as a
deflated base85 blob under `GIT binary patch`, but that form has no `+++ b/`
header -- so `scripts/patch_manifest.py` would report the patch as owning no
targets, `scripts/verify_patch_integrity.py` would find no hunks to count, and
the two guards that make the stack trustworthy would both be blind to it. The
overlay replaces whole files instead, by mirroring the Chromium path under
`downstream/assets/`, and this is the guard that makes *that* trustworthy.

What is checked here, without touching the network:

  * every overlay file mirrors a path that is syntactically a Chromium source
    path -- relative, no traversal, no absolute root
  * no overlay path is also claimed by the patch stack. A patch applies first
    and the overlay copies over it, so an overlap would silently discard the
    patch's edit. Nothing else would report it: `git apply` succeeds, the copy
    succeeds, and the build ships the file the patch was supposed to change.
  * every `.ico` is a structurally valid Windows icon whose entries are inside
    the file and whose sizes are exactly the set Chromium's own icons carry

What is *not* checked here is whether the destination still exists upstream.
That needs the pinned revision, so `scripts/verify_pinned_upstream.py` owns it.
An overlay whose destination upstream deleted or renamed would otherwise write
a new file into the checkout and change nothing about the build -- the icon
would silently stay Chromium's.

This guard claims no invariant identifier; no contract declares one for the
overlay format.
"""

from __future__ import annotations

from pathlib import Path, PurePosixPath
import struct
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]

OVERLAY_DIR = "downstream/assets"

# Copied from Chromium's `chromium.ico` at the pinned revision, not chosen.
# Windows selects an entry by exact pixel match and rescales the nearest one
# when there is none, so a set that differs from upstream's changes which entry
# the shell picks at some DPI settings and not others.
REQUIRED_ICO_SIZES = frozenset({16, 32, 48, 256})

ICONDIR = struct.Struct("<HHH")
ICONDIRENTRY = struct.Struct("<BBBBHHII")


class OverlayError(ValueError):
    pass


def overlay_files(root: Path = ROOT) -> dict[str, Path]:
    """Destination Chromium path -> the file in this repository that supplies it."""

    base = root / OVERLAY_DIR
    if not base.is_dir():
        return {}

    mapping: dict[str, Path] = {}
    for path in sorted(base.rglob("*")):
        if not path.is_file():
            continue
        destination = path.relative_to(base).as_posix()
        pure = PurePosixPath(destination)
        if pure.is_absolute() or ".." in pure.parts:
            raise OverlayError(f"invalid overlay destination: {destination}")
        if path.stat().st_size == 0:
            raise OverlayError(f"overlay asset is empty: {OVERLAY_DIR}/{destination}")
        mapping[destination] = path
    return mapping


def patch_targets(root: Path = ROOT) -> set[str]:
    """Every path the patch stack claims, asked of the tool that owns the answer.

    Shelling out rather than importing keeps one definition of what a patch
    claims. `--paths` prints upstream targets only, which is exactly the set an
    overlay could collide with: a path the stack *creates* does not exist
    upstream, so an overlay replacing it would be replacing Sunshine's own file
    and is caught by the same comparison for a different reason.
    """

    result = subprocess.run(
        [sys.executable, str(root / "scripts/patch_manifest.py"), "--paths"],
        capture_output=True,
        text=True,
        check=True,
    )
    return set(result.stdout.split())


def untracked(root: Path, destinations: list[str]) -> list[str]:
    """Overlay files git is not carrying, which are the ones CI will not see.

    This is not hypothetical tidiness. `.gitignore` listed `chromium/`, and
    without a leading slash that matches a directory of the name at *any* depth
    -- so `downstream/assets/chrome/app/theme/chromium/win/chromium.ico` was
    ignored, and the application icon was silently left out of its own commit.
    Every check in this file passed anyway, because the file was on the disk of
    the machine running them.

    That is the shape of the failure worth spending a subprocess on: the build
    runner checks out from git, finds no icon to copy, and ships Chromium's
    under Sunshine's name with every step reporting success.
    """

    result = subprocess.run(
        ["git", "-C", str(root), "ls-files", "-z", "--", OVERLAY_DIR],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        # No git, or not a checkout. Reporting every asset as untracked here
        # would be a confident lie; the tracked-ness of a file is unknown, not
        # false.
        return []

    tracked = {
        entry.removeprefix(f"{OVERLAY_DIR}/")
        for entry in result.stdout.split("\0")
        if entry
    }
    return [destination for destination in destinations if destination not in tracked]


def ico_sizes(path: Path) -> set[int]:
    """The square sizes a Windows icon declares, validated against the file.

    Reading the directory rather than trusting the extension is the point. A
    truncated or wrongly converted icon still ends in `.ico`, still commits, and
    fails at `rc.exe` time on the build runner -- which is hours into a queue on
    the machine that is also the only CI.
    """

    data = path.read_bytes()
    if len(data) < ICONDIR.size:
        raise OverlayError(f"{path.name}: too short to be an icon")

    reserved, kind, count = ICONDIR.unpack_from(data, 0)
    if reserved != 0 or kind != 1:
        raise OverlayError(f"{path.name}: not a Windows icon (reserved={reserved}, type={kind})")
    if count == 0:
        raise OverlayError(f"{path.name}: icon declares no images")

    end = ICONDIR.size + count * ICONDIRENTRY.size
    if len(data) < end:
        raise OverlayError(f"{path.name}: icon directory runs past the end of the file")

    sizes: set[int] = set()
    for index in range(count):
        offset = ICONDIR.size + index * ICONDIRENTRY.size
        width, height, _colours, _reserved, _planes, _bits, length, start = ICONDIRENTRY.unpack_from(
            data, offset
        )
        # Zero means 256 in the directory; the field is one byte and 256 does
        # not fit. An icon that really were 0 px wide has no meaning.
        width = width or 256
        height = height or 256
        if width != height:
            raise OverlayError(f"{path.name}: entry {index} is {width}x{height}, not square")
        if length == 0:
            raise OverlayError(f"{path.name}: entry {index} ({width}px) holds no image data")
        if start + length > len(data):
            raise OverlayError(
                f"{path.name}: entry {index} ({width}px) points past the end of the file"
            )
        sizes.add(width)
    return sizes


def validate(root: Path = ROOT) -> list[str]:
    """Every problem found, as lines. Empty means the overlay is sound."""

    failures: list[str] = []
    files = overlay_files(root)
    if not files:
        return failures

    for destination in untracked(root, sorted(files)):
        failures.append(
            f"{destination} is not tracked by git; the build runner checks out "
            "from git and would find nothing to copy (check .gitignore)"
        )

    claimed = patch_targets(root)
    for destination in sorted(files):
        if destination in claimed:
            failures.append(
                f"overlay and patch stack both own {destination}; "
                "the overlay copies over the patch and discards its edit"
            )

    for destination, path in sorted(files.items()):
        if not destination.endswith(".ico"):
            continue
        sizes = ico_sizes(path)
        if sizes != set(REQUIRED_ICO_SIZES):
            expected = ", ".join(f"{size}px" for size in sorted(REQUIRED_ICO_SIZES))
            found = ", ".join(f"{size}px" for size in sorted(sizes)) or "none"
            failures.append(f"{destination}: icon carries {found}; upstream carries {expected}")

    return failures


def main() -> int:
    try:
        files = overlay_files()
        failures = validate()
    except OverlayError as error:
        print(f"Asset overlay check failed: {error}", file=sys.stderr)
        return 1

    if failures:
        print("Asset overlay check failed:", file=sys.stderr)
        for failure in failures:
            print(f"  {failure}", file=sys.stderr)
        return 1

    print(f"Asset overlay passed: {len(files)} file(s) replacing upstream assets.")
    for destination in sorted(files):
        print(f"  {destination}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
