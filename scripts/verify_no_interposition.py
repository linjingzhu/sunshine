#!/usr/bin/env python3
"""Fail when Sunshine builds something Chromium already owns.

Four contract criteria say the same thing in four places: the defect is the
*existence* of a Sunshine-owned copy, not its behaviour. That makes them
decidable against this repository today, with no build and no baseline, which
`docs/ACCEPTANCE_SUITES.md` section 8 lists them as and nothing implemented.

    docs/OMNIBOX_CONTRACT.md      section 13.20  no second URL parser
    docs/TAB_LIFECYCLE_CONTRACT.md section 13.2  no stored per-tab lifecycle flag
    docs/ADVANCED_TABS_CONTRACT.md section 11.10 no pinned/recently-closed/
                                                 duplicate/canonical-URL store
    docs/PERFORMANCE_BUDGET.md    P5, cheap form no repeating timer or idle task

Two design rules make the difference between a usable check and one the next
person deletes.

**Only Sunshine-authored text is searched.** A patch file is mostly upstream:
`0002-sunshine-new-tab.patch` carries `VOICE_IDLE_TIMEOUT_MS` and an
`ntp-logo` element in its context lines, and neither is Sunshine's. Patches are
therefore reduced to their added lines before any pattern runs. The guards in
`scripts/` are excluded for the mirror-image reason: a guard has to name the
thing it forbids, so scanning `verify_*.py` and `validate_*.py` for the words
they forbid is a check that fails on itself. Everything else under `scripts/`
is scanned, so a new *model* module is covered by default and only a new
*guard* needs the established name prefix.

**Declared data is separated from code that reads data.** AT-1 does not forbid
reading pinned state -- it says pinned state is read from `TabStripModel` when
needed -- so a rule that fires on the word `pinned` anywhere would fire on the
compliant implementation. What the contracts forbid is a *field*. So field
names are extracted structurally (`json` for manifests, `ast` for Python
module- and class-level declarations and dict literals, conservative patterns
for added patch lines) and only those names are tested. Function locals are not
declared data and are not collected.

Enforces: OS-9, AT-1, AT-9, AT-12, P5.

The two remaining criteria have no identifier to claim. `OMNIBOX_CONTRACT`
13.20 is an ordinal in a renumbering list, and `TAB_LIFECYCLE_CONTRACT` calls
its rule "invariant 1" with no prefix; `docs/ACCEPTANCE_SUITES.md` section 9
already records that as a defect in the contract set.
"""

from __future__ import annotations

import ast
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]

SEARCHED = ("first_party", "downstream", "scripts", "config")

# A guard names what it prohibits. `verify_*` and `validate_*` is the naming
# convention this repository already uses for them, and CI already runs them by
# that glob; `trace_invariants.py` reads the claims those guards write.
GUARD_PREFIXES = ("verify_", "validate_")
GUARD_NAMES = frozenset({"trace_invariants.py"})

SKIPPED_PARTS = frozenset({"__pycache__", ".git"})


# --- What counts as a Sunshine source ----------------------------------------


def _is_guard(path: Path) -> bool:
    return path.name in GUARD_NAMES or path.name.startswith(GUARD_PREFIXES)


def added_lines(patch_text: str) -> str:
    """The Sunshine-authored half of a patch.

    A `+++ b/path` header also starts with `+` and names an upstream file; it is
    the single most likely false positive in the whole check, because every
    patch contains one and it always points at Chromium's tree.
    """

    kept = []
    for line in patch_text.splitlines():
        if line.startswith("+") and not line.startswith("+++"):
            kept.append(line[1:])
    return "\n".join(kept)


def sunshine_sources(root: Path) -> list[tuple[str, str]]:
    """(label, text) for every piece of Sunshine-authored text in scope."""

    sources: list[tuple[str, str]] = []
    for directory in SEARCHED:
        base = root / directory
        if not base.is_dir():
            continue
        for path in sorted(base.rglob("*")):
            if not path.is_file() or SKIPPED_PARTS & set(path.parts):
                continue
            if _is_guard(path):
                continue
            try:
                text = path.read_text(encoding="utf-8")
            except (UnicodeDecodeError, OSError):
                continue
            relative = path.relative_to(root).as_posix()
            if path.suffix == ".patch":
                sources.append((f"{relative} (added lines)", added_lines(text)))
            else:
                sources.append((relative, text))
    return sources


# --- What counts as a declared field -----------------------------------------

