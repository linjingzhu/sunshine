#!/usr/bin/env python3
"""Check the module mount port against the contract that declares it.

The mount port is the one seam where content authored outside this project
reaches a page running at browser privilege. Everything about it that can be
decided from source is decided here rather than at run time, because the run
time is a browser nobody in CI has.

What is checked, and which invariant each check claims:

  * the message names in `mount_port.ts` are closed sets, and
    `docs/MODULE_MOUNT_CONTRACT.md` sections 3 and 4 name the same ones (MM-4);
  * `mount_port.ts` imports nothing (MM-3);
  * the manifest's URL shape and the port's URL shape accept the same set
    (MM-1), and only a surface module declares a mount (MM-2);
  * no field of the port is a URL, a path or a handle -- checked as the absence
    of the shapes that would carry one (MM-5);
  * the shell's receiver tests source, origin and payload, all three (MM-6);
  * the shell writes module strings with `textContent` and never as markup
    (MM-7);
  * a `describe` from the panel region is discarded (MM-8).

Enforces: MM-1, MM-2, MM-3, MM-4, MM-5, MM-6, MM-7, MM-8.
"""

from __future__ import annotations

import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import verify_patch_references  # noqa: E402

PORT = "chrome/browser/resources/sunshine/shell/mount_port.ts"
MOUNT = "chrome/browser/resources/sunshine/shell/mount.ts"
APP = "chrome/browser/resources/sunshine/shell/app.ts"
CONTRACT = "docs/MODULE_MOUNT_CONTRACT.md"

# `export const NAME = ['a', 'b'] as const;`, possibly spread over lines.
CONST_LIST = re.compile(
    r"export const (?P<name>[A-Z_]+) = \[(?P<body>[^\]]*)\] as const;", re.S
)
QUOTED = re.compile(r"'([^']*)'")
# Any import at all, including a bare side-effect one.
IMPORT = re.compile(r"^\s*import\b", re.M)
# A message name as the contract writes it: a backticked cell in a table row.
CONTRACT_MESSAGE = re.compile(r"^\| `([a-z-]+)` \|", re.M)


def _const_lists(source: str) -> dict[str, list[str]]:
    found = {}
    for match in CONST_LIST.finditer(source):
        found[match.group("name")] = QUOTED.findall(match.group("body"))
    return found


def _section(text: str, heading: str) -> str:
    """One `## ` section of a Markdown document, heading excluded."""

    start = text.index(heading) + len(heading)
    following = text.find("\n## ", start)
    return text[start:] if following == -1 else text[start:following]


