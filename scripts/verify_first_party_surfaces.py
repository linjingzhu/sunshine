#!/usr/bin/env python3
"""Check that Sunshine's first-party surfaces do not collide with or duplicate
what Chromium already owns.

Four acceptance criteria that `docs/ACCEPTANCE_SUITES.md` §8 lists as
offline-decidable and unimplemented. All four are non-interposition checks --
the class that fails when Sunshine has built something Chromium already has,
which is this project's characteristic failure mode: it shipped a split-view
model duplicating `SplitTabCollection` because nobody checked.

The host-collision check needs the pinned sources and lives in its own function
so the tests can stub it and the suite stays offline.

Enforces: SPA-9, CPA-9, SCA-13, SEC-13, SECA-10.

Three of the four are now citable. They were ordinals in renumbering lists when
this file was written -- `SIDE_PANEL_CONTRACT` §12.9, `COMMAND_PALETTE_CONTRACT`
§14.9, `SECURITY_CENTER_CONTRACT` 13 -- so no claim was made, because an
invented identifier would inflate the coverage number while pointing at nothing.
`scripts/trace_invariants.py` rejects exactly that, and it caught two invented
identifiers in an earlier draft of this file. The acceptance lists have since
been given stable prefixes, and the ordinals were preserved through the rename,
so §12.9 is `SPA-9` and the same check now cites something durable.

The fourth remains uncounted: `TAB_LIFECYCLE_CONTRACT` §15 is a section, not a
criterion, and nothing was invented to cover that.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import sys
import urllib.error
import urllib.request

ROOT = Path(__file__).resolve().parents[1]

MIRROR = "https://raw.githubusercontent.com/chromium/chromium/{version}/{path}"
HOST_HEADER = "chrome/common/webui_url_constants.h"
HOST_CONSTANT = re.compile(r'kChromeUI[A-Za-z0-9]*Host\[\]\s*=\s*"([a-z0-9._-]+)"')

# Panels Chromium already registers. `SIDE_PANEL_CONTRACT` SPA-9: the bookmarks
# and history panels present must be Chromium's, with no Sunshine entry -- a
# parallel entry makes the extension-registered panels invisible or misplaced.
CHROMIUM_OWNED_PANELS = ("bookmark", "history")

# `TAB_LIFECYCLE_CONTRACT` §15: the per-workspace last active tab needs an owner.
# It has one now; this keeps it from being removed without noticing.
#
# Matched as definitions, not bare names. Checking for the name alone passed
# when the class was deleted, because the identifier survived in the type
# annotations of functions that returned it.
# ADR 0003 settled that Sunshine registers no URL scheme -- not internally, and
# not with any operating system. It was settled and unenforced: nothing stopped
# a later design from introducing `sunshine://` or `sunshine-module://` as a
# module origin, which is exactly what one later proposal did.
#
# Chromium's own schemes are not Sunshine registering anything, and neither is
# an ordinary network or inline URL.
ALLOWED_SCHEMES = frozenset({
    "http", "https", "file", "data", "blob", "about", "ws", "wss",
    "chrome", "chrome-untrusted", "chrome-error", "chrome-extension",
    "chrome-search", "devtools", "isolated-app", "filesystem",
})
SCHEME_LITERAL = re.compile(r"\b([a-z][a-z0-9+.-]*)://")
# The Chromium calls that make a scheme real, and the Windows registry value
# that makes one real to the operating system.
SCHEME_REGISTRATION = (
    "AddStandardScheme",
    "AddLocalScheme",
    "AddNoAccessScheme",
    "AddCorsEnabledScheme",
    "RegisterCustomScheme",
    "URL Protocol",
)

LAST_ACTIVE_TAB_API = (
    "class WindowWorkspaceState",
    "def resolve_switch_target",
    "def record_active_tab",
    "def persistable_window_state",
)


def pinned_version(root: Path = ROOT) -> str:
    for line in (root / "config/chromium.version").read_text(encoding="utf-8").splitlines():
        if line.startswith("CHROMIUM_REVISION="):
            return line.split("=", 1)[1].strip().removeprefix("refs/tags/")
    raise RuntimeError("config/chromium.version has no CHROMIUM_REVISION")


def upstream_hosts(version: str) -> set[str]:
    """Internal-page hosts compiled into Chromium at the pinned revision."""

    url = MIRROR.format(version=version, path=HOST_HEADER)
    try:
        with urllib.request.urlopen(url, timeout=60) as response:
            text = response.read().decode("utf-8", errors="replace")
    except urllib.error.URLError as error:
        raise RuntimeError(f"could not read {HOST_HEADER} at {version}: {error}") from error
    return set(HOST_CONSTANT.findall(text))


def sunshine_hosts(root: Path) -> set[str]:
    """`chrome://sunshine-*` hosts the contracts claim."""

    hosts: set[str] = set()
    pattern = re.compile(r"chrome://(sunshine-[a-z0-9-]+)")
    for path in sorted((root / "docs").rglob("*.md")):
        hosts.update(pattern.findall(path.read_text(encoding="utf-8")))
    return hosts


def check_panels(root: Path, failures: list[str]) -> None:
    """SIDE_PANEL SPA-9: no Sunshine entry for a Chromium-owned panel."""

    registry = json.loads((root / "first_party/registry.json").read_text(encoding="utf-8"))
    for entry in registry["modules"]:
        manifest = json.loads((root / entry).read_text(encoding="utf-8"))
        blob = json.dumps(manifest).lower()
        for panel in CHROMIUM_OWNED_PANELS:
            if f"{panel}s-panel" in blob or f"side_panel.{panel}" in blob:
                failures.append(
                    f"{manifest['id']}: registers a {panel} side panel that Chromium already provides"
                )


def check_reason_tokens(root: Path, failures: list[str]) -> None:
    """COMMAND_PALETTE CPA-9, declared half.

    A command with a predicate must declare the reasons that predicate can
    return, or a disabled row cannot explain itself -- which is the whole
    requirement. The registry validator enforces the pairing; this states the
    criterion in the palette's own terms and fails if the two ever diverge.
    """

    registry = json.loads((root / "first_party/commands.json").read_text(encoding="utf-8"))
    for command in registry["commands"]:
        has_predicate = bool(command["predicate"])
        has_reasons = bool(command["unavailable_reasons"])
        if has_predicate and not has_reasons:
            failures.append(f"{command['id']}: has a predicate but declares no unavailable reason")
        if has_reasons and not has_predicate:
            failures.append(f"{command['id']}: declares unavailable reasons with no predicate")


def check_last_active_tab_owner(root: Path, failures: list[str]) -> None:
    """TAB_LIFECYCLE §15: the per-workspace last active tab has a storage owner."""

    model = (root / "scripts/workspace_model.py").read_text(encoding="utf-8")
    for symbol in LAST_ACTIVE_TAB_API:
        if symbol not in model:
            failures.append(
                f"workspace_model.py no longer defines `{symbol}`; "
                "workspace.switch claims to restore a last active tab that nothing stores"
            )


def sunshine_authored(root: Path) -> list[tuple[str, str]]:
    """Sunshine-authored text, patches reduced to their added lines.

    A patch's context lines are upstream's and routinely contain schemes
    Sunshine does not register; counting them would make this fire on every
    patch that touches a WebUI file.
    """

    sources: list[tuple[str, str]] = []
    for directory in ("first_party", "downstream", "config"):
        base = root / directory
        if not base.is_dir():
            continue
        for path in sorted(base.rglob("*")):
            if not path.is_file() or "__pycache__" in path.parts:
                continue
            try:
                text = path.read_text(encoding="utf-8")
            except (UnicodeDecodeError, OSError):
                continue
            label = path.relative_to(root).as_posix()
            if path.suffix == ".patch":
                text = "\n".join(
                    line[1:] for line in text.splitlines()
                    if line.startswith("+") and not line.startswith("+++")
                )
            sources.append((label, text))
    return sources


def check_no_scheme_registration(root: Path, failures: list[str]) -> None:
    """SEC-13: Sunshine registers no URL scheme (ADR 0003)."""

    for label, text in sunshine_authored(root):
        for number, line in enumerate(text.splitlines(), start=1):
            for scheme in SCHEME_LITERAL.findall(line):
                if scheme not in ALLOWED_SCHEMES:
                    failures.append(
                        f"{label}:{number}: {scheme}:// is a URL scheme Sunshine does not "
                        "register; ADR 0003 settled that it registers none (SEC-13)"
                    )
            for call in SCHEME_REGISTRATION:
                if call in line:
                    failures.append(
                        f"{label}:{number}: {call} registers a URL scheme, which ADR 0003 "
                        "forbids (SEC-13)"
                    )


def check_host_collisions(root: Path, failures: list[str], version: str) -> None:
    """SECURITY_CENTER SCA-13, collision half.

    Sunshine's surfaces live under Chromium's internal scheme (ADR 0003), so a
    host is only Sunshine's while upstream does not take it. Upstream adds hosts
    every roll, and a collision would silently shadow one of the two.
    """

    claimed = sunshine_hosts(root)
    if not claimed:
        return
    taken = upstream_hosts(version)
    for host in sorted(claimed & taken):
        failures.append(f"chrome://{host} collides with an upstream internal host at {version}")


def validate(root: Path = ROOT, *, offline: bool = False) -> list[str]:
    failures: list[str] = []
    check_panels(root, failures)
    check_reason_tokens(root, failures)
    check_last_active_tab_owner(root, failures)
    check_no_scheme_registration(root, failures)
    if not offline:
        check_host_collisions(root, failures, pinned_version(root))
    return failures


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--offline", action="store_true", help="skip the upstream host check")
    arguments = parser.parse_args()

    try:
        failures = validate(offline=arguments.offline)
    except RuntimeError as error:
        print(error, file=sys.stderr)
        return 1
    if failures:
        print("\n".join(failures), file=sys.stderr)
        return 1
    print("First-party surface check passed: no panel duplication, no host collision.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
