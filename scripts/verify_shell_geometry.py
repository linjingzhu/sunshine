#!/usr/bin/env python3
"""Hold the module shell's measurements and its contract to each other.

`docs/MODULE_SHELL_CONTRACT.md` section 2 states the shell's geometry as a
table, and `downstream/patches/0011-sunshine-module-shell.patch` declares the
same numbers as constants in `geometry.ts`. Two copies of seventeen numbers
drift, and the drift is the quiet kind: a width changed in one place still
produces a shell that renders, just not the one anybody agreed to.

So the contract is the source and this compares the code against it. MS-4.

**Why the constants and not the stylesheet.** The stylesheet names no
measurement of its own -- every width reaches CSS as a custom property set from
`geometry.ts` at startup -- so checking the constants checks the whole surface.
A literal width appearing in the CSS would defeat that, and this checks for it
too.

This guard claims no invariant identifier of its own beyond MS-4, which
`docs/MODULE_SHELL_CONTRACT.md` declares.

Enforces: MS-4.
"""

from __future__ import annotations

from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]

CONTRACT = "docs/MODULE_SHELL_CONTRACT.md"
PATCH_NAME = "0011-sunshine-module-shell.patch"
GEOMETRY = "chrome/browser/resources/sunshine/shell/geometry.ts"
STYLESHEET = "chrome/browser/resources/sunshine/shell/app.css"

# `| `KEY` | 123 | prose |` in the contract's geometry table.
CONTRACT_ROW = re.compile(r"^\|\s*`([A-Z][A-Z0-9_]*)`\s*\|\s*(\d+)\s*\|")
# `export const KEY = 123;` in the TypeScript.
DECLARATION = re.compile(r"^export const ([A-Z][A-Z0-9_]*) = (\d+);")

# A pixel length in a CSS declaration. Only lengths that could plausibly be one
# of the contract's measurements are checked: the threshold is the smallest
# value the table states, so a hairline border and the focus ring are below it
# by construction. Those belong to the design system, which has its own guard
# and its own contract; this one is about region geometry.
CSS_LENGTH = re.compile(r":\s*[^;]*?(?<![\w.-])(\d+)px")


class GeometryError(ValueError):
    pass


def added_file(patch_text: str, path: str) -> str | None:
    """The content of one file a patch creates, with diff prefixes removed."""

    lines = patch_text.splitlines()
    for index, line in enumerate(lines):
        if line != f"+++ b/{path}" or lines[index - 1] != "--- /dev/null":
            continue
        body: list[str] = []
        for entry in lines[index + 1:]:
            if entry.startswith("diff --git ") or entry.startswith("--- "):
                break
            if entry.startswith("@@"):
                continue
            if entry.startswith("+"):
                body.append(entry[1:])
            elif entry.startswith("\\"):
                continue
            else:
                break
        return "\n".join(body) + "\n"
    return None


def contract_geometry(root: Path = ROOT) -> dict[str, int]:
    """The table in section 2, read as the source of truth."""

    text = (root / CONTRACT).read_text(encoding="utf-8")
    found: dict[str, int] = {}
    for line in text.splitlines():
        match = CONTRACT_ROW.match(line)
        if match:
            name, value = match.group(1), int(match.group(2))
            if name in found:
                raise GeometryError(f"{CONTRACT}: {name} is stated twice")
            found[name] = value
    if not found:
        raise GeometryError(f"{CONTRACT}: no geometry table found")
    return found


def declared_geometry(source: str) -> dict[str, int]:
    found: dict[str, int] = {}
    for line in source.splitlines():
        match = DECLARATION.match(line)
        if match:
            found[match.group(1)] = int(match.group(2))
    return found


def check(root: Path = ROOT) -> list[str]:
    failures: list[str] = []
    patch = root / "downstream/patches" / PATCH_NAME
    if not patch.is_file():
        return [f"{PATCH_NAME} is missing, so the shell has no geometry to check"]

    patch_text = patch.read_text(encoding="utf-8")
    source = added_file(patch_text, GEOMETRY)
    if source is None:
        return [f"{PATCH_NAME} no longer creates {GEOMETRY}"]

    expected = contract_geometry(root)
    declared = declared_geometry(source)

    for name, value in sorted(expected.items()):
        if name not in declared:
            failures.append(
                f"{GEOMETRY} declares no {name}, which {CONTRACT} states as {value}"
            )
        elif declared[name] != value:
            failures.append(
                f"{GEOMETRY} has {name} = {declared[name]}; {CONTRACT} states {value}"
            )
    for name in sorted(set(declared) - set(expected)):
        failures.append(
            f"{GEOMETRY} declares {name} = {declared[name]}, which {CONTRACT} "
            "does not state -- a measurement no contract carries"
        )

    stylesheet = added_file(patch_text, STYLESHEET)
    if stylesheet is None:
        failures.append(f"{PATCH_NAME} no longer creates {STYLESHEET}")
    else:
        floor = min(expected.values())
        for number, line in enumerate(stylesheet.splitlines(), start=1):
            for literal in CSS_LENGTH.findall(line):
                if int(literal) >= floor:
                    failures.append(
                        f"{STYLESHEET}:{number} sets a length of {literal}px "
                        f"directly, at or above the contract's smallest "
                        f"measurement ({floor}px). Every measurement reaches CSS "
                        "from geometry.ts as a custom property: "
                        f"{line.strip()!r}"
                    )
    return failures


def main() -> int:
    try:
        failures = check()
    except GeometryError as error:
        print(f"Shell geometry check failed: {error}", file=sys.stderr)
        return 1
    if failures:
        for failure in failures[:20]:
            print(f"Shell geometry check failed: {failure}", file=sys.stderr)
        return 1
    print(
        f"Shell geometry check passed: {len(contract_geometry())} measurement(s) "
        f"in {CONTRACT} match {GEOMETRY}, and the stylesheet invents none."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
