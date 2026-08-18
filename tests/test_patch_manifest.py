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


class SeamExtensionTests(unittest.TestCase):
    """`docs/decisions/0007-module-contribution-seam.md`: a path this stack
    creates is Sunshine's own file, and once created a later patch may extend
    it -- the shape needed for a second surface patch to register itself in a
    seam patch's registry file without re-touching upstream.
    """

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

    def write_new_file(self, name: str, target: str) -> None:
        (self.patch_dir / name).write_text(
            f"diff --git a/{target} b/{target}\n"
            "new file mode 100644\n"
            "index 0000000..1111111\n"
            "--- /dev/null\n"
            f"+++ b/{target}\n"
            "@@ -0,0 +1 @@\n+new\n",
            encoding="utf-8",
        )

    def series(self, *entries: str) -> None:
        (self.patch_dir / "series").write_text("\n".join(entries) + "\n", encoding="utf-8")

    def test_a_created_registry_file_may_be_extended_by_a_later_patch(self) -> None:
        """The seam creates the registry; each surface patch appends to it."""

        self.write_new_file("0001-seam.patch", "chrome/browser/ui/webui/sunshine/registry.cc")
        self.write("0002-security-surface.patch", "chrome/browser/ui/webui/sunshine/registry.cc")
        self.series("0001-seam.patch", "0002-security-surface.patch")

        owners = self.module.validate(self.root)
        self.assertEqual(
            ["0001-seam.patch", "0002-security-surface.patch"],
            owners["chrome/browser/ui/webui/sunshine/registry.cc"],
        )

    def test_a_third_patch_may_extend_the_same_registry_too(self) -> None:
        self.write_new_file("0001-seam.patch", "chrome/browser/ui/webui/sunshine/registry.cc")
        self.write("0002-security-surface.patch", "chrome/browser/ui/webui/sunshine/registry.cc")
        self.write("0003-workspace-surface.patch", "chrome/browser/ui/webui/sunshine/registry.cc")
        self.series("0001-seam.patch", "0002-security-surface.patch", "0003-workspace-surface.patch")

        owners = self.module.validate(self.root)
        self.assertEqual(3, len(owners["chrome/browser/ui/webui/sunshine/registry.cc"]))

    def test_two_patches_independently_creating_the_same_path_still_conflicts(self) -> None:
        """Extension is allowed; two origins for one path is still a mistake."""

        self.write_new_file("0001-one.patch", "chrome/browser/ui/webui/sunshine/registry.cc")
        self.write_new_file("0002-two.patch", "chrome/browser/ui/webui/sunshine/registry.cc")
        self.series("0001-one.patch", "0002-two.patch")
        with self.assertRaisesRegex(self.module.ManifestError, "overlaps"):
            self.module.validate(self.root)

    def test_upstream_files_still_reject_a_second_surface_naively_built(self) -> None:
        """The regression this refinement must not introduce.

        Reproduces the collision `docs/decisions/0007-module-contribution-seam.md`
        recorded: two surface patches, each modifying the same seven upstream
        files directly (the shape before a seam exists), must still conflict.
        Only paths the stack itself creates lose their exclusivity -- these
        seven do not.
        """

        shared_upstream = (
            "chrome/common/webui_url_constants.h",
            "chrome/common/webui_url_constants.cc",
            "chrome/browser/ui/webui/chrome_web_ui_configs.cc",
            "chrome/browser/ui/webui/BUILD.gn",
            "chrome/browser/resources/BUILD.gn",
            "chrome/chrome_paks.gni",
            "tools/gritsettings/resource_ids.spec",
        )
        names = [f"security-surface-{i}" for i in range(len(shared_upstream))] + [
            f"workspace-surface-{i}" for i in range(len(shared_upstream))
        ]
        entries = [f"{number:04d}-{name}.patch" for number, name in enumerate(names, start=1)]
        for entry, target in zip(entries, list(shared_upstream) * 2):
            self.write(entry, target)
        self.series(*entries)
        with self.assertRaisesRegex(self.module.ManifestError, "overlaps"):
            self.module.validate(self.root)

    def test_the_summary_line_reports_extension_separately_from_creation(self) -> None:
        self.write_new_file("0001-seam.patch", "chrome/browser/ui/webui/sunshine/registry.cc")
        self.write("0002-surface.patch", "chrome/browser/ui/webui/sunshine/registry.cc")
        self.write("0003-branding.patch", "chrome/app/BRANDING")
        self.series("0001-seam.patch", "0002-surface.patch", "0003-branding.patch")
        owners = self.module.validate(self.root)
        self.assertEqual(2, len(owners))


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

    def write_new_file(self, name: str, target: str) -> None:
        """A patch that adds a file upstream does not have."""

        (self.patch_dir / name).write_text(
            f"diff --git a/{target} b/{target}\n"
            "new file mode 100644\n"
            "index 0000000..1111111\n"
            "--- /dev/null\n"
            f"+++ b/{target}\n"
            "@@ -0,0 +1 @@\n+new\n",
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

    def test_a_created_file_is_owned_but_is_not_an_upstream_path(self) -> None:
        """The two answers a target needs, and they are not the same answer.

        `verify_pinned_upstream.py` builds its temp tree by fetching every path
        `--paths` names. A file the stack *creates* has no pinned revision to
        fetch, so naming it there turns a correct patch into a 404 reported as
        a missing upstream file -- and the whole point of that checker's
        `ABSENT_STATUS` handling is that it never reports a path as absent
        unless it really asked and really was told no.
        """

        self.write("0001-branding.patch", "chrome/app/BRANDING")
        self.write_new_file("0002-surface.patch", "chrome/browser/ui/webui/sunshine/ui.cc")
        self.series("0001-branding.patch", "0002-surface.patch")

        owners = self.module.validate(self.root)
        self.assertEqual(
            ["0002-surface.patch"], owners["chrome/browser/ui/webui/sunshine/ui.cc"]
        )
        self.assertEqual(
            ["chrome/app/BRANDING"], self.module.upstream_targets(self.root)
        )

    def test_two_patches_may_not_create_the_same_file(self) -> None:
        """Exclusive ownership covers creation as much as modification."""

        self.write_new_file("0001-one.patch", "chrome/browser/sunshine/ui.cc")
        self.write_new_file("0002-two.patch", "chrome/browser/sunshine/ui.cc")
        self.series("0001-one.patch", "0002-two.patch")
        with self.assertRaisesRegex(self.module.ManifestError, "overlaps"):
            self.module.validate(self.root)

    def test_a_modified_file_is_still_an_upstream_path(self) -> None:
        """The `--- a/path` form must not be swept up by the new distinction."""

        self.write("0001-branding.patch", "chrome/app/BRANDING")
        self.series("0001-branding.patch")
        self.assertEqual(
            ["chrome/app/BRANDING"], self.module.upstream_targets(self.root)
        )
        self.assertEqual(set(), self.module.created_paths(self.root, ["0001-branding.patch"]))

    def test_the_real_stack_never_asks_upstream_for_a_path_it_creates(self) -> None:
        """The repository's own patch files, not a fixture.

        Read from the directory rather than through `read_manifest`, so that a
        patch which exists but is not yet listed in the series -- the state a
        stack is in while a wave is under review -- is still checked here.
        Making the series and the directory agree belongs to
        `test_patch_integrity.RepositoryTests` and is left there.

        Two independent signals in each patch have to say the same thing: git
        writes a `new file mode` header for a file it adds, and it writes
        `--- /dev/null` for the same file. If a hand-edit ever leaves one
        without the other, the manifest's answer to "is this an upstream path?"
        stops matching what `git apply` will actually do.
        """

        directory = ROOT / "downstream/patches"
        entries = sorted(path.name for path in directory.glob("*.patch"))
        self.assertTrue(entries, "the repository has no patches to check")

        created = self.module.created_paths(ROOT, entries)
        modified = set()
        for entry in entries:
            text = (directory / entry).read_text(encoding="utf-8")
            sections = self.module.patch_sections(text)
            modified.update(target for target, is_new in sections if not is_new)
            self.assertEqual(
                text.count("\nnew file mode "),
                sum(1 for _target, is_new in sections if is_new),
                f"{entry}: `new file mode` headers and `--- /dev/null` sections disagree",
            )

        self.assertEqual(
            set(),
            created & modified,
            "a path cannot be both created and modified by the stack",
        )
        self.assertEqual(created | modified, set(self.module.patch_targets(ROOT, entries)))


if __name__ == "__main__":
    unittest.main()

