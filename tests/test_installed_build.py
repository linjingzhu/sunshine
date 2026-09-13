"""Tests for the built-browser check.

This is the first check that reads the build output, so its failure modes are
different from every other guard's: it can be pointed at nothing, at a build
made with the wrong configuration, or run on a platform where half of it cannot
execute. Each of those must be distinguishable from a pass.
"""

from pathlib import Path
import struct
import sys
import tempfile
import unittest
from unittest import mock

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY_ROOT / "scripts"))

import verify_installed_build as built  # noqa: E402


class BuildOutputTests(unittest.TestCase):
    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory()
        self.out = Path(self.directory.name)
        self.addCleanup(self.directory.cleanup)
        for name in built.ARTIFACTS:
            (self.out / name).write_bytes(b"x" * 1024)
        self.write_args("\n".join(built.REQUIRED_ARGS))

    def write_args(self, text: str) -> None:
        (self.out / "args.gn").write_text(text + "\n", encoding="utf-8")

    def statuses(self) -> list[tuple[str, str]]:
        result = built.Result()
        built.check_artifacts(self.out, result)
        built.check_build_arguments(self.out, result)
        return [(status, name) for status, name, _ in result.rows]

    def test_a_complete_build_passes(self) -> None:
        self.assertNotIn(built.FAILED, [status for status, _ in self.statuses()])

    def test_a_missing_artifact_fails(self) -> None:
        (self.out / "chrome.exe").unlink()
        self.assertIn((built.FAILED, "artifact chrome.exe"), self.statuses())

    def test_a_missing_args_file_fails(self) -> None:
        (self.out / "args.gn").unlink()
        self.assertIn(built.FAILED, [status for status, _ in self.statuses()])

    def test_codecs_disabled_in_the_actual_build_fails(self) -> None:
        """ADR 0004 is a claim about the artifact, not about the script.

        The build script could be edited, reverted, or simply not the thing that
        produced this directory. args.gn is what GN actually used.
        """

        self.write_args("is_official_build=true\nis_debug=false\nproprietary_codecs=false")
        failures = [name for status, name in self.statuses() if status == built.FAILED]
        self.assertIn("build argument proprietary_codecs=true", failures)

    def test_widevine_disabled_in_the_actual_build_fails(self) -> None:
        """ADR 0024, and the one argument whose loss is hardest to attribute.

        A build without it plays every unprotected video perfectly and fails on
        Netflix with M7701-1003 -- a message that names a *setting* the user is
        told to change. So the symptom points at the user's browser
        configuration and not at the build, which is exactly how build #57 spent
        a session being diagnosed as a site problem. This is the cheapest place
        to say what it really is.
        """

        kept = [arg for arg in built.REQUIRED_ARGS if not arg.startswith("enable_widevine")]
        self.write_args("\n".join(kept))
        failures = [name for status, name in self.statuses() if status == built.FAILED]
        self.assertIn("build argument enable_widevine=true", failures)

    def test_widevine_explicitly_turned_off_fails(self) -> None:
        """Absent and false are different edits and both have to be refused."""

        kept = [arg for arg in built.REQUIRED_ARGS if not arg.startswith("enable_widevine")]
        self.write_args("\n".join(kept) + "\nenable_widevine=false")
        failures = [name for status, name in self.statuses() if status == built.FAILED]
        self.assertIn("build argument enable_widevine=true", failures)

    def test_a_sandbox_disabling_argument_in_the_build_fails(self) -> None:
        self.write_args("\n".join(built.REQUIRED_ARGS) + '\nextra_cflags="--no-sandbox"')
        failures = [name for status, name in self.statuses() if status == built.FAILED]
        self.assertIn("no security boundary is disabled", failures)

    def test_an_isolation_disabling_argument_in_the_build_fails(self) -> None:
        self.write_args("\n".join(built.REQUIRED_ARGS) + '\nextra_args="--single-process"')
        failures = [name for status, name in self.statuses() if status == built.FAILED]
        self.assertIn("no security boundary is disabled", failures)

    def test_an_enabling_argument_does_not_fail(self) -> None:
        self.write_args("\n".join(built.REQUIRED_ARGS) + '\nextra_args="--site-per-process"')
        self.assertNotIn(built.FAILED, [status for status, _ in self.statuses()])


