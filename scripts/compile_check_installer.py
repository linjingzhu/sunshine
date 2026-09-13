#!/usr/bin/env python3
"""Syntax-check the installer front-ends with a Windows cross-compiler.

**Why this exists.** `installer/sunshine_setup.cpp` and
`installer/sunshine_uninstall.cpp` are the only C++ in this repository, they
are compiled by MSVC on one Windows machine, and until now nothing anywhere
else could tell whether they even parsed. The cost of finding out was a
forty-minute Chromium build followed by a seven-second compile step at the end
of it -- and three separate builds have already been spent on defects that a
compiler would have named instantly.

`x86_64-w64-mingw32-g++ -fsyntax-only` is not MSVC and this does not pretend to
be a substitute for the real compile. What it catches is the large class this
project actually loses builds to: a brace that does not close, a name that does
not exist, a signature that does not match, an include that was removed while a
use of it was not.

Two accommodations, both stated rather than hidden:

  * `BCRYPT_SHA256_ALG_HANDLE` is a Windows 10 SDK pseudo-handle that
    mingw-w64's headers do not define. It is supplied on the command line with
    its documented value. Without it this tool reports two errors in code that
    has compiled on the real toolchain for months, which is worse than useless.
  * `engine_hash.h` is generated at build time and deliberately never committed,
    so a stand-in is written into a temporary directory.

Skips, loudly, when the cross-compiler is absent: a check that silently passes
because its tool is missing is the thing this file is trying to replace.
"""

from __future__ import annotations

from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
COMPILER = "x86_64-w64-mingw32-g++"

SOURCES = ("installer/sunshine_setup.cpp", "installer/sunshine_uninstall.cpp")

# mingw-w64 13 does not declare this. `bcrypt.h` in the Windows 10 SDK defines
# the SHA-256 algorithm pseudo-handle as 0x00000041.
DEFINES = ("BCRYPT_SHA256_ALG_HANDLE=((BCRYPT_ALG_HANDLE)0x00000041)",)

ENGINE_HASH = """\
// A stand-in for the header scripts/build_installer_frontend.ps1 generates.
// The real one carries one build's engine hash and is never committed.
#ifndef SUNSHINE_INSTALLER_ENGINE_HASH_H_
#define SUNSHINE_INSTALLER_ENGINE_HASH_H_
inline constexpr wchar_t kEngineSha256[] =
    L"0000000000000000000000000000000000000000000000000000000000000000";
#endif  // SUNSHINE_INSTALLER_ENGINE_HASH_H_
"""


def available() -> bool:
    return shutil.which(COMPILER) is not None


def check(root: Path = ROOT) -> list[str]:
    failures: list[str] = []
    with tempfile.TemporaryDirectory() as directory:
        work = Path(directory)
        for header in (root / "installer").glob("*.h"):
            shutil.copy(header, work / header.name)
        (work / "engine_hash.h").write_text(ENGINE_HASH, encoding="utf-8")
        for relative in SOURCES:
            source = root / relative
            if not source.is_file():
                failures.append(f"{relative}: missing")
                continue
            shutil.copy(source, work / source.name)
            command = [
                COMPILER, "-fsyntax-only", "-std=c++20", "-Wall", "-Wextra",
                "-municode", "-DUNICODE", "-D_UNICODE", "-D_WIN32_WINNT=0x0A00",
                *(f"-D{define}" for define in DEFINES),
                "-I.", source.name,
            ]
            result = subprocess.run(command, cwd=work, capture_output=True,
                                    text=True, check=False)
            if result.returncode != 0:
                failures.append(f"{relative}:\n{result.stdout}{result.stderr}")
            elif result.stderr.strip():
                failures.append(f"{relative} warns:\n{result.stderr}")
            else:
                print(f"OK   {relative}")
    return failures


def main() -> int:
    if not available():
        print(f"{COMPILER} is not installed, so the installer front-ends were "
              f"NOT syntax-checked.\nInstall it with: apt-get install mingw-w64",
              file=sys.stderr)
        return 2
    failures = check()
    for failure in failures:
        print(failure, file=sys.stderr)
    if failures:
        print(f"{len(failures)} installer source(s) did not compile.", file=sys.stderr)
        return 1
    print(f"Installer front-ends syntax-checked with {COMPILER}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
