#!/usr/bin/env python3
"""Validate and enumerate the ordered Sunshine Chromium patch stack."""

from __future__ import annotations

import argparse
from collections import defaultdict
from pathlib import Path, PurePosixPath
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
PATCH_NAME = re.compile(r"^(\d{4})-[a-z0-9][a-z0-9-]*\.patch$")
SOURCE_LINE = re.compile(r"^--- (?:a/(.+)|/dev/null)$")
TARGET_LINE = re.compile(r"^\+\+\+ b/(.+)$")


class ManifestError(ValueError):
    pass


def read_manifest(root: Path) -> list[str]:
    series = root / "downstream/patches/series"
    entries = [
        line.strip()
        for line in series.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]
    if len(entries) != len(set(entries)):
        raise ManifestError("patch series contains duplicate entries")

    numbers: list[int] = []
    for entry in entries:
        if PurePosixPath(entry).name != entry:
            raise ManifestError(f"patch series path traversal is forbidden: {entry}")
        match = PATCH_NAME.fullmatch(entry)
        if not match:
            raise ManifestError(f"invalid patch filename: {entry}")
        numbers.append(int(match.group(1)))

    expected = list(range(1, len(entries) + 1))
    if numbers != expected:
        raise ManifestError(
            f"patch numbers must be contiguous and ordered: expected {expected}, got {numbers}"
        )

    patch_dir = series.parent
    on_disk = {path.name for path in patch_dir.glob("*.patch")}
    listed = set(entries)
    if on_disk != listed:
        missing = sorted(listed - on_disk)
        unlisted = sorted(on_disk - listed)
        raise ManifestError(f"patch inventory mismatch; missing={missing}, unlisted={unlisted}")
    return entries


def patch_sections(text: str) -> list[tuple[str, bool]]:
    """(target path, whether the patch creates it) for each file section.

    A section headed `--- /dev/null` adds a file that upstream does not have.
    That distinction has to survive to the caller: the target is still owned
    exclusively, and still may not be claimed by a second patch, but it is not
    an upstream path and must never be asked of the pinned revision. Fetching
    it would 404, and a 404 on a path the stack *creates* would be reported as
    a missing upstream file -- the same false accusation
    `scripts/verify_pinned_upstream.py` documents at length for its citation
    check.
    """

    sections: list[tuple[str, bool]] = []
    lines = text.splitlines()
    for index, line in enumerate(lines):
        target = TARGET_LINE.match(line)
        if not target:
            continue
        previous = SOURCE_LINE.match(lines[index - 1]) if index else None
        created = previous is not None and previous.group(1) is None
        sections.append((target.group(1), created))
    return sections


def patch_targets(root: Path, entries: list[str]) -> dict[str, list[str]]:
    owners: dict[str, list[str]] = defaultdict(list)
    patch_dir = root / "downstream/patches"
    for entry in entries:
        text = (patch_dir / entry).read_text(encoding="utf-8")
        targets = {target for target, _created in patch_sections(text)}
        if not targets:
            raise ManifestError(f"patch has no tracked targets: {entry}")
        for target in targets:
            path = PurePosixPath(target)
            if path.is_absolute() or ".." in path.parts:
                raise ManifestError(f"invalid patch target in {entry}: {target}")
            owners[target].append(entry)

    overlaps = {path: patches for path, patches in owners.items() if len(patches) > 1}
    if overlaps:
        raise ManifestError(f"patch target ownership overlaps: {overlaps}")
    return dict(sorted(owners.items()))


def created_paths(root: Path, entries: list[str]) -> set[str]:
    """Targets the stack creates rather than modifies."""

    patch_dir = root / "downstream/patches"
    created: set[str] = set()
    for entry in entries:
        text = (patch_dir / entry).read_text(encoding="utf-8")
        created.update(target for target, is_new in patch_sections(text) if is_new)
    return created


def upstream_targets(root: Path = ROOT) -> list[str]:
    """The targets that must already exist at the pinned revision."""

    entries = read_manifest(root)
    owners = patch_targets(root, entries)
    created = created_paths(root, entries)
    return [path for path in owners if path not in created]


def validate(root: Path = ROOT) -> dict[str, list[str]]:
    return patch_targets(root, read_manifest(root))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--paths",
        action="store_true",
        help="print the target paths that must exist at the pinned revision; "
        "paths the stack creates are excluded, because they do not",
    )
    args = parser.parse_args()
    try:
        owners = validate()
    except (OSError, ManifestError) as error:
        print(error, file=sys.stderr)
        return 1

    if args.paths:
        print("\n".join(upstream_targets()))
    else:
        created = created_paths(ROOT, read_manifest(ROOT))
        print(
            f"Patch manifest passed: {len(owners)} exclusive targets, "
            f"{len(owners) - len(created)} of them upstream and {len(created)} added."
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())

