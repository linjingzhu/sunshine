"""Failure-policy tests for the compile-free workspace state model."""

from copy import deepcopy
import unittest

from scripts.workspace_model import (
    DEFAULT_WORKSPACE_ID,
    NativeTab,
    UnknownSchemaError,
    WorkspaceModelError,
    close_workspace_atomic,
    default_catalog,
    move_tabs_atomic,
    parse_catalog,
    recover_membership,
)


class WorkspaceModelTests(unittest.TestCase):
    ONE = "11111111-1111-4111-8111-111111111111"
    TWO = "22222222-2222-4222-8222-222222222222"
    DESTINATION = "33333333-3333-4333-8333-333333333333"

    def test_unknown_schema_is_not_rewritten(self) -> None:
        payload = {"schema_version": 2, "workspaces": [{"future": {"untouched": True}}]}
        original = deepcopy(payload)
        with self.assertRaises(UnknownSchemaError):
            parse_catalog(payload)
        self.assertEqual(original, payload)
        with self.assertRaises(UnknownSchemaError):
            parse_catalog({"schema_version": True, "workspaces": []})

    def test_catalog_requires_unique_ids_and_normalizes_names(self) -> None:
        catalog = parse_catalog(
            {"schema_version": 1, "workspaces": [{"id": self.ONE, "name": "  My   Work  ", "color": "blue", "order": 7}]}
        )
        self.assertEqual("My Work", catalog.workspaces[0].name)
        self.assertEqual(7, catalog.workspaces[0].order)
        with self.assertRaises(WorkspaceModelError):
            parse_catalog(
                {"schema_version": 1, "workspaces": [
                    {"id": self.ONE, "name": "One", "order": 0},
                    {"id": self.ONE, "name": "Two", "order": 1}
                ]}
            )

    def test_corrupt_membership_recovers_every_native_tab_once(self) -> None:
        tabs = (
            NativeTab("runtime-1", self.ONE, "missing"),
            NativeTab("runtime-2", self.TWO, None),
        )
        recovered = recover_membership(default_catalog(), tabs)
        self.assertEqual(("runtime-1", "runtime-2"), tuple(tab.runtime_id for tab in recovered))
        self.assertTrue(all(tab.workspace_id == DEFAULT_WORKSPACE_ID for tab in recovered))

    def test_duplicate_durable_id_is_cleared_not_guessed(self) -> None:
        recovered = recover_membership(
            default_catalog(),
            (NativeTab("one", self.ONE, DEFAULT_WORKSPACE_ID), NativeTab("two", self.ONE, DEFAULT_WORKSPACE_ID)),
        )
        self.assertEqual(self.ONE, recovered[0].sunshine_tab_uuid)
        self.assertIsNone(recovered[1].sunshine_tab_uuid)

    def test_invalid_durable_uuid_is_cleared_and_runtime_ids_are_unique(self) -> None:
        recovered = recover_membership(default_catalog(), (NativeTab("one", "not-a-uuid", None),))
        self.assertIsNone(recovered[0].sunshine_tab_uuid)
        with self.assertRaisesRegex(WorkspaceModelError, "runtime tab IDs"):
            recover_membership(
                default_catalog(),
                (NativeTab("same", self.ONE, None), NativeTab("same", self.TWO, None)),
            )

    def test_move_failure_rolls_back_exact_state(self) -> None:
        catalog = parse_catalog(
            {"schema_version": 1, "workspaces": [
                {"id": DEFAULT_WORKSPACE_ID, "name": "Default", "order": 0},
                {"id": self.DESTINATION, "name": "Destination", "order": 1},
            ]}
        )
        tabs = (NativeTab("one", self.ONE, DEFAULT_WORKSPACE_ID),)
        self.assertIs(tabs, move_tabs_atomic(tabs, ["one"], self.DESTINATION, catalog, fail_before_commit=True))

    def test_move_commits_without_changing_native_identity(self) -> None:
        catalog = parse_catalog(
            {"schema_version": 1, "workspaces": [
                {"id": DEFAULT_WORKSPACE_ID, "name": "Default", "order": 0},
                {"id": self.DESTINATION, "name": "Destination", "order": 1},
            ]}
        )
        tabs = (NativeTab("one", self.ONE, DEFAULT_WORKSPACE_ID, group_id="native-group"),)
        moved = move_tabs_atomic(tabs, ["one"], self.DESTINATION, catalog)
        self.assertEqual(self.DESTINATION, moved[0].workspace_id)
        self.assertEqual(("one", self.ONE, "native-group"), (moved[0].runtime_id, moved[0].sunshine_tab_uuid, moved[0].group_id))

    def test_partial_native_group_move_requires_explicit_choice(self) -> None:
        catalog = parse_catalog(
            {"schema_version": 1, "workspaces": [
                {"id": DEFAULT_WORKSPACE_ID, "name": "Default", "order": 0},
                {"id": self.DESTINATION, "name": "Destination", "order": 1},
            ]}
        )
        tabs = (
            NativeTab("one", self.ONE, DEFAULT_WORKSPACE_ID, group_id="group"),
            NativeTab("two", self.TWO, DEFAULT_WORKSPACE_ID, group_id="group"),
        )
        with self.assertRaisesRegex(WorkspaceModelError, "explicit_choice"):
            move_tabs_atomic(tabs, ["one"], self.DESTINATION, catalog)


