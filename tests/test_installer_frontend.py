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

    def test_a_switch_named_silent_is_no_longer_what_the_rule_looks_for(self) -> None:
        """And that is the point, not a regression.

        The vocabulary rule this replaces would have caught `--silent` and did
        not catch `--sunshine-elevated`, which was an actual unattended install
        path sitting in the same table it scanned. A rule that matches spellings
        catches the careless and misses the real thing. IU-15 is now a property
        -- two call sites into the engine, one window -- and the tests below are
        what hold it."""

        self.rewrite(
            "installer/sunshine_setup.cpp",
            '{L"--make-default", &Choices::make_default, true},',
            '{L"--silent", &Choices::make_default, true},',
        )
        # A switch that only sets a preference installs nothing on its own.
        self.assertEqual([], self.failures())

    def test_a_third_route_into_the_engine_is_rejected(self) -> None:
        """The shape a silent mode actually takes: another call site that does
        not pass through the dialog."""

        self.rewrite(
            "installer/sunshine_setup.cpp",
            "  INITCOMMONCONTROLSEX controls",
            "  if (choices.make_default) { RunEngine(choices, false); }\n  INITCOMMONCONTROLSEX controls",
        )
        self.assertFailsWith("IU-15")

    def test_removing_the_dialog_is_rejected(self) -> None:
        self.rewrite("installer/sunshine_setup.cpp", "::DialogBoxParamW(", "::NoDialog(")
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
    """IU-4 was reversed by the owner; IU-5 was not.

    This used to be one check for two invariants -- no edit control anywhere,
    because a typed install path and a typed product name each need one. The
    install path is now typed, so the blanket rule stopped expressing the
    invariant that survived. What replaces it is a count and an identity, and
    these are the cases that matter.
    """

    def test_a_second_text_box_is_rejected(self) -> None:
        """Enforces: IU-5.

        The next field somebody adds has to come through this check rather than
        past it -- an executable-name box above all, which
        `docs/INSTALLER_CHOICE_PLAN.md` section 4 prices and nobody has paid
        for.
        """

        self.rewrite(
            "installer/sunshine_setup.rc",
            'LTEXT           "", IDC_LOCATION_NOTE, 28, 136, 296, 10',
            'EDITTEXT        IDC_EXE_NAME, 28, 136, 296, 13, ES_AUTOHSCROLL',
        )
        self.assertFailsWith("exactly one is")

    def test_the_one_box_must_be_the_install_root(self) -> None:
        """Enforces: IU-4, IU-5. One box is permitted; not any one box."""

        self.rewrite(
            "installer/sunshine_setup.rc", "EDITTEXT        IDC_LOCATION_EDIT",
            "EDITTEXT        IDC_PRODUCT_NAME")
        self.assertFailsWith("IDC_LOCATION_EDIT")

    def test_an_edit_control_declared_the_other_way_is_rejected(self) -> None:
        """Enforces: IU-5.

        `CONTROL ... "Edit"` is the same control by another spelling, and a
        check that only reads EDITTEXT would not see it.
        """

        self.rewrite(
            "installer/sunshine_setup.rc",
            'LTEXT           "", IDC_LOCATION_NOTE, 28, 136, 296, 10',
            'CONTROL         "", IDC_EXE_NAME, "Edit", ES_AUTOHSCROLL, 28, 136, 296, 13')
        self.assertFailsWith("Edit")


class InstallRootTests(GuardTestCase):
    """The warning that replaces upstream's %ProgramFiles% guarantee.

    `docs/INSTALLER_CHOICE_PLAN.md` section 3 is exact about the one way to get
    this wrong -- "a writability test performed before elevating tests the
    wrong token" -- so what is checked is where the test is reached from, not
    that a warning exists somewhere.
    """

    def test_removing_the_writability_test_is_rejected(self) -> None:
        """Enforces: IU-4."""

        path = self.root / "installer/sunshine_setup.cpp"
        text = path.read_text(encoding="utf-8")
        call = text.index("if (!choices.install_root.empty() && UsersCanWrite(")
        end = text.index("\n    }\n", call) + len("\n    }\n")
        text = text[:call] + text[end:]
        start = text.index("bool UsersCanWrite(")
        text = text[:start] + text[text.index("\n}\n", start) + 3:]
        path.write_text(text, encoding="utf-8")
        self.assertFailsWith("puts nothing in its place")

    def test_warning_before_elevation_is_rejected(self) -> None:
        """Enforces: IU-4.

        The defect the rule exists for: the check moved into the dialog, where
        it runs unelevated and passes on exactly the folders it is there to
        catch.
        """

        self.rewrite(
            "installer/sunshine_setup.cpp",
            "if (!choices.install_root.empty() && UsersCanWrite(choices.install_root)) {",
            "if (false) {")
        self.assertFailsWith("wrong token")


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


