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

Five facts are decidable from files in this repository:

    first_party/commands.json           how many commands are registered
    first_party/commands.json           how many command surfaces are declared
    first_party/registry.json           how many first-party modules exist
    downstream/patches/series           how many patches are in the stack
    tests/                              how many tests the suite holds

and one value is decidable from `config/chromium.version` -- the pinned
revision. A stale revision literal in a contract is not a count, but it is the
same failure with the same cause (a repository fact restated in prose and then
left behind), so it is checked here rather than in a sixth guard nobody runs.

The suite count was added last and for a specific reason. The acceptance index
once said the repository held "one hundred and forty tests"; the real number was
383 by the time anyone noticed. It was rewritten to a dated measurement -- "On
2026-08-17 `python -m unittest discover -s tests` reported 418 tests" -- which
is the weakest available fix, because a number with a date on it is still a
number that rots and the date only says how stale it might be. The count is
reconstructed from source instead; see "Counting the suite without running it".

Precision, not coverage
-----------------------

The corpus decides the patterns; the patterns were read out of `docs/*.md`,
not invented. English states counts in many forms, and most of the forms that
look like registry claims are not. A guard that fires on a sentence which was
never a claim about this repository gets deleted the first time it blocks
correct work, so every rule below exists to *narrow* what matches.

A phrase is a claim only when all of these hold.

**The counted noun is one of five.** `commands` (and `command names`,
`command entries`), `surfaces`, `modules`, `patches`, `tests` (and `test
methods`, `test cases`). Nothing else.
`docs/TELEMETRY_CONTRACT.md` section 5.5 weighs "twenty-four separate histogram
names" against "one enumerated histogram with twenty-four buckets", and
`docs/OPEN_DECISIONS.md` P1 repeats it as a question. Those sentences contain
the registry's number because they are *about* the registry's size, but they
count histogram names, XML entries and buckets -- none of which this repository
holds. `docs/BROWSER_UTILITIES_CONTRACT.md` counts "Eleven of these utilities",
a subset, with the registry path in the same sentence. A noun set that grew to
cover any of them would turn a correct document into a build failure.

**The claim names its source.** The count phrase's block must contain
`first_party/commands.json`, `first_party/registry.json`, or
`downstream/patches/series`. Without that anchor, "N commands" is almost always
a subset: `docs/ADVANCED_TABS_CONTRACT.md` says "its two registered commands"
about `tab.group.create` and `tab.group.ungroup`, and it is right. The anchor is
looked for in the enclosing block rather than the sentence because
`docs/EXTENSION_MIME_CONTRACT.md` XM-C3 names the file in one sentence of a
table cell and states the count in the next.

For `tests` the anchor is the string `unittest discover`, and deliberately not
`tests/`. `tests/` is the obvious choice and is unusable: the contracts name
individual test files constantly, so any block mentioning
`tests/test_command_registry.py` would anchor a count of tests sitting near it.
`docs/TAB_WORKSPACE_SPLIT_CONTRACT.md` section 4.2 is exactly that block -- "the
two tests that assert their presence", beside `tests/test_command_registry.py`
-- and anchoring on `tests/` reports that correct sentence as claiming 2 when
the suite holds 469. The claim worth checking is "what the discover command
reports", so the citation of that command is what makes a sentence the claim.
The consequence is a real narrowing: a document that states a test count without
citing the command is not checked, and that is the intended trade.

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

  * bare counts with no source named, at or below the total -- subsets;
  * any noun outside the five above, including `names`, `buckets`, `entries`,
    `rows`, `utilities`, `items`;
  * counts of tests that do not cite the discover command, including the
    acceptance index's own "14 tests SRA-1…SRA-14" and "8 tests DSA-1…DSA-8",
    which count criteria in a contract and not test methods in `tests/`;
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

