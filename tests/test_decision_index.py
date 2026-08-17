"""Tests for the open-decisions index guard.

`docs/OPEN_DECISIONS.md` closes with the rule it lives by -- "An index that only
grows becomes a second backlog, and one that disagrees with its sources is worse
than none" -- and nothing enforced it. The failure it names is quiet by
construction: a question answered elsewhere and still listed as open costs
nothing at the time and reads as blocking work for as long as it survives.

Every case here injects the violation. A guard that has only ever seen a clean
tree is indistinguishable from one whose patterns do not match -- and for a
guard built out of regular expressions over prose, that is the likelier of the
two failures. The cases that assert *nothing* is reported are as deliberate:
the index writes paths, symbols and CSS values in the same backticks, and a
guard that read `font-weight: 650` as a missing file would be deleted in a week.
"""

from pathlib import Path
import sys
import tempfile
import unittest

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY_ROOT / "scripts"))

import verify_decision_index as index  # noqa: E402


# A miniature of the real document: two P0 rows, two P1 items, two settled
# rows, and the same mix of backticked paths, symbols and values the real one
# carries. Each test replaces one part of it and leaves the rest clean, so a
# reported failure can only have come from the injected change.
P0_ROWS = [
    "| Are the acceptance suites gates or reports? | `docs/ACCEPTANCE_SUITES.md` §9 | Stage 1 exit |",
    "| When, if ever, is Sunshine distributed? It re-opens ADR 0004. "
    "| `docs/SECURITY_ARCHITECTURE_CONTRACT.md` §9 | distribution |",
]

P1_ITEMS = [
    "- Can a workspace span multiple windows? — handoff §11",
    "- Korean initial-consonant search in the palette — currently scoped out. "
    "— `docs/COMMAND_PALETTE_CONTRACT.md` §15",
]

SETTLED_ROWS = [
    "| Is an internal `sunshine` scheme registered? | `docs/decisions/0003-internal-scheme.md` "
    "— no scheme; surfaces are `chrome://sunshine-*` |",
    "| Is `font-weight: 650` resolvable? | Changed to 600, inside the allowed set; "
    "`docs/DESIGN_SYSTEM_CONTRACT.md` S8 now passes |",
]

# Documents the fixture index points at, plus one decision record cited by
# number only. Written empty: this guard checks that a reference resolves, not
# what it resolves to.
FIXTURE_DOCUMENTS = (
    "docs/ACCEPTANCE_SUITES.md",
    "docs/SECURITY_ARCHITECTURE_CONTRACT.md",
    "docs/COMMAND_PALETTE_CONTRACT.md",
    "docs/DESIGN_SYSTEM_CONTRACT.md",
    "docs/decisions/0003-internal-scheme.md",
    "docs/decisions/0004-media-codecs.md",
)


class IndexTestCase(unittest.TestCase):
    def setUp(self) -> None:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        for relative in FIXTURE_DOCUMENTS:
            self.write(relative, "# fixture\n")

    def write(self, relative: str, text: str) -> None:
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    def write_index(
        self,
        p0: list[str] | None = None,
        p1: list[str] | None = None,
        settled: list[str] | None = None,
        drop: str = "",
    ) -> None:
        """Write the fixture index, optionally with one section replaced or
        dropped entirely."""

        parts = ["# Open decisions", "", "Status and location, not content.", ""]
        if drop != "P0":
            parts += ["## P0 — blocking", ""]
            parts += ["| Question | Owner document | Blocks |", "| --- | --- | --- |"]
            parts += P0_ROWS if p0 is None else p0
            parts += [""]
        if drop != "P1":
            parts += ["## P1 — shapes the work, does not stop it", ""]
            parts += P1_ITEMS if p1 is None else p1
            parts += [""]
        if drop != "SETTLED":
            parts += ["## Settled, and where", ""]
            parts += ["| Was | Settled by |", "| --- | --- |"]
            parts += SETTLED_ROWS if settled is None else settled
            parts += [""]
        parts += ["## Keeping this honest", "", "Moved here in the same change.", ""]
        self.write("docs/OPEN_DECISIONS.md", "\n".join(parts))

    def failures(self) -> list[str]:
        return index.validate(self.root)[1]

    def assertRejected(self, needle: str) -> None:
        found = self.failures()
        self.assertTrue(found, "the violation was accepted")
        self.assertTrue(any(needle in failure for failure in found), f"{needle!r} not in {found}")


