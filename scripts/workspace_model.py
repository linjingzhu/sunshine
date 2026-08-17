#!/usr/bin/env python3
"""Pure workspace metadata model used before native Chromium wiring.

Chromium owns tabs and session restore. This module validates only Sunshine's
workspace catalog and projects Chromium-restored tab extra_data into it. It is
deliberately free of browser/UI dependencies so failure policy can be tested
without claiming native delivery.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Iterable, Mapping
from uuid import UUID


WORKSPACE_SCHEMA_VERSION = 1
WORKSPACE_SCOPE = "profile_catalog_window_active"
WORKSPACE_MIN_COUNT = 1
WORKSPACE_UNKNOWN_SCHEMA_POLICY = "preserve_without_rewrite"
WORKSPACE_CORRUPTION_POLICY = "recover_tabs_to_default"
WORKSPACE_FAILURE_POLICY = "rollback"
WORKSPACE_OFF_THE_RECORD_POLICY = "memory_only"
WORKSPACE_GROUP_PARTIAL_MOVE_POLICY = "explicit_choice"
WORKSPACE_CLOSE_POLICY = "explicit_destination_atomic_transfer"
WORKSPACE_ARCHIVE_POLICY = "excluded_from_mvp"

DEFAULT_WORKSPACE_ID = "00000000-0000-4000-8000-000000000001"
MAX_NAME_LENGTH = 64
ALLOWED_COLORS = frozenset({"grey", "blue", "red", "yellow", "green", "pink", "purple", "cyan", "orange"})


class WorkspaceModelError(ValueError):
    """Base class for rejected workspace metadata or operations."""


class UnknownSchemaError(WorkspaceModelError):
    """Future metadata must be preserved rather than silently rewritten."""


@dataclass(frozen=True)
class Workspace:
    id: str
    name: str
    color: str
    order: int


@dataclass(frozen=True)
class Catalog:
    schema_version: int
    workspaces: tuple[Workspace, ...]

    def by_id(self) -> dict[str, Workspace]:
        return {workspace.id: workspace for workspace in self.workspaces}


@dataclass(frozen=True)
class NativeTab:
    """Projection of one Chromium-restored tab and its session extra_data."""

    runtime_id: str
    sunshine_tab_uuid: str | None
    workspace_id: str | None
    group_id: str | None = None
    off_the_record: bool = False


def _normalized_name(value: object) -> str:
    if not isinstance(value, str):
        raise WorkspaceModelError("workspace name must be a string")
    name = " ".join(value.split())
    if not name or len(name) > MAX_NAME_LENGTH:
        raise WorkspaceModelError("workspace name must contain 1..64 normalized characters")
    return name


def canonical_uuid(value: object, field: str) -> str:
    if not isinstance(value, str):
        raise WorkspaceModelError(f"{field} must be a UUID string")
    try:
        parsed = UUID(value)
    except ValueError as error:
        raise WorkspaceModelError(f"{field} must be a canonical UUID") from error
    if parsed.version != 4 or str(parsed) != value:
        raise WorkspaceModelError(f"{field} must be a canonical UUIDv4")
    return value


def parse_catalog(payload: Mapping[str, object]) -> Catalog:
    version = payload.get("schema_version")
    if type(version) is not int or version != WORKSPACE_SCHEMA_VERSION:
        raise UnknownSchemaError(WORKSPACE_UNKNOWN_SCHEMA_POLICY)
    raw_workspaces = payload.get("workspaces")
    if not isinstance(raw_workspaces, list) or len(raw_workspaces) < WORKSPACE_MIN_COUNT:
        raise WorkspaceModelError("at least one workspace is required")

    parsed: list[Workspace] = []
    seen_ids: set[str] = set()
    seen_orders: set[int] = set()
    for raw in raw_workspaces:
        if not isinstance(raw, Mapping):
            raise WorkspaceModelError("workspace entries must be objects")
        workspace_id = canonical_uuid(raw.get("id"), "workspace ID")
        if workspace_id in seen_ids:
            raise WorkspaceModelError("workspace IDs must be unique")
        color = raw.get("color", "grey")
        if color not in ALLOWED_COLORS:
            raise WorkspaceModelError("unsupported workspace color")
        order = raw.get("order")
        if type(order) is not int or order < 0 or order in seen_orders:
            raise WorkspaceModelError("workspace order must be a unique non-negative integer")
        seen_ids.add(workspace_id)
        seen_orders.add(order)
        parsed.append(Workspace(workspace_id, _normalized_name(raw.get("name")), str(color), order))

    return Catalog(WORKSPACE_SCHEMA_VERSION, tuple(sorted(parsed, key=lambda workspace: workspace.order)))


def default_catalog() -> Catalog:
    return Catalog(WORKSPACE_SCHEMA_VERSION, (Workspace(DEFAULT_WORKSPACE_ID, "Default", "blue", 0),))


def recover_membership(catalog: Catalog, tabs: Iterable[NativeTab]) -> tuple[NativeTab, ...]:
    """Recover every native tab exactly once without inventing session ownership.

    Missing/unknown workspace references fall back to Default. Duplicate durable
    tab UUIDs are cleared so native wiring can generate a new UUID and persist it
    through Chromium's own tab extra_data channel.
    """

    valid_workspaces = catalog.by_id()
    fallback = DEFAULT_WORKSPACE_ID if DEFAULT_WORKSPACE_ID in valid_workspaces else catalog.workspaces[0].id
    seen_uuids: set[str] = set()
    seen_runtime_ids: set[str] = set()
    recovered: list[NativeTab] = []
    for tab in tabs:
        if not tab.runtime_id or tab.runtime_id in seen_runtime_ids:
            raise WorkspaceModelError("native runtime tab IDs must be non-empty and unique")
        seen_runtime_ids.add(tab.runtime_id)
        try:
            durable_id = canonical_uuid(tab.sunshine_tab_uuid, "Sunshine tab ID")
        except WorkspaceModelError:
            durable_id = None
        if durable_id and durable_id in seen_uuids:
            durable_id = None
        if durable_id:
            seen_uuids.add(durable_id)
        workspace_id = tab.workspace_id if tab.workspace_id in valid_workspaces else fallback
        recovered.append(replace(tab, sunshine_tab_uuid=durable_id, workspace_id=workspace_id))
    return tuple(recovered)


def move_tabs_atomic(
    tabs: tuple[NativeTab, ...],
    runtime_ids: Iterable[str],
    destination_workspace_id: str,
    catalog: Catalog,
    *,
    fail_before_commit: bool = False,
) -> tuple[NativeTab, ...]:
    """Return a new committed projection, or the exact original on failure."""

    if destination_workspace_id not in catalog.by_id():
        raise WorkspaceModelError("destination workspace does not exist")
    selected = frozenset(runtime_ids)
    if not selected:
        raise WorkspaceModelError("at least one tab must be selected")
    existing = {tab.runtime_id for tab in tabs}
    if not selected <= existing:
        raise WorkspaceModelError("selected native tab is stale")
    selected_groups = {tab.group_id for tab in tabs if tab.runtime_id in selected and tab.group_id}
    for group_id in selected_groups:
        group_members = {tab.runtime_id for tab in tabs if tab.group_id == group_id}
        if not group_members <= selected:
            raise WorkspaceModelError(WORKSPACE_GROUP_PARTIAL_MOVE_POLICY)
    candidate = tuple(
        replace(tab, workspace_id=destination_workspace_id) if tab.runtime_id in selected else tab
        for tab in tabs
    )
    return tabs if fail_before_commit else candidate


def close_workspace_atomic(
    catalog: Catalog,
    tabs: tuple[NativeTab, ...],
    closed_workspace_id: str,
    destination_workspace_id: str,
    *,
    fail_before_commit: bool = False,
) -> tuple[Catalog, tuple[NativeTab, ...]]:
    """Retire a workspace by transferring every one of its tabs at once.

    Closing requires an explicit destination. Tabs are never discarded and
    archiving is not a supported outcome. On failure the exact original catalog
    and projection objects are returned so the caller can roll back.

    The caller owns window-local state: any window whose active workspace was the
    closed one must select the destination, and its split layout must be
    re-resolved so no pane keeps pointing at the retired workspace.
    """

    known = catalog.by_id()
    if closed_workspace_id not in known or destination_workspace_id not in known:
        raise WorkspaceModelError("closed and destination workspaces must both exist")
    if closed_workspace_id == destination_workspace_id:
        raise WorkspaceModelError(WORKSPACE_CLOSE_POLICY)

    for group_id in {tab.group_id for tab in tabs if tab.group_id and tab.workspace_id == closed_workspace_id}:
        if {tab.workspace_id for tab in tabs if tab.group_id == group_id} != {closed_workspace_id}:
            raise WorkspaceModelError(WORKSPACE_GROUP_PARTIAL_MOVE_POLICY)

    transferred = {tab.runtime_id for tab in tabs if tab.workspace_id == closed_workspace_id}
    if fail_before_commit:
        return catalog, tabs
    return (
        Catalog(catalog.schema_version, tuple(ws for ws in catalog.workspaces if ws.id != closed_workspace_id)),
        tuple(
            replace(tab, workspace_id=destination_workspace_id) if tab.runtime_id in transferred else tab
            for tab in tabs
        ),
    )


# --- Availability predicates -------------------------------------------------
#
# Side-effect free answers to "may this command be offered?", returning None when
# it may and the reason token the surface shows the user when it may not. See the
# The `guard` field could not serve this purpose: it held the operation, not a
# predicate, so asking a command whether it was available performed it.


def can_close_workspace(catalog: Catalog, closed_workspace_id: str) -> str | None:
    """Closing needs a distinct destination in the same profile to receive tabs."""

    known = catalog.by_id()
    if closed_workspace_id not in known:
        return "workspace_not_found"
    if len(known) < 2:
        return "no_destination_workspace"
    return None


def can_move_tabs(catalog: Catalog, destination_workspace_id: str) -> str | None:
    """Tabs can only move to a workspace that exists."""

    if destination_workspace_id not in catalog.by_id():
        return "no_destination_workspace"
    return None


# --- Window-local workspace state --------------------------------------------
#
# `workspace.switch` is specified to restore a workspace's last active tab, and
# nothing stored it. The catalog holds id/profile/name/colour/order, and window
# extra-data held only the active workspace, so the behaviour was specified with
# no owner.
#
# It belongs in *window* session extra-data, not the catalog: the catalog is
# profile-wide, so two windows showing the same workspace would overwrite each
# other's idea of where the user was. The reference is a durable Sunshine UUID,
# never a runtime id, which does not survive restart.
#
# This stores a pointer into Chromium's tabs. It does not shadow them: if the
# pointer no longer resolves, the answer is Chromium's own restored active tab.


WINDOW_STATE_SCHEMA_VERSION = 1


@dataclass(frozen=True)
class WindowWorkspaceState:
    """One window's workspace selection and where it left off in each."""

    schema_version: int
    active_workspace_id: str
    last_active_tab: Mapping[str, str]


