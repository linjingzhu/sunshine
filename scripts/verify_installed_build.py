#!/usr/bin/env python3
"""Check the built browser against what the contracts claim was built.

Every other guard in `scripts/` reads the repository. This one reads the
*output*: the artifacts, the configuration they were actually generated from,
and the state the operating system holds about them. It is the first check in
this project that can fail because of what was produced rather than what was
written.

It exists because the contract set had reached 418 declared invariants with 33
enforced, and most of the remainder are class B -- decidable only with a built
browser. The browser now exists. Nothing was reading it.

**Platform honesty.** The registry check is meaningful only on Windows. On any
other platform it reports NOT AVAILABLE and the script exits 2, which is neither
success nor failure: a check that silently passes where it cannot run is worse
than one that is absent, because it produces a green result nobody earned.

Enforces: SEC-1, SEC-2, SEC-13, SECA-11.
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from verify_chromium_security_invariants import (  # noqa: E402
    ISOLATION_SWITCHES,
    SANDBOX_SWITCHES,
    switch_pattern,
)

PASSED, FAILED, UNAVAILABLE = "PASS", "FAIL", "NOT AVAILABLE"

ARTIFACTS = ("chrome.exe", "mini_installer.exe")

# What ADR 0004 decided, stated as the two arguments that carry it. Read back
# from the generated configuration rather than from the script that writes it:
# the question is what the build used, not what the source intended.
REQUIRED_ARGS = (
    "is_official_build=true",
    "is_debug=false",
    "proprietary_codecs=true",
    'ffmpeg_branding="Chrome"',
)

# Scheme names Sunshine must not have registered with Windows. ADR 0003 settled
# that it registers none; SEC-13 checks the source, and this checks the machine,
# which is where a registration would actually matter.
FORBIDDEN_SCHEMES = ("sunshine", "sunshine-module", "sunshineos")


class Result:
    def __init__(self) -> None:
        self.rows: list[tuple[str, str, str]] = []

    def record(self, status: str, name: str, detail: str = "") -> None:
        self.rows.append((status, name, detail))

    @property
    def failed(self) -> bool:
        return any(status == FAILED for status, _, _ in self.rows)

    @property
    def unavailable(self) -> bool:
        return any(status == UNAVAILABLE for status, _, _ in self.rows)

    def report(self) -> str:
        width = max((len(status) for status, _, _ in self.rows), default=0)
        lines = [
            f"  {status:<{width}}  {name}" + (f" -- {detail}" if detail else "")
            for status, name, detail in self.rows
        ]
        return "\n".join(lines)


def check_artifacts(out: Path, result: Result) -> None:
    for name in ARTIFACTS:
        path = out / name
        if path.is_file():
            megabytes = round(path.stat().st_size / (1024 * 1024), 1)
            result.record(PASSED, f"artifact {name}", f"{megabytes} MB")
        else:
            result.record(FAILED, f"artifact {name}", f"missing at {path}")


def check_build_arguments(out: Path, result: Result) -> None:
    """SEC-1, SEC-2 and ADR 0004, read from the configuration the build used."""

    args_gn = out / "args.gn"
    if not args_gn.is_file():
        result.record(FAILED, "args.gn", f"missing at {args_gn}")
        return
    text = args_gn.read_text(encoding="utf-8")

    for required in REQUIRED_ARGS:
        if required in text:
            result.record(PASSED, f"build argument {required}")
        else:
            result.record(FAILED, f"build argument {required}", "not in args.gn")

    weakening = [
        switch for switch in SANDBOX_SWITCHES + ISOLATION_SWITCHES
        if switch_pattern(switch).search(text)
    ]
    if weakening:
        result.record(FAILED, "no security boundary is disabled", ", ".join(weakening))
    else:
        result.record(PASSED, "no security boundary is disabled", "SEC-1, SEC-2")


def check_no_registered_scheme(result: Result) -> None:
    """SEC-13 at the layer that matters: what the operating system believes."""

    if sys.platform != "win32":
        result.record(
            UNAVAILABLE,
            "no URL scheme registered with the OS",
            f"needs Windows; this is {sys.platform}",
        )
        return

    import winreg  # noqa: PLC0415 -- Windows-only, and importing it elsewhere fails

    for scheme in FORBIDDEN_SCHEMES:
        try:
            with winreg.OpenKey(winreg.HKEY_CLASSES_ROOT, scheme) as key:
                try:
                    winreg.QueryValueEx(key, "URL Protocol")
                except FileNotFoundError:
                    result.record(PASSED, f"{scheme} is not a URL protocol", "key exists, no protocol value")
                    continue
                result.record(
                    FAILED,
                    "no URL scheme registered with the OS",
                    f"HKCR\\{scheme} declares URL Protocol, which ADR 0003 forbids",
                )
        except FileNotFoundError:
            result.record(PASSED, f"{scheme}:// is not registered", "SEC-13")


def check_chrome_launches(out: Path, result: Result) -> None:
    """The one check that answers "does this actually run," not just "does the
    configuration that produced it look right."

    Every other check in this file reads a file or a registry key -- evidence
    that is consistent with a browser that works, but also consistent with one
    that is missing a resource, links against a DLL that is not beside it, or
    is silently killed the instant it starts. `chrome.exe --version` is the
    cheapest code path that exercises real process startup: it initializes
    enough of the binary to print its own version string, then exits, without
    opening a window, touching a profile directory, or needing the sandbox this
    project will not weaken to get a faster smoke test.

    This is also the only check positioned to catch what a build machine's own
    antivirus or SmartScreen might do to an unsigned, freshly compiled binary --
    a class of failure that leaves every artifact on disk, at a plausible size,
    built with the right arguments, and still unable to run. A person watching
    a blank screen after double-clicking the installer cannot tell that story
    apart from a genuinely broken build; this check can, because it captures
    the real exit code and output instead of a closed window.
    """

    if sys.platform != "win32":
        result.record(
            UNAVAILABLE,
            "chrome.exe launches and reports its version",
            f"needs Windows; this is {sys.platform}",
        )
        return

    chrome = out / "chrome.exe"
    if not chrome.is_file():
        # check_artifacts already recorded this as FAILED; recorded again here
        # would just restate it, and there is nothing to launch.
        return

    try:
        completed = subprocess.run(
            [str(chrome), "--version"],
            capture_output=True,
            text=True,
            timeout=30,
        )
    except subprocess.TimeoutExpired:
        result.record(
            FAILED,
            "chrome.exe launches and reports its version",
            "did not exit within 30s -- hung, or waiting on something interactive",
        )
        return
    except OSError as error:
        # The shape a real-time antivirus quarantine or a SmartScreen block
        # takes: the file is on disk (check_artifacts passed) but the OS
        # refuses to start it. WinError 5 is access denied; WinError 1260 is
        # "blocked by your organization's policy."
        result.record(
            FAILED,
            "chrome.exe launches and reports its version",
            f"process could not start: {error}",
        )
        return

    output = (completed.stdout + completed.stderr).strip()
    if completed.returncode != 0:
        result.record(
            FAILED,
            "chrome.exe launches and reports its version",
            f"exit code {completed.returncode}: {output or '(no output)'}",
        )
        return
    if not output:
        result.record(
            FAILED,
            "chrome.exe launches and reports its version",
            "exited 0 but printed nothing -- not the version-print code path",
        )
        return
    result.record(PASSED, "chrome.exe launches and reports its version", output)


def resolve_out(explicit: str | None) -> Path | None:
    if explicit:
        return Path(explicit)
    workspace = os.environ.get("SUNSHINE_CHROMIUM_WORKSPACE")
    if workspace:
        return Path(workspace) / "src" / "out" / "Sunshine"
    return None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--out",
        help="the build output directory; defaults to $SUNSHINE_CHROMIUM_WORKSPACE/src/out/Sunshine",
    )
    arguments = parser.parse_args()

    out = resolve_out(arguments.out)
    result = Result()
    if out is None:
        print(
            "SUNSHINE_CHROMIUM_WORKSPACE is not set and --out was not given, so there "
            "is no build to read.",
            file=sys.stderr,
        )
        return 2

    check_artifacts(out, result)
    check_build_arguments(out, result)
    check_no_registered_scheme(result)
    check_chrome_launches(out, result)

    print(f"Built browser at {out}")
    print(result.report())
    if result.failed:
        print("Built browser does not match what the contracts claim.", file=sys.stderr)
        return 1
    if result.unavailable:
        print("Some checks could not run on this platform; the result is not a pass.")
        return 2
    print("Built browser matches the contracts.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