import ast
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
    Subject(
        name="tests",
        source="tests/",
        nouns=r"test\s+methods|test\s+cases|tests",
        # The discover command, and only the discover command. `tests/` looks
        # like the obvious anchor and is not usable: it appears throughout the
        # contracts as the head of a file path, so a block naming
        # `tests/test_command_registry.py` would anchor any count of tests near
        # it. `docs/TAB_WORKSPACE_SPLIT_CONTRACT.md` §4.2 does exactly that --
        # "the two tests that assert their presence" sits in a block that names
        # `tests/test_command_registry.py` -- and anchoring on `tests/` reports
        # that correct sentence as claiming 2 when the suite holds 469. The
        # claim being checked is "what that command reports", so the citation of
        # that command is the honest anchor for it.
        anchors=("unittest discover",),
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


# --- Counting the suite without running it ------------------------------------
#
# `python -m unittest discover -s tests` reports a number by importing every
# test module and executing every test. This guard may do neither: it must stay
# fast and side-effect free. So the number is reconstructed from source, and the
# reconstruction has to equal what that command prints -- a guard that checks a
# nearby-but-different number is worse than the dated prose it replaces, because
# it looks authoritative.
#
# What `unittest` actually counts, and what is reproduced here:
#
#   * files under the start directory matching `test*.py` (the discover default);
#   * module-level classes deriving from `TestCase`, transitively;
#   * their methods whose names begin with `test` (`testMethodPrefix`, whose
#     default is `test` and not `test_`), **including methods inherited from a
#     base class** -- a base with one test method and three subclasses is four
#     tests, not one -- and de-duplicated by name, so an override is one test.
#
# Three things it is easy to get wrong, all verified against real discovery in
# `tests/test_stated_counts.py`: a `subTest` loop is **one** test however many
# sub-cases it runs; a `@unittest.skip` method is still counted, because it is
# collected and reported; and a class nested inside another class is *not*
# collected, because the loader iterates module attributes.
#
# Where a construct makes membership undecidable from source, this refuses to
# answer rather than guessing low. Silently under-counting is the failure that
# matters: it would let the documented number drift back toward the truth from
# the wrong side and read as agreement. The refusals below were each checked to
# fire on a fixture and to be absent from `tests/` today.

TESTCASE_BASES = frozenset(
    {
        "unittest.TestCase",
        "TestCase",
        "unittest.IsolatedAsyncioTestCase",
        "IsolatedAsyncioTestCase",
    }
)
# Bases that cannot be a TestCase, so a class carrying one stays decidable.
INERT_BASES = frozenset({"object", "Exception", "ValueError", "RuntimeError"})

DISCOVER_GLOB = "test*.py"  # unittest.TestLoader.discover's default pattern
TEST_METHOD_PREFIX = "test"  # unittest.TestLoader.testMethodPrefix's default


class UncountableSuite(Exception):
    """The suite contains something whose test count is not decidable statically."""


def _class_table(tree: ast.Module) -> dict[str, tuple[list[str], list[str]]]:
    """name -> (base expressions, own test-method names), module level only."""

    table: dict[str, tuple[list[str], list[str]]] = {}
    for node in tree.body:
        if isinstance(node, ast.ClassDef):
            methods = [
                item.name
                for item in node.body
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef))
                and item.name.startswith(TEST_METHOD_PREFIX)
            ]
            table[node.name] = ([ast.unparse(base) for base in node.bases], methods)
    return table


