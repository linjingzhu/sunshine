"""Tests for the check that reads the stack for broken references.

Every build this project lost, it lost to a mistake that was decidable before
the build. So the tests that matter are the ones proving this notices each
kind — a guard that only ever passes on the committed stack is
indistinguishable from one that always passes.

The reconstruction is itself worth testing. It replays each patch's hunks over
the file the previous patch produced, checking context as it goes, which it can
only do if the stack applies in the order its series states.
"""

from pathlib import Path
import shutil
import sys
import tempfile
import unittest

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY_ROOT / "scripts"))

import verify_patch_references as guard  # noqa: E402


class ResourceIdTests(unittest.TestCase):
    def test_the_name_is_derived_the_way_build_webui_derives_it(self) -> None:
        self.assertEqual("IDR_SUNSHINE_SHELL_APP_HTML", guard.resource_id("shell/app.html"))
        self.assertEqual(
            "IDR_SUNSHINE_DOCUMENT_CONTENT_APP_HTML",
            guard.resource_id("document_content/app.html"),
        )
        self.assertEqual("IDR_SUNSHINE_SECURITY_APP_CSS", guard.resource_id("security/app.css"))


class ReconstructionTests(unittest.TestCase):
    def test_the_stack_reconstructs(self) -> None:
        produced = guard.stack_files()
        self.assertGreater(len(produced), 30)
        for path in (
            "chrome/browser/resources/sunshine/BUILD.gn",
            "chrome/browser/ui/webui/sunshine/BUILD.gn",
            "chrome/browser/resources/sunshine/shell/geometry.ts",
        ):
            with self.subTest(path=path):
                self.assertIn(path, produced)

    def test_upstream_files_are_absent_rather_than_guessed(self) -> None:
        """Their content starts from a tree this guard does not have, and a
        guess would be worse than not asking."""

        produced = guard.stack_files()
        self.assertNotIn("chrome/common/webui_url_constants.cc", produced)
        self.assertNotIn("chrome/browser/ui/views/bookmarks/bookmark_bar_view.cc", produced)

    def test_a_later_patch_really_extended_the_earlier_file(self) -> None:
        """The reconstruction is only meaningful if the hunks applied."""

        build = "\n".join(
            guard.stack_files()["chrome/browser/resources/sunshine/BUILD.gn"]
        )
        for surface in ("security/app.html", "document/app.html", "shell/app.html"):
            with self.subTest(surface=surface):
                self.assertIn(surface, build)


