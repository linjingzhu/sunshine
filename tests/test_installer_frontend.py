"""Tests for the installer front-end guard.

The front-end cannot be built or run here, so these tests are the only place
its rules are ever exercised. Each breaks the source and asserts the guard
notices; a guard for a program nobody in CI can execute is worth exactly what
its failures are worth.
"""

from pathlib import Path
import shutil
import sys
import tempfile
import unittest

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY_ROOT / "scripts"))

import verify_installer_frontend as guard  # noqa: E402


class GuardTestCase(unittest.TestCase):
    def setUp(self) -> None:
        directory = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, directory, True)
        self.root = Path(directory)
        for relative in ("installer", "scripts", "docs", "downstream/patches"):
            source = REPOSITORY_ROOT / relative
            if source.is_dir():
                shutil.copytree(source, self.root / relative)

    def rewrite(self, relative: str, old: str, new: str) -> None:
        path = self.root / relative
        text = path.read_text(encoding="utf-8")
        self.assertIn(old, text, "the fixture no longer contains the anchor")
        path.write_text(text.replace(old, new, 1), encoding="utf-8")

    def failures(self) -> list[str]:
        return guard.check(self.root)

    def assertFailsWith(self, fragment: str) -> None:
        failures = self.failures()
        self.assertTrue(
            any(fragment in failure for failure in failures),
            f"expected a failure mentioning {fragment!r}, got {failures}",
        )


class CleanTreeTests(GuardTestCase):
    def test_the_repository_passes(self) -> None:
        self.assertEqual([], self.failures())


class CommentTests(GuardTestCase):
    def test_a_comment_saying_there_is_no_silent_mode_is_not_a_silent_mode(self) -> None:
        """Three rules fired on their own explanations the first time this ran.
        The fix was to read code, and this is what keeps it read."""

        self.rewrite(
            "installer/sunshine_setup.cpp",
            "// the contract refuses a silent mode, and IU-15 is that refusal.",
            "// the contract refuses a silent quiet passive unattend mode.",
        )
        self.assertEqual([], self.failures())

    def test_a_real_silent_switch_is_still_caught(self) -> None:
        self.rewrite(
            "installer/sunshine_setup.cpp",
            '{L"--make-default", &Choices::make_default, true},',
            '{L"--silent", &Choices::make_default, true},',
        )
        self.assertFailsWith("IU-15")


class DrawingTests(GuardTestCase):
    def test_owner_drawn_controls_with_no_draw_handler_are_rejected(self) -> None:
        """The defect this rule was written for. BS_OWNERDRAW with no
        WM_DRAWITEM compiles, passes every other rule, and renders blank
        rectangles that only someone running the build would ever see."""

        self.rewrite("installer/sunshine_setup.cpp", "case WM_DRAWITEM: {", "case WM_NULL: {")
        self.assertFailsWith("draw nothing")

    def test_decoding_the_banner_from_anything_but_memory_is_rejected(self) -> None:
        self.rewrite("installer/sunshine_setup.cpp", "InitializeFromMemory", "InitializeFromFilename")
        self.assertFailsWith("IU-6")

    def test_an_owner_drawn_control_without_a_focus_indicator_is_rejected(self) -> None:
        self.rewrite("installer/sunshine_setup.cpp", "::DrawFocusRect(", "::DrawEdge(")
        self.assertFailsWith("IU-14")


class ElevationTests(GuardTestCase):
    def test_an_always_elevating_manifest_is_rejected(self) -> None:
        self.rewrite(
            "installer/sunshine_setup.manifest",
            'level="asInvoker"',
            'level="requireAdministrator"',
        )
        self.assertFailsWith("IU-7")

    def test_staging_the_engine_where_the_user_can_write_is_rejected(self) -> None:
        """The classic shape of this bug, and the one the first version of this
        rule could not see. It sliced the source from `if (elevated_continuation)`
        to end-of-file and grepped the tail for file reads; every function the
        elevated path calls is *defined above* that point, so the rule passed for
        a reason unrelated to the property."""

        self.rewrite(
            "installer/sunshine_setup.cpp",
            "const UINT length = ::GetSystemWindowsDirectoryW(",
            "const UINT length = ::GetTempPathW(",
        )
        self.assertFailsWith("IU-9")

    def test_an_elevated_continuation_that_trusts_the_command_line_is_rejected(self) -> None:
        """Without this, `--sunshine-elevated` is a complete unattended install
        path for anything that can already start a process -- which is what
        IU-15 forbids, while the guard was looking for the word "silent"."""

        # The call site, not the definition: `rewrite` replaces the first
        # occurrence, and the first occurrence of the bare name is `bool
        # RunningElevated() {`.
        self.rewrite("installer/sunshine_setup.cpp",
                     "if (!RunningElevated()", "if (false")
        self.assertFailsWith("IU-15")

    def test_losing_the_closed_switch_table_is_rejected(self) -> None:
        self.rewrite("installer/sunshine_setup.cpp", "kSwitches[]", "kOptions[]")
        self.assertFailsWith("closed switch table")


