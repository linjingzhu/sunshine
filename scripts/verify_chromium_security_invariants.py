#!/usr/bin/env python3
"""Fail when Sunshine would weaken a Chromium security boundary it inherits.

`docs/SECURITY_ARCHITECTURE_CONTRACT.md` states the principle these two
invariants come from: Sunshine does not replace Chromium's security boundaries,
it adds privileges behind them. The renderer sandbox and site isolation are the
two boundaries every other guarantee in that document rests on, and until this
check existed nothing in the repository mentioned either of them -- a build
argument or a patch turning one off would have been reviewed like any other
line.

    SEC-1  no configuration or patch disables the sandbox
    SEC-2  no configuration or patch disables or weakens site isolation

**The switch names are upstream's, not remembered.** They were read at the
pinned revision from
[`sandbox/policy/switches.cc`](https://github.com/chromium/chromium/blob/152.0.7977.42/sandbox/policy/switches.cc)
and
[`content/public/common/content_switches.cc`](https://github.com/chromium/chromium/blob/152.0.7977.42/content/public/common/content_switches.cc).
That matters: an earlier draft of the security document called the flag
`disable-site-isolation`, which is not a switch Chromium has. A guard spelled
that way would have passed forever while catching nothing.

**Enabling switches are deliberately absent from the prohibition.**
`site-per-process` and `isolate-origins` strengthen isolation, and a guard that
matched the substring `site-per-process` would fire on the fix as well as the
defect.

Enforces: SEC-1, SEC-2, SECA-8.
"""

from __future__ import annotations

from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]

SEARCHED = ("first_party", "downstream", "scripts", "config", ".github")

# A guard has to name what it forbids, so scanning the guards for the words they
# forbid is a check that fails on itself. Same convention as
# `scripts/verify_no_interposition.py`.
GUARD_PREFIXES = ("verify_", "validate_", "test_")
SKIPPED_PARTS = frozenset({"__pycache__", ".git"})

# From sandbox/policy/switches.cc at the pinned revision. Every one of these
# turns off a sandbox or lowers its bar; `service-sandbox-type` and the process
# type names in the same file are not prohibitions and are absent.
SANDBOX_SWITCHES = (
    "no-sandbox",
    "no-zygote-sandbox",
    "disable-gpu-sandbox",
    "disable-landlock-sandbox",
    "disable-namespace-sandbox",
    "disable-seccomp-filter-sandbox",
    "disable-setuid-sandbox",
    "disable-webnn-compiler-sandbox",
    "allow-sandbox-debugging",
    # Windows-specific, and the runner's platform: it readmits third-party DLLs
    # that Chromium blocks from the browser process.
    "allow-third-party-modules",
)

# From content/public/common/content_switches.cc at the pinned revision.
ISOLATION_SWITCHES = (
    "disable-site-isolation-trials",
    "disable-site-isolation-for-policy",
    # Not an isolation switch by name, and the most complete removal of the
    # boundary there is: the renderer runs inside the browser process.
    "single-process",
    "disable-web-security",
    "allow-insecure-localhost",
)

# Upstream areas that own these boundaries. A patch reaching one of them is not
# necessarily wrong, but it is never a routine downstream change, and the patch
# stack is meant to stay small and reviewable.
PROTECTED_AREAS = (
    "sandbox/",
    "content/browser/site_instance",
    "content/public/browser/site_isolation_policy",
    "content/browser/renderer_host/render_process_host",
)

PATCH_TARGET = re.compile(r"^\+\+\+ b/(.+)$", re.MULTILINE)


def _is_guard(path: Path) -> bool:
    return path.name.startswith(GUARD_PREFIXES)


def added_lines(patch_text: str) -> str:
    """The Sunshine-authored half of a patch.

    A `+++ b/path` header also starts with `+` and names an upstream file, so it
    is removed here and read separately by `patched_paths`.
    """

    return "\n".join(
        line[1:] for line in patch_text.splitlines()
        if line.startswith("+") and not line.startswith("+++")
    )


def sunshine_sources(root: Path) -> list[tuple[str, str]]:
    sources: list[tuple[str, str]] = []
    for directory in SEARCHED:
        base = root / directory
        if not base.is_dir():
            continue
        for path in sorted(base.rglob("*")):
            if not path.is_file() or SKIPPED_PARTS & set(path.parts) or _is_guard(path):
                continue
            try:
                text = path.read_text(encoding="utf-8")
            except (UnicodeDecodeError, OSError):
                continue
            relative = path.relative_to(root).as_posix()
            if path.suffix == ".patch":
                sources.append((f"{relative} (added lines)", added_lines(text)))
            else:
                sources.append((relative, text))
    return sources


def switch_pattern(switch: str) -> re.Pattern[str]:
    """Match the switch as a whole token, with or without its leading dashes.

    The left boundary excludes word characters but *not* a hyphen, because the
    ordinary way to write one of these is `--no-sandbox` and a hyphen-excluding
    lookbehind rejects every real occurrence. The right boundary does exclude
    the hyphen, so `--no-sandbox-something`, which is not a switch Chromium has,
    is not reported as one.
    """

    return re.compile(rf"(?<![A-Za-z0-9_]){re.escape(switch)}(?![A-Za-z0-9_-])")


def check_switches(root: Path, failures: list[str]) -> None:
    prohibited = [
        (switch, "SEC-1", "disables a sandbox") for switch in SANDBOX_SWITCHES
    ] + [
        (switch, "SEC-2", "disables or weakens site isolation") for switch in ISOLATION_SWITCHES
    ]
    for label, text in sunshine_sources(root):
        for switch, invariant, why in prohibited:
            if switch_pattern(switch).search(text):
                failures.append(f"{label}: {switch!r} {why} ({invariant})")


def patched_paths(root: Path) -> list[tuple[str, str]]:
    found: list[tuple[str, str]] = []
    for patch in sorted((root / "downstream/patches").glob("*.patch")):
        for target in PATCH_TARGET.findall(patch.read_text(encoding="utf-8")):
            found.append((patch.name, target))
    return found


def check_protected_areas(root: Path, failures: list[str]) -> None:
    for patch_name, target in patched_paths(root):
        for area in PROTECTED_AREAS:
            if target.startswith(area):
                failures.append(
                    f"{patch_name}: patches {target}, which owns a security boundary "
                    "Sunshine inherits rather than maintains (SEC-1, SEC-2)"
                )


def validate(root: Path = ROOT) -> list[str]:
    failures: list[str] = []
    check_switches(root, failures)
    check_protected_areas(root, failures)
    return failures


def main() -> int:
    failures = validate()
    if failures:
        print("\n".join(failures), file=sys.stderr)
        return 1
    print("Chromium security invariants passed: sandbox and site isolation intact.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
