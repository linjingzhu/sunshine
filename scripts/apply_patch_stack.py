#!/usr/bin/env python3
"""Apply the whole patch stack to an existing Chromium checkout.

This is `scripts/bootstrap_chromium.py`'s last three steps and nothing else. It
exists so that a machine which can hold a `src` checkout but not a Chromium
build can still answer the one question the offline guards cannot:

    **do these patches apply to the real tree at the pinned revision?**

Every guard in this repository reads the stack against itself.
`verify_patch_integrity.py` checks the arithmetic of each hunk;
`verify_patch_references.py` replays hunks against files the stack itself
creates; `verify_pinned_upstream.py` asks whether the upstream files a document
cites exist. None of them touches an upstream file's *contents*, because none of
them has a checkout -- and so the first thing that ever reads a patch against
the real tree is `git apply` on the build machine, hours into a queue.

Build #18 died that way. It is decidable in five minutes on any machine with
enough disk for `src`, which is a GitHub-hosted runner, and this is the script
that decides it.

**Not a build, and not a substitute for one.** A stack that applies can still
fail to compile: eslint, gn, and the C++ compiler have opinions nothing here
consults. What this rules out is the class of failure that costs a whole build
slot to discover.

`bootstrap_chromium.py` remains the workstation path and is unchanged. This
script imports its functions rather than restating them, so the two cannot
disagree about what applying the stack means.
"""

from __future__ import annotations

import argparse
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import bootstrap_chromium as bootstrap  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--src",
        required=True,
        type=pathlib.Path,
        help="an existing Chromium `src` checkout at the pinned revision",
    )
    parser.add_argument(
        "--skip-overlay",
        action="store_true",
        help="do not copy the binary asset overlay. The overlay is checked "
             "offline by scripts/verify_asset_overlay.py; skipping it here "
             "keeps this run to the question in the docstring.",
    )
    args = parser.parse_args()

    src = args.src.resolve()
    if not (src / "chrome" / "VERSION").is_file():
        print(f"{src} does not look like a Chromium checkout", file=sys.stderr)
        return 1

    revision = bootstrap.read_revision()
    patch_names = bootstrap.read_series()
    print(f"pinned revision: {revision}")
    print(f"patches: {len(patch_names)}")

    # Before the first `git apply --check`, not after a failure -- the reason is
    # in bootstrap_chromium.py and it is the reason build #18 died: `git apply`
    # rejects a whole patch when one file it creates already exists.
    bootstrap.remove_created_paths(src, patch_names)

    for patch_name in patch_names:
        patch_path = ROOT / "downstream/patches" / patch_name
        bootstrap.run("git", "apply", "--check", str(patch_path), cwd=src)
        bootstrap.run("git", "apply", str(patch_path), cwd=src)
        print(f"applied: {patch_name}")

    if not args.skip_overlay:
        bootstrap.apply_overlay(src)

    print(f"The stack applies to {src} at {revision}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