def _refuse_unmodellable(tree: ast.Module, table: dict, label: str) -> None:
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == "load_tests":
            raise UncountableSuite(f"{label} defines load_tests(), which builds the suite at runtime")

    # A class the loader can see but this parser cannot: one defined inside an
    # `if`, a loop, or a factory function still becomes a module attribute.
    # A class nested directly in another class does not, and is fine.
    permitted = {id(node) for node in tree.body}
    permitted |= {
        id(item)
        for node in tree.body
        if isinstance(node, ast.ClassDef)
        for item in node.body
    }
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and id(node) not in permitted:
            raise UncountableSuite(
                f"{label} defines class {node.name} at line {node.lineno} outside the module body; "
                "whether the loader sees it depends on runtime"
            )
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "setattr":
            raise UncountableSuite(
                f"{label} calls setattr() at line {node.lineno}; test methods may be added at import time"
            )

    for name, (bases, _) in table.items():
        for base in bases:
            if base not in TESTCASE_BASES and base not in INERT_BASES and base not in table:
                raise UncountableSuite(
                    f"{label}: class {name} inherits from {base!r}, which is not defined in that "
                    "module, so its inherited test methods cannot be read"
                )

    # `Alias = SomeTestCaseClass` gives the loader a second module attribute for
    # the same class, and it counts the tests twice.
    for node in tree.body:
        if isinstance(node, ast.Assign) and isinstance(node.value, ast.Name) and node.value.id in table:
            raise UncountableSuite(
                f"{label} binds {node.value.id} to a second module-level name at line {node.lineno}; "
                "the loader would count its tests twice"
            )


def count_module_tests(text: str, label: str) -> int:
    try:
        tree = ast.parse(text)
    except SyntaxError as error:
        raise UncountableSuite(f"{label} does not parse: {error}") from error

    table = _class_table(tree)
    _refuse_unmodellable(tree, table, label)

    def is_case(name: str, seen: tuple[str, ...] = ()) -> bool:
        if name in seen or name not in table:
            return False
        bases, _ = table[name]
        return any(
            base in TESTCASE_BASES or is_case(base, seen + (name,)) for base in bases
        )

    def methods(name: str, seen: tuple[str, ...] = ()) -> set[str]:
        if name in seen:
            return set()
        bases, own = table[name]
        found = set(own)
        for base in bases:
            if base in table:
                found |= methods(base, seen + (name,))
        return found

    return sum(len(methods(name)) for name in table if is_case(name))


def count_tests(root: Path) -> int:
    """What `python -m unittest discover -s tests` would report."""

    base = root / "tests"
    if not base.is_dir():
        raise UncountableSuite("there is no tests/ directory")
    for entry in sorted(base.iterdir()):
        if entry.is_dir() and entry.name != "__pycache__":
            raise UncountableSuite(
                f"tests/{entry.name}/ is a subdirectory; whether discovery recurses into it "
                "depends on package rules this does not model"
            )
    return sum(
        count_module_tests(path.read_text(encoding="utf-8"), path.name)
        for path in sorted(base.glob(DISCOVER_GLOB))
    )


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

    try:
        counts["tests"] = count_tests(root)
    except UncountableSuite:
        # The reason is reported by `stated_counts`, and only when a document
        # actually claims a test count -- a suite this cannot count is not by
        # itself a defect.
        pass

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
    actual: int | None  # None when the repository side could not be computed
    sentence: str
    rule: str  # "names the source file" or "above the registry total"
    unavailable: str = ""

    @property
    def agrees(self) -> bool:
        return self.actual is not None and self.stated == self.actual

    def failure(self) -> str:
        if self.actual is None:
            return (
                f"{self.document}:{self.line}: states {self.stated} {self.subject}, "
                f"which cannot be checked -- {self.unavailable} -- {self.sentence!r}"
            )
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

    # A subject whose *file* is missing is skipped entirely (another guard owns
    # absence). The suite is different: it is always present, so failing to
    # count it means this guard has met a construct it cannot model, and a
    # document claiming a number the guard silently stopped checking is the
    # exact failure the guard exists to prevent. So the claim is still reported,
    # as unverifiable rather than as wrong.
    unavailable = ""
    if "tests" not in counts:
        try:
            count_tests(root)
        except UncountableSuite as error:
            unavailable = str(error)

    claims: list[Claim] = []
    for path in _documents(root):
        label = path.relative_to(root).as_posix()
        text = path.read_text(encoding="utf-8")
        for block in blocks(text):
            masked = mask_quoted(block.text)
            for subject in SUBJECTS:
                actual = counts.get(subject.name)
                if actual is None and not (subject.name == "tests" and unavailable):
                    continue
                anchored = any(anchor in block.text for anchor in subject.anchors)
                if not anchored and not subject.bounded:
                    continue
                claims.extend(
                    _claims_in_block(
                        label, block, masked, subject, actual, anchored, unavailable
                    )
                )
    return claims


