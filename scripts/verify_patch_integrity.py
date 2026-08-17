#!/usr/bin/env python3
"""Check that every patch in the stack is internally well-formed.

The patch stack is the project's core artifact, and it is the one artifact
nothing read for correctness. `scripts/patch_manifest.py` reads which upstream
files each patch claims; `scripts/bootstrap_chromium.py` hands the files to
`git apply` and finds out the rest on the Windows runner, hours into a build
queue, on the machine that is also the only CI.

The expensive form of that is arithmetic. A hunk header states how many lines
its body holds:

    @@ -185,9 +185,14 @@
        ^ old_start,old_count  ^ new_start,new_count

and every hand-edit to the body has to keep those four numbers true. Nothing
checked them, so the cost of getting them wrong was paid at build time by
whoever was waiting for the build. Counting them here costs milliseconds.

What is checked, per patch:

  * the body of each hunk holds exactly `old_count` context-or-removal lines
    and exactly `new_count` context-or-addition lines, with an omitted count
    meaning 1, as unified diff specifies
  * every body line carries a diff prefix
  * each file section has `--- a/path` immediately followed by `+++ b/path`,
    naming the same file
  * hunks within a file section run in ascending, non-overlapping order

and, across the directory, that `downstream/patches/series` and the files on
disk describe the same stack in the same order.

What is not checked is whether a hunk matches Chromium: that needs the
checkout, and `bootstrap_chromium.py` already runs `git apply --check` against
it. This guard is about the patch file alone, which is the part that can be
wrong before any checkout exists.

This guard claims no invariant identifier; no contract declares one for the
patch format.
"""

from __future__ import annotations

from pathlib import Path
import re
import sys
from typing import NamedTuple

ROOT = Path(__file__).resolve().parents[1]

PATCH_DIR = "downstream/patches"
SERIES = f"{PATCH_DIR}/series"

# `@@ -185,9 +185,14 @@`, and the short forms `@@ -3 +3,2 @@`. Unified diff
# omits a count when it is 1, and git emits the short form regularly, so the
# omission is normal input and not a defect to report.
HUNK = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@")

# A file section header pair. `/dev/null` stands in for the missing side when a
# patch adds or deletes a whole file; the stack contains no such patch today,
# but rejecting the form would turn the first added file into a guard failure.
# A trailing tab-separated timestamp is what `diff -u` adds and git does not;
# it is stripped rather than rejected.
OLD_HEADER = re.compile(r"^--- (?:a/([^\t]*)|/dev/null)\s*$")
NEW_HEADER = re.compile(r"^\+\+\+ (?:b/([^\t]*)|/dev/null)\s*$")
DIFF_GIT = re.compile(r"^diff --git ")

PATCH_NAME = re.compile(r"^(\d{4})-[a-z0-9][a-z0-9-]*\.patch$")

# The one line inside a body that carries no diff prefix and counts as nothing.
NO_NEWLINE = "\\"


class Hunk(NamedTuple):
    """A hunk header and where it was found. `header` is the literal `@@ ... @@`
    text, so a failure quotes the patch back to its author rather than a
    reconstruction of it."""

    line: int
    header: str
    old_start: int
    old_count: int
    new_start: int
    new_count: int

    @property
    def old_end(self) -> int:
        return self.old_start + self.old_count


def _is_body_line(line: str) -> bool:
    """Whether a line can belong to a hunk body.

    A completely empty line counts as a blank context line. Git generates
    ` ` + the line, so a blank context line should be a single space -- but
    trailing whitespace is stripped by editors, mailers, and by every "clean up
    whitespace" hook in existence, and git accepts the stripped form for that
    reason. `0003-sunshine-no-missing-api-key-warning.patch` in this stack has
    two of them and applies cleanly. Rejecting the form would fail a patch git
    is happy with, which is the kind of false positive that ends with the guard
    deleted rather than the patch fixed.
    """

    return line == "" or line[:1] in (" ", "+", "-", NO_NEWLINE)


