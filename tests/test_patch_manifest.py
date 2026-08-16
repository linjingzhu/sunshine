"""Tests for ordered, exclusive Chromium downstream patch ownership."""

from pathlib import Path
import importlib.util
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/patch_manifest.py"


def load_manifest():
    spec = importlib.util.spec_from_file_location("patch_manifest", SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError("Unable to load patch manifest verifier")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class PatchManifestTests(unittest.TestCase):
    def setUp(self) -> None:
        self.module = load_manifest()
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.patch_dir = self.root / "downstream/patches"
        self.patch_dir.mkdir(parents=True)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def write(self, name: str, target: str) -> None:
        (self.patch_dir / name).write_text(
            f"diff --git a/{target} b/{target}\n"
            f"--- a/{target}\n"
            f"+++ b/{target}\n"
            "@@ -1 +1 @@\n-old\n+new\n",
            encoding="utf-8",
        )

    def series(self, *entries: str) -> None:
        (self.patch_dir / "series").write_text("\n".join(entries) + "\n", encoding="utf-8")

    def test_valid_exclusive_stack(self) -> None:
        self.write("0001-branding.patch", "chrome/app/BRANDING")
        self.write("0002-new-tab.patch", "chrome/browser/new_tab.html")
        self.series("0001-branding.patch", "0002-new-tab.patch")
        owners = self.module.validate(self.root)
        self.assertEqual(["0001-branding.patch"], owners["chrome/app/BRANDING"])

    def test_duplicate_series_entry_fails(self) -> None:
        self.write("0001-branding.patch", "chrome/app/BRANDING")
        self.series("0001-branding.patch", "0001-branding.patch")
        with self.assertRaisesRegex(self.module.ManifestError, "duplicate"):
            self.module.validate(self.root)

    def test_unlisted_patch_fails(self) -> None:
        self.write("0001-branding.patch", "chrome/app/BRANDING")
        self.write("0002-orphan.patch", "chrome/app/orphan")
        self.series("0001-branding.patch")
        with self.assertRaisesRegex(self.module.ManifestError, "unlisted"):
            self.module.validate(self.root)

    def test_non_contiguous_numbering_fails(self) -> None:
        self.write("0001-branding.patch", "chrome/app/BRANDING")
        self.write("0003-gap.patch", "chrome/app/gap")
        self.series("0001-branding.patch", "0003-gap.patch")
        with self.assertRaisesRegex(self.module.ManifestError, "contiguous"):
            self.module.validate(self.root)

    def test_path_traversal_fails(self) -> None:
        self.write("0001-branding.patch", "chrome/app/BRANDING")
        self.series("../0001-branding.patch")
        with self.assertRaisesRegex(self.module.ManifestError, "traversal"):
            self.module.validate(self.root)

    def test_overlapping_patch_targets_fail(self) -> None:
        self.write("0001-branding.patch", "chrome/app/shared.cc")
        self.write("0002-feature.patch", "chrome/app/shared.cc")
        self.series("0001-branding.patch", "0002-feature.patch")
        with self.assertRaisesRegex(self.module.ManifestError, "overlaps"):
            self.module.validate(self.root)


if __name__ == "__main__":
    unittest.main()

