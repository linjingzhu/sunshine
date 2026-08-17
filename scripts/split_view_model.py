#!/usr/bin/env python3
"""Pure two-pane split-view state model used before native Chromium wiring.

Chromium owns tabs, WebContents lifetime, navigation, and session restore. This
module validates only Sunshine's window-scoped split metadata and routes pane
focus between two Chromium-owned tabs. It carries no browser or UI dependency so
the fail-closed policy can be tested without claiming native delivery.

Orientation values are ``columns`` and ``rows`` rather than vertical/horizontal so
that split-pane orientation can never be confused with the permanently excluded
tab-strip orientation scope, which repository text guards keep out of the tree.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Iterable, Mapping

from scripts.workspace_model import NativeTab, WorkspaceModelError, canonical_uuid


SPLIT_SCHEMA_VERSION = 1
SPLIT_SCOPE = "window_session_extra_data"
SPLIT_PANE_COUNT = 2
SPLIT_UNKNOWN_SCHEMA_POLICY = "preserve_without_rewrite"
SPLIT_CORRUPTION_POLICY = "fail_closed_single_pane"
SPLIT_OFF_THE_RECORD_POLICY = "memory_only"
SPLIT_SWAP_POLICY = "position_only_no_navigation"

LEADING = "leading"
TRAILING = "trailing"
PANES = (LEADING, TRAILING)

ORIENTATION_COLUMNS = "columns"
ORIENTATION_ROWS = "rows"
ORIENTATIONS = frozenset({ORIENTATION_COLUMNS, ORIENTATION_ROWS})

DEFAULT_ORIENTATION = ORIENTATION_COLUMNS
DEFAULT_RATIO = 0.5
MIN_RATIO = 0.2
MAX_RATIO = 0.8


class SplitViewError(ValueError):
    """Base class for rejected split metadata or operations."""


class UnknownSplitSchemaError(SplitViewError):
    """Future split metadata must be preserved rather than silently rewritten."""


@dataclass(frozen=True)
class SplitLayout:
    """Window-scoped split state referencing durable Sunshine tab UUIDs.

    The layout never stores URLs, titles, navigation entries, native SessionIDs,
    or WebContents pointers. Chromium remains the only owner of that state.
    """

    schema_version: int
    leading_tab_uuid: str
    trailing_tab_uuid: str
    orientation: str
    ratio: float
    focused_pane: str

    def tab_uuids(self) -> tuple[str, str]:
        return (self.leading_tab_uuid, self.trailing_tab_uuid)

    def focused_tab_uuid(self) -> str:
        return self.leading_tab_uuid if self.focused_pane == LEADING else self.trailing_tab_uuid


def _split_uuid(value: object, field: str) -> str:
    """Reuse the workspace UUID rule while keeping split failures fail-closed.

    ``restore_layout`` recovers from ``SplitViewError`` only, so a shared-helper
    rejection must not escape as a foreign exception type.
    """

    try:
        return canonical_uuid(value, field)
    except WorkspaceModelError as error:
        raise SplitViewError(str(error)) from error


def _validated_pane(value: object) -> str:
    if value not in PANES:
        raise SplitViewError(f"pane must be one of {PANES}")
    return str(value)


def _validated_orientation(value: object) -> str:
    if value not in ORIENTATIONS:
        raise SplitViewError("split orientation must be 'columns' or 'rows'")
    return str(value)


def _validated_ratio(value: object) -> float:
    if type(value) not in (int, float):
        raise SplitViewError("split ratio must be a real number")
    ratio = float(value)
    if not MIN_RATIO <= ratio <= MAX_RATIO:
        raise SplitViewError(f"split ratio must be within [{MIN_RATIO}, {MAX_RATIO}]")
    return ratio


def parse_layout(payload: Mapping[str, object]) -> SplitLayout:
    """Strictly parse persisted split metadata.

    Raises ``UnknownSplitSchemaError`` for future versions so native wiring
    preserves the stored payload instead of rewriting it.
    """

    if not isinstance(payload, Mapping):
        raise SplitViewError("split metadata must be an object")
    version = payload.get("schema_version")
    if type(version) is not int or version != SPLIT_SCHEMA_VERSION:
        raise UnknownSplitSchemaError(SPLIT_UNKNOWN_SCHEMA_POLICY)

    leading = _split_uuid(payload.get("leading_tab_uuid"), "leading pane tab ID")
    trailing = _split_uuid(payload.get("trailing_tab_uuid"), "trailing pane tab ID")
    if leading == trailing:
        raise SplitViewError("a tab cannot be rendered live in both panes")
    return SplitLayout(
        SPLIT_SCHEMA_VERSION,
        leading,
        trailing,
        _validated_orientation(payload.get("orientation", DEFAULT_ORIENTATION)),
        _validated_ratio(payload.get("ratio", DEFAULT_RATIO)),
        _validated_pane(payload.get("focused_pane", LEADING)),
    )


def _eligible_tabs(tabs: Iterable[NativeTab], active_workspace_id: str) -> dict[str, NativeTab]:
    """Index active-workspace tabs by durable UUID, dropping ambiguous entries."""

    eligible: dict[str, NativeTab] = {}
    duplicated: set[str] = set()
    for tab in tabs:
        durable_id = tab.sunshine_tab_uuid
        if not durable_id or tab.workspace_id != active_workspace_id:
            continue
        if durable_id in eligible:
            duplicated.add(durable_id)
            continue
        eligible[durable_id] = tab
    for durable_id in duplicated:
        eligible.pop(durable_id, None)
    return eligible


def _paired_tabs(eligible: Mapping[str, NativeTab], leading: str, trailing: str) -> None:
    """Reject any pane pair Chromium could not own inside one window."""

    for durable_id in (leading, trailing):
        if durable_id not in eligible:
            raise SplitViewError("split panes require distinct tabs in the active workspace")
    if eligible[leading].off_the_record != eligible[trailing].off_the_record:
        raise SplitViewError("split panes must stay within one profile")


def open_split(
    tabs: Iterable[NativeTab],
    active_workspace_id: str,
    leading_tab_uuid: str,
    trailing_tab_uuid: str,
    *,
    orientation: str = DEFAULT_ORIENTATION,
    ratio: float = DEFAULT_RATIO,
) -> SplitLayout:
    """Place two distinct active-workspace tabs into two panes."""

    leading = _split_uuid(leading_tab_uuid, "leading pane tab ID")
    trailing = _split_uuid(trailing_tab_uuid, "trailing pane tab ID")
    if leading == trailing:
        raise SplitViewError("a tab cannot be rendered live in both panes")

    _paired_tabs(_eligible_tabs(tabs, active_workspace_id), leading, trailing)
    return SplitLayout(
        SPLIT_SCHEMA_VERSION,
        leading,
        trailing,
        _validated_orientation(orientation),
        _validated_ratio(ratio),
        LEADING,
    )


def restore_layout(
    payload: Mapping[str, object] | None,
    tabs: Iterable[NativeTab],
    active_workspace_id: str,
) -> SplitLayout | None:
    """Fail closed: return a usable layout, or ``None`` for the normal one-pane view.

    This never raises and never drops a tab. A damaged, stale, cross-workspace,
    or future-schema record simply yields ``None`` so the window shows its normal
    active tab while Chromium keeps every restored tab alive.
    """

    if payload is None:
        return None
    try:
        layout = parse_layout(payload)
        _paired_tabs(_eligible_tabs(tabs, active_workspace_id), *layout.tab_uuids())
    except SplitViewError:
        return None
    return layout


def swap_panes(layout: SplitLayout) -> SplitLayout:
    """Exchange pane positions only. Navigation, reload, and ratio are untouched."""

    return replace(
        layout,
        leading_tab_uuid=layout.trailing_tab_uuid,
        trailing_tab_uuid=layout.leading_tab_uuid,
        focused_pane=TRAILING if layout.focused_pane == LEADING else LEADING,
    )


def focus_pane(layout: SplitLayout, pane: str) -> SplitLayout:
    return replace(layout, focused_pane=_validated_pane(pane))


def resize_split(layout: SplitLayout, ratio: object) -> SplitLayout:
    """Clamp an interactive drag into the supported range instead of failing."""

    if type(ratio) not in (int, float):
        raise SplitViewError("split ratio must be a real number")
    clamped = min(MAX_RATIO, max(MIN_RATIO, float(ratio)))
    return replace(layout, ratio=clamped)


def close_pane(layout: SplitLayout, pane: str) -> str:
    """Dissolve the split and return the surviving tab's durable UUID.

    Both tabs stay alive. The caller drops the layout and shows the survivor in
    the normal active view.
    """

    closed = _validated_pane(pane)
    return layout.trailing_tab_uuid if closed == LEADING else layout.leading_tab_uuid


def persistable_layout(layout: SplitLayout | None, *, off_the_record: bool) -> dict[str, object] | None:
    """Serialize window-scoped split state, or ``None`` when it must stay in memory.

    Incognito and Guest windows keep split state in memory only; it is never
    written to persistent Sunshine metadata.
    """

    if layout is None or off_the_record:
        return None
    return {
        "schema_version": layout.schema_version,
        "leading_tab_uuid": layout.leading_tab_uuid,
        "trailing_tab_uuid": layout.trailing_tab_uuid,
        "orientation": layout.orientation,
        "ratio": layout.ratio,
        "focused_pane": layout.focused_pane,
    }
