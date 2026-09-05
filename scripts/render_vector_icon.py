#!/usr/bin/env python3
"""Read a Chromium `.icon` file, check it, and draw it as SVG.

A `.icon` file is not a picture. It is a comma-separated list of C++ tokens
that `aggregate_vector_icons.py` pastes verbatim into a generated array, so a
misspelled command is not a drawing mistake -- it is an undeclared identifier,
and the first thing that says so is the compiler, twenty minutes into a build
on the owner's workstation. That is the shape of failure this repository has
paid for twice: build #46 on a stylesheet upstream's linter would not accept,
build #49 on a `.grd` upstream's XML parser could not read. The pattern is
always the same. A guard asked whether the patch lands; nothing asked whether
the tool that reads what it landed can read it.

So this reads the file the way Chromium does, in two layers:

  * **the aggregate script's rules** -- reps are delimited by
    `CANVAS_DIMENSIONS`, each names exactly one integer size, sizes are unique
    and in descending order, and a file has at least one rep;
  * **the interpreter's grammar** -- every command is a real
    `gfx::CommandType`, and each is followed by exactly the number of arguments
    `PaintPath()` reads from it. `ARC_TO` takes seven, not six; `H_LINE_TO`
    takes one, not two. Both are silent in a diff and loud in a compile.

What it cannot check is whether the drawing is any good, so it also renders.
`--svg` writes the path out as SVG, which is the same geometry in a format a
person can open, and is the only way to see a native icon without the three
hours of build standing between the edit and the pixels.

    python scripts/render_vector_icon.py path/to/icon.icon --check
    python scripts/render_vector_icon.py path/to/icon.icon --svg out.svg

The SVG is a preview, not a build input: nothing in the stack reads it, and
Chromium draws from the `.icon` file itself.
"""

from __future__ import annotations

import argparse
from pathlib import Path
import re
import sys

# Argument counts are read off the switch in `ui/gfx/paint_vector_icon.cc` at
# the pinned revision -- the highest `arg(N)` each case reads, plus one. They
# are transcribed rather than derived, because the file that defines them is
# upstream's and this guard runs without a checkout.
COMMANDS: dict[str, int] = {
    "NEW_PATH": 0,
    "FILL_RULE_NONZERO": 0,
    "PATH_COLOR_ALPHA": 1,
    "PATH_COLOR_ARGB": 4,
    "PATH_MODE_CLEAR": 0,
    "STROKE": 1,
    "CAP_SQUARE": 0,
    "MOVE_TO": 2,
    "R_MOVE_TO": 2,
    "ARC_TO": 7,
    "R_ARC_TO": 7,
    "LINE_TO": 2,
    "R_LINE_TO": 2,
    "H_LINE_TO": 1,
    "R_H_LINE_TO": 1,
    "V_LINE_TO": 1,
    "R_V_LINE_TO": 1,
    "CUBIC_TO": 6,
    "R_CUBIC_TO": 6,
    "CUBIC_TO_SHORTHAND": 4,
    "QUADRATIC_TO": 4,
    "R_QUADRATIC_TO": 4,
    "QUADRATIC_TO_SHORTHAND": 2,
    "R_QUADRATIC_TO_SHORTHAND": 2,
    "CIRCLE": 3,
    "OVAL": 4,
    "ROUND_RECT": 5,
    "CLOSE": 0,
    "CANVAS_DIMENSIONS": 1,
    "CLIP": 4,
    "DISABLE_AA": 0,
    "FLIPS_IN_RTL": 0,
}

# The SVG path letter each command maps to. Commands absent from this table
# either draw a shape of their own (CIRCLE, OVAL, ROUND_RECT) or set state
# rather than geometry.
PATH_LETTERS: dict[str, str] = {
    "MOVE_TO": "M",
    "R_MOVE_TO": "m",
    "LINE_TO": "L",
    "R_LINE_TO": "l",
    "H_LINE_TO": "H",
    "R_H_LINE_TO": "h",
    "V_LINE_TO": "V",
    "R_V_LINE_TO": "v",
    "CUBIC_TO": "C",
    "R_CUBIC_TO": "c",
    "CUBIC_TO_SHORTHAND": "S",
    "QUADRATIC_TO": "Q",
    "R_QUADRATIC_TO": "q",
    "QUADRATIC_TO_SHORTHAND": "T",
    "R_QUADRATIC_TO_SHORTHAND": "t",
    "ARC_TO": "A",
    "R_ARC_TO": "a",
    "CLOSE": "Z",
}

# The aggregate script's default when a file's first rep does not declare one.
REFERENCE_SIZE_DIP = 48

NUMBER = re.compile(r"^-?(?:\d+\.?\d*|\.\d+)f?$")


class IconError(Exception):
    """A `.icon` file that Chromium's own tools would reject."""


class Rep:
    """One representation: a canvas size and the commands drawn on it."""

    def __init__(self, size: int) -> None:
        self.size = size
        self.commands: list[tuple[str, list[float], int]] = []