def parse_window_state(payload: Mapping[str, object]) -> WindowWorkspaceState:
    """Fail closed on damaged window extra-data rather than guessing."""

    if not isinstance(payload, Mapping):
        raise WorkspaceModelError("window state must be a mapping")
    version = payload.get("schema_version")
    if version != WINDOW_STATE_SCHEMA_VERSION:
        raise UnknownSchemaError(f"unsupported window state schema: {version!r}")

    active = canonical_uuid(payload.get("active_workspace_id"), "active_workspace_id")

    raw = payload.get("last_active_tab", {})
    if not isinstance(raw, Mapping):
        raise WorkspaceModelError("last_active_tab must be a mapping")
    resolved: dict[str, str] = {}
    for workspace_id, tab_uuid in raw.items():
        resolved[canonical_uuid(workspace_id, "last_active_tab key")] = canonical_uuid(
            tab_uuid, "last_active_tab value"
        )
    return WindowWorkspaceState(WINDOW_STATE_SCHEMA_VERSION, active, resolved)


def record_active_tab(
    state: WindowWorkspaceState, workspace_id: str, tab_uuid: str
) -> WindowWorkspaceState:
    """Remember where the user is in `workspace_id`, for this window only."""

    updated = dict(state.last_active_tab)
    updated[canonical_uuid(workspace_id, "workspace_id")] = canonical_uuid(tab_uuid, "tab_uuid")
    return WindowWorkspaceState(state.schema_version, state.active_workspace_id, updated)