class PlatformHonestyTests(unittest.TestCase):
    """A check that cannot run must not report that it passed."""

    def test_the_registry_check_reports_unavailable_off_windows(self) -> None:
        result = built.Result()
        with mock.patch.object(built.sys, "platform", "linux"):
            built.check_no_registered_scheme(result)
        self.assertTrue(result.unavailable)
        self.assertFalse(result.failed)

    def test_unavailable_is_not_success(self) -> None:
        """Exit 2 is neither pass nor fail, and CI must not read it as green."""

        result = built.Result()
        result.record(built.PASSED, "something")
        result.record(built.UNAVAILABLE, "something else")
        self.assertTrue(result.unavailable)
        self.assertFalse(result.failed)


class VersionResourceCheckTests(unittest.TestCase):
    """The check that replaced a launching one, and why.

    Launching `chrome.exe` on the build machine broke the next build: a browser
    left running by build #20's verification held `chrome_elf.dll` open, and
    build #21 died on `lld-link: permission denied`. On Windows the exit code
    cannot tell "printed a version and exited" from "launched the browser and
    handed off", so there was no safe way to keep it. Reading the binary is
    what remains, and it is not nothing -- VERSIONINFO is written by rc.exe
    from the branding this project patches.
    """

    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory()
        self.out = Path(self.directory.name)
        self.addCleanup(self.directory.cleanup)
        (self.out / "chrome.exe").write_bytes(b"x" * 1024)

    def test_off_windows_is_unavailable_not_a_pass(self) -> None:
        result = built.Result()
        with mock.patch.object(built.sys, "platform", "linux"):
            built.check_version_resource(self.out, result)
        self.assertTrue(result.unavailable)
        self.assertFalse(result.failed)

    def test_a_missing_binary_reports_nothing_new(self) -> None:
        """`check_artifacts` already failed on this."""

        (self.out / "chrome.exe").unlink()
        result = built.Result()
        with mock.patch.object(built.sys, "platform", "win32"):
            built.check_version_resource(self.out, result)
        self.assertEqual([], result.rows)

    def test_the_check_never_starts_a_process(self) -> None:
        """The property build #21 paid for. `verify_installed_build` must not
        import subprocess or launch anything: the build machine is also the
        only CI, and a browser it starts holds its own DLLs open until the next
        build fails to link them."""

        source = (REPOSITORY_ROOT / "scripts" / "verify_installed_build.py").read_text(
            encoding="utf-8"
        )
        for forbidden in ("import subprocess", "subprocess.run", "Popen", "os.system"):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, source)


