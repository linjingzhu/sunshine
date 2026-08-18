"""Tests for the part of the bootstrap that makes a workspace reusable.

Build #18 died 97 seconds in, before a single object compiled, with seven lines
of `already exists in working directory`. Patch 0004 is the first patch in the
stack that *creates* files, and a created file is untracked -- so
`git checkout --force` reverts every tracked file it finds and leaves those
seven exactly where the previous build put them. `git apply` then refuses the
whole patch, because applying a patch that adds a file that is already there is
not a thing it will guess at.

The obvious fix is `git clean`, and it is wrong: `out/Sunshine` is untracked too,
and deleting hours of incremental build to solve a seven-file problem trades one
broken build for a slow one forever. So the reset is driven by the stack's own
declaration of what it creates.

These tests are about that list being right. A list that is too small leaves the
build broken; one that is too large deletes upstream files and breaks it
differently.
"""

from pathlib import Path
import sys
import tempfile
import unittest

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY_ROOT / "scripts"))

import bootstrap_chromium as bootstrap  # noqa: E402

CREATED = """\
diff --git a/chrome/browser/resources/sunshine_security/app.css b/chrome/browser/resources/sunshine_security/app.css
--- /dev/null
+++ b/chrome/browser/resources/sunshine_security/app.css
@@ -0,0 +1,1 @@
+:host { display: block; }
"""

MODIFIED = """\
diff --git a/chrome/common/webui_url_constants.h b/chrome/common/webui_url_constants.h
--- a/chrome/common/webui_url_constants.h
+++ b/chrome/common/webui_url_constants.h
@@ -1,1 +1,2 @@
 inline constexpr char kChromeUIAboutHost[] = "about";
+inline constexpr char kChromeUISunshineSecurityHost[] = "sunshine-security";
"""


class CreatedPathTests(unittest.TestCase):
    def paths_of(self, text: str) -> set[str]:
        with tempfile.TemporaryDirectory() as directory:
            patch = Path(directory) / "0001-fixture.patch"
            patch.write_text(text, encoding="utf-8")
            return bootstrap.patch_created_paths(patch)

    def test_a_created_file_is_listed(self):
        self.assertEqual(
            self.paths_of(CREATED),
            {"chrome/browser/resources/sunshine_security/app.css"},
        )

    def test_a_modified_upstream_file_is_not(self):
        # The distinction the whole reset rests on. Deleting an upstream file
        # here would make `git apply` fail for the opposite reason, and the
        # checkout would be missing a file Chromium needs.
        self.assertEqual(self.paths_of(MODIFIED), set())

    def test_a_patch_doing_both_lists_only_what_it_creates(self):
        self.assertEqual(
            self.paths_of(MODIFIED + CREATED),
            {"chrome/browser/resources/sunshine_security/app.css"},
        )


class RealStackTests(unittest.TestCase):
    def created(self) -> set[str]:
        paths: set[str] = set()
        for name in bootstrap.read_series():
            paths |= bootstrap.patch_created_paths(
                REPOSITORY_ROOT / "downstream/patches" / name
            )
        return paths

    def test_the_stack_creates_the_security_surface_files(self):
        # If this ever returns nothing, the reset has quietly become a no-op and
        # the next build on a warm workspace fails the way #18 did.
        created = self.created()
        self.assertIn("chrome/browser/resources/sunshine/security/app.css", created)
        self.assertIn(
            "chrome/browser/ui/webui/sunshine/security/sunshine_security_ui.cc", created
        )

    def test_nothing_the_stack_creates_is_also_an_upstream_target(self):
        """A path that is both would be deleted and then patched as if upstream
        had it, which is `git apply` failing on a file that is simply gone."""

        import patch_manifest  # noqa: PLC0415

        entries = patch_manifest.read_manifest(REPOSITORY_ROOT)
        owners = patch_manifest.patch_targets(REPOSITORY_ROOT, entries)
        upstream = {
            target
            for target in owners
            if not any(
                target
                in bootstrap.patch_created_paths(
                    REPOSITORY_ROOT / "downstream/patches" / entry
                )
                for entry in entries
            )
        }
        self.assertEqual(self.created() & upstream, set())


class RemovalTests(unittest.TestCase):
    def test_only_the_created_paths_are_removed(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            patches = root / "downstream/patches"
            patches.mkdir(parents=True)
            (patches / "0001-fixture.patch").write_text(MODIFIED + CREATED, encoding="utf-8")

            src = root / "src"
            created = src / "chrome/browser/resources/sunshine_security/app.css"
            upstream = src / "chrome/common/webui_url_constants.h"
            build_output = src / "out/Sunshine/chrome.exe"
            for path in (created, upstream, build_output):
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("x", encoding="utf-8")

            original = bootstrap.ROOT
            bootstrap.ROOT = root
            try:
                bootstrap.remove_created_paths(src, ["0001-fixture.patch"])
            finally:
                bootstrap.ROOT = original

            self.assertFalse(created.exists())
            self.assertTrue(upstream.exists())
            # The reason `git clean` was not the fix.
            self.assertTrue(build_output.exists())

    def test_a_path_that_is_already_gone_is_not_an_error(self):
        # The cold-workspace case, which is every first build.
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            patches = root / "downstream/patches"
            patches.mkdir(parents=True)
            (patches / "0001-fixture.patch").write_text(CREATED, encoding="utf-8")

            original = bootstrap.ROOT
            bootstrap.ROOT = root
            try:
                bootstrap.remove_created_paths(root / "src", ["0001-fixture.patch"])
            finally:
                bootstrap.ROOT = original


if __name__ == "__main__":
    unittest.main()