def _claims_in_block(
    label: str,
    block: Block,
    masked: str,
    subject: Subject,
    actual: int | None,
    anchored: bool,
    unavailable: str = "",
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
            elif actual is not None and stated > actual and not CONDITIONAL.search(sentence):
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
                    unavailable=unavailable,
                )
            )
    return claims


# --- The pinned revision ------------------------------------------------------

# Revisions a document may name **because** they are not the pin.
#
# One thing in this repository has that shape: the roll-cost measurement in
# `docs/BROWSER_OR_APP_REVIEW.md` section 10, whose entire subject is what the
# patch stack costs at a revision other than the pinned one. Its literal is a
# record of an experiment, not a link into upstream source, so a roll must
# leave it alone -- which is the opposite of what the rule below enforces.
#
# Keyed by document, so the exemption cannot spread on its own. A file not
# listed here that names the same revision is still a failure -- adding one is a
# visible edit to this table and not something a document can do to itself.
NOT_THE_PIN: dict[str, tuple[str, ...]] = {
    "docs/BROWSER_OR_APP_REVIEW.md": ("153.0.8000.0",),
    # The gesture patch's roll cost, measured against the same milestone before
    # the patch was committed. Same shape as above: a record of what the next
    # roll will require, which a roll must not rewrite.
    "docs/GESTURE_CONTRACT.md": ("153.0.8000.0",),
    # The store's roll-cost measurement, taken before the store was written.
    # Same shape again: a record of what the next milestone costs, which a roll
    # must not rewrite.
    "docs/DOCUMENT_STORE_CONTRACT.md": ("153.0.8000.0",),
    # What owning the installer's files would cost at the next milestone,
    # measured before any of them is owned. The literal is load-bearing in the
    # opposite direction from the rule: this document's finding is that
    # `util_constants.cc` does not exist at that revision, which a roll that
    # rewrote the number would erase.
    "docs/INSTALLER_CHOICE_PLAN.md": ("153.0.8000.0",),
    # §3c's roll-cost table for the two searchbox files, measured before either
    # was owned. The point of the row is that the two lines the patch anchors on
    # are byte-identical at that milestone while the files around them move; a
    # roll that rewrote the literal would turn a measurement into a claim about
    # whichever revision was current when someone last ran sed.
    "docs/NEWTAB_BACKGROUND_CONTRACT.md": ("153.0.8000.0",),
    # §16's two routes to a localised command title, measured before either is
    # taken. The finding is a comparison -- `chrome_repack_locales.gni` moves by
    # two lines where `chromium_strings.grd` moves by sixty-four -- and a roll
    # that rewrote the literal would leave the two numbers describing different
    # revisions and the comparison meaning nothing.
    "docs/COMMAND_PALETTE_CONTRACT.md": ("153.0.8000.0",),
}


# --- Status claims ------------------------------------------------------------
#
# A third failure with the same cause as the two above: a repository fact
# restated in prose and then left behind. This one is about existence rather
# than quantity, and it has now happened four times in two documents.
#
#   * `docs/INSTALLER_UI_CONTRACT.md` said "No implementation exists" while
#     `installer/sunshine_setup.cpp` held 948 lines;
#   * the same document then said neither of the owner's two decisions was
#     built, three days after the folder half landed as patch `0023`;
#   * `docs/INSTALLER_CHOICE_PLAN.md` §9 said "Nothing is built, and nothing
#     has been compiled" and that the relaxed-validation patch "has not been
#     written or applied" -- in a document whose §3 is headed *Built, and what
#     it actually took*;
#   * `docs/NEWTAB_BACKGROUND_CONTRACT.md` §3a said "Nothing is built" from the
#     day resting landed in patch `0002`.
#
# **Two rules, and both are about form rather than meaning**, because meaning is
# what made the obvious rule useless: the natural check -- refuse a sentence
# saying a named patch is unwritten -- would have caught **none** of the four,
# since not one of them named a patch. What it does is make the next such
# sentence checkable, by refusing the one shape that can be decided.
#
# Neither rule catches a scoped claim like "neither of the two is built". That
# is stated here rather than papered over: the coverage is the shape that can be
# decided offline, and a person reading the document is still the only thing
# that catches the rest.