class CleanIndexTests(IndexTestCase):
    def test_a_consistent_index_passes(self) -> None:
        self.write_index()
        counts, failures = index.validate(self.root)
        self.assertEqual([], failures)
        self.assertEqual({"P0": 2, "P1": 2, "SETTLED": 2}, {k: counts[k] for k in ("P0", "P1", "SETTLED")})
        self.assertEqual(5, counts["references"])
        self.assertEqual(1, counts["adrs"])

    def test_backticked_text_that_is_not_a_path_is_not_a_reference(self) -> None:
        """The index backticks symbols, schemes and CSS values as well as paths.

        `sunshine`, `chrome://sunshine-*` and `font-weight: 650` all appear in
        the fixture's settled rows. A guard that read any of them as a document
        would fail on the real index the day it was written.
        """

        self.write_index()
        self.assertEqual([], self.failures())
        self.assertEqual(5, index.validate(self.root)[0]["references"])

    def test_two_differently_worded_questions_are_not_a_duplicate(self) -> None:
        """The duplicate rule is exact after normalisation, and stays that way.

        These two ask nearly the same thing in different words. Catching them
        would need fuzzy matching, and the first time fuzzy matching separated
        two genuinely distinct questions the guard would be deleted.
        """

        self.write_index(
            settled=[
                "| Are the acceptance suites reports, or gates? | `docs/ACCEPTANCE_SUITES.md` |",
            ]
        )
        self.assertEqual([], self.failures())


class ReferenceTests(IndexTestCase):
    def test_a_p0_row_naming_a_missing_owner_document_is_rejected(self) -> None:
        self.write_index(
            p0=["| Is partial extension compatibility acceptable? "
                "| `docs/EXTENSION_SCOPE.md` §4 | Stage 1 |"]
        )
        self.assertRejected("docs/EXTENSION_SCOPE.md does not exist")

    def test_a_p1_item_naming_a_missing_document_is_rejected(self) -> None:
        """The P1 list is a bullet list, not a table; it is parsed separately
        and would otherwise be checked by nothing."""

        self.write_index(p1=["- Should the tabs panel ship? — `docs/TABS_PANEL.md`"])
        self.assertRejected("P1 item 1: docs/TABS_PANEL.md does not exist")

    def test_a_settled_row_naming_a_missing_settling_document_is_rejected(self) -> None:
        self.write_index(
            settled=["| What is the telemetry sink? | `docs/TELEMETRY_CONTRACT.md` — record only |"]
        )
        self.assertRejected("docs/TELEMETRY_CONTRACT.md does not exist")

    def test_a_decision_record_that_was_never_written_is_rejected(self) -> None:
        """An ADR path is caught by the reference rule; `docs/decisions/0009-*`
        does not exist here, and a renamed slug would be caught too."""

        self.write_index(
            settled=["| Is a module a compiled capability? | `docs/decisions/0009-modules.md` |"]
        )
        self.assertRejected("docs/decisions/0009-modules.md does not exist")

    def test_an_adr_cited_by_number_alone_must_exist(self) -> None:
        """A bare number is the citation form most likely to name a decision
        record nobody ever wrote, precisely because it names no file."""

        self.write_index(
            p0=["| When is Sunshine distributed? It re-opens ADR 0011. | handoff §11 | distribution |"]
        )
        self.assertRejected("cites ADR 0011")

    def test_an_adr_whose_slug_changed_still_resolves(self) -> None:
        """The number is the identity; the slug after it is free to change."""

        (self.root / "docs/decisions/0004-media-codecs.md").rename(
            self.root / "docs/decisions/0004-codec-licensing.md"
        )
        self.write_index()
        self.assertEqual([], self.failures())


class DuplicateQuestionTests(IndexTestCase):
    def test_a_question_listed_as_open_and_as_settled_is_rejected(self) -> None:
        """The exact failure the index was built to end: a question answered
        elsewhere and still listed as blocking."""

        self.write_index(
            settled=["| Are the acceptance suites gates or reports? | `docs/ACCEPTANCE_SUITES.md` §9 |"]
        )
        self.assertRejected("also listed as settled")

    def test_the_duplicate_survives_rewrapping_and_emphasis(self) -> None:
        """A question moved between sections is usually retouched on the way --
        bolded, rewrapped, its dash restyled. Normalisation is what makes the
        rule worth having rather than a test for copy-paste."""

        self.write_index(
            settled=[
                "| Are the **acceptance   suites** gates or reports? "
                "| `docs/ACCEPTANCE_SUITES.md` §9 |",
            ]
        )
        self.assertRejected("also listed as settled")

    def test_the_same_question_asked_twice_while_open_is_rejected(self) -> None:
        """"Some of them the same question asked three times" is the condition
        that created the index; it must not reappear inside it."""

        self.write_index(
            p1=[
                "- Can a workspace span multiple windows? — handoff §11",
                "- Can a workspace span multiple windows? — `docs/COMMAND_PALETTE_CONTRACT.md`",
            ]
        )
        self.assertRejected("repeats the question at P1 item 1")

    def test_a_question_repeated_across_the_two_open_sections_is_rejected(self) -> None:
        self.write_index(
            p1=["- Are the acceptance suites gates or reports? — `docs/ACCEPTANCE_SUITES.md`"]
        )
        self.assertRejected("repeats the question at P0 row 1")


