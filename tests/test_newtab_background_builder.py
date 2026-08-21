"""The frame builder's pure logic, which is where its one real bug lives.

Pillow is not imported here and `scripts/build_newtab_background.py` does not
import it at module scope, so these run on a machine that has never installed
it -- which is every machine the guard workflow uses.
"""

from __future__ import annotations

from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.build_newtab_background import (  # noqa: E402
    asset_names,
    default_output,
    frame_duration_ms,
    max_asset_bytes,
    natural_key,
    ordered_frames,
    pingpong,
)


class FrameOrder(unittest.TestCase):
    def test_ten_follows_two(self):
        """The bug this tool exists to not have.

        Every lexical sort puts `frame10` before `frame2`, and the result is an
        animation that plays in the wrong order while looking like a bad export
        rather than a bad sort.
        """
        names = [Path(f"frame{i}.png") for i in (1, 2, 9, 10, 11, 100)]
        shuffled = [names[3], names[0], names[5], names[2], names[4], names[1]]
        self.assertEqual(
            [p.name for p in ordered_frames(shuffled)],
            ["frame1.png", "frame2.png", "frame9.png",
             "frame10.png", "frame11.png", "frame100.png"],
        )

    def test_zero_padded_names_are_unharmed(self):
        names = [Path(f"f{i:04d}.png") for i in range(1, 6)]
        self.assertEqual(
            [p.name for p in ordered_frames(list(reversed(names)))],
            [p.name for p in names],
        )

    def test_case_does_not_split_the_sequence(self):
        given = [Path("Frame2.png"), Path("frame1.png"), Path("FRAME3.png")]
        self.assertEqual(
            [p.name for p in ordered_frames(given)],
            ["frame1.png", "Frame2.png", "FRAME3.png"],
        )

    def test_non_frames_are_left_behind(self):
        given = [Path("a1.png"), Path(".DS_Store"), Path("notes.txt"),
                 Path("project.aep"), Path("a2.png")]
        self.assertEqual([p.name for p in ordered_frames(given)],
                         ["a1.png", "a2.png"])

    def test_numbers_elsewhere_in_the_name(self):
        given = [Path("shot2_frame10.png"), Path("shot2_frame2.png"),
                 Path("shot10_frame1.png")]
        self.assertEqual(
            [p.name for p in ordered_frames(given)],
            ["shot2_frame2.png", "shot2_frame10.png", "shot10_frame1.png"],
        )

    def test_natural_key_is_orderable_across_shapes(self):
        # Mixed int/str tuples raise TypeError when compared, so a folder whose
        # names differ in shape must not reach a comparison that throws.
        keys = sorted(natural_key(n) for n in ("a.png", "1.png", "a1.png"))
        self.assertEqual(len(keys), 3)


class PingPong(unittest.TestCase):
    def test_neither_endpoint_plays_twice(self):
        self.assertEqual(pingpong([1, 2, 3, 4]), [1, 2, 3, 4, 3, 2])

    def test_three_frames(self):
        self.assertEqual(pingpong([1, 2, 3]), [1, 2, 3, 2])

    def test_two_frames_have_no_return_trip(self):
        self.assertEqual(pingpong([1, 2]), [1, 2])

    def test_one_frame(self):
        self.assertEqual(pingpong([1]), [1])

    def test_empty(self):
        self.assertEqual(pingpong([]), [])

    def test_the_loop_is_seamless(self):
        """Wrapping from the last frame to the first must advance by one.

        If either endpoint repeated, the turn would hold a still frame for two
        durations and read as a stutter.
        """
        forward = [1, 2, 3, 4, 5]
        loop = pingpong(forward)
        wrapped = loop + loop[:1]
        for a, b in zip(wrapped, wrapped[1:]):
            self.assertNotEqual(a, b)


class Duration(unittest.TestCase):
    def test_thirty_fps(self):
        self.assertEqual(frame_duration_ms(30), 33)

    def test_twenty_five_fps_is_exact(self):
        self.assertEqual(frame_duration_ms(25), 40)

    def test_a_very_fast_rate_still_advances(self):
        self.assertEqual(frame_duration_ms(5000), 1)

    def test_zero_is_refused(self):
        with self.assertRaises(ValueError):
            frame_duration_ms(0)


class ReadsTheBrowsersRules(unittest.TestCase):
    """The cap and the names come from the patch, not from this tool."""

    def test_cap_matches_the_patch(self):
        self.assertEqual(max_asset_bytes(), 32 * 1024 * 1024)

    def test_names_are_the_browsers_names(self):
        self.assertEqual(
            sorted(asset_names()),
            ["newtab-background.jpg", "newtab-background.png",
             "newtab-background.webp"],
        )

    def test_output_names(self):
        self.assertEqual(default_output(".webp"), "newtab-background.webp")
        self.assertEqual(default_output(".png"), "newtab-background.png")

    def test_a_moved_cap_stops_the_tool(self):
        with self.assertRaises(SystemExit):
            max_asset_bytes("nothing here names a cap")

    def test_moved_names_stop_the_tool(self):
        with self.assertRaises(SystemExit):
            asset_names("nothing here names a file")


if __name__ == "__main__":
    unittest.main()