# An object-literal, JSON or TypeScript-interface key on an added patch line.
# CSS declarations have the same shape and are deliberately not excluded: a
# rule that skipped `name: value;` would also skip a TypeScript field, and CSS
# property names collide with none of the prohibited fields below. CSS custom
# properties begin with `--` and match nothing here.
KEY = re.compile(r"""^\s*(?:"([^"]+)"|'([^']+)'|([A-Za-z_$][\w$-]*))\s*:""")
# A Chromium member variable carries a trailing underscore by convention.
CPP_MEMBER = re.compile(r"^\s*(?:const |static |mutable )*[\w:<>,\s*&]+?\s+([a-z]\w*_)\s*[=;]")
# A Chromium constant or preference name.
CPP_CONSTANT = re.compile(r"\bk([A-Z]\w*)\b")


def _json_keys(payload: object, prefix: str = "") -> list[tuple[str, str]]:
    found: list[tuple[str, str]] = []
    if isinstance(payload, dict):
        for key, value in payload.items():
            found.append((f"{prefix}{key}", key))
            found.extend(_json_keys(value, f"{prefix}{key}."))
    elif isinstance(payload, list):
        for index, value in enumerate(payload):
            found.extend(_json_keys(value, f"{prefix}{index}."))
    return found


def _python_declarations(text: str) -> list[tuple[str, str]]:
    """Module- and class-level names, plus the keys of every dict literal.

    Function locals are deliberately absent. `pinned = tab.IsPinned()` inside a
    function is a read of Chromium's state, which AT-1 requires; a class field
    or a serialised key of the same name is the mirror it prohibits.
    """

    try:
        tree = ast.parse(text)
    except SyntaxError:
        return []

    found: list[tuple[str, str]] = []
    scopes: list[ast.AST] = [tree]
    scopes.extend(node for node in ast.walk(tree) if isinstance(node, ast.ClassDef))
    for scope in scopes:
        for node in getattr(scope, "body", []):
            if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
                found.append((f"line {node.lineno}", node.target.id))
            elif isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        found.append((f"line {node.lineno}", target.id))
    for node in ast.walk(tree):
        if isinstance(node, ast.Dict):
            for key in node.keys:
                if isinstance(key, ast.Constant) and isinstance(key.value, str):
                    found.append((f"line {key.lineno}", key.value))
    return found


def _patch_declarations(text: str) -> list[tuple[str, str]]:
    found: list[tuple[str, str]] = []
    for number, line in enumerate(text.splitlines(), start=1):
        match = KEY.match(line)
        if match:
            found.append((f"added line {number}", next(g for g in match.groups() if g)))
        member = CPP_MEMBER.match(line)
        if member:
            found.append((f"added line {number}", member.group(1).rstrip("_")))
        for constant in CPP_CONSTANT.findall(line):
            found.append((f"added line {number}", constant))
    return found


def declared_names(root: Path) -> list[tuple[str, str, str]]:
    """(file label, where, field name) for every field Sunshine declares."""

    found: list[tuple[str, str, str]] = []
    for label, text in sunshine_sources(root):
        if label.endswith("(added lines)"):
            found.extend((label, where, name) for where, name in _patch_declarations(text))
        elif label.endswith(".json"):
            try:
                payload = json.loads(text)
            except json.JSONDecodeError:
                continue
            found.extend((label, where, name) for where, name in _json_keys(payload))
        elif label.endswith(".py"):
            found.extend((label, where, name) for where, name in _python_declarations(text))
    return found


def normalize(name: str) -> tuple[str, ...]:
    """Field name to underscore-separated segments, however it was spelled.

    `pinnedTabs`, `pinned-tabs`, `kPinnedTabs` and `PINNED_TABS` are one field.
    """

    if re.fullmatch(r"k[A-Z]\w*", name):
        name = name[1:]
    name = re.sub(r"[-\s.]+", "_", name)
    name = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", "_", name)
    return tuple(part for part in name.lower().split("_") if part)


# --- The prohibited fields, per criterion ------------------------------------

_STATES = ("loading", "ready", "crashed", "frozen", "discarded", "closing", "detaching")
LIFECYCLE_FIELDS = frozenset(
    {"throbber", "spinner", "is_throbbing"}
    | {f"{state}" for state in _STATES}
    | {f"is_{state}" for state in _STATES}
    | {f"was_{state}" for state in _STATES}
    | {f"tab_{state}" for state in _STATES}
    | {f"{state}_flag" for state in _STATES}
    | {f"{state}_state" for state in _STATES}
)


def _lifecycle_field(name: str, segments: tuple[str, ...]) -> str | None:
    """TAB_LIFECYCLE_CONTRACT 13.2: no stored per-tab lifecycle state."""

    if name in LIFECYCLE_FIELDS:
        return "a stored per-tab lifecycle flag"
    marker = {"state", "states", "status", "flag"} & set(segments)
    if marker and {"lifecycle", "tab", "tabs"} & set(segments):
        return "a stored per-tab lifecycle flag"
    return None