class CloseWorkspaceTransactionTests(unittest.TestCase):
    ONE = "11111111-1111-4111-8111-111111111111"
    TWO = "22222222-2222-4222-8222-222222222222"
    DESTINATION = "33333333-3333-4333-8333-333333333333"

    def catalog(self) -> object:
        return parse_catalog(
            {"schema_version": 1, "workspaces": [
                {"id": DEFAULT_WORKSPACE_ID, "name": "Default", "order": 0},
                {"id": self.DESTINATION, "name": "Destination", "order": 1},
            ]}
        )

    def test_close_transfers_every_tab_and_discards_none(self) -> None:
        tabs = (
            NativeTab("one", self.ONE, DEFAULT_WORKSPACE_ID),
            NativeTab("two", self.TWO, self.DESTINATION),
        )
        catalog, moved = close_workspace_atomic(self.catalog(), tabs, DEFAULT_WORKSPACE_ID, self.DESTINATION)
        self.assertEqual(len(tabs), len(moved))
        self.assertEqual((self.DESTINATION, self.DESTINATION), tuple(tab.workspace_id for tab in moved))
        self.assertEqual((self.ONE, self.TWO), tuple(tab.sunshine_tab_uuid for tab in moved))
        self.assertEqual((self.DESTINATION,), tuple(workspace.id for workspace in catalog.workspaces))

    def test_close_requires_a_distinct_existing_destination(self) -> None:
        tabs = (NativeTab("one", self.ONE, DEFAULT_WORKSPACE_ID),)
        with self.assertRaisesRegex(WorkspaceModelError, "must both exist"):
            close_workspace_atomic(self.catalog(), tabs, DEFAULT_WORKSPACE_ID, self.ONE)
        with self.assertRaisesRegex(WorkspaceModelError, "explicit_destination_atomic_transfer"):
            close_workspace_atomic(self.catalog(), tabs, DEFAULT_WORKSPACE_ID, DEFAULT_WORKSPACE_ID)

    def test_the_last_workspace_cannot_be_closed(self) -> None:
        """A sole workspace has no distinct destination, so close is always rejected."""

        catalog = default_catalog()
        tabs = (NativeTab("one", self.ONE, DEFAULT_WORKSPACE_ID),)
        self.assertEqual(1, len(catalog.workspaces))
        with self.assertRaisesRegex(WorkspaceModelError, "explicit_destination_atomic_transfer"):
            close_workspace_atomic(catalog, tabs, DEFAULT_WORKSPACE_ID, DEFAULT_WORKSPACE_ID)
        with self.assertRaisesRegex(WorkspaceModelError, "must both exist"):
            close_workspace_atomic(catalog, tabs, DEFAULT_WORKSPACE_ID, self.DESTINATION)

    def test_close_failure_rolls_back_exact_state(self) -> None:
        catalog = self.catalog()
        tabs = (NativeTab("one", self.ONE, DEFAULT_WORKSPACE_ID),)
        rolled_back = close_workspace_atomic(
            catalog, tabs, DEFAULT_WORKSPACE_ID, self.DESTINATION, fail_before_commit=True
        )
        self.assertIs(catalog, rolled_back[0])
        self.assertIs(tabs, rolled_back[1])

    def test_close_rejects_a_group_straddling_two_workspaces(self) -> None:
        tabs = (
            NativeTab("one", self.ONE, DEFAULT_WORKSPACE_ID, group_id="group"),
            NativeTab("two", self.TWO, self.DESTINATION, group_id="group"),
        )
        with self.assertRaisesRegex(WorkspaceModelError, "explicit_choice"):
            close_workspace_atomic(self.catalog(), tabs, DEFAULT_WORKSPACE_ID, self.DESTINATION)

    def test_closing_an_empty_workspace_is_allowed(self) -> None:
        tabs = (NativeTab("two", self.TWO, self.DESTINATION),)
        catalog, kept = close_workspace_atomic(self.catalog(), tabs, DEFAULT_WORKSPACE_ID, self.DESTINATION)
        self.assertEqual(tabs, kept)
        self.assertEqual((self.DESTINATION,), tuple(workspace.id for workspace in catalog.workspaces))


if __name__ == "__main__":
    unittest.main()
