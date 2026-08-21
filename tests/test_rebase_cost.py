"""Tests for the roll-cost measurement.

The measurement needs the network, so what is decided here is everything around
the fetch: the hunk arithmetic, the reject accounting, and the property that
made the first version of this experiment report a wrong answer -- one failing
patch cascading into twelve.

That cascade is the case worth having a test for. It is not a hypothetical; the
first run reported thirteen of sixteen patches failing at trunk when four
failed and nine were missing files the four would have created.
"""

from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY_ROOT / "scripts"))

import measure_rebase_cost as measure  # noqa: E402
import verify_pinned_upstream as upstream_module  # noqa: E402

BASE = "one\ntwo\nthree\nfour\nfive\n"

# Creates `made.txt`, and edits `base.txt` in a way that only applies to BASE.
CREATOR = """diff --git a/made.txt b/made.txt
new file mode 100644
index 0000000..1234567
--- /dev/null
+++ b/made.txt
@@ -0,0 +1 @@
+made by the first patch
diff --git a/base.txt b/base.txt
index 1234567..89abcde 100644
--- a/base.txt
+++ b/base.txt
@@ -1,5 +1,6 @@
 one
 two
+inserted
 three
 four
 five
"""

# Edits the file the first patch created. Fails outright if that file is absent.
DEPENDENT = """diff --git a/made.txt b/made.txt
index 1234567..89abcde 100644
--- a/made.txt
+++ b/made.txt
@@ -1 +1,2 @@
 made by the first patch
+and extended by the second
"""


class HunkCountingTests(unittest.TestCase):
    def test_the_denominator_is_every_hunk_in_the_patch(self) -> None:
        self.assertEqual(2, measure.count_hunks(CREATOR))
        self.assertEqual(1, measure.count_hunks(DEPENDENT))

    def test_a_patch_with_no_hunk_counts_zero(self) -> None:
        self.assertEqual(0, measure.count_hunks("diff --git a/x b/x\n"))

    def test_the_real_series_is_read_in_order(self) -> None:
        """Derived, not restated. A count written here would be a second place
        the stack's size lives, and it went stale on the commit that added the
        seventeenth patch."""

        names = measure.series(REPOSITORY_ROOT)
        files = sorted((REPOSITORY_ROOT / "downstream/patches").glob("[0-9]*.patch"))
        self.assertEqual([path.name for path in files], names)
        for ordinal, name in enumerate(names, start=1):
            self.assertTrue(name.startswith(f"{ordinal:04d}-"), name)


class CascadeTests(unittest.TestCase):
    """The property `--reject` buys, stated as the failure it prevents."""

    def setUp(self) -> None:
        directory = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, directory, True)
        self.tree = Path(directory)
        self.patches = self.tree / "patches"
        self.patches.mkdir()
        self.root = self.tree / "root"
        self.root.mkdir()
        (self.root / "downstream/patches").mkdir(parents=True)
        for name, body in (("0001-creator.patch", CREATOR), ("0002-dependent.patch", DEPENDENT)):
            (self.root / "downstream/patches" / name).write_text(body, encoding="utf-8")
        (self.root / "downstream/patches/series").write_text(
            "0001-creator.patch\n0002-dependent.patch\n", encoding="utf-8"
        )
        self.work = self.tree / "work"
        self.work.mkdir()

    def seed(self, content: str) -> None:
        (self.work / "base.txt").write_text(content, encoding="utf-8")
        for command in (
            ["git", "init", "-q", "."],
            ["git", "add", "-A"],
            ["git", "-c", "user.email=x@y", "-c", "user.name=x", "commit", "-qm", "base"],
        ):
            subprocess.run(command, cwd=self.work, capture_output=True, check=False)

    def test_an_unchanged_base_applies_the_whole_series(self) -> None:
        self.seed(BASE)
        outcomes = measure.apply_series(self.work, self.root)
        self.assertEqual([0, 0], [outcome.rejected for outcome in outcomes])
        self.assertEqual(
            "made by the first patch\nand extended by the second\n",
            (self.work / "made.txt").read_text(encoding="utf-8"),
        )

    def test_a_conflict_in_one_patch_does_not_fail_the_next(self) -> None:
        """The whole reason for `--reject`. The first patch's edit to base.txt
        cannot apply, but the file it creates still lands, so the second patch
        is judged on its own hunk rather than on a missing file."""

        self.seed("one\ntwo\nTHREE HAS MOVED\nfour\nfive\n")
        outcomes = measure.apply_series(self.work, self.root)
        self.assertEqual(1, outcomes[0].rejected)
        self.assertEqual(("base.txt",), outcomes[0].files)
        self.assertEqual(0, outcomes[1].rejected, "the dependent patch cascaded")

    def test_the_report_names_the_file_a_hunk_was_rejected_from(self) -> None:
        self.seed("one\ntwo\nTHREE HAS MOVED\nfour\nfive\n")
        text = measure.format_report("probe", measure.apply_series(self.work, self.root))
        self.assertIn("CONFLICT", text)
        self.assertIn("base.txt", text)
        self.assertIn("1 of 2 patches conflict", text)
        self.assertIn("1 of 3 hunk(s) need a person", text)

    def test_rejects_do_not_leak_between_patches(self) -> None:
        """A `.rej` left behind would be counted again by the next patch, and
        every patch after a conflict would inherit it."""

        self.seed("one\ntwo\nTHREE HAS MOVED\nfour\nfive\n")
        measure.apply_series(self.work, self.root)
        self.assertEqual([], list(self.work.rglob("*.rej")))


class DelegationTests(unittest.TestCase):
    def test_the_mirrors_are_not_restated_here(self) -> None:
        """Where Chromium is belongs to one file. Two copies of a URL template
        are two things that must change together and one that will not."""

        source = (REPOSITORY_ROOT / "scripts/measure_rebase_cost.py").read_text("utf-8")
        for fragment in ("googlesource.com", "raw.githubusercontent.com"):
            with self.subTest(fragment=fragment):
                self.assertNotIn(fragment, source)
        self.assertIs(measure.upstream.SOURCES, upstream_module.SOURCES)

    def test_the_owned_file_list_comes_from_the_manifest(self) -> None:
        """Not from a list here. The stack decides which upstream files it owns,
        and a second list would measure a roll against the wrong files."""

        source = (REPOSITORY_ROOT / "scripts/measure_rebase_cost.py").read_text("utf-8")
        self.assertIn("patch_manifest.upstream_targets", source)
        self.assertNotIn("chrome/app/chromium_strings.grd", source)


if __name__ == "__main__":
    unittest.main()
