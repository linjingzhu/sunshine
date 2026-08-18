"""Tests for the patch integrity guard.

The stack is hand-maintained, and until now the only thing that read a hunk
header for correctness was `git apply` on the Windows runner -- hours into a
build queue, on the machine that is also the only CI. The arithmetic in
`@@ -a,b +c,d @@` is the part a person has to keep true by hand every time they
edit a body, and it is the part that costs a build when it is not.

Every case injects the malformation into a fixture. The real patches are never
mutated on disk: a guard tested by editing the artifact it guards would pass by
construction, and the artifact would be one careless cleanup away from
inheriting a fixture.

The cases that assert nothing is reported carry as much weight. A hunk header
is four numbers and a body is four line shapes; a guard strict about the wrong
one of them fails a patch git applies happily, and gets deleted rather than
consulted.
"""

from pathlib import Path
import sys
import tempfile
import unittest

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY_ROOT / "scripts"))

import verify_patch_integrity as integrity  # noqa: E402


def patch(*lines: str) -> str:
    """A patch file body. Joined with a trailing newline, as git writes them."""

    return "\n".join(lines) + "\n"


# One removal and three context lines: `@@ -1,4 +1,4 @@` is the truth about it.
# Every arithmetic case below is this patch with one number or one line moved.
CLEAN = patch(
    "diff --git a/chrome/app/theme/chromium/BRANDING b/chrome/app/theme/chromium/BRANDING",
    "--- a/chrome/app/theme/chromium/BRANDING",
    "+++ b/chrome/app/theme/chromium/BRANDING",
    "@@ -1,4 +1,4 @@",
    "-PRODUCT_FULLNAME=Chromium",
    "+PRODUCT_FULLNAME=Sunshine OS",
    " MAC_CREATOR_CODE=Cr24",
    " MAC_TEAM_ID=",
    " MAC_INSTALLER_ID=",
)


class PatchTestCase(unittest.TestCase):
    def setUp(self) -> None:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        (self.root / "downstream/patches").mkdir(parents=True)

    def write(self, name: str, text: str) -> None:
        (self.root / "downstream/patches" / name).write_text(text, encoding="utf-8")

    def stack(self, *patches: str, series: list[str] | None = None) -> None:
        """Write a numbered stack and a series that lists it, so that a test
        about a hunk is never also a test about the series."""

        names = []
        for number, text in enumerate(patches, start=1):
            name = f"{number:04d}-fixture.patch"
            self.write(name, text)
            names.append(name)
        listed = names if series is None else series
        (self.root / "downstream/patches/series").write_text(
            "".join(f"{name}\n" for name in listed), encoding="utf-8"
        )

    def failures(self) -> list[str]:
        return integrity.check(self.root)[1]

    def assertRejected(self, needle: str) -> None:
        found = self.failures()
        self.assertTrue(found, "the malformed patch was accepted")
        self.assertTrue(any(needle in failure for failure in found), f"{needle!r} not in {found}")

    def assertAccepted(self) -> None:
        self.assertEqual([], self.failures())


class CleanStackTests(PatchTestCase):
    def test_a_well_formed_stack_passes(self) -> None:
        self.stack(CLEAN)
        counts, failures = integrity.check(self.root)
        self.assertEqual([], failures)
        self.assertEqual({"patches": 1, "sections": 1, "hunks": 1}, counts)

    def test_omitted_counts_mean_one(self) -> None:
        """Unified diff omits a count of 1, and git emits the short form."""

        self.stack(patch(
            "--- a/x/y.cc",
            "+++ b/x/y.cc",
            "@@ -3 +3 @@",
            "-one",
            "+two",
        ))
        self.assertAccepted()

    def test_an_index_line_between_the_headers_is_accepted(self) -> None:
        """`git diff` writes one; `0002-sunshine-new-tab.patch` has three."""

        self.stack(patch(
            "diff --git a/x/y.cc b/x/y.cc",
            "index d9d32b0..355c621 100644",
            "--- a/x/y.cc",
            "+++ b/x/y.cc",
            "@@ -1,2 +1,2 @@",
            "-one",
            "+two",
            " three",
        ))
        self.assertAccepted()

    def test_a_no_newline_marker_counts_as_neither_side(self) -> None:
        self.stack(patch(
            "--- a/x/y.cc",
            "+++ b/x/y.cc",
            "@@ -1,2 +1,2 @@",
            " one",
            "-two",
            "\\ No newline at end of file",
            "+three",
            "\\ No newline at end of file",
        ))
        self.assertAccepted()

    def test_a_file_added_against_dev_null_is_accepted(self) -> None:
        """No patch in the stack adds a file yet. Rejecting the form would make
        the first one that does look like a malformed patch."""

        self.stack(patch(
            "diff --git a/x/new.cc b/x/new.cc",
            "new file mode 100644",
            "--- /dev/null",
            "+++ b/x/new.cc",
            "@@ -0,0 +1,2 @@",
            "+one",
            "+two",
        ))
        self.assertAccepted()


