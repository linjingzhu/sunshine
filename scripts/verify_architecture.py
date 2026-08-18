#!/usr/bin/env python3
"""Fail when excluded wrapper runtimes return to Sunshine OS."""

from __future__ import annotations

import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
EXCLUDED_NAMES = {"package.json", "electron-builder.yml", "electron-builder.yaml"}
# `WebContentsView` was here and has been removed deliberately. It is the name of
# a real Chromium type in content/, which this repository is a downstream of and
# is entitled to name -- a side panel or split-view patch reaches that layer
# directly. The wrapper runtime's class of the same name cannot be used without
# importing the runtime, which the markers below already catch, so the entry
# added no detection and would have failed the build on legitimate upstream
# terminology. `test_a_wrapper_view_class_is_still_caught_by_its_import` and
# `test_the_chromium_type_of_the_same_name_is_allowed` pin both halves of that.
EXCLUDED_TEXT = ("from \"electron\"", "require(\"electron\")", "electron-builder")
# Wrapper-runtime API and configuration names. Unlike EXCLUDED_TEXT these also
# appear in prose specifications, which is how a wrapper architecture survived in
# an active handoff document while the code tree was already clean. Plain
# prohibition prose naming a runtime is deliberately not matched.
EXCLUDED_DESIGN_TEXT = (
    "nodeIntegration",
    "contextIsolation",
    "webPreferences",
    "ipcRenderer",
    "ipcMain",
    "@electron/",
)
GOOGLE_STARTUP_URL = "https://www.google.com"
IGNORED_PARTS = {".git", "chromium", "node_modules", "dist", "release", ".ai", "upload"}
# Specifications are scanned for wrapper-runtime design, but not for a hardcoded
# startup URL: that rule constrains what the product ships, and documentation
# legitimately quotes the URL when stating that it must never be forced.
DOCUMENTATION_ROOTS = {"docs"}
PINNED_REVISION = re.compile(r"^refs/tags/\d+\.\d+\.\d+\.\d+$")
REQUIRED_NEW_TAB_MARKERS = (
    "chrome/browser/resources/new_tab_page/app.html",
    "chrome/browser/resources/new_tab_page/app.css",
    'id="sunshineWordmark"',
    'aria-label="Sunshine OS"',
    # The wordmark occupies the native logo slot, so it must keep the two
    # Chromium-owned behaviours that slot carries: the logo visibility state and
    # the theme-controlled spacing below it.
    '?hidden="${!this.logoEnabled_}"',
    "var(--ntp-logo-margin-bottom",
)
FORBIDDEN_NEW_TAB_MARKERS = ("Life Dashboard", "Three.js", "AI assistant")
FORBIDDEN_NEW_TAB_REMOVALS = ("-    <ntp-searchbox", "-      <cr-most-visited")


def validate_revision(failures: list[str]) -> None:
    version_path = ROOT / "config/chromium.version"
    if not version_path.is_file():
        failures.append("CHROMIUM_REVISION file missing: config/chromium.version")
        return
    revision = ""
    for line in version_path.read_text().splitlines():
        if line.startswith("CHROMIUM_REVISION="):
            revision = line.split("=", 1)[1].strip()
            break
    if not PINNED_REVISION.fullmatch(revision):
        failures.append("CHROMIUM_REVISION must be a pinned four-part refs/tags version")


def validate_patch_series(failures: list[str]) -> None:
    series_path = ROOT / "downstream/patches/series"
    if not series_path.is_file():
        failures.append("patch series missing: downstream/patches/series")
        return
    for entry in series_path.read_text().splitlines():
        patch_name = entry.strip()
        if not patch_name or patch_name.startswith("#"):
            continue
        if pathlib.PurePath(patch_name).name != patch_name:
            failures.append(f"invalid patch series entry: {patch_name}")
            continue
        if not (series_path.parent / patch_name).is_file():
            failures.append(f"missing downstream patch: {patch_name}")


def validate_new_tab_patch(failures: list[str]) -> None:
    patch_path = ROOT / "downstream/patches/0002-sunshine-new-tab.patch"
    if not patch_path.is_file():
        failures.append("Sunshine New Tab patch missing")
        return
    text = patch_path.read_text()
    for marker in REQUIRED_NEW_TAB_MARKERS:
        if marker not in text:
            failures.append(f"Sunshine New Tab patch missing required marker: {marker}")
    for marker in FORBIDDEN_NEW_TAB_MARKERS:
        if marker in text:
            failures.append(f"Stage 1 New Tab contains deferred feature marker: {marker}")
    for marker in FORBIDDEN_NEW_TAB_REMOVALS:
        if marker in text:
            failures.append(f"Stage 1 New Tab removes Chromium browser primitive: {marker[1:].strip()}")


def main() -> int:
    failures: list[str] = []
    validate_revision(failures)
    validate_patch_series(failures)
    validate_new_tab_patch(failures)
    for path in ROOT.rglob("*"):
        relative = path.relative_to(ROOT)
        if not path.is_file() or any(part in IGNORED_PARTS for part in relative.parts):
            continue
        # Reported with forward slashes on every platform. The first run of
        # this guard on the Windows build runner failed four of its own tests
        # -- they assert `src/legacy-wrapper.js` and the guard emitted
        # `src\legacy-wrapper.js` -- which is a real defect in the report, not
        # in the tests: a path in a failure message is quoted into commits,
        # issues and search, and it must not change shape with the machine that
        # happened to run the check. Every other guard in `scripts/` already
        # uses `as_posix()`; this one was the exception.
        reported = relative.as_posix()
        if path.resolve() == pathlib.Path(__file__).resolve():
            continue
        if path.name in EXCLUDED_NAMES:
            failures.append(f"excluded wrapper manifest: {reported}")
            continue
        try:
            text = path.read_text()
        except UnicodeDecodeError:
            continue
        for marker in EXCLUDED_TEXT:
            if marker in text:
                failures.append(f"excluded runtime marker {marker!r}: {reported}")
        for marker in EXCLUDED_DESIGN_TEXT:
            if marker in text:
                failures.append(f"excluded wrapper-runtime design marker {marker!r}: {reported}")
        if relative.parts[0] in DOCUMENTATION_ROOTS:
            continue
        if GOOGLE_STARTUP_URL in text:
            failures.append(f"hardcoded Google startup URL: {reported}")
    if failures:
        print("\n".join(failures), file=sys.stderr)
        return 1
    print("Architecture check passed: native Chromium downstream; no Electron runtime markers.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
