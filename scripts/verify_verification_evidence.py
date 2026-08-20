#!/usr/bin/env python3
"""Hold `docs/RUNTIME_VERIFICATION.md` and the module manifests to each other.

That document defines how a module's `verification` fields advance from
`pending` to `passed`, and states the rule the whole scheme rests on:

    A verification state may only be changed by someone who ran the step and
    recorded the result. `passed` with no recorded evidence is worse than
    `pending`, because `pending` is true.

**This guard passes vacuously today, and that is the point.** Every manifest
reads `pending` for all three fields, no evidence record exists, and rule 5
below therefore has nothing to judge. A guard written after the first false
`passed` would be a fix; written before it, it is a ratchet -- the check is in
place on the commit that makes the first claim, rather than being written by
whoever has just discovered that the claim was wrong.

The vacuity is also not total, which is worth being precise about, because
"passes vacuously" is the kind of sentence that gets a check deleted. Rules 1
to 4 and 6 have live subjects right now: twelve gates, sixteen references and
two manifests are read on every run. Only the evidence rule waits.

  1. gates        every gate the document defines is numbered once and
                  contiguously, and the namespace section 4 declares for its
                  evidence records is the namespace the tables actually define
  2. references   every invariant, ADR and patch a gate cites resolves --
                  contract identifiers through `scripts/trace_invariants.py`,
                  ADRs to `docs/decisions/`, patches to `downstream/patches/`
  3. paths        every repository path the document names in backticks exists
  4. records      an evidence record names a defined gate, carries one of the
                  three results, and a PASS identifies the build it came from
  5. evidence     a manifest field reading `passed` has a PASS record for every
                  gate in the section that owns that field
  6. agreement    section 4's claim about `scripts/validate_first_party_modules.py`
                  is true, confirmed by exercising that validator rather than by
                  restating its rule here
  7. run sheet    `docs/RETURN_RUN_SHEET.md`, which orders the manual gates for
                  whoever sits down to run them, names only gates this document
                  defines, and names every gate this document has no PASS for

Rule 7 is what keeps the run sheet from becoming the second copy it would
otherwise be. That sheet holds order, prerequisites and stop rules and no
expectations at all, so the only way it can lie is by going stale: a gate added
here and never scheduled, a gate recorded PASS and still on the list, a label
mistyped. All three are decidable from this document, so all three are checked
rather than trusted.

Rule 6 deserves its own note. The rule it describes -- `runtime_verified`
requires `native_build` and `runtime` -- is already enforced, and duplicating it
here would mean two checks that must be changed together and one that will not
be. What is *not* enforced anywhere is that the sentence in section 4 saying so
remains true. If that rule were dropped from the validator, this document's
safety argument would quietly become false while every check still passed. So
the validator is called, not copied.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
DOCUMENT = "docs/RUNTIME_VERIFICATION.md"
RUN_SHEET = "docs/RETURN_RUN_SHEET.md"
MODULES = "first_party/modules"

sys.path.insert(0, str(Path(__file__).resolve().parent))
import trace_invariants as tracer  # noqa: E402
import validate_first_party_modules as modules  # noqa: E402
import verify_pinned_upstream as upstream  # noqa: E402

# `## 2. Manual -- the runtime gate`. The number is what section 6 of the
# document refers to its own sections by, so it is what failures name too.
SECTION = re.compile(r"^##\s+(\d+)\.\s*(.*)$")

# A gate label: a letter series and an ordinal, optionally hyphenated, in the
# first column of a table whose first header cell is `#`. Deliberately local to
# this document -- these are not contract invariant identifiers and must not be
# resolved as if they were. See the note on the R collision below.
#
# The hyphen is not cosmetic. The gates were renamed from a bare `R`/`V` pair to
# `RV`/`RVV` because the bare series collided with another contract's, and this
# pattern matched neither of the new labels -- so the guard found zero gates and
# still passed. Both halves are fixed: the label shape accepts the repository's
# hyphenated convention, and an empty gate set is now a failure.
GATE = re.compile(r"^([A-Z]+)-?(\d+)$")

# A gate label as prose spells it. Deliberately looser than `GATE`, which
# anchors to a whole table cell: the run sheet names gates inside sentences and
# inside comma-separated table cells. The hyphen is optional for the same reason
# it is in `GATE` -- the series spelling belongs to the document, not to this
# guard. Labels whose series this document does not define are dropped rather
# than reported, because `SEC-1` in a stop rule is a contract identifier and not
# a mistyped gate, and `H264` is not a label at all.
PROSE_GATE = re.compile(r"\b([A-Z]+-?\d+)\b")

# `ADR 0004`, `patch 0002`. Both are four-digit series with a file per number.
ADR = re.compile(r"\bADR\s+(\d{4})\b")
PATCH = re.compile(r"\bpatch\s+(\d{4})\b")

# A backticked repository path. `chrome://version` and `sunshine://anything` are
# URLs the gates tell a person to type, not files, and the `://` is what tells
# them apart from `docs/decisions/0004-media-codecs.md`.
BACKTICKED = re.compile(r"`([^`]+)`")

# One `key value` line of an evidence record, in the shape section 4 gives.
RECORD_LINE = re.compile(r"^(gate|result|build|observed)\s+(.*?)\s*$")
RESULTS = ("PASS", "FAIL", "NOT RUN")

# The three fields a manifest carries, and the states they may hold, both taken
# from the validator that owns the schema rather than restated. A state added
# there is one this guard sees on the same commit.
FIELDS = ("native_build", "runtime", "visual")
PASSED = "passed"


@dataclass(frozen=True)
class Gate:
    label: str
    section: str
    letter: str
    number: int
    cells: tuple[str, ...]


@dataclass(frozen=True)
class Record:
    """One observation of one gate, as section 4 says to write it down."""

    gate: str
    result: str
    build: str
    line: int


@dataclass
class Section:
    number: str
    heading: str
    lines: list[str]
    start: int

    @property
    def text(self) -> str:
        # The heading is part of the section for every purpose here. Section 3
        # is headed "Visual" and never uses the word again, so a section text
        # that dropped its own title would leave the `visual` field ownerless
        # and rule 5 silently checking nothing.
        return "\n".join([self.heading, *self.lines])


def parse_sections(text: str) -> list[Section]:
    """The numbered sections, in order. The preamble is deliberately dropped.

    It shows a manifest snippet with all three field names in it, and reading
    that as the section which owns those fields would attach every gate to the
    wrong place.
    """

    sections: list[Section] = []
    for number, line in enumerate(text.splitlines(), start=1):
        heading = SECTION.match(line)
        if heading:
            sections.append(Section(heading.group(1), heading.group(2), [], number))
        elif sections:
            sections[-1].lines.append(line)
    return sections


def _rows(text: str) -> list[list[str]]:
    """Markdown table rows, header and separator included."""

    return [
        [cell.strip() for cell in line.strip("|").split("|")]
        for line in text.splitlines()
        if line.strip().startswith("|")
    ]


def gates(section: Section) -> list[Gate]:
    """The gates one section defines.

    A gate table is one whose first column is headed `#`. Section 1 has a table
    and no such column, so it defines no gates -- which is a fact about the
    document rather than a quirk of this parser, and rule 5 reports what it
    costs.
    """

    rows = _rows(section.text)
    if not rows or rows[0][0] != "#":
        return []
    found: list[Gate] = []
    for cells in rows[1:]:
        match = GATE.match(cells[0])
        if match:
            found.append(
                Gate(cells[0], section.number, match.group(1), int(match.group(2)), tuple(cells))
            )
    return found


def evidence_records(text: str) -> tuple[list[Record], list[tuple[int, dict[str, str]]]]:
    """(records, blocks that look like records but name no single gate).

    Records live in fenced blocks. The one in section 4 is the *shape* rather
    than an instance, and it is separated out by what it says rather than by
    where it sits: its `gate` line reads `R1..R9, V1..V3` and its `result` line
    lists all three verdicts, so it names no single gate and no single result.
    A record is about one gate; a line offering a range or a list is the
    template.

    Blocks with a `gate` line that names one token which is not a defined gate
    are returned as records anyway, so the caller can reject them. Dropping
    them would repeat the mistake this repository has made three times now: an
    unreadable claim that is silently absent rather than reported.
    """

    records: list[Record] = []
    templates: list[tuple[int, dict[str, str]]] = []
    fenced = False
    block: dict[str, str] = {}
    start = 0
    for number, raw in enumerate(text.splitlines(), start=1):
        if raw.strip().startswith("```"):
            if fenced and {"gate", "result"} <= set(block):
                gate = block["gate"]
                if len(gate.split()) == 1 and "," not in gate and ".." not in gate:
                    records.append(
                        Record(gate, block.get("result", ""), block.get("build", ""), start)
                    )
                else:
                    templates.append((start, dict(block)))
            fenced = not fenced
            block = {}
            start = number
            continue
        if fenced:
            line = RECORD_LINE.match(raw.strip())
            if line:
                block[line.group(1)] = line.group(2)
    return records, templates


def owning_sections(sections: list[Section], field: str) -> list[Section]:
    """The sections that speak for one manifest verification field.

    Ownership is read out of the document: a section owns a field if it names
    that field and carries a table. The table requirement is what keeps section
    4, which mentions two of the fields while specifying the record shape, and
    section 5, which mentions one while explaining why nothing has advanced,
    from being read as definitions of a gate set.
    """

    word = re.compile(rf"\b{re.escape(field)}\b", re.IGNORECASE)
    return [
        section
        for section in sections
        if word.search(section.text) and _rows(section.text)
    ]


def manifests(root: Path) -> list[tuple[str, dict]]:
    base = root / MODULES
    if not base.is_dir():
        return []
    found = []
    for path in sorted(base.glob("*/module.json")):
        try:
            found.append((path.relative_to(root).as_posix(), json.loads(path.read_text("utf-8"))))
        except (OSError, json.JSONDecodeError):
            # A malformed manifest is validate_first_party_modules.py's failure
            # to report, and two guards failing for one cause tells a reader
            # nothing extra.
            continue
    return found


def check(root: Path = ROOT) -> tuple[list[str], list[str]]:
    """Returns (report lines, failures)."""

    failures: list[str] = []
    path = root / DOCUMENT
    if not path.is_file():
        return [], [f"{DOCUMENT} does not exist"]

    text = path.read_text(encoding="utf-8")
    sections = parse_sections(text)
    all_gates = [gate for section in sections for gate in gates(section)]
    by_label = {gate.label: gate for gate in all_gates}

    # --- 1. the gate namespace -------------------------------------------
    #
    # Emptiness first. A guard that reports "0 gates" and exits 0 has stopped
    # checking the document and started agreeing with whatever it can no longer
    # read -- which is exactly what happened when the labels were renamed and
    # this pattern stopped matching them.
    if not all_gates:
        failures.append(
            f"{DOCUMENT}: no gate was found. Either the document defines none, "
            "or the label shape changed and this guard can no longer read it; "
            "both are failures, and neither is a pass."
        )
    seen: dict[str, list[Gate]] = {}
    for gate in all_gates:
        seen.setdefault(gate.label, []).append(gate)
    for label, found in sorted(seen.items()):
        if len(found) > 1:
            failures.append(
                f"{DOCUMENT}: gate {label} is defined {len(found)} times "
                f"(sections {', '.join(sorted({g.section for g in found}))})"
            )
    for letter in sorted({gate.letter for gate in all_gates}):
        numbers = sorted(gate.number for gate in all_gates if gate.letter == letter)
        expected = list(range(1, len(numbers) + 1))
        if numbers != expected:
            failures.append(
                f"{DOCUMENT}: {letter} gates are numbered {numbers}, "
                f"which is not {expected[0]}..{expected[-1]} without a gap"
            )

    # The evidence template declares the namespace its records may name. If the
    # tables and the template disagree, one of them has been edited alone, and
    # a record written against the template would cite a gate nothing defines.
    records, templates = evidence_records(text)
    if not templates:
        # Without it there is no declared namespace to compare the tables
        # against, and this rule would pass by having nothing to do -- the
        # quiet kind of green that the rest of this file exists to refuse.
        failures.append(
            f"{DOCUMENT}: no evidence record template found; section 4 is what "
            "declares the shape and the gate namespace a record may name"
        )
    for line, block in templates:
        declared: set[str] = set()
        for piece in block["gate"].split(","):
            piece = piece.strip()
            bounds = piece.split("..")
            first, last = GATE.match(bounds[0]), GATE.match(bounds[-1])
            if first and last and first.group(1) == last.group(1):
                # Rebuilt with the separator the template actually used, not a
                # canonical one. Reconstructing `RV-1` as `RV1` made every gate
                # read as declared-and-undefined *and* defined-and-undeclared at
                # once -- a set difference reported in both directions, which is
                # the signature of a normalisation the comparison did not agree
                # with rather than of a real disagreement.
                separator = "-" if bounds[0].startswith(f"{first.group(1)}-") else ""
                declared.update(
                    f"{first.group(1)}{separator}{number}"
                    for number in range(int(first.group(2)), int(last.group(2)) + 1)
                )
        if declared and declared != set(by_label):
            missing = sorted(declared - set(by_label))
            extra = sorted(set(by_label) - declared)
            failures.append(
                f"{DOCUMENT}:{line}: the evidence template declares gates "
                f"{block['gate']!r}, but the tables define a different set"
                + (f"; declared and undefined: {', '.join(missing)}" if missing else "")
                + (f"; defined and undeclared: {', '.join(extra)}" if extra else "")
            )

    # --- 2 and 3. what the gates cite ------------------------------------
    declared_identifiers = tracer.declared(root)
    references = 0
    for gate in all_gates:
        # The last column of a gate table is what the gate is evidence *for*.
        # Only that column is scanned for contract identifiers: the gate labels
        # themselves are R1..R9, and `DESIGN_SYSTEM_CONTRACT` already uses R1..R14
        # for something else, so reading a whole row would resolve this
        # document's gate numbers against another document's runtime checks.
        cell = gate.cells[-1] if len(gate.cells) > 3 else ""
        for identifier in sorted(tracer._identifiers(cell)):
            references += 1
            # Declared by some *other* document. `tracer.declared` counts an
            # identifier as declared wherever it appears, so without this the
            # rule would be self-satisfying: a gate citing a misspelled SEC-99
            # would be the very occurrence that made SEC-99 declared, and the
            # citation would resolve against itself.
            elsewhere = declared_identifiers.get(identifier, set()) - {Path(DOCUMENT).name}
            if not elsewhere:
                failures.append(
                    f"{DOCUMENT}: gate {gate.label} cites {identifier}, "
                    "which no other document in docs/ declares"
                )

    for number, line in enumerate(text.splitlines(), start=1):
        for adr in ADR.findall(line):
            references += 1
            if not list((root / "docs/decisions").glob(f"{adr}-*.md")):
                failures.append(f"{DOCUMENT}:{number}: cites ADR {adr}, which does not exist")
        for patch in PATCH.findall(line):
            references += 1
            if not list((root / "downstream/patches").glob(f"{patch}-*.patch")):
                failures.append(f"{DOCUMENT}:{number}: cites patch {patch}, which does not exist")
        for token in BACKTICKED.findall(line):
            if "://" in token or "/" not in token:
                continue  # a URL a gate tells a person to type, or not a path
            if token.split("/", 1)[0] not in upstream.OWN_PREFIXES:
                # A Chromium path, not one of ours. It is not skipped, it is
                # checked elsewhere: `scripts/verify_pinned_upstream.py` reads
                # every path cited anywhere in `docs/` and asks whether it
                # exists at the pinned revision, which is the only question
                # worth asking about an upstream file and the one this guard
                # cannot answer offline. Requiring it in the working tree would
                # mean a gate could never name the upstream source it is about
                # -- and RV-10's cause was found in `chrome/app/chrome_exe.rc`,
                # which is exactly such a name.
                continue
            references += 1
            if not (root / token).exists():
                failures.append(f"{DOCUMENT}:{number}: names `{token}`, which does not exist")

    # --- 4. the records themselves ---------------------------------------
    for record in records:
        if record.gate not in by_label:
            failures.append(
                f"{DOCUMENT}:{record.line}: evidence names gate {record.gate}, "
                "which this document does not define"
            )
        if record.result not in RESULTS:
            failures.append(
                f"{DOCUMENT}:{record.line}: evidence for {record.gate} results "
                f"{record.result!r}, which is not one of {', '.join(RESULTS)}"
            )
        # "the run to be identifiable -- workflow run number and commit".
        # A PASS nobody can trace back to a run is the shape of claim this
        # whole document exists to refuse.
        if record.result == "PASS" and not record.build:
            failures.append(
                f"{DOCUMENT}:{record.line}: evidence for {record.gate} is PASS "
                "with no build recorded"
            )

    passing: dict[str, set[str]] = {}
    for record in records:
        passing.setdefault(record.gate, set()).add(record.result)
    for gate, results in sorted(passing.items()):
        if len(results) > 1:
            failures.append(
                f"{DOCUMENT}: gate {gate} has contradictory evidence: {', '.join(sorted(results))}"
            )

    # --- 5. a manifest may not claim more than the record supports --------
    found_manifests = manifests(root)
    for label, manifest in found_manifests:
        verification = manifest.get("verification")
        if not isinstance(verification, dict):
            continue  # the validator's failure to report, not this one's
        for field in FIELDS:
            if verification.get(field) != PASSED:
                continue
            owners = [
                section for section in owning_sections(sections, field) if gates(section)
            ]
            required = sorted(
                (gate.label for section in owners for gate in gates(section)),
                key=lambda name: (by_label[name].letter, by_label[name].number),
            )
            if not required:
                failures.append(
                    f"{label}: {field} is {PASSED}, but no section of {DOCUMENT} "
                    "defines a numbered gate for it, so no evidence record can name "
                    "what was run"
                )
                continue
            for gate in required:
                if "PASS" not in passing.get(gate, set()):
                    failures.append(
                        f"{label}: {field} is {PASSED}, but {DOCUMENT} records no "
                        f"PASS for gate {gate}"
                    )

    # --- 6. the document's claim about the other validator ----------------
    failures.extend(_agreement(found_manifests))

    # --- 7. the run sheet schedules exactly what is still owed ------------
    sheet = root / RUN_SHEET
    scheduled: set[str] = set()
    if sheet.is_file():
        letters = {gate.letter for gate in all_gates}
        for label in PROSE_GATE.findall(sheet.read_text(encoding="utf-8")):
            # The series comes from `GATE`, which is the one place the label
            # shape is decided. Splitting on the hyphen instead would read the
            # unhyphenated form `R1` as a series called "R1" and drop it.
            series = GATE.match(label)
            if not series or series.group(1) not in letters:
                continue
            if label not in by_label:
                failures.append(
                    f"{RUN_SHEET}: schedules gate {label}, which {DOCUMENT} "
                    "does not define"
                )
                continue
            scheduled.add(label)
        owed = sorted(
            (label for label in by_label if "PASS" not in passing.get(label, set())),
            key=lambda name: (by_label[name].letter, by_label[name].number),
        )
        unscheduled = [label for label in owed if label not in scheduled]
        if unscheduled:
            failures.append(
                f"{RUN_SHEET}: {DOCUMENT} has no PASS for "
                f"{', '.join(unscheduled)}, and the sheet does not say when to "
                "run them"
            )

    letters = sorted({gate.letter for gate in all_gates})
    report = [
        f"Checked {len(all_gates)} gates ({', '.join(letters) or 'none'}), "
        f"{references} references and {len(found_manifests)} manifests "
        f"against {DOCUMENT}; {len(records)} evidence record(s) found."
    ]
    if sheet.is_file():
        report.append(f"{RUN_SHEET} schedules {len(scheduled)} of them.")
    return report, failures


def _agreement(found_manifests: list[tuple[str, dict]]) -> list[str]:
    """Confirm section 4's sentence about `validate_first_party_modules.py`.

    Exercised rather than read: a real manifest is taken, `status` is set to
    `runtime_verified` while its verification fields stay `pending`, and the
    validator is expected to refuse it. Grepping that script for the rule would
    pass on a commented-out copy of it.
    """

    if not found_manifests:
        return []
    label, manifest = found_manifests[0]
    probe = json.loads(json.dumps(manifest))  # a copy; the original is an input
    probe["status"] = "runtime_verified"
    probe["verification"] = {field: "pending" for field in FIELDS}
    try:
        modules.validate_manifest(probe, label)
    except modules.ModuleValidationError:
        return []
    except Exception as error:  # noqa: BLE001 - a probe that cannot run proves nothing
        return [
            f"{DOCUMENT}: could not confirm the section 4 claim about "
            f"scripts/validate_first_party_modules.py: {error}"
        ]
    return [
        f"{DOCUMENT}: section 4 says scripts/validate_first_party_modules.py refuses "
        "status: runtime_verified unless native_build and runtime are passed; it does not"
    ]


def main() -> int:
    report, failures = check()
    print("\n".join(report))
    if failures:
        print("\n".join(failures), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
