#!/usr/bin/env python3
"""Hold `docs/OPEN_DECISIONS.md` to the promise it makes about itself.

The index exists because the open questions had spread across fifteen
documents, several of them the same question asked more than once, and several
already answered without the asking document being updated. Its closing section
states the rule it lives by: "An index that only grows becomes a second
backlog, and one that disagrees with its sources is worse than none -- which is
the failure it was built to end."

Nothing checked that. This does, and only for the disagreements that can be
settled without reading a question for meaning:

  * a row names a document that is not on disk
  * a row cites an ADR that was never written
  * one question is listed as open and as settled at the same time, or twice in
    the same section -- the duplication the index was created to remove
  * a settled row names nothing that settled it
  * the index has quietly emptied, or has been restructured out from under the
    four rules above, so that they pass by finding nothing to check

Content is deliberately out of scope. The index "records status and location,
not content" by its own statement -- the owning contract states each question
in full -- so this guard reads a question only for identity, never for meaning.
Every comparison below is exact after normalisation. Near-match detection was
considered and rejected: the first false positive on two genuinely different
questions would end with the guard deleted, which is worse than the rule not
existing.

This guard claims no invariant identifier; no contract declares one for the
index itself.
"""

from __future__ import annotations

from pathlib import Path
import re
import sys
from typing import NamedTuple

ROOT = Path(__file__).resolve().parents[1]

INDEX = "docs/OPEN_DECISIONS.md"

HEADING = re.compile(r"^##\s+(.*\S)\s*$")
BULLET = re.compile(r"^-\s+(.*\S)\s*$")

# `| --- | --- | --- |` and its variants. Matched only to skip it; it has no
# letters, so it cannot be confused with a row.
TABLE_RULE = re.compile(r"^\|[\s:|-]+\|$")

# The sections that carry entries; the rest of the file is prose. A section is
# recognised by how its heading starts, not by the whole heading, because
# "P1 -- shapes the work, does not stop it" is a sentence somebody will reword
# and a guard that fails on a reworded subtitle gets deleted. What the rules
# below actually depend on is that all three kinds are present and populated,
# and that is what is enforced.
KINDS = (("P0", "p0"), ("P1", "p1"), ("SETTLED", "settled"))
OPEN_KINDS = ("P0", "P1")

# A backticked repository-relative path. Only backticked text is considered a
# reference: the index writes every path in backticks, and prose mentions of
# "handoff §11" name a document section, not a file. Requiring a slash and an
# extension keeps the other backticked things in the document -- `sunshine`,
# `kSplitViewHorizontal`, `font-weight: 650`, `proprietary_codecs=false`,
# `chrome://sunshine-*` -- from being read as paths that do not exist.
BACKTICKED = re.compile(r"`([^`]+)`")
PATH = re.compile(r"[A-Za-z0-9_][A-Za-z0-9_.\-]*(?:/[A-Za-z0-9_][A-Za-z0-9_.\-]*)+\.[A-Za-z0-9]+")

# `ADR 0004`, written in prose where the file is not spelled out. The number is
# the identity; the slug after it is free to change, so the file is looked up
# by glob rather than by an assumed name.
ADR_CITATION = re.compile(r"\bADR\s+(\d{4})\b")
ADR_DIRECTORY = "docs/decisions"


class Entry(NamedTuple):
    """One indexed decision: a table row, or a bullet in the P1 list."""

    kind: str
    ordinal: int
    cells: list[str]
    # Column count of the section's header row, or None for a bullet list.
    width: int | None

    @property
    def label(self) -> str:
        shape = "item" if self.width is None else "row"
        return f"{self.kind} {shape} {self.ordinal}"

    @property
    def text(self) -> str:
        return " ".join(self.cells)


def _kind(heading: str) -> str | None:
    folded = heading.casefold()
    for kind, prefix in KINDS:
        if folded.startswith(prefix):
            return kind
    return None


