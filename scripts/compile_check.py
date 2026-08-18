#!/usr/bin/env python3
"""Byte-compile every repository Python tool.

This was two bash steps expressed with `mapfile` and process substitution, which
tie the check to a shell the self-hosted Windows runner does not reliably have.
The check itself is platform-neutral, so it lives here and both guards call it.
"""

from __future__ import annotations

import py_compile
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
SOURCES = ("scripts", "tests")


def compile_all(root: Path = ROOT) -> tuple[int, list[str]]:
    failures: list[str] = []
    paths = sorted(
        path
        for source in SOURCES
        for path in (root / source).rglob("*.py")
        if "__pycache__" not in path.parts
    )
    if not paths:
        return 0, [f"no Python tools found under {', '.join(SOURCES)}/"]

    for path in paths:
        try:
            py_compile.compile(str(path), doraise=True, quiet=1)
        except py_compile.PyCompileError as error:
            failures.append(f"{path.relative_to(root)}: {error.msg.strip()}")
    return len(paths), failures


def main() -> int:
    count, failures = compile_all()
    if failures:
        print("\n".join(failures), file=sys.stderr)
        return 1
    print(f"Compile check passed: {count} Python file(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