def _tokens(text: str) -> list[tuple[str, int]]:
    """Every comma-separated token, paired with the line it was written on."""
    out: list[tuple[str, int]] = []
    for number, line in enumerate(text.splitlines(), start=1):
        # The aggregate script strips from the first `//` and does not know
        # about block comments, so neither does this.
        for piece in line.partition("//")[0].split(","):
            piece = piece.strip()
            if piece:
                out.append((piece, number))
    return out


def parse(text: str) -> list[Rep]:
    """Parse a `.icon` file into reps, or raise `IconError` saying why not."""
    reps: list[Rep] = []
    pending: list[tuple[str, list[float], int]] = []

    tokens = _tokens(text)
    index = 0
    while index < len(tokens):
        name, line = tokens[index]
        if name not in COMMANDS:
            if NUMBER.match(name):
                raise IconError(f"line {line}: argument `{name}` with no command before it")
            raise IconError(f"line {line}: `{name}` is not a vector icon command")

        wanted = COMMANDS[name]
        args: list[float] = []
        for offset in range(1, wanted + 1):
            if index + offset >= len(tokens):
                raise IconError(
                    f"line {line}: `{name}` takes {wanted} arguments and the file ends after {len(args)}")
            argument, argument_line = tokens[index + offset]
            if not NUMBER.match(argument):
                raise IconError(
                    f"line {argument_line}: `{name}` takes {wanted} arguments; "
                    f"argument {offset} is `{argument}`, which is a command")
            args.append(float(argument.rstrip("f")))
        index += wanted + 1

        if name == "CANVAS_DIMENSIONS":
            if args[0] != int(args[0]):
                raise IconError(f"line {line}: canvas size {args[0]:g} is not a whole number")
            if pending:
                reps.append(_finish(reps, pending))
                pending = []
        pending.append((name, args, line))

    if not pending:
        raise IconError("no icon in this file")
    reps.append(_finish(reps, pending))

    sizes = [rep.size for rep in reps]
    if sizes != sorted(sizes, reverse=True):
        raise IconError(
            "reps must be in descending order of size, and these are "
            + ", ".join(str(size) for size in sizes))
    if len(set(sizes)) != len(sizes):
        raise IconError("two reps declare the same canvas size")
    return reps


def _finish(reps: list[Rep], pending: list[tuple[str, list[float], int]]) -> Rep:
    head = pending[0]
    size = int(head[1][0]) if head[0] == "CANVAS_DIMENSIONS" else REFERENCE_SIZE_DIP
    rep = Rep(size)
    rep.commands = pending
    return rep


def _number(value: float) -> str:
    return f"{value:g}"


def to_svg(rep: Rep, color: str = "currentColor") -> str:
    """Render one rep as an SVG document."""
    fill_rule = "evenodd"
    path: list[str] = []
    shapes: list[str] = []
    for name, args, _ in rep.commands:
        if name == "FILL_RULE_NONZERO":
            fill_rule = "nonzero"
        elif name in PATH_LETTERS:
            path.append(PATH_LETTERS[name] + " " + " ".join(_number(a) for a in args))
        elif name == "CIRCLE":
            shapes.append(
                f'<circle cx="{_number(args[0])}" cy="{_number(args[1])}" r="{_number(args[2])}"/>')
        elif name == "OVAL":
            shapes.append(
                f'<ellipse cx="{_number(args[0])}" cy="{_number(args[1])}" '
                f'rx="{_number(args[2])}" ry="{_number(args[3])}"/>')
        elif name == "ROUND_RECT":
            shapes.append(
                f'<rect x="{_number(args[0])}" y="{_number(args[1])}" '
                f'width="{_number(args[2])}" height="{_number(args[3])}" '
                f'rx="{_number(args[4])}"/>')

    body = "\n  ".join(shapes)
    if path:
        drawn = " ".join(path).replace("Z ", "Z").strip()
        body = (body + "\n  " if body else "") + f'<path fill-rule="{fill_rule}" d="{drawn}"/>'
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{rep.size}" height="{rep.size}" '
        f'viewBox="0 0 {rep.size} {rep.size}" fill="{color}">\n  {body}\n</svg>\n')


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("icon", type=Path, help="a .icon file")
    parser.add_argument("--svg", type=Path, help="write the largest rep here as SVG")
    parser.add_argument("--size", type=int, help="render the rep with this canvas size")
    parser.add_argument("--color", default="currentColor", help="fill for the preview")
    args = parser.parse_args()

    try:
        reps = parse(args.icon.read_text(encoding="utf-8"))
    except IconError as error:
        print(f"{args.icon}: {error}", file=sys.stderr)
        return 1

    print(f"{args.icon}: {len(reps)} rep(s) at " + ", ".join(str(rep.size) for rep in reps))
    if args.svg:
        chosen = reps[0]
        if args.size is not None:
            matching = [rep for rep in reps if rep.size == args.size]
            if not matching:
                print(f"no rep at size {args.size}", file=sys.stderr)
                return 1
            chosen = matching[0]
        args.svg.write_text(to_svg(chosen, args.color), encoding="utf-8")
        print(f"wrote {args.svg} from the {chosen.size}px rep")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
