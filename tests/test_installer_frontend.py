"""Tests for the installer front-end guard.

The front-end cannot be built or run here, so these tests are the only place
its rules are ever exercised. Each breaks the source and asserts the guard
notices; a guard for a program nobody in CI can execute is worth exactly what
its failures are worth.
"""

from pathlib import Path
import re
import shutil
import xml.dom.minidom
import sys
import tempfile
import unittest

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY_ROOT / "scripts"))

import verify_installer_frontend as guard  # noqa: E402

# Every file `guard.check()` reads.
#
# It was written out at each call site, and adding the uninstall launcher's
# three files broke a test about `/MT` -- which then reported "missing" for
# files the test was not about. One list, so the next file added to the guard
# does not fail a test that has nothing to do with it.
GUARD_INPUTS = (
    guard.SOURCE, guard.RESOURCE, guard.MANIFEST, guard.BUILD, guard.CONTRACT,
    guard.UNINSTALL_SOURCE, guard.UNINSTALL_RESOURCE, guard.UNINSTALL_MANIFEST,
)


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
    """IU-19: the dialog is the system's, so nothing here paints.

    **These tests used to assert the opposite** -- that an owner-drawn control
    draws itself, that the banner is decoded from memory, that a hand-painted
    control draws its own focus rectangle. Each was a rule about doing custom
    painting correctly. The owner asked for the system's dialog, so the rules
    became "do not paint", which forbids by construction every defect the old
    ones caught and needs no `WM_DRAWITEM` to be correct.
    """

    def test_an_owner_drawn_control_is_rejected(self) -> None:
        self.rewrite(
            "installer/sunshine_setup.rc",
            'PUSHBUTTON      "Browse...", IDC_BROWSE, 270, 65, 54, 16',
            'CONTROL "Browse...", IDC_BROWSE, "Button", BS_OWNERDRAW | WS_TABSTOP, 270, 65, 54, 16',
        )
        self.assertFailsWith("IU-19")

    def test_a_draw_handler_coming_back_is_rejected(self) -> None:
        self.rewrite("installer/sunshine_setup.cpp", "case kEngineFinished: {",
                     "case WM_DRAWITEM: case kEngineFinished: {")
        self.assertFailsWith("painted by hand")

    def test_stripping_a_control_theme_is_rejected(self) -> None:
        """The violation the old palette needed, now that its reason is gone.

        Six checkboxes had `SetWindowTheme(c, L"", L"")` applied so a hand-mixed
        colour would take -- IU-13 asks a dialog not to do exactly that, and it
        was being done to serve the look IU-19 removed.
        """

        self.rewrite("installer/sunshine_setup.cpp",
                     "      RefreshLocation(dialog, state);\n      ShowPage",
                     '      ::SetWindowTheme(dialog, L"", L"");\n'
                     "      RefreshLocation(dialog, state);\n      ShowPage")
        self.assertFailsWith("SetWindowTheme")

    def test_imposing_a_colour_the_system_did_not_choose_is_rejected(self) -> None:
        self.rewrite("installer/sunshine_setup.cpp", "enum Page {",
                     "auto* brush = ::CreateSolidBrush(0);\nenum Page {")
        self.assertFailsWith("IU-19")