class IconResourceCheckTests(unittest.TestCase):
    """RV-10's automatable half: did `rc.exe` link the icon the overlay supplies?

    ADR 0008 named this gap and left it open -- the overlay is verified in
    source and against the pinned revision, and neither can see whether the copy
    reached the resource compiler. A build shipping Chromium's blue sphere under
    Sunshine's name passes every other guard in the repository.

    The linked side is synthesised here rather than taken from a real binary.
    The committed `.ico` is read as the expected side and never written to: the
    fixtures below rebuild its images into the `GRPICONDIR` + `RT_ICON` shape a
    PE holds, which is exactly the transformation the check has to see through.
    That the two forms are *not* byte-identical is the reason the check compares
    payloads instead of files, and `test_a_matching_build_passes` is what proves
    the transformation alone does not read as a mismatch.
    """

    COMMITTED = "downstream/assets/chrome/app/theme/chromium/win/chromium.ico"

    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory()
        self.out = Path(self.directory.name)
        self.addCleanup(self.directory.cleanup)
        (self.out / "chrome.exe").write_bytes(b"x" * 1024)
        self.images = built.ico_images((REPOSITORY_ROOT / self.COMMITTED).read_bytes())

    @staticmethod
    def resources(images, group=101, first_id=1):
        """The committed images in the shape a PE carries them.

        `rc.exe` splits the file: each image becomes an `RT_ICON` of its own and
        the directory is rewritten with resource ids where the file had offsets.
        The ids here start at 1 rather than matching anything real, which is the
        point -- nothing in the comparison may depend on them.
        """

        entries = b""
        icons = {}
        for index, (size, payload) in enumerate(images):
            identifier = first_id + index
            # 0 means 256 in a one-byte width field, going out as it came in.
            entries += struct.pack(
                "<BBBBHHIH", size % 256, size % 256, 0, 0, 1, 32, len(payload), identifier
            )
            icons[identifier] = payload
        return group, struct.pack("<HHH", 0, 1, len(images)) + entries, icons

    def run_check(self, reader):
        result = built.Result()
        with mock.patch.object(built.sys, "platform", "win32"):
            built.check_icon_resource(self.out, result, reader=reader)
        return result

    def test_off_windows_is_unavailable_not_a_pass(self) -> None:
        result = built.Result()
        with mock.patch.object(built.sys, "platform", "linux"):
            built.check_icon_resource(self.out, result, reader=lambda path: None)
        self.assertTrue(result.unavailable)
        self.assertFalse(result.failed)

    def test_a_missing_binary_reports_nothing_new(self) -> None:
        """`check_artifacts` already failed on this, as with the version check."""

        (self.out / "chrome.exe").unlink()
        self.assertEqual([], self.run_check(lambda path: None).rows)

    def test_a_matching_build_passes(self) -> None:
        result = self.run_check(lambda path: self.resources(self.images))
        self.assertFalse(result.failed, result.report())
        self.assertIn(built.PASSED, [status for status, _, _ in result.rows])

    def test_a_binary_carrying_a_different_icon_fails(self) -> None:
        """The failure the check exists for, and the reason it is not a size check.

        The stand-in for Chromium's own icon declares the *same four sizes* --
        16, 32, 48 and 256 -- because `verify_asset_overlay.py` took that set
        from upstream rather than choosing it. So the size set cannot tell the
        two icons apart, and only the image data can.
        """

        other = [(size, bytes(len(payload))) for size, payload in self.images]
        self.assertEqual(
            [size for size, _ in self.images], [size for size, _ in other],
            "the fixture must differ in image data alone",
        )
        result = self.run_check(lambda path: self.resources(other))
        self.assertTrue(result.failed, result.report())
        self.assertIn("linked a different icon", result.report())

    def test_one_altered_image_fails_and_the_size_is_named(self) -> None:
        """A partial overlay -- three sizes replaced, one left as Chromium's."""

        damaged = list(self.images)
        size, payload = damaged[2]
        damaged[2] = (size, bytes([payload[0] ^ 0xFF]) + payload[1:])
        result = self.run_check(lambda path: self.resources(damaged))
        self.assertTrue(result.failed, result.report())
        self.assertIn(f"{size}px", result.report())

    def test_a_string_named_group_passes(self) -> None:
        """chrome.exe's real shape. Every icon in it is named, not numbered, so
        a check that only handled integer names could not pass on the browser
        it exists to check -- which is what builds #27 and #28 showed."""

        result = self.run_check(
            lambda path: self.resources(self.images, group="IDR_MAINFRAME")
        )
        self.assertFalse(result.failed, result.report())
        self.assertIn(built.PASSED, [status for status, _, _ in result.rows])

    def test_a_string_named_group_carrying_the_wrong_icon_still_fails(self) -> None:
        """The name is how the resource is found; it must not soften what is
        compared once it is."""

        wrong = [(size, bytes(len(payload))) for size, payload in self.images]
        result = self.run_check(
            lambda path: self.resources(wrong, group="IDR_MAINFRAME")
        )
        self.assertTrue(result.failed, result.report())

    def test_a_binary_with_no_icon_resource_fails_and_names_the_cause(self) -> None:
        """The silent failure ADR 0008 describes, in its purest form.

        `None` from the reader now means something stronger than it did: the
        reader only returns it once RT_VERSION has been found, so the message
        may say the table was read and held no icon. Before that control
        existed the same `None` also covered "the enumeration saw nothing at
        all", and build #27 is where that ambiguity cost a run -- the check
        told the build it had shipped no icon when it could not yet tell that
        from its own enumeration failing.
        """

        result = self.run_check(lambda path: None)
        self.assertTrue(result.failed, result.report())
        self.assertIn("RT_GROUP_ICON", result.report())
        self.assertIn("RT_VERSION", result.report())

    def test_an_enumeration_that_reads_nothing_is_not_a_missing_icon(self) -> None:
        """The distinction the control draws, from the consumer's side.

        A reader that cannot read raises rather than returning `None`, and the
        failure names the check rather than the build. Both are FAIL -- neither
        is a pass -- but they send whoever reads the log to different files.
        """

        def broken(path):
            raise built.IconResourceError(
                f"{path.name}: this check found no RT_VERSION either, and the "
                "version resource is demonstrably present -- so it is not "
                "reading the binary's resource table and cannot speak to the "
                "icon either way"
            )

        result = self.run_check(broken)
        self.assertTrue(result.failed, result.report())
        self.assertIn("not reading the binary's resource table", result.report())
        self.assertNotIn("rc.exe linked none", result.report())

    def test_the_control_type_is_the_one_the_other_check_proves(self) -> None:
        """RT_VERSION is the control precisely because `check_version_resource`
        reads it through `version.dll` and passes. If that check were ever
        removed the control would lose its warrant, so the two are pinned
        together here rather than left to a comment."""

        self.assertEqual(16, built.RT_VERSION)
        source = (REPOSITORY_ROOT / "scripts" / "verify_installed_build.py").read_text(
            encoding="utf-8"
        )
        self.assertIn("def check_version_resource", source)
        self.assertIn("GetFileVersionInfoSizeW", source)

    def test_a_group_naming_an_absent_icon_fails(self) -> None:
        group, directory, icons = self.resources(self.images)
        icons.pop(max(icons))
        result = self.run_check(lambda path: (group, directory, icons))
        self.assertTrue(result.failed, result.report())
        self.assertIn("does not carry", result.report())

    def test_a_group_directory_that_is_not_one_fails(self) -> None:
        result = self.run_check(lambda path: (101, b"not a directory", {}))
        self.assertTrue(result.failed, result.report())

    def test_the_committed_icon_and_the_linked_form_are_not_byte_identical(self) -> None:
        """Why a whole-file comparison would fail on a correct build.

        This is the premise of the docstring's argument, asserted rather than
        stated: the same images, correctly linked, produce a directory that
        differs from the file's.
        """

        _, directory, _ = self.resources(self.images)
        committed = (REPOSITORY_ROOT / self.COMMITTED).read_bytes()
        self.assertNotEqual(committed[: len(directory)], directory)

    def test_the_lowest_numbered_group_is_the_one_checked(self) -> None:
        """`chrome_exe.rc` declares five icons; Windows shows the application
        the lowest-numbered one, which is `IDR_MAINFRAME`. The reader picks it,
        and the pass row names the group so the choice is visible in the log."""

        result = self.run_check(lambda path: self.resources(self.images, group=101))
        self.assertIn("group 101", result.report())


