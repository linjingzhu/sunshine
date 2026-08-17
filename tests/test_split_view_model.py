"""Fail-closed tests for the compile-free two-pane split-view model."""

from copy import deepcopy
import unittest

from scripts.split_view_model import (
    DEFAULT_RATIO,
    LEADING,
    MAX_RATIO,
    MIN_RATIO,
    ORIENTATION_ROWS,
    SPLIT_SCHEMA_VERSION,
    SPLIT_UNKNOWN_SCHEMA_POLICY,
    TRAILING,
    SplitViewError,
    UnknownSplitSchemaError,
    close_pane,
    focus_pane,
    open_split,
    parse_layout,
    persistable_layout,
    resize_split,
    restore_layout,
    swap_panes,
)
from scripts.workspace_model import DEFAULT_WORKSPACE_ID, NativeTab


ALPHA = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
BETA = "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"
GAMMA = "cccccccc-cccc-4ccc-8ccc-cccccccccccc"
OTHER_WORKSPACE = "33333333-3333-4333-8333-333333333333"


def active_tabs() -> tuple[NativeTab, ...]:
    return (
        NativeTab("runtime-a", ALPHA, DEFAULT_WORKSPACE_ID),
        NativeTab("runtime-b", BETA, DEFAULT_WORKSPACE_ID),
        NativeTab("runtime-c", GAMMA, OTHER_WORKSPACE),
    )


