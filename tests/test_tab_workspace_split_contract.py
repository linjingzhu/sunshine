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
        """Both structs carry workspace state, so both must be checked.

        The assertion moved out of the workflow and into
        scripts/verify_pinned_upstream.py, which searches each struct body
        rather than the whole file.
        """

        checker = (ROOT / "scripts" / "verify_pinned_upstream.py").read_text(encoding="utf-8")
        self.assertIn("struct SESSIONS_EXPORT SessionTab {", checker)
        self.assertIn("struct SESSIONS_EXPORT SessionWindow {", checker)

        workflow = (
            ROOT / ".github" / "workflows" / "architecture-guard-self-hosted.yml"
        ).read_text(encoding="utf-8")
        self.assertIn("scripts/verify_pinned_upstream.py", workflow)

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
        ):
            with self.subTest(command=command):
                self.assertIn(f"`{command}`", self.text)

    def test_compile_free_wave_does_not_claim_runtime_delivery(self) -> None:
        self.assertIn("native runtime verification pending", self.text)
        self.assertIn("not a completed browser feature", self.text)

    # The one patch allowed to name a deferred runtime, and the reason it is
    # allowed: it adds an affordance for an upstream action, not a runtime.
    # `docs/decisions/0021-split-swap-affordance.md`.
    SPLIT_AFFORDANCE_PATCH = "0027-sunshine-split-swap-button.patch"

    def test_runtime_patch_series_is_unchanged(self) -> None:
        series = (ROOT / "downstream" / "patches" / "series").read_text(encoding="utf-8")
        for deferred in ("workspace", "tab-group"):
            with self.subTest(deferred=deferred):
                self.assertNotIn(deferred, series.lower())

        # `split` was in that list until patch 0027. Dropping it outright would
        # have retired the rule; what the rule protects is that Sunshine ships
        # no split *runtime*, so the name is allowed for exactly one patch and
        # the property is checked directly below.
        named = [
            line.strip()
            for line in series.splitlines()
            if "split" in line.lower() and line.strip()
        ]
        self.assertEqual([self.SPLIT_AFFORDANCE_PATCH], named)

    def test_the_split_affordance_reaches_upstream_and_writes_nothing(self) -> None:
        """The affordance may call upstream's swap; it may not become a model.

        Invariant 12 says Sunshine writes no split state and contains no split
        model, and section 4.2 retired three commands to avoid "a second code
        path that could drift from the native one". Both survive only if the
        button's single route out is `MultiContentsView::OnSwap()` -- the same
        function the splitter's own double-click calls. Reaching the tab strip
        directly, or storing any of the split's own state, would be the second
        path arriving under a different name.
        """

        patch = (ROOT / "downstream" / "patches" / self.SPLIT_AFFORDANCE_PATCH).read_text(
            encoding="utf-8"
        )
        added = "\n".join(
            line[1:] for line in patch.splitlines()
            if line.startswith("+") and not line.startswith("+++")
        )

        self.assertIn("OnSwap()", added)
        for forbidden in (
            "ReverseTabsInSplit",
            "RemoveSplit",
            "SplitTabVisualData(",
            "split_ratio",
            "SetSplitRatio",
        ):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, added)

    def test_permanently_excluded_vertical_tabs_are_not_in_stage_roadmap(self) -> None:
        roadmap = (
            ROOT / "docs" / "SUNSHINE_OS_STAGE_1_TO_3_IMPLEMENTATION_HANDOFF.md"
        ).read_text(encoding="utf-8").lower()
        self.assertNotIn("vertical tab", roadmap)
        self.assertNotIn("vertical tabs", roadmap)


if __name__ == "__main__":
    unittest.main()
