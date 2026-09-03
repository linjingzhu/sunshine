#!/usr/bin/env python3
"""Check that the patch stack refers only to files it actually produces.

Every build this project has lost, it lost to this class of mistake. Build #18
died because a patch created a file the tree already had; #22 on an expression
that does not compile; #24 on an import upstream's eslint forbids. All of them
were decidable before the build and none of them was decided, because the only
thing that read the stack for meaning was `ninja`, twenty minutes in, on the
machine that is also the owner's workstation.

This reads four kinds of reference and asks whether each one resolves:

  * a `IDR_SUNSHINE_*` named in C++ must be a resource the bundle produces,
    under the name `build_webui()` derives from the file's path;
  * every entry in the resource bundle's `static_files` and `ts_files` must be
    a file the stack creates;
  * every entry in the browser target's `sources` must be a file the stack
    creates;
  * every `#include` of a Sunshine-owned header must name a file the stack
    creates.

**How it knows what the stack produces, offline.** The four seam files are
themselves created by the stack, so their content can be reconstructed without
a Chromium checkout: the creating patch supplies the whole file, and each later
patch's hunks are applied in series. Upstream files are skipped -- their
content depends on a tree this guard does not have, and guessing would be worse
than not asking.

Applying a hunk here is also a check in its own right. The line numbers must
land and the context must match, which they can only do if the reconstruction
so far is exactly what `git apply` would have produced.

This guard claims no invariant identifier; no contract declares one for the
integrity of a reference.
"""

from __future__ import annotations

from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import patch_manifest  # noqa: E402

RESOURCES_BUILD = "chrome/browser/resources/sunshine/BUILD.gn"
RESOURCES_DIR = "chrome/browser/resources/sunshine/"
BROWSER_BUILD = "chrome/browser/ui/webui/sunshine/BUILD.gn"
BROWSER_DIR = "chrome/browser/ui/webui/sunshine/"

# Headers the stack owns. An include of one of these must resolve inside the
# stack; an include of anything else is Chromium's and not this guard's.
OWNED_INCLUDE_PREFIXES = (
    "chrome/browser/ui/webui/sunshine/",
    "chrome/common/sunshine/",
    "components/sunshine/",
)

HUNK = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@")
RESOURCE_ID = re.compile(r"\bIDR_SUNSHINE_[A-Z0-9_]+\b")
INCLUDE = re.compile(r'^\s*#include\s+"([^"]+)"')
GN_LIST = re.compile(r"(\w+)\s*=\s*\[(.*?)\]", re.DOTALL)
GN_ENTRY = re.compile(r'"([^"]+)"')


class ReferenceError(ValueError):
    pass


def stack_files(root: Path = ROOT) -> dict[str, list[str]]:
    """Final content of every file the stack creates, keyed by repository path.

    Files the stack modifies rather than creates are absent: their content
    starts from a Chromium tree this guard does not have.
    """

    produced: dict[str, list[str]] = {}
    for entry in patch_manifest.read_manifest(root):
        text = (root / "downstream/patches" / entry).read_text(encoding="utf-8")
        lines = text.splitlines()
        index = 0
        while index < len(lines):
            line = lines[index]
            if not line.startswith("--- "):
                index += 1
                continue
            target_line = lines[index + 1]
            if not target_line.startswith("+++ b/"):
                index += 1
                continue
            path = target_line[6:]
            creates = line == "--- /dev/null"
            index += 2

            body: list[tuple[int, list[str]]] = []
            while index < len(lines) and lines[index].startswith("@@"):
                match = HUNK.match(lines[index])
                if not match:
                    raise ReferenceError(f"{entry}: unreadable hunk header {lines[index]!r}")
                start = int(match.group(1))
                index += 1
                chunk: list[str] = []
                while index < len(lines) and lines[index][:1] in (" ", "+", "-", "\\"):
                    if lines[index].startswith("\\"):
                        index += 1
                        continue
                    chunk.append(lines[index])
                    index += 1
                body.append((start, chunk))

            if creates:
                produced[path] = [
                    entry_line[1:] for _, chunk in body for entry_line in chunk
                    if entry_line.startswith("+")
                ]
            elif path in produced:
                produced[path] = _apply(produced[path], body, f"{entry}:{path}")
            # else: an upstream file, whose base this guard does not have.
    return produced


def _apply(content: list[str], body: list[tuple[int, list[str]]], label: str) -> list[str]:
    """Apply hunks to a reconstruction, checking the context as it goes."""

    result = list(content)
    offset = 0
    for start, chunk in body:
        cursor = start - 1 + offset
        for line in chunk:
            kind, text = line[0], line[1:]
            if kind == " ":
                if cursor >= len(result) or result[cursor] != text:
                    raise ReferenceError(
                        f"{label}: context at line {cursor + 1} does not match the "
                        "reconstruction, so the stack does not apply in the order "
                        "its series states"
                    )
                cursor += 1
            elif kind == "-":
                if cursor >= len(result) or result[cursor] != text:
                    raise ReferenceError(
                        f"{label}: removal at line {cursor + 1} does not match the "
                        "reconstruction"
                    )
                del result[cursor]
                offset -= 1
            elif kind == "+":
                result.insert(cursor, text)
                cursor += 1
                offset += 1
    return result


def gn_lists(content: list[str]) -> dict[str, list[str]]:
    found: dict[str, list[str]] = {}
    for name, block in GN_LIST.findall("\n".join(content)):
        found.setdefault(name, []).extend(GN_ENTRY.findall(block))
    return found


