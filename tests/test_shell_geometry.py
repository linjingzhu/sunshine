"""Tests for the check that keeps the shell's measurements and its contract equal.

Two copies of eighteen numbers drift, and the drift is quiet: a width changed
in one place still renders a shell, just not the one anybody agreed to. So the
tests that matter are the ones proving the guard notices — a guard that only
ever passes on the committed patch is indistinguishable from one that always
passes.
"""

from pathlib import Path
import shutil
import sys
import tempfile
import unittest

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY_ROOT / "scripts"))

import verify_shell_geometry as guard  # noqa: E402


class ContractTableTests(unittest.TestCase):
    def test_the_contract_states_the_regions(self) -> None:
        table = guard.contract_geometry()
        for name in (
            "BAR_HEIGHT", "DOCK_ICONS", "DOCK_EXPANDED", "TABS_DEFAULT",
            "TABS_MIN", "TABS_MAX", "BODY_MIN", "PANEL_DEFAULT", "PANEL_MIN",
            "PANEL_MAX", "HEADER_HEIGHT", "SPLITTER_VISUAL", "SPLITTER_HIT",
        ):
            with self.subTest(name=name):
                self.assertIn(name, table)

    def test_the_source_drawings_numbers_survived_transcription(self) -> None:
        """Read off the owner's layout rules. If a value here is wrong the
        shell is wrong, and no other check in the repository would say so."""

        table = guard.contract_geometry()
        self.assertEqual(32, table["BAR_HEIGHT"])
        self.assertEqual(56, table["DOCK_ICONS"])
        self.assertEqual(224, table["DOCK_EXPANDED"])
        self.assertEqual(232, table["TABS_DEFAULT"])
        self.assertEqual(180, table["TABS_MIN"])
        self.assertEqual(360, table["TABS_MAX"])
        self.assertEqual(480, table["BODY_MIN"])
        self.assertEqual(320, table["PANEL_DEFAULT"])
        self.assertEqual(280, table["PANEL_MIN"])
        self.assertEqual(520, table["PANEL_MAX"])
        self.assertEqual(40, table["HEADER_HEIGHT"])
        self.assertEqual(4, table["SPLITTER_VISUAL"])
        self.assertEqual(8, table["SPLITTER_HIT"])
        self.assertEqual(1440, table["DENSE_MIN_WIDTH"])

    def test_the_ranges_are_coherent(self) -> None:
        """A default outside its own bounds is a defect the numbers can show."""

        table = guard.contract_geometry()
        self.assertLessEqual(table["TABS_MIN"], table["TABS_DEFAULT"])
        self.assertLessEqual(table["TABS_DEFAULT"], table["TABS_MAX"])
        self.assertLessEqual(table["PANEL_MIN"], table["PANEL_DEFAULT"])
        self.assertLessEqual(table["PANEL_DEFAULT"], table["PANEL_MAX"])
        self.assertLess(table["DOCK_ICONS"], table["DOCK_EXPANDED"])
        self.assertLess(table["SPLITTER_VISUAL"], table["SPLITTER_HIT"])

    def test_the_densest_arrangement_fits_the_width_it_recommends(self) -> None:
        """State 06 at its minimums must fit in DENSE_MIN_WIDTH, or the
        contract recommends an arrangement it also forbids."""

        table = guard.contract_geometry()
        densest = (
            table["DOCK_EXPANDED"] + table["TABS_MIN"] + table["BODY_MIN"]
            + table["PANEL_MIN"] + 2 * table["SPLITTER_HIT"]
        )
        self.assertLessEqual(densest, table["DENSE_MIN_WIDTH"])


class PatchTests(unittest.TestCase):
    def setUp(self) -> None:
        directory = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, directory, True)
        self.root = Path(directory)
        (self.root / "docs").mkdir()
        shutil.copy(
            REPOSITORY_ROOT / guard.CONTRACT, self.root / guard.CONTRACT
        )
        patches = self.root / "downstream/patches"
        patches.mkdir(parents=True)
        self.patch = patches / guard.PATCH_NAME
        shutil.copy(
            REPOSITORY_ROOT / "downstream/patches" / guard.PATCH_NAME, self.patch
        )

    def rewrite(self, old: str, new: str) -> None:
        text = self.patch.read_text(encoding="utf-8")
        self.assertIn(old, text)
        self.patch.write_text(text.replace(old, new, 1), encoding="utf-8")

    def test_the_repository_agrees_with_itself(self) -> None:
        self.assertEqual([], guard.check())
        self.assertEqual([], guard.check(self.root))

    def test_a_width_changed_only_in_the_code_fails(self) -> None:
        """The failure this guard exists for."""

        self.rewrite("+export const TABS_DEFAULT = 232;",
                     "+export const TABS_DEFAULT = 260;")
        failures = guard.check(self.root)
        self.assertTrue(any("TABS_DEFAULT" in f for f in failures), failures)

    def test_a_measurement_removed_from_the_code_fails(self) -> None:
        self.rewrite("+export const PANEL_MAX = 520;\n", "")
        failures = guard.check(self.root)
        self.assertTrue(any("PANEL_MAX" in f for f in failures), failures)

    def test_a_measurement_no_contract_states_fails(self) -> None:
        """The other direction: a number invented in the code."""

        self.rewrite("+export const BAR_HEIGHT = 32;",
                     "+export const BAR_HEIGHT = 32;\n+export const GUTTER = 12;")
        failures = guard.check(self.root)
        self.assertTrue(any("GUTTER" in f for f in failures), failures)

    def test_a_layout_length_written_into_the_stylesheet_fails(self) -> None:
        """Every width reaches CSS as a custom property, so a literal there is
        a second place the geometry lives."""

        self.rewrite("+#page {", "+#page {\n+  min-inline-size: 900px;")
        failures = guard.check(self.root)
        self.assertTrue(any("900px" in f for f in failures), failures)

    def test_a_hairline_is_not_a_layout_length(self) -> None:
        """1px borders and the 2px focus ring are the design system's, and it
        has its own guard. The threshold is the contract's own smallest value,
        so this cannot drift into an opinion."""

        self.rewrite("+#page {", "+#page {\n+  border-top: 1px solid red;")
        self.assertEqual([], [f for f in guard.check(self.root) if "1px" in f])

    def test_a_missing_patch_is_reported(self) -> None:
        self.patch.unlink()
        self.assertNotEqual([], guard.check(self.root))

    def test_a_patch_that_stops_creating_the_geometry_is_reported(self) -> None:
        self.patch.write_text("diff --git a/x b/x\n--- a/x\n+++ b/x\n", encoding="utf-8")
        self.assertNotEqual([], guard.check(self.root))

    def test_a_contract_with_no_table_is_reported(self) -> None:
        (self.root / guard.CONTRACT).write_text("# no table here\n", encoding="utf-8")
        with self.assertRaises(guard.GeometryError):
            guard.check(self.root)


if __name__ == "__main__":
    unittest.main()