# Only these. Each is an assertion that a thing does not exist, in the present
# perfect or present tense; none of them is a statement about running, seeing,
# measuring or compiling, which are the honest contents of a NOT VERIFIED
# section and must keep passing.
ABSENCE = re.compile(
    r"\b(?:ha(?:s|ve) not been (?:written|applied|created)"
    r"|(?:is|are) not written"
    r"|do(?:es)? not exist"
    r"|no such patch)\b",
    re.IGNORECASE,
)

# "Nothing is built" in a document that elsewhere heads a section *Built*.
NOTHING_BUILT = re.compile(
    r"\bnothing (?:is|has been) built\b|\bnothing has been compiled\b", re.I)
BUILT_HEADING = re.compile(r"^#{2,5} .*\bBuilt\b.*$", re.M)

# A patch this repository either has or has not. Restricted to patches on
# purpose: a `docs/…` path can exist as a file while the thing it names does
# not exist as a decision, and that ambiguity is exactly what a guard must not
# adjudicate. A patch has no such reading.
PATCH_REFERENCE = re.compile(r"(?:downstream/patches/)?(\d{4}-[a-z0-9][a-z0-9-]*\.patch)")

# Straight and curly double quotes only. Backticks are deliberately left alone:
# the patch reference this rule needs to see is inside them.
_SPEECH = (re.compile(r'"[^"\n]*"'), re.compile(r"\u201c[^\u201d\n]*\u201d"))


def mask_speech(text: str) -> str:
    """Blank the inside of every double-quoted span, keeping offsets.

    This repository corrects a document by quoting the sentence that was wrong
    and leaving it visible. Every correction therefore contains the very words
    these rules refuse, and a rule that could not tell a quotation from a claim
    would make the honest fix impossible.
    """

    masked = text
    for pattern in _SPEECH:
        masked = pattern.sub(
            lambda m: m.group(0)[0] + "#" * (len(m.group(0)) - 2) + m.group(0)[-1],
            masked,
        )
    return masked


# A sentence ends at `.`, `!` or `?` followed by space. Deliberately naive: the
# alternative is a sentence tokeniser, and every case this rule judges is one
# clause long.
_SENTENCE_END = re.compile(r"(?<=[.!?])\s+")


def _sentences(text: str) -> list[tuple[int, str]]:
    """(offset, sentence) for each sentence in `text`."""

    spans, cursor = [], 0
    for match in _SENTENCE_END.finditer(text):
        spans.append((cursor, text[cursor:match.start()]))
        cursor = match.end()
    spans.append((cursor, text[cursor:]))
    return [(start, body) for start, body in spans if body.strip()]


# A Sunshine surface spelled as a scheme this build does not register.
#
# ADR 0003 decided there is no `sunshine://` scheme: every surface is
# `chrome://sunshine-<host>`, and SEC-13 refuses the alternative. RV-4 is the
# runtime gate for what happens when a person types one anyway -- it searches.
#
# So a document that spells a surface `sunshine://account` is not using an old
# name; it is telling a reader to type something that will search the web for
# the page they are standing next to. Both places this fired had been written
# *after* ADR 0003, describing a page patch 0018 had already registered at the
# other address.
#
# The hosts come from the patch stack rather than from a list here, so a surface
# added tomorrow is covered the day it is registered.
SCHEME_SPELLING = re.compile(r"\bsunshine://([a-z][a-z0-9-]*)")

