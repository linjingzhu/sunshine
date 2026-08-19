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
import struct
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

# The one icon ADR 0008's overlay supplies for `chrome.exe`. The mirrored path
# *is* the destination, so this literal is the same string the overlay uses and
# a rename on either side is a missing file rather than a silent disagreement.
ICON_ASSET = "downstream/assets/chrome/app/theme/chromium/win/chromium.ico"

# Windows resource types, from `winuser.h`. Named here rather than imported
# because `ctypes` is loaded only on the Windows path and these are read by the
# pure parsers below, which run everywhere.
RT_ICON = 3
RT_GROUP_ICON = 14

# Not an icon type. It is the control: `check_version_resource` reads
# chrome.exe's VERSIONINFO through an entirely different API and it passes, so
# a resource enumeration that cannot see RT_VERSION is not reading the binary.
RT_VERSION = 16

# The three layouts an icon takes on its way into a binary. An `.ico` file is an
# `ICONDIR` followed by `ICONDIRENTRY` records that point at image payloads by
# *file offset*; a PE holds the same header as a `GRPICONDIR` whose entries end
# in a two-byte `RT_ICON` *resource id* instead of a four-byte offset. The
# header is identical, the entries are not, and that difference is the whole
# reason a byte-for-byte comparison of the two forms is the wrong test.
#
# These are not imported from `scripts/verify_asset_overlay.py`, which parses
# the first of them for a different purpose. That module imports `subprocess` at
# module scope, and the property this file is built around -- proved by
# `tests/test_installed_build.py` and paid for by build #21 -- is that nothing
# here can start a process. Two small `struct` formats are a cheaper thing to
# keep in step than that guarantee is to give up.
ICONDIR = struct.Struct("<HHH")
ICONDIRENTRY = struct.Struct("<BBBBHHII")
GRPICONDIRENTRY = struct.Struct("<BBBBHHIH")


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


def check_version_resource(out: Path, result: Result) -> None:
    """Read the version Windows will show for `chrome.exe`, without running it.

    An earlier version of this check launched `chrome.exe --version`, and it
    was wrong twice over. First it required console output, which a Windows GUI
    subsystem binary never writes to a redirected pipe, so build #20 reported
    FAIL on a browser that was fine. Then the deeper problem surfaced: on
    Windows the exit code cannot distinguish "printed its version and exited"
    from "launched the browser and the stub handed off", because both return 0
    immediately. Build #21 proved which one had been happening --
    `lld-link: failed to write output './chrome_elf.dll': permission denied`,
    because a browser started by the previous run's verification was still
    alive and holding its own DLL open.

    So the build machine must not start the browser it just built. What is left
    is reading the binary, which is genuinely worth doing: `VERSIONINFO` is
    written by `rc.exe` from the branding this project patches, so a correct
    version string is evidence that the resource pipeline ran end to end and
    that patch 0001's BRANDING reached the artifact. That is the same pipeline
    the icon overlay depends on.

    **What no longer has an automated answer.** Whether the browser starts at
    all is now a manual gate (RV-1 and after), and that is the honest position
    rather than a gap: the only way to answer it here was to run a browser on
    the machine that is also the only CI, which breaks the next build.
    """

    if sys.platform != "win32":
        result.record(
            UNAVAILABLE,
            "chrome.exe carries a version resource",
            f"needs Windows; this is {sys.platform}",
        )
        return

    chrome = out / "chrome.exe"
    if not chrome.is_file():
        # check_artifacts already recorded the failure; restating it here would
        # be noise.
        return

    import ctypes  # noqa: PLC0415 -- Windows-only path
    from ctypes import wintypes  # noqa: PLC0415

    version_dll = ctypes.WinDLL("version")
    path = str(chrome)

    size = version_dll.GetFileVersionInfoSizeW(path, None)
    if not size:
        result.record(
            FAILED,
            "chrome.exe carries a version resource",
            "no VERSIONINFO -- rc.exe did not write one, or the link dropped it",
        )
        return

    buffer = ctypes.create_string_buffer(size)
    if not version_dll.GetFileVersionInfoW(path, 0, size, buffer):
        result.record(FAILED, "chrome.exe carries a version resource", "VERSIONINFO unreadable")
        return

    value = ctypes.c_void_p()
    length = wintypes.UINT()
    if not version_dll.VerQueryValueW(
        buffer, "\\", ctypes.byref(value), ctypes.byref(length)
    ) or not length.value:
        result.record(FAILED, "chrome.exe carries a version resource", "no fixed-info block")
        return

    # VS_FIXEDFILEINFO: dwSignature, dwStrucVersion, then the four 16-bit
    # version fields packed as two DWORDs, most significant word first.
    fixed = ctypes.cast(value, ctypes.POINTER(wintypes.DWORD * 4)).contents
    if fixed[0] != 0xFEEF04BD:
        result.record(FAILED, "chrome.exe carries a version resource", "bad VS_FIXEDFILEINFO signature")
        return

    most, least = fixed[2], fixed[3]
    version = f"{most >> 16}.{most & 0xFFFF}.{least >> 16}.{least & 0xFFFF}"
    if version.startswith("0.0.0"):
        result.record(
            FAILED,
            "chrome.exe carries a version resource",
            f"version reads {version} -- the build did not stamp one",
        )
        return
    result.record(PASSED, "chrome.exe carries a version resource", version)


