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


def patch_targets(root: Path, entries: list[str]) -> dict[str, list[str]]:
    owners: dict[str, list[str]] = defaultdict(list)
    patch_dir = root / "downstream/patches"
    for entry in entries:
        text = (patch_dir / entry).read_text(encoding="utf-8")
        targets = {match.group(1) for line in text.splitlines() if (match := TARGET_LINE.match(line))}
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


def validate(root: Path = ROOT) -> dict[str, list[str]]:
    return patch_targets(root, read_manifest(root))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--paths", action="store_true", help="print upstream target paths")
    args = parser.parse_args()
    try:
        owners = validate()
    except (OSError, ManifestError) as error:
        print(error, file=sys.stderr)
        return 1

    if args.paths:
        print("\n".join(owners))
    else:
        print(f"Patch manifest passed: {len(owners)} exclusive upstream targets.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

