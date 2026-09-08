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


def _function_body(code: str, name: str) -> str | None:
    """The braced body of the first definition of `name`, or None.

    Brace counting rather than a parser: this file has no string literal
    containing an unbalanced brace, and the check that uses it says what it
    assumes rather than pretending to understand C++.
    """

    start = re.search(rf"^\w[\w:<>*&\s]*\b{re.escape(name)}\s*\([^;]*?\)\s*\{{",
                      code, re.M)
    if not start:
        return None
    depth = 0
    for index in range(start.end() - 1, len(code)):
        if code[index] == "{":
            depth += 1
        elif code[index] == "}":
            depth -= 1
            if depth == 0:
                return code[start.end():index]
    return None


def check(root: Path = ROOT) -> list[str]:
    failures: list[str] = []
    source = _read(root, SOURCE, failures)
    resource = _read(root, RESOURCE, failures)
    manifest = _read(root, MANIFEST, failures)
    build = _read(root, BUILD, failures)
    contract = _read(root, CONTRACT, failures)
    if failures:
        return failures

    # -- IU-17: it runs on a machine that never had a compiler ----------------
    #
    # `cl.exe` defaults to /MD, the dynamic CRT, and a binary built that way
    # needs VCRUNTIME140.dll, VCRUNTIME140_1.dll and MSVCP140.dll wherever it
    # runs. The build machine has them because Visual Studio put them there, so
    # this is invisible in every place it is built and fatal in every place it
    # is used: the loader fails before wWinMain, so not one of the message
    # boxes below ever runs and the user sees nothing at all.
    #
    # Build #55's installer did exactly that. The flag is one token and the
    # failure it prevents is silent, which is the whole argument for checking
    # it here rather than trusting whoever next edits the command line.
    if not re.search(r"cl\.exe[^\n]*(`\n[^\n]*)*\s/MT\b", build):
        failures.append(
            f"{BUILD}: the front-end is not compiled with /MT, so it links the "
            "dynamic CRT and does nothing on a machine without the Visual C++ "
            "redistributable -- silently, because the loader fails before "
            "wWinMain (IU-17)")
    if re.search(r"cl\.exe[^\n]*(`\n[^\n]*)*\s/MD\b", build):
        failures.append(
            f"{BUILD}: the front-end is compiled with /MD, which is the dynamic "
            "CRT (IU-17)")

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
    # Both sides read the same shape -- a lower_snake_case identifier -- rather
    # than the three families this used to enumerate. A key outside that
    # enumeration was invisible to the check instead of refused by it, which is
    # the opposite of what IU-3 asks for, and `program_files_dir` is the key
    # that would have walked past it.
    named = set(re.findall(r"`([a-z][a-z0-9]*(?:_[a-z0-9]+)+)`", contract))
    written = set(re.findall(r'\\"([a-z][a-z0-9]*(?:_[a-z0-9]+)+)\\"', source_code))
    if not written:
        failures.append(f"{SOURCE}: writes no preferences key, so nothing is requested")
    for key in sorted(written - named):
        failures.append(
            f"{SOURCE}: writes preferences key {key!r}, which {CONTRACT} does not "
            "name; IU-3"
        )

    # -- IU-4 and IU-5: one text box, and it is the install root --------------
    #
    # This was an absence: no EDITTEXT anywhere. That was one check standing in
    # for two invariants -- a typed install path and a typed product name both
    # need an edit control, so forbidding the control forbade both. The owner
    # reversed IU-4, and the proxy stopped expressing the invariant that
    # survived.
    #
    # So it is now a count and an identity. IU-5 is still the rule; what
    # enforces it is that the only box on the dialog is the one IU-4 now
    # permits. A second box is a refusal without needing to guess what it is
    # for, and that is deliberate: the next field somebody adds should have to
    # come through this check rather than past it.
    boxes = re.findall(r"^\s*EDITTEXT\s+([A-Z0-9_]+)", resource_code, re.M)
    other = re.findall(r'\bCONTROL\b[^\n]*"Edit"', resource_code)
    if other:
        failures.append(
            f"{RESOURCE}: declares an edit control through CONTROL ... \"Edit\", "
            "which this check cannot name; declare it as EDITTEXT (IU-5)"
        )
    if boxes != ["IDC_LOCATION_EDIT"]:
        failures.append(
            f"{RESOURCE}: text boxes are {boxes or 'none'}; exactly one is "
            "permitted and it is IDC_LOCATION_EDIT, the install root (IU-4). "
            "The product name has no control at all (IU-5), and neither does "
            "the executable's name until docs/INSTALLER_CHOICE_PLAN.md section "
            "4 is paid for"
        )

    # -- The warning that replaces upstream's guarantee ------------------------
    #
    # `docs/INSTALLER_CHOICE_PLAN.md` section 7 decision 2 accepts a warning in
    # place of a refusal, and section 3 is exact about the one way to get it
    # wrong: "a writability test performed before elevating tests the wrong
    # token". So the check is not that a warning exists -- it is that the
    # writability test is reached only from the elevated continuation.
    # A call site, not a mention. The first version of this counted the name and
    # flagged the tree it was written for: the function's own definition sits
    # above `wWinMain`, so "appears before the elevated continuation" is true of
    # every correct arrangement. What it has to find is `UsersCanWrite(` used as
    # a call, which the definition is not.
    def calls(text: str) -> int:
        return len(re.findall(r"(?<!bool )\bUsersCanWrite\(", text))

    if "UsersCanWrite" not in source_code:
        failures.append(
            f"{SOURCE}: relaxing the install root without testing whether "
            "unprivileged users can write it drops upstream's guarantee and "
            "puts nothing in its place; INSTALLER_CHOICE_PLAN section 7"
        )
    else:
        elevated = source_code.split("if (elevated_continuation)", 1)
        if len(elevated) != 2 or not calls(elevated[1]):
            failures.append(
                f"{SOURCE}: the writability test is not reached from the "
                "elevated continuation. Performed before elevating it tests "
                "the wrong token and passes on exactly the folders it exists "
                "to catch; INSTALLER_CHOICE_PLAN section 3"
            )
        if calls(source_code.split("if (elevated_continuation)")[0]):
            failures.append(
                f"{SOURCE}: the writability test is also called before the "
                "elevated continuation, where the token is the wrong one"
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

    # -- IU-18: the notification loop that never opened a window -------------
    #
    # An edit control notifies its parent with EN_CHANGE whenever its text is
    # set, and it does not care whether a person typed it or the program wrote
    # it. So a WM_COMMAND/EN_CHANGE handler that writes the same box calls
    # itself, synchronously, forever. Build #56 shipped exactly that: the write
    # was on the per-user branch, WM_INITDIALOG seeds the dialog per-user, and
    # the process died of STATUS_STACK_OVERFLOW inside DialogBoxParamW with no
    # window ever drawn and nothing at all on screen.
    #
    # What is checked is the mechanism rather than a name. Find the function the
    # EN_CHANGE case calls; if that function writes an edit control, it must
    # hold a re-entrancy flag -- read in an early return, set true, set false --
    # and that flag must be a member of DialogState, which is the only thing
    # that lives across the nested call.
    handler = re.search(r"EN_CHANGE\)\s*\{\s*(\w+)\(", source_code)
    if not handler:
        failures.append(
            f"{SOURCE}: the EN_CHANGE case does not call a named function, so "
            "this check cannot tell whether it can re-enter itself (IU-18)")
    else:
        name = handler.group(1)
        body = _function_body(source_code, name)
        if body is None:
            failures.append(
                f"{SOURCE}: EN_CHANGE calls {name}, which is not defined here "
                "(IU-18)")
        elif "SetDlgItemTextW" in body and "_EDIT" in body:
            guard = re.search(
                r"if\s*\(\s*state->(\w+)\s*\)\s*\{\s*return;\s*\}", body)
            if not guard:
                failures.append(
                    f"{SOURCE}: {name} handles EN_CHANGE and writes an edit "
                    "control, so setting that control calls it again. It has no "
                    "re-entrancy guard, which is unbounded recursion and a "
                    "dialog that never opens (IU-18)")
            else:
                flag = guard.group(1)
                for value in ("true", "false"):
                    if f"state->{flag} = {value};" not in body:
                        failures.append(
                            f"{SOURCE}: {name}'s re-entrancy guard never sets "
                            f"{flag} to {value}, so it either never engages or "
                            "never releases (IU-18)")
                if not re.search(
                        rf"struct DialogState\s*\{{[^}}]*\bbool {flag} = false;",
                        source_code, re.S):
                    failures.append(
                        f"{SOURCE}: {flag} is not a `bool ... = false` member of "
                        "DialogState; a guard that does not outlive the call it "
                        "guards guards nothing (IU-18)")

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