def check(root: Path = ROOT) -> list[str]:
    failures: list[str] = []
    files = verify_patch_references.stack_files(root)

    for path in (PORT, MOUNT, APP):
        if path not in files:
            failures.append(f"{path}: the patch stack does not create it")
    if failures:
        return failures

    port = "\n".join(files[PORT])
    mount = "\n".join(files[MOUNT])
    app = "\n".join(files[APP])
    contract = (root / CONTRACT).read_text(encoding="utf-8")

    # -- MM-3: the port reaches for nothing ----------------------------------
    #
    # The whole value of a port is that a second host can implement it by
    # copying one file. An import -- of geometry, of Chromium, of anything --
    # makes that copy drag something with it, and the copy is the thing
    # docs/decisions/0013-module-data-portability.md is for.
    if IMPORT.search(port):
        failures.append(f"{PORT}: imports something; MM-3 requires it to import nothing")

    lists = _const_lists(port)
    for name in ("HOST_MESSAGES", "MODULE_MESSAGES", "REGIONS", "ICONS"):
        if name not in lists:
            failures.append(f"{PORT}: {name} is missing or is not a closed `as const` list")
    if failures:
        return failures

    # -- MM-4: the contract and the port name the same messages --------------
    for name, heading in (
        ("HOST_MESSAGES", "## 3. What crosses, shell to module"),
        ("MODULE_MESSAGES", "## 4. What crosses, module to shell"),
    ):
        declared = set(lists[name])
        documented = set(CONTRACT_MESSAGE.findall(_section(contract, heading)))
        if declared != documented:
            failures.append(
                f"{CONTRACT} {heading.strip('# ')}: documents {sorted(documented)}, "
                f"{PORT} declares {sorted(declared)}"
            )

    # -- MM-5: nothing on the port can hold a location -----------------------
    #
    # Checked as an absence rather than as a filter. A field that could carry a
    # URL would have to be typed as one somewhere, and the port declares its
    # fields in one place, so a name that reads like a location is the signal.
    #
    # `contentUrl` is exempt and is the reason the rule needs stating: it is
    # not a field of any message, it is the check applied to the registry's own
    # URL before the shell navigates to it.
    for match in re.finditer(r"^\s{2}(?P<field>[a-z][A-Za-z]*)[?]?:", port, re.M):
        field = match.group("field")
        if re.search(r"url|uri|path|href|src|handle|callback|port", field, re.I):
            if field != "path":
                failures.append(f"{PORT}: field {field!r} names a location; MM-5")
    # `path` is a field, and it is display text: the header shows it and
    # nothing resolves it. That it is validated by `label()` rather than by
    # anything URL-shaped is what makes it text, so check exactly that.
    if not re.search(r"const path = label\(fields\['path'\]\);", port):
        failures.append(f"{PORT}: `path` must be validated as a label, not as a location; MM-5")
    if "transfer" in port or "MessagePort" in port or "MessagePort" in mount:
        failures.append("mount port: a transferable would be a capability; MM-5")

    # -- MM-6: three independent checks on an inbound message ----------------
    for fragment, why in (
        ("event.source !== this.frame.contentWindow", "source"),
        ("event.origin !== this.origin", "origin"),
        ("port.moduleMessage(event.data)", "payload"),
    ):
        if fragment not in mount:
            failures.append(f"{MOUNT}: the receiver does not check the {why}; MM-6")
    # postMessage with an explicit target origin, never '*'.
    if "postMessage(message, this.origin)" not in mount:
        failures.append(f"{MOUNT}: outbound messages must name a target origin; MM-6")
    if re.search(r"postMessage\([^)]*'\*'", mount):
        failures.append(f"{MOUNT}: postMessage to '*'; MM-6")

    # -- MM-7: what the shell draws, it draws as text ------------------------
    #
    # `verify_web_asset_security.py` already refuses innerHTML anywhere. What
    # is specific here is the positive form: every module-supplied string
    # reaches the document through textContent or an attribute that cannot
    # navigate.
    for banned in ("insertAdjacentHTML", "createContextualFragment", "srcdoc"):
        if banned in app or banned in mount:
            failures.append(f"shell: {banned} puts module content in the document; MM-7")
    if re.search(r"\.href\s*=|\.action\s*=\s*[^=]", app):
        failures.append(f"{APP}: assigns a navigable attribute; MM-7")

    # -- MM-8: the panel describes nothing -----------------------------------
    if "describe: () => {}," not in app:
        failures.append(f"{APP}: E's mount must discard `describe`; MM-8")

    # -- MM-1 and MM-2: the manifest side ------------------------------------
    import validate_first_party_modules as validator

    registry = json.loads((root / "first_party/registry.json").read_text(encoding="utf-8"))
    declared = 0
    for relative in registry["modules"]:
        manifest = json.loads((root / relative).read_text(encoding="utf-8"))
        if "mount" not in manifest:
            continue
        declared += 1
        url = manifest["mount"]["content_url"]
        if not validator.CONTENT_URL.fullmatch(url):
            failures.append(f"{relative}: mount content_url is not the contract's shape; MM-1")
        if manifest["kind"] != "surface":
            failures.append(f"{relative}: only a surface module may declare a mount; MM-2")

    # The two shapes have to accept the same set, so a manifest the validator
    # admits is never one the shell then refuses to navigate to -- which would
    # be a module that passes CI and shows an empty region.
    for probe, admissible in (
        ("chrome-untrusted://sunshine-a/", True),
        ("chrome-untrusted://sunshine-a", False),
        ("chrome-untrusted://sunshine-a/x", False),
        ("chrome-untrusted://sunshine-a/?q=1", False),
        ("chrome://sunshine-a/", False),
        ("chrome-untrusted://-a/", False),
        ("chrome-untrusted://A/", False),
    ):
        if bool(validator.CONTENT_URL.fullmatch(probe)) != admissible:
            failures.append(
                f"validate_first_party_modules.CONTENT_URL disagrees with MM-1 on {probe!r}"
            )

    print(f"module mount: {declared} module(s) declare a mount.")
    return failures


def main() -> int:
    failures = check()
    for failure in failures:
        print(failure)
    if failures:
        print(f"{len(failures)} module mount failure(s).")
        return 1
    print("Module mount port passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
