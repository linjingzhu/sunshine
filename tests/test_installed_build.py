"""Tests for the built-browser check.

This is the first check that reads the build output, so its failure modes are
different from every other guard's: it can be pointed at nothing, at a build
made with the wrong configuration, or run on a platform where half of it cannot
execute. Each of those must be distinguishable from a pass.
"""

from pathlib import Path
import sys
import subprocess
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


class LaunchCheckTests(unittest.TestCase):
    """`chrome.exe --version` is the one check that exercises real process
    startup rather than reading a file or a registry key. These pin the
    failure shapes that all leave every artifact on disk, at a plausible
    size, and still unable to run -- the exact gap between "the build
    succeeded" and "a person can use the browser."
    """

    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory()
        self.out = Path(self.directory.name)
        self.addCleanup(self.directory.cleanup)
        (self.out / "chrome.exe").write_bytes(b"x" * 1024)

    def run_check(self):
        result = built.Result()
        with mock.patch.object(built.sys, "platform", "win32"):
            built.check_chrome_launches(self.out, result)
        return result

    def test_off_windows_is_unavailable_not_a_pass(self) -> None:
        result = built.Result()
        with mock.patch.object(built.sys, "platform", "linux"):
            built.check_chrome_launches(self.out, result)
        self.assertTrue(result.unavailable)
        self.assertFalse(result.failed)

    def test_a_missing_binary_reports_nothing_new(self) -> None:
        """`check_artifacts` already failed on this; a second, identically
        worded failure here would just be noise."""

        (self.out / "chrome.exe").unlink()
        result = self.run_check()
        self.assertEqual([], result.rows)

    def test_a_clean_version_print_passes(self) -> None:
        completed = subprocess.CompletedProcess([], 0, stdout="Sunshine OS 152.0.7977.42\n", stderr="")
        with mock.patch.object(built.subprocess, "run", return_value=completed):
            result = self.run_check()
        self.assertFalse(result.failed)
        self.assertIn(
            (built.PASSED, "chrome.exe launches and reports its version", "Sunshine OS 152.0.7977.42"),
            result.rows,
        )

    def test_a_nonzero_exit_fails(self) -> None:
        completed = subprocess.CompletedProcess([], 1, stdout="", stderr="fatal error\n")
        with mock.patch.object(built.subprocess, "run", return_value=completed):
            result = self.run_check()
        self.assertTrue(result.failed)
        self.assertIn("exit code 1", result.rows[0][2])

    def test_a_hang_fails_rather_than_blocking_forever(self) -> None:
        with mock.patch.object(
            built.subprocess, "run", side_effect=built.subprocess.TimeoutExpired(cmd="chrome.exe", timeout=30)
        ):
            result = self.run_check()
        self.assertTrue(result.failed)
        self.assertIn("30s", result.rows[0][2])

    def test_a_blocked_launch_fails_with_the_os_error(self) -> None:
        """The shape a real-time antivirus quarantine or SmartScreen block
        takes: the file exists, but the OS refuses to start it."""

        with mock.patch.object(built.subprocess, "run", side_effect=OSError(5, "Access is denied")):
            result = self.run_check()
        self.assertTrue(result.failed)
        self.assertIn("could not start", result.rows[0][2])

    def test_exit_zero_with_no_output_is_not_the_version_path(self) -> None:
        completed = subprocess.CompletedProcess([], 0, stdout="", stderr="")
        with mock.patch.object(built.subprocess, "run", return_value=completed):
            result = self.run_check()
        self.assertTrue(result.failed)


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