class DetectionTests(unittest.TestCase):
    """Each failure the guard exists for, injected.

    **The injections target the security surface, not the shell**, and that is
    load-bearing rather than arbitrary. A later patch's context lines are the
    earlier patch's text, so mutating a file that a later patch extends makes
    the reconstruction diverge first and the guard reports *that* instead --
    which is correct behaviour and the wrong thing to be testing here. Patch
    0015 extends the shell's C++, so three of these moved to patch 0005, whose
    files no later patch touches.

    **The two build-list injections target `modules/`, and the reason is the
    same rule applied to a different kind of line.** A GN list is sorted, so a
    new surface inserts itself alphabetically and quotes its three neighbours
    as context. `shell/` is the last surface in both lists, so *every*
    insertion lands directly above it and quotes it -- patch 0024's settings
    surface did, and the two tests that mutated `shell/app.css` and
    `shell/sunshine_shell_ui.cc` began failing on a reconstruction mismatch
    rather than on what they exist to detect. `modules/` sits in the middle
    with occupied neighbours on both sides, so nothing has quoted it and it is
    the durable place to put this. `test_the_injection_targets_are_isolated`
    below checks that property rather than trusting this paragraph.
    """

    def setUp(self) -> None:
        directory = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, directory, True)
        self.root = Path(directory)
        shutil.copytree(
            REPOSITORY_ROOT / "downstream", self.root / "downstream",
            ignore=shutil.ignore_patterns("assets"),
        )

    def patch(self, number: str) -> Path:
        matches = sorted((self.root / "downstream/patches").glob(f"{number}*.patch"))
        self.assertEqual(1, len(matches))
        return matches[0]

    def rewrite(self, number: str, old: str, new: str) -> None:
        path = self.patch(number)
        text = path.read_text(encoding="utf-8")
        self.assertIn(old, text)
        path.write_text(text.replace(old, new, 1), encoding="utf-8")

    def test_the_injection_targets_are_isolated(self) -> None:
        """No later patch quotes the lines the two build-list tests mutate.

        This is the precondition those tests rest on, and it is not a property
        of the lines themselves -- it is a property of where the next surface
        happens to sort. When a patch does quote one of them, the two tests
        below stop reporting what they are named after and start reporting a
        reconstruction mismatch, which reads as a bug in the guard. Failing
        here instead says which line moved and why.
        """

        directory = self.root / "downstream/patches"
        entries = sorted(path.name for path in directory.glob("*.patch"))
        texts = {entry: (directory / entry).read_text(encoding="utf-8")
                 for entry in entries}
        for owner, line in (("0007", '"modules/app.css",'),
                            ("0007", '"modules/sunshine_modules_ui.cc",')):
            later = [entry for entry in entries
                     if entry[:4] > owner and line in texts[entry]]
            self.assertEqual(
                [], later,
                f"{line} is now quoted by {later}; the build-list injections "
                "need a target no later patch's context contains"
            )

    def test_the_repository_as_committed_resolves(self) -> None:
        self.assertEqual([], guard.check())
        self.assertEqual([], guard.check(self.root))

    def test_a_resource_id_the_bundle_does_not_produce_fails(self) -> None:
        """The typo class: C++ naming an IDR_ that no file backs."""

        self.rewrite("0005", "IDR_SUNSHINE_SECURITY_APP_HTML", "IDR_SUNSHINE_SECURIT_APP_HTML")
        failures = guard.check(self.root)
        self.assertTrue(any("IDR_SUNSHINE_SECURIT_APP_HTML" in f for f in failures), failures)

    def test_a_bundle_entry_with_no_file_fails(self) -> None:
        self.rewrite("0007", '+    "modules/app.css",', '+    "modules/missing.css",')
        failures = guard.check(self.root)
        self.assertTrue(any("missing.css" in f for f in failures), failures)

    def test_a_browser_source_with_no_file_fails(self) -> None:
        self.rewrite(
            "0007", '+    "modules/sunshine_modules_ui.cc",', '+    "modules/absent.cc",'
        )
        failures = guard.check(self.root)
        self.assertTrue(any("absent.cc" in f for f in failures), failures)

    def test_an_include_of_a_header_no_patch_creates_fails(self) -> None:
        self.rewrite(
            "0005",
            '+#include "chrome/browser/ui/webui/sunshine/security/sunshine_security_ui.h"',
            '+#include "chrome/browser/ui/webui/sunshine/security/not_written.h"',
        )
        failures = guard.check(self.root)
        self.assertTrue(any("not_written.h" in f for f in failures), failures)

    def test_a_generated_mojo_header_is_not_a_missing_file(self) -> None:
        """The one include that legitimately names something no patch writes.
        What the stack owes is the .mojom it is generated from, and it has it."""

        self.assertEqual(
            [], [f for f in guard.check(self.root) if ".mojom.h" in f]
        )

    def test_a_chromium_include_is_not_this_guards_business(self) -> None:
        self.rewrite(
            "0005",
            '+#include "content/public/browser/web_ui.h"',
            '+#include "content/public/browser/web_ui_nonexistent.h"',
        )
        self.assertEqual([], guard.check(self.root))

    def test_a_stack_that_does_not_apply_in_series_order_is_reported(self) -> None:
        """Context that does not match means the reconstruction diverged, which
        means the patches do not apply in the order the series states."""

        self.rewrite("0011", "   ts_files = [", "   ts_files_moved = [")
        with self.assertRaises(guard.ReferenceError):
            guard.check(self.root)


if __name__ == "__main__":
    unittest.main()
