#!/usr/bin/env python3
"""Fail when a document states a count the repository disagrees with.

The contracts under `docs/` state counts about this repository in prose --
"twenty-four registered commands", "three patches" -- and prose does not
recompile when the thing it counts changes. This has already gone wrong twice
in ways that were checkable offline in seconds:

  * `docs/BROWSER_UTILITIES_CONTRACT.md` was left saying no browser utility was
    registered by the same wave that registered eleven of them;
  * `docs/COMMAND_PALETTE_CONTRACT.md` counted 27 registered commands and 21
    Chromium-owned ones after the three `view.split.*` commands were retired,
    when the registry held 24 and 20. `docs/ACCEPTANCE_SUITES.md` C5 records the
    correction, and section 15 of the palette contract records it again, and
    section 4.3 of that same contract still reads 27 today.

Four facts are decidable from files in this repository:

    first_party/commands.json           how many commands are registered
    first_party/commands.json           how many command surfaces are declared
    first_party/registry.json           how many first-party modules exist
    downstream/patches/series           how many patches are in the stack

and one value is decidable from `config/chromium.version` -- the pinned
revision. A stale revision literal in a contract is not a count, but it is the
same failure with the same cause (a repository fact restated in prose and then
left behind), so it is checked here rather than in a fifth guard nobody runs.

Precision, not coverage
-----------------------

The corpus decides the patterns; the patterns were read out of `docs/*.md`,
not invented. English states counts in many forms, and most of the forms that
look like registry claims are not. A guard that fires on a sentence which was
never a claim about this repository gets deleted the first time it blocks
correct work, so every rule below exists to *narrow* what matches.

A phrase is a claim only when all of these hold.

**The counted noun is one of four.** `commands` (and `command names`,
`command entries`), `surfaces`, `modules`, `patches`. Nothing else.
`docs/TELEMETRY_CONTRACT.md` section 5.5 weighs "twenty-four separate histogram
names" against "one enumerated histogram with twenty-four buckets", and
`docs/OPEN_DECISIONS.md` P1 repeats it as a question. Those sentences contain
the registry's number because they are *about* the registry's size, but they
count histogram names, XML entries and buckets -- none of which this repository
holds. `docs/BROWSER_UTILITIES_CONTRACT.md` counts "Eleven of these utilities",
a subset, with the registry path in the same sentence. A noun set that grew to
cover any of them would turn a correct document into a build failure.

**The claim names its source file.** The count phrase's block must contain
`first_party/commands.json`, `first_party/registry.json`, or
`downstream/patches/series`. Without that anchor, "N commands" is almost always
a subset: `docs/ADVANCED_TABS_CONTRACT.md` says "its two registered commands"
about `tab.group.create` and `tab.group.ungroup`, and it is right. The anchor is
looked for in the enclosing block rather than the sentence because
`docs/EXTENSION_MIME_CONTRACT.md` XM-C3 names the file in one sentence of a
table cell and states the count in the next.

**The count is not inside quotation marks or backticks.** Block-scoped anchoring
would otherwise catch the one place in the corpus that quotes a wrong number in
order to correct it: `docs/ACCEPTANCE_SUITES.md` C5 reads
`It refers to "the 27 registered commands" ...` and then gives the true count
from `first_party/commands.json` two sentences later, in the same paragraph.
Firing on a document's own correction is the worst thing this guard could do.

**Nothing restricting sits between the number and the noun.** Only `registered`,
`shipped`, `declared` and `first-party` may intervene -- adjectives that do not
select a subset. `21 Chromium-owned commands`, `three split commands` and `the
four Sunshine-owned commands` are all counts of parts, and all are excluded by
this rule alone.

**The noun is not followed by backticked identifiers.** "the two registered
commands `tab.group.create` / `tab.group.ungroup`" enumerates which ones; a
phrase that lists its members is a claim about those members, not about the
total.

One rule fires without an anchor, because it is sound without one: a count of
`commands` **greater than the registry total** is wrong whatever subset it
describes, since no subset exceeds the whole. That is what catches
`docs/COMMAND_PALETTE_CONTRACT.md` section 4.3's surviving "Twenty-seven
commands", and it is what would have caught the palette contract's original
"27 registered commands" in the sentence that introduced it. It is applied to
`commands` only -- `surfaces` and `modules` are ordinary words in these
documents ("two profile-scoped surfaces", "a second module") and a bound on them
would fire on prose that never meant the registry. Sentences carrying a
conditional marker (`if`, `would`, `could`, ...) are exempt, because a
hypothetical palette "that rendered twenty-seven rows" is not an assertion.

Deliberately not matched, and left that way
-------------------------------------------

  * bare counts with no source file named, at or below the total -- subsets;
  * any noun outside the four above, including `names`, `buckets`, `entries`,
    `rows`, `utilities`, `items`;
  * counts written as `no` / `none` ("registers no download command") -- the
    word is doing set-selection work, not counting;
  * section and identifier references (`section 4.2`, `CPA-14`, `invariant 9`,
    `schema version 2`), headings, and ordered-list markers;
  * anything inside a fenced code block.

Each of those has a test asserting it stays unmatched. Those tests are the point:
they are what stops the matcher being "improved" into something that fires on
correct prose and is then removed altogether.

This guard claims no contract invariant identifier. `docs/ACCEPTANCE_SUITES.md`
section 9 records that the bare-ordinal invariant lists have no stable prefixes,
and inventing one here would be the same defect this file exists to prevent.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]

DOCS_DIRECTORY = "docs"


# --- Numbers as English writes them -------------------------------------------

_UNITS = {
    "zero": 0, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6,
    "seven": 7, "eight": 8, "nine": 9, "ten": 10, "eleven": 11, "twelve": 12,
    "thirteen": 13, "fourteen": 14, "fifteen": 15, "sixteen": 16,
    "seventeen": 17, "eighteen": 18, "nineteen": 19,
}
_TENS = {
    "twenty": 20, "thirty": 30, "forty": 40, "fifty": 50, "sixty": 60,
    "seventy": 70, "eighty": 80, "ninety": 90,
}

# Longest alternative first, or `nineteen` is read as `nine` and the rest of the
# word is left to be matched as an adjective, which it is not.
_UNIT_ALTERNATIVES = sorted(_UNITS, key=len, reverse=True)
_SMALL_UNITS = [word for word in _UNIT_ALTERNATIVES if 1 <= _UNITS[word] <= 9]
_NUMBER_WORD = "|".join(
    [rf"(?:{tens})[- ](?:{'|'.join(_SMALL_UNITS)})" for tens in _TENS]
    + list(_TENS)
    + _UNIT_ALTERNATIVES
)
# A digit run, or a cardinal word. Anchoring both ends on `\b` and checking the
# character before the match is what keeps `152.0.7977.42` and `CPA-14` out.
NUMBER = rf"(?:\d+|{_NUMBER_WORD})"


def parse_number(text: str) -> int | None:
    """The integer a matched number token names, or None if it is not one."""

    token = text.strip().lower().replace("‑", "-")
    if token.isdigit():
        return int(token)
    parts = re.split(r"[- ]", token)
    if len(parts) == 1:
        return _UNITS.get(parts[0], _TENS.get(parts[0]))
    if len(parts) == 2 and parts[0] in _TENS and parts[1] in _UNITS:
        return _TENS[parts[0]] + _UNITS[parts[1]]
    return None


# --- What may be counted ------------------------------------------------------


@dataclass(frozen=True)
class Subject:
    """One repository fact, and the English that may legitimately state it."""

    name: str
    source: str  # the file the count is read from, quoted back in failures
    nouns: str  # regex alternation, matched case-insensitively
    anchors: tuple[str, ...]  # naming one of these makes a phrase a claim
    bounded: bool  # may an unanchored count above the total be judged wrong?


SUBJECTS = (
    Subject(
        name="commands",
        source="first_party/commands.json",
        nouns=r"command\s+names|command\s+entries|commands",
        anchors=("first_party/commands.json",),
        bounded=True,
    ),
    Subject(
        name="command surfaces",
        source="first_party/commands.json",
        nouns=r"command\s+surfaces|surfaces",
        anchors=("first_party/commands.json",),
        bounded=False,
    ),
    Subject(
        name="modules",
        source="first_party/registry.json",
        nouns=r"module\s+manifests|first-party\s+modules|modules",
        anchors=("first_party/registry.json",),
        bounded=False,
    ),
    Subject(
        name="patches",
        source="downstream/patches/series",
        nouns=r"patch\s+files|patches",
        anchors=("downstream/patches/series",),
        bounded=False,
    ),
)

# Adjectives that describe the whole set rather than selecting part of it. Every
# other word between the number and the noun stops the match; that single rule
# excludes "21 Chromium-owned commands", "three split commands" and "the four
# Sunshine-owned commands", which are all counts of parts.
NEUTRAL_ADJECTIVE = r"(?:registered|shipped|declared|first-party)"

# A number preceded by any of these is an address, not a quantity. Identifier
# forms (`CPA-14`, `OMA-20`) and dotted forms (`4.2`) need no entry here: the
# character immediately before the number is checked separately.
REFERENCE_LEAD = re.compile(
    r"(?:§|\bsections?|\bsubsections?|\binvariants?|\bschema|\bstage|\bversion"
    r"|\bsteps?|\bitems?|\bfigures?|\btables?|\bwave|\bposition|\bruling|\badr"
    r"|\bpart|\bchapter|\bappendix)\s*$",
    re.IGNORECASE,
)

# The bound rule reasons about what *is*; these words mark a sentence that
# reasons about what would be.
CONDITIONAL = re.compile(
    r"\b(?:if|would|could|should|were|may|might|suppose|assume|imagine"
    r"|hypothetical|proposal|proposes|proposed|propose)\b",
    re.IGNORECASE,
)

QUOTED = (
    re.compile(r'"[^"\n]*"'),
    re.compile(r"“[^”\n]*”"),
    re.compile(r"`[^`\n]*`"),
)

# Immediately after the noun: an enumeration of the members being counted.
ENUMERATION_FOLLOWS = re.compile(r"^\s*(?:[:,]|--|—)?\s*`")


def _phrase_pattern(subject: Subject) -> re.Pattern[str]:
    return re.compile(
        rf"\b({NUMBER})\s+((?:{NEUTRAL_ADJECTIVE}\s+){{0,2}})(?:{subject.nouns})\b",
        re.IGNORECASE,
    )


PHRASE_PATTERNS = {subject.name: _phrase_pattern(subject) for subject in SUBJECTS}

# A four-part Chromium version. Restricted to this shape so it cannot match a
# section number, a date, or a token from a `.patch` hunk header.
VERSION_LITERAL = re.compile(r"\b\d{2,3}\.\d+\.\d{4}\.\d+\b")


# --- Ground truth -------------------------------------------------------------


def repository_counts(root: Path) -> dict[str, int]:
    """The four countable facts, read from the files that own them.

    A subject whose source file is missing is simply not checked: this guard
    reports disagreement, and `scripts/verify_architecture.py` already reports
    absence. Two guards failing for one cause tells a reader nothing extra.
    """

    counts: dict[str, int] = {}

    commands_path = root / "first_party/commands.json"
    if commands_path.is_file():
        registry = json.loads(commands_path.read_text(encoding="utf-8"))
        if isinstance(registry.get("commands"), list):
            counts["commands"] = len(registry["commands"])
        if isinstance(registry.get("surfaces"), list):
            counts["command surfaces"] = len(registry["surfaces"])

    registry_path = root / "first_party/registry.json"
    if registry_path.is_file():
        modules = json.loads(registry_path.read_text(encoding="utf-8"))
        if isinstance(modules.get("modules"), list):
            counts["modules"] = len(modules["modules"])

    series_path = root / "downstream/patches/series"
    if series_path.is_file():
        counts["patches"] = len(
            [
                line
                for line in series_path.read_text(encoding="utf-8").splitlines()
                if line.strip() and not line.lstrip().startswith("#")
            ]
        )

    return counts


def pinned_revision(root: Path) -> str | None:
    """The bare version the repository pins, without the `refs/tags/` prefix."""

    path = root / "config/chromium.version"
    if not path.is_file():
        return None
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("CHROMIUM_REVISION="):
            return line.split("=", 1)[1].strip().removeprefix("refs/tags/")
    return None


# --- Turning Markdown into judgeable units ------------------------------------


@dataclass(frozen=True)
class Block:
    """A paragraph, a list item, or one cell of a table row.

    Hard-wrapped prose means a sentence is not a line, so lines are joined and
    every offset in the joined text is mapped back to the line it came from.
    """

    text: str
    starts: tuple[tuple[int, int], ...]  # (offset in text, source line number)

    def line_of(self, offset: int) -> int:
        line = self.starts[0][1]
        for start, number in self.starts:
            if start > offset:
                break
            line = number
        return line


_TABLE_RULE = re.compile(r"^\s*\|[\s:|-]+\|\s*$")
_LIST_ITEM = re.compile(r"^\s*(?:[-*+]\s+|\d{1,3}[.)]\s+)")


def blocks(text: str) -> list[Block]:
    """Every judgeable unit of a Markdown document.

    Headings are dropped: `### 6.4 Commands` is a title, and its number is a
    section address. List items start new blocks so that an anchor in one bullet
    cannot make a claim out of a count in the next.
    """

    found: list[Block] = []
    pending: list[tuple[int, str]] = []
    fenced = False

    def flush() -> None:
        if not pending:
            return
        pieces: list[str] = []
        starts: list[tuple[int, int]] = []
        offset = 0
        for number, content in pending:
            starts.append((offset, number))
            pieces.append(content)
            offset += len(content) + 1
        found.append(Block(" ".join(pieces), tuple(starts)))
        pending.clear()

    for number, raw in enumerate(text.splitlines(), start=1):
        stripped = raw.strip()
        if stripped.startswith("```") or stripped.startswith("~~~"):
            flush()
            fenced = not fenced
            continue
        if fenced:
            continue
        if not stripped or stripped.startswith("#"):
            flush()
            continue
        if stripped.startswith("|"):
            flush()
            if _TABLE_RULE.match(raw):
                continue
            # A table row is several independent statements sharing a line.
            for cell in stripped.strip("|").split("|"):
                if cell.strip():
                    found.append(Block(cell.strip(), ((0, number),)))
            continue
        marker = _LIST_ITEM.match(raw)
        if marker:
            flush()
            # The list marker itself is dropped, so `21. **CPA-21.**` never
            # offers `21` as a quantity.
            pending.append((number, raw[marker.end():]))
            continue
        pending.append((number, stripped))
    flush()
    return found


_SENTENCE_END = re.compile(r"(?<=[.!?:;])\s+")


def sentence_spans(text: str) -> list[tuple[int, int]]:
    spans: list[tuple[int, int]] = []
    start = 0
    for boundary in _SENTENCE_END.finditer(text):
        spans.append((start, boundary.start()))
        start = boundary.end()
    if start < len(text):
        spans.append((start, len(text)))
    return spans


def mask_quoted(text: str) -> str:
    """Blank the inside of every quoted or backticked span, keeping offsets.

    Delimiters survive so that the "noun followed by backticked identifiers"
    test still sees them, and the anchor search runs on the unmasked text.
    """

    masked = text
    for pattern in QUOTED:
        masked = pattern.sub(lambda m: m.group(0)[0] + "#" * (len(m.group(0)) - 2) + m.group(0)[-1], masked)
    return masked


# --- Claims -------------------------------------------------------------------


@dataclass(frozen=True)
class Claim:
    document: str
    line: int
    subject: str
    source: str
    stated: int
    actual: int
    sentence: str
    rule: str  # "names the source file" or "above the registry total"

    @property
    def agrees(self) -> bool:
        return self.stated == self.actual

    def failure(self) -> str:
        return (
            f"{self.document}:{self.line}: states {self.stated} {self.subject}, "
            f"{self.source} has {self.actual} ({self.rule}) -- {self.sentence!r}"
        )


def _documents(root: Path) -> list[Path]:
    base = root / DOCS_DIRECTORY
    if not base.is_dir():
        return []
    return sorted(path for path in base.rglob("*.md") if path.is_file())


def stated_counts(root: Path) -> list[Claim]:
    counts = repository_counts(root)
    claims: list[Claim] = []
    for path in _documents(root):
        label = path.relative_to(root).as_posix()
        text = path.read_text(encoding="utf-8")
        for block in blocks(text):
            masked = mask_quoted(block.text)
            for subject in SUBJECTS:
                if subject.name not in counts:
                    continue
                anchored = any(anchor in block.text for anchor in subject.anchors)
                if not anchored and not subject.bounded:
                    continue
                claims.extend(
                    _claims_in_block(
                        label, block, masked, subject, counts[subject.name], anchored
                    )
                )
    return claims


def _claims_in_block(
    label: str,
    block: Block,
    masked: str,
    subject: Subject,
    actual: int,
    anchored: bool,
) -> list[Claim]:
    claims: list[Claim] = []
    pattern = PHRASE_PATTERNS[subject.name]
    for start, end in sentence_spans(block.text):
        sentence = block.text[start:end].strip()
        for match in pattern.finditer(masked, start, end):
            stated = parse_number(match.group(1))
            if stated is None:
                continue
            if REFERENCE_LEAD.search(masked[max(0, match.start() - 24):match.start()]):
                continue
            if match.start() and masked[match.start() - 1] in ".-/§":
                continue  # part of `4.2`, `CPA-14`, or a path
            if ENUMERATION_FOLLOWS.match(masked[match.end():match.end() + 8]):
                continue
            if anchored:
                rule = "names the source file"
            elif stated > actual and not CONDITIONAL.search(sentence):
                rule = "above the registry total"
            else:
                continue
            claims.append(
                Claim(
                    document=label,
                    line=block.line_of(match.start()),
                    subject=subject.name,
                    source=subject.source,
                    stated=stated,
                    actual=actual,
                    sentence=sentence,
                    rule=rule,
                )
            )
    return claims


# --- The pinned revision ------------------------------------------------------


@dataclass(frozen=True)
class Citation:
    document: str
    line: int
    stated: str
    actual: str
    sentence: str

    @property
    def agrees(self) -> bool:
        return self.stated == self.actual

    def failure(self) -> str:
        return (
            f"{self.document}:{self.line}: cites Chromium {self.stated}, "
            f"config/chromium.version pins {self.actual} -- {self.sentence!r}"
        )


def revision_citations(root: Path) -> list[Citation]:
    """Every four-part Chromium version literal a document states.

    Unlike the count rules this needs no natural-language judgement at all: the
    literal either equals the pinned revision or it does not. Documents cite it
    ~150 times, mostly inside upstream source URLs, and a roll that updates
    `config/chromium.version` without updating them leaves every one of those
    links pointing at the previous release.
    """

    pinned = pinned_revision(root)
    if pinned is None:
        return []
    citations: list[Citation] = []
    for path in _documents(root):
        label = path.relative_to(root).as_posix()
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            for match in VERSION_LITERAL.finditer(line):
                citations.append(
                    Citation(
                        document=label,
                        line=number,
                        stated=match.group(0),
                        actual=pinned,
                        sentence=line.strip()[:160],
                    )
                )
    return citations


# --- Entry point --------------------------------------------------------------


def check(root: Path = ROOT) -> tuple[str, list[str]]:
    """(summary, failures) for one repository tree."""

    claims = stated_counts(root)
    citations = revision_citations(root)
    failures = [claim.failure() for claim in claims if not claim.agrees]
    failures += [citation.failure() for citation in citations if not citation.agrees]
    documents = {claim.document for claim in claims} | {c.document for c in citations}
    summary = (
        f"{len(claims)} stated count(s) and {len(citations)} pinned-revision "
        f"citation(s) checked across {len(documents)} document(s)"
    )
    return summary, failures


def main() -> int:
    summary, failures = check()
    if failures:
        print("\n".join(failures), file=sys.stderr)
        print(f"Stated count check failed: {summary}.", file=sys.stderr)
        return 1
    print(f"Stated count check passed: {summary}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
