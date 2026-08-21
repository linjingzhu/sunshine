"""Tests for the copy of the module registry the module home is served.

The thing under test is a *copy*, which is the whole reason the guard exists.
So the tests that matter are the ones that prove the guard notices when the two
sides stop agreeing -- a guard that only ever passes on the real repository is
indistinguishable from one that always passes.
"""

import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY_ROOT / "scripts"))

import module_registry_payload as canonical  # noqa: E402
import verify_module_registry_sync as sync  # noqa: E402


class CanonicalFormTests(unittest.TestCase):
    def test_the_payload_is_sorted_and_reproducible(self) -> None:
        first = canonical.payload()
        self.assertEqual(first, canonical.payload())
        document = json.loads(first)
        self.assertEqual(
            json.dumps(document, indent=2, sort_keys=True) + "\n", first
        )

    def test_it_carries_whole_manifests_not_a_projection(self) -> None:
        """A projection would be a second schema. Every manifest key survives."""

        document = json.loads(canonical.payload())
        registry = json.loads(
            (REPOSITORY_ROOT / "first_party/registry.json").read_text(encoding="utf-8")
        )
        self.assertEqual(len(registry["modules"]), len(document["modules"]))
        for relative, served in zip(registry["modules"], document["modules"]):
            source = json.loads((REPOSITORY_ROOT / relative).read_text(encoding="utf-8"))
            self.assertEqual(source, served)

    def test_the_literal_accounts_for_the_opening_newline(self) -> None:
        self.assertEqual("\n" + canonical.payload(), canonical.literal())

    def test_the_payload_cannot_close_the_raw_string(self) -> None:
        """`)json"` inside the payload would end the literal early and the
        header would not compile. Nothing in a manifest can produce it today;
        this fails if something ever does."""

        self.assertNotIn(')json"', canonical.payload())


class SyncTests(unittest.TestCase):
    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory()
        self.root = Path(self.directory.name)
        self.addCleanup(self.directory.cleanup)
        shutil.copytree(REPOSITORY_ROOT / "first_party", self.root / "first_party")
        patches = self.root / "downstream/patches"
        patches.mkdir(parents=True)
        self.patch = patches / sync.PATCH_NAME
        shutil.copy(REPOSITORY_ROOT / "downstream/patches" / sync.PATCH_NAME, self.patch)

    def test_the_repository_as_committed_agrees(self) -> None:
        self.assertEqual([], sync.check())

    def test_a_copy_of_the_repository_agrees(self) -> None:
        self.assertEqual([], sync.check(self.root))

    def test_a_module_added_to_first_party_alone_fails(self) -> None:
        """The failure this guard exists for: the module home would not list it."""

        source = self.root / "first_party/modules/sunshine-document/module.json"
        added = self.root / "first_party/modules/sunshine-later/module.json"
        added.parent.mkdir()
        manifest = json.loads(source.read_text(encoding="utf-8"))
        manifest["id"] = "sunshine.later"
        manifest["display_name"] = "Added Later"
        manifest["entrypoints"] = [
            {"type": "chromium_webui", "target": "chrome://sunshine-later"}
        ]
        added.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

        registry_path = self.root / "first_party/registry.json"
        registry = json.loads(registry_path.read_text(encoding="utf-8"))
        registry["modules"].append("first_party/modules/sunshine-later/module.json")
        registry_path.write_text(json.dumps(registry, indent=2) + "\n", encoding="utf-8")

        self.assertNotEqual([], sync.check(self.root))

    def test_an_edited_field_fails(self) -> None:
        """Not just additions. A permission widened on one side and not the
        other is the quieter version of the same defect."""

        path = self.root / "first_party/modules/sunshine-document/module.json"
        manifest = json.loads(path.read_text(encoding="utf-8"))
        manifest["security"]["filesystem"]["access"] = "user_selected"
        path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
        self.assertNotEqual([], sync.check(self.root))

    def test_reordering_the_registry_fails(self) -> None:
        """Order is part of the canonical form: it is the order the module home
        lists modules in, so a reorder is a visible change."""

        path = self.root / "first_party/registry.json"
        registry = json.loads(path.read_text(encoding="utf-8"))
        registry["modules"].reverse()
        path.write_text(json.dumps(registry, indent=2) + "\n", encoding="utf-8")
        self.assertNotEqual([], sync.check(self.root))

    def test_a_missing_patch_is_reported_not_ignored(self) -> None:
        self.patch.unlink()
        self.assertNotEqual([], sync.check(self.root))

    def test_a_patch_that_stops_creating_the_header_is_reported(self) -> None:
        self.patch.write_text("diff --git a/x b/x\n--- a/x\n+++ b/x\n", encoding="utf-8")
        self.assertNotEqual([], sync.check(self.root))

    def test_a_header_without_the_literal_is_reported(self) -> None:
        text = self.patch.read_text(encoding="utf-8")
        self.patch.write_text(text.replace(sync.OPENING, "+// removed"), encoding="utf-8")
        self.assertNotEqual([], sync.check(self.root))


class PatchReaderTests(unittest.TestCase):
    def test_only_created_files_are_read(self) -> None:
        """A modified section's meaning depends on the file it applies to, so
        the reader must not pretend it can reconstruct one."""

        patch = "diff --git a/x b/x\n--- a/x\n+++ b/x\n@@ -1 +1,2 @@\n line\n+added\n"
        self.assertIsNone(sync.added_file(patch, "x"))

    def test_a_created_file_is_reconstructed_without_prefixes(self) -> None:
        patch = (
            "diff --git a/x b/x\nnew file mode 100644\n--- /dev/null\n+++ b/x\n"
            "@@ -0,0 +1,2 @@\n+first\n+second\n"
        )
        self.assertEqual("first\nsecond\n", sync.added_file(patch, "x"))

    def test_a_file_the_patch_does_not_touch_is_absent(self) -> None:
        patch = "diff --git a/x b/x\n--- /dev/null\n+++ b/x\n@@ -0,0 +1 @@\n+one\n"
        self.assertIsNone(sync.added_file(patch, "y"))


if __name__ == "__main__":
    unittest.main()