def resource_id(relative: str) -> str:
    """The name `build_webui()` derives for one bundle file.

    `ui/webui/resources/tools/generate_grd.py` builds it from the grd prefix
    and the file's path, uppercased with the separators replaced -- so
    "shell/app.html" is IDR_SUNSHINE_SHELL_APP_HTML.
    """

    return "IDR_SUNSHINE_" + re.sub(r"[^A-Za-z0-9]", "_", relative).upper()


# What a Mojo target generates from one `.mojom`. The header is never written
# by a patch and never should be; what the stack owes is the interface
# definition it is generated from.
MOJOM_SUFFIXES = (".mojom.h", ".mojom-forward.h", ".mojom-shared.h",
                  ".mojom-params-data.h", ".mojom-test-utils.h")


def _resolves(included: str, produced: dict[str, list[str]]) -> bool:
    """Whether an include names something the stack produces, directly or by
    generation."""

    if included in produced:
        return True
    for suffix in MOJOM_SUFFIXES:
        if included.endswith(suffix):
            return included[: -len(suffix)] + ".mojom" in produced
    return False


# Files the stack creates whose whole point is being parsed by a tool before a
# compiler ever sees them.
MARKUP_SUFFIXES = (".grd", ".grdp", ".xml", ".rc.xml")


def check_markup_parses(produced: dict[str, list[str]], failures: list[str]) -> None:
    """Every XML file the stack creates must be well-formed XML.

    **This is the cheapest check in this repository and it was written after a
    six-hour build died in fourteen seconds without it.** Build #49 failed in
    `//tools/gritsettings:default_resource_ids` with

        sunshine_command_strings.grd:12:20: not well-formed (invalid token)

    because the file's opening comment contained `--`, which XML forbids inside
    a comment. This repository writes `--` for an em dash everywhere in prose,
    so the habit that produced it is the house style meeting a format that does
    not allow it.

    Nothing offline caught it. The patch applied, `verify_pinned_upstream`
    applied the whole stack to the real pinned tree, twenty-six guards passed
    and 881 tests passed -- because every one of them asks whether the patch
    *lands*, and none asked whether what it lands is a file its own reader can
    parse. That is the same gap that failed build #46 on stylelint, one format
    over.

    Only created files are checked. `stack_files` reconstructs those in full;
    an upstream file the stack merely edits is a partial view and parsing it
    would report a truncation as a defect.
    """

    import xml.parsers.expat

    for path, lines in sorted(produced.items()):
        if not path.endswith(MARKUP_SUFFIXES):
            continue
        parser = xml.parsers.expat.ParserCreate()
        text = "\n".join(lines)
        try:
            parser.Parse(text, True)
        except xml.parsers.expat.ExpatError as error:
            failures.append(
                f"{path}: not well-formed XML at line {error.lineno}, column "
                f"{error.offset}: {xml.parsers.expat.ErrorString(error.code)}"
            )


def check(root: Path = ROOT) -> list[str]:
    failures: list[str] = []
    produced = stack_files(root)

    check_markup_parses(produced, failures)

    if RESOURCES_BUILD not in produced or BROWSER_BUILD not in produced:
        return [
            "the seam's BUILD.gn files are not created by the stack, so nothing "
            "here can be reconstructed"
        ]

    # -- the resource bundle ---------------------------------------------------
    resources = gn_lists(produced[RESOURCES_BUILD])
    bundle: list[str] = []
    for key in ("static_files", "ts_files"):
        for relative in resources.get(key, []):
            bundle.append(relative)
            path = RESOURCES_DIR + relative
            if path not in produced:
                failures.append(
                    f"{RESOURCES_BUILD} lists {key} entry {relative!r}, which no "
                    "patch creates"
                )

    # -- the browser target ----------------------------------------------------
    for relative in gn_lists(produced[BROWSER_BUILD]).get("sources", []):
        path = BROWSER_DIR + relative
        if path not in produced:
            failures.append(
                f"{BROWSER_BUILD} lists source {relative!r}, which no patch creates"
            )

    # -- resource ids named in C++ --------------------------------------------
    # A .ts file reaches the page as .js, which is what the bundle names.
    available = {
        resource_id(relative[:-3] + ".js" if relative.endswith(".ts") else relative)
        for relative in bundle
    }
    for path, content in sorted(produced.items()):
        if not path.endswith((".cc", ".h")):
            continue
        for number, line in enumerate(content, start=1):
            for name in RESOURCE_ID.findall(line):
                if name not in available:
                    failures.append(
                        f"{path}:{number} names {name}, which the resource bundle "
                        "does not produce"
                    )

    # -- includes of Sunshine-owned headers ------------------------------------
    for path, content in sorted(produced.items()):
        if not path.endswith((".cc", ".h")):
            continue
        for number, line in enumerate(content, start=1):
            match = INCLUDE.match(line)
            if not match:
                continue
            included = match.group(1)
            if not included.startswith(OWNED_INCLUDE_PREFIXES):
                continue
            if _resolves(included, produced):
                continue
            failures.append(
                f"{path}:{number} includes {included!r}, which no patch creates"
            )
    return failures


def main() -> int:
    try:
        failures = check()
    except ReferenceError as error:
        print(f"Patch reference check failed: {error}", file=sys.stderr)
        return 1
    if failures:
        for failure in failures[:25]:
            print(f"Patch reference check failed: {failure}", file=sys.stderr)
        if len(failures) > 25:
            print(f"... and {len(failures) - 25} more", file=sys.stderr)
        return 1
    produced = stack_files()
    print(
        f"Patch reference check passed: {len(produced)} file(s) reconstructed from "
        "the stack; every resource id, build entry and Sunshine include resolves."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