class SplitViewModelTests(unittest.TestCase):
    def test_open_places_two_distinct_active_workspace_tabs(self) -> None:
        layout = open_split(active_tabs(), DEFAULT_WORKSPACE_ID, ALPHA, BETA)
        self.assertEqual((ALPHA, BETA), layout.tab_uuids())
        self.assertEqual(LEADING, layout.focused_pane)
        self.assertEqual(DEFAULT_RATIO, layout.ratio)
        self.assertEqual(SPLIT_SCHEMA_VERSION, layout.schema_version)

    def test_a_tab_can_never_occupy_both_panes(self) -> None:
        with self.assertRaisesRegex(SplitViewError, "both panes"):
            open_split(active_tabs(), DEFAULT_WORKSPACE_ID, ALPHA, ALPHA)
        with self.assertRaisesRegex(SplitViewError, "both panes"):
            parse_layout(
                {
                    "schema_version": 1,
                    "leading_tab_uuid": ALPHA,
                    "trailing_tab_uuid": ALPHA,
                }
            )

    def test_split_cannot_reach_outside_the_active_workspace(self) -> None:
        with self.assertRaisesRegex(SplitViewError, "active workspace"):
            open_split(active_tabs(), DEFAULT_WORKSPACE_ID, ALPHA, GAMMA)

    def test_tabs_without_a_durable_identity_are_not_eligible(self) -> None:
        tabs = (
            NativeTab("runtime-a", ALPHA, DEFAULT_WORKSPACE_ID),
            NativeTab("runtime-b", None, DEFAULT_WORKSPACE_ID),
        )
        with self.assertRaisesRegex(SplitViewError, "active workspace"):
            open_split(tabs, DEFAULT_WORKSPACE_ID, ALPHA, BETA)

    def test_ambiguous_duplicate_identity_is_not_split(self) -> None:
        tabs = (
            NativeTab("runtime-a", ALPHA, DEFAULT_WORKSPACE_ID),
            NativeTab("runtime-b", ALPHA, DEFAULT_WORKSPACE_ID),
            NativeTab("runtime-c", BETA, DEFAULT_WORKSPACE_ID),
        )
        with self.assertRaisesRegex(SplitViewError, "active workspace"):
            open_split(tabs, DEFAULT_WORKSPACE_ID, ALPHA, BETA)

    def test_panes_cannot_mix_regular_and_off_the_record_tabs(self) -> None:
        tabs = (
            NativeTab("runtime-a", ALPHA, DEFAULT_WORKSPACE_ID),
            NativeTab("runtime-b", BETA, DEFAULT_WORKSPACE_ID, off_the_record=True),
        )
        with self.assertRaisesRegex(SplitViewError, "one profile"):
            open_split(tabs, DEFAULT_WORKSPACE_ID, ALPHA, BETA)
        payload = {"schema_version": 1, "leading_tab_uuid": ALPHA, "trailing_tab_uuid": BETA}
        self.assertIsNone(restore_layout(payload, tabs, DEFAULT_WORKSPACE_ID))

    def test_unknown_future_schema_is_reported_and_not_rewritten(self) -> None:
        payload = {"schema_version": 2, "future": {"panes": ["untouched"]}}
        original = deepcopy(payload)
        with self.assertRaisesRegex(UnknownSplitSchemaError, SPLIT_UNKNOWN_SCHEMA_POLICY):
            parse_layout(payload)
        self.assertEqual(original, payload)
        with self.assertRaises(UnknownSplitSchemaError):
            parse_layout({"schema_version": True})

    def test_damaged_metadata_falls_back_to_one_pane_without_losing_tabs(self) -> None:
        tabs = active_tabs()
        for name, payload in (
            ("absent", None),
            ("future_schema", {"schema_version": 9, "leading_tab_uuid": ALPHA}),
            ("not_a_uuid", {"schema_version": 1, "leading_tab_uuid": "x", "trailing_tab_uuid": BETA}),
            ("same_tab_twice", {"schema_version": 1, "leading_tab_uuid": ALPHA, "trailing_tab_uuid": ALPHA}),
            ("stale_tab", {"schema_version": 1, "leading_tab_uuid": ALPHA, "trailing_tab_uuid": GAMMA}),
            (
                "bad_ratio",
                {"schema_version": 1, "leading_tab_uuid": ALPHA, "trailing_tab_uuid": BETA, "ratio": 0.99},
            ),
            (
                "bad_pane",
                {"schema_version": 1, "leading_tab_uuid": ALPHA, "trailing_tab_uuid": BETA, "focused_pane": "middle"},
            ),
            ("wrong_type", "not-an-object"),
        ):
            with self.subTest(case=name):
                self.assertIsNone(restore_layout(payload, tabs, DEFAULT_WORKSPACE_ID))
        self.assertEqual(3, len(tabs))

    def test_switching_workspace_fails_the_split_closed(self) -> None:
        layout = open_split(active_tabs(), DEFAULT_WORKSPACE_ID, ALPHA, BETA)
        payload = persistable_layout(layout, off_the_record=False)
        self.assertIsNone(restore_layout(payload, active_tabs(), OTHER_WORKSPACE))

    def test_persist_restore_round_trip_is_stable(self) -> None:
        layout = open_split(active_tabs(), DEFAULT_WORKSPACE_ID, ALPHA, BETA, orientation=ORIENTATION_ROWS, ratio=0.3)
        payload = persistable_layout(layout, off_the_record=False)
        self.assertEqual(layout, restore_layout(payload, active_tabs(), DEFAULT_WORKSPACE_ID))

    def test_swap_moves_position_and_focus_but_no_navigation_state(self) -> None:
        layout = open_split(active_tabs(), DEFAULT_WORKSPACE_ID, ALPHA, BETA, orientation=ORIENTATION_ROWS, ratio=0.3)
        swapped = swap_panes(layout)
        self.assertEqual((BETA, ALPHA), swapped.tab_uuids())
        self.assertEqual(ALPHA, swapped.focused_tab_uuid())
        self.assertEqual((layout.orientation, layout.ratio), (swapped.orientation, swapped.ratio))
        self.assertEqual(layout, swap_panes(swapped))

    def test_persisted_record_carries_no_chromium_owned_state(self) -> None:
        layout = open_split(active_tabs(), DEFAULT_WORKSPACE_ID, ALPHA, BETA)
        payload = persistable_layout(layout, off_the_record=False)
        self.assertEqual(
            {"schema_version", "leading_tab_uuid", "trailing_tab_uuid", "orientation", "ratio", "focused_pane"},
            set(payload),
        )

    def test_off_the_record_split_state_is_never_persisted(self) -> None:
        layout = open_split(active_tabs(), DEFAULT_WORKSPACE_ID, ALPHA, BETA)
        self.assertIsNone(persistable_layout(layout, off_the_record=True))
        self.assertIsNone(persistable_layout(None, off_the_record=False))

    def test_closing_a_pane_returns_the_survivor(self) -> None:
        layout = open_split(active_tabs(), DEFAULT_WORKSPACE_ID, ALPHA, BETA)
        self.assertEqual(BETA, close_pane(layout, LEADING))
        self.assertEqual(ALPHA, close_pane(layout, TRAILING))
        with self.assertRaisesRegex(SplitViewError, "pane must be"):
            close_pane(layout, "middle")

    def test_focus_routing_is_explicit(self) -> None:
        layout = open_split(active_tabs(), DEFAULT_WORKSPACE_ID, ALPHA, BETA)
        self.assertEqual(BETA, focus_pane(layout, TRAILING).focused_tab_uuid())
        with self.assertRaisesRegex(SplitViewError, "pane must be"):
            focus_pane(layout, "")

    def test_interactive_resize_clamps_and_rejects_non_numbers(self) -> None:
        layout = open_split(active_tabs(), DEFAULT_WORKSPACE_ID, ALPHA, BETA)
        self.assertEqual(MIN_RATIO, resize_split(layout, 0.01).ratio)
        self.assertEqual(MAX_RATIO, resize_split(layout, 5).ratio)
        self.assertEqual(0.35, resize_split(layout, 0.35).ratio)
        with self.assertRaisesRegex(SplitViewError, "real number"):
            resize_split(layout, "0.5")

    def test_open_rejects_unsupported_orientation_and_ratio(self) -> None:
        with self.assertRaisesRegex(SplitViewError, "orientation"):
            open_split(active_tabs(), DEFAULT_WORKSPACE_ID, ALPHA, BETA, orientation="vertical")
        with self.assertRaisesRegex(SplitViewError, "ratio"):
            open_split(active_tabs(), DEFAULT_WORKSPACE_ID, ALPHA, BETA, ratio=0.95)


if __name__ == "__main__":
    unittest.main()
