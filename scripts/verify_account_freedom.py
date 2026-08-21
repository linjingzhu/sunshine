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

Enforces: PO-A1, PO-A2, PO-A3, PO-A16, PO-A17.
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

# PO-A16. Sunshine's own credential name carries no value in this tree.
#
# PO-A1 above refuses Chrome's three build arguments and anything shaped like a
# real Google credential. Neither rule sees the failure this one is about: a
# *placeholder*. `#define SUNSHINE_ACCOUNT_CLIENT_ID "test-1234"` is not shaped
# like a Google client id, sets none of Chrome's arguments, and still makes
# `LinkAvailable()` return true in every build made from this tree -- which is
# exactly the state section 5 of the plan promises cannot exist.
#
# The value has to arrive from the release pipeline or not at all, so the rule
# is that the name may appear here but a literal value may not.
# The value must be a quoted run with **no whitespace in it**, and the quotes
# must match. Both halves of that were learned by getting it wrong: an earlier
# version accepted any `"..."` after the name, and the first thing it rejected
# was `scripts/build_chromium_windows.ps1` assembling the argument from a
# variable --
#
#     $gnArgs += ("sunshine_account_client_id=" + [char]34 + $Id + [char]34)
#
# where the quote it read as opening a value is the one closing the argument
# *name*. Requiring no whitespace is not a patch over that one line; it is the
# property that separates a credential from code, because no client id, secret
# or API key contains a space.
# The escaped form counts too. `chrome/browser/ui/sunshine/BUILD.gn` spells the
# define as `"SUNSHINE_ACCOUNT_CLIENT_ID=\\"$sunshine_account_client_id\\""`, so a
# rule that only understood a bare quote would read the one shape the feature
# actually uses as no value at all -- and would have accepted a real id written
# the same way.
#
# What separates the two is not the quoting: it is that a GN or shell
# **reference** begins with `$` and a literal does not. That is the check.
SUNSHINE_CREDENTIAL_VALUE = re.compile(
    r"\bSUNSHINE_[A-Z0-9_]*(?:CLIENT_ID|CLIENT_SECRET|API_KEY)\b\s*=?\s*"
    r"\\?(?P<quote>[\"'])(?!\$)(?P<value>[^\"'\s\\]+)\\?(?P=quote)",
    re.I,
)

# PO-A17. Sunshine's own code reaches none of Chromium's identity surface.
#
# PO-A2 above forbids *patching* the identity, sync and first-run areas. That is
# not the same rule as this one, and the difference is the whole reason this
# exists: a file can leave every upstream source untouched and still call into
# it. `docs/ACCOUNT_LINK_PLAN.md` section 1 calls the account link **L4** -- an
# ordinary OAuth client held by an application -- and L4 is only true for as
# long as the code stays outside the machinery that makes L2 and L3 true. The
# moment a Sunshine file holds an `IdentityManager`, the profile has a browser
# identity no matter what the plan says it is.
#
# Scope is **every Sunshine source**, not the account files. Scoping it by path
# would mean naming the files the rule is about, and a rule that must be told
# where to look stops applying the moment someone adds a file it was not told
# about. `docs/memory/PROJECT_LESSONS.md`'s IU-15 is this exact mistake made
# once already. Nothing in the tree reaches any of these today, so the broad
# form costs nothing and cannot be quietly outgrown.
#
# Written before the code it constrains rather than alongside it: section 8 of
# the plan asks for the guard to land with the authorization, and landing it
# first means the authorization is written under the rule instead of audited
# against it afterwards.
IDENTITY_SYMBOLS = (
    ("IdentityManager", "Chromium's identity manager"),
    ("PrimaryAccount", "the profile's primary account"),
    ("ProfileOAuth2TokenService", "the profile's OAuth token service"),
    ("OAuth2AccessTokenManager", "the profile's access token manager"),
    ("signin::", "the signin component"),
    ("SigninManager", "the signin manager"),
    ("AccountTrackerService", "the account tracker"),
    ("AccountInfo", "Chromium's account record"),
    ("GaiaAuthFetcher", "Gaia's authentication fetcher"),
    ("GaiaCookieManagerService", "Gaia's cookie manager"),
    ("GoogleServiceAuthError", "Chromium's Google-service error type"),
    ("kSigninAllowed", "the preference that gates browser sign-in"),
    ("CanEnableDiceForBuild", "the Dice build predicate"),
    ("SyncService", "the sync service"),
    ("syncer::", "the sync component"),
    ("sync_pb", "sync's wire types"),
    # The cookie jar. Step 4 of the plan's section 4 turns on the authorization
    # code arriving on a socket Sunshine opened rather than out of the jar, and
    # PO-R7's credential rule is true only while nothing is promoted out of it.
    ("CookieManager", "the profile's cookie jar"),
    ("GetCookieList", "a read of the profile's cookie jar"),
    ("CanonicalCookie", "the profile's cookie jar"),
)


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


