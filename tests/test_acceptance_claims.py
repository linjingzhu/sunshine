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
import re
import shutil
import sys
import tempfile
import unittest

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY_ROOT / "scripts"))

import trace_invariants as tracer  # noqa: E402
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


class SubLetteredIdentifierTests(GuardTestCase):
    """The defect this module's own copy of the identifier shape caused.

    `PERFORMANCE_BUDGET` splits one budget into PB-2a, PB-2b and PB-2c. The
    tracer's pattern could not parse those at all, so they vanished; this
    module's copy was *unanchored*, so instead of vanishing they truncated --
    `PB-2a` was read as `PB-2`, an identifier that also exists, and the row
    passed on the strength of a citation it does not make.

    Truncation is the worse of the two failures. A vanished token moves a
    count and can be noticed; a truncated one substitutes a different real
    answer and reports success. Every case here would pass under the old copy
    while checking the wrong thing, which is why they are written against a
    fixture that declares one form and not the other.
    """

    def declare(self, *extra: str) -> None:
        """Rewrite the fixture contract to declare exactly these criteria."""

        rows = "\n".join(
            f"| {identifier} | a rule |" for identifier in ("SPA-1", "SPA-2", "SPA-3") + extra
        )
        self.write(
            "docs/SAMPLE_CONTRACT.md",
            f"# Sample contract\n\n## 3. Acceptance criteria\n\n{rows}\n",
        )

    def test_a_sub_lettered_citation_is_not_truncated_to_a_declared_one(self) -> None:
        """The regression itself: the document declares PB-2, the row cites
        PB-2a, and the guard must object rather than quietly read PB-2."""

        self.declare("PB-2")
        found = self.failures(evidence="`SAMPLE_CONTRACT` PB-2a")
        self.assertTrue(any("cites PB-2a," in failure for failure in found), found)
        self.assertFalse(any("cites PB-2," in failure for failure in found), found)

    def test_a_declared_sub_lettered_citation_passes(self) -> None:
        self.declare("PB-2a")
        self.assertEqual([], self.failures(evidence="`SAMPLE_CONTRACT` PB-2a"))

    def test_the_base_identifier_is_not_accepted_for_the_sub_lettered_one(self) -> None:
        """The mirror image, and the reason the first test is not enough on its
        own: PB-2 and PB-2a are different rules, so declaring one must not
        discharge a citation of the other in either direction."""

        self.declare("PB-2a")
        found = self.failures(evidence="`SAMPLE_CONTRACT` PB-2")
        self.assertTrue(any("cites PB-2," in failure for failure in found), found)

    def test_a_range_across_a_letter_is_not_expanded_but_both_ends_are_checked(self) -> None:
        """`PB-2a-PB-2c` spans an axis the document has never counted over.

        Refusing to expand it is checking less, which is safe; inventing PB-2b
        as a member would be checking something the row never claimed.
        """

        self.declare("PB-2a")
        found = self.failures(evidence="`SAMPLE_CONTRACT` PB-2a–PB-2c")
        self.assertTrue(any("cites PB-2c," in failure for failure in found), found)
        self.assertFalse(any("PB-2b" in failure for failure in found), found)

    def test_a_range_whose_second_end_drops_its_family_is_not_expanded(self) -> None:
        """`SPA-1-9` is not a form the document uses -- every range it writes
        repeats the prefix. Refusing the shorthand is stricter than the copy
        this replaces, which guessed the missing family; the lone endpoint is
        still checked."""

        self.declare()
        self.assertEqual([], self.failures(evidence="`SAMPLE_CONTRACT` SPA-1–9"))
        found = self.failures(evidence="`SAMPLE_CONTRACT` SPA-1–SPA-9")
        self.assertTrue(any("cites SPA-9," in failure for failure in found), found)