def _body(lines: list[str], start: int) -> tuple[list[str], int]:
    """The body lines following a hunk header, and the index after them.

    The body runs until something that can only be structure: the next hunk,
    the next `diff --git`, or a `---`/`+++` header pair. The pair is required
    before `---` is read as structure, because a removal line whose content
    began with `-- ` is indistinguishable from a header on its own -- and a
    removed line beginning `-- ` followed by an added line beginning `++ ` is
    not something Chromium source contains.

    A line inside `@@ ... @@` would end the body early; this stack patches
    Chromium source, not patch files, so that trade is safe here and would need
    revisiting only if Sunshine ever patched a diff.
    """

    index = start
    while index < len(lines):
        line = lines[index]
        if DIFF_GIT.match(line) or HUNK.match(line):
            break
        if (
            OLD_HEADER.match(line)
            and index + 1 < len(lines)
            and NEW_HEADER.match(lines[index + 1])
        ):
            break
        if not _is_body_line(line):
            break
        index += 1
    return lines[start:index], index


def _count(body: list[str]) -> tuple[int, int]:
    """(old lines, new lines) the body actually holds."""

    old = new = 0
    for line in body:
        if line == "" or line.startswith(" "):
            old += 1
            new += 1
        elif line.startswith("-"):
            old += 1
        elif line.startswith("+"):
            new += 1
        # The `\ No newline at end of file` marker annotates the line above it
        # and is content on neither side.
    return old, new


def _drop_trailing_blanks(body: list[str], hunk: Hunk) -> list[str]:
    """Resolve the one genuinely ambiguous line: a blank at the end of a body.

    An empty line there is either the hunk's last context line or the blank
    somebody left between this patch and the end of the file. Git resolves it
    positionally -- it stops reading once the declared counts are met, so a
    blank beyond them is never part of the hunk -- and this does the same, by
    dropping trailing blanks only while they are surplus. A hunk that really
    ends in a blank context line keeps it, because then the counts already
    agree and nothing is dropped.
    """

    trimmed = list(body)
    while trimmed and trimmed[-1] == "":
        old, new = _count(trimmed)
        if old <= hunk.old_count and new <= hunk.new_count:
            break
        trimmed.pop()
    return trimmed


def check_patch(text: str, label: str, failures: list[str]) -> tuple[int, int]:
    """Check one patch file. Returns (file sections, hunks) seen."""

    lines = text.splitlines()
    sections = 0
    hunks = 0
    current: str | None = None
    previous: Hunk | None = None
    index = 0

    while index < len(lines):
        line = lines[index]
        number = index + 1

        if DIFF_GIT.match(line):
            # `diff --git` opens a section; the `---`/`+++` pair below it is
            # what names the file, and an `index` line may sit between them.
            current = None
            previous = None
            index += 1
            continue

        old_header = OLD_HEADER.match(line)
        if old_header:
            following = lines[index + 1] if index + 1 < len(lines) else ""
            new_header = NEW_HEADER.match(following)
            if not new_header:
                failures.append(
                    f"{label}:{number}: {line!r} is not followed by a '+++ ' header"
                )
                index += 1
                continue
            before, after = old_header.group(1), new_header.group(1)
            # Either side may be None, meaning /dev/null: a file added or
            # deleted outright has nothing to agree with.
            if before is not None and after is not None and before != after:
                failures.append(
                    f"{label}:{number}: --- a/{before} and +++ b/{after} name different files"
                )
            current = after if after is not None else before
            previous = None
            sections += 1
            index += 2
            continue

        match = HUNK.match(line)
        if match:
            hunk = Hunk(
                number,
                match.group(0),
                int(match.group(1)),
                1 if match.group(2) is None else int(match.group(2)),
                int(match.group(3)),
                1 if match.group(4) is None else int(match.group(4)),
            )
            hunks += 1
            if current is None:
                failures.append(
                    f"{label}:{number}: {hunk.header} appears before any '--- '/'+++ ' header"
                )
            elif previous is not None and hunk.old_start < previous.old_end:
                # Ascending and non-overlapping are one condition: a hunk must
                # start at or after the end of the old-side range the previous
                # hunk consumed. `git apply` walks a file once, forwards.
                failures.append(
                    f"{label}:{number}: {hunk.header} starts at old line {hunk.old_start}, "
                    f"inside or before {previous.header} at line {previous.line} "
                    f"which covers old lines {previous.old_start}-{previous.old_end - 1} "
                    f"of {current}"
                )

            body, index = _body(lines, index + 1)
            body = _drop_trailing_blanks(body, hunk)
            old, new = _count(body)

            if old != hunk.old_count:
                failures.append(
                    f"{label}:{number}: {hunk.header} declares {hunk.old_count} old line(s), "
                    f"body holds {old} (context and removal)"
                )
            if new != hunk.new_count:
                failures.append(
                    f"{label}:{number}: {hunk.header} declares {hunk.new_count} new line(s), "
                    f"body holds {new} (context and addition)"
                )

            # A line with no diff prefix is only a defect while the hunk still
            # owes lines. Once the counts are met, git stops reading the
            # fragment and whatever follows is trailing matter it ignores --
            # so flagging it here would report on text that changes nothing.
            if index < len(lines) and not _is_body_line(lines[index]):
                stop = lines[index]
                if not (DIFF_GIT.match(stop) or HUNK.match(stop) or OLD_HEADER.match(stop)):
                    if old < hunk.old_count or new < hunk.new_count:
                        failures.append(
                            f"{label}:{index + 1}: {stop!r} carries no diff prefix "
                            f"(' ', '+', '-' or '{NO_NEWLINE}'), and {hunk.header} "
                            f"at line {number} is still incomplete"
                        )
            previous = hunk
            continue

        index += 1

    if hunks == 0:
        # A patch with no hunk changes nothing, and a patch whose hunks stopped
        # being recognised looks exactly the same from here.
        failures.append(f"{label}: contains no hunks")
    return sections, hunks


