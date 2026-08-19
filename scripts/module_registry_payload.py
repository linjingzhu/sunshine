#!/usr/bin/env python3
"""The one canonical form of the first-party module registry.

`first_party/` is where a module is declared, and it is deliberately not
something Chromium can read: the manifests live in this repository, the browser
is built from a Chromium checkout, and nothing carries a directory of JSON files
across that gap. So `chrome://sunshine-modules` is served a copy, baked into
`downstream/patches/0007-sunshine-modules-webui.patch` as a string literal.

A copy is a thing that drifts. This module exists so that the copy has exactly
one definition -- byte for byte -- which the patch carries and
`scripts/verify_module_registry_sync.py` recomputes and compares. Without that,
the module home would eventually describe a registry that no longer exists, and
it would do so in the one surface whose entire job is to say what is installed.

The canonical form is `json.dumps(..., indent=2, sort_keys=True)` over the whole
manifests, in the order `first_party/registry.json` lists them. Whole manifests
rather than a projection, because a projection is a second schema: it would have
to be kept in step with the first one, and the drift it allowed would be
invisible in exactly the way this file exists to prevent.
"""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def payload(root: Path = ROOT) -> str:
    """The registry as the surface is served it. Ends with a newline."""

    registry = json.loads((root / "first_party/registry.json").read_text(encoding="utf-8"))
    modules = [
        json.loads((root / relative).read_text(encoding="utf-8"))
        for relative in registry["modules"]
    ]
    document = {"schema_version": registry["schema_version"], "modules": modules}
    return json.dumps(document, indent=2, sort_keys=True) + "\n"


def literal(root: Path = ROOT) -> str:
    """The payload exactly as the C++ raw string literal holds it.

    The header opens with `R"json(` and a newline, because putting the JSON on
    the same line as the delimiter would indent its first brace by the width of
    the declaration and make the header unreadable. That newline is part of the
    string, and `JSON.parse` skips leading whitespace, so it costs nothing at
    runtime -- but a byte comparison has to account for it, and this is where
    it is accounted for rather than in the guard's regular expression.
    """

    return "\n" + payload(root)


if __name__ == "__main__":
    print(payload(), end="")
