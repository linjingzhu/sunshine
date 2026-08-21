"""Tests for the check that keeps the product rename honest.

The patch under test changes 527 lines. Nobody reviews 527 lines of diff, so
the guard is the review — and a guard that only ever passes on the committed
patch is indistinguishable from one that always passes. Every rule below is
proved by injecting the violation it exists to catch.

The exclusion rule is tested hardest, because it is the one that was already
wrong once. The first version of the rename listed five *messages* whose names
looked like attribution; the guard rejected the result, because `ChromiumOS`
and the developer note appear in dozens of messages whose names look like
nothing in particular. The rule is a property of the text, not of an id list.
"""

from pathlib import Path
import shutil
import sys
import tempfile
import unittest

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY_ROOT / "scripts"))

import verify_branding_substitution as guard  # noqa: E402


class RenameRuleTests(unittest.TestCase):
    def test_the_product_name_is_renamed(self) -> None:
        self.assertEqual("Sunshine is a web browser", guard.rename("Chromium is a web browser"))

    def test_every_occurrence_on_a_line_is_renamed(self) -> None:
        self.assertEqual(
            "Sunshine blocked it, so Sunshine is safe",
            guard.rename("Chromium blocked it, so Chromium is safe"),
        )

    def test_upstreams_operating_system_survives(self) -> None:
        self.assertEqual("ChromiumOS could not sync", guard.rename("ChromiumOS could not sync"))

    def test_the_copyright_survives(self) -> None:
        self.assertEqual(
            "Copyright 2026 The Chromium Authors. All rights reserved.",
            guard.rename("Copyright 2026 The Chromium Authors. All rights reserved."),
        )

    def test_the_developer_note_survives(self) -> None:
        self.assertEqual(
            "Not used in Chromium. Placeholder to keep resource maps in sync.",
            guard.rename("Not used in Chromium. Placeholder to keep resource maps in sync."),
        )

    def test_a_protected_phrase_does_not_shield_the_rest_of_the_line(self) -> None:
        """The case masking exists for: both names on one line, only one ours."""

        self.assertEqual(
            "ChromiumOS could not save Sunshine data",
            guard.rename("ChromiumOS could not save Chromium data"),
        )

    def test_masking_cannot_be_re_matched(self) -> None:
        """A sentinel containing the word being replaced would corrupt the
        restore. The mask is an index between NULs, so it cannot."""

        for phrase in guard.PROTECTED:
            with self.subTest(phrase=phrase):
                self.assertEqual(phrase, guard.rename(phrase))

    def test_the_forbidden_list_is_derived_from_the_protected_one(self) -> None:
        """Two hand-written lists would drift, and the drift would let exactly
        the mistake through that both exist to stop."""

        self.assertEqual(
            tuple(p.replace(guard.OLD, guard.NEW) for p in guard.PROTECTED),
            guard.FORBIDDEN_IN_ADDITIONS,
        )


class PatchTests(unittest.TestCase):
    def setUp(self) -> None:
        directory = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, directory, True)
        self.root = Path(directory)
        patches = self.root / "downstream/patches"
        patches.mkdir(parents=True)
        self.patch = patches / guard.PATCH_NAME
        shutil.copy(REPOSITORY_ROOT / "downstream/patches" / guard.PATCH_NAME, self.patch)

    def rewrite(self, old: str, new: str) -> None:
        text = self.patch.read_text(encoding="utf-8")
        self.assertIn(old, text)
        self.patch.write_text(text.replace(old, new, 1), encoding="utf-8")

    def test_the_committed_patch_is_only_the_rename(self) -> None:
        self.assertEqual([], guard.check())
        self.assertEqual([], guard.check(self.root))

    def test_an_unrelated_edit_smuggled_in_fails(self) -> None:
        """The failure the guard exists for: a reworded sentence hidden in 527
        lines of mechanical diff."""

        self.rewrite("+            Sunshine\n", "+            Sunshine Browser\n")
        self.assertNotEqual([], guard.check(self.root))

    def test_a_changed_line_that_never_said_chromium_fails(self) -> None:
        text = self.patch.read_text(encoding="utf-8")
        first = next(l for l in text.splitlines() if l.startswith("-") and not l.startswith("---"))
        self.rewrite(first + "\n", "-          Some unrelated line\n")
        self.assertNotEqual([], guard.check(self.root))

    def test_a_removed_line_with_no_replacement_fails(self) -> None:
        """A rename replaces one for one. A deletion is something else."""

        text = self.patch.read_text(encoding="utf-8")
        first = next(l for l in text.splitlines() if l.startswith("+") and not l.startswith("+++"))
        self.patch.write_text(text.replace(first + "\n", "", 1), encoding="utf-8")
        failures = guard.check(self.root)
        self.assertTrue(any("one for one" in f for f in failures), failures)

    def test_renaming_upstreams_operating_system_fails(self) -> None:
        self.rewrite("+            Sunshine\n", "+            SunshineOS\n")
        failures = guard.check(self.root)
        self.assertTrue(any("SunshineOS" in f for f in failures), failures)

    def test_renaming_the_copyright_holder_fails(self) -> None:
        self.rewrite("+            Sunshine\n", "+            The Sunshine Authors\n")
        failures = guard.check(self.root)
        self.assertTrue(any("Sunshine Authors" in f for f in failures), failures)

    def test_a_missing_patch_is_reported(self) -> None:
        self.patch.unlink()
        self.assertNotEqual([], guard.check(self.root))

    def test_a_patch_that_changes_nothing_is_reported(self) -> None:
        self.patch.write_text("diff --git a/x b/x\n--- a/x\n+++ b/x\n", encoding="utf-8")
        self.assertNotEqual([], guard.check(self.root))


if __name__ == "__main__":
    unittest.main()
