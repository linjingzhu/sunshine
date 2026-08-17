"""Tests for the acceptance-index self-consistency guard.

`docs/ACCEPTANCE_SUITES.md` is a document whose whole content is claims about
other documents, and until this guard nothing checked one of them. The risk it
addresses is not that a verdict is generous -- no tool can judge that -- but
that a citation stops resolving and the row keeps reading as coverage.

Every rule is proved by injecting the violation into a temporary tree. A guard
that has only ever seen the real document is indistinguishable from one whose
patterns match nothing, and the real document currently satisfies four of the
five rules, so four of them would be untested by observation alone.

The fixture uses the `SPA-` family because `trace_invariants` must recognise it
as an identifier family; the document name and section numbers are invented.
"""

from pathlib import Path
import shutil
import sys
import tempfile
import unittest

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY_ROOT / "scripts"))

import verify_acceptance_claims as guard  # noqa: E402

CONTRACT = """# Sample contract

## 3. Acceptance criteria

| SPA-1 | the first thing |
| SPA-2 | the second thing |
| SPA-3 | the third thing |
"""

INDEX = """# Index

## 1. Method

### 1.1 Verdicts

| Verdict | Meaning |
|---|---|
| **Covered** | every named behaviour has a criterion |
| **Partial** | some named behaviour has one |
| **Uncovered** | nothing would fail |
| **Unrunnable** | a criterion exists but cannot run |

### 1.2 Checkability classes

| Class | Meaning |
|---|---|
| **O** | decidable against this repository today |
| **B** | needs a native build |
| **H** | needs a person |

## 2. Where the criteria live

| Document | Criteria | Identifier scheme |
|---|---|---|
| `docs/SAMPLE_CONTRACT.md` | {registry} | SPA- |

## 3. Stage 1 — handoff §5.7

| ID | §5.7 item | Established by | Class | Verdict |
|---|---|---|---|---|
| A1.1 | thing one | {evidence} | {klass} | {verdict} |
| A1.2 | thing two | **nothing** | H | **Uncovered** |

{tally}

## 8. What is checkable offline today

| Criterion | Why it is offline-decidable | Status |
|---|---|---|
| {criterion} | a source search | {status} |

## 9. Open questions for the product owner

| Priority | Question | Blocks |
|---|---|---|
| P1 | Settled by {question}. | Stage 1 exit |
"""

DEFAULTS = {
    "registry": "§3, 3 criteria SPA-1…SPA-3",
    "evidence": "`SAMPLE_CONTRACT` SPA-1–SPA-2",
    "klass": "B",
    "verdict": "**Covered**",
    "tally": "**Stage 1: 1 covered, 1 uncovered.**",
    "criterion": "`SAMPLE_CONTRACT` SPA-3",
    "status": "not implemented",
    "question": "`docs/SAMPLE_CONTRACT.md` §3",
}


class GuardTestCase(unittest.TestCase):
    def setUp(self) -> None:
        directory = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, directory, True)
        self.root = Path(directory)
        for name in ("docs", "tests", "scripts", "config"):
            (self.root / name).mkdir()
        self.write("docs/SAMPLE_CONTRACT.md", CONTRACT)

    def write(self, relative: str, text: str) -> None:
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    def failures(self, **overrides: str) -> list[str]:
        fields = dict(DEFAULTS, **overrides)
        self.write("docs/ACCEPTANCE_SUITES.md", INDEX.format(**fields))
        _, failures = guard.check(self.root)
        return failures

    def claim(self, identifier: str) -> None:
        """Make a check in the fixture tree claim an identifier.

        The `Enforces:` marker is assembled at runtime on purpose. Written
        literally it would sit in this file inside the real repository, where
        `trace_invariants` scans `tests/` for exactly that string, and this
        test would start registering claims against the real contracts.
        """

        marker = "Enforces" + ": " + identifier + "."
        self.write("scripts/verify_sample.py", f'"""{marker}"""\n')


class CleanFixtureTests(GuardTestCase):
    def test_a_consistent_index_passes(self) -> None:
        self.assertEqual([], self.failures())

    def test_the_report_names_what_was_checked(self) -> None:
        self.write("docs/ACCEPTANCE_SUITES.md", INDEX.format(**DEFAULTS))
        report, _ = guard.check(self.root)
        self.assertIn("rows", report[0])
        self.assertIn("claims", report[0])


