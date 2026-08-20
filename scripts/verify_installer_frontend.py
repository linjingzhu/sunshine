#!/usr/bin/env python3
"""Hold the installer front-end to `docs/INSTALLER_UI_CONTRACT.md`.

The front-end cannot be compiled or run anywhere in this project's CI: it needs
MSVC and Windows, and the one machine that has both is also the only machine
that builds Chromium. So everything about it that can be decided from source is
decided here, and the rules chosen are the ones whose failure would be silent.

What is checked, and which invariant each claims:

  * the manifest requests `asInvoker`, and requests nothing else (IU-7);
  * every preferences key the program writes is one the contract names, so a
    control cannot quietly acquire an effect upstream did not agree to (IU-3);
  * no text box exists anywhere in the dialog -- which is how both "the path is
    shown, never typed" and "the name has no control" are enforced, because
    each would need one (IU-4, IU-5);
  * nothing installs: no registry write, no shortcut, no copy into a program
    directory (IU-2);
  * no image is opened at run time (IU-6);
  * the choices cross the elevation boundary as switches from a closed table,
    and the elevated continuation reads no file to learn them (IU-8);
  * the engine is hashed against a generated constant before it is run, and the
    constant is generated rather than committed (IU-10);
  * there is no switch that skips the dialog (IU-15);
  * exactly two registry paths are read, and they are the two IU-16 names.

**IU-16 is the reason this file exists in this shape.** Its first draft said the
front-end reads one key and "no other". Drawing in the user's light or dark
theme needs a second, so the rule as written could only have been kept by
dropping the theme or by breaking it quietly. Naming both keys and asserting the
source reads *exactly* those is a stronger check than "as few as possible" ever
was, and it is the shape a rule takes once someone has tried to obey it.

Enforces: IU-1
"""

from __future__ import annotations

from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]

SOURCE = "installer/sunshine_setup.cpp"
RESOURCE = "installer/sunshine_setup.rc"
MANIFEST = "installer/sunshine_setup.manifest"
BUILD = "scripts/build_installer_frontend.ps1"
CONTRACT = "docs/INSTALLER_UI_CONTRACT.md"

# The two registry paths IU-16 permits, matched by the fragment that identifies
# each. The uninstall registration says whether Sunshine is installed; the
# Personalize key says whether to draw light or dark.
PERMITTED_KEYS = (
    "CurrentVersion\\\\Uninstall\\\\Sunshine",
    "Themes\\\\\"\n                      L\"Personalize",
)

# A registry open, however it is spelled.
REGISTRY_OPEN = re.compile(r"Reg(?:Open|Create)KeyEx[WA]?\s*\(")
REGISTRY_WRITE = re.compile(r"Reg(?:SetValue|DeleteValue|CreateKey)")

# Things that would mean this program installs something itself (IU-2).
INSTALLING = (
    "IShellLink",
    "CopyFileW",
    "MoveFileW",
    "SHFileOperation",
    "CreateSymbolicLink",
)

# Reading an image at run time (IU-6).
IMAGE_AT_RUNTIME = (
    "LoadImageW",
    "GdipLoadImageFromFile",
    "SHCreateStreamOnFile",
    "CreateDecoderFromFilename",
)


# Line comments, in both the C++ and the resource script.
COMMENT = re.compile(r"^\s*//.*$", re.M)


def code_only(text: str) -> str:
    """The file with its line comments removed.

    Three of this guard's rules fired on their own explanations the first time
    it ran: a comment saying "there is no silent mode" was read as a silent
    mode, and one saying "deliberately no EDITTEXT" was read as an EDITTEXT.
    A guard that reads prose is a guard that makes people write worse prose to
    get past it, so it reads code.
    """

    return COMMENT.sub("", text)


def _read(root: Path, relative: str, failures: list[str]) -> str:
    path = root / relative
    if not path.is_file():
        failures.append(f"{relative}: missing")
        return ""
    return path.read_text(encoding="utf-8")