class DerivedShapeTests(unittest.TestCase):
    """The identifier shape has one home, and it is not this module.

    Two kinds of assertion are made here, and they are not interchangeable.
    The identity and containment tests assert the *mechanism* -- that the
    pattern is spliced in from `trace_invariants` rather than written out --
    and they are the ones that stop the copy coming back, because a restated
    literal fails them the moment the original is widened again.

    The corpus test asserts *behaviour* over shapes that are actually in use.
    On its own it would be the weaker choice: a fresh hand-copy of today's
    shape passes it, and would go on passing until the next widening, which is
    precisely the history that produced this file. It is kept as the backstop
    for a copy that is merely close rather than identical.
    """

    def test_the_identifier_shape_is_the_tracers_own_pattern(self) -> None:
        self.assertEqual(tracer.INVARIANT.pattern, guard.IDENTIFIER)

    def test_both_users_of_the_shape_embed_it_rather_than_restating_it(self) -> None:
        self.assertIn(guard.IDENTIFIER, guard.TOKEN.pattern)
        self.assertIn(guard.IDENTIFIER, guard.RANGE.pattern)

    def test_the_shape_contributes_exactly_one_capture_group(self) -> None:
        """`TOKEN` reads the identifier out of group 2 and `RANGE` reads its
        endpoints out of groups 1 and 2. Both numberings assume the spliced
        pattern brings exactly one group with it, so that assumption is
        asserted rather than left to hold by luck."""

        self.assertEqual(1, re.compile(guard.IDENTIFIER).groups)
        self.assertEqual(2, guard.TOKEN.groups)
        self.assertEqual(2, guard.RANGE.groups)

    def test_the_two_modules_read_the_same_token_out_of_every_shape_in_use(self) -> None:
        for token in ("PB-2a", "PB-2c", "SECA-11", "PO-A15", "S12", "D4", "OMA-20", "BH-A7"):
            with self.subTest(token=token):
                match = guard.TOKEN.search(token)
                self.assertIsNotNone(match, token)
                self.assertEqual(token, match.group(2))
                self.assertEqual({token}, tracer._identifiers(token))

    def test_every_declared_family_round_trips(self) -> None:
        """Generated from the tracer's own family list, so a family added there
        is covered here without this file being edited."""

        for family in tracer.FAMILIES:
            with self.subTest(family=family):
                token = f"{family}-1"
                match = guard.TOKEN.search(token)
                self.assertIsNotNone(match, token)
                self.assertEqual(token, match.group(2))


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

    All five rules hold today: every artifact the index names exists, every
    identifier it cites is declared by the document it names, every Covered row
    rests on something, the vocabularies and tallies agree with the tables, and
    the section 8 Status column agrees with what `scripts/trace_invariants.py`
    records as enforced.

    That last one was false in seven rows when this guard was written, and the
    document was corrected rather than the rule relaxed. The empty expected set
    below is what that correction looks like from here.
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

    def test_every_sub_lettered_citation_in_the_index_is_read_whole(self) -> None:
        """The fixture cases proved on real data.

        Written as a sweep rather than against row A2.3 by name, so that it
        keeps testing the property while citations move around it. Today the
        index carries exactly one sub-lettered citation -- `PERFORMANCE_BUDGET`
        PB-2a -- which the old copy of the pattern read as PB-2, a different
        budget that happens to be declared in the same document. The row passed
        on a citation it does not make.
        """

        text = (REPOSITORY_ROOT / guard.INDEX).read_text(encoding="utf-8")
        rows = "\n".join(line for line in text.splitlines() if line.startswith("|"))
        cited = {
            token
            for token in tracer.CANDIDATE.findall(rows)
            if token[-1].islower() and tracer._family(token) in tracer.FAMILIES
        }
        parsed = {
            claim.value
            for table in guard.parse_tables(text)
            for cells in table.rows
            for cell in cells
            for claim in guard.claims(cell)
            if claim.kind == "identifier"
        }
        self.assertTrue(cited, "no sub-lettered citation left in the index to test")
        for token in sorted(cited):
            with self.subTest(token=token):
                self.assertIn(token, parsed)


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