class IconDirectoryParserTests(unittest.TestCase):
    """The two layouts, parsed by one walk. Neither parser interprets an image."""

    def test_the_committed_icon_declares_the_four_upstream_sizes(self) -> None:
        images = built.ico_images(
            (REPOSITORY_ROOT / IconResourceCheckTests.COMMITTED).read_bytes()
        )
        self.assertEqual([16, 32, 48, 256], sorted(size for size, _ in images))

    def test_a_zero_width_entry_reads_as_256(self) -> None:
        """One byte cannot hold 256, so the format writes 0. The committed
        icon's largest entry is exactly that, and reading it as 0px would make
        every comparison against it wrong in the same direction."""

        payload = b"image"
        data = struct.pack("<HHH", 0, 1, 1) + struct.pack(
            "<BBBBHHII", 0, 0, 0, 0, 1, 32, len(payload), 6 + 16
        ) + payload
        self.assertEqual([(256, payload)], built.ico_images(data))

    def test_a_directory_that_is_not_an_icon_is_rejected(self) -> None:
        with self.assertRaises(built.IconResourceError):
            built.ico_images(struct.pack("<HHH", 0, 2, 1) + bytes(16))

    def test_an_entry_pointing_past_the_end_is_rejected(self) -> None:
        data = struct.pack("<HHH", 0, 1, 1) + struct.pack(
            "<BBBBHHII", 16, 16, 0, 0, 1, 32, 4096, 22
        )
        with self.assertRaises(built.IconResourceError):
            built.ico_images(data)

    def test_an_empty_directory_is_rejected(self) -> None:
        with self.assertRaises(built.IconResourceError):
            built.group_icon_entries(struct.pack("<HHH", 0, 1, 0))

    def test_a_group_entry_yields_a_resource_id_not_an_offset(self) -> None:
        data = struct.pack("<HHH", 0, 1, 1) + struct.pack(
            "<BBBBHHIH", 48, 48, 0, 0, 1, 32, 4026, 7
        )
        self.assertEqual([(48, 7)], built.group_icon_entries(data))


