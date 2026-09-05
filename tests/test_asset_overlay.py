"""Tests for the binary asset overlay guard.

The overlay carries the one kind of change a unified diff cannot express, and
it pays for that with a failure mode the patch stack does not have: a copy
always succeeds. `git apply` refuses a hunk whose context moved, which is what
makes an upstream restructure loud; `shutil.copyfile` writes wherever it is
pointed. So the checks here are what stand in for the conflict that will never
happen -- see `docs/decisions/0008-binary-asset-overlay.md`.

Fixtures are synthesised, and the committed icons are never mutated. A guard
tested by editing the artifact it guards passes by construction.

The cases asserting that a *valid* overlay is accepted carry as much weight as
the rejections. An icon parser strict about the wrong byte rejects a file
Windows loads happily, and a guard that does that gets deleted rather than
fixed.
"""

from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import unittest
import unittest.mock

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY_ROOT / "scripts"))

import verify_asset_overlay as overlay  # noqa: E402


def build_ico(sizes=(16, 32, 48, 256), *, payload=b"\x89PNG-not-really", truncate=False) -> bytes:
    """A structurally valid icon whose image data is arbitrary.

    The guard reads the directory, never the images, and that is deliberate:
    decoding PNG and BMP is what Pillow is for, and the guard is stdlib-only so
    that CI never needs it. So the fixture only has to be honest about the
    directory.
    """

    count = len(sizes)
    header = struct.pack("<HHH", 0, 1, count)
    offset = len(header) + count * 16
    entries = b""
    images = b""
    for size in sizes:
        entries += struct.pack(
            "<BBBBHHII",
            0 if size == 256 else size,
            0 if size == 256 else size,
            0,
            0,
            1,
            32,
            len(payload),
            offset + len(images),
        )
        images += payload
    data = header + entries + images
    return data[: len(data) - 1] if truncate else data


