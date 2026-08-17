#!/usr/bin/env python3
"""Fail when excluded wrapper runtimes return to Sunshine OS."""

from __future__ import annotations

import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
EXCLUDED_NAMES = {"package.json", "electron-builder.yml", "electron-builder.yaml"}
EXCLUDED_TEXT = ("from \"electron\"", "require(\"electron\")", "electron-builder", "WebContentsView")
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
        if path.resolve() == pathlib.Path(__file__).resolve():
            continue
        if path.name in EXCLUDED_NAMES:
            failures.append(f"excluded wrapper manifest: {relative}")
            continue
        try:
            text = path.read_text()
        except UnicodeDecodeError:
            continue
        for marker in EXCLUDED_TEXT:
            if marker in text:
                failures.append(f"excluded runtime marker {marker!r}: {relative}")
        for marker in EXCLUDED_DESIGN_TEXT:
            if marker in text:
                failures.append(f"excluded wrapper-runtime design marker {marker!r}: {relative}")
        if relative.parts[0] in DOCUMENTATION_ROOTS:
            continue
        if GOOGLE_STARTUP_URL in text:
            failures.append(f"hardcoded Google startup URL: {relative}")
    if failures:
        print("\n".join(failures), file=sys.stderr)
        return 1
    print("Architecture check passed: native Chromium downstream; no Electron runtime markers.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