class ProgressTests(GuardTestCase):
    """IU-20 and IU-21.

    The window now stays open while the engine runs, which is the whole reason
    the progress page exists -- before this the dialog closed and the person
    watched an empty desktop for however long `mini_installer.exe` took.

    **IU-21 guards against a plausible change rather than a careless one.**
    Replacing a marquee with a filling bar looks like an improvement. It is not
    available: nothing tells this program how far the install has got, so any
    position it sets is a number it made up.
    """

    def test_a_bar_that_claims_to_know_its_position_is_rejected(self) -> None:
        self.rewrite("installer/sunshine_setup.rc", "PBS_MARQUEE | WS_BORDER", "WS_BORDER")
        self.assertFailsWith("IU-21")

    def test_setting_a_position_is_rejected(self) -> None:
        self.rewrite("installer/sunshine_setup.cpp", "PBM_SETMARQUEE", "PBM_SETPOS")
        self.assertFailsWith("invented")

    def test_running_the_engine_on_the_ui_thread_is_rejected(self) -> None:
        """A progress bar that cannot animate reads as a hang."""

        self.rewrite("installer/sunshine_setup.cpp", "::CreateThread(", "::RunHere(")
        self.assertFailsWith("freezes")

    def test_forgetting_the_progress_class_is_rejected(self) -> None:
        """Without ICC_PROGRESS_CLASS the control fails to create and
        DialogBoxParamW returns -1 -- a window that never opens, which is the
        failure mode two builds of this program have already shipped."""

        self.rewrite("installer/sunshine_setup.cpp",
                     "ICC_STANDARD_CLASSES | ICC_PROGRESS_CLASS", "ICC_STANDARD_CLASSES")
        self.assertFailsWith("never opens")


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
        """IU-6 outlived the image it was written for.

        There is no banner any more, so nothing in this program has a reason to
        open one -- which makes the rule cheaper to keep than to retire, and
        keeps the next person who wants a logo from reaching for a file path.
        """

        self.rewrite("installer/sunshine_setup.cpp", "enum Page {",
                     "void* p = LoadImageW(0,0,0,0,0,0);\nenum Page {")
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
            'LTEXT           "", IDC_LOCATION_NOTE, 28, 85, 296, 10',
            'EDITTEXT        IDC_EXE_NAME, 28, 85, 296, 13, ES_AUTOHSCROLL',
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
            'LTEXT           "", IDC_LOCATION_NOTE, 28, 85, 296, 10',
            'CONTROL         "", IDC_EXE_NAME, "Edit", ES_AUTOHSCROLL, 28, 85, 296, 13')
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
    def test_a_second_registry_read_is_rejected(self) -> None:
        """IU-16 permits one since IU-19. A second is inventory of a machine
        the installer has not been given permission to change.

        It permitted two until the dialog stopped drawing itself: the second
        was `AppsUseLightTheme`, and Windows now decides light or dark.
        """

        self.rewrite(
            "installer/sunshine_setup.cpp",
            "  return std::wstring();\n}\n\n// ----",
            "  ::RegOpenKeyExW(HKEY_LOCAL_MACHINE, L\"x\", 0, 0, nullptr);\n"
            "  return std::wstring();\n}\n\n// ----",
        )
        self.assertFailsWith("IU-16 permits exactly one")

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
            for relative in GUARD_INPUTS:
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
        """No quiet exit can explain a silent double-click.

        A double-click passes no arguments, so `elevated_continuation` is
        false and the only failure that can precede the dialog is a command
        line this program does not recognise -- which it reports. Every quiet
        `return` lives inside the elevated branch, behind a switch a
        double-click cannot supply.

        That much is what this test checks, and it holds. The inference drawn
        from it did not: it was read as "so the program never reached
        wWinMain", and the loader was blamed. Build #56's exit code was
        0xC00000FD -- STATUS_STACK_OVERFLOW -- which says the program ran and
        then recursed to death in RefreshLocation. This rules out a quiet
        return. It never ruled out a crash.
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


class RefreshLocationDoesNotCallItself(unittest.TestCase):
    """The defect that made build #56 do nothing when double-clicked.

    `SetDlgItemTextW` on an edit control makes it notify its parent with
    EN_CHANGE, and the dialog's EN_CHANGE handler is `RefreshLocation`, which
    writes that same control on the per-user branch. `WM_INITDIALOG` seeds the
    dialog per-user, so the recursion started before the window existed and the
    process died of STATUS_STACK_OVERFLOW inside `DialogBoxParamW`.
    """

    def setUp(self) -> None:
        self.source = (REPOSITORY_ROOT / "installer/sunshine_setup.cpp").read_text(
            encoding="utf-8")

    def body(self) -> str:
        found = guard._function_body(self.source, "RefreshLocation")
        assert found is not None
        return found

    def test_the_handler_holds_a_flag_across_the_nested_call(self) -> None:
        body = self.body()
        self.assertIn("if (state->refreshing_location) {", body)
        self.assertIn("state->refreshing_location = true;", body)
        self.assertIn("state->refreshing_location = false;", body)
        # It has to outlive the call, so it is state and not a local.
        self.assertIn("bool refreshing_location = false;", self.source)

    def test_the_flag_is_released_on_the_way_out(self) -> None:
        """Not merely present -- released after the last write to a control.

        A guard set true and cleared before the writes it protects is a guard
        that is not there, and would read as present to a check that only
        greps.
        """

        body = self.body()
        engaged = body.index("state->refreshing_location = true;")
        released = body.index("state->refreshing_location = false;")
        last_write = body.rindex("SetDlgItemTextW")
        self.assertLess(engaged, last_write)
        self.assertLess(last_write, released)

    def test_init_reaches_the_branch_that_writes_the_box(self) -> None:
        """Why it failed on every launch rather than on some of them.

        WM_INITDIALOG calls RefreshLocation, `Choices::system_level` defaults
        to false, and false is the branch that writes IDC_LOCATION_EDIT. There
        was no sequence of clicks that avoided this.
        """

        self.assertIn("bool system_level = false;", self.source)
        init = self.source[self.source.index("case WM_INITDIALOG"):]
        # The next case in the switch, whatever it is called. It used to be
        # WM_SETTINGCHANGE, which IU-19 removed along with the palette that
        # needed to follow the system theme.
        init = init[:init.index("case kEngineFinished")]
        self.assertIn("RefreshLocation(dialog, state);", init)
        body = self.body()
        per_user = body[body.index("if (!machine) {"):]
        self.assertIn("IDC_LOCATION_EDIT, L\"\"", per_user)

    def test_the_guard_refuses_the_source_that_shipped_build_56(self) -> None:
        without = self.source
        for line in ("  if (state->refreshing_location) {\n    return;\n  }\n"
                     "  state->refreshing_location = true;\n\n",
                     "\n  state->refreshing_location = false;\n"):
            self.assertIn(line, without)
            without = without.replace(line, "", 1)
        self.assertNotIn("refreshing_location = true", without)

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for relative in GUARD_INPUTS:
                target = root / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                text = (REPOSITORY_ROOT / relative).read_text(encoding="utf-8")
                if relative == guard.SOURCE:
                    text = without
                target.write_text(text, encoding="utf-8")
            failures = guard.check(root)
        self.assertTrue(any("re-entrancy guard" in f for f in failures), failures)

    def test_the_guard_refuses_a_flag_that_is_only_a_local(self) -> None:
        """A guard that does not outlive the nested call does nothing."""

        weakened = self.source.replace(
            "  bool refreshing_location = false;\n", "", 1)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for relative in GUARD_INPUTS:
                target = root / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                text = (REPOSITORY_ROOT / relative).read_text(encoding="utf-8")
                if relative == guard.SOURCE:
                    text = weakened
                target.write_text(text, encoding="utf-8")
            failures = guard.check(root)
        self.assertTrue(any("DialogState" in f for f in failures), failures)


class UninstallLauncherTests(unittest.TestCase):
    """UN-1 through UN-5, each by breaking the source.

    The launcher is small enough to be trusted by reading, which is exactly
    why it is not. **UN-3's failure mode is a local privilege escalation**: the
    per-user `UninstallString` lives in `HKEY_CURRENT_USER`, which the
    unprivileged user owns, so a launcher that elevated what it found there
    would run an attacker's command line as administrator — shipped as a
    convenience, with an icon.
    """

    def setUp(self) -> None:
        self.source = guard.code_only(
            (REPOSITORY_ROOT / guard.UNINSTALL_SOURCE).read_text(encoding="utf-8"))
        self.resource = guard.code_only(
            (REPOSITORY_ROOT / guard.UNINSTALL_RESOURCE).read_text(encoding="utf-8"))
        self.manifest = (REPOSITORY_ROOT / guard.UNINSTALL_MANIFEST).read_text(
            encoding="utf-8")
        self.build = (REPOSITORY_ROOT / guard.BUILD).read_text(encoding="utf-8")

    def check(self, *, source=None, resource=None, manifest=None, build=None):
        return guard.check_uninstall_launcher(
            self.source if source is None else source,
            self.resource if resource is None else resource,
            self.manifest if manifest is None else manifest,
            self.build if build is None else build)

    def test_the_launcher_as_written_passes(self) -> None:
        self.assertEqual([], self.check())

    def test_elevating_every_command_is_refused(self) -> None:
        """The escalation itself: `runas` with no conditional."""

        broken = self.source.replace(
            'installation.machine ? L"runas" : L"open"', 'L"runas"')
        self.assertNotEqual(broken, self.source)
        failures = self.check(source=broken)
        self.assertTrue(any("privilege escalation" in f for f in failures), failures)

    def test_a_hive_flag_forced_true_is_refused(self) -> None:
        """The same defect one level down, which reading would likely miss.

        The conditional is still there and still mentions both hives; only the
        flag it tests has stopped depending on which hive answered. A check
        that looked for the word `runas` beside the word `HKEY_LOCAL_MACHINE`
        would pass this.
        """

        broken = self.source.replace("found.machine = hive.second;",
                                     "found.machine = true;")
        self.assertNotEqual(broken, self.source)
        failures = self.check(source=broken)
        self.assertTrue(any("bare `true`" in f for f in failures), failures)

    def test_requiring_administrator_in_the_manifest_is_refused(self) -> None:
        broken = self.manifest.replace('level="asInvoker"',
                                       'level="requireAdministrator"')
        failures = self.check(manifest=broken)
        self.assertTrue(any("asInvoker" in f for f in failures), failures)

    def test_writing_the_registry_is_refused(self) -> None:
        broken = self.source.replace("::RegOpenKeyExW(hive.first",
                                     "::RegSetValueExW(hive.first")
        failures = self.check(source=broken)
        self.assertTrue(any("permits reads only" in f for f in failures), failures)

    def test_reading_a_value_the_contract_does_not_name_is_refused(self) -> None:
        broken = self.source.replace('L"DisplayVersion"', 'L"InstallLocation"')
        failures = self.check(source=broken)
        self.assertTrue(any("InstallLocation" in f for f in failures), failures)

    def test_a_dialog_of_its_own_is_refused(self) -> None:
        """UN-1. The browser already draws one, and it is the better one."""

        failures = self.check(
            resource=self.resource + "\nIDD_CONFIRM DIALOGEX 0, 0, 200, 100\n")
        self.assertTrue(any("asks the same question worse" in f for f in failures),
                        failures)

    def test_taking_the_profile_decision_from_the_browser_is_refused(self) -> None:
        broken = self.source.replace(
            "kExitCouldNotRun = 0xB3",
            'kExitCouldNotRun = 0xB3;\nconstexpr wchar_t kD[] = L"--delete-profile"')
        failures = self.check(source=broken)
        self.assertTrue(any("delete-profile" in f for f in failures), failures)

    def test_the_launcher_must_be_built_with_the_static_runtime(self) -> None:
        """IU-17 is about the machine a binary runs on.

        An uninstaller runs on machines that never had a compiler, and a loader
        failure there shows the user nothing at all — which is the whole of
        what happened to build #55.
        """

        line = guard._compile_line(self.build, "sunshine_uninstall.cpp")
        self.assertIn("/MT", line)
        self.assertNotIn("/MD", line)

    def test_a_build_that_stops_producing_it_is_refused(self) -> None:
        broken = self.build.replace("sunshine-uninstall.exe", "something-else.exe")
        failures = self.check(build=broken)
        self.assertTrue(any("nobody builds" in f for f in failures), failures)

    def test_exit_codes_do_not_collide_with_the_setup_front_end(self) -> None:
        """§5 and UN-4: the engine's code passes through, so ours must not
        occupy a value either the engine or the other binary already uses."""

        setup = (REPOSITORY_ROOT / guard.SOURCE).read_text(encoding="utf-8")
        mine = set(re.findall(r"constexpr int kExit\w+ = (0x[0-9A-Fa-f]+);", self.source))
        theirs = set(re.findall(r"constexpr int kExit\w+ = (0x[0-9A-Fa-f]+);", setup))
        self.assertTrue(mine)
        self.assertTrue(theirs)
        self.assertEqual(set(), mine & theirs)
        # And clear of installer::InstallStatus, which starts at 0.
        self.assertTrue(all(int(code, 16) > 0x10 for code in mine))

    def test_the_manifest_is_well_formed_xml(self) -> None:
        """A `--` inside an XML comment is not a comment, and this file had one.

        Build #49 was lost to a `.grd` an XML parser could not read. The same
        mistake in a manifest is a binary the side-by-side loader refuses to
        start, which looks from outside exactly like the two silent installers
        already in this project's history.
        """

        xml.dom.minidom.parseString(self.manifest)

