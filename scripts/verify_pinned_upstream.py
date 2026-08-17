#!/usr/bin/env python3
"""Check that the pinned Chromium revision still supports the patch stack.

Everything here needs the upstream sources, so it cannot run from the patch
files alone. Three questions are asked of the pinned revision:

1. the ordered patch stack applies to it,
2. the native integration seams the workspace design depends on still exist,
3. the New Tab tokens the wordmark consumes without a fallback still exist.

Each token is checked against the source that defines it. `--ntp-theme-text-shadow`
is a plain custom property declared in `app.css`. `--color-new-tab-page-*` tokens
are not declared in any stylesheet: Chromium emits them from the colour IDs in
`chrome_color_id.h` and serves them through `chrome://theme`, so absence from
`app.css` is not absence. Grepping the stylesheet for both -- which this check
first did, in bash, inside the workflow -- fails the build on a token that
exists. That is why this lives in one tested place instead of two untested ones.

`--source github` reads the same revision from the GitHub mirror. It is a
convenience for environments whose egress policy blocks the authoritative host,
not a second source of truth: CI runs the default.
"""

from __future__ import annotations

import argparse
import base64
from pathlib import Path
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request

ROOT = Path(__file__).resolve().parents[1]

SOURCES = {
    "googlesource": (
        "https://chromium.googlesource.com/chromium/src/+/refs/tags/{version}/{path}?format=TEXT",
        True,
    ),
    "github": (
        "https://raw.githubusercontent.com/chromium/chromium/{version}/{path}",
        False,
    ),
}

# path -> ((description, needle), ...). A needle is matched against the file as
# a whole; SECTION_SEAMS below covers the cases where position matters.
SEAMS: dict[str, tuple[tuple[str, str], ...]] = {
    "chrome/browser/ui/tabs/tab_strip_model.h": (("TabStripModel", "class TabStripModel"),),
    "chrome/browser/ui/tabs/tab_group_model.h": (("TabGroupModel", "class TabGroupModel"),),
    "chrome/browser/ui/tabs/tab_strip_model_observer.h": (
        ("tab strip change notification", "OnTabStripModelChanged"),
    ),
    "components/sessions/core/session_service_commands.cc": (
        ("tab extra-data command", "CreateAddTabExtraDataCommand"),
        ("window extra-data command", "CreateAddWindowExtraDataCommand"),
    ),
}

# Workspace state rides on these fields specifically, so finding `extra_data`
# anywhere in the file would not be evidence.
SECTION_SEAMS: tuple[tuple[str, str, str, str], ...] = (
    (
        "components/sessions/core/session_types.h",
        "SessionTab.extra_data",
        "struct SESSIONS_EXPORT SessionTab {",
        "extra_data",
    ),
    (
        "components/sessions/core/session_types.h",
        "SessionWindow.extra_data",
        "struct SESSIONS_EXPORT SessionWindow {",
        "extra_data",
    ),
)

TOKENS: tuple[tuple[str, str, str, str], ...] = (
    (
        "chrome/browser/resources/new_tab_page/app.css",
        "--ntp-theme-text-shadow",
        "--ntp-theme-text-shadow:",
        "app.css no longer declares the shadow token",
    ),
    (
        "chrome/browser/ui/color/chrome_color_id.h",
        "--color-new-tab-page-primary-foreground",
        "kColorNewTabPagePrimaryForeground",
        "the colour ID that emits the wordmark's colour is gone",
    ),
)


class UpstreamCheckError(RuntimeError):
    pass


def pinned_version(root: Path = ROOT) -> str:
    for line in (root / "config/chromium.version").read_text(encoding="utf-8").splitlines():
        if line.startswith("CHROMIUM_REVISION="):
            return line.split("=", 1)[1].strip().removeprefix("refs/tags/")
    raise UpstreamCheckError("config/chromium.version has no CHROMIUM_REVISION")


def fetch(source: str, version: str, path: str) -> str:
    template, encoded = SOURCES[source]
    url = template.format(version=version, path=path)
    try:
        with urllib.request.urlopen(url, timeout=60) as response:
            payload = response.read()
    except urllib.error.URLError as error:
        raise UpstreamCheckError(f"could not read {path} at {version}: {error}") from error
    if encoded:
        payload = base64.b64decode(payload)
    return payload.decode("utf-8", errors="replace")


def section(text: str, opening: str) -> str:
    """The struct body starting at `opening`, up to the closing brace."""

    start = text.find(opening)
    if start == -1:
        return ""
    end = text.find("\n};", start)
    return text[start : end if end != -1 else len(text)]


def check_patch_stack(source: str, version: str, root: Path, report: list[str]) -> bool:
    entries = subprocess.run(
        [sys.executable, str(root / "scripts/patch_manifest.py"), "--paths"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.split()
    if not entries:
        raise UpstreamCheckError("patch manifest returned no upstream targets")

    series = [
        line.strip()
        for line in (root / "downstream/patches/series").read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]

    with tempfile.TemporaryDirectory() as directory:
        worktree = Path(directory)
        for path in entries:
            target = worktree / path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(fetch(source, version, path), encoding="utf-8")

        git = ["git", "-C", str(worktree)]
        subprocess.run([*git, "init", "--quiet"], check=True)
        subprocess.run([*git, "add", "."], check=True)
        subprocess.run(
            [*git, "-c", "user.name=check", "-c", "user.email=check@localhost",
             "commit", "--quiet", "-m", "upstream-inputs"],
            check=True,
        )

        healthy = True
        for entry in series:
            patch = root / "downstream/patches" / entry
            applied = subprocess.run([*git, "apply", str(patch)], capture_output=True, text=True)
            if applied.returncode == 0:
                report.append(f"  OK   patch applies: {entry}")
            else:
                report.append(f"  FAIL patch does not apply: {entry}: {applied.stderr.strip()}")
                healthy = False
        return healthy


def verify(source: str = "googlesource", root: Path = ROOT) -> tuple[bool, list[str]]:
    version = pinned_version(root)
    report = [f"Pinned Chromium {version} via {source}"]
    healthy = True

    for path, expectations in sorted(SEAMS.items()):
        text = fetch(source, version, path)
        for description, needle in expectations:
            if needle in text:
                report.append(f"  OK   seam: {description}")
            else:
                report.append(f"  FAIL seam absent upstream: {description} ({needle})")
                healthy = False

    for path, description, opening, needle in SECTION_SEAMS:
        body = section(fetch(source, version, path), opening)
        if needle in body:
            report.append(f"  OK   seam: {description}")
        else:
            report.append(f"  FAIL seam absent upstream: {description}")
            healthy = False

    for path, token, needle, explanation in TOKENS:
        if needle in fetch(source, version, path):
            report.append(f"  OK   token: {token}")
        else:
            report.append(f"  FAIL token: {token} -- {explanation}")
            report.append(f"       checked for {needle!r} in {path}")
            healthy = False

    healthy = check_patch_stack(source, version, root, report) and healthy
    return healthy, report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--source",
        choices=sorted(SOURCES),
        default="googlesource",
        help="where to read the pinned revision; the default is authoritative",
    )
    arguments = parser.parse_args()

    try:
        healthy, report = verify(arguments.source)
    except UpstreamCheckError as error:
        print(f"Pinned upstream check failed: {error}", file=sys.stderr)
        return 1

    print("\n".join(report))
    if not healthy:
        print("Pinned upstream no longer satisfies the patch stack.", file=sys.stderr)
        return 1
    print("Pinned upstream check passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
