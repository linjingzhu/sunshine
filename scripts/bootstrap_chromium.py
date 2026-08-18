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

# `fetch chromium` is exactly `gclient config` followed by `gclient sync
# --nohooks`, and it exposes no way to bound concurrency. gclient defaults to one
# job per core, so a 24-thread runner opens 24 anonymous clones against
# chromium.googlesource.com and the server answers HTTP 429:
#
#   RESOURCE_EXHAUSTED  subject: "shared/shared_anonymous"
#   "Short term server-time rate limit exceeded"
#
# Running the two steps directly lets the job count be bounded. Authenticating to
# googlesource leaves the shared anonymous quota pool entirely and is the better
# fix; see docs/WINDOWS_CHROMIUM_BUILD.md.
#
# checkout_pgo_profiles is off by default, and without it an official build
# stops during GN generation: default_pgo_flags asks update_pgo_profiles.py for
# a profile path and gets nothing. Turning off PGO instead would quietly weaken
# the release configuration that docs/SIZE_BUDGET.md pins.
CHROMIUM_SPEC = (
    'solutions = [\n'
    '  {\n'
    '    "name": "src",\n'
    '    "url": "https://chromium.googlesource.com/chromium/src.git",\n'
    '    "custom_deps": {},\n'
    '    "custom_vars": {"checkout_pgo_profiles": True},\n'
    '  },\n'
    ']\n'
)
DEFAULT_SYNC_JOBS = 8


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


def patch_created_paths(patch_path: pathlib.Path) -> set[str]:
    """Repository paths a unified diff *adds*, headed `--- /dev/null`.

    These are the paths that survive a reset, and knowing which they are is what
    lets the reset stay surgical. `git checkout --force` reverts modifications to
    tracked files; a file the patch stack created is untracked, so git has no
    opinion about it and leaves it exactly where the last build put it. The next
    `git apply` then refuses the whole patch with `already exists in working
    directory`.

    `git clean` would remove them, and also `out/Sunshine` -- hours of
    incremental build, deleted to fix a seven-file problem. So the stack's own
    declaration of what it creates is the list, and nothing outside it is
    touched.
    """

    paths: set[str] = set()
    lines = patch_path.read_text().splitlines()
    for index, line in enumerate(lines):
        match = re.match(r"^\+\+\+ b/(.+)$", line)
        if match and index and lines[index - 1].rstrip() == "--- /dev/null":
            paths.add(match.group(1))
    return paths


def remove_created_paths(src: pathlib.Path, patch_names: list[str]) -> None:
    """Delete the files the stack creates, so the stack can create them again."""

    for patch_name in patch_names:
        for path in sorted(patch_created_paths(ROOT / "downstream/patches" / patch_name)):
            target = src / path
            if target.is_file():
                target.unlink()
                print(f"reset: {path}")


def overlay_assets() -> dict[str, pathlib.Path]:
    """Chromium-relative destination -> the repository file that replaces it.

    The mapping is the directory layout: `downstream/assets/` mirrors the
    Chromium tree, so nothing has to be declared twice and the two halves cannot
    drift apart. `scripts/verify_asset_overlay.py` is the guard on the contents;
    this is only the reader.
    """

    base = ROOT / "downstream/assets"
    if not base.is_dir():
        return {}
    return {
        path.relative_to(base).as_posix(): path
        for path in sorted(base.rglob("*"))
        if path.is_file()
    }


def apply_overlay(src: pathlib.Path) -> None:
    """Copy the binary assets the patch stack cannot carry.

    After the patches, deliberately. A patch that edited the same path would
    have its edit discarded here, which is why `verify_asset_overlay.py` refuses
    that overlap outright rather than leaving the order to decide it.

    Every destination must already exist. Chromium reads these by fixed path
    from `.rc` files, so writing one that upstream does not have produces a file
    nothing compiles and a build that silently keeps the old icon.
    """

    for destination, source in overlay_assets().items():
        target = src / destination
        if not target.exists():
            raise SystemExit(
                f"overlay destination is not in the Chromium checkout: {destination}"
            )
        shutil.copyfile(source, target)
        print(f"overlay: {destination}")


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
    expected_paths: set[str] = set(overlay_assets())
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
    parser.add_argument(
        "--jobs",
        type=int,
        default=DEFAULT_SYNC_JOBS,
        help=(
            "parallel gclient jobs. gclient otherwise uses one per core, which "
            "an anonymous client cannot sustain against googlesource."
        ),
    )
    args = parser.parse_args()

    if args.jobs < 1:
        raise SystemExit("--jobs must be at least 1")
    if not shutil.which("gclient"):
        raise SystemExit("depot_tools is required and must be on PATH")

    workspace = args.workspace.resolve()
    src = workspace / "src"
    jobs = f"-j{args.jobs}"
    if not args.skip_fetch:
        workspace.mkdir(parents=True, exist_ok=True)
        # Written directly rather than through `gclient config --spec`. The
        # depot_tools entry point is a .bat, so the spec would travel through
        # cmd.exe, which cannot carry the embedded newlines: gclient received
        # one mangled line and reported a syntax error at character 13. The
        # file is the whole of what that command produces.
        #
        # Rewritten on every run, so an existing workspace picks up a changed
        # spec -- such as newly requesting PGO profiles -- on its next sync.
        (workspace / ".gclient").write_text(CHROMIUM_SPEC, encoding="utf-8")
        if not src.exists():
            run("gclient", "sync", "--nohooks", jobs, cwd=workspace)

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

    # Returning early here is for a person re-running the bootstrap over their
    # own checkout. A build-owned workspace must always reach the sync below:
    # gclient reads .gclient there, so skipping it means a changed spec never
    # takes effect. Requesting PGO profiles looked applied for two runs while
    # this path quietly returned first, and the build failed the same way twice.
    if dirty_paths(src) and not args.reset:
        if current_head == fetched_head and patch_stack_is_applied(src, patch_names):
            print(f"Sunshine Chromium checkout already ready at {src}")
            return 0
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

    # An interrupted sync can leave a dependency checkout that gclient will not
    # reconcile on its own; it tries to rebase and gives up with "Unrecognized
    # error, please merge or rebase manually". In a build-owned workspace the
    # pinned revision always wins, so force a hard checkout of the dependency
    # rather than requiring someone to repair it by hand. Untracked trees are
    # deliberately left alone, which keeps out/Sunshine and its incremental
    # build intact.
    sync = ["gclient", "sync", jobs]
    if args.reset:
        sync += ["--force", "--reset"]
    run(*sync, cwd=workspace)

    # Before the first `git apply --check`, not after a failure. A patch that
    # creates files is all-or-nothing: `git apply` rejects the entire patch when
    # one target already exists, so the seven files patch 0004 adds stopped
    # build #18 before a single object compiled.
    remove_created_paths(src, patch_names)

    for patch_name in patch_names:
        patch_path = ROOT / "downstream/patches" / patch_name
        run("git", "apply", "--check", str(patch_path), cwd=src)
        run("git", "apply", str(patch_path), cwd=src)

    apply_overlay(src)

    print(f"Sunshine Chromium checkout ready at {src}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
