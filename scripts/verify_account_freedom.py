#!/usr/bin/env python3
"""Enforce that a Sunshine build cannot quietly acquire an account identity.

`docs/PROFILE_ONBOARDING_CONTRACT.md` establishes that local-only operation is
not a mode Sunshine builds -- it is what an honest build produces. The chain is
upstream and was read at the pinned revision:

    no OAuth client configured
      -> CanEnableDiceForBuild() is false        (account_consistency_mode_manager.cc)
      -> prefs::kSigninAllowed is written false
      -> GetPolicyEffect() returns kDisabled     (first_run_service.cc)
      -> the first-run experience is skipped entirely

Every link holds only while this repository ships no OAuth client id, secret, or
API key, and patches none of the identity machinery. Both are checkable here,
today, without a build -- which is what makes these the first acceptance criteria
in the contract set that a check can actually decide.

Enforces: PO-A1, PO-A2, PO-A3.
"""

from __future__ import annotations

import base64
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]

SEARCHED = ("first_party", "downstream", "scripts", "config")

# Google OAuth client ids end in this host; secrets and API keys have stable
# shapes. Matched case-insensitively against text and against anything that
# decodes as base64, since "in any encoding" is the criterion.
SECRET_PATTERNS = (
    ("OAuth client id", re.compile(r"\d{10,}-[a-z0-9]{20,}\.apps\.googleusercontent\.com", re.I)),
    ("OAuth client secret", re.compile(r"GOCSPX-[A-Za-z0-9_\-]{20,}")),
    ("Google API key", re.compile(r"AIza[A-Za-z0-9_\-]{35}")),
    ("legacy OAuth secret", re.compile(r"\bclient_secret\s*[:=]\s*['\"][^'\"]{8,}")),
)

# GN arguments that would configure a key at build time.
KEY_ARGUMENTS = ("google_api_key", "google_default_client_id", "google_default_client_secret")

# Upstream areas the patch stack must not touch. Patching any of them could
# restore sign-in without the key, which is exactly what the contract forbids;
# `g_ignore_missing_oauth_client_for_testing` exists upstream for tests and must
# not be reached from a shipped build.
PROTECTED_AREAS = (
    "chrome/browser/signin/",
    "components/signin/",
    "chrome/browser/ui/startup/first_run",
    "chrome/browser/sync/",
    "components/sync/",
    "google_apis/",
)

# Command surfaces that would put an account action behind a Sunshine command.
ACCOUNT_COMMAND_WORDS = ("signin", "sign_in", "sync", "account", "profile.create", "profile.delete")


def _candidates(text: str) -> list[str]:
    """The text, plus anything embedded in it that decodes as base64."""

    found = [text]
    for blob in re.findall(r"[A-Za-z0-9+/]{24,}={0,2}", text):
        try:
            decoded = base64.b64decode(blob, validate=True).decode("utf-8", errors="ignore")
        except (ValueError, UnicodeDecodeError):
            continue
        if decoded.isprintable():
            found.append(decoded)
    return found


def check_no_credentials(root: Path, failures: list[str]) -> None:
    """PO-A1: no OAuth client id, secret, or API key, in any encoding."""

    for directory in SEARCHED:
        for path in sorted((root / directory).rglob("*")):
            if not path.is_file() or "__pycache__" in path.parts:
                continue
            if path.resolve() == Path(__file__).resolve():
                continue
            try:
                text = path.read_text(encoding="utf-8")
            except (UnicodeDecodeError, OSError):
                continue
            relative = path.relative_to(root).as_posix()
            for candidate in _candidates(text):
                for label, pattern in SECRET_PATTERNS:
                    if pattern.search(candidate):
                        failures.append(f"{relative}: contains a {label}")
            for argument in KEY_ARGUMENTS:
                if re.search(rf"\b{argument}\s*=", text):
                    failures.append(f"{relative}: sets the build argument {argument}")


def check_patch_stack_avoids_identity(root: Path, failures: list[str]) -> None:
    """PO-A2: the patch stack touches no identity, sync, or first-run source."""

    target = re.compile(r"^\+\+\+ b/(.+)$", re.MULTILINE)
    for patch in sorted((root / "downstream/patches").glob("*.patch")):
        for path in target.findall(patch.read_text(encoding="utf-8")):
            for area in PROTECTED_AREAS:
                if path.startswith(area):
                    failures.append(f"{patch.name}: patches {path}, inside protected area {area}")


def check_no_account_commands(root: Path, failures: list[str]) -> None:
    """PO-A3: no registered command creates a profile, signs in, or syncs."""

    registry = json.loads((root / "first_party/commands.json").read_text(encoding="utf-8"))
    for command in registry["commands"]:
        identifier = command["id"]
        for word in ACCOUNT_COMMAND_WORDS:
            if word in identifier:
                failures.append(f"{identifier}: registers an account or profile-lifecycle action")


def validate(root: Path = ROOT) -> list[str]:
    failures: list[str] = []
    check_no_credentials(root, failures)
    check_patch_stack_avoids_identity(root, failures)
    check_no_account_commands(root, failures)
    return failures


def main() -> int:
    failures = validate()
    if failures:
        print("\n".join(failures), file=sys.stderr)
        return 1
    print("Account-freedom check passed: no credentials, no identity patches, no account commands.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