class HunkArithmeticTests(PatchTestCase):
    def test_an_old_count_lower_than_the_body_is_rejected(self) -> None:
        """The shape of the defect this guard was written for: a body edited,
        a header left behind."""

        self.stack(CLEAN.replace("@@ -1,4 +1,4 @@", "@@ -1,3 +1,4 @@"))
        self.assertRejected("declares 3 old line(s), body holds 4")

    def test_an_old_count_higher_than_the_body_is_rejected(self) -> None:
        """The direction `git apply` calls a corrupt patch: the fragment ends
        before the header says it should, and the build stops."""

        self.stack(CLEAN.replace("@@ -1,4 +1,4 @@", "@@ -1,6 +1,4 @@"))
        self.assertRejected("declares 6 old line(s), body holds 4")

    def test_a_new_count_that_disagrees_is_rejected(self) -> None:
        self.stack(CLEAN.replace("@@ -1,4 +1,4 @@", "@@ -1,4 +1,9 @@"))
        self.assertRejected("declares 9 new line(s), body holds 4")

    def test_a_removed_body_line_is_rejected(self) -> None:
        """The counts are unchanged and a line went missing -- the same
        disagreement approached from the body instead of the header."""

        self.stack(CLEAN.replace(" MAC_TEAM_ID=\n", ""))
        self.assertRejected("declares 4 old line(s), body holds 3")

    def test_an_omitted_count_is_one_and_is_held_to_one(self) -> None:
        self.stack(patch(
            "--- a/x/y.cc",
            "+++ b/x/y.cc",
            "@@ -3 +3 @@",
            "-one",
            "-two",
            "+three",
        ))
        self.assertRejected("@@ -3 +3 @@ declares 1 old line(s), body holds 2")

    def test_the_failure_names_the_patch_the_hunk_and_the_arithmetic(self) -> None:
        """A guard that says "a hunk is wrong" sends someone to count lines by
        hand, which is the job it was written to remove."""

        self.stack(CLEAN.replace("@@ -1,4 +1,4 @@", "@@ -1,3 +1,4 @@"))
        failure = self.failures()[0]
        self.assertIn("downstream/patches/0001-fixture.patch:4", failure)
        self.assertIn("@@ -1,3 +1,4 @@", failure)
        self.assertIn("declares 3 old line(s), body holds 4", failure)


class BodyLineTests(PatchTestCase):
    def test_a_line_with_no_diff_prefix_is_rejected(self) -> None:
        self.stack(patch(
            "--- a/x/y.cc",
            "+++ b/x/y.cc",
            "@@ -1,3 +1,3 @@",
            " one",
            "this line lost its prefix",
            " three",
        ))
        self.assertRejected("carries no diff prefix")

    def test_an_empty_line_is_a_blank_context_line(self) -> None:
        """Editors and hooks strip the trailing space off a blank context line.
        Git accepts the stripped form and so does this; two hunks in
        `0003-sunshine-no-missing-api-key-warning.patch` depend on it.
        """

        self.stack(patch(
            "--- a/x/y.cc",
            "+++ b/x/y.cc",
            "@@ -1,4 +1,4 @@",
            " one",
            "",
            "-two",
            "+three",
            " four",
        ))
        self.assertAccepted()

    def test_a_blank_context_line_is_counted_on_both_sides(self) -> None:
        """Treating the blank as nothing would make this hunk's own header
        wrong, which is how the tolerance is proved rather than assumed."""

        self.stack(patch(
            "--- a/x/y.cc",
            "+++ b/x/y.cc",
            "@@ -1,3 +1,3 @@",
            " one",
            "",
            " three",
        ).replace("@@ -1,3 +1,3 @@", "@@ -1,2 +1,2 @@"))
        self.assertRejected("declares 2 old line(s), body holds 3")

    def test_a_trailing_blank_at_the_end_of_the_file_is_not_a_body_line(self) -> None:
        """The last line of a hunk is the one place a blank is ambiguous: the
        hunk's own context, or the blank someone left at the end of the file.
        Git reads it as neither once the counts are met, and so must this, or
        every patch that ends with a spare newline fails."""

        self.stack(CLEAN + "\n")
        self.assertAccepted()

    def test_a_hunk_that_really_ends_in_a_blank_context_line_keeps_it(self) -> None:
        """The other side of the same ambiguity. The trailing blank is dropped
        only while it is surplus, so a header that counts it still agrees."""

        self.stack(patch(
            "--- a/x/y.cc",
            "+++ b/x/y.cc",
            "@@ -1,3 +1,3 @@",
            "-one",
            "+two",
            " three",
            "",
        ))
        self.assertAccepted()


