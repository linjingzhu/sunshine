"""Tests for invariant coverage tracing.

The gap this measures is real and mostly unfixable offline: the contracts
declare invariants about what a running browser does, and no unit test can
establish those. What it does prevent is enforcement disappearing quietly, and
a test claiming an invariant identifier that no contract declares -- which
happens when a contract is renumbered and its tests are not.
"""

from pathlib import Path
import shutil
import sys
import tempfile
import unittest

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY_ROOT / "scripts"))

import trace_invariants as tracer  # noqa: E402


class InvariantTracingTests(unittest.TestCase):
    def setUp(self) -> None:
        directory = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, directory, True)
        self.root = Path(directory)
        (self.root / "docs").mkdir()
        (self.root / "tests").mkdir()
        (self.root / "scripts").mkdir()
        (self.root / "config").mkdir()

    def write(self, relative: str, text: str) -> None:
        (self.root / relative).write_text(text, encoding="utf-8")

    def test_the_repository_is_consistent_today(self) -> None:
        report, failures = tracer.check(REPOSITORY_ROOT)
        self.assertEqual([], failures, "\n".join(report))

    def test_declared_invariants_are_found(self) -> None:
        self.write("docs/C.md", "| OS-3 | The installer registers nothing. |\n")
        self.assertIn("OS-3", tracer.declared(self.root))

    def test_ordinary_prose_is_not_read_as_an_invariant(self) -> None:
        """`P1`, a version, and a Chromium symbol are not invariants."""

        self.write("docs/C.md", "P1 blocks this. Pinned at 152.0.7977.42. See H264 support.\n")
        self.assertEqual({}, tracer.declared(self.root))

    def test_a_claim_is_recognised(self) -> None:
        self.write("docs/C.md", "| AT-7 | Do not repurpose the visibility bit. |\n")
        self.write("tests/test_x.py", '"""Enforces: AT-7."""\n')
        report, failures = tracer.check(self.root)
        self.assertEqual([], failures)
        self.assertIn("Claimed by a test or tool: 1", report)

    def test_claiming_an_invariant_no_contract_declares_fails(self) -> None:
        """The renumbering guard.

        A contract's identifiers change and its tests keep the old ones. The
        test still passes -- it never checked the identifier -- so nothing
        notices that it now claims a rule that does not exist.
        """

        self.write("docs/C.md", "| AT-7 | Do not repurpose the visibility bit. |\n")
        self.write("tests/test_x.py", '"""Enforces: AT-9."""\n')
        _, failures = tracer.check(self.root)
        self.assertTrue(any("AT-9" in failure and "no contract declares it" in failure for failure in failures))

    def test_losing_an_enforced_invariant_fails(self) -> None:
        """Ratcheting down has to be a decision, not an accident."""

        self.write("docs/C.md", "| SC-1 | A verdict may not relax a Chromium decision. |\n")
        self.write("config/invariant_coverage.txt", "SC-1\n")
        _, failures = tracer.check(self.root)
        self.assertTrue(any("SC-1" in failure and "no longer is" in failure for failure in failures))

    def test_gaining_coverage_is_free(self) -> None:
        self.write("docs/C.md", "| SC-1 | A verdict may not relax a Chromium decision. |\n")
        self.write("tests/test_x.py", '"""Enforces: SC-1."""\n')
        self.write("config/invariant_coverage.txt", "")
        report, failures = tracer.check(self.root)
        self.assertEqual([], failures)
        self.assertTrue(any("Newly enforced" in line for line in report))

    def test_the_baseline_records_why_it_is_empty(self) -> None:
        """An empty file reads as an oversight unless it says otherwise, and
        this one is a measurement: almost nothing here is checkable offline."""

        text = (REPOSITORY_ROOT / "config/invariant_coverage.txt").read_text(encoding="utf-8")
        self.assertIn("running browser", text)
        self.assertIn("Enforces:", text)


if __name__ == "__main__":
    unittest.main()


class FourLetterFamilyTests(unittest.TestCase):
    """SECA-n could not be parsed at all, and nothing reported the gap.

    The pattern was `[A-Z]{1,3}`, so a four-letter family matched nothing. Two
    acceptance criteria read as enforced in their contract and as unclaimed by
    the tracer, and because an unparsed token is simply absent rather than
    rejected, the disagreement was invisible from both ends.
    """

    def test_a_four_letter_family_identifier_is_parsed(self) -> None:
        self.assertEqual(["SECA-11"], [m.group(1) for m in tracer.INVARIANT.finditer("see SECA-11 here")])

    def test_the_shorter_forms_still_parse(self) -> None:
        text = "SEC-13, PO-A1, AT-9, SPA-9, S12 and BH-2"
        found = [m.group(1) for m in tracer.INVARIANT.finditer(text)]
        for token in ("SEC-13", "PO-A1", "AT-9", "SPA-9", "S12", "BH-2"):
            with self.subTest(token=token):
                self.assertIn(token, found)

    def test_every_declared_family_is_parseable_by_the_pattern(self) -> None:
        """A family nobody can parse is a family nobody enforces."""

        for family in tracer.FAMILIES:
            with self.subTest(family=family):
                sample = f"{family}-1"
                self.assertEqual(
                    [sample],
                    [m.group(1) for m in tracer.INVARIANT.finditer(sample)],
                    f"{family} is in FAMILIES but the pattern cannot parse {sample}",
                )
