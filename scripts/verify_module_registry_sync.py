#!/usr/bin/env python3
"""Check that the module registry the browser serves is the one in `first_party/`.

`chrome://sunshine-modules` exists to answer one question -- what is built into
this browser -- and it answers it from a copy. The manifests live in
`first_party/`, on this side of the patch stack; the browser is built from a
Chromium checkout, and nothing carries a directory of JSON files across that
gap. So `downstream/patches/0007-sunshine-modules-webui.patch` bakes the
registry into a C++ string literal, and that copy can drift.

Drift here is worse than drift elsewhere. Every other guard protects a claim
made in a document; this one protects the claim a *surface* makes to the person
using the browser. A module added to `first_party/` and not to the patch is a
module the module home says does not exist.

The comparison is bytes, not meaning. `scripts/module_registry_payload.py`
defines the canonical form once, this recomputes it, and equality is the whole
test -- a hand-edit that is merely equivalent JSON still fails, which is the
point of having a canonical form at all.

This guard claims no invariant identifier; no contract declares one for the
registry copy. `scripts/trace_invariants.py` rejects invented ones, and
inventing one here would inflate the coverage number while pointing at nothing.
"""

from __future__ import annotations

from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from module_registry_payload import literal  # noqa: E402

PATCH_NAME = "0007-sunshine-modules-webui.patch"
PATCH = ROOT / "downstream/patches" / PATCH_NAME
HEADER = "chrome/browser/ui/webui/sunshine/modules/sunshine_module_registry.h"
OPENING = 'inline constexpr char kSunshineModuleRegistryJson[] = R"json('
CLOSING = ')json";'


def added_file(patch_text: str, path: str) -> str | None:
    """The content of one file a patch creates, with the diff prefixes removed.

    Only whole-file additions are read. A section that modifies an existing
    file has context and removal lines whose meaning depends on the file it is
    applied to, and reconstructing that without the checkout is guesswork; the
    registry header is created by this patch, so there is nothing to guess.
    """

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
                # "\ No newline at end of file" -- metadata, not content.
                continue
            else:
                break
        return "\n".join(body) + "\n"
    return None


def check(root: Path = ROOT) -> list[str]:
    failures: list[str] = []

    patch = root / "downstream/patches" / PATCH_NAME
    if not patch.is_file():
        return [f"{PATCH_NAME} is missing, so the module home has no registry to serve"]

    header = added_file(patch.read_text(encoding="utf-8"), HEADER)
    if header is None:
        return [f"{PATCH_NAME} no longer creates {HEADER}"]

    match = re.search(
        re.escape(OPENING) + r"(.*?)" + re.escape(CLOSING), header, re.DOTALL
    )
    if not match:
        return [
            f"{HEADER} does not declare kSunshineModuleRegistryJson as a "
            f'R"json(...)json" literal, so there is nothing to compare'
        ]

    baked = match.group(1)
    expected = literal(root)
    if baked != expected:
        failures.append(
            f"{HEADER} carries a registry that is not the one in first_party/. "
            "Regenerate it: python3 scripts/module_registry_payload.py, and put "
            "the output between the R\"json( and )json\" delimiters, keeping the "
            "newline after the opening delimiter. "
            f"({len(baked)} bytes baked, {len(expected)} expected)"
        )
    return failures


def main() -> int:
    failures = check()
    if failures:
        for failure in failures:
            print(f"Module registry sync failed: {failure}", file=sys.stderr)
        return 1
    print(
        "Module registry sync passed: the registry baked into "
        f"{PATCH_NAME} is byte-identical to first_party/."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