class ArtifactTests(GuardTestCase):
    """Rule 1. A row that names a file promises the file is there."""

    def test_a_bare_contract_name_with_no_document_is_rejected(self) -> None:
        found = self.failures(evidence="`MISSING_CONTRACT` SPA-1")
        self.assertTrue(any("docs/MISSING_CONTRACT.md" in failure for failure in found), found)

    def test_a_written_out_path_that_does_not_exist_is_rejected(self) -> None:
        found = self.failures(question="`docs/decisions/0009-nothing.md`")
        self.assertTrue(
            any("0009-nothing.md" in failure and "does not exist" in failure for failure in found),
            found,
        )

    def test_a_script_a_row_names_must_exist(self) -> None:
        found = self.failures(criterion="`SAMPLE_CONTRACT` SPA-3 in `scripts/absent.py`")
        self.assertTrue(any("scripts/absent.py" in failure for failure in found), found)

    def test_a_section_reference_into_a_named_document_must_resolve(self) -> None:
        found = self.failures(evidence="`SAMPLE_CONTRACT` §9 and SPA-1")
        self.assertTrue(any("§9" in failure and "not a section" in failure for failure in found), found)

    def test_a_section_reference_that_does_not_follow_a_document_is_left_alone(self) -> None:
        """"`X` answers §9.2 with deltas" is a handoff reference, not one into X.

        Adjacency is the only thing separating the two readings, so a
        non-adjacent §-number is deliberately not checked -- guessing would
        make the rule fire on correct prose, which is how rules get deleted.
        """

        self.assertEqual([], self.failures(evidence="`SAMPLE_CONTRACT` SPA-1, which answers §92"))


class IdentifierTests(GuardTestCase):
    """Rule 2. A cited criterion must be declared by the document cited for it."""

    def test_an_identifier_the_named_document_does_not_declare_is_rejected(self) -> None:
        found = self.failures(evidence="`SAMPLE_CONTRACT` SPA-1, SPA-9")
        self.assertTrue(
            any("SPA-9" in failure and "does not declare" in failure for failure in found), found
        )

    def test_a_range_is_checked_through_its_interior(self) -> None:
        """A range is a claim about every member, and the members are where a
        renumbering shows up first: endpoints tend to be edited, middles do not."""

        found = self.failures(evidence="`SAMPLE_CONTRACT` SPA-1–SPA-5")
        self.assertTrue(any("SPA-4" in failure for failure in found), found)
        self.assertTrue(any("SPA-5" in failure for failure in found), found)

    def test_an_identifier_with_no_document_before_it_is_rejected(self) -> None:
        found = self.failures(evidence="SPA-1 and SPA-2, from somewhere")
        self.assertTrue(
            any("no document named" in failure for failure in found), found
        )

    def test_the_registry_table_is_held_to_the_same_rule(self) -> None:
        found = self.failures(registry="§3, 4 criteria SPA-1…SPA-4")
        self.assertTrue(any("SPA-4" in failure for failure in found), found)

    def test_an_identifier_attaches_to_the_nearest_document_before_it(self) -> None:
        """Two documents in one cell is the ordinary case, not an edge case."""

        self.write("docs/OTHER_CONTRACT.md", "# Other\n\n| SPA-7 | a thing |\n")
        found = self.failures(evidence="`SAMPLE_CONTRACT` SPA-1; `OTHER_CONTRACT` SPA-7")
        self.assertEqual([], found)
        found = self.failures(evidence="`OTHER_CONTRACT` SPA-1; `SAMPLE_CONTRACT` SPA-7")
        self.assertEqual(2, len(found), found)


class VerdictTests(GuardTestCase):
    """Rule 3 and the verdict vocabulary."""

    def test_covered_naming_nothing_is_rejected(self) -> None:
        found = self.failures(evidence="**nothing**", tally="**Stage 1: 1 covered, 1 uncovered.**")
        self.assertTrue(
            any("Covered but the row names no artifact" in failure for failure in found), found
        )

    def test_covered_naming_only_a_document_that_is_gone_is_rejected(self) -> None:
        """The failure this guard exists for: the citation is well-formed, the
        verdict reads as coverage, and the document it rests on is not there."""

        found = self.failures(evidence="`MISSING_CONTRACT` SPA-1")
        self.assertTrue(any("does not exist" in failure for failure in found), found)
        self.assertTrue(
            any("Covered but the row names no artifact" in failure for failure in found), found
        )

    def test_an_uncovered_row_may_name_nothing(self) -> None:
        """Only Covered carries the promise; the other three verdicts are
        statements that something is missing and must not be pushed to cite."""

        self.assertEqual(
            [],
            self.failures(
                evidence="**nothing**",
                verdict="**Uncovered**",
                tally="**Stage 1: 2 uncovered.**",
            ),
        )

    def test_a_verdict_outside_the_declared_set_is_rejected(self) -> None:
        found = self.failures(verdict="**Mostly**", tally="**Stage 1: 1 mostly, 1 uncovered.**")
        self.assertTrue(any("'Mostly' is not one section 1.1 declares" in failure for failure in found), found)