class OverlayFileTests(unittest.TestCase):
    def test_the_mirrored_path_is_the_destination(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target = root / "downstream/assets/chrome/app/theme/chromium/win/chromium.ico"
            target.parent.mkdir(parents=True)
            target.write_bytes(build_ico())

            self.assertEqual(
                sorted(overlay.overlay_files(root)),
                ["chrome/app/theme/chromium/win/chromium.ico"],
            )

    def test_no_overlay_directory_is_not_a_failure(self):
        with tempfile.TemporaryDirectory() as directory:
            self.assertEqual(overlay.overlay_files(Path(directory)), {})

    def test_an_empty_asset_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target = root / "downstream/assets/chrome/app/theme/chromium/win/chromium.ico"
            target.parent.mkdir(parents=True)
            target.write_bytes(b"")

            with self.assertRaises(overlay.OverlayError):
                overlay.overlay_files(root)


class IconStructureTests(unittest.TestCase):
    def size_of(self, data: bytes) -> set[int]:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "icon.ico"
            path.write_bytes(data)
            return overlay.ico_sizes(path)

    def test_the_four_upstream_sizes_are_read(self):
        self.assertEqual(self.size_of(build_ico()), {16, 32, 48, 256})

    def test_zero_in_the_directory_means_256(self):
        # The width field is one byte, so 256 does not fit and upstream's own
        # icons store it as 0. Reading that literally would report a 0px entry.
        self.assertIn(256, self.size_of(build_ico(sizes=(256,))))

    def test_a_truncated_icon_is_rejected(self):
        with self.assertRaises(overlay.OverlayError):
            self.size_of(build_ico(truncate=True))

    def test_a_file_that_is_not_an_icon_is_rejected(self):
        with self.assertRaises(overlay.OverlayError):
            self.size_of(b"\x89PNG\r\n\x1a\n" + b"\x00" * 64)

    def test_an_icon_declaring_no_images_is_rejected(self):
        with self.assertRaises(overlay.OverlayError):
            self.size_of(struct.pack("<HHH", 0, 1, 0))

    def test_an_entry_with_no_image_data_is_rejected(self):
        with self.assertRaises(overlay.OverlayError):
            self.size_of(build_ico(payload=b""))


class CommittedOverlayTests(unittest.TestCase):
    """The real overlay, as committed. These are the assertions that would fail
    if somebody replaced an icon with something Windows cannot load."""

    def test_the_committed_overlay_passes_its_own_guard(self):
        self.assertEqual(overlay.validate(REPOSITORY_ROOT), [])

    def test_both_windows_icons_are_present_and_complete(self):
        files = overlay.overlay_files(REPOSITORY_ROOT)
        for destination in (
            "chrome/app/theme/chromium/win/chromium.ico",
            "chrome/installer/mini_installer/mini_installer.ico",
        ):
            with self.subTest(destination=destination):
                self.assertIn(destination, files)
                self.assertEqual(
                    overlay.ico_sizes(files[destination]),
                    set(overlay.REQUIRED_ICO_SIZES),
                )

    def test_every_overlay_file_is_tracked_by_git(self):
        # The regression this pins: `.gitignore` carried an unanchored
        # `chromium/`, which matches a directory of that name at any depth, and
        # it swallowed `.../theme/chromium/win/chromium.ico`. Every other check
        # passed, because the file was on the disk of the machine running them.
        files = overlay.overlay_files(REPOSITORY_ROOT)
        self.assertEqual(overlay.untracked(REPOSITORY_ROOT, sorted(files)), [])

    def test_an_ignored_overlay_file_is_reported(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            subprocess.run(["git", "-C", str(root), "init", "--quiet"], check=True)
            (root / ".gitignore").write_text("chromium/\n", encoding="utf-8")
            target = root / "downstream/assets/chrome/app/theme/chromium/win/chromium.ico"
            target.parent.mkdir(parents=True)
            target.write_bytes(build_ico())
            subprocess.run(["git", "-C", str(root), "add", "-A"], check=True)

            self.assertEqual(
                overlay.untracked(root, ["chrome/app/theme/chromium/win/chromium.ico"]),
                ["chrome/app/theme/chromium/win/chromium.ico"],
            )

    def test_tracked_ness_is_unknown_rather_than_false_outside_a_checkout(self):
        # Reporting every asset as untracked where git cannot answer would fail
        # a release tarball for a reason that is not true of it.
        with tempfile.TemporaryDirectory() as directory:
            self.assertEqual(overlay.untracked(Path(directory), ["some/asset.ico"]), [])

    def test_no_overlay_path_is_also_claimed_by_the_patch_stack(self):
        # The overlay copies after the patches, so an overlap would discard a
        # patch's edit with every command in the pipeline reporting success.
        self.assertEqual(
            set(overlay.overlay_files(REPOSITORY_ROOT)) & overlay.patch_targets(REPOSITORY_ROOT),
            set(),
        )


class AdditionTests(unittest.TestCase):
    """An overlay file upstream does not have, and the three ways it goes wrong.

    The declaration is the point of these. Recognising an addition by asking
    upstream would make a mistyped destination -- one letter out of
    `default_200_percent` -- answer "upstream does not have it" and be waved
    through as an addition, skipping the probe that exists to catch exactly
    that. So every case here is a disagreement between the declaration and
    something real.
    """

    def build_root(self, directory, *, patch_body="", series=("0026-x.patch",)):
        root = Path(directory)
        (root / "downstream/patches").mkdir(parents=True)
        (root / "downstream/patches/series").write_text(
            "\n".join(series) + "\n", encoding="utf-8")
        for name in series:
            (root / "downstream/patches" / name).write_text(patch_body, encoding="utf-8")
        return root

    def test_the_grd_reference_is_the_path_below_the_scale_directory(self):
        # theme_resources.grd's `file=` attribute is relative to the scale
        # directory, so that is the string a patch has to contain.
        self.assertEqual(
            "sunshine/bookmark_folder.png",
            overlay.grd_reference(
                "chrome/app/theme/default_200_percent/sunshine/bookmark_folder.png"),
        )

    def test_a_path_outside_a_scale_directory_falls_back_to_its_name(self):
        self.assertEqual(
            "chromium.ico",
            overlay.grd_reference("chrome/app/theme/chromium/win/chromium.ico"))

    def test_a_declared_addition_missing_from_the_overlay_is_reported(self):
        with tempfile.TemporaryDirectory() as directory:
            root = self.build_root(directory)
            failures = []
            with unittest.mock.patch.dict(
                    overlay.ADDITIONS, {"a/b.png": "0026-x.patch"}, clear=True):
                overlay.check_additions({}, root, failures)
            self.assertTrue(any("is not in the overlay" in line for line in failures),
                            failures)

    def test_an_addition_whose_patch_is_not_in_the_series_is_reported(self):
        with tempfile.TemporaryDirectory() as directory:
            root = self.build_root(directory, series=("0001-other.patch",))
            failures = []
            with unittest.mock.patch.dict(
                    overlay.ADDITIONS, {"a/b.png": "0026-x.patch"}, clear=True):
                overlay.check_additions({"a/b.png": root}, root, failures)
            self.assertTrue(any("not in downstream/patches/series" in line
                                for line in failures), failures)

    def test_an_addition_no_patch_names_is_reported(self):
        # An image nothing reads is an image the build ignores, and the build
        # says nothing about it: grit only complains about a `file=` with no
        # file, never a file with no `file=`.
        with tempfile.TemporaryDirectory() as directory:
            root = self.build_root(directory, patch_body="+something else\n")
            failures = []
            with unittest.mock.patch.dict(
                    overlay.ADDITIONS,
                    {"chrome/app/theme/default_100_percent/s/f.png": "0026-x.patch"},
                    clear=True):
                overlay.check_additions(
                    {"chrome/app/theme/default_100_percent/s/f.png": root},
                    root, failures)
            self.assertTrue(any("no patch adds a line naming" in line
                                for line in failures), failures)

    def test_a_reference_in_patch_context_does_not_count(self):
        # A path already in an upstream file is a path upstream already reads,
        # which is the opposite of what an addition has to prove. Only added
        # lines count, so the same text as context must still fail.
        with tempfile.TemporaryDirectory() as directory:
            root = self.build_root(directory, patch_body=" s/f.png\n-s/f.png\n")
            failures = []
            with unittest.mock.patch.dict(
                    overlay.ADDITIONS,
                    {"chrome/app/theme/default_100_percent/s/f.png": "0026-x.patch"},
                    clear=True):
                overlay.check_additions(
                    {"chrome/app/theme/default_100_percent/s/f.png": root},
                    root, failures)
            self.assertTrue(any("no patch adds a line naming" in line
                                for line in failures), failures)

    def test_a_scale_set_with_a_hole_is_reported(self):
        # fallback_to_low_resolution="true" means a missing 200 percent image
        # does not fail the build. Chrome upscales the 100 percent one, and the
        # icon is soft on exactly the machines that have the pixels for it.
        with tempfile.TemporaryDirectory() as directory:
            root = self.build_root(directory, patch_body="+s/f.png\n")
            files = {
                "chrome/app/theme/default_100_percent/s/f.png": root,
                "chrome/app/theme/default_300_percent/s/f.png": root,
            }
            failures = []
            with unittest.mock.patch.dict(
                    overlay.ADDITIONS,
                    {name: "0026-x.patch" for name in files}, clear=True):
                overlay.check_additions(files, root, failures)
            self.assertTrue(any("default_200_percent counterpart" in line
                                for line in failures), failures)

    def test_the_committed_additions_are_declared_and_complete(self):
        failures = []
        overlay.check_additions(
            overlay.overlay_files(REPOSITORY_ROOT), REPOSITORY_ROOT, failures)
        self.assertEqual([], failures)

    def test_every_committed_addition_is_a_theme_image_at_three_scales(self):
        by_reference = {}
        for destination in overlay.ADDITIONS:
            by_reference.setdefault(overlay.grd_reference(destination), set()).add(
                next(part for part in Path(destination).parts
                     if part in overlay.THEME_SCALE_DIRECTORIES))
        self.assertTrue(by_reference)
        for reference, scales in by_reference.items():
            self.assertEqual(set(overlay.THEME_SCALE_DIRECTORIES), scales, reference)


class UpstreamProbeDirectionTests(unittest.TestCase):
    """The probe asks a different question of each kind, and both matter.

    A replacement upstream renamed leaves the build shipping Chromium's bytes
    under Sunshine's name. An addition upstream has since grown leaves the copy
    quietly replacing a real resource -- and the patch's `.grd` entry may now be
    reading upstream's drawing instead of the owner's.
    """

    def setUp(self):
        sys.path.insert(0, str(REPOSITORY_ROOT / "scripts"))
        import verify_pinned_upstream  # noqa: PLC0415

        self.pinned = verify_pinned_upstream

    def run_probe(self, present):
        report = []
        with unittest.mock.patch.object(self.pinned, "exists",
                                        lambda *args, **kwargs: present):
            healthy = self.pinned.check_asset_overlay(
                "github", "unused", REPOSITORY_ROOT, report)
        return healthy, report

    def test_an_addition_upstream_already_has_is_a_failure(self):
        healthy, report = self.run_probe(True)
        self.assertFalse(healthy)
        self.assertTrue(any("addition already exists upstream" in line
                            for line in report), report)

    def test_a_replacement_upstream_lost_is_a_failure(self):
        healthy, report = self.run_probe(False)
        self.assertFalse(healthy)
        self.assertTrue(any("destination absent upstream" in line
                            for line in report), report)


class BootstrapWiringTests(unittest.TestCase):
    """The guard can only check what the build actually copies. These pin the
    two places `bootstrap_chromium.py` has to agree with it."""

    def setUp(self):
        sys.path.insert(0, str(REPOSITORY_ROOT / "scripts"))
        import bootstrap_chromium  # noqa: PLC0415

        self.bootstrap = bootstrap_chromium

    def test_bootstrap_and_the_guard_see_the_same_files(self):
        self.assertEqual(
            sorted(self.bootstrap.overlay_assets()),
            sorted(overlay.overlay_files(REPOSITORY_ROOT)),
        )

    def test_a_missing_destination_stops_the_bootstrap(self):
        # Copying into a checkout that does not have the file would produce a
        # build that silently keeps Chromium's icon, since the `.rc` names a
        # path by hand and nothing would have written it. Only replacements are
        # asked this; an addition has nothing to be missing.
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(SystemExit) as raised:
                self.bootstrap.apply_overlay(Path(directory))
            self.assertIn("not in the Chromium checkout", str(raised.exception))

    def test_an_addition_upstream_already_has_stops_the_bootstrap(self):
        # The mirror of the case above, and the reason additions are declared:
        # a file already there is a real Chromium resource this would replace.
        with tempfile.TemporaryDirectory() as directory:
            checkout = Path(directory)
            for destination in overlay.overlay_files(REPOSITORY_ROOT):
                target = checkout / destination
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(b"upstream")
            with self.assertRaises(SystemExit) as raised:
                self.bootstrap.apply_overlay(checkout)
            self.assertIn("declared an addition, but upstream has it",
                          str(raised.exception))

    def test_an_addition_brings_its_own_directory(self):
        # `sunshine/` under each scale directory does not exist upstream, so a
        # copy without mkdir would fail on a real checkout and nowhere else.
        with tempfile.TemporaryDirectory() as directory:
            checkout = Path(directory)
            for destination in overlay.overlay_files(REPOSITORY_ROOT):
                if destination in overlay.ADDITIONS:
                    continue
                target = checkout / destination
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(b"upstream")
            self.bootstrap.apply_overlay(checkout)
            for destination in overlay.ADDITIONS:
                self.assertTrue((checkout / destination).is_file(), destination)


if __name__ == "__main__":
    unittest.main()
