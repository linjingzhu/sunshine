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
CHECK = SET_ROOT / ".ai" / "tools" / "check_policy_set.py"
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


def default_branch(clone: Path) -> str | None:
    """The branch the remote's HEAD names, or None when it cannot be read."""
    out = git(clone, "ls-remote", "--symref", "origin", "HEAD").stdout
    match = re.search(r"^ref: refs/heads/(\S+)\s+HEAD$", out, re.M)
    return match.group(1) if match else None


def problems(report: str) -> set[str]:
    """The problem lines of a check report: one `- …` line per failure."""
    return {line.strip() for line in report.splitlines() if line.lstrip().startswith("- ")}


def run_check(tool: Path, tree: Path) -> tuple[bool, set[str]]:
    """Whether `tool` fails on `tree`, and the problem lines it prints. The
    exit status decides failure: a checker that crashes prints no lines."""
    done = subprocess.run([sys.executable, "-B", str(tool), str(tree)], capture_output=True, text=True)
    return bool(done.returncode), problems(done.stdout + done.stderr)


def base_check(clone: Path) -> tuple[bool, set[str]]:
    """Whether the tree as it stands fails its own copy of the set's check,
    and what that failure looks like to the check this release ships.

    The second half is what an upgrade's failures are compared against. The
    tree's own checker is older and may word the same failure differently, so
    its lines would make every reworded message look like one the upgrade
    added."""
    own = clone / ".ai" / "tools" / "check_policy_set.py"
    if not own.is_file():
        return False, set()
    failed, _ = run_check(own, clone)
    if not failed:
        return False, set()
    return True, run_check(CHECK, clone)[1]


def upgrade_one(clone: Path, base: str, version: str, trailers: list[str], push: bool) -> tuple[str, str]:
    """Returns (outcome, detail). Outcome is upgraded, current or failed."""
    branch = f"claude/set-{version}"
    # Switching carries uncommitted work along, and `add -A` would commit it
    # into the upgrade as if the set had delivered it.
    dirty = git(clone, "status", "--porcelain").stdout.strip()
    if dirty:
        return "failed", f"the clone has uncommitted changes, which would ride into the upgrade:\n{dirty}"
    # Preflight. A registered base that is no longer where the repository
    # works sends the release to a branch nobody merges from; it was found
    # only when a deleted base made the fetch fail.
    notes: list[str] = []
    default = default_branch(clone)
    if default and default != base:
        notes.append(f"the registry says base `{base}`, but the remote's default branch is "
                     f"`{default}` — correct {REGISTRY.name} if the repository moved")
    drift = "".join(f"{n}\n" for n in notes)
    for step in (("fetch", "-q", "origin", base), ("switch", "-q", "-C", branch, f"origin/{base}")):
        done = git(clone, *step)
        if done.returncode:
            return "failed", f"{drift}git {step[0]}: {done.stderr.strip()}"
    # A repository whose CI does not run the check can break it with its own
    # change and nobody hears until the next release. Say so apart from a
    # failure the upgrade causes: the fix is the repository's, not the set's.
    base_failed, before_problems = base_check(clone)
    if base_failed:
        notes.append(f"`{base}` already failed its own check before this upgrade")
    before = release(clone) if (clone / ".ai" / "CHANGELOG.md").exists() else "none"
    run = subprocess.run([sys.executable, "-B", str(ADOPT), "--upgrade", "--into", str(clone)],
                         capture_output=True, text=True)
    report = run.stdout + run.stderr
    if run.returncode:
        added = sorted(problems(report) - before_problems)
        if base_failed and not added:
            cause = ("the base already failed the set's check before the upgrade, and still fails after it "
                     "— look at the repository's own changes first:\n")
        elif base_failed:
            cause = ("the base already failed the set's check before the upgrade, and the upgrade adds "
                     "failures of its own:\n" + "".join(f"  {a}\n" for a in added) + "\n")
        else:
            cause = "the set's check fails after the upgrade:\n"
        return "failed", drift + cause + report
    git(clone, "add", "-A")
    if git(clone, "diff", "--cached", "--quiet").returncode == 0:
        return "current", f"already at {before}" + "".join(f"; {n}" for n in notes)
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
    (clone.parent / f"{clone.name}.pr.md").write_text("\n".join(body) + "\n", encoding="utf-8")
    note = "".join(f"; {n}" for n in notes)
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