class IconResourceError(RuntimeError):
    """A resource that cannot be read at all, as distinct from one that differs."""


def ico_images(data: bytes) -> list[tuple[int, bytes]]:
    """`[(declared pixel size, image payload)]` from an `.ico` file.

    The payload is the slice the directory entry points at -- a DIB or, for the
    256 px entry, a PNG -- and it is what survives being linked. Nothing here
    interprets it.
    """

    return _icon_directory(data, ICONDIRENTRY, "icon file")


def group_icon_entries(data: bytes) -> list[tuple[int, int]]:
    """`[(declared pixel size, RT_ICON resource id)]` from a `GRPICONDIR`.

    Same header, same first six fields per entry, and then the difference that
    matters: where the file wrote a four-byte offset into itself, the binary
    writes the two-byte id of the `RT_ICON` holding that image.
    """

    return _icon_directory(data, GRPICONDIRENTRY, "group icon resource")


def _icon_directory(
    data: bytes, entry_struct: struct.Struct, what: str
) -> list[tuple[int, bytes]] | list[tuple[int, int]]:
    """The shared walk over both directory layouts.

    They differ only in the last field of an entry, so the header validation,
    the 0-means-256 convention and the bounds arithmetic are written once. A
    second copy of them is how the two forms would drift apart.
    """

    if len(data) < ICONDIR.size:
        raise IconResourceError(f"{what} is too short to hold a directory")
    reserved, kind, count = ICONDIR.unpack_from(data, 0)
    if reserved != 0 or kind != 1:
        raise IconResourceError(f"{what} is not an icon directory (reserved={reserved}, type={kind})")
    if count == 0:
        raise IconResourceError(f"{what} declares no images")
    end = ICONDIR.size + count * entry_struct.size
    if len(data) < end:
        raise IconResourceError(f"{what} directory runs past the end of the data")

    found = []
    for index in range(count):
        fields = entry_struct.unpack_from(data, ICONDIR.size + index * entry_struct.size)
        width, _height, _colours, _reserved, _planes, _bits, length, tail = fields
        # Zero means 256: the field is one byte and 256 does not fit. This is
        # the same convention `scripts/verify_asset_overlay.py` reads, and it is
        # why the committed icon's fourth entry declares width 0.
        width = width or 256
        if entry_struct is GRPICONDIRENTRY:
            # `tail` is the RT_ICON id; there is nothing to bound-check, the
            # resource either exists in the binary or it does not.
            found.append((width, tail))
            continue
        # `tail` is a byte offset into this same file.
        if length == 0 or tail + length > len(data):
            raise IconResourceError(f"{what} entry {index} ({width}px) points past the end")
        found.append((width, data[tail:tail + length]))
    return found


