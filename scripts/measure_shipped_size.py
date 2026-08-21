#!/usr/bin/env python3
"""Measure what Sunshine actually installs, from upstream's own manifest.

`docs/SIZE_BUDGET.md` names two numbers. One of them has been measured since
build #12: the compressed installer. The other -- **installed app bundle,
investigate above 250 MB** -- has never been measured by anything, because the
only size report this project produces reads `chrome.exe` and
`mini_installer.exe`, and `chrome.exe` is a 4 MB launcher stub whose size says
nothing about what lands on a disk.

So a budget row with a threshold sat next to no measurement, which is the shape
of rule this repository keeps finding out about the hard way.

**The file list is not written here.** `chrome/installer/mini_installer/chrome.release`
is upstream's own manifest of what the installer packs, sectioned by build
configuration, and it is what `mini_installer` is generated from. Reading it is
the only way to get an answer that cannot drift from what actually ships -- a
list maintained here would be a second copy of a file that changes every time
upstream adds a DLL.

What this does not do is install anything. It resolves the manifest against the
build output directory and sums what it finds, which is the same set of bytes
the installer compresses. That is a measurement of the payload, not of the
directory after setup runs; §"What this is not" in the report says so, because
the difference is real: setup also writes a version directory structure and an
uninstall registration.

Sections are reported separately rather than filtered. Which of them apply is a
property of the build configuration -- `GOOGLE_CHROME` is branded-only,
`FFMPEG` depends on how ffmpeg was linked -- and a filter written here would be
a guess about a configuration this script can see directly: a section whose
files are not in the output directory contributes nothing and says so.
"""

from __future__ import annotations

import argparse
import fnmatch
import json
import os
from pathlib import Path, PurePosixPath
import sys

ROOT = Path(__file__).resolve().parents[1]

# `chrome/installer/mini_installer/chrome.release`, relative to the Chromium
# source tree. Upstream's list, read at the pinned revision the workspace holds.
MANIFEST = Path("chrome/installer/mini_installer/chrome.release")

# `[GENERAL]` and friends. A line that is exactly a bracketed name starts a
# section; everything after it belongs to that section until the next one.
SECTION_PREFIX = "["

# `chrome.dll: %(VersionDir)s\`. Only the left side is a file; the right side is
# where setup puts it, which this script has no opinion about.
SEPARATOR = ":"


def parse_release(text: str) -> dict[str, list[str]]:
    """`{section: [source pattern, ...]}`, in file order.

    Comments and blank lines are dropped. A section with no entries is kept --
    `[TOUCH]` is empty at the pinned revision, and reporting it as absent would
    be reporting a fact about this parser rather than about the build.
    """

    sections: dict[str, list[str]] = {}
    current: str | None = None
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if stripped.startswith(SECTION_PREFIX) and stripped.endswith("]"):
            current = stripped[1:-1]
            sections.setdefault(current, [])
            continue
        if current is None or SEPARATOR not in stripped:
            continue
        source = stripped.split(SEPARATOR, 1)[0].strip()
        if source:
            sections[current].append(source)
    return sections


def _candidates(root: Path) -> list[str]:
    """Every file under `root`, as forward-slashed relative paths.

    Built once and matched against, rather than globbing per pattern. The
    manifest's patterns are Windows-shaped (`locales\\*.pak`) and its wildcards
    are not path-aware, so `fnmatch` over a flat list is both simpler and closer
    to what the installer's own generator does than `Path.glob` would be.
    """

    return [
        path.relative_to(root).as_posix()
        for path in root.rglob("*")
        if path.is_file()
    ]


