#!/usr/bin/env python3
"""Report which contract invariants the repository actually enforces.

Twenty-three contracts declare fifty-plus numbered invariants -- OS-3, AT-11,
SC-8, D4 -- and a test suite of a hundred and forty. Nothing connected the two,
so the honest answer to "is OS-3 enforced?" was that nobody could say. That gap
grows silently: each wave adds contracts faster than checks, and a declared
invariant reads like a guarantee.

A test claims an invariant by naming it in a docstring or comment:

    def test_the_installer_registers_no_scheme(self) -> None:
        \"\"\"Enforces: OS-3.\"\"\"

The claim is not verified here -- no tool can confirm a test really establishes
a prose rule. What is verified is that coverage does not silently shrink:
`config/invariant_coverage.txt` records what is claimed today, and an invariant
disappearing from it fails the build. Ratcheting up is free; ratcheting down is
a decision someone has to make on purpose.
"""

from __future__ import annotations

from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
BASELINE = ROOT / "config/invariant_coverage.txt"

# `OS-3`, `AT-11`, `SC-8`, `OT-2`, `R1`, `D4`. Two or three capitals and a
# number, or a single capital and a number for the shorter families.
INVARIANT = re.compile(r"\b([A-Z]{1,3}-?\d{1,2})\b")

# Families a contract actually uses. Without this the pattern also matches
# version numbers, Chromium symbols and ordinary prose like "P1".
FAMILIES = ("AT", "OS", "SC", "OT", "OC", "OP", "D", "R", "E", "SP")


def _identifiers(text: str) -> set[str]:
    found = set()
    for candidate in INVARIANT.findall(text):
        family = candidate.split("-")[0] if "-" in candidate else candidate.rstrip("0123456789")
        if family in FAMILIES and any(character.isdigit() for character in candidate):
            found.add(candidate)
    return found


def declared(root: Path = ROOT) -> dict[str, set[str]]:
    """Invariant identifiers each contract declares, keyed by identifier."""

    result: dict[str, set[str]] = {}
    for path in sorted((root / "docs").rglob("*.md")):
        for identifier in _identifiers(path.read_text(encoding="utf-8")):
            result.setdefault(identifier, set()).add(path.name)
    return result


def claimed(root: Path = ROOT) -> dict[str, set[str]]:
    """Invariants a test or tool claims to enforce, keyed by identifier."""

    result: dict[str, set[str]] = {}
    for directory in ("tests", "scripts"):
        for path in sorted((root / directory).rglob("*.py")):
            if path.name == Path(__file__).name:
                continue
            text = path.read_text(encoding="utf-8")
            for match in re.finditer(r"Enforces:\s*([A-Z0-9,\-\s]+)", text):
                for identifier in _identifiers(match.group(1)):
                    result.setdefault(identifier, set()).add(path.name)
    return result


def read_baseline(path: Path = BASELINE) -> set[str]:
    if not path.is_file():
        return set()
    return {
        line.strip()
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.startswith("#")
    }


def check(root: Path = ROOT) -> tuple[list[str], list[str]]:
    """Returns (report lines, failures)."""

    all_declared = declared(root)
    all_claimed = claimed(root)
    covered = set(all_claimed) & set(all_declared)
    baseline = read_baseline(root / "config/invariant_coverage.txt")

    report = [
        f"Declared invariants: {len(all_declared)}",
        f"Claimed by a test or tool: {len(covered)}",
    ]

    failures = []

    # Claiming an invariant no contract declares means the identifier is wrong,
    # or the contract that declared it was edited without the test.
    orphaned = sorted(set(all_claimed) - set(all_declared))
    for identifier in orphaned:
        failures.append(
            f"{identifier} is claimed by {', '.join(sorted(all_claimed[identifier]))} "
            "but no contract declares it"
        )

    lost = sorted(baseline - covered)
    for identifier in lost:
        failures.append(
            f"{identifier} was enforced and no longer is; "
            "restore the check or remove it from config/invariant_coverage.txt on purpose"
        )

    gained = sorted(covered - baseline)
    if gained:
        report.append(f"Newly enforced, add to the baseline: {', '.join(gained)}")

    return report, failures


def main() -> int:
    report, failures = check()
    print("\n".join(report))
    if failures:
        print("\n".join(failures), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
