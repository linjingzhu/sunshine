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

    def test_the_source_margin_is_discarded_and_COVERAGE_put_back(self):
        """Both halves, and the fixture is what tells them apart.

        The source is 120 pixels of drawing adrift in a 200-pixel canvas, so
        it fills 60% of its own canvas. A renderer that skipped the crop and
        merely scaled the whole canvas would leave ink across 0.60 * COVERAGE
        of the box -- 48% at COVERAGE 0.8 -- while one that crops first leaves
        exactly COVERAGE. Asserting the width therefore proves the crop
        happened as well as the inset, which a bounds-touch assertion did not.
        """

        size = 48
        with tempfile.TemporaryDirectory() as directory:
            data = renderer.render(self.source(directory), size)
            with Image.open(io.BytesIO(data)) as image:
                bounds = image.convert("RGBA").getchannel("A").getbbox()

        width = bounds[2] - bounds[0]
        self.assertAlmostEqual(size * renderer.COVERAGE, width, delta=1)
        # Centred: the margin is the same on both sides, to a pixel of rounding.
        self.assertAlmostEqual(bounds[0], size - bounds[2], delta=1)
        self.assertAlmostEqual(bounds[1], size - bounds[3], delta=1)
        # And it is a margin, not a crop to the edge -- which is the whole
        # point of the change and what the previous version of this test
        # asserted the opposite of.
        self.assertGreater(bounds[0], 0)
        self.assertLess(bounds[2], size)

    def test_coverage_is_a_fraction_that_leaves_a_margin(self):
        self.assertGreater(renderer.COVERAGE, 0)
        self.assertLess(renderer.COVERAGE, 1)

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


@needs_pillow
class DifferenceTests(unittest.TestCase):
    """What `--check` may forgive, and what it must not.

    It compared bytes until the self-hosted Windows runner re-rendered this
    artwork and produced different 48px and 72px images from the same source.
    The committed images were not stale; byte-identity across machines is not
    a property Pillow offers, and the check had only ever run on Linux, so
    nothing had said so. These tests draw the line where it now sits.
    """

    def art(self, *, size=48, shift=0, noise=0, alpha=255):
        art = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        for x in range(8 + shift, size - 8 + shift):
            for y in range(12, size - 12):
                if 0 <= x < size:
                    art.putpixel((x, y), (10 + noise, 20 + noise, 30 + noise, alpha))
        return art

    def encoded(self, image, **save):
        buffer = io.BytesIO()
        image.save(buffer, format="PNG", **save)
        return buffer.getvalue()

    def test_the_same_pixels_encoded_differently_are_not_a_difference(self):
        """The failure that started this: re-encoding is not staleness."""

        art = self.art()
        loose = self.encoded(art, optimize=False, compress_level=1)
        tight = self.encoded(art, optimize=True)
        self.assertNotEqual(loose, tight)
        worst, why = renderer.difference(loose, tight)
        self.assertEqual("", why)
        self.assertEqual(0, worst)

    def test_colour_under_a_transparent_pixel_is_not_a_difference(self):
        """Two encoders may write anything under `alpha == 0`.

        Comparing raw RGBA would call these 255 apart and make the check
        useless, which is why colour is compared composited over black.
        """

        clear_black = Image.new("RGBA", (8, 8), (0, 0, 0, 0))
        clear_white = Image.new("RGBA", (8, 8), (255, 255, 255, 0))
        worst, why = renderer.difference(self.encoded(clear_black),
                                         self.encoded(clear_white))
        self.assertEqual("", why)
        self.assertEqual(0, worst)

    def test_ink_that_moved_is_a_difference(self):
        """A changed COVERAGE or BASE_DIP, which is what this must still catch.

        Moving the drawing by one pixel is far smaller than either would do,
        and it already exceeds TOLERANCE by a wide margin.
        """

        worst, why = renderer.difference(self.encoded(self.art()),
                                         self.encoded(self.art(shift=1)))
        self.assertEqual("", why)
        self.assertGreater(worst, renderer.TOLERANCE)

    def test_a_different_size_is_refused_without_comparing_pixels(self):
        worst, why = renderer.difference(self.encoded(self.art(size=48)),
                                         self.encoded(self.art(size=24)))
        self.assertIn("48x48", why)
        self.assertIn("24x24", why)
        self.assertEqual(255, worst)

    def test_tolerance_is_small_enough_to_be_invisible(self):
        """It forgives a resampler, not a recolour.

        8/255 is about 3%. The check is allowed to miss a difference nobody
        can see; it is not allowed to miss a different drawing.
        """

        self.assertGreater(renderer.TOLERANCE, 0)
        self.assertLessEqual(renderer.TOLERANCE, 16)

    def test_a_shade_within_tolerance_passes_and_beyond_it_does_not(self):
        base = self.encoded(self.art())
        inside, why = renderer.difference(base, self.encoded(self.art(noise=renderer.TOLERANCE)))
        self.assertEqual("", why)
        self.assertLessEqual(inside, renderer.TOLERANCE)
        outside, why = renderer.difference(base, self.encoded(self.art(noise=renderer.TOLERANCE + 20)))
        self.assertEqual("", why)
        self.assertGreater(outside, renderer.TOLERANCE)


if __name__ == "__main__":
    unittest.main()