def _pinned_field(_name: str, segments: tuple[str, ...]) -> str | None:
    """ADVANCED_TABS_CONTRACT AT-1: Sunshine stores no pinned state."""

    if {"pin", "pinned", "unpinned", "pinning"} & set(segments):
        return "a pinned flag; pinned state is read from TabStripModel (AT-1)"
    return None


def _recently_closed_field(_name: str, segments: tuple[str, ...]) -> str | None:
    """ADVANCED_TABS_CONTRACT AT-9: Sunshine keeps no recently-closed store."""

    present = set(segments)
    if {"recently", "recent"} & present and {"closed", "close", "tab", "tabs"} & present:
        return "a recently-closed entry (AT-9)"
    if "closed" in present and {"tab", "tabs"} & present:
        return "a recently-closed entry (AT-9)"
    return None


def _duplicate_field(_name: str, segments: tuple[str, ...]) -> str | None:
    """ADVANCED_TABS_CONTRACT AT-12: duplicate detection is derived, never stored."""

    present = set(segments)
    if {"duplicate", "duplicates", "dedup", "dedupe", "dedupkey"} & present:
        return "a duplicate set (AT-12)"
    if "canonical" in present and {"url", "urls", "link", "links"} & present:
        return "a canonical-URL table (AT-12)"
    return None


def _omnibox_field(_name: str, segments: tuple[str, ...]) -> str | None:
    """OMNIBOX_CONTRACT section 12: the state a second parser would need."""

    present = set(segments)
    if {"tld", "tlds"} & present or {"public", "suffix"} <= present:
        return "a TLD list"
    if "schemes" in present or ("scheme" in present and {"table", "map", "list", "set", "allowlist"} & present):
        return "a scheme table"
    if {"host", "hosts"} & present and {"allowlist", "whitelist", "validator", "table", "map", "pattern", "patterns"} & present:
        return "a host validator or development-host allowlist"
    if {"omnibox", "autocomplete", "suggestion", "suggestions"} & present:
        return "a Sunshine autocomplete or suggestion store"
    if {"typed", "query", "search"} & present and {"history", "url", "urls", "cache"} & present:
        return "a typed-URL store or query history"
    return None


def _repeating_field(_name: str, segments: tuple[str, ...]) -> str | None:
    """PERFORMANCE_BUDGET P5: Sunshine's legitimate idle cost is zero."""

    if {"timer", "timers", "interval", "poll", "polling", "heartbeat"} & set(segments):
        return "a repeating timer or poll (P5)"
    return None


FIELD_RULES = (
    _lifecycle_field,
    _pinned_field,
    _recently_closed_field,
    _duplicate_field,
    _omnibox_field,
    _repeating_field,
)


# --- The prohibited symbols --------------------------------------------------

# Each of these does one job. None has a use in first-party code that is not the
# second parser `docs/OMNIBOX_CONTRACT.md` section 1 enumerates, which is what
# makes the list narrow enough to keep.
PARSER_SYMBOLS = (
    ("an omnibox classifier", ("AutocompleteInput", "AutocompleteClassifier",
                               "AutocompleteSchemeClassifier", "AutocompleteController",
                               "AutocompleteProvider")),
    ("a URL fixup or segmentation routine", ("url_formatter::", "FixupURL", "SegmentURL")),
    ("a registry/TLD lookup", ("registry_controlled_domains", "GetDomainAndRegistry",
                               "HostHasRegistryControlledDomain", "PublicSuffixList")),
    ("an IDN renderer", ("IDNToUnicode", "IDNSpoofChecker", "FormatUrlForSecurityDisplay",
                         "FormatUrlForDisplay")),
    ("a host validator", ("net::IsLocalhost", "HostStringIsIPAddress", "CanonicalizeHost",
                          "IsCanonicalizedHostCompliant")),
    ("a URL parser", ("urllib.parse", "urlparse(", "urlsplit(", "new URL(", "URL.parse(",
                      "URL.canParse(")),
)

# OS-9: no first-party page, handler or module accepts a string and navigates.
NAVIGATION_SYMBOLS = ("LoadURLWithParams", "OpenURLFromTab", "OpenURLParams", "NavigateParams",
                      "location.assign(", "location.replace(", "location.href =", "window.open(")