def resolve_switch_target(
    state: WindowWorkspaceState, workspace_id: str, tabs: Iterable[NativeTab]
) -> str | None:
    """The tab `workspace.switch` should activate, or None to let Chromium choose.

    None is a real answer, not a failure: on a first visit, after the remembered
    tab is closed, or when it has moved to another workspace, Chromium's own
    restored active tab is correct and Sunshine must not override it.

    Membership is re-checked here rather than trusted from the record. A tab
    moved to another workspace still matches by UUID, and activating it would
    project a tab the target workspace does not contain.
    """

    remembered = state.last_active_tab.get(workspace_id)
    if remembered is None:
        return None
    for tab in tabs:
        if tab.sunshine_tab_uuid == remembered and tab.workspace_id == workspace_id:
            return remembered
    return None


def prune_window_state(state: WindowWorkspaceState, catalog: Catalog) -> WindowWorkspaceState:
    """Drop entries for workspaces that no longer exist.

    Without this a closed workspace's entry outlives it, and a later workspace
    reusing that UUID is not possible, so the entry simply accumulates.
    """

    known = catalog.by_id()
    kept = {w: t for w, t in state.last_active_tab.items() if w in known}
    if len(kept) == len(state.last_active_tab):
        return state
    return WindowWorkspaceState(state.schema_version, state.active_workspace_id, kept)


def persistable_window_state(
    state: WindowWorkspaceState | None, *, off_the_record: bool
) -> dict[str, object] | None:
    """Serialize window workspace state, or None when it must stay in memory.

    Incognito and Guest windows keep it in memory only. A per-workspace record of
    the last page the user was reading is browsing history by another name.
    """

    if state is None or off_the_record:
        return None
    return {
        "schema_version": state.schema_version,
        "active_workspace_id": state.active_workspace_id,
        "last_active_tab": dict(sorted(state.last_active_tab.items())),
    }