class SettlementTests(IndexTestCase):
    def test_a_settled_row_that_cites_nothing_is_rejected(self) -> None:
        """"Yes" is not a settlement. It leaves a reader holding the old
        question with nowhere to take it, which is the state the Settled table
        exists to end."""

        self.write_index(settled=["| Does the split-view model stay? | Yes, agreed in review |"])
        self.assertRejected("cites no document")

    def test_a_settled_row_with_an_empty_settling_cell_is_rejected(self) -> None:
        self.write_index(settled=["| Does the split-view model stay? |  |"])
        self.assertRejected("names no settling document")

    def test_a_settlement_that_is_not_a_document_is_accepted(self) -> None:
        """Two rows in the real index are settled by something that is not a
        document -- a registry schema, and an upstream symbol confirmed at the
        pinned tag -- and they are legitimately settled. Requiring a document
        path here would fail the repository on the day the guard landed.
        """

        self.write_index(
            settled=[
                "| Does the command registry separate operation from predicate? "
                "| Registry schema 2 — `implementation`, `predicate`, `unavailable_reasons` |",
            ]
        )
        self.assertEqual([], self.failures())


class StructureTests(IndexTestCase):
    def test_an_empty_p0_table_is_a_result_not_a_pass(self) -> None:
        """Zero blocking questions is a claim about the project. It must be
        made on purpose, not left to a guard that finds nothing to check."""

        self.write_index(p0=[])
        self.assertRejected("the P0 section has no entries")

    def test_an_empty_settled_table_is_reported_too(self) -> None:
        self.write_index(settled=[])
        self.assertRejected("the SETTLED section has no entries")

    def test_a_removed_section_is_rejected(self) -> None:
        """If the index is restructured, the rules above stop reading it and
        would otherwise pass by finding nothing."""

        self.write_index(drop="SETTLED")
        self.assertRejected("no SETTLED section")

    def test_a_reworded_section_heading_still_parses(self) -> None:
        """The subtitle after the priority is prose and will be reworded. Only
        the leading P0/P1/Settled is depended upon."""

        self.write_index()
        path = self.root / "docs/OPEN_DECISIONS.md"
        path.write_text(
            path.read_text(encoding="utf-8").replace(
                "## P1 — shapes the work, does not stop it", "## P1 (informational)"
            ),
            encoding="utf-8",
        )
        self.assertEqual([], self.failures())

    def test_a_row_that_does_not_match_its_header_is_rejected(self) -> None:
        """A missing column, or an unescaped pipe, moves every cell; the
        column-addressed rules would then read the wrong one."""

        self.write_index(p0=["| Is the roll cadence decided? | `docs/ACCEPTANCE_SUITES.md` |"])
        self.assertRejected("has 2 column(s), header declares 3")

    def test_a_row_with_no_question_is_rejected(self) -> None:
        self.write_index(p0=["|  | `docs/ACCEPTANCE_SUITES.md` §9 | Stage 1 exit |"])
        self.assertRejected("names no question")

    def test_a_missing_index_is_rejected(self) -> None:
        """The document is the whole subject of the guard; its absence must not
        read as nothing to check."""

        self.assertRejected("docs/OPEN_DECISIONS.md: missing")


class RepositoryTests(unittest.TestCase):
    def test_the_real_index_agrees_with_its_sources_today(self) -> None:
        counts, failures = index.validate(REPOSITORY_ROOT)
        self.assertEqual([], failures)
        # Named counts, so that a parse that silently stopped matching rows
        # fails here rather than passing quietly.
        self.assertGreater(counts["P0"], 0)
        self.assertGreater(counts["P1"], 0)
        self.assertGreater(counts["SETTLED"], 0)
        self.assertGreater(counts["references"], 0)


if __name__ == "__main__":
    unittest.main()