# P5. `setTimeout` is absent on purpose: one-shot is legitimate and a
# self-rearming one is not distinguishable from it by any pattern worth
# defending. The repeating and idle-triggered forms are unambiguous.
REPEATING_SYMBOLS = ("setInterval(", "requestIdleCallback(", "base::RepeatingTimer",
                     "RepeatingTimer<", "base::DelayTimer", "base::MetronomeTimer",
                     "IdleTaskRunner", "RunWhenIdle", "threading.Timer(", "sched.scheduler(",
                     "animation-iteration-count: infinite",
                     "animation-iteration-count:infinite")

# A scheme table written as literals rather than as a named field. Matched only
# in the `scheme:` or `scheme://` spelling, so that the bare words `data` and
# `file` -- both ordinary keys in this repository's manifests -- cannot trip it.
SCHEME_LITERAL = re.compile(
    r"""["'](https?|ftp|file|data|javascript|view-source|about|blob|wss?|"""
    r"""chrome|chrome-untrusted|mailto)(?::(?://)?)["']"""
)
# A TLD list is three or more of these; two co-occur in ordinary prose.
TLD_LITERAL = re.compile(
    r"""["']\.(com|net|org|edu|gov|info|biz|io|co|uk|de|jp|fr|cn|ru|kr|br|au|ca|nl)["']"""
)


# --- Checks ------------------------------------------------------------------


def check_declared_fields(root: Path, failures: list[str]) -> None:
    for label, where, name in declared_names(root):
        segments = normalize(name)
        joined = "_".join(segments)
        for rule in FIELD_RULES:
            verdict = rule(joined, segments)
            if verdict:
                failures.append(f"{label} ({where}): field {name!r} is {verdict}")


def check_no_second_parser(root: Path, failures: list[str]) -> None:
    """OMNIBOX_CONTRACT 13.20 and OS-9."""

    for label, text in sunshine_sources(root):
        for description, symbols in PARSER_SYMBOLS:
            for symbol in symbols:
                if symbol in text:
                    failures.append(f"{label}: {symbol!r} is {description}")
        for symbol in NAVIGATION_SYMBOLS:
            if symbol in text:
                failures.append(f"{label}: {symbol!r} navigates from an unclassified string (OS-9)")
        schemes = {match.lower() for match in SCHEME_LITERAL.findall(text)}
        if len(schemes) >= 2:
            failures.append(f"{label}: scheme table over {sorted(schemes)}")
        tlds = {match.lower() for match in TLD_LITERAL.findall(text)}
        if len(tlds) >= 3:
            failures.append(f"{label}: TLD list over {sorted(tlds)}")


def check_no_repeating_task(root: Path, failures: list[str]) -> None:
    """PERFORMANCE_BUDGET P5, cheap form."""

    for label, text in sunshine_sources(root):
        for symbol in REPEATING_SYMBOLS:
            if symbol in text:
                failures.append(f"{label}: {symbol!r} is a Sunshine-owned repeating or idle task (P5)")


def check_no_per_tab_sunshine_store(root: Path, failures: list[str]) -> None:
    """One declaration answers three criteria at once.

    A module manifest states who owns each store it touches, at what scope, and
    for how long. A Sunshine-owned, tab-scoped, surviving store is the shape of
    every mirror these contracts forbid -- a pinned copy (AT-1), a lifecycle
    flag (TAB_LIFECYCLE_CONTRACT invariant 1), a per-tab duplicate marker
    (AT-12). Chromium-owned tab data is the permitted channel: invariant 3 has
    Sunshine writing tab session extra-data at insertion and membership change,
    and the workspace module declares exactly that. `retention: none` stays
    allowed, because transient state is what both contracts permit.
    """

    for path in sorted((root / "first_party").rglob("*.json")):
        try:
            manifest = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        if not isinstance(manifest, dict) or "data" not in manifest:
            continue
        entries = manifest["data"] if isinstance(manifest["data"], list) else []
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            if (entry.get("owner") == "sunshine" and entry.get("scope") == "tab"
                    and entry.get("retention") in {"session", "persistent"}):
                failures.append(
                    f"{path.relative_to(root).as_posix()}: declares a Sunshine-owned, "
                    f"tab-scoped, {entry.get('retention')} store; per-tab state is Chromium's"
                )


def validate(root: Path = ROOT) -> list[str]:
    failures: list[str] = []
    check_declared_fields(root, failures)
    check_no_second_parser(root, failures)
    check_no_repeating_task(root, failures)
    check_no_per_tab_sunshine_store(root, failures)
    return failures


def main() -> int:
    failures = validate()
    if failures:
        print("\n".join(failures), file=sys.stderr)
        return 1
    print("Non-interposition check passed: no second parser, no stored lifecycle or "
          "tab state, no repeating task.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
