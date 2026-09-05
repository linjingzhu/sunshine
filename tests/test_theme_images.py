"""Tests for the theme image renderer.

`chrome/app/theme/theme_resources.grd` reads one image per scale factor out of
three sibling directories, and nothing derives them from each other. Three
files that have to be the same drawing at three sizes is three chances for one
of them to be a different drawing, or the wrong size, or absent -- and absent
is the quiet one: `fallback_to_low_resolution="true"` means the build upscales
the 100 percent image and says nothing.

So the checks that matter here are the arithmetic and the agreement: that the
scales are exact multiples of the base, and that every image the renderer owns
is a destination the overlay guard has declared. Those need no Pillow and run
in CI. The drawing itself does need Pillow, which CI does not install -- the
rendered images are committed precisely so that it does not have to -- so those
cases skip rather than fail.
"""

import io
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY_ROOT / "scripts"))

import render_theme_images as renderer  # noqa: E402
import verify_asset_overlay as overlay  # noqa: E402

try:
    from PIL import Image
except ModuleNotFoundError:  # pragma: no cover - depends on the machine
    Image = None

needs_pillow = unittest.skipIf(Image is None, "Pillow is not installed")


class TargetTests(unittest.TestCase):
    def test_every_family_is_rendered_at_every_scale(self):
        self.assertEqual(len(renderer.FAMILIES) * len(renderer.SCALES),
                         len(renderer.targets()))

    def test_the_scales_are_exact_multiples_of_the_base(self):
        # A 47 pixel image for a 24 dip slot at 200 percent is a resample at
        # draw time on every HiDPI machine, which is the blur the per-scale
        # directories exist to avoid.
        sizes = sorted({size for _, _, size in renderer.targets()})
        self.assertEqual(
            [renderer.BASE_DIP * scale // 100 for scale in sorted(renderer.SCALES)],
            sizes)
        for scale, size in zip(sorted(renderer.SCALES), sizes):
            self.assertEqual(renderer.BASE_DIP * scale, size * 100)

    def test_the_base_size_is_the_size_the_bookmark_bar_draws_today(self):
        # `GetDefaultSizeOfVectorIcon` returns the first rep of
        # folder_chrome_refresh_old.icon, which is 24, and the bar asks for no
        # size. Any other value here moves every button on the bar.
        self.assertEqual(24, renderer.BASE_DIP)

    def test_every_rendered_image_is_a_declared_overlay_addition(self):
        # The renderer writes into the overlay; the overlay guard is what tells
        # `verify_pinned_upstream` to ask whether upstream has the path. An
        # image written but never declared would be copied into the checkout
        # with nothing asking that question.
        for _, destination, _ in renderer.targets():
            relative = destination.relative_to(REPOSITORY_ROOT).as_posix()
            self.assertTrue(relative.startswith("downstream/assets/"), relative)
            self.assertIn(relative.removeprefix("downstream/assets/"),
                          overlay.ADDITIONS, relative)

    def test_every_source_is_committed(self):
        for source, _, _ in renderer.targets():
            self.assertTrue(source.is_file(), source)


@needs_pillow
class RenderTests(unittest.TestCase):
    def source(self, directory, *, inset=40, size=200, alpha=255):
        """A small opaque square adrift in a large transparent canvas."""

        art = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        for x in range(inset, size - inset):
            for y in range(inset + 20, size - inset - 20):
                art.putpixel((x, y), (10, 20, 30, alpha))
        path = Path(directory) / "art.png"
        art.save(path)
        return path

    def test_the_output_is_a_square_png_of_the_requested_size(self):
        with tempfile.TemporaryDirectory() as directory:
            data = renderer.render(self.source(directory), 24)
            with Image.open(io.BytesIO(data)) as image:
                self.assertEqual("PNG", image.format)
                self.assertEqual((24, 24), image.size)

    def test_the_transparent_margin_is_cropped_away(self):
        # A bookmark bar button sizes itself to the image it is given, so
        # shipping the source's margin would draw the folder at a fraction of
        # the slot and align it with nothing beside it.
        with tempfile.TemporaryDirectory() as directory:
            data = renderer.render(self.source(directory), 48)
            with Image.open(io.BytesIO(data)) as image:
                bounds = image.convert("RGBA").getchannel("A").getbbox()
        # The drawing is wider than it is tall, so it touches left and right.
        self.assertEqual(0, bounds[0])
        self.assertEqual(48, bounds[2])
        self.assertGreater(bounds[1], 0)
        self.assertLess(bounds[3], 48)

    def test_an_entirely_transparent_source_is_refused(self):
        with tempfile.TemporaryDirectory() as directory:
            blank = Path(directory) / "blank.png"
            Image.new("RGBA", (32, 32), (0, 0, 0, 0)).save(blank)
            with self.assertRaises(SystemExit):
                renderer.render(blank, 24)

    def test_the_committed_images_are_a_fresh_render_of_the_source(self):
        # This is what makes the committed output trustworthy without running
        # the renderer in CI, and what would catch artwork replaced in
        # `resource/` without the theme images being rewritten.
        result = subprocess.run(
            [sys.executable, str(REPOSITORY_ROOT / "scripts/render_theme_images.py"),
             "--check"],
            capture_output=True, text=True, check=False)
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