# The one document that may carry the spelling, because retiring it is what the
# document is about. ADR 0003 also names five documents whose legacy spellings
# it left to later waves; every one of those has since been corrected, so they
# are not exempt and must not become so again.
SCHEME_EXEMPT = frozenset({"docs/decisions/0003-internal-scheme.md"})


def registered_hosts(root: Path) -> set[str]:
    """The `sunshine-<name>` hosts the patch stack registers, as `<name>`."""

    directory = root / "downstream/patches"
    if not directory.is_dir():
        return set()
    pattern = re.compile(r'kChromeUISunshine[A-Za-z]+Host\[\] = "sunshine-([a-z-]+)"')
    found: set[str] = set()
    for patch in sorted(directory.glob("*.patch")):
        found.update(pattern.findall(patch.read_text(encoding="utf-8")))
    return found


@dataclass(frozen=True)
class StatusClaim:
    document: str
    line: int
    rule: str
    detail: str
    sentence: str

    def failure(self) -> str:
        return (
            f"{self.document}:{self.line}: {self.detail} -- {self.rule} "
            f"({self.sentence!r})"
        )


def status_claims(root: Path) -> list[StatusClaim]:
    """Every existence claim a document makes that the repository disagrees with."""

    series = root / "downstream/patches/series"
    if not series.is_file():
        return []
    applied = {
        line.strip()
        for line in series.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    }

    hosts = registered_hosts(root)

    claims: list[StatusClaim] = []
    for path in _documents(root):
        label = path.relative_to(root).as_posix()
        text = path.read_text(encoding="utf-8")
        has_built_heading = BUILT_HEADING.search(text) is not None
        spoken = mask_speech(text)

        if label not in SCHEME_EXEMPT:
            for number, line in enumerate(text.splitlines(), start=1):
                for match in SCHEME_SPELLING.finditer(line):
                    name = match.group(1)
                    if name not in hosts:
                        continue
                    claims.append(
                        StatusClaim(
                            document=label,
                            line=number,
                            rule="ADR 0003 registers no scheme; the surface is "
                                 f"chrome://sunshine-{name}",
                            detail=f"spells a registered surface sunshine://{name}",
                            sentence=line.strip()[:160],
                        )
                    )

        for block in blocks(spoken):
            # Sentence scope, not paragraph scope, and a false positive on the
            # first run is why. `docs/ACCOUNT_LINK_PLAN.md` §0 names patch 0018
            # in one sentence and lists what does not exist -- consent, tokens,
            # unlinking -- in the next. Both are true, both are in one
            # paragraph, and a paragraph-wide rule read them as one claim. A
            # guard that fires on a correct document is deleted by the first
            # person it blocks.
            for start, sentence in _sentences(block.text):
                if not ABSENCE.search(sentence):
                    continue
                for match in PATCH_REFERENCE.finditer(sentence):
                    name = match.group(1)
                    if name in applied:
                        claims.append(
                            StatusClaim(
                                document=label,
                                line=block.line_of(start + match.start()),
                                rule="the patch is in downstream/patches/series",
                                detail=f"says {name} does not exist",
                                sentence=sentence.strip()[:160],
                            )
                        )
            if has_built_heading:
                for match in NOTHING_BUILT.finditer(block.text):
                    claims.append(
                        StatusClaim(
                            document=label,
                            line=block.line_of(match.start()),
                            rule="this document also heads a section 'Built'",
                            detail=f"says {match.group(0)!r}",
                            sentence=block.text.strip()[:160],
                        )
                    )
    return claims


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
                if match.group(0) in NOT_THE_PIN.get(label, ()):
                    continue
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
    statuses = status_claims(root)
    failures = [claim.failure() for claim in claims if not claim.agrees]
    failures += [citation.failure() for citation in citations if not citation.agrees]
    failures += [status.failure() for status in statuses]
    documents = {claim.document for claim in claims} | {c.document for c in citations}
    documents |= {status.document for status in statuses}
    summary = (
        f"{len(claims)} stated count(s), {len(citations)} pinned-revision "
        f"citation(s) and every document's existence claims checked across "
        f"{len(documents)} document(s)"
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
