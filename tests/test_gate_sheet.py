"""Tests for the Korean gate sheet generator.

`scripts/build_gate_sheet.py` is not a guard, so nothing ran it, so nothing
noticed when it stopped working. It refused to generate anything from the day
RV-39 was added until RV-55: fifteen gates with no Korean, block letters the
run sheet used and it did not know, and a block-row parser that read
"**RV-39 first**" as a gate id. The owner went on opening the committed sheet,
which was three releases and nine gates out of date and stamped with the wrong
build number.

So the generator is now run by CI and these tests are the reason it can be. The
sheet is an instrument for a person doing a long manual session; an instrument
that quietly stops agreeing with what it measures is worse than none.
"""

from pathlib import Path
import sys
import unittest

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY_ROOT / "scripts"))

import build_gate_sheet as sheet  # noqa: E402


class TranslationCoverage(unittest.TestCase):
    def setUp(self) -> None:
        self.gates = sheet.gates(REPOSITORY_ROOT)

    def test_every_gate_the_document_defines_has_korean(self) -> None:
        self.assertEqual([], sorted(set(self.gates) - set(sheet.KOREAN)))

    def test_no_korean_survives_a_gate_that_was_removed(self) -> None:
        self.assertEqual([], sorted(set(sheet.KOREAN) - set(self.gates)))

    def test_every_runnable_gate_has_a_walkthrough(self) -> None:
        """A person cannot start from the contract's wording alone.

        The contract says what to observe; the walkthrough says which keys to
        press to get there. A gate with only the former reads as an instruction
        to someone who already knows the answer.
        """

        runnable = set(self.gates) - set(sheet.BLOCKED) - set(sheet.DONE) - set(sheet.VERIFIED)
        self.assertEqual([], sorted(runnable - set(sheet.HOWTO)))

    def test_a_walkthrough_has_steps_and_both_outcomes(self) -> None:
        for gate, entry in sheet.HOWTO.items():
            with self.subTest(gate=gate):
                steps, passed, failed = entry
                self.assertTrue(steps)
                self.assertTrue(all(step.strip() for step in steps))
                self.assertTrue(passed.strip())
                self.assertTrue(failed.strip())


class RunSheetAgreement(unittest.TestCase):
    def test_every_block_letter_has_a_korean_title(self) -> None:
        letters = [letter for letter, _, _, _ in sheet.blocks(REPOSITORY_ROOT)]
        self.assertEqual([], sorted(set(letters) - set(sheet.BLOCK_TITLES)))

    def test_block_rows_carry_gate_ids_and_not_the_prose_around_them(self) -> None:
        """The run sheet writes for a person: "**RV-39 first**, then RV-41".

        Splitting that cell on commas produced "**RV-39 first**" and
        "then RV-41" as gate ids, and every one of them failed the lookup. The
        order in the cell is the order that is kept; only the decoration goes.
        """

        found = dict((letter, ids) for letter, ids, _, _ in sheet.blocks(REPOSITORY_ROOT))
        self.assertIn("F", found)
        self.assertEqual("RV-39", found["F"][0])
        self.assertEqual("RV-43", found["F"][-1])
        for ids in found.values():
            for gate in ids:
                self.assertRegex(gate, r"^RVV?-\d+$")

    def test_every_scheduled_gate_exists(self) -> None:
        defined = sheet.gates(REPOSITORY_ROOT)
        for letter, ids, _, _ in sheet.blocks(REPOSITORY_ROOT):
            for gate in ids:
                with self.subTest(block=letter, gate=gate):
                    self.assertIn(gate, defined)


class BuildStamp(unittest.TestCase):
    def test_the_stamp_names_a_build(self) -> None:
        sheet.check_stamp_is_current(REPOSITORY_ROOT)

    def test_a_stamp_older_than_the_document_is_refused(self) -> None:
        """It said #47 while #56 was the shipped build.

        Every exported result carries the stamp, so a stale one attributes a
        person's evening to a binary they did not run.
        """

        original = sheet.BUILD
        sheet.BUILD = "#47 (0ba6134)"
        try:
            with self.assertRaises(SystemExit) as caught:
                sheet.check_stamp_is_current(REPOSITORY_ROOT)
        finally:
            sheet.BUILD = original
        self.assertIn("#47", str(caught.exception))
        self.assertIn("wrong binary", str(caught.exception))


class CommittedSheet(unittest.TestCase):
    def test_the_committed_sheet_is_what_the_generator_produces(self) -> None:
        """Regenerating is not optional, because the sheet is committed.

        CI checks the same thing with `git diff --exit-code`; this says it
        again here so that a person editing the generator finds out in the same
        second rather than on a push.
        """

        committed = (REPOSITORY_ROOT / "gate-sheet.html").read_text(encoding="utf-8")
        self.assertEqual(committed, sheet.build())


if __name__ == "__main__":
    unittest.main()