def resolve(
    patterns: list[str], root: Path, candidates: list[str] | None = None
) -> tuple[list[tuple[str, int]], list[str]]:
    """`([(relative path, bytes)], [pattern that matched nothing])`.

    A pattern matching nothing is returned rather than dropped. Most of them are
    expected -- the manifest names Widevine for three architectures and a
    branded build's executables -- but "expected" is a judgement the caller
    makes with the section in hand, and a silent drop would let a genuinely
    missing `chrome.dll` look exactly like an absent `LogoCanary.png`.
    """

    if candidates is None:
        candidates = _candidates(root)
    found: dict[str, int] = {}
    missing: list[str] = []
    for pattern in patterns:
        normalised = pattern.replace("\\", "/")
        if "*" in normalised or "?" in normalised:
            matched = fnmatch.filter(candidates, normalised)
        else:
            matched = [normalised] if normalised in candidates else []
        if not matched:
            missing.append(pattern)
            continue
        for relative in matched:
            # A path reached by two patterns is one file. `chrome.release` does
            # not do this today; a sum that double-counted if it ever did would
            # be wrong in the direction nobody checks.
            found[relative] = (root / PurePosixPath(relative)).stat().st_size
    return sorted(found.items()), missing


def measure(root: Path, manifest_text: str) -> dict:
    sections = parse_release(manifest_text)
    candidates = _candidates(root)
    report: dict = {"sections": {}, "total_bytes": 0, "files": {}}
    for name, patterns in sections.items():
        found, missing = resolve(patterns, root, candidates)
        report["sections"][name] = {
            "bytes": sum(size for _, size in found),
            "files": len(found),
            "absent": missing,
        }
        for relative, size in found:
            report["files"][relative] = size
    report["total_bytes"] = sum(report["files"].values())
    return report


def _megabytes(size: int) -> float:
    return round(size / (1024 * 1024), 1)


def format_report(report: dict, top: int = 12) -> str:
    lines = [
        f"Shipped payload: {_megabytes(report['total_bytes'])} MB "
        f"across {len(report['files'])} file(s)."
    ]
    for name, section in report["sections"].items():
        if not section["files"]:
            lines.append(f"  {name:<16} -- no file of this section is in the build output")
            continue
        absent = f", {len(section['absent'])} pattern(s) absent" if section["absent"] else ""
        lines.append(
            f"  {name:<16} {_megabytes(section['bytes']):>7} MB  "
            f"{section['files']} file(s){absent}"
        )
    biggest = sorted(report["files"].items(), key=lambda item: -item[1])[:top]
    if biggest:
        lines.append(f"  the {len(biggest)} largest:")
        for relative, size in biggest:
            share = 100 * size / report["total_bytes"] if report["total_bytes"] else 0
            lines.append(f"    {_megabytes(size):>7} MB  {share:4.1f}%  {relative}")
    return "\n".join(lines)


def default_workspace() -> Path | None:
    workspace = os.environ.get("SUNSHINE_CHROMIUM_WORKSPACE")
    return Path(workspace) if workspace else None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--out",
        type=Path,
        help="the build output directory; defaults to "
        "$SUNSHINE_CHROMIUM_WORKSPACE/src/out/Sunshine",
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        help=f"upstream's {MANIFEST.as_posix()}; defaults to the one in the workspace",
    )
    parser.add_argument("--json", type=Path, help="also write the measurement here")
    arguments = parser.parse_args()

    workspace = default_workspace()
    out = arguments.out or (workspace / "src" / "out" / "Sunshine" if workspace else None)
    manifest = arguments.manifest or (workspace / "src" / MANIFEST if workspace else None)
    if out is None or manifest is None:
        print(
            "SUNSHINE_CHROMIUM_WORKSPACE is not set and --out/--manifest were not "
            "given, so there is no build to measure.",
            file=sys.stderr,
        )
        return 2
    if not out.is_dir():
        print(f"no build output directory at {out}", file=sys.stderr)
        return 2
    if not manifest.is_file():
        # The whole measurement rests on this file. Guessing a file list instead
        # would produce a number that looks like an answer.
        print(f"upstream's shipped-file manifest is not at {manifest}", file=sys.stderr)
        return 2

    report = measure(out, manifest.read_text(encoding="utf-8"))
    print(format_report(report))
    if arguments.json:
        arguments.json.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