def parse(text: str) -> dict[str, list[Entry]]:
    """Entries by section kind. A kind absent from the result had no heading;
    a kind present but empty had a heading and nothing under it. The two are
    different failures and are reported differently."""

    sections: dict[str, list[Entry]] = {}
    kind: str | None = None
    width: int | None = None
    ordinal = 0

    for line in text.splitlines():
        heading = HEADING.match(line)
        if heading:
            kind = _kind(heading.group(1))
            width = None
            ordinal = 0
            if kind is not None:
                sections.setdefault(kind, [])
            continue
        if kind is None:
            continue

        stripped = line.strip()
        if stripped.startswith("|"):
            cells = [cell.strip() for cell in stripped.strip("|").split("|")]
            if width is None:
                # The first table line in a section is its header, and its
                # column count is what every row is held to.
                width = len(cells)
                continue
            if TABLE_RULE.match(stripped):
                continue
            ordinal += 1
            sections[kind].append(Entry(kind, ordinal, cells, width))
            continue

        bullet = BULLET.match(stripped)
        if bullet:
            ordinal += 1
            sections[kind].append(Entry(kind, ordinal, [bullet.group(1)], None))

    return sections


def question_key(text: str) -> str:
    """The identity of a question, for exact comparison.

    Everything up to and including the first `?` -- which is the question, with
    whatever context precedes it -- lowercased with punctuation and markup
    removed, so that a row copied between sections still matches after it has
    been rewrapped or its emphasis changed. Entries with no `?` (a few P1
    items are phrased as statements) use their whole text, which includes the
    owning document and so is if anything more specific, not less.
    """

    collapsed = re.sub(r"\s+", " ", text).strip()
    head, mark, _ = collapsed.partition("?")
    question = head + mark if mark else collapsed
    return re.sub(r"[^a-z0-9 ]+", "", question.casefold()).strip()


def check_structure(sections: dict[str, list[Entry]], failures: list[str]) -> None:
    """The index must still have the shape the other rules read.

    An empty section is not a pass by absence. If every blocking question has
    been answered that is a result worth stating in the section, and stating it
    is a deliberate edit; a table that has quietly emptied looks identical to
    one whose rows stopped being parsed, and the guard must not be unable to
    tell those apart.
    """

    for kind, _ in KINDS:
        if kind not in sections:
            failures.append(
                f"{INDEX}: no {kind} section; the index was restructured and "
                "the checks below no longer read it"
            )
        elif not sections[kind]:
            failures.append(
                f"{INDEX}: the {kind} section has no entries; if that is true, "
                "say so in the section rather than leaving it empty"
            )


def check_rows_are_well_formed(sections: dict[str, list[Entry]], failures: list[str]) -> None:
    """A row that does not match its header has an unescaped pipe or a missing
    column, and every column-addressed rule after this one would read the wrong
    cell. An empty question cell is a row that indexes nothing."""

    for entries in sections.values():
        for entry in entries:
            if entry.width is not None and len(entry.cells) != entry.width:
                failures.append(
                    f"{INDEX} {entry.label}: has {len(entry.cells)} column(s), "
                    f"header declares {entry.width}"
                )
            elif not entry.cells[0]:
                failures.append(f"{INDEX} {entry.label}: names no question")


def references(entry: Entry) -> list[str]:
    """Repository-relative document paths the entry cites."""

    found = []
    for token in BACKTICKED.findall(entry.text):
        candidate = token.strip()
        if PATH.fullmatch(candidate):
            found.append(candidate)
    return found


def check_references_resolve(
    root: Path, sections: dict[str, list[Entry]], failures: list[str]
) -> int:
    """Rule one: a row that points at a document that is not there is exactly
    the disagreement-with-its-sources the index was built to end."""

    count = 0
    for kind, _ in KINDS:
        for entry in sections.get(kind, []):
            for reference in references(entry):
                count += 1
                # `PATH` admits only segments that begin with a letter, digit
                # or underscore, so a reference can be neither absolute nor a
                # `..` escape and there is nothing further to guard here.
                if not (root / reference).is_file():
                    failures.append(f"{INDEX} {entry.label}: {reference} does not exist")
    return count