def read_icon_resources(path: Path) -> tuple[int, bytes, dict[int, bytes]] | None:
    """`(lowest RT_GROUP_ICON id, its bytes, {RT_ICON id: bytes})`, or None.

    None means the binary carries no `RT_GROUP_ICON` at all. Windows-only; every
    caller reaches this behind the same platform gate the other checks use.

    **Why the loader API and not a PE parser.** Both were available. Parsing the
    PE resource directory out of the file would be stdlib-only and would run
    anywhere, which is a real advantage -- but it means writing a second
    implementation of the lookup Windows itself performs, and the question this
    check asks is precisely *what Windows will find*. A parser that disagreed
    with the loader about which `RT_GROUP_ICON` wins, or about how a resource
    directory with a name level and a language level is walked, would answer a
    question nobody asked. `LoadLibraryExW` answers the real one, and it is
    roughly sixty lines instead of two hundred.

    **And it still does not run the binary.** `LOAD_LIBRARY_AS_DATAFILE` maps
    the file as data: no entry point is called, no `DllMain` runs, no imports
    are resolved, and the mapping is not even required to match this process's
    architecture. That is the whole reason it is safe here. Build #21 died
    because verification *started* the browser and it held `chrome_elf.dll`
    open; a data-file mapping is closed by `FreeLibrary` before this returns and
    holds nothing after that.
    """

    import ctypes  # noqa: PLC0415 -- Windows-only path
    from ctypes import wintypes  # noqa: PLC0415

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.LoadLibraryExW.restype = wintypes.HMODULE
    kernel32.LoadLibraryExW.argtypes = (wintypes.LPCWSTR, wintypes.HANDLE, wintypes.DWORD)
    kernel32.FindResourceW.restype = wintypes.HANDLE
    kernel32.FindResourceW.argtypes = (wintypes.HMODULE, ctypes.c_void_p, ctypes.c_void_p)
    kernel32.LoadResource.restype = wintypes.HANDLE
    kernel32.LoadResource.argtypes = (wintypes.HMODULE, wintypes.HANDLE)
    kernel32.LockResource.restype = ctypes.c_void_p
    kernel32.LockResource.argtypes = (wintypes.HANDLE,)
    kernel32.SizeofResource.restype = wintypes.DWORD
    kernel32.SizeofResource.argtypes = (wintypes.HMODULE, wintypes.HANDLE)
    kernel32.FreeLibrary.argtypes = (wintypes.HMODULE,)
    kernel32.EnumResourceNamesW.restype = wintypes.BOOL
    kernel32.EnumResourceNamesW.argtypes = (
        wintypes.HMODULE, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p
    )

    LOAD_LIBRARY_AS_DATAFILE = 0x00000002
    ERROR_RESOURCE_DATA_NOT_FOUND = 1812
    ERROR_RESOURCE_TYPE_NOT_FOUND = 1813

    module = kernel32.LoadLibraryExW(str(path), None, LOAD_LIBRARY_AS_DATAFILE)
    if not module:
        raise IconResourceError(
            f"{path.name} could not be mapped as a data file "
            f"(GetLastError {ctypes.get_last_error()})"
        )

    try:
        def ids(resource_type: int) -> list[int]:
            """Integer resource ids of one type.

            The callback takes the name as `c_void_p` deliberately. An integer
            id arrives as a small value in a pointer-shaped argument, and a
            prototype declaring `LPCWSTR` would have `ctypes` dereference `101`.
            Names above 0xFFFF are real strings; `.rc` files can use them, this
            project's icons do not, and one that appeared would be skipped
            rather than misread.
            """

            found: list[int] = []
            callback = ctypes.WINFUNCTYPE(
                wintypes.BOOL, wintypes.HMODULE, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p
            )

            def visit(_module, _type, name, _parameter):
                if name is not None and name < 0x10000:
                    found.append(int(name))
                return True

            ctypes.set_last_error(0)
            if not kernel32.EnumResourceNamesW(module, resource_type, callback(visit), None):
                # FALSE means either "this binary holds no resource of that
                # type" or "the enumeration failed", and those must not be
                # reported as the same thing: the first is the finding this
                # check exists to make, the second is a check that did not run.
                # Only the two not-found codes are the first.
                code = ctypes.get_last_error()
                if code not in (ERROR_RESOURCE_DATA_NOT_FOUND, ERROR_RESOURCE_TYPE_NOT_FOUND):
                    raise IconResourceError(
                        f"{path.name}: enumerating resource type {resource_type} failed "
                        f"(GetLastError {code})"
                    )
            return found

        def resource(resource_type: int, identifier: int) -> bytes:
            handle = kernel32.FindResourceW(module, identifier, resource_type)
            if not handle:
                raise IconResourceError(f"{path.name} lost resource {resource_type}/{identifier}")
            size = kernel32.SizeofResource(module, handle)
            address = kernel32.LockResource(kernel32.LoadResource(module, handle))
            if not address or not size:
                raise IconResourceError(f"{path.name} resource {resource_type}/{identifier} is empty")
            return ctypes.string_at(address, size)

        groups = ids(RT_GROUP_ICON)
        if not groups:
            # "No icon in this binary" and "this enumeration is not working"
            # are different findings, and only the first is this check's to
            # make. The distinction is already drawn one level down, for the
            # two not-found error codes; it has to be drawn here too, because
            # an enumeration that silently visits nothing returns TRUE and
            # looks exactly like an absent resource.
            #
            # RT_VERSION settles it. `check_version_resource` reads chrome.exe's
            # VERSIONINFO through `version.dll` -- a different API, no
            # enumeration -- and reports the version, so the resource is there.
            # If this code cannot see it either, the fault is here, and
            # reporting a missing icon would be reporting our own defect as the
            # build's.
            if not ids(RT_VERSION):
                raise IconResourceError(
                    f"{path.name}: this check found no RT_VERSION either, and the "
                    "version resource is demonstrably present -- so it is not "
                    "reading the binary's resource table and cannot speak to the "
                    "icon either way"
                )
            return None
        # Windows shows the application the *lowest-numbered* group icon, which
        # in Chromium's `chrome/app/chrome_exe.rc` is `IDR_MAINFRAME`. That is
        # the one the overlay replaces and the only one this check speaks for.
        group = min(groups)
        return group, resource(RT_GROUP_ICON, group), {
            identifier: resource(RT_ICON, identifier) for identifier in ids(RT_ICON)
        }
    finally:
        kernel32.FreeLibrary(module)


