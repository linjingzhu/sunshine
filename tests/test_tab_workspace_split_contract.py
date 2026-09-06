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

    # A patch may name a deferred runtime only if it does not implement one.
    # Each entry is the word, the single patch allowed to carry it, and the
    # property that makes it an exception rather than a breach -- what its
    # added lines must contain, and what they must not. The forbidden lists are
    # the names a real implementation of that runtime could not avoid.
    #
    # `workspace` has no exception: nothing implements or borders it yet.
    DEFERRED_RUNTIMES = {
        # docs/decisions/0021-split-swap-affordance.md: an affordance for an
        # upstream action. Its one route out must stay MultiContentsView::OnSwap().
        "split": (
            "0027-sunshine-split-swap-button.patch",
            ("OnSwap()",),
            ("ReverseTabsInSplit", "RemoveSplit", "SplitTabVisualData(",
             "split_ratio", "SetSplitRatio"),
        ),
        # docs/decisions/0022-no-tab-groups-on-the-bookmark-bar.md: a registered
        # default moves from true to false. Touching the tab group model, the
        # saved-tab-group views, or that feature's own prefs would be a runtime.
        "tab-group": (
            "0028-sunshine-no-tab-groups-on-bookmark-bar.patch",
            ("kShowTabGroupsInBookmarkBar",),
            ("SavedTabGroupBar", "SavedTabGroupUtils", "TabGroupModel",
             "TabGroupId", "tab_groups::prefs"),
        ),
    }

    def test_runtime_patch_series_is_unchanged(self) -> None:
        series = (ROOT / "downstream" / "patches" / "series").read_text(encoding="utf-8")
        self.assertNotIn("workspace", series.lower())

        # `split` and `tab-group` were in that list too. Dropping either
        # outright would have retired the rule; what the rule protects is that
        # Sunshine ships no runtime for them, so each name is allowed for
        # exactly one patch and the property is checked directly below.
        for word, (allowed, _, _) in self.DEFERRED_RUNTIMES.items():
            with self.subTest(deferred=word):
                named = [
                    line.strip()
                    for line in series.splitlines()
                    if word in line.lower() and line.strip()
                ]
                self.assertEqual([allowed], named)

    def test_each_deferred_runtime_exception_stays_an_exception(self) -> None:
        """A patch allowed to name a deferred runtime may not implement one.

        This is the half of the rule that survives the exceptions. Without it
        the allow-list above is a hole: any future patch could take the
        permitted name and bring a model in behind it.
        """

        for word, (allowed, required, forbidden) in self.DEFERRED_RUNTIMES.items():
            patch = (ROOT / "downstream" / "patches" / allowed).read_text(encoding="utf-8")
            added = "\n".join(
                line[1:] for line in patch.splitlines()
                if line.startswith("+") and not line.startswith("+++")
            )
            for marker in required:
                with self.subTest(deferred=word, required=marker):
                    self.assertIn(marker, added)
            for marker in forbidden:
                with self.subTest(deferred=word, forbidden=marker):
                    self.assertNotIn(marker, added)

    def test_permanently_excluded_vertical_tabs_are_not_in_stage_roadmap(self) -> None:
        roadmap = (
            ROOT / "docs" / "SUNSHINE_OS_STAGE_1_TO_3_IMPLEMENTATION_HANDOFF.md"
        ).read_text(encoding="utf-8").lower()
        self.assertNotIn("vertical tab", roadmap)
        self.assertNotIn("vertical tabs", roadmap)


if __name__ == "__main__":
    unittest.main()
