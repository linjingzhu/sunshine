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
import re
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



class MarkupTests(unittest.TestCase):
    """Enforces: every XML file the stack creates parses.

    Written after build #49 died in fourteen seconds on a `--` inside an XML
    comment, having passed twenty-six guards and 881 tests on the way there.
    Every one of those asks whether a patch *lands*; none asked whether what it
    lands can be read by the tool that reads it.
    """

    def test_the_repository_parses_today(self) -> None:
        self.assertEqual([], guard.check(REPOSITORY_ROOT))

    def test_a_double_hyphen_in_a_comment_is_rejected(self) -> None:
        """The exact defect, in the exact shape it arrived in.

        XML forbids `--` inside a comment. This repository writes `--` for an em
        dash throughout its prose, so the habit that produced it is the house
        style meeting a format that does not allow it -- which is why a guard is
        the right answer and "remember not to" is not.
        """

        failures: list[str] = []
        guard.check_markup_parses(
            {"chrome/app/x.grd": [
                "<?xml version=\"1.0\" encoding=\"UTF-8\"?>",
                "<!-- a comment -- with a double hyphen in it -->",
                "<grit><release seq=\"1\"><messages></messages></release></grit>",
            ]},
            failures,
        )
        self.assertTrue(failures, "the malformed comment was accepted")
        self.assertIn("not well-formed", failures[0])

    def test_a_well_formed_grd_passes(self) -> None:
        failures: list[str] = []
        guard.check_markup_parses(
            {"chrome/app/x.grd": [
                "<?xml version=\"1.0\" encoding=\"UTF-8\"?>",
                "<!-- a comment with an em dash \u2014 in it -->",
                "<grit><release seq=\"1\"><messages></messages></release></grit>",
            ]},
            failures,
        )
        self.assertEqual([], failures)

    def test_a_file_that_is_not_markup_is_not_parsed(self) -> None:
        """A `.ts` file full of angle brackets is not an XML document."""

        failures: list[str] = []
        guard.check_markup_parses({"a/b.ts": ["const x = a < b && c > d;"]}, failures)
        self.assertEqual([], failures)


if __name__ == "__main__":
    unittest.main()


class TypeScriptImportTests(unittest.TestCase):
    """Enforces: no import statement mixes a value with a type.

    Written after build #53 died ninety-nine seconds in, on one line of one new
    file, with upstream's own eslint saying exactly what was wrong:

        Do not mix type and value imports in the same statement.
        @webui-eslint/no-mixed-type-and-value-imports

    The third build lost to the same shape -- #46 to stylelint, #49 to an XML
    parser, #53 to eslint -- and the second one to be lost after a guard was
    written for the previous one. `MarkupTests` closed the format above this;
    this closes the format beside it.
    """

    def failures_for(self, source: str) -> list[str]:
        failures: list[str] = []
        guard.check_typescript_imports({"a/b.ts": source.splitlines()}, failures)
        return failures

    def test_the_mixed_import_that_failed_build_53(self) -> None:
        failures = self.failures_for(
            "import {hostMessage, type HostMessage} from './mount_port.js';")
        self.assertEqual(1, len(failures))
        self.assertIn("hostMessage", failures[0])
        self.assertIn("type HostMessage", failures[0])

    def test_two_statements_are_how_it_is_written(self) -> None:
        self.assertEqual([], self.failures_for(
            "import {hostMessage} from './mount_port.js';\n"
            "import type {HostMessage, MountTab} from './mount_port.js';"))

    def test_a_multi_line_statement_is_read_whole(self) -> None:
        """The form a formatter produces, which is the one worth catching."""

        self.assertEqual(1, len(self.failures_for(
            "import {\n  hostMessage,\n  type HostMessage,\n} from './p.js';")))

    def test_a_file_that_is_not_typescript_is_not_read(self) -> None:
        failures: list[str] = []
        guard.check_typescript_imports(
            {"a/b.js": ["import {a, type B} from './c.js';"]}, failures)
        self.assertEqual([], failures)

    def test_the_repository_has_none(self) -> None:
        failures: list[str] = []
        guard.check_typescript_imports(guard.stack_files(), failures)
        self.assertEqual([], failures)


class BundleIdAllocationTests(unittest.TestCase):
    """Enforces: the resource bundle fits the ids the spec allocates it.

    Written after build #54 died two minutes in, one id short:

        ID range overflow.: Generated .grd file used more IDs (31) than were
        allocated for it (30) for type includes.

    The fourth build lost to something decidable before the build, and the
    third in a row -- #52 bootstrap, #53 eslint, #54 grit. Adding a surface
    adds four files and nobody looks at a number in `resource_ids.spec` that
    only grit ever reads.
    """

    BUILD = "chrome/browser/resources/sunshine/BUILD.gn"

    def test_the_repository_fits(self) -> None:
        failures: list[str] = []
        guard.check_bundle_id_allocation(guard.stack_files(), failures)
        self.assertEqual([], failures)

    def test_the_count_agrees_with_what_grit_reported(self) -> None:
        """Grit said 31 when #54 failed. This arithmetic has to say 31 too.

        A guard whose number is its own opinion is a guard that passes while
        the build fails, which is worse than not having it.
        """

        build = "\n".join(guard.stack_files()[self.BUILD])
        needed = sum(
            len(re.findall(r'"([^"]+)"', body))
            for _name, body in guard.BUNDLE_LISTS.findall(build))
        self.assertEqual(31, needed)

    def test_one_id_too_few_is_refused(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "downstream/patches").mkdir(parents=True)
            (root / "downstream/patches/0004-sunshine-webui-seam.patch").write_text(
                '+  "<(SHARED_INTERMEDIATE_DIR)/chrome/browser/resources/sunshine/'
                'resources.grd": {\n'
                '+    "META": {"sizes": {"includes": [2]}},\n'
                '+  },\n',
                encoding="utf-8")
            produced = {
                self.BUILD: [
                    "  static_files = [",
                    '    "a/app.html",',
                    '    "a/app.css",',
                    "  ]",
                    "  ts_files = [",
                    '    "a/app.ts",',
                    "  ]",
                ]
            }
            failures: list[str] = []
            guard.check_bundle_id_allocation(produced, failures, root)
            self.assertEqual(1, len(failures))
            self.assertIn("needs 3 include ids", failures[0])
            self.assertIn("allocates 2", failures[0])

    def test_exactly_enough_is_enough(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "downstream/patches").mkdir(parents=True)
            (root / "downstream/patches/0004-sunshine-webui-seam.patch").write_text(
                '+  "<(SHARED_INTERMEDIATE_DIR)/chrome/browser/resources/sunshine/'
                'resources.grd": {\n'
                '+    "META": {"sizes": {"includes": [3]}},\n'
                '+  },\n',
                encoding="utf-8")
            produced = {
                self.BUILD: [
                    "  static_files = [",
                    '    "a/app.html",',
                    '    "a/app.css",',
                    "  ]",
                    "  ts_files = [",
                    '    "a/app.ts",',
                    "  ]",
                ]
            }
            failures: list[str] = []
            guard.check_bundle_id_allocation(produced, failures, root)
            self.assertEqual([], failures)
