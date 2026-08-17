#!/usr/bin/env python3
"""Create a pinned Chromium checkout and apply the Sunshine patch stack."""

from __future__ import annotations

import argparse
import pathlib
import re
import shutil
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]


def executable(name: str) -> str:
    """Resolve a tool to a full path before launching it.

    depot_tools ships `fetch`, `gclient`, and `gn` as `.bat` shims. Windows
    `CreateProcess`, which `subprocess` uses, does not apply `PATHEXT`, so a bare
    name raises `FileNotFoundError` even though the shim is on `PATH` and a shell
    resolves it fine. `shutil.which` applies `PATHEXT` and returns the shim
    itself, which `subprocess` can then launch.
    """

    resolved = shutil.which(name)
    if resolved is None:
        raise SystemExit(f"required command is not on PATH: {name}")
    return resolved


def run(*args: str, cwd: pathlib.Path | None = None) -> None:
    subprocess.run((executable(args[0]), *args[1:]), cwd=cwd, check=True)


def read_revision() -> str:
    for line in (ROOT / "config/chromium.version").read_text().splitlines():
        if line.startswith("CHROMIUM_REVISION="):
            return line.split("=", 1)[1].strip()
    raise RuntimeError("CHROMIUM_REVISION is missing")


def read_series() -> list[str]:
    path = ROOT / "downstream/patches/series"
    return [line.strip() for line in path.read_text().splitlines() if line.strip() and not line.startswith("#")]


def patch_paths(patch_path: pathlib.Path) -> set[str]:
    """Return repository paths changed by a unified diff."""
    paths: set[str] = set()
    for line in patch_path.read_text().splitlines():
        match = re.match(r"^\+\+\+ b/(.+)$", line)
        if match:
            paths.add(match.group(1))
    return paths


def dirty_paths(src: pathlib.Path) -> set[str]:
    output = subprocess.run(
        (executable("git"), "status", "--porcelain=v1", "-z"),
        cwd=src,
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    paths: set[str] = set()
    for entry in output.split("\0"):
        if not entry:
            continue
        path = entry[3:]
        if " -> " in path:
            path = path.split(" -> ", 1)[1]
        paths.add(path)
    return paths


def patch_stack_is_applied(src: pathlib.Path, patch_names: list[str]) -> bool:
    expected_paths: set[str] = set()
    for patch_name in patch_names:
        patch_path = ROOT / "downstream/patches" / patch_name
        expected_paths.update(patch_paths(patch_path))
        result = subprocess.run(
            (executable("git"), "apply", "--reverse", "--check", str(patch_path)),
            cwd=src,
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        if result.returncode != 0:
            return False
    return bool(expected_paths) and dirty_paths(src) == expected_paths


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workspace", type=pathlib.Path, default=ROOT / "chromium")
    parser.add_argument("--skip-fetch", action="store_true")
    parser.add_argument(
        "--reset",
        action="store_true",
        help=(
            "discard modifications to tracked upstream files in a build-owned workspace. "
            "Untracked build output such as out/ is never touched."
        ),
    )
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

    revision = read_revision()
    patch_names = read_series()
    run("git", "fetch", "origin", revision, "--depth=1", cwd=src)
    current_head = subprocess.run(
        (executable("git"), "rev-parse", "HEAD"), cwd=src, check=True, capture_output=True, text=True
    ).stdout.strip()
    fetched_head = subprocess.run(
        (executable("git"), "rev-parse", "FETCH_HEAD"), cwd=src, check=True, capture_output=True, text=True
    ).stdout.strip()

    if dirty_paths(src):
        if current_head == fetched_head and patch_stack_is_applied(src, patch_names):
            print(f"Sunshine Chromium checkout already ready at {src}")
            return 0
        if not args.reset:
            raise SystemExit(
                "Chromium checkout has uncommitted changes that are not exactly the current "
                "Sunshine patch stack. Preserve or remove those changes before bootstrapping, "
                "or pass --reset in a build-owned workspace."
            )

    # A build workspace holds the previous wave's patch stack, so every patch
    # change would otherwise stop the next build for manual cleanup. --force
    # discards modifications to tracked upstream files only; untracked build
    # output such as out/Sunshine survives, keeping the incremental build.
    checkout = ["git", "checkout", "--detach"]
    if args.reset:
        checkout.append("--force")
    run(*checkout, "FETCH_HEAD", cwd=src)
    run("gclient", "sync", cwd=workspace)

    for patch_name in patch_names:
        patch_path = ROOT / "downstream/patches" / patch_name
        run("git", "apply", "--check", str(patch_path), cwd=src)
        run("git", "apply", str(patch_path), cwd=src)

    print(f"Sunshine Chromium checkout ready at {src}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