class ResourceNameTests(unittest.TestCase):
    """The overload that cost two builds.

    `EnumResourceNames` hands a name over as `LPWSTR` and overloads it: below
    0x10000 the value *is* the id, above it the value is a pointer to a wide
    string. The first version of the reader kept only the integers, on the
    stated assumption that "this project's icons do not" use string names.

    chrome.exe's icons are exactly that case. `chrome/app/chrome_exe.rc` writes
    `IDR_MAINFRAME ICON "theme\\chromium\\win\\chromium.ico"`, and
    `IDR_MAINFRAME` is defined in none of the three headers that file includes
    -- `chrome_exe_resource.h` carries only Visual Studio's APSTUDIO
    boilerplate. An undefined identifier in a `.rc` file is a string name, so
    every icon in chrome.exe has one, and dropping the strings dropped all of
    them. Build #28 reported a browser with no application icon.

    Both halves are tested here because both can be: reading a wide string at
    an address is not a Windows-only operation.
    """

    def test_a_small_value_is_the_id_itself(self) -> None:
        self.assertEqual(1, built.resource_name(1))
        self.assertEqual(101, built.resource_name(101))
        self.assertEqual(0xFFFF, built.resource_name(0xFFFF))

    def test_a_large_value_is_a_pointer_to_a_name(self) -> None:
        import ctypes

        buffer = ctypes.create_unicode_buffer("IDR_MAINFRAME")
        address = ctypes.addressof(buffer)
        self.assertGreaterEqual(address, 0x10000)
        self.assertEqual("IDR_MAINFRAME", built.resource_name(address))

    def test_the_boundary_belongs_to_the_string_side(self) -> None:
        """0x10000 is the first value Windows treats as a pointer, and the
        integer ids stop one below it."""

        import ctypes

        buffer = ctypes.create_unicode_buffer("X")
        self.assertIsInstance(built.resource_name(ctypes.addressof(buffer)), str)
        self.assertIsInstance(built.resource_name(0xFFFF), int)


class ApplicationIconSelectionTests(unittest.TestCase):
    """Which of several group icons Windows shows for the application.

    `chrome/app/chrome_exe.rc` states the rule it is written to satisfy: the
    application icon "should have the lowest ID, be placed first, and its
    resource name should be alphabetically less than the name of any other icon
    resource". `min()` over integers implemented half of that, and chrome.exe
    is the half it did not implement.
    """

    def test_chrome_exes_own_names_select_the_main_frame(self) -> None:
        """The real set, from chrome_exe.rc at the pinned revision."""

        names = [
            "IDR_X001_APP_LIST",
            "IDR_MAINFRAME",
            "IDR_X003_INCOGNITO",
            "IDR_X006_HTML_DOC",
            "IDR_X007_PDF_DOC",
        ]
        self.assertEqual("IDR_MAINFRAME", built.application_icon_name(names))

    def test_integer_names_still_select_the_lowest(self) -> None:
        self.assertEqual(101, built.application_icon_name([203, 101, 150]))

    def test_an_integer_name_outranks_a_string_one(self) -> None:
        """"Lowest ID" comes first in the rule, so a numbered icon wins over a
        named one however the name sorts."""

        self.assertEqual(101, built.application_icon_name(["AAA_FIRST", 101]))

    def test_a_single_name_is_the_answer(self) -> None:
        self.assertEqual("ONLY", built.application_icon_name(["ONLY"]))


class InvocationTests(unittest.TestCase):
    def test_no_workspace_and_no_argument_is_not_a_pass(self) -> None:
        with mock.patch.dict(built.os.environ, {}, clear=True):
            self.assertIsNone(built.resolve_out(None))

    def test_the_workspace_variable_locates_the_build(self) -> None:
        with mock.patch.dict(built.os.environ, {"SUNSHINE_CHROMIUM_WORKSPACE": "/w"}, clear=True):
            self.assertEqual(Path("/w/src/out/Sunshine"), built.resolve_out(None))

    def test_an_explicit_directory_wins(self) -> None:
        with mock.patch.dict(built.os.environ, {"SUNSHINE_CHROMIUM_WORKSPACE": "/w"}, clear=True):
            self.assertEqual(Path("/other"), built.resolve_out("/other"))


class SwitchListProvenanceTests(unittest.TestCase):
    def test_the_switch_lists_are_shared_with_the_source_guard(self) -> None:
        """Two lists would drift, and the drift would be silent.

        The source guard and this one must reject the same switches, so this
        imports them rather than restating them.
        """

        import verify_chromium_security_invariants as source

        self.assertIs(built.SANDBOX_SWITCHES, source.SANDBOX_SWITCHES)
        self.assertIs(built.ISOLATION_SWITCHES, source.ISOLATION_SWITCHES)


if __name__ == "__main__":
    unittest.main()