class ClassTests(GuardTestCase):
    """Rule 4a. O, B and H are declared in section 1.2 and nowhere else."""

    def test_a_class_letter_outside_the_declared_set_is_rejected(self) -> None:
        found = self.failures(klass="B + X")
        self.assertTrue(any("class 'X'" in failure for failure in found), found)

    def test_a_compound_class_of_declared_letters_is_accepted(self) -> None:
        self.assertEqual([], self.failures(klass="O + B + H"))


class TallyTests(GuardTestCase):
    """Rule 4b. The count under a table is a claim about the table."""

    def test_a_tally_that_disagrees_with_the_rows_is_rejected(self) -> None:
        found = self.failures(tally="**Stage 1: 2 covered.**")
        self.assertTrue(any("tally" in failure for failure in found), found)

    def test_a_stated_zero_is_not_a_disagreement(self) -> None:
        """"0 covered" is how the real document says a stage covers nothing."""

        self.assertEqual([], self.failures(tally="**Stage 1: 0 partial, 1 covered, 1 uncovered.**"))

    def test_a_missing_tally_is_rejected(self) -> None:
        found = self.failures(tally="Stage 1 has some rows.")
        self.assertTrue(any("tally lines" in failure for failure in found), found)


class OfflineStatusTests(GuardTestCase):
    """Rule 5. Section 8 grades each criterion as implemented or not, and
    `trace_invariants` already knows which checks claim which identifier."""

    def test_not_implemented_while_a_check_claims_it_is_rejected(self) -> None:
        self.claim("SPA-3")
        found = self.failures(status="not implemented")
        self.assertTrue(
            any("SPA-3" in failure and "verify_sample.py" in failure for failure in found), found
        )

    def test_implemented_while_nothing_claims_it_is_rejected(self) -> None:
        found = self.failures(status="**implemented and checked** — by the model")
        self.assertTrue(
            any("no check claims SPA-3" in failure for failure in found), found
        )

    def test_implemented_with_a_claim_passes(self) -> None:
        self.claim("SPA-3")
        self.assertEqual([], self.failures(status="**implemented and checked** — by the model"))

    def test_an_unreadable_status_is_rejected(self) -> None:
        """Neither grading applies, so the rule would silently stop looking.
        Reporting it keeps a reworded cell a decision rather than an escape."""

        found = self.failures(status="mostly there")
        self.assertTrue(any("is neither" in failure for failure in found), found)

    def test_a_row_naming_no_identifier_is_graded_but_not_traced(self) -> None:
        """The real section 8 has one such row -- a §15 storage decision with
        no identifier to claim -- and it must not be forced to have one."""

        self.assertEqual(
            [],
            self.failures(
                criterion="`SAMPLE_CONTRACT` §3 storage decision",
                status="**implemented and checked** — in the model",
            ),
        )


class NotAnIdentifierTests(GuardTestCase):
    """Prose that looks like a citation and is not.

    Each of these appears in the real document. A guard that read any of them
    as a claim would fail on correct text, which costs more than the rule
    earns.
    """

    def test_priority_labels_ordinals_and_row_ids_are_prose(self) -> None:
        self.assertEqual(
            [],
            self.failures(
                evidence="`SAMPLE_CONTRACT` SPA-1; the P1 decision, invariants 1–8, and A1.4"
            ),
        )

    def test_a_backticked_identifier_is_not_read_as_a_missing_document(self) -> None:
        """The document writes "`PB-1`…`PB-6` rather than `P1`…`P6`" in a row."""

        self.assertEqual(
            [], self.failures(evidence="`SAMPLE_CONTRACT` SPA-1, written `SPA-1` not `P1`")
        )

    def test_a_backticked_identifier_is_still_held_to_its_document(self) -> None:
        found = self.failures(evidence="`SAMPLE_CONTRACT` cites `SPA-9`")
        self.assertTrue(any("SPA-9" in failure for failure in found), found)


