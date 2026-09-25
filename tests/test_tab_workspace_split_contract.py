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

    def test_both_structs_extra_data_is_checked_separately(self) -> None:
        """Both structs carry workspace state, so both must be checked.

        The assertion moved out of the workflow and into
        scripts/verify_pinned_upstream.py, which searches each struct body
        rather than the whole file.

        **This test used to also assert that a workflow ran that script, and
        it cannot any more.** The owner disabled GitHub Actions and every
        workflow file was removed on 2026-09-25
        (`.ai/reports/2026-09-25-rules-and-actions-result.md`), so there is no
        CI for a check to be wired into. What is lost is real and is recorded
        here rather than dropped quietly: the separation below is now verified
        only when someone runs `.ai/PROJECT_CONTEXT.md` § *Facts the checks
        read*'s `test_command`. The invariant is unchanged; the assurance that
        it runs unattended is gone.
        """

        checker = (ROOT / "scripts" / "verify_pinned_upstream.py").read_text(encoding="utf-8")
        self.assertIn("struct SESSIONS_EXPORT SessionTab {", checker)
        self.assertIn("struct SESSIONS_EXPORT SessionWindow {", checker)

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
    # Each entry is the word, the patches allowed to carry it, and the property
    # that makes them an exception rather than a breach -- what their added
    # lines must contain, and what they must not. The forbidden lists are the
    # names a real implementation of that runtime could not avoid.
    #
    # `workspace` has no exception: nothing implements or borders it yet.
    DEFERRED_RUNTIMES = {
        # docs/decisions/0021-split-swap-affordance.md,
        # docs/decisions/0028-split-hover-widget.md: affordances for upstream
        # actions.
        #
        # **`RemoveSplit` moved from forbidden to allowed, and that is a
        # decision rather than an accommodation.** It was listed because the
        # swap affordance was meant to have exactly one route out, and a
        # second call would have been a second behaviour appearing without
        # anyone deciding on it. The owner has now asked for two more actions
        # on a split -- open the other half, and separate the halves into
        # ordinary tabs -- so the list is what changed, not the rule. What the
        # rule protects is that Sunshine keeps no split model of its own, and
        # the forbidden names below are still every part of one: the visual
        # data, the ratio, the layout, and reversing the tabs behind
        # `OnSwap()`'s back.
        "split": (
            ("0027-sunshine-split-swap-button.patch",
             "0031-sunshine-split-link-mode.patch",
             "0032-sunshine-split-hover-widget.patch"),
            ("OnSwap()",),
            ("ReverseTabsInSplit", "SplitTabVisualData(", "split_ratio",
             "SetSplitRatio", "UpdateSplitRatio", "UpdateSplitLayout",
             "AddToNewSplit"),
        ),
        # docs/decisions/0022-no-tab-groups-on-the-bookmark-bar.md: a registered
        # default moves from true to false. Touching the tab group model, the
        # saved-tab-group views, or that feature's own prefs would be a runtime.
        "tab-group": (
            ("0028-sunshine-no-tab-groups-on-bookmark-bar.patch",),
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
                self.assertEqual(sorted(allowed), named)

    def test_each_deferred_runtime_exception_stays_an_exception(self) -> None:
        """A patch allowed to name a deferred runtime may not implement one.

        This is the half of the rule that survives the exceptions. Without it
        the allow-list above is a hole: any future patch could take the
        permitted name and bring a model in behind it.
        """

        for word, (allowed, required, forbidden) in self.DEFERRED_RUNTIMES.items():
            texts = {
                name: (ROOT / "downstream" / "patches" / name).read_text(encoding="utf-8")
                for name in allowed
            }
            added = {
                name: "\n".join(
                    line[1:] for line in text.splitlines()
                    if line.startswith("+") and not line.startswith("+++")
                )
                for name, text in texts.items()
            }
            # Required across the set, forbidden in each patch. A marker that
            # says the exception is what it claims to be need only appear once
            # -- `OnSwap()` is the swap's one route out wherever the swap is
            # offered from -- while a marker that would make it a runtime is
            # forbidden wherever it appears.
            for marker in required:
                with self.subTest(deferred=word, required=marker):
                    self.assertTrue(
                        any(marker in body for body in added.values()),
                        f"{marker!r} appears in none of {sorted(allowed)}",
                    )
            for name, body in added.items():
                for marker in forbidden:
                    with self.subTest(deferred=word, patch=name, forbidden=marker):
                        self.assertNotIn(marker, body)

    def test_permanently_excluded_vertical_tabs_are_not_in_stage_roadmap(self) -> None:
        roadmap = (
            ROOT / "docs" / "SUNSHINE_OS_STAGE_1_TO_3_IMPLEMENTATION_HANDOFF.md"
        ).read_text(encoding="utf-8").lower()
        self.assertNotIn("vertical tab", roadmap)
        self.assertNotIn("vertical tabs", roadmap)


if __name__ == "__main__":
    unittest.main()
