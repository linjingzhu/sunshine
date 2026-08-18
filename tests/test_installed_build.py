"""Tests for the built-browser check.

This is the first check that reads the build output, so its failure modes are
different from every other guard's: it can be pointed at nothing, at a build
made with the wrong configuration, or run on a platform where half of it cannot
execute. Each of those must be distinguishable from a pass.
"""

from pathlib import Path
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
