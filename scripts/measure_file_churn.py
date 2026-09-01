#!/usr/bin/env python3
"""Measure how much a set of upstream files changes between Chromium revisions.

`scripts/measure_rebase_cost.py` answers "does the stack still apply?" for the
files the stack already owns. This answers the question that comes *before*
owning a file: if Sunshine took this file, how often would it have to redo the
work?

`docs/INSTALLER_CHOICE_PLAN.md` §8.4 asked for exactly this and named the wrong
tool for it -- the rebase-cost script applies the series, and a file the series
does not touch is invisible to it. The executable-name change would own files no
patch has ever named, so nothing in this repository could price it.

**Why a number that is written down needs a script under it.** §6 of that plan
carries a table of measurements taken by hand. One of its rows is wrong --
`util_constants.h` is shown as not existing at the pin, when it exists there
with 277 lines and merely does not yet *define* the constants -- and nothing
could have caught it, because the measurement was a thing someone did once. The
acceptance index once said this repository held "one hundred and forty tests"
when it held 383, for the same reason. A measurement that can be re-run is a
measurement that can be re-run at the next roll.

**What this does not measure.** Lines differing is not effort. A file can be
rewritten wholesale and still carry the same three constants in the same shape,
and a two-line change can move the exact declaration a patch anchors to. The
number is a proxy, it is the cheapest honest one available without applying a
patch that does not exist, and the deleted/unchanged verdicts either side of it
are facts rather than proxies.
"""

from __future__ import annotations

import argparse
import concurrent.futures
import difflib
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import verify_pinned_upstream as upstream  # noqa: E402

# The blast radius `docs/INSTALLER_CHOICE_PLAN.md` §4 enumerates for a
# user-chosen executable name, plus the files §6 measured by hand. Named here
# rather than discovered, because discovering it means searching Chromium and
# this repository reads the pinned tree by path.
SETS = {
    "executable-name": (
        # The constants themselves.
        "chrome/installer/util/util_constants.cc",
        "chrome/installer/util/util_constants.h",
        # The update swap: new_chrome.exe renamed over chrome.exe.
        "chrome/installer/setup/setup_main.cc",
        "chrome/installer/setup/install.cc",
        "chrome/installer/setup/install_worker.cc",
        "chrome/installer/setup/setup_util.cc",
        "chrome/installer/setup/installer_state.cc",
        "chrome/installer/setup/setup_constants.cc",
        "chrome/installer/setup/setup_install_details.cc",
        "chrome/installer/setup/uninstall.cc",
        "chrome/installer/setup/setup_singleton.cc",
        "chrome/installer/setup/brand_behaviors.h",
        "chrome/installer/util/delete_old_versions.cc",
        # Shortcuts, ProgID, default-browser registration.
        "chrome/installer/util/shell_util.cc",
        "chrome/installer/util/install_util.cc",
        "chrome/installer/util/helper.cc",
        "chrome/browser/shell_integration_win.cc",
        # install_static: read at earliest startup and by the crash handler,
        # and designed around brand identity being a compile-time constant.
        "chrome/install_static/install_util.cc",
        "chrome/install_static/install_util.h",
        "chrome/install_static/install_modes.h",
        "chrome/install_static/install_modes.cc",
        "chrome/install_static/product_install_details.cc",
    ),
    # `docs/COMMAND_PALETTE_CONTRACT.md` §5(1): every registered command needs a
    # localised title, and titles belong in Chromium's localisation system
    # rather than in a WebUI bundle, because the toolbar, the menus and the
    # gestures invoke commands too and none of them can read a bundle.
    #
    # The two routes and what each costs are measured here rather than argued.
    # The Sunshine WebUI bundle is an `includes` grd wired through
    # `chrome_paks.gni`; a *strings* grd is a different flow, packed per locale
    # through `chrome_repack_locales.gni`, which the stack does not own.
    "command-titles": (
        # Route A -- a Sunshine strings grd. This is the file that would become
        # the stack's twenty-seventh owned upstream file: two lines, one
        # source_pattern and one dep.
        "chrome/chrome_repack_locales.gni",
        # Route B -- the branded-strings file patch 0010 already owns, used for
        # something it was not meant for.
        "chrome/app/chromium_strings.grd",
        # Owned already, and needed either way for reference.
        "chrome/chrome_paks.gni",
        "tools/gritsettings/resource_ids.spec",
        # The file neither route takes, priced so that "not this one" is a
        # measurement rather than a feeling.
        "chrome/app/generated_resources.grd",
    ),
}


def changed_lines(before: str, after: str) -> int:
    """Lines a unified diff with no context would add or remove."""

    return sum(
        1
        for line in difflib.unified_diff(
            before.splitlines(), after.splitlines(), n=0, lineterm=""
        )
        if line[:1] in "+-" and not line.startswith(("---", "+++"))
    )


def verdict(before: str | None, after: str | None) -> str:
    if before is None:
        return "absent at the base revision"
    if after is None:
        return "deleted"
    if after == before:
        return "unchanged"
    return f"{changed_lines(before, after)} lines differ"


def measure(
    paths: tuple[str, ...],
    base: str,
    references: tuple[str, ...],
    source: str = "github",
) -> list[tuple[str, int | None, dict[str, str]]]:
    def body(reference: str, path: str) -> str | None:
        try:
            return upstream.fetch(source, reference, path)
        except upstream.UpstreamCheckError:
            return None

    def one(path: str):
        fetched = {r: body(r, path) for r in (base, *references)}
        at_base = fetched[base]
        lines = None if at_base is None else len(at_base.splitlines())
        return path, lines, {r: verdict(at_base, fetched[r]) for r in references}

    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
        return list(pool.map(one, paths))


def format_report(
    base: str, references: tuple[str, ...], rows: list
) -> str:
    out = [f"| File | at {base} | " + " | ".join(references) + " |"]
    out.append("| --- | --- |" + " --- |" * len(references))
    for path, lines, verdicts in rows:
        at_base = "**absent**" if lines is None else f"{lines} lines"
        cells = " | ".join(
            f"**{verdicts[r]}**" if verdicts[r] in ("unchanged", "deleted")
            else verdicts[r]
            for r in references
        )
        out.append(f"| `{path}` | {at_base} | {cells} |")
    return "\n".join(out)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("set", choices=sorted(SETS), help="which file set to measure")
    parser.add_argument(
        "references", nargs="*", default=["153.0.8000.0", "main"],
        help="revisions to compare the pin against",
    )
    parser.add_argument(
        "--source", default="github", choices=sorted(upstream.SOURCES))
    arguments = parser.parse_args()

    base = upstream.pinned_version(ROOT)
    references = tuple(arguments.references)
    rows = measure(SETS[arguments.set], base, references, arguments.source)
    print(format_report(base, references, rows))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
