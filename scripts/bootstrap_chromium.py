#!/usr/bin/env python3
"""Create a pinned Chromium checkout and apply the Sunshine patch stack."""

from __future__ import annotations

import argparse
import pathlib
import shutil
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]


def run(*args: str, cwd: pathlib.Path | None = None) -> None:
    subprocess.run(args, cwd=cwd, check=True)


def read_revision() -> str:
    for line in (ROOT / "config/chromium.version").read_text().splitlines():
        if line.startswith("CHROMIUM_REVISION="):
            return line.split("=", 1)[1].strip()
    raise RuntimeError("CHROMIUM_REVISION is missing")


def read_series() -> list[str]:
    path = ROOT / "downstream/patches/series"
    return [line.strip() for line in path.read_text().splitlines() if line.strip() and not line.startswith("#")]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workspace", type=pathlib.Path, default=ROOT / "chromium")
    parser.add_argument("--skip-fetch", action="store_true")
    args = parser.parse_args()

    if not shutil.which("fetch") or not shutil.which("gclient"):
        raise SystemExit("depot_tools is required and must be on PATH")

    workspace = args.workspace.resolve()
    src = workspace / "src"
    if not args.skip_fetch:
        workspace.mkdir(parents=True, exist_ok=True)
        if not src.exists():
            run("fetch", "--nohooks", "chromium", cwd=workspace)

    if not (src / ".git").exists():
        raise SystemExit(f"Chromium checkout not found: {src}")

    run("git", "fetch", "origin", read_revision(), "--depth=1", cwd=src)
    run("git", "checkout", "--detach", "FETCH_HEAD", cwd=src)
    run("gclient", "sync", "--with_branch_heads", "--with_tags", cwd=workspace)

    for patch_name in read_series():
        patch_path = ROOT / "downstream/patches" / patch_name
        run("git", "apply", "--check", str(patch_path), cwd=src)
        run("git", "apply", str(patch_path), cwd=src)

    print(f"Sunshine Chromium checkout ready at {src}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
