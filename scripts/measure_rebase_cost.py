#!/usr/bin/env python3
"""Measure what a Chromium roll costs this patch stack.

`docs/BROWSER_OR_APP_REVIEW.md` argued twice that staying a Chromium downstream
was right, and both times its own NOT VERIFIED section named the one number that
would change the answer:

    This project has not yet rolled the pin once, so the recurring cost of the
    patch stack is an estimate with no data behind it -- and it is the one
    number that would most change section 4 if it turned out large.

This measures it without rolling anything. It fetches the upstream files the
stack owns at some *other* revision, applies the series against them, and
reports which patches conflict and how many hunks need a person.

**Why `--reject` rather than a plain apply.** The first run of this experiment
reported thirteen of sixteen patches failing at trunk, which was wrong in the
most misleading direction. Patch 0004 creates the seam's files; when it fails,
every later patch fails for a missing file *it would itself have received* --
one conflict reading as twelve. `--reject` lands what applies and leaves the
rest, so the chain continues and each patch is judged on its own hunks.

**What this does not measure.** `git apply` succeeding is placement, not a
build: a hunk can land in exactly the right place and still not compile, and
this consults no compiler, no `gn`, and no linter. It is also a partial tree --
only the files the stack owns -- so an upstream change to a symbol these files
merely *call* is invisible here. The number this produces is a floor on the
work a roll costs, and the honest way to read it is as an upper bound on the
good news.

Both source mirrors and the URL shapes belong to `verify_pinned_upstream.py`,
which is imported rather than copied. Two files that must agree about where
Chromium is are two files that will eventually disagree.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
import re
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import patch_manifest  # noqa: E402
import verify_pinned_upstream as upstream  # noqa: E402

PATCHES = ROOT / "downstream/patches"
HUNK = re.compile(r"^@@", re.M)


@dataclass(frozen=True)
class Outcome:
    patch: str
    hunks: int
    rejected: int
    files: tuple[str, ...]

    @property
    def conflicted(self) -> bool:
        return self.rejected > 0


def count_hunks(patch_text: str) -> int:
    """Hunks in a patch, which is the denominator every number here is over."""

    return len(HUNK.findall(patch_text))


def series(root: Path = ROOT) -> list[str]:
    return [
        line.strip()
        for line in (root / "downstream/patches/series").read_text("utf-8").splitlines()
        if line.strip()
    ]


def _rejects(tree: Path) -> list[Path]:
    return sorted(tree.rglob("*.rej"))


def apply_series(tree: Path, root: Path = ROOT) -> list[Outcome]:
    """Apply every patch in order, recording what each one could not place."""

    outcomes: list[Outcome] = []
    for name in series(root):
        patch = root / "downstream/patches" / name
        for stale in _rejects(tree):
            stale.unlink()
        subprocess.run(
            ["git", "apply", "--reject", "--whitespace=nowarn", str(patch)],
            cwd=tree,
            capture_output=True,
            check=False,
        )
        rejected = 0
        files: list[str] = []
        for reject in _rejects(tree):
            rejected += count_hunks(reject.read_text("utf-8", errors="replace"))
            files.append(reject.relative_to(tree).as_posix().removesuffix(".rej"))
            reject.unlink()
        outcomes.append(
            Outcome(name, count_hunks(patch.read_text("utf-8")), rejected, tuple(files))
        )
    return outcomes


def format_report(reference: str, outcomes: list[Outcome]) -> str:
    lines = [f"=== {reference} ==="]
    for outcome in outcomes:
        if not outcome.conflicted:
            lines.append(f"  clean     {outcome.patch:<48} {outcome.hunks:>3} hunk(s)")
            continue
        lines.append(
            f"  CONFLICT  {outcome.patch:<48} "
            f"{outcome.rejected} of {outcome.hunks} hunk(s) rejected"
        )
        lines.extend(f"              {name}" for name in outcome.files)
    conflicted = sum(1 for outcome in outcomes if outcome.conflicted)
    rejected = sum(outcome.rejected for outcome in outcomes)
    total = sum(outcome.hunks for outcome in outcomes)
    lines.append(
        f"=== {reference}: {conflicted} of {len(outcomes)} patches conflict, "
        f"{rejected} of {total} hunk(s) need a person ==="
    )
    return "\n".join(lines)


def build_tree(tree: Path, reference: str, source: str) -> list[str]:
    """Write the stack's owned upstream files at `reference`. Returns the absent."""

    absent: list[str] = []
    for path in patch_manifest.upstream_targets(ROOT):
        destination = tree / path
        destination.parent.mkdir(parents=True, exist_ok=True)
        try:
            destination.write_text(upstream.fetch(source, reference, path), encoding="utf-8")
        except Exception:  # noqa: BLE001
            # A file upstream no longer has is the most expensive shape of roll
            # there is, and it must be reported as itself rather than as a
            # patch that mysteriously failed.
            absent.append(path)
    for command in (
        ["git", "init", "-q", "."],
        ["git", "add", "-A"],
        ["git", "-c", "user.email=x@y", "-c", "user.name=x", "commit", "-qm", "base"],
    ):
        subprocess.run(command, cwd=tree, capture_output=True, check=False)
    return absent


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "reference",
        help="the Chromium revision to measure against, e.g. 153.0.8000.0 or main",
    )
    parser.add_argument("--source", default="github", choices=sorted(upstream.SOURCES))
    arguments = parser.parse_args()

    with tempfile.TemporaryDirectory() as directory:
        tree = Path(directory)
        absent = build_tree(tree, arguments.reference, arguments.source)
        for path in absent:
            print(f"  ABSENT    {path} does not exist at {arguments.reference}")
        outcomes = apply_series(tree)
    print(format_report(arguments.reference, outcomes))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
