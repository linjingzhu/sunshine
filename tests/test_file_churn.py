"""Tests for the upstream-file churn measurement.

The fetching is network and is not tested here. What is tested is everything
that turns fetched bytes into a verdict, because that is where a measurement
becomes a claim -- and a wrong claim in a table nobody can re-run is exactly the
failure `docs/INSTALLER_CHOICE_PLAN.md` §6 already carried.
"""

from pathlib import Path
import sys
import unittest

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY_ROOT / "scripts"))

import measure_file_churn as churn  # noqa: E402


class ChangedLineTests(unittest.TestCase):
    def test_identical_text_has_no_changed_lines(self) -> None:
        self.assertEqual(0, churn.changed_lines("a\nb\n", "a\nb\n"))

    def test_one_replaced_line_counts_as_two(self) -> None:
        """One removal and one addition, which is what a diff shows."""

        self.assertEqual(2, churn.changed_lines("a\nb\n", "a\nc\n"))

    def test_an_added_line_counts_once(self) -> None:
        self.assertEqual(1, churn.changed_lines("a\n", "a\nb\n"))

    def test_a_rewrite_can_exceed_the_original_length(self) -> None:
        """Why `util_constants.h` reports 320 differing lines in a 277-line file.

        Every line removed and a different number added: the count is of diff
        lines, not of file lines, and a reader who takes it for the second
        concludes the tool is broken.
        """

        before = "\n".join(f"old {n}" for n in range(10)) + "\n"
        after = "\n".join(f"new {n}" for n in range(12)) + "\n"
        self.assertEqual(22, churn.changed_lines(before, after))


class VerdictTests(unittest.TestCase):
    def test_absent_after_means_deleted(self) -> None:
        self.assertEqual("deleted", churn.verdict("a\n", None))

    def test_absent_before_is_not_a_deletion(self) -> None:
        """A file that does not exist at the base revision was never owned."""

        self.assertEqual("absent at the base revision", churn.verdict(None, "a\n"))

    def test_absent_on_both_sides_reports_the_base(self) -> None:
        self.assertEqual("absent at the base revision", churn.verdict(None, None))

    def test_equal_bodies_are_unchanged(self) -> None:
        self.assertEqual("unchanged", churn.verdict("a\nb\n", "a\nb\n"))

    def test_a_difference_is_reported_as_a_count(self) -> None:
        self.assertEqual("2 lines differ", churn.verdict("a\nb\n", "a\nc\n"))


class ReportTests(unittest.TestCase):
    def test_the_report_is_a_markdown_table_a_contract_can_hold(self) -> None:
        rows = [
            ("chrome/x.cc", 10, {"153": "unchanged"}),
            ("chrome/y.cc", 20, {"153": "deleted"}),
            ("chrome/z.cc", None, {"153": "absent at the base revision"}),
        ]
        report = churn.format_report("152.0.7977.42", ("153",), rows).splitlines()
        self.assertEqual("| File | at 152.0.7977.42 | 153 |", report[0])
        self.assertIn("**unchanged**", report[2])
        self.assertIn("**deleted**", report[3])
        self.assertIn("**absent**", report[4])


class FileSetTests(unittest.TestCase):
    def test_the_executable_name_set_covers_what_the_plan_enumerates(self) -> None:
        """§4 names five areas; each must have at least one file measured.

        A set that quietly lost a file would report a cheaper roll than the
        truth, which is the direction a measurement must never be wrong in.
        """

        paths = churn.SETS["executable-name"]
        for area in (
            "util_constants",            # the constants
            "setup/setup_main",          # the update swap
            "util/shell_util",           # shortcuts, ProgID, default browser
            "install_static/",           # earliest startup and the crash handler
            "setup/setup_singleton",     # Active Setup's neighbourhood
        ):
            with self.subTest(area=area):
                self.assertTrue(
                    any(area in path for path in paths),
                    f"no file measured for {area}",
                )

    def test_every_path_is_a_chromium_source_path(self) -> None:
        for path in churn.SETS["executable-name"]:
            with self.subTest(path=path):
                self.assertTrue(path.startswith("chrome/"), path)
                self.assertFalse(path.endswith("/"), path)


if __name__ == "__main__":
    unittest.main()
