#!/usr/bin/env python3
"""Hold `docs/ACCEPTANCE_SUITES.md` to the claims it makes about itself.

The index maps every stage acceptance item to the contract criteria that answer
it, and stamps each row with a verdict. One hundred and seventeen identifiers,
seventeen document references, and not one of them checked by anything. A row
that reads

    | A1.6 | bookmark / history persistence | `BOOKMARKS_HISTORY_CONTRACT`
      BH-A1-BH-A7 ... | B | **Covered** |

is a promise that a named document declares those criteria. When a contract is
renamed, renumbered or deleted, the row does not change and nothing complains.
That failure mode is worse than an uncovered row: **Covered** stops the next
reader looking, so a stale citation buys silence rather than coverage.

What is checkable is not whether a criterion really establishes an acceptance
line -- no tool can read prose for that -- but whether the *citation resolves*.
Every rule below is of that kind, and every one is derived from the document's
own structure rather than from a list kept here:

  1. artifacts     every path and document a table row names exists, and a
                   section reference attached to a document resolves to a
                   numbered heading in it
  2. identifiers   every contract identifier a row cites is declared by the
                   document the row names for it
  3. covered       a row whose verdict is **Covered** names at least one
                   artifact that exists
  4. vocabulary    class letters and verdicts come from the sets sections 1.1
                   and 1.2 declare, and the per-stage tally under each table
                   matches the verdicts in it
  5. status        a section 8 row saying "not implemented" is not in fact
                   claimed by a check, and one saying "implemented" is

Rule 5 is the one that reaches outside the document, and it is the reason this
guard imports `trace_invariants` rather than restating its grammar: that module
already knows which identifier families exist and how a check claims one, and a
mirrored copy would drift the first time either changed.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
INDEX = "docs/ACCEPTANCE_SUITES.md"

# Importable both as `python3 scripts/verify_acceptance_claims.py` (where the
# script directory is already on the path) and from a test that has inserted
# `scripts/` itself. The insert is idempotent enough for either.
sys.path.insert(0, str(Path(__file__).resolve().parent))
import trace_invariants as tracer  # noqa: E402

# A backticked token or a bare identifier, matched in one pass so that document
# references and the identifiers that follow them stay in reading order. The
# identifier alternative is `trace_invariants.INVARIANT` without its anchors --
# whether a match is really an identifier is decided by that module, not here.
TOKEN = re.compile(r"`([^`]+)`|([A-Z]{1,4}-?[A-Z]?\d{1,2})")

# A section reference counts as belonging to a document only when it directly
# follows it: "`TAB_LIFECYCLE_CONTRACT` §10.2" is a reference into that
# contract, while "`docs/PERFORMANCE_BUDGET.md` answers §9.2 with deltas" is a
# reference to the handoff. Adjacency is the only signal that separates them,
# so anything further away is left alone rather than guessed at.
SECTION_AFTER = re.compile(r"\s*§(\d+(?:\.\d+)*)")

# `## 13. Acceptance criteria`, `### 9.1 Group S`. Every contract in docs/
# numbers its headings this way, which is what makes a §-reference decidable.
HEADING = re.compile(r"^#{1,6}\s+(\d+(?:\.\d+)*)\.?\s")

# A bare document reference: SCREAMING_SNAKE with at least one underscore. The
# underscore is load-bearing -- it is what keeps `P1` and `PB-1`, which the
# document also writes in backticks, from being read as missing documents.
DOCUMENT_NAME = re.compile(r"[A-Z][A-Z0-9]*(?:_[A-Z0-9]+)+")

# `BH-A1-BH-A7`, `SPA-1...SPA-26`, `S2-S12`. Written with an en dash or an
# ellipsis; an ASCII hyphen is deliberately not a range separator, because it
# is already the separator inside every identifier.
RANGE = re.compile(r"([A-Z]{1,4}-?[A-Z]?)(\d{1,2})\s*[–—…]\s*([A-Z]{1,4}-?[A-Z]?)?(\d{1,2})")

# `**Stage 1: 2 covered, 5 partial, 2 uncovered.**` under each stage table.
TALLY = re.compile(r"^\*\*Stage \d+:\s*(.+?)\.\*\*\s*$")
TALLY_TERM = re.compile(r"(\d+)\s+([a-z]+)")

# Section 8 grades each offline-decidable criterion. Only two gradings exist,
# and an unrecognised one is reported rather than skipped: a rule that quietly
# stops applying when someone rewords a cell is not a rule.
IMPLEMENTED = "implemented"
NOT_IMPLEMENTED = "not implemented"


@dataclass(frozen=True)
class Claim:
    """One resolvable thing a row asserts."""

    kind: str  # "artifact" | "identifier" | "section"
    value: str
    document: str | None  # the document the claim is made against


@dataclass
class Table:
    section: str  # "3.2", "8"
    header: list[str]
    rows: list[list[str]]


def _is_identifier(token: str) -> bool:
    """True when the whole token is an identifier of a family a contract uses.

    Delegated to `trace_invariants` so that the family list has exactly one
    home. Equality rather than truthiness: a token that merely *contains* an
    identifier is prose.
    """

    return tracer._identifiers(token) == {token}


def parse_tables(text: str) -> list[Table]:
    """Every markdown table in the document, tagged with its section number."""

    tables: list[Table] = []
    lines = text.splitlines()
    section = ""
    index = 0
    while index < len(lines):
        heading = HEADING.match(lines[index])
        if heading:
            section = heading.group(1).rstrip(".")
        if lines[index].startswith("|"):
            end = index
            while end < len(lines) and lines[end].startswith("|"):
                end += 1
            # A table is header, separator, body; anything shorter is not one.
            if end - index >= 3:
                header = [cell.strip() for cell in lines[index].strip("|").split("|")]
                rows = [
                    [cell.strip() for cell in line.strip("|").split("|")]
                    for line in lines[index + 2 : end]
                ]
                tables.append(Table(section, header, rows))
            index = end
            continue
        index += 1
    return tables


def expand_ranges(text: str) -> str:
    """Rewrite `TLA-1-TLA-25` as every identifier it stands for.

    A range is a claim about all of its members, not just its endpoints: a row
    citing TLA-1-TLA-25 is wrong if TLA-13 does not exist, and checking only
    the ends would never see it.
    """

    def expand(match: re.Match[str]) -> str:
        prefix, first, second_prefix, last = match.groups()
        if second_prefix and second_prefix != prefix:
            return match.group(0)  # not a range, two unrelated identifiers
        low, high = int(first), int(last)
        if high < low or not _is_identifier(f"{prefix}{low}"):
            return match.group(0)
        return " ".join(f"{prefix}{number}" for number in range(low, high + 1))

    return RANGE.sub(expand, text)


def artifact_target(token: str) -> str | None:
    """The repository path a backticked token names, or None if it names none.

    Two forms occur: a written-out path (`docs/PERFORMANCE_BUDGET.md`,
    `first_party/commands.json`) and a bare contract name that the document
    uses as shorthand for a file in `docs/`.
    """

    if "/" in token:
        return token
    if DOCUMENT_NAME.fullmatch(token):
        return f"docs/{token}.md"
    return None


def claims(cell: str) -> list[Claim]:
    """Every resolvable claim in one table cell, in reading order.

    An identifier belongs to the nearest document named before it in the same
    cell, which is exactly how the document reads: "`SESSION_PROFILE_CONTRACT`
    SRA-9, SRA-11; `BOOKMARKS_HISTORY_CONTRACT` BH-D1-BH-D2" attributes three
    identifiers to the first document and two to the second. A non-document
    artifact -- a script, a JSON registry -- does not take over that role,
    because a criterion is never declared by one.
    """

    text = expand_ranges(cell)
    found: list[Claim] = []
    current: str | None = None
    for match in TOKEN.finditer(text):
        token = match.group(1)
        if token is None:
            token = match.group(2)
            if _is_identifier(token):
                found.append(Claim("identifier", token, current))
            continue
        # Backticked. The document writes some identifiers in backticks too.
        if _is_identifier(token):
            found.append(Claim("identifier", token, current))
            continue
        target = artifact_target(token)
        if target is None:
            continue
        found.append(Claim("artifact", target, None))
        if target.endswith(".md"):
            current = target
            section = SECTION_AFTER.match(text, match.end())
            if section:
                found.append(Claim("section", section.group(1), target))
    return found


def section_numbers(path: Path) -> set[str]:
    return {
        match.group(1).rstrip(".")
        for line in path.read_text(encoding="utf-8").splitlines()
        if (match := HEADING.match(line))
    }


def legend_terms(table: Table) -> list[str]:
    """The bolded first-column values of a two-column legend table.

    Sections 1.1 and 1.2 declare the verdict and class vocabularies this way,
    so the sets are read from the document rather than restated here -- adding
    a fifth verdict to section 1.1 should not need an edit to this file.
    """

    terms = []
    for row in table.rows:
        match = re.fullmatch(r"\*\*(.+?)\*\*", row[0].strip())
        if match:
            terms.append(match.group(1))
    return terms


def row_label(table: Table, index: int, cells: list[str]) -> str:
    """A label that names the row a failure is about, as a reader would."""

    first = re.sub(r"[`~*]", "", cells[0]).strip()
    if table.header[0] == "ID":
        return f"§{table.section} {first}"
    if first == str(index):
        return f"§{table.section} row {index}"
    return f"§{table.section} row {index} ({first})" if first else f"§{table.section} row {index}"


def evidence_column(header: list[str]) -> int:
    """The column holding the criteria a row cites.

    Derived from position rather than from a header name, because the three
    stage tables and the section 3.2 breakdown all spell that header
    differently -- "Established by", "Mechanism established by", "Owning
    criterion" -- while all four place it immediately before the grading.
    """

    anchor = "Class" if "Class" in header else "Verdict"
    return header.index(anchor) - 1


def check(root: Path = ROOT) -> tuple[list[str], list[str]]:
    """Returns (report lines, failures)."""

    failures: list[str] = []
    index_path = root / INDEX
    if not index_path.is_file():
        return [], [f"{INDEX} does not exist"]

    text = index_path.read_text(encoding="utf-8")
    lines = text.splitlines()
    tables = parse_tables(text)

    legends = {
        table.header[0]: legend_terms(table)
        for table in tables
        if len(table.header) == 2 and table.header[1] == "Meaning"
    }
    verdicts = legends.get("Verdict", [])
    classes = legends.get("Class", [])
    if not verdicts or not classes:
        # Without the two legends there is no vocabulary to check against, and
        # a guard that silently checked nothing would be worse than no guard.
        return [], [f"{INDEX}: section 1.1 or 1.2 no longer declares a legend table"]

    declared = tracer.declared(root)
    claimed = tracer.claimed(root)
    headings: dict[str, set[str]] = {}

    rows_checked = 0
    counted = {"artifact": 0, "identifier": 0, "section": 0}

    def resolve(label: str, cell: str) -> list[Claim]:
        """Rules 1 and 2 for one cell, returning what it claimed."""

        found = claims(cell)
        for claim in found:
            counted[claim.kind] += 1
            if claim.kind == "artifact":
                if not (root / claim.value).exists():
                    failures.append(f"{label}: names `{claim.value}`, which does not exist")
            elif claim.kind == "identifier":
                if claim.document is None:
                    failures.append(
                        f"{label}: cites {claim.value} with no document named before it"
                    )
                elif Path(claim.document).name not in declared.get(claim.value, set()):
                    failures.append(
                        f"{label}: cites {claim.value}, which `{claim.document}` does not declare"
                    )
            elif claim.kind == "section":
                document = root / claim.document
                if not document.is_file():
                    continue  # already reported as a missing artifact
                if claim.document not in headings:
                    headings[claim.document] = section_numbers(document)
                if claim.value not in headings[claim.document]:
                    failures.append(
                        f"{label}: cites `{claim.document}` §{claim.value}, "
                        "which is not a section of it"
                    )
        return found

    for table in tables:
        # The registry table: each row promises that a document exists and
        # declares the criteria named beside it.
        if table.header[:2] == ["Document", "Criteria"]:
            for number, cells in enumerate(table.rows, start=1):
                rows_checked += 1
                label = row_label(table, number, cells)
                # Document and criteria are separate columns, joined so the
                # document is the one every identifier is attributed to. The
                # "Identifier scheme" column is prose about prefixes and makes
                # no citable claim, so it is left out.
                resolve(label, f"{cells[0]} {cells[1]}")
            continue

        # Section 8: criterion, why it is offline-decidable, and whether a
        # check exists for it.
        if table.header[0] == "Criterion" and "Status" in table.header:
            status_column = table.header.index("Status")
            for number, cells in enumerate(table.rows, start=1):
                rows_checked += 1
                label = row_label(table, number, cells)
                found = resolve(label, cells[0])
                status = re.sub(r"[`*]", "", cells[status_column]).strip().lower()
                cited = [claim.value for claim in found if claim.kind == "identifier"]
                # Reported once per row rather than once per identifier: a row
                # citing S2-S12 is one wrong grading, not eleven.
                if status.startswith(NOT_IMPLEMENTED):
                    enforced = [identifier for identifier in cited if identifier in claimed]
                    if enforced:
                        by = sorted({name for one in enforced for name in claimed[one]})
                        failures.append(
                            f'{label}: status says "not implemented" but '
                            f"{', '.join(enforced)} {'is' if len(enforced) == 1 else 'are'} "
                            f"claimed by {', '.join(by)}"
                        )
                elif status.startswith(IMPLEMENTED):
                    unenforced = [identifier for identifier in cited if identifier not in claimed]
                    if unenforced:
                        failures.append(
                            f'{label}: status says "implemented" but no check claims '
                            f"{', '.join(unenforced)}"
                        )
                else:
                    failures.append(
                        f"{label}: status {cells[status_column]!r} is neither "
                        f'"{IMPLEMENTED}" nor "{NOT_IMPLEMENTED}"'
                    )
            continue

        # The open-questions table cites documents and criteria in prose, and
        # a settled question pointing at a document that does not exist is the
        # same defect as a Covered row doing so.
        if table.header[:2] == ["Priority", "Question"]:
            for number, cells in enumerate(table.rows, start=1):
                rows_checked += 1
                resolve(row_label(table, number, cells), cells[1])
            continue

        # The three stage tables and the section 3.2 breakdown.
        if "Verdict" in table.header and len(table.header) > 2:
            column = evidence_column(table.header)
            verdict_column = table.header.index("Verdict")
            class_column = table.header.index("Class") if "Class" in table.header else None
            for number, cells in enumerate(table.rows, start=1):
                rows_checked += 1
                label = row_label(table, number, cells)
                found = resolve(label, cells[column])

                stated = re.findall(r"\*\*([A-Za-z]+)\*\*", cells[verdict_column])
                for verdict in stated:
                    if verdict not in verdicts:
                        failures.append(
                            f"{label}: verdict {verdict!r} is not one section 1.1 declares "
                            f"({', '.join(verdicts)})"
                        )
                # Rule 3. A Covered row that names nothing, or names only a
                # document that is gone, is the failure this guard exists for.
                if "Covered" in stated and not any(
                    claim.kind == "artifact" and (root / claim.value).exists()
                    for claim in found
                ):
                    failures.append(
                        f"{label}: verdict is Covered but the row names no artifact that exists"
                    )

                if class_column is not None:
                    for letter in cells[class_column].split("+"):
                        letter = letter.strip()
                        if letter and letter not in classes:
                            failures.append(
                                f"{label}: class {letter!r} is not one section 1.2 declares "
                                f"({', '.join(classes)})"
                            )

    # Rule 4, the tallies. Each stage table is followed by a bolded count of
    # its own verdicts; a row whose verdict is edited without the tally leaves
    # the summary reading better than the table.
    stage_tables = [
        table
        for table in tables
        if "Verdict" in table.header and len(table.header) > 2 and table.header[0] == "ID"
    ]
    tallies = [line for line in lines if TALLY.match(line)]
    if len(tallies) != len(stage_tables):
        failures.append(
            f"{INDEX}: {len(stage_tables)} stage tables but {len(tallies)} tally lines"
        )
    for table, line in zip(stage_tables, tallies):
        verdict_column = table.header.index("Verdict")
        actual: dict[str, int] = {}
        for cells in table.rows:
            for verdict in re.findall(r"\*\*([A-Za-z]+)\*\*", cells[verdict_column]):
                actual[verdict.lower()] = actual.get(verdict.lower(), 0) + 1
        # "0 covered" is a real and useful thing for a tally to say, and it has
        # no row to correspond to, so a stated zero is dropped rather than
        # counted as a disagreement with an absent verdict.
        stated = {
            term: int(count)
            for count, term in TALLY_TERM.findall(TALLY.match(line).group(1))
            if int(count)
        }
        if stated != actual:
            failures.append(
                f"§{table.section} tally {line.strip('*')!r} does not match the table "
                f"({', '.join(f'{count} {term}' for term, count in sorted(actual.items()))})"
            )

    total = sum(counted.values())
    report = [
        f"Checked {rows_checked} rows of {INDEX} and {total} claims: "
        f"{counted['artifact']} artifact references, "
        f"{counted['identifier']} contract identifiers (ranges expanded), "
        f"{counted['section']} section references."
    ]
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