def check_adr_citations(
    root: Path, sections: dict[str, list[Entry]], failures: list[str]
) -> int:
    """Rule two, for the ADRs cited by number rather than by path.

    `docs/decisions/0004-media-codecs.md` is caught by the path rule above.
    "re-opens ADR 0004" is not a path and would otherwise go unchecked, which
    matters because a bare number is the citation form most likely to name a
    decision record nobody ever wrote.
    """

    count = 0
    for kind, _ in KINDS:
        for entry in sections.get(kind, []):
            for number in ADR_CITATION.findall(entry.text):
                count += 1
                if not sorted((root / ADR_DIRECTORY).glob(f"{number}-*.md")):
                    failures.append(
                        f"{INDEX} {entry.label}: cites ADR {number}, "
                        f"and no {ADR_DIRECTORY}/{number}-*.md exists"
                    )
    return count


def check_settled_rows_name_a_settlement(
    sections: dict[str, list[Entry]], failures: list[str]
) -> None:
    """Rule four: a settled row has to say what settled it.

    The citation is required to be concrete -- a backticked path, symbol or
    schema name -- and not required to be a document path. Two rows in the
    index today are settled by something that is not a document at all (a
    registry schema, and an upstream symbol confirmed at the pinned tag), and
    they are legitimately settled. What this rejects is the vague settlement:
    "yes", "decided", "agreed in review", a cell that leaves the reader with
    the old question and nowhere to take it.
    """

    for entry in sections.get("SETTLED", []):
        if len(entry.cells) < 2:
            continue  # already reported as malformed
        settled_by = entry.cells[1]
        if not settled_by:
            failures.append(f"{INDEX} {entry.label}: names no settling document")
        elif not BACKTICKED.search(settled_by):
            failures.append(
                f"{INDEX} {entry.label}: settled by {settled_by!r}, which cites "
                "no document, decision record or named artefact"
            )


def check_no_question_listed_twice(
    sections: dict[str, list[Entry]], failures: list[str]
) -> None:
    """Rule three, and the reason the index exists.

    A question that is open and settled at once reads as blocking work that is
    not blocked -- the expensive failure named in the index's own preamble --
    and a question listed twice in the open sections is the duplication it was
    created to collapse. Both are the same test: one normalised question, two
    places.
    """

    seen: dict[str, str] = {}
    for kind, _ in KINDS:
        for entry in sections.get(kind, []):
            key = question_key(entry.cells[0])
            if not key:
                continue
            if key in seen:
                first = seen[key]
                if first.split()[0] in OPEN_KINDS and entry.kind == "SETTLED":
                    failures.append(
                        f"{INDEX} {entry.label}: the question at {first} is also "
                        "listed as settled; an open question that is already "
                        "answered reads as blocking work that is not blocked"
                    )
                else:
                    failures.append(
                        f"{INDEX} {entry.label}: repeats the question at {first}"
                    )
            else:
                seen[key] = entry.label


def validate(root: Path = ROOT) -> tuple[dict[str, int], list[str]]:
    """Returns (counts, failures). Counts are reported on success because a
    guard that says only "passed" cannot be told from one that checked
    nothing."""

    counts = {"P0": 0, "P1": 0, "SETTLED": 0, "references": 0, "adrs": 0}
    failures: list[str] = []

    path = root / INDEX
    if not path.is_file():
        return counts, [f"{INDEX}: missing"]

    sections = parse(path.read_text(encoding="utf-8"))
    for kind, _ in KINDS:
        counts[kind] = len(sections.get(kind, []))

    check_structure(sections, failures)
    check_rows_are_well_formed(sections, failures)
    counts["references"] = check_references_resolve(root, sections, failures)
    counts["adrs"] = check_adr_citations(root, sections, failures)
    check_settled_rows_name_a_settlement(sections, failures)
    check_no_question_listed_twice(sections, failures)
    return counts, failures


def main() -> int:
    counts, failures = validate()
    if failures:
        print("\n".join(failures), file=sys.stderr)
        return 1
    print(
        "Decision index check passed: "
        f"{counts['P0']} P0, {counts['P1']} P1, {counts['SETTLED']} settled; "
        f"{counts['references']} document reference(s), "
        f"{counts['adrs']} ADR citation(s), all resolving."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