class EngineTests(GuardTestCase):
    def test_running_the_engine_unhashed_is_rejected(self) -> None:
        self.rewrite("installer/sunshine_setup.cpp", "BCryptHashData", "memcmp")
        self.assertFailsWith("IU-10")

    def test_hashing_the_resource_instead_of_the_written_file_is_rejected(self) -> None:
        """The defect this rule was rewritten for. Hashing the in-memory
        resource proves the build carried what it meant to; it says nothing
        about the bytes on disk when CreateProcessW runs, which is the entire
        window IU-9 and IU-10 exist to close."""

        self.rewrite("installer/sunshine_setup.cpp",
                     "HANDLE verified = OpenVerifiedEngine",
                     "HANDLE verified = (HANDLE)HashMatchesResource")
        self.assertFailsWith("IU-10")

    def test_a_committed_engine_hash_is_rejected(self) -> None:
        """It belongs to one build's engine. Committed, it is a value that will
        one day describe a different file."""

        (self.root / "installer/engine_hash.h").write_text("// stale\n", encoding="utf-8")
        self.assertFailsWith("committed")


class InstallingTests(GuardTestCase):
    def test_writing_the_registry_is_rejected(self) -> None:
        self.rewrite("installer/sunshine_setup.cpp", "::RegCloseKey(key);\n    if (status", "::RegSetValueExW(key,0,0,0,0,0);\n    ::RegCloseKey(key);\n    if (status")
        self.assertFailsWith("IU-2")

    def test_creating_a_shortcut_is_rejected(self) -> None:
        self.rewrite("installer/sunshine_setup.cpp", "struct Outcome {", "struct Outcome { IShellLink* link;")
        self.assertFailsWith("IU-2")

    def test_opening_an_image_at_run_time_is_rejected(self) -> None:
        self.rewrite("installer/sunshine_setup.cpp", "struct Palette {", "struct Palette { void* p = LoadImageW(0,0,0,0,0,0);")
        self.assertFailsWith("IU-6")


class InputTests(GuardTestCase):
    def test_a_text_box_in_the_dialog_is_rejected(self) -> None:
        """One check for two invariants: a typed install path and a typed
        product name each need an edit control, and neither can appear without
        one."""

        self.rewrite(
            "installer/sunshine_setup.rc",
            'LTEXT           "", IDC_LOCATION, 28, 118, 296, 10',
            'EDITTEXT        IDC_LOCATION, 28, 118, 296, 12, ES_AUTOHSCROLL',
        )
        self.assertFailsWith("text box")


class RegistryReadTests(GuardTestCase):
    def test_a_third_registry_read_is_rejected(self) -> None:
        """IU-16 permits two and names both. A third is inventory of a machine
        the installer has not been given permission to change."""

        self.rewrite(
            "installer/sunshine_setup.cpp",
            "  return status == ERROR_SUCCESS && type == REG_DWORD && light == 0;",
            "  ::RegOpenKeyExW(HKEY_LOCAL_MACHINE, L\"x\", 0, 0, &key);\n"
            "  return status == ERROR_SUCCESS && type == REG_DWORD && light == 0;",
        )
        self.assertFailsWith("IU-16 permits exactly two")

    def test_dropping_the_version_read_is_rejected(self) -> None:
        self.rewrite(
            "installer/sunshine_setup.cpp",
            'L"Software\\\\Microsoft\\\\Windows\\\\CurrentVersion\\\\Uninstall\\\\Sunshine";',
            'L"Software\\\\Sunshine";',
        )
        self.assertFailsWith("uninstall registration")


class PreferencesTests(GuardTestCase):
    def test_a_preferences_key_the_contract_does_not_name_is_rejected(self) -> None:
        self.rewrite(
            "installer/sunshine_setup.cpp",
            '\\"do_not_launch_chrome\\"',
            '\\"do_not_register_for_update_launch\\"',
        )
        self.assertFailsWith("IU-3")


class PatchStackTests(GuardTestCase):
    def test_the_front_end_may_not_enter_the_patch_stack(self) -> None:
        """It owns no upstream file and is not part of Chromium's build. A patch
        carrying it would make both untrue."""

        (self.root / "downstream/patches/9999-x.patch").write_text(
            "+++ b/installer/sunshine_setup.cpp\n", encoding="utf-8"
        )
        self.assertFailsWith("IU-1")


if __name__ == "__main__":
    unittest.main()