class RepositoryStateTests(unittest.TestCase):
    """What the guard says about the repository as it stands.

    Rules 1 to 4 hold: every artifact the index names exists, every identifier
    it cites is declared by the document it names, every Covered row rests on
    something, and the vocabularies and tallies agree with the tables.

    Rule 5 does not, in seven rows. Section 8 grades ten offline-decidable
    criteria as "not implemented" and the paragraph directly beneath the table
    says "All ten are now implemented"; seven of the ten are in fact claimed by
    a check today, so the table is the half that is stale. This test records
    that finding rather than tolerating it -- correcting the document is what
    changes this list, and the check that reports the drift stays strict in the
    meantime.
    """

    # The seven rows this guard first reported -- §8 rows 1, 4, 5, 6, 7, 8 and
    # 10 -- were corrected in the change that landed the guard, so the expected
    # set is now empty. It is kept as an explicit empty set rather than deleted
    # because the assertion is the point: the Status column and
    # `scripts/trace_invariants.py` must agree, and any future disagreement in
    # either direction has to be fixed rather than added here.
    STALE_STATUS_ROWS: set[str] = set()

    def setUp(self) -> None:
        self.report, self.failures = guard.check(REPOSITORY_ROOT)

    def test_every_citation_and_verdict_in_the_index_resolves(self) -> None:
        """Rules 1 to 4, asserted against the real document."""

        other = [
            failure for failure in self.failures if 'status says' not in failure
        ]
        self.assertEqual([], other, "\n".join(self.report))

    def test_the_offline_status_column_agrees_with_what_is_enforced(self) -> None:
        """The summary above the table said "all ten are now implemented".

        Seven rows below it said "not implemented" about invariants that were
        enforced, and two rows the summary counted -- TLA-2 and ATA-10 -- are
        claimed by nothing. The document disagreed with itself in both
        directions at once, and nothing noticed until the two halves were
        compared mechanically.
        """

        reported = {failure.split(": status says")[0] for failure in self.failures}
        self.assertEqual(self.STALE_STATUS_ROWS, reported)

    def test_the_guard_reports_a_row_and_claim_count(self) -> None:
        self.assertRegex(self.report[0], r"Checked \d+ rows .* and \d+ claims")


class IndexStructureTests(unittest.TestCase):
    """The structural assumptions every rule above is derived from.

    Each rule reads the document's own shape -- the legend tables, the column
    order, the tally lines. If that shape changes, the rules do not fail, they
    silently check less, so the shape is asserted here.
    """

    def setUp(self) -> None:
        self.tables = guard.parse_tables(
            (REPOSITORY_ROOT / guard.INDEX).read_text(encoding="utf-8")
        )

    def test_the_two_legend_tables_declare_the_vocabularies(self) -> None:
        legends = {
            table.header[0]: guard.legend_terms(table)
            for table in self.tables
            if len(table.header) == 2 and table.header[1] == "Meaning"
        }
        self.assertEqual(["Covered", "Partial", "Uncovered", "Unrunnable"], legends["Verdict"])
        self.assertEqual(["O", "B", "H"], legends["Class"])

    def test_every_claim_table_puts_the_evidence_before_the_grading(self) -> None:
        claim_tables = [
            table for table in self.tables if "Verdict" in table.header and len(table.header) > 2
        ]
        self.assertEqual(4, len(claim_tables))
        for table in claim_tables:
            with self.subTest(section=table.section):
                self.assertIn(
                    table.header[guard.evidence_column(table.header)],
                    ("Established by", "Mechanism established by", "Owning criterion"),
                )

    def test_there_is_one_tally_line_for_each_stage_table(self) -> None:
        stage_tables = [
            table
            for table in self.tables
            if "Verdict" in table.header and len(table.header) > 2 and table.header[0] == "ID"
        ]
        lines = (REPOSITORY_ROOT / guard.INDEX).read_text(encoding="utf-8").splitlines()
        self.assertEqual(3, len(stage_tables))
        self.assertEqual(3, len([line for line in lines if guard.TALLY.match(line)]))


if __name__ == "__main__":
    unittest.main()