class FileHeaderTests(PatchTestCase):
    def test_an_old_header_with_no_new_header_is_rejected(self) -> None:
        self.stack(patch(
            "--- a/x/y.cc",
            "@@ -1,1 +1,1 @@",
            "-one",
            "+two",
        ))
        self.assertRejected("is not followed by a '+++ ' header")

    def test_headers_naming_different_files_are_rejected(self) -> None:
        """A copied section with one path updated applies the hunk to the wrong
        file, or to no file at all, depending on which half is read."""

        self.stack(patch(
            "--- a/x/y.cc",
            "+++ b/x/z.cc",
            "@@ -1,1 +1,1 @@",
            "-one",
            "+two",
        ))
        self.assertRejected("--- a/x/y.cc and +++ b/x/z.cc name different files")

    def test_a_hunk_before_any_file_header_is_rejected(self) -> None:
        """A hunk with no file section belongs to nothing."""

        self.stack(patch(
            "@@ -1,1 +1,1 @@",
            "-one",
            "+two",
        ))
        self.assertRejected("appears before any '--- '/'+++ ' header")

    def test_a_patch_with_no_hunks_is_rejected(self) -> None:
        """A patch that changes nothing, and a patch whose hunks stopped being
        recognised, look the same from here; both are worth a failure."""

        self.stack(patch(
            "diff --git a/x/y.cc b/x/y.cc",
            "--- a/x/y.cc",
            "+++ b/x/y.cc",
        ))
        self.assertRejected("contains no hunks")


class HunkOrderTests(PatchTestCase):
    def test_overlapping_hunks_are_rejected(self) -> None:
        """`git apply` walks a file forwards once. A second hunk reaching back
        into the lines the first one consumed cannot be applied as written."""

        self.stack(patch(
            "--- a/x/y.cc",
            "+++ b/x/y.cc",
            "@@ -10,3 +10,3 @@",
            "-one",
            "+two",
            " three",
            " four",
            "@@ -11,2 +11,2 @@",
            "-five",
            "+six",
            " seven",
        ))
        self.assertRejected("starts at old line 11, inside or before @@ -10,3 +10,3 @@")

    def test_descending_hunks_are_rejected(self) -> None:
        self.stack(patch(
            "--- a/x/y.cc",
            "+++ b/x/y.cc",
            "@@ -100,2 +100,2 @@",
            "-one",
            "+two",
            " three",
            "@@ -10,2 +10,2 @@",
            "-four",
            "+five",
            " six",
        ))
        self.assertRejected("starts at old line 10, inside or before @@ -100,2 +100,2 @@")

    def test_adjacent_hunks_are_accepted(self) -> None:
        """The boundary case. Git merges hunks this close, but a hand-edited
        stack may not, and rejecting them would be a false positive on a patch
        that applies."""

        self.stack(patch(
            "--- a/x/y.cc",
            "+++ b/x/y.cc",
            "@@ -1,3 +1,3 @@",
            "-one",
            "+two",
            " three",
            " four",
            "@@ -4,2 +4,2 @@",
            "-five",
            "+six",
            " seven",
        ))
        self.assertAccepted()

    def test_the_order_restarts_at_each_file_section(self) -> None:
        """Line numbers are per file. `0002-sunshine-new-tab.patch` patches
        three files, and the second starts near the top of its own."""

        self.stack(patch(
            "diff --git a/x/y.cc b/x/y.cc",
            "--- a/x/y.cc",
            "+++ b/x/y.cc",
            "@@ -900,2 +900,2 @@",
            "-one",
            "+two",
            " three",
            "diff --git a/x/z.cc b/x/z.cc",
            "--- a/x/z.cc",
            "+++ b/x/z.cc",
            "@@ -10,2 +10,2 @@",
            "-four",
            "+five",
            " six",
        ))
        self.assertAccepted()


