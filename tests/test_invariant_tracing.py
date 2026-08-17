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