def check_icon_resource(out: Path, result: Result, reader=None) -> None:
    """Prove `rc.exe` linked Sunshine's icon into `chrome.exe`, by reading it.

    This is the automated half of RV-10, and ADR 0008 is explicit about why it
    was missing: the overlay's failure mode is *silence*.
    `scripts/verify_asset_overlay.py` proves the committed `.ico` is a valid
    icon and `scripts/verify_pinned_upstream.py` proves the destination still
    exists upstream, but neither can prove the copy happened or that the
    resource compiler consumed it. A build that shipped Chromium's own blue
    sphere under Sunshine's name passes both of them and every other guard.

    **What is compared, and why not the whole file.** The committed `.ico` and
    the linked resource are different objects by construction. The file is an
    `ICONDIR` whose entries carry byte offsets into itself; the binary holds a
    `GRPICONDIR` whose entries carry `RT_ICON` resource ids, with each image
    moved into a resource of its own. `rc.exe` rewrites the directory, so a
    whole-file comparison would fail on a *correct* build. What it does not
    touch is the images: each one is copied into its `RT_ICON` verbatim. So the
    comparison is **the set of image payloads** -- resolve every group entry to
    its `RT_ICON` and require that multiset to equal the payload multiset the
    committed file holds.

    **Why not the size set.** It is simpler and it is nearly worthless here.
    `verify_asset_overlay.py` requires 16, 32, 48 and 256 px because that is the
    set *Chromium's own* `chromium.ico` carries -- the set was copied from
    upstream, not chosen. So the icon this check exists to catch has exactly the
    same size set as the icon it expects, and a size comparison would pass the
    one build it is supposed to fail.

    **What this does not establish.** Three things; RV-10 keeps the first two
    and RV-11 the last.

      * That anything *looks* right. This compares bytes, not pixels. An icon
        drawn wrong, upside down, or at the wrong scale is byte-identical to
        itself and passes here.
      * That Windows *shows* it. The shell picks an entry by exact pixel match
        and caches what it picked; Explorer's list view, the taskbar and a
        pinned shortcut do not all ask for the same size, and a shortcut can
        carry its own icon regardless of the binary. Only a person looking at
        three sizes settles that.
      * Anything about `mini_installer.exe`, whose icon is a separate overlay
        file and remains RV-11's alone, or about the other icons
        `chrome_exe.rc` declares -- `IDR_X001_APP_LIST`, `IDR_X003_INCOGNITO`,
        `IDR_X006_HTML_DOC`, `IDR_X007_PDF_DOC`. Those are Chromium's own
        artwork, the overlay does not replace them, and no contract here says
        what they should contain. Checking them would be asserting that
        upstream had not changed its own document icons.
    """

    name = "chrome.exe carries the Sunshine icon"

    if sys.platform != "win32":
        result.record(UNAVAILABLE, name, f"needs Windows; this is {sys.platform}")
        return

    chrome = out / "chrome.exe"
    if not chrome.is_file():
        # check_artifacts already recorded the failure; restating it here would
        # be noise.
        return

    committed = ROOT / ICON_ASSET
    if not committed.is_file():
        result.record(FAILED, name, f"nothing to compare against: {ICON_ASSET} is missing")
        return

    try:
        expected = ico_images(committed.read_bytes())
        found = (reader or read_icon_resources)(chrome)
    except IconResourceError as error:
        result.record(FAILED, name, str(error))
        return

    if found is None:
        result.record(
            FAILED,
            name,
            "chrome.exe carries RT_VERSION but no RT_GROUP_ICON -- the "
            "resource table is being read, and there is no application icon "
            "in it, so rc.exe linked none",
        )
        return

    group, directory, icons = found
    try:
        entries = group_icon_entries(directory)
    except IconResourceError as error:
        result.record(FAILED, name, str(error))
        return

    linked: list[tuple[int, bytes]] = []
    for size, identifier in entries:
        if identifier not in icons:
            result.record(
                FAILED,
                name,
                f"group icon {group} names RT_ICON {identifier} for {size}px, "
                "which chrome.exe does not carry -- the resource table is truncated",
            )
            return
        linked.append((size, icons[identifier]))

    if sorted(payload for _, payload in expected) == sorted(payload for _, payload in linked):
        sizes = ", ".join(f"{size}px" for size, _ in sorted(expected))
        result.record(PASSED, name, f"application icon is group {group}; {sizes} match ADR 0008")
        return

    shipped = {payload for _, payload in linked}
    missing = sorted(size for size, payload in expected if payload not in shipped)
    result.record(
        FAILED,
        name,
        f"group {group} carries {_sizes(linked)} but not the committed image data"
        + (f" at {', '.join(f'{size}px' for size in missing)}" if missing else "")
        + f"; the build linked a different icon than {ICON_ASSET} "
        "-- most likely Chromium's own, because the overlay copy did not reach the .rc",
    )


def _sizes(entries: list[tuple[int, bytes]]) -> str:
    return ", ".join(f"{size}px" for size, _ in sorted(entries)) or "no images"


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
    check_version_resource(out, result)
    check_icon_resource(out, result)

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