class SeriesTests(PatchTestCase):
    def test_a_series_naming_a_patch_that_is_not_there_is_rejected(self) -> None:
        self.stack(CLEAN, series=["0001-fixture.patch", "0002-gone.patch"])
        self.assertRejected("lists 0002-gone.patch, which is not in downstream/patches/")

    def test_a_patch_missing_from_the_series_is_rejected(self) -> None:
        """An unlisted patch is never applied. Nothing else would say so: the
        file is present, readable, and silently inert."""

        self.stack(CLEAN, CLEAN, series=["0001-fixture.patch"])
        self.assertRejected("0002-fixture.patch: is not listed in downstream/patches/series")

    def test_a_duplicated_series_entry_is_rejected(self) -> None:
        self.stack(CLEAN, series=["0001-fixture.patch", "0001-fixture.patch"])
        self.assertRejected("lists 0001-fixture.patch more than once")

    def test_two_patches_sharing_a_number_are_rejected(self) -> None:
        """The number is the stack's ordering, so two of them is two answers to
        where a patch belongs."""

        self.write("0002-alpha.patch", CLEAN)
        self.write("0002-beta.patch", CLEAN)
        (self.root / "downstream/patches/series").write_text(
            "0002-alpha.patch\n0002-beta.patch\n", encoding="utf-8"
        )
        self.assertRejected("0002-beta.patch reuses the number of 0002-alpha.patch")

    def test_a_series_out_of_numeric_order_is_rejected(self) -> None:
        """The directory listing and the apply order must not disagree; a
        reader who sorts by name would otherwise predict the wrong stack."""

        self.write("0001-alpha.patch", CLEAN)
        self.write("0002-beta.patch", CLEAN)
        (self.root / "downstream/patches/series").write_text(
            "0002-beta.patch\n0001-alpha.patch\n", encoding="utf-8"
        )
        self.assertRejected("0001-alpha.patch is listed after 0002-beta.patch")

    def test_comments_and_blank_lines_in_the_series_are_ignored(self) -> None:
        self.write("0001-fixture.patch", CLEAN)
        (self.root / "downstream/patches/series").write_text(
            "# the stack, in order\n\n0001-fixture.patch\n", encoding="utf-8"
        )
        self.assertAccepted()

    def test_a_missing_series_is_rejected(self) -> None:
        self.write("0001-fixture.patch", CLEAN)
        self.assertRejected("downstream/patches/series: missing")


class UnreadableStackTests(PatchTestCase):
    """The two ways there is nothing to read. Both are failures rather than
    quiet passes: a guard that finds no patches and reports success is
    indistinguishable from one pointed at the wrong tree."""

    def test_a_missing_patch_directory_is_rejected(self) -> None:
        empty = self.root / "elsewhere"
        empty.mkdir()
        self.assertEqual(
            ["downstream/patches/: missing"], integrity.check(empty)[1]
        )

    def test_a_patch_that_is_not_utf8_is_rejected(self) -> None:
        """Patch bodies carry Chromium source, which is UTF-8. A binary or
        mis-encoded file cannot be checked and must not be skipped in silence."""

        self.stack(CLEAN)
        (self.root / "downstream/patches/0001-fixture.patch").write_bytes(
            b"--- a/x/y.cc\n+++ b/x/y.cc\n@@ -1,1 +1,1 @@\n-caf\xe9\n+cafe\n"
        )
        self.assertRejected("is not UTF-8 text")


class RepositoryTests(unittest.TestCase):
    """The stack as it stands. These read the real files and never write them."""

    def test_the_real_series_and_directory_agree(self) -> None:
        _, failures = integrity.check(REPOSITORY_ROOT)
        self.assertEqual([], [failure for failure in failures if "series" in failure])

    def test_every_real_patch_is_well_formed(self) -> None:
        counts, failures = integrity.check(REPOSITORY_ROOT)
        self.assertGreater(counts["patches"], 0)
        self.assertGreater(counts["hunks"], 0)
        self.assertEqual(
            [],
            failures,
            "a patch in the stack disagrees with its own hunk headers; "
            "correct the header counts in downstream/patches/, not this test",
        )


if __name__ == "__main__":
    unittest.main()