def check_series(root: Path, failures: list[str]) -> None:
    """The series file and the directory must describe the same stack.

    `patch_manifest.py` also reads this file, and demands more: numbers
    contiguous from 0001, and no two patches touching the same upstream file.
    Nothing here contradicts it -- a stack that satisfies that one satisfies
    this -- but the checks are repeated rather than imported because that tool
    raises on the first problem it meets, and a guard that reports one failure
    per run turns a five-minute fix into five runs.
    """

    series = root / SERIES
    if not series.is_file():
        failures.append(f"{SERIES}: missing")
        return

    entries = [
        line.strip()
        for line in series.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]
    on_disk = sorted(path.name for path in (root / PATCH_DIR).glob("*.patch"))

    seen: set[str] = set()
    for entry in entries:
        if entry in seen:
            failures.append(f"{SERIES}: lists {entry} more than once")
        seen.add(entry)
        if not (root / PATCH_DIR / entry).is_file():
            failures.append(f"{SERIES}: lists {entry}, which is not in {PATCH_DIR}/")

    for name in on_disk:
        if name not in seen:
            failures.append(f"{PATCH_DIR}/{name}: is not listed in {SERIES} and would never be applied")

    numbers: dict[int, str] = {}
    order: list[tuple[int, str]] = []
    for entry in entries:
        match = PATCH_NAME.fullmatch(entry)
        if not match:
            failures.append(f"{SERIES}: {entry} carries no NNNN- prefix, so its place in the order is undefined")
            continue
        number = int(match.group(1))
        if number in numbers:
            failures.append(f"{SERIES}: {entry} reuses the number of {numbers[number]}")
        else:
            numbers[number] = entry
        order.append((number, entry))

    for (number, entry), (previous_number, previous_entry) in zip(order[1:], order):
        if number <= previous_number:
            # The stack is ordered, and the order is the numbering. A series
            # that disagrees with its own prefixes applies the stack in an
            # order nobody reading the directory would predict.
            failures.append(
                f"{SERIES}: {entry} is listed after {previous_entry}, "
                "but its number is not higher"
            )


def check(root: Path = ROOT) -> tuple[dict[str, int], list[str]]:
    """Returns (counts, failures). The counts are printed on success: a guard
    that reports only "passed" cannot be told from one that found nothing to
    read."""

    counts = {"patches": 0, "sections": 0, "hunks": 0}
    failures: list[str] = []

    directory = root / PATCH_DIR
    if not directory.is_dir():
        return counts, [f"{PATCH_DIR}/: missing"]

    check_series(root, failures)

    # Every patch on disk is read, listed in the series or not. An unlisted
    # patch is reported above and is still worth checking: it is usually one
    # that is about to be listed.
    for path in sorted(directory.glob("*.patch")):
        label = f"{PATCH_DIR}/{path.name}"
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            failures.append(f"{label}: is not UTF-8 text")
            continue
        counts["patches"] += 1
        sections, hunks = check_patch(text, label, failures)
        counts["sections"] += sections
        counts["hunks"] += hunks

    return counts, failures


def main() -> int:
    counts, failures = check()
    if failures:
        print("\n".join(failures), file=sys.stderr)
        return 1
    print(
        "Patch integrity check passed: "
        f"{counts['patches']} patch(es), {counts['sections']} file section(s), "
        f"{counts['hunks']} hunk(s); every hunk header agrees with its body."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
