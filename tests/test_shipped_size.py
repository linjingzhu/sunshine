"""Tests for the shipped-payload measurement.

The measurement itself can only run on the build machine, which is also the only
CI, which is why every part of it that can be a pure function is one. These
tests exercise those functions against a synthetic output directory, so the
parsing and the resolution are decided off Windows and the machine that builds
is left with nothing to be the first to discover.

The fixture manifest is written here rather than copied from upstream on
purpose: what is under test is the parser's treatment of shapes -- sections,
comments, wildcards, absent entries -- and pinning it to whatever
`chrome.release` happens to contain would make an upstream edit fail these tests
for no reason. `MeasuredAgainstUpstreamTests` reads the real file separately,
and asserts only what this project depends on.
"""

from pathlib import Path
import shutil
import sys
import tempfile
import unittest

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY_ROOT / "scripts"))

import measure_shipped_size as measure  # noqa: E402

MANIFEST = """# a comment
# another

[GENERAL]
chrome.exe: %(ChromeDir)s\\
#
# the version dir
#
chrome.dll: %(VersionDir)s\\
icudtl.dat: %(VersionDir)s\\
locales\\*.pak: %(VersionDir)s\\Locales
absent.dll: %(VersionDir)s\\

[TOUCH]

[GOOGLE_CHROME]
elevation_service.exe: %(VersionDir)s\\
"""


class ParseTests(unittest.TestCase):
    def setUp(self) -> None:
        self.sections = measure.parse_release(MANIFEST)

    def test_every_section_is_kept_including_the_empty_one(self) -> None:
        """`[TOUCH]` has no entries at the pinned revision. Dropping it would
        report a fact about the parser as if it were one about the build."""

        self.assertEqual(["GENERAL", "TOUCH", "GOOGLE_CHROME"], list(self.sections))
        self.assertEqual([], self.sections["TOUCH"])

    def test_only_the_source_side_is_read(self) -> None:
        self.assertIn("chrome.dll", self.sections["GENERAL"])
        self.assertNotIn("%(VersionDir)s\\", self.sections["GENERAL"])

    def test_comments_and_blanks_are_dropped(self) -> None:
        for entry in self.sections["GENERAL"]:
            self.assertFalse(entry.startswith("#"))
            self.assertTrue(entry)

    def test_a_line_before_any_section_belongs_to_none(self) -> None:
        stray = measure.parse_release("loose.dll: %(VersionDir)s\\\n[GENERAL]\na.dll: x\n")
        self.assertEqual({"GENERAL": ["a.dll"]}, stray)


class ResolveTests(unittest.TestCase):
    def setUp(self) -> None:
        directory = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, directory, True)
        self.root = Path(directory)
        self.write("chrome.exe", 10)
        self.write("chrome.dll", 1000)
        self.write("icudtl.dat", 500)
        self.write("locales/en-US.pak", 20)
        self.write("locales/ko.pak", 30)
        self.write("locales/README", 999)  # not a .pak: must not be counted
        self.write("not_shipped.pdb", 100000)

    def write(self, relative: str, size: int) -> None:
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"x" * size)

    def test_a_wildcard_matches_within_its_directory_only(self) -> None:
        found, missing = measure.resolve(["locales\\*.pak"], self.root)
        self.assertEqual(["locales/en-US.pak", "locales/ko.pak"], [name for name, _ in found])
        self.assertEqual([], missing)

    def test_a_pattern_that_matches_nothing_is_reported_not_dropped(self) -> None:
        """The whole point. An absent LogoCanary.png and an absent chrome.dll
        must not look the same to the caller."""

        _, missing = measure.resolve(["absent.dll"], self.root)
        self.assertEqual(["absent.dll"], missing)

    def test_a_file_the_manifest_does_not_name_is_not_counted(self) -> None:
        report = measure.measure(self.root, MANIFEST)
        self.assertNotIn("not_shipped.pdb", report["files"])
        self.assertNotIn("locales/README", report["files"])

    def test_the_total_is_the_sum_of_what_the_manifest_names(self) -> None:
        report = measure.measure(self.root, MANIFEST)
        self.assertEqual(10 + 1000 + 500 + 20 + 30, report["total_bytes"])

    def test_a_file_matched_twice_is_counted_once(self) -> None:
        found, _ = measure.resolve(["chrome.dll", "chrome.*"], self.root)
        self.assertEqual(1, sum(1 for name, _ in found if name == "chrome.dll"))
        self.assertEqual(1000 + 10, sum(size for _, size in found))

    def test_sections_are_measured_separately(self) -> None:
        report = measure.measure(self.root, MANIFEST)
        self.assertEqual(0, report["sections"]["GOOGLE_CHROME"]["files"])
        self.assertEqual(
            ["elevation_service.exe"], report["sections"]["GOOGLE_CHROME"]["absent"]
        )
        self.assertEqual(5, report["sections"]["GENERAL"]["files"])

    def test_the_report_names_the_largest_contributors(self) -> None:
        report = measure.measure(self.root, MANIFEST)
        text = measure.format_report(report)
        self.assertIn("chrome.dll", text)
        self.assertIn("Shipped payload", text)


class MeasuredAgainstUpstreamTests(unittest.TestCase):
    """What this project depends on in the real `chrome.release`.

    Deliberately thin. The file is upstream's and changes when upstream adds a
    DLL; asserting its contents would make this suite fail on a rebase for a
    reason that is not a defect. What is asserted is only what the measurement
    would be *wrong* without.
    """

    MANIFEST = REPOSITORY_ROOT / "downstream/upstream_cache/chrome.release"

    def test_the_manifest_is_read_from_the_workspace_not_from_here(self) -> None:
        """There is no copy of upstream's manifest in this repository, and there
        must not be. A copy is a second list that drifts from what ships, which
        is the exact failure this measurement exists to avoid."""

        self.assertFalse(self.MANIFEST.exists())
        source = (REPOSITORY_ROOT / "scripts/measure_shipped_size.py").read_text("utf-8")
        self.assertIn("chrome/installer/mini_installer/chrome.release", source)

    def test_no_file_list_is_written_into_the_script(self) -> None:
        source = (REPOSITORY_ROOT / "scripts/measure_shipped_size.py").read_text("utf-8")
        for shipped in ("chrome.dll", "icudtl.dat", "v8_context_snapshot.bin"):
            with self.subTest(name=shipped):
                # Naming one in a docstring is fine; naming one in a list is the
                # copy this file is about.
                self.assertNotIn(f'"{shipped}"', source)
                self.assertNotIn(f"'{shipped}'", source)


if __name__ == "__main__":
    unittest.main()
