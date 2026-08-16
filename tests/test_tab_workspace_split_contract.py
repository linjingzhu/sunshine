"""Static gates for the A-grade browser productivity foundation."""

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "docs" / "TAB_WORKSPACE_SPLIT_CONTRACT.md"


class TabWorkspaceSplitContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.text = CONTRACT.read_text(encoding="utf-8")

    def test_native_chromium_ownership_is_explicit(self) -> None:
        for marker in (
            "TabStripModel",
            "TabGroupModel",
            "TabGroupVisualData",
            "Profile",
            "StoragePartition",
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, self.text)

    def test_workspace_does_not_shadow_chromium_session_state(self) -> None:
        self.assertIn("does not keep a shadow", self.text)
        self.assertNotIn('"tab_ids"', self.text)
        self.assertNotIn('"pinned_tab_ids"', self.text)
        self.assertNotIn('"last_active_tab_id"', self.text)

    def test_ci_checks_tab_and_window_extra_data_separately(self) -> None:
        workflow = (
            ROOT / ".github" / "workflows" / "chromium-architecture-check.yml"
        ).read_text(encoding="utf-8")
        self.assertIn("struct SESSIONS_EXPORT SessionTab {", workflow)
        self.assertIn("struct SESSIONS_EXPORT SessionWindow {", workflow)

    def test_data_loss_and_identity_boundaries_are_explicit(self) -> None:
        for marker in (
            "exactly one native owner",
            "never crosses a Chromium profile boundary",
            "Tabs are never silently discarded",
            "cannot be rendered live in both",
            "fail closed",
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, self.text)

    def test_command_first_entry_points_are_defined(self) -> None:
        for command in (
            "tab.group.create",
            "workspace.create",
            "workspace.switch",
            "workspace.tab.move",
            "workspace.close",
            "view.split.open",
            "view.split.swap",
            "view.split.close",
        ):
            with self.subTest(command=command):
                self.assertIn(f"`{command}`", self.text)

    def test_compile_free_wave_does_not_claim_runtime_delivery(self) -> None:
        self.assertIn("native runtime verification pending", self.text)
        self.assertIn("not a completed browser feature", self.text)

    def test_runtime_patch_series_is_unchanged(self) -> None:
        series = (ROOT / "downstream" / "patches" / "series").read_text(encoding="utf-8")
        for deferred in ("workspace", "split", "tab-group"):
            with self.subTest(deferred=deferred):
                self.assertNotIn(deferred, series.lower())

    def test_permanently_excluded_vertical_tabs_are_not_in_stage_roadmap(self) -> None:
        roadmap = (
            ROOT / "docs" / "SUNSHINE_OS_STAGE_1_TO_3_IMPLEMENTATION_HANDOFF.md"
        ).read_text(encoding="utf-8").lower()
        self.assertNotIn("vertical tab", roadmap)
        self.assertNotIn("vertical tabs", roadmap)


if __name__ == "__main__":
    unittest.main()