class StaticRuntimeTests(unittest.TestCase):
    """Enforces: IU-17.

    Build #55 produced a `sunshine-setup.exe` that did nothing when it was
    double-clicked. Not a dialog, not an error, nothing -- because the loader
    failed before `wWinMain`, and every failure this program knows how to
    report is reported from inside `wWinMain`.

    The cause was one absent token. `cl.exe` defaults to `/MD`, so the binary
    needed the Visual C++ runtime DLLs; the build machine had them and the
    machine it was carried to did not.
    """

    def setUp(self) -> None:
        self.build = (REPOSITORY_ROOT / "scripts/build_installer_frontend.ps1").read_text(
            encoding="utf-8")

    def compile_line(self) -> str:
        """The cl.exe invocation alone.

        Read from `cl.exe` to the end of its backtick continuations, because
        the prose above it names `/MD` on purpose -- the comment explaining why
        /MT is there has to be able to say what /MT is not.
        """

        after = self.build.split("& cl.exe", 1)[1]
        lines: list[str] = []
        for line in after.splitlines():
            lines.append(line)
            if not line.rstrip().endswith("`"):
                break
        return "\n".join(lines)

    def test_the_compile_line_asks_for_the_static_runtime(self) -> None:
        line = self.compile_line()
        self.assertIn("/MT", line)
        self.assertNotIn("/MD", line)

    def test_the_guard_refuses_the_line_that_shipped_build_55(self) -> None:
        without = self.build.replace("/O2 /GL /MT /guard:cf", "/O2 /GL /guard:cf", 1)
        self.assertNotIn("/MT", without.split("cl.exe")[1].split("`")[0])
        failures: list[str] = []
        # The guard reads the file, so give it one that carries the defect.
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for relative in (guard.SOURCE, guard.RESOURCE, guard.MANIFEST,
                             guard.BUILD, guard.CONTRACT):
                target = root / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                text = (REPOSITORY_ROOT / relative).read_text(encoding="utf-8")
                if relative == guard.BUILD:
                    text = without
                target.write_text(text, encoding="utf-8")
            failures = guard.check(root)
        self.assertTrue(any("/MT" in f for f in failures), failures)
        self.assertTrue(any("before wWinMain" in f for f in failures), failures)

    def test_a_double_click_reaches_the_dialog_or_a_message_box(self) -> None:
        """Why silence located the fault outside the program.

        A double-click passes no arguments, so `elevated_continuation` is
        false and the only failure that can precede the dialog is a command
        line this program does not recognise -- which it reports. Every quiet
        exit lives inside the elevated branch, behind a switch a double-click
        cannot supply. So a run that shows nothing at all never reached
        `wWinMain`, which is what made the loader the place to look.
        """

        source = (REPOSITORY_ROOT / "installer/sunshine_setup.cpp").read_text(
            encoding="utf-8")
        body = source[source.index("int WINAPI wWinMain"):]
        before_dialog, _, _ = body.partition("if (elevated_continuation)")
        # The one pre-dialog failure, and it speaks.
        self.assertIn("ParseCommandLine", before_dialog)
        self.assertIn("MessageBoxW", before_dialog)
        self.assertNotIn("return kExitRefusedElevation", before_dialog)

        quiet_branch, _, after = body.partition("INITCOMMONCONTROLSEX")
        self.assertIn("return kExitRefusedElevation", quiet_branch)
        # And the dialog path reports the one thing that can go wrong with it.
        self.assertIn("could not open its installer window", after)
