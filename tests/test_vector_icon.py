"""The `.icon` reader, tested against the mistakes it exists to catch.

Every case here is a file that `aggregate_vector_icons.py` would either paste
into a generated C++ array unchanged -- making it a compile error twenty
minutes into a build -- or reject with a message no one sees until then. The
fixtures are shaped like real icons rather than minimal, because a grammar
checker that only ever sees three-line inputs is not evidence about the files
it will actually read.
"""

from __future__ import annotations

from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.render_vector_icon import (  # noqa: E402
    COMMANDS,
    IconError,
    parse,
    to_svg,
)

# A transcription of upstream's `folder_flippable.icon` at the pinned revision,
# shortened to the commands it uses. It is here to hold the grammar to a file
# Chromium actually compiles, not to a file this repository invented.
UPSTREAM = """
// Copyright 2026 The Chromium Authors

CANVAS_DIMENSIONS, 20,
FLIPS_IN_RTL,
FILL_RULE_NONZERO,
MOVE_TO, 3.5f, 16,
R_CUBIC_TO, -0.4f, 0, -0.75f, -0.15f, -1.05f, -0.45f,
R_V_LINE_TO, -9,
ARC_TO, 1.45f, 1.45f, 0, 0, 1, 3.5f, 4,
R_H_LINE_TO, 3.87f,
LINE_TO, 10, 6,
H_LINE_TO, 9.38f,
CLOSE
"""

TWO_REPS = """
CANVAS_DIMENSIONS, 24,
MOVE_TO, 4, 4,
LINE_TO, 20, 20,
CLOSE

CANVAS_DIMENSIONS, 20,
MOVE_TO, 3, 3,
LINE_TO, 17, 17,
CLOSE
"""


class Grammar(unittest.TestCase):
    def test_an_upstream_icon_parses(self):
        reps = parse(UPSTREAM)
        self.assertEqual([rep.size for rep in reps], [20])
        self.assertEqual(reps[0].commands[0][0], "CANVAS_DIMENSIONS")

    def test_a_misspelled_command_is_not_a_drawing_mistake(self):
        """`LINE_T0` with a zero compiles to an undeclared identifier.

        Nothing between the diff and the compiler reads this file, so without
        this check the first report of the typo is a build failure on the
        owner's workstation.
        """
        with self.assertRaises(IconError) as caught:
            parse("CANVAS_DIMENSIONS, 24,\nLINE_T0, 4, 4,\n")
        self.assertIn("LINE_T0", str(caught.exception))
        self.assertIn("not a vector icon command", str(caught.exception))

    def test_arc_to_takes_seven_arguments(self):
        """The one arity that is genuinely easy to get wrong.

        SVG's own arc takes seven and every other curve command here takes an
        even number, so six reads as complete. It leaves the next command's
        name sitting where an argument belongs.
        """
        self.assertEqual(COMMANDS["ARC_TO"], 7)
        with self.assertRaises(IconError) as caught:
            parse("CANVAS_DIMENSIONS, 24,\n"
                  "MOVE_TO, 4, 4,\n"
                  "ARC_TO, 2, 2, 0, 0, 1, 6,\n"
                  "CLOSE\n")
        self.assertIn("ARC_TO", str(caught.exception))
        self.assertIn("`CLOSE`", str(caught.exception))

    def test_an_argument_with_no_command_is_named_as_such(self):
        with self.assertRaises(IconError) as caught:
            parse("CANVAS_DIMENSIONS, 24,\n4, 4,\n")
        self.assertIn("no command before it", str(caught.exception))

    def test_a_file_that_ends_mid_command_says_so(self):
        with self.assertRaises(IconError) as caught:
            parse("CANVAS_DIMENSIONS, 24,\nMOVE_TO, 4,\n")
        self.assertIn("the file ends", str(caught.exception))

    def test_comments_and_blank_lines_are_not_content(self):
        reps = parse("// a folder\n\nCANVAS_DIMENSIONS, 16, // sixteen\n"
                     "CLOSE\n")
        self.assertEqual([rep.size for rep in reps], [16])

    def test_an_empty_file_has_no_icon_in_it(self):
        with self.assertRaises(IconError):
            parse("// nothing but a licence header\n")


class Reps(unittest.TestCase):
    def test_reps_are_split_on_canvas_dimensions(self):
        reps = parse(TWO_REPS)
        self.assertEqual([rep.size for rep in reps], [24, 20])
        self.assertTrue(all(rep.commands[0][0] == "CANVAS_DIMENSIONS" for rep in reps))

    def test_ascending_reps_are_rejected(self):
        """Upstream's own rule, and it is not cosmetic.

        `GetRepForPxSize` walks the array backwards assuming descending order,
        so a file sorted the other way returns the wrong rep at some sizes and
        the right one at others.
        """
        with self.assertRaises(IconError) as caught:
            parse("CANVAS_DIMENSIONS, 20,\nCLOSE\n\nCANVAS_DIMENSIONS, 24,\nCLOSE\n")
        self.assertIn("descending", str(caught.exception))

    def test_two_reps_of_one_size_are_rejected(self):
        with self.assertRaises(IconError) as caught:
            parse("CANVAS_DIMENSIONS, 24,\nCLOSE\n\nCANVAS_DIMENSIONS, 24,\nCLOSE\n")
        self.assertIn("same canvas size", str(caught.exception))

    def test_a_fractional_canvas_size_is_rejected(self):
        """`aggregate_vector_icons.py` finds sizes with `\\d+`.

        A canvas of `20.5f` yields two matches, which upstream reports as a
        malformed line; a canvas of `.5f` yields one and would be believed.
        """
        with self.assertRaises(IconError):
            parse("CANVAS_DIMENSIONS, 20.5f,\nCLOSE\n")


class Svg(unittest.TestCase):
    def test_an_arc_keeps_all_seven_numbers(self):
        rep = parse("CANVAS_DIMENSIONS, 24,\nMOVE_TO, 4, 4,\n"
                    "ARC_TO, 2, 2, 0, 0, 1, 6, 6,\nCLOSE\n")[0]
        self.assertIn("A 2 2 0 0 1 6 6", to_svg(rep))

    def test_the_fill_rule_follows_the_file(self):
        even = parse("CANVAS_DIMENSIONS, 24,\nMOVE_TO, 4, 4,\nCLOSE\n")[0]
        self.assertIn('fill-rule="evenodd"', to_svg(even))
        nonzero = parse("CANVAS_DIMENSIONS, 24,\nFILL_RULE_NONZERO,\n"
                        "MOVE_TO, 4, 4,\nCLOSE\n")[0]
        self.assertIn('fill-rule="nonzero"', to_svg(nonzero))

    def test_shapes_that_are_not_paths_are_drawn_as_shapes(self):
        rep = parse("CANVAS_DIMENSIONS, 24,\nCIRCLE, 12, 12, 6,\n"
                    "ROUND_RECT, 2, 2, 20, 20, 4,\n")[0]
        drawn = to_svg(rep)
        self.assertIn('<circle cx="12" cy="12" r="6"/>', drawn)
        self.assertIn('rx="4"', drawn)

    def test_the_canvas_size_is_the_viewbox(self):
        rep = parse(TWO_REPS)[1]
        self.assertIn('viewBox="0 0 20 20"', to_svg(rep))


if __name__ == "__main__":
    unittest.main()
