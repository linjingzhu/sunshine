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
  * every declared *addition* -- an overlay file upstream does not have, which
    a patch introduces by naming it -- is really in the overlay, is really
    named by the patch that claims to name it, and brings its whole set of
    scale factors with it

What is *not* checked here is whether the destination exists upstream. That
needs the pinned revision, so `scripts/verify_pinned_upstream.py` owns it, and
it asks the question in both directions: a replacement upstream deleted or
renamed would otherwise write a new file into the checkout and change nothing
about the build, and an addition upstream has since acquired would silently
overwrite a real Chromium file instead of adding Sunshine's.

**Why additions are declared rather than inferred.** An overlay file that
upstream does not have could be recognised by asking upstream, but then a
mistyped destination -- `default_200_pecent/`, a renamed subdirectory -- would
answer "upstream does not have it" and be waved through as an addition, which
is exactly the failure the existence probe exists to catch. Declaring them
turns both mistakes into failures: a typo is an undeclared file that upstream
lacks, and a stale declaration is a declared file upstream has.

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

# Overlay destinations Chromium does not have, mapped to the patch that gives
# each one a reader. Nothing in the tree looks for a file by this path on its
# own -- an added image is reachable only because a `.grd` entry names it, so
# the patch carrying that entry is the other half of the addition and is named
# here so the two can be checked against each other.
ADDITIONS: dict[str, str] = {
    "chrome/app/theme/default_100_percent/sunshine/bookmark_folder.png":
        "0026-sunshine-bookmark-folder-artwork.patch",
    "chrome/app/theme/default_200_percent/sunshine/bookmark_folder.png":
        "0026-sunshine-bookmark-folder-artwork.patch",
    "chrome/app/theme/default_300_percent/sunshine/bookmark_folder.png":
        "0026-sunshine-bookmark-folder-artwork.patch",
}

# The scale factors `chrome/app/theme/theme_resources.grd` reads: one `<output>`
# per context. `fallback_to_low_resolution="true"` in that file means a missing
# one does not fail the build -- Chrome upscales the 100 percent image, and the
# result is soft on exactly the machines that have the pixels for it and
# nowhere else. So a partial set is refused here, where it is visible.
THEME_SCALE_DIRECTORIES = ("default_100_percent", "default_200_percent",
                           "default_300_percent")

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


def stack_text(root: Path = ROOT) -> str:
    """Every line the patch stack adds, as one blob to search.

    Only added lines. A path that appears in a patch's *context* is a path
    upstream already reads, which is the opposite of what an addition needs to
    prove.
    """

    lines: list[str] = []
    for patch in sorted((root / "downstream/patches").glob("*.patch")):
        for line in patch.read_text(encoding="utf-8").splitlines():
            if line.startswith("+") and not line.startswith("+++"):
                lines.append(line[1:])
    return "\n".join(lines)


def series_names(root: Path = ROOT) -> list[str]:
    series = root / "downstream/patches/series"
    if not series.is_file():
        return []
    return [line.strip() for line in series.read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.startswith("#")]


def grd_reference(destination: str) -> str:
    """How a `theme_resources.grd` entry names an image at this destination.

    The `<structure file="...">` attribute is relative to the scale directory,
    so the destination's path below `default_NNN_percent/` is the string the
    patch has to contain. Deriving it here rather than storing it keeps the
    directory layout the single declaration it was designed to be.
    """

    parts = PurePosixPath(destination).parts
    for index, part in enumerate(parts):
        if part in THEME_SCALE_DIRECTORIES:
            return PurePosixPath(*parts[index + 1:]).as_posix()
    return PurePosixPath(destination).name


def check_additions(files: dict[str, Path], root: Path, failures: list[str]) -> None:
    """Each declared addition is present, is named by its patch, and is complete."""

    names = series_names(root)
    added = stack_text(root)

    for destination, patch in sorted(ADDITIONS.items()):
        if destination not in files:
            failures.append(
                f"{destination} is declared an addition but is not in the overlay")
            continue
        if patch not in names:
            failures.append(
                f"{destination} names {patch}, which is not in downstream/patches/series")
            continue
        reference = grd_reference(destination)
        if reference not in added:
            failures.append(
                f"{destination} is declared an addition, but no patch adds a line "
                f"naming `{reference}`; an image nothing reads is an image the "
                "build ignores")

    # A scale set is all or nothing. Ask it of the sibling directories rather
    # than of the declaration, so a scale that was rendered but never declared
    # is caught too.
    for destination in sorted(set(ADDITIONS) | set(files)):
        pure = PurePosixPath(destination)
        if not any(part in THEME_SCALE_DIRECTORIES for part in pure.parts):
            continue
        for scale in THEME_SCALE_DIRECTORIES:
            sibling = PurePosixPath(*[
                scale if part in THEME_SCALE_DIRECTORIES else part for part in pure.parts
            ]).as_posix()
            if sibling not in files:
                failures.append(
                    f"{destination} has no {scale} counterpart; "
                    "theme_resources.grd upscales the 100 percent image silently")


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

    check_additions(files, root, failures)

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

    replacing = [name for name in sorted(files) if name not in ADDITIONS]
    adding = [name for name in sorted(files) if name in ADDITIONS]
    print(f"Asset overlay passed: {len(replacing)} file(s) replacing upstream assets, "
          f"{len(adding)} adding.")
    for destination in replacing:
        print(f"  replaces {destination}")
    for destination in adding:
        print(f"  adds     {destination}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
