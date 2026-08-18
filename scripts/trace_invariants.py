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

# `OS-3`, `AT-11`, `SC-8`, `OT-2`, `D4`, the compound form `PO-A1` where the
# family is followed by a lettered series, and the sub-lettered form `PB-2a`
# where one budget is split into parts that are each their own rule.
#
# Every widening here has been the same bug arriving again, and the shape of it
# is worth stating once: **an unparsed token is absent, not rejected.** Nothing
# errors, no count moves, and both ends of the disagreement -- the contract that
# declares the identifier and the check that claims it -- read as consistent,
# because neither can see the other.
#
#   `{1,4}` and not `{1,3}`: SECA-n is a four-letter family and matched nothing
#   at all. The claims in verify_web_asset_security.py and
#   verify_first_party_surfaces.py were simply not seen.
#
#   `[a-z]?`: PERFORMANCE_BUDGET declares PB-2a, PB-2b and PB-2c. Ending the
#   pattern at `\d{1,2}` did not truncate them to PB-2 -- the trailing `\b`
#   fails against the letter, so the whole token vanished, which is why nothing
#   downstream could notice a wrong answer either.
#
# The suffix is lowercase deliberately, and that is the whole of what separates
# an identifier from an acronym: `E2E` would parse as family E with an uppercase
# suffix, and E is a declared family. Every identifier-shaped token in docs/ was
# surveyed before this was widened, and the survey is what the bounds are drawn
# from: one sub-lettered shape in use (PB-2a/b/c, 15 occurrences), one
# uppercase-suffixed one (E2E, twice), and nothing numbered past 99. The last
# two widenings were designed from imagination and each looked general enough.
# tests/test_invariant_tracing.py re-runs the survey against the documents, so
# the bounds are asserted rather than trusted here.
INVARIANT = re.compile(r"\b([A-Z]{1,4}-?[A-Z]?\d{1,2}[a-z]?)\b")

# Deliberately wider than INVARIANT, in the two directions identifiers have
# actually grown: more digits, and a suffix after them. Nothing is parsed with
# this -- it exists so that a token of a *declared family* which it matches and
# INVARIANT does not can be reported as lost rather than dropped in silence.
CANDIDATE = re.compile(r"\b[A-Z]{1,6}-?[A-Z]?\d{1,4}[a-z]{0,3}\b")

# The leading run of capitals. Read off the front, because the front is the
# part that has stayed still: both widenings above were changes to the tail of
# an identifier, and a family derived by stripping the tail would have had to
# change with each of them.
FAMILY = re.compile(r"^[A-Z]+")

# Families a contract actually uses. Without this the pattern also matches
# version numbers, Chromium symbols and ordinary prose like "P1".
#
# Bare "P" is still absent, and now for a narrower reason than before. Every
# contract uses P0/P1/P2 for decision priority -- 23 occurrences in
# PERFORMANCE_BUDGET alone -- so admitting "P" would turn a priority label into
# an invariant everywhere. The budgets that used to need it were renamed to
# PB-1..PB-6, so they are counted under their own family and the priority
# labels stay prose. PERFORMANCE_BUDGET section 4 states the resulting rule: a
# bare P number in that document is always a priority.
#
# The acceptance families carry a trailing "A" (ATA, OMA, CPA, ...) so that a
# document's acceptance criteria cannot be confused with the invariant family
# declared in the same document -- SP-n invariants and SPA-n criteria coexist.
FAMILIES = (
    "AT", "OS", "SC", "OT", "OC", "OP", "PO", "S", "D", "R", "E", "SP", "XM",
    # Acceptance criteria and budgets, one prefix per owning document.
    "ATA", "OMA", "TLA", "CPA", "SPA", "SCA", "GA", "BUA", "SRA", "DSA", "BH",
    "TA", "PB",
    # The security architecture: SEC-n invariants, SECA-n acceptance criteria.
    "SEC", "SECA",
    # Runtime verification gates: RV-n needs the browser open, RVV-n needs a
    # person looking. Both prefixes exist because the first draft numbered them
    # R1-R9 and V1-V3 -- colliding with DESIGN_SYSTEM_CONTRACT's own R series in
    # one direction, and unparseable in the other.
    "RV", "RVV",
    # The document surface: DOC-n invariants, DOCA-n acceptance criteria.
    "DOC", "DOCA",
)


# This tool and its own tests are excluded from the claim scan. The tests write
# fixture documents containing `Enforces:` lines to prove the check works, and
# counting those as real claims made the tool report invariants that no file in
# the repository actually enforces.
EXCLUDED = {Path(__file__).name, "test_invariant_tracing.py"}

# The text a check offers as its claim: the rest of the line after the marker.
# Lowercase is admitted so that a sub-lettered identifier survives being read at
# all -- without it `Enforces: PB-2a` is captured as `PB-2` and the claim is
# truncated before anything is in a position to reject it. Prose swept up
# alongside is harmless: whether a word is an identifier is decided by INVARIANT
# and FAMILIES, never by this character class.
CLAIM = re.compile(r"Enforces:[ \t]*([A-Za-z0-9,\- \t]+)")


def _family(candidate: str) -> str:
    """The family a token belongs to: its leading run of capitals."""

    match = FAMILY.match(candidate)
    return match.group(0) if match else ""


def _identifiers(text: str) -> set[str]:
    found = set()
    for candidate in INVARIANT.findall(text):
        if _family(candidate) in FAMILIES and any(character.isdigit() for character in candidate):
            found.add(candidate)
    return found


def unparsed_claims(root: Path = ROOT) -> list[tuple[str, str]]:
    """(file, token) for every claim this tool can see but cannot read.

    The gap the pattern widenings kept falling into, closed from the other side.
    A check writing `Enforces: PB-2a` registered nothing at all, and no count
    moved, so the only way to find out was for a person to wonder. Here the
    token is compared against a pattern wider than the parsing one, and a
    mismatch is reported instead of dropped.

    Restricted to families a contract declares. `MV3`, `AV1` and `E2E` are the
    shapes that would otherwise be swept up out of ordinary prose, and none of
    them is a claim about anything.
    """

    found: list[tuple[str, str]] = []
    for directory in ("tests", "scripts"):
        for path in sorted((root / directory).rglob("*.py")):
            if path.name in EXCLUDED:
                continue
            for match in CLAIM.finditer(path.read_text(encoding="utf-8")):
                parsed = _identifiers(match.group(1))
                for token in CANDIDATE.findall(match.group(1)):
                    if _family(token) in FAMILIES and token not in parsed:
                        found.append((path.name, token))
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
            if path.name in EXCLUDED:
                continue
            text = path.read_text(encoding="utf-8")
            for match in CLAIM.finditer(text):
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

    # A claim this tool cannot read is worse than a wrong one: a wrong claim is
    # reported below, an unreadable one used to count as no claim at all. It is
    # listed first because every other number on this report is computed from
    # tokens that parsed, and an unparsed one makes all of them quietly short.
    for name, token in unparsed_claims(root):
        failures.append(
            f"{name} claims {token}, which INVARIANT cannot parse; {_family(token)} is a "
            "declared family, so the identifier is being lost rather than counted "
            "-- widen the pattern or correct the claim"
        )

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
