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
        # path by hand and nothing would have written it.
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(SystemExit):
                self.bootstrap.apply_overlay(Path(directory))


if __name__ == "__main__":
    unittest.main()