def _is_guard(path: Path) -> bool:
    """A guard names what it prohibits, so it cannot be scanned for it.

    Same convention as `scripts/verify_no_interposition.py`: this repository's
    checks are `verify_*`/`validate_*`, and the symbol tables inside them are
    prohibitions rather than uses.
    """

    return path.name.startswith(("verify_", "validate_", "trace_"))


def sunshine_sources(root: Path) -> list[tuple[str, str]]:
    """(label, text) for every piece of Sunshine-authored text in scope.

    A patch contributes only its **added** lines. Its `+++ b/path` headers name
    upstream files and also begin with `+`, which is the likeliest false
    positive in the whole check, so they are dropped.
    """

    sources: list[tuple[str, str]] = []
    for directory in SEARCHED:
        base = root / directory
        if not base.is_dir():
            continue
        for path in sorted(base.rglob("*")):
            if not path.is_file() or "__pycache__" in path.parts:
                continue
            if _is_guard(path):
                continue
            try:
                text = path.read_text(encoding="utf-8")
            except (UnicodeDecodeError, OSError):
                continue
            relative = path.relative_to(root).as_posix()
            if path.suffix == ".patch":
                kept = [
                    line[1:]
                    for line in text.splitlines()
                    if line.startswith("+") and not line.startswith("+++ ")
                ]
                sources.append((f"{relative} (added lines)", "\n".join(kept)))
            else:
                sources.append((relative, text))
    return sources


def check_no_sunshine_credential_value(root: Path, failures: list[str]) -> None:
    """PO-A16: Sunshine's own credential name is declared, never given a value."""

    for label, text in sunshine_sources(root):
        for match in SUNSHINE_CREDENTIAL_VALUE.finditer(text):
            value = match.group("value")
            failures.append(
                f"{label}: gives a Sunshine credential the literal value {value!r} -- "
                "PO-A16, it must come from the release pipeline"
            )


def check_no_identity_surface(root: Path, failures: list[str]) -> None:
    """PO-A17: no Sunshine source reaches Chromium's identity surface."""

    for label, text in sunshine_sources(root):
        for symbol, description in IDENTITY_SYMBOLS:
            if symbol in text:
                failures.append(f"{label}: reaches {description} ({symbol!r}) -- PO-A17")


def validate(root: Path = ROOT) -> list[str]:
    failures: list[str] = []
    check_no_credentials(root, failures)
    check_patch_stack_avoids_identity(root, failures)
    check_no_account_commands(root, failures)
    check_no_sunshine_credential_value(root, failures)
    check_no_identity_surface(root, failures)
    return failures


def main() -> int:
    failures = validate()
    if failures:
        print("\n".join(failures), file=sys.stderr)
        return 1
    print("Account-freedom check passed: no credentials, no identity patches, no "
          "account commands, no Sunshine credential value, no reach into "
          "Chromium's identity surface.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
