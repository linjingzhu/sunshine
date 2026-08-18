"""Tests for the first-party surface checks.

All four criteria are non-interposition checks: they fail when Sunshine has
built something Chromium already owns. That is this project's characteristic
failure mode -- a split-view model duplicating `SplitTabCollection` shipped
because nobody looked -- so each check is proved by injecting the duplication
it is meant to catch.
"""

from pathlib import Path
import json
import shutil
import sys
import tempfile
import unittest
from unittest import mock

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY_ROOT / "scripts"))

import verify_first_party_surfaces as checker  # noqa: E402


class FirstPartySurfaceTests(unittest.TestCase):
    def setUp(self) -> None:
        directory = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, directory, True)
        self.root = Path(directory) / "repo"
        shutil.copytree(
            REPOSITORY_ROOT,
            self.root,
            ignore=shutil.ignore_patterns(".git", "__pycache__", "chromium"),
        )

    def failures(self):
        return checker.validate(self.root, offline=True)

    def assertRejected(self, needle: str) -> None:
        failures = self.failures()
        self.assertTrue(failures, "the violation was accepted")
        self.assertTrue(any(needle in f for f in failures), f"{needle!r} not in {failures}")

    def test_the_repository_passes_today(self) -> None:
        self.assertEqual([], self.failures())

    def test_registering_a_chromium_owned_panel_is_rejected(self) -> None:
        """SIDE_PANEL SPA-9. Chromium ships bookmarks and history panels with
        their own coordinators; a parallel Sunshine entry makes the
        extension-registered panels invisible or misplaced."""

        manifest = self.root / "first_party/modules/sunshine-workspace/module.json"
        data = json.loads(manifest.read_text(encoding="utf-8"))
        data["entrypoints"].append({"type": "chromium_webui_overlay", "target": "bookmarks-panel"})
        manifest.write_text(json.dumps(data, indent=2), encoding="utf-8")
        self.assertRejected("side panel that Chromium already provides")

    def test_a_predicate_without_declared_reasons_is_rejected(self) -> None:
        """COMMAND_PALETTE CPA-9. A disabled row that cannot say why is the
        requirement unmet, not a cosmetic gap."""

        path = self.root / "first_party/commands.json"
        registry = json.loads(path.read_text(encoding="utf-8"))
        for command in registry["commands"]:
            if command["predicate"]:
                command["unavailable_reasons"] = []
                break
        path.write_text(json.dumps(registry, indent=2), encoding="utf-8")
        self.assertRejected("declares no unavailable reason")

    def test_losing_the_last_active_tab_owner_is_rejected(self) -> None:
        """TAB_LIFECYCLE §15. `workspace.switch` is specified to restore a
        workspace's last active tab; for a long time nothing stored one, and the
        behaviour read as done. This fails if that owner disappears again."""

        model = self.root / "scripts/workspace_model.py"
        model.write_text(
            model.read_text(encoding="utf-8").replace("class WindowWorkspaceState", "class Removed", 1),
            encoding="utf-8",
        )
        self.assertRejected("WindowWorkspaceState")

    def test_a_host_colliding_with_upstream_is_rejected(self) -> None:
        """SECURITY_CENTER SCA-13, collision half. Sunshine's surfaces live under
        Chromium's internal scheme, so a host is only Sunshine's while upstream
        does not take it -- and upstream adds hosts every roll."""

        failures: list[str] = []
        with mock.patch.object(checker, "upstream_hosts", return_value={"sunshine-security", "settings"}), \
             mock.patch.object(checker, "sunshine_hosts", return_value={"sunshine-security"}):
            checker.check_host_collisions(self.root, failures, "152.0.7977.42")
        self.assertTrue(any("collides with an upstream internal host" in f for f in failures), failures)

    def test_a_free_host_is_accepted(self) -> None:
        """The check must not fire on the ordinary case, or it gets deleted."""

        failures: list[str] = []
        with mock.patch.object(checker, "upstream_hosts", return_value={"settings", "history"}), \
             mock.patch.object(checker, "sunshine_hosts", return_value={"sunshine-security"}):
            checker.check_host_collisions(self.root, failures, "152.0.7977.42")
        self.assertEqual([], failures)

    def test_the_upstream_host_pattern_reads_real_declarations(self) -> None:
        """A regex that silently stops matching turns this into a no-op that
        always passes, which is worse than not having it."""

        sample = 'inline constexpr char kChromeUISettingsHost[] = "settings";\n'
        self.assertEqual({"settings"}, set(checker.HOST_CONSTANT.findall(sample)))

    def test_the_claimed_hosts_come_from_the_contracts(self) -> None:
        found = checker.sunshine_hosts(REPOSITORY_ROOT)
        self.assertIn("sunshine-security", found)


if __name__ == "__main__":
    unittest.main()