def check(root: Path = ROOT) -> list[str]:
    failures: list[str] = []
    source = _read(root, SOURCE, failures)
    resource = _read(root, RESOURCE, failures)
    manifest = _read(root, MANIFEST, failures)
    build = _read(root, BUILD, failures)
    contract = _read(root, CONTRACT, failures)
    if failures:
        return failures

    # -- IU-7: asInvoker, and only that ---------------------------------------
    levels = re.findall(r'requestedExecutionLevel\s+level="([^"]+)"', manifest)
    if levels != ["asInvoker"]:
        failures.append(
            f"{MANIFEST}: requests {levels or 'no execution level'}; IU-7 requires "
            "exactly one, asInvoker"
        )

    source_code = code_only(source)
    resource_code = code_only(resource)

    # -- IU-3: only preferences keys the contract names -----------------------
    #
    # The keys are written into a JSON literal, so in the C++ they appear with
    # their quotes escaped.
    named = set(re.findall(r"`(do_not_[a-z_]+|make_chrome_default_for_user|system_level)`", contract))
    written = set(
        re.findall(r'\\"(do_not_[a-z_]+|make_chrome_default_for_user|system_level)\\"', source_code)
    )
    if not written:
        failures.append(f"{SOURCE}: writes no preferences key, so nothing is requested")
    for key in sorted(written - named):
        failures.append(
            f"{SOURCE}: writes preferences key {key!r}, which {CONTRACT} does not "
            "name; IU-3"
        )

    # -- IU-4 and IU-5: no text box, anywhere ---------------------------------
    #
    # Checked as an absence in the dialog template rather than as a rule about
    # two particular fields. A typed install path and a typed product name both
    # need an edit control, and neither can appear without one.
    if re.search(r"\bEDITTEXT\b|\bES_AUTOHSCROLL\b|\"Edit\"", resource_code):
        failures.append(
            f"{RESOURCE}: contains a text box. The install location is shown and "
            "never typed (IU-4) and the product name has no control at all (IU-5)"
        )

    # -- IU-2: it installs nothing -------------------------------------------
    for symbol in INSTALLING:
        if symbol in source_code:
            failures.append(
                f"{SOURCE}: uses {symbol}, which is installing rather than asking; IU-2"
            )
    if REGISTRY_WRITE.search(source_code):
        failures.append(f"{SOURCE}: writes to the registry; IU-2 and IU-16")

    # -- IU-6: no image opened at run time ------------------------------------
    for symbol in IMAGE_AT_RUNTIME:
        if symbol in source_code:
            failures.append(
                f"{SOURCE}: uses {symbol}, so an image could come from disk; IU-6"
            )

    # -- IU-6 and IU-14: what is owner-drawn is actually drawn ----------------
    #
    # This rule exists because the first version of this program declared
    # BS_OWNERDRAW buttons and an SS_OWNERDRAW banner and handled no
    # WM_DRAWITEM, which renders them as blank rectangles. Nothing else would
    # have caught it: it compiles, every other rule passes, and the failure is
    # visible only to someone running a build nobody in this project can make.
    owner_drawn = re.findall(r"\b(?:BS_OWNERDRAW|SS_OWNERDRAW)\b", resource_code)
    if owner_drawn and "WM_DRAWITEM" not in source_code:
        failures.append(
            f"{RESOURCE}: declares {len(owner_drawn)} owner-drawn control(s) and "
            f"{SOURCE} handles no WM_DRAWITEM, so they draw nothing"
        )
    if "InitializeFromMemory" not in source_code:
        failures.append(
            f"{SOURCE}: the banner is not decoded from memory, so it may be "
            "arriving from a file; IU-6"
        )
    if "DrawFocusRect" not in source_code:
        failures.append(
            f"{SOURCE}: an owner-drawn control must draw its own focus, and "
            "nothing here does; IU-14"
        )

    # -- IU-8: the switch table is closed, and elevation carries no file ------
    if "kSwitches[]" not in source_code:
        failures.append(f"{SOURCE}: has no closed switch table; IU-8")
    if "BuildElevatedCommandLine" not in source_code:
        failures.append(f"{SOURCE}: does not build the elevated command line; IU-8")
    # This rule used to slice the source text from `if (elevated_continuation)`
    # to the end of the file and grep the tail for file reads. It found nothing,
    # and could not: `RunEngine` and `WriteFileBytes` are *defined above* that
    # point, so the elevated path's entire file I/O sat outside the slice. A
    # check that reads text position instead of reachability is a check that
    # passes for a reason unrelated to the property.
    #
    # What IU-8 and IU-9 actually need is that nothing the elevated instance
    # touches is in a place an unprivileged user can write. That is decidable,
    # and it is where the staging directory comes from.
    if "GetSystemWindowsDirectoryW" not in source_code:
        failures.append(
            f"{SOURCE}: the elevated staging root must come from "
            "GetSystemWindowsDirectoryW. UAC gives the elevated process the "
            "same profile, so %TEMP%'s parent grants the unelevated user "
            "FILE_DELETE_CHILD -- they cannot write into a protected child, "
            "but they can delete it and put their own there; IU-9"
        )
    if not re.search(r"if \(elevated\)\s*\{[^}]*GetSystemWindowsDirectoryW", source_code, re.S):
        failures.append(
            f"{SOURCE}: GetSystemWindowsDirectoryW is present but is not what "
            "the elevated branch uses; IU-9"
        )
    if not re.search(r"if \(!RunningElevated\(\)", source_code):
        failures.append(
            f"{SOURCE}: the elevated continuation does not verify that it is "
            "elevated. Taking that from the command line makes the switch a "
            "complete unattended install path; IU-15"
        )

    # -- IU-10: the hash is over the file that runs, not over the resource ----
    #
    # The first version of this hashed the in-memory resource, which came out of
    # this binary's own image and could not have been tampered with by an
    # unprivileged user in the first place. It proved the build carried what the
    # build intended and said nothing about the bytes on disk at the moment of
    # execution -- which is the whole window IU-9 and IU-10 exist to close.
    if "kEngineSha256" not in source_code or "BCryptHashData" not in source_code:
        failures.append(f"{SOURCE}: does not hash the engine before running it; IU-10")
    if "OpenVerifiedEngine" not in source_code:
        failures.append(
            f"{SOURCE}: nothing hashes the extracted engine through a handle it "
            "holds; hashing the resource proves nothing about what runs; IU-10"
        )
    else:
        verify = source_code.find("HANDLE verified = OpenVerifiedEngine")
        launch = source_code.find("::CreateProcessW")
        close = source_code.find("::CloseHandle(verified)")
        if not (0 < verify < launch < close):
            failures.append(
                f"{SOURCE}: the engine must be verified before CreateProcessW "
                "and its handle held until after, so nothing can replace the "
                "file in between; IU-10"
            )
    if (root / "installer/engine_hash.h").exists():
        failures.append(
            "installer/engine_hash.h is committed. It belongs to one build's "
            "engine and to no other; the build script writes it; IU-10"
        )
    if "engine_hash.h" not in build or "Get-FileHash" not in build:
        failures.append(f"{BUILD}: does not generate the engine hash; IU-10")

    # -- IU-15: every install was preceded by the dialog ----------------------
    #
    # This rule used to grep for a vocabulary -- "silent", "quiet", "passive",
    # "unattend". It was wrong twice over. It fired on the *comment* explaining
    # that there is no silent mode, which is a check that makes people write
    # worse prose; and it never fired on the actual violation, because the
    # switch that performed a complete unattended install was spelled
    # `--sunshine-elevated` and no vocabulary list was ever going to contain it.
    #
    # The property is not a spelling. It is that every path reaching the engine
    # goes through the dialog, or through an elevation the dialog started. That
    # is countable: two call sites, one window.
    engine_calls = len(re.findall(r"RunEngine\(", source_code)) - 1  # minus the definition
    if engine_calls != 2:
        failures.append(
            f"{SOURCE}: RunEngine is called from {engine_calls} place(s). IU-15 "
            "allows exactly two -- the elevated continuation, and the path after "
            "the dialog returned IDOK. A third is an install nobody watched"
        )
    if len(re.findall(r"::DialogBoxParamW\(", source_code)) != 1:
        failures.append(
            f"{SOURCE}: the dialog must be shown from exactly one place, so that "
            "'was the dialog shown' has one answer; IU-15"
        )

    # -- IU-16: exactly two reads, and they are the two named -----------------
    opens = len(REGISTRY_OPEN.findall(source_code))
    if opens != 2:
        failures.append(
            f"{SOURCE}: opens {opens} registry key(s); IU-16 permits exactly two "
            "-- the uninstall registration and the light/dark preference"
        )
    if "CurrentVersion\\\\Uninstall\\\\Sunshine" not in source_code:
        failures.append(f"{SOURCE}: does not read the uninstall registration; IU-16")
    if "AppsUseLightTheme" not in source_code:
        failures.append(
            f"{SOURCE}: does not read the light/dark preference, which is the "
            "second read IU-16 permits and the reason it permits one; IU-16"
        )

    # -- IU-1: zero upstream Chromium files ----------------------------------
    for patch in sorted((root / "downstream/patches").glob("*.patch")):
        if "installer/sunshine_setup" in patch.read_text(encoding="utf-8"):
            failures.append(
                f"{patch.name}: the front-end is in the patch stack. It owns no "
                "upstream file and is not part of Chromium's build; IU-1"
            )

    print(f"installer front-end: {len(written)} preferences key(s), {opens} registry read(s).")
    return failures


def main() -> int:
    failures = check()
    for failure in failures:
        print(failure)
    if failures:
        print(f"{len(failures)} installer front-end failure(s).")
        return 1
    print("Installer front-end passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
