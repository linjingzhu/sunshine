#!/usr/bin/env python3
"""Send the set's current release to every repository that subscribes to it.

Run at the set's home, after a release has merged. `.ai/SUBSCRIBERS.md` lists
the subscribers; each needs a clone under `--clones`, named after the
repository. For every subscriber this fetches its base branch, cuts
`claude/set-<version>` from it, runs `adopt.py --upgrade`, and commits. The
pull request body, with the upgrade's own report and check result, is written
beside the clone as `<repo>.pr.md`; opening the pull request is left to
whoever runs this, because that needs the forge's credentials, not git's.

    python3 .ai/tools/propagate.py --clones ../subscribers [--push] \\
        [--trailer "Co-Authored-By: ..."]

A subscriber marked `hold` is named and skipped. Nothing is pushed without
`--push`, so a first run shows every upgrade before any of them leaves this
machine. Standard library only.

Exit status is 0 when every subscriber not on hold is upgraded or already
current, 1 otherwise.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

sys.dont_write_bytecode = True
SET_ROOT = Path(__file__).resolve().parents[2]
REGISTRY = SET_ROOT / ".ai" / "SUBSCRIBERS.md"
ADOPT = SET_ROOT / ".ai" / "tools" / "adopt.py"
# `owner/repo  base-branch`, optionally followed by `hold: <why>`.
ENTRY = re.compile(r"^([\w.-]+/[\w.-]+)\s+(\S+)(?:\s+hold:\s*(.+))?$")


def subscribers(text: str) -> list[tuple[str, str, str | None]]:
    """The entries inside the registry's fenced block, in order."""
    found: list[tuple[str, str, str | None]] = []
    fenced = False
    for number, line in enumerate(text.splitlines(), 1):
        if line.lstrip().startswith("```"):
            fenced = not fenced
            continue
        if not fenced or not line.strip() or line.lstrip().startswith("#"):
            continue
        match = ENTRY.match(line.strip())
        if not match:
            raise SystemExit(f"{REGISTRY.name} line {number}: expected `owner/repo  base [hold: why]`: {line}")
        found.append((match.group(1), match.group(2), match.group(3)))
    return found


def release(root: Path) -> str:
    for line in (root / ".ai" / "CHANGELOG.md").read_text(encoding="utf-8").splitlines():
        if re.match(r"^## \d+\.\d+\.\d+ ", line):
            return line[3:].split()[0]
    return "unknown"


def git(clone: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", "-C", str(clone), *args], capture_output=True, text=True)


def upgrade_one(clone: Path, base: str, version: str, trailers: list[str], push: bool) -> tuple[str, str]:
    """Returns (outcome, detail). Outcome is upgraded, current or failed."""
    branch = f"claude/set-{version}"
    # Switching carries uncommitted work along, and `add -A` would commit it
    # into the upgrade as if the set had delivered it.
    dirty = git(clone, "status", "--porcelain").stdout.strip()
    if dirty:
        return "failed", f"the clone has uncommitted changes, which would ride into the upgrade:\n{dirty}"
    for step in (("fetch", "-q", "origin", base), ("switch", "-q", "-C", branch, f"origin/{base}")):
        done = git(clone, *step)
        if done.returncode:
            return "failed", f"git {step[0]}: {done.stderr.strip()}"
    before = release(clone) if (clone / ".ai" / "CHANGELOG.md").exists() else "none"
    run = subprocess.run([sys.executable, "-B", str(ADOPT), "--upgrade", "--into", str(clone)],
                         capture_output=True, text=True)
    report = run.stdout + run.stderr
    if run.returncode:
        return "failed", "the set's check fails after the upgrade:\n" + report
    git(clone, "add", "-A")
    if git(clone, "diff", "--cached", "--quiet").returncode == 0:
        return "current", f"already at {before}"
    message = (
        f"Upgrade the ai-dev-rule policy set from {before} to {version}\n\n"
        "Ran `adopt.py --upgrade` from the set's home. The set's files are a\n"
        "subscribed copy recorded in `.ai/set.lock`; every file this repository\n"
        "owns was handed back. The set's check passes in this tree.\n"
    )
    if trailers:
        message += "\n" + "\n".join(trailers) + "\n"
    done = git(clone, "-c", "commit.gpgsign=false", "commit", "-q", "-m", message)
    if done.returncode:
        return "failed", f"git commit: {done.stderr.strip()}"
    if push:
        done = git(clone, "push", "-q", "-u", "origin", branch)
        if done.returncode:
            return "failed", f"git push: {done.stderr.strip()}"
    # A tree made with "Use this template" and never finished still carries
    # the file that marks the set's home, so its checks believe they are here
    # and the subscription is never asked about.
    unfinished = (clone / "LESSONS_FROM_PRACTICE.md").exists()
    files = git(clone, "diff", "--name-status", "HEAD~1", "HEAD").stdout.strip().splitlines()
    flags = [line for line in report.splitlines() if line.startswith(("[local]", "[stale]"))]
    results = [line for line in report.splitlines() if line.startswith(("[PASS]", "[FAIL]", "[SKIP]"))]
    body = [
        f"Upgrades the ai-dev-rule policy set: **{before} → {version}**.", "",
        "`adopt.py --upgrade`, run from the set's home, replaced the set's files and "
        "handed back every file this repository owns. The set's files are now a "
        "subscribed copy recorded in `.ai/set.lock`: the set's check fails if one is "
        "edited here. A rule only this repository needs goes in its project context, "
        "under Local rules.", "",
        "## The set's check in this tree", "", "```text", *results, "```", "",
        "## Files the upgrade named", "",
        *([f"- `{line}`" for line in flags] or ["- none: no `[local]` or `[stale]` file"]), "",
        f"## Changed files ({len(files)})", "", "```text", *files, "```", "",
        f"What changed in the set: `.ai/CHANGELOG.md`, the entries above {before}.",
    ]
    if unfinished:
        body[2:2] = [
            "**This repository still looks like the set's own home.** It holds "
            "`LESSONS_FROM_PRACTICE.md`, so it was made with \"Use this template\" and "
            "`adopt.py --from-template` was never run. Its checks therefore skip the "
            "subscription. Finishing it needs the project's facts, which only its owner has.", "",
        ]
    (clone.parent / f"{clone.name}.pr.md").write_text("\n".join(body) + "\n", encoding="utf-8")
    note = "; template copy never finished, so the subscription is not checked there" if unfinished else ""
    return "upgraded", f"{before} → {version}, {len(files)} files, {len(flags)} named{note}"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--clones", type=Path, required=True, help="directory holding one clone per subscriber")
    parser.add_argument("--push", action="store_true", help="push each upgrade branch")
    parser.add_argument("--trailer", action="append", default=[], help="a line to end each commit message with")
    args = parser.parse_args(sys.argv[1:] if argv is None else argv)

    if not REGISTRY.is_file():
        raise SystemExit(
            f"no {REGISTRY.relative_to(SET_ROOT)}: propagation runs at the set's home, "
            "which lists its subscribers there"
        )
    version = release(SET_ROOT)
    failed = 0
    for repository, base, hold in subscribers(REGISTRY.read_text(encoding="utf-8")):
        name = repository.split("/")[1]
        clone = args.clones.resolve() / name
        if hold:
            print(f"[hold]     {repository}: {hold}")
            continue
        if not (clone / ".git").exists():
            print(f"[no clone] {repository}: expected at {clone}")
            failed += 1
            continue
        outcome, detail = upgrade_one(clone, base, version, args.trailer, args.push)
        failed += outcome == "failed"
        print(f"[{outcome}]{' ' * (9 - len(outcome))}{repository}: {detail}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
