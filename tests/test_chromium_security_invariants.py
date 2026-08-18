"""Tests for the Chromium security invariant guard.

Every case here injects the violation rather than asserting the repository is
clean today. A guard that has never rejected anything is indistinguishable from
one whose patterns do not match, which is the failure the security document's
own draft contained: it named a flag, `disable-site-isolation`, that Chromium
does not have.
"""

from pathlib import Path
import shutil
import sys
import tempfile
import unittest

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY_ROOT / "scripts"))

import verify_chromium_security_invariants as guard  # noqa: E402


class SecurityInvariantTests(unittest.TestCase):
    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory()
        self.root = Path(self.directory.name)
        (self.root / "scripts").mkdir(parents=True)
        (self.root / "downstream/patches").mkdir(parents=True)
        self.addCleanup(self.directory.cleanup)

    def write(self, relative: str, text: str) -> None:
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    def failures(self) -> list[str]:
        return guard.validate(self.root)

    # --- SEC-1: the sandbox -------------------------------------------------

    def test_a_build_argument_disabling_the_sandbox_is_rejected(self) -> None:
        self.write("scripts/build.ps1", '$args = @("--no-sandbox")')
        self.assertTrue(any("no-sandbox" in failure for failure in self.failures()))

    def test_every_sandbox_switch_upstream_defines_is_rejected(self) -> None:
        for switch in guard.SANDBOX_SWITCHES:
            with self.subTest(switch=switch):
                self.write("scripts/build.ps1", f"launch --{switch}")
                self.assertTrue(
                    any(switch in failure for failure in self.failures()),
                    f"{switch} is listed but not caught",
                )

    def test_the_windows_dll_blocking_switch_is_covered(self) -> None:
        """`allow-third-party-modules` readmits DLLs Chromium blocks, and the
        runner's platform is the one where it applies."""

        self.write("config/launch.json", '{"flags": ["allow-third-party-modules"]}')
        self.assertTrue(any("allow-third-party-modules" in f for f in self.failures()))

    # --- SEC-2: site isolation ---------------------------------------------

    def test_disabling_site_isolation_trials_is_rejected(self) -> None:
        self.write("config/flags.txt", "--disable-site-isolation-trials")
        self.assertTrue(any("SEC-2" in failure for failure in self.failures()))

    def test_single_process_is_rejected(self) -> None:
        """The most complete removal of the boundary: renderer inside browser."""

        self.write("first_party/launch.json", '{"argv": ["--single-process"]}')
        self.assertTrue(any("single-process" in failure for failure in self.failures()))

    def test_enabling_switches_are_not_rejected(self) -> None:
        """`site-per-process` and `isolate-origins` strengthen isolation.

        A substring match would fire on the fix as well as the defect, and the
        result is a guard someone deletes the first time it blocks correct work.
        """

        self.write("config/flags.txt", "--site-per-process --isolate-origins=https://example.com")
        self.assertEqual([], self.failures())

    # --- Boundaries of the match -------------------------------------------

    def test_a_longer_switch_does_not_trigger_a_shorter_one(self) -> None:
        self.write("config/flags.txt", "--service-sandbox-type=renderer")
        self.assertEqual([], self.failures())

    def test_a_guard_naming_the_switch_is_not_itself_a_violation(self) -> None:
        self.write("scripts/verify_something.py", 'FORBIDDEN = ("--no-sandbox",)')
        self.write("scripts/test_something.py", 'self.assertRejected("--no-sandbox")')
        self.assertEqual([], self.failures())

    def test_upstream_context_in_a_patch_is_not_a_violation(self) -> None:
        """A patch is mostly upstream. Only the added lines are Sunshine's."""

        self.write("downstream/patches/0001-x.patch", "\n".join([
            "--- a/chrome/browser/thing.cc",
            "+++ b/chrome/browser/thing.cc",
            "@@ -1,3 +1,4 @@",
            " const char kNoSandbox[] = \"no-sandbox\";",
            "+// Sunshine comment",
        ]))
        self.assertEqual([], self.failures())

    def test_an_added_patch_line_disabling_the_sandbox_is_rejected(self) -> None:
        self.write("downstream/patches/0001-x.patch", "\n".join([
            "--- a/chrome/browser/thing.cc",
            "+++ b/chrome/browser/thing.cc",
            "@@ -1,3 +1,4 @@",
            "+  command_line->AppendSwitch(\"no-sandbox\");",
        ]))
        self.assertTrue(any("no-sandbox" in failure for failure in self.failures()))

    # --- Protected upstream areas ------------------------------------------

    def test_a_patch_touching_the_sandbox_tree_is_rejected(self) -> None:
        self.write("downstream/patches/0001-x.patch", "\n".join([
            "--- a/sandbox/policy/switches.cc",
            "+++ b/sandbox/policy/switches.cc",
            "@@ -1,2 +1,2 @@",
            "+// harmless looking",
        ]))
        self.assertTrue(any("sandbox/policy" in failure for failure in self.failures()))

    def test_a_patch_touching_site_isolation_policy_is_rejected(self) -> None:
        self.write("downstream/patches/0001-x.patch", "\n".join([
            "--- a/content/public/browser/site_isolation_policy.h",
            "+++ b/content/public/browser/site_isolation_policy.h",
            "@@ -1,2 +1,2 @@",
            "+// harmless looking",
        ]))
        self.assertTrue(any("site_isolation_policy" in failure for failure in self.failures()))

    def test_an_ordinary_patch_is_accepted(self) -> None:
        self.write("downstream/patches/0001-x.patch", "\n".join([
            "--- a/chrome/browser/resources/new_tab_page/app.css",
            "+++ b/chrome/browser/resources/new_tab_page/app.css",
            "@@ -1,2 +1,3 @@",
            "+#sunshineWordmark { color: red; }",
        ]))
        self.assertEqual([], self.failures())


class RepositoryIsCleanTests(unittest.TestCase):
    def test_the_repository_passes_today(self) -> None:
        self.assertEqual([], guard.validate(REPOSITORY_ROOT))


class SwitchProvenanceTests(unittest.TestCase):
    """The lists must stay traceable to upstream, not to memory."""

    def test_the_guard_cites_the_upstream_files_the_switches_came_from(self) -> None:
        source = (REPOSITORY_ROOT / "scripts/verify_chromium_security_invariants.py").read_text(
            encoding="utf-8"
        )
        self.assertIn("sandbox/policy/switches.cc", source)
        self.assertIn("content/public/common/content_switches.cc", source)

    def test_no_enabling_switch_is_in_a_prohibition_list(self) -> None:
        prohibited = set(guard.SANDBOX_SWITCHES) | set(guard.ISOLATION_SWITCHES)
        for enabling in ("site-per-process", "isolate-origins", "service-sandbox-type"):
            with self.subTest(switch=enabling):
                self.assertNotIn(enabling, prohibited)


if __name__ == "__main__":
    unittest.main()
