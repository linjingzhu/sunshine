#!/usr/bin/env python3
"""Validate the Sunshine command registry without building Chromium.

The command-first rule requires every user-visible action to be a command with
one authoritative implementation, an availability predicate, a telemetry event,
and an error result. Before this registry those identifiers lived only in prose
tables in two documents, which had already drifted apart.
"""

from __future__ import annotations

import importlib
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
# Guards are addressed as scripts.<module>, so the repository root has to be
# importable however this validator is invoked.
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

REGISTRY = ROOT / "first_party/commands.json"
DOCS = ROOT / "docs"

REQUIRED_KEYS = {"id", "summary", "owner", "availability", "guard", "telemetry", "errors"}
SEGMENT = re.compile(r"^[a-z][a-z0-9]*(?:_[a-z0-9]+)*$")
TELEMETRY = re.compile(r"^Sunshine\.Command\.[A-Za-z0-9]+$")
GUARD = re.compile(r"^scripts\.[a-z_]+:[a-z_]+$")
# Tokens in documentation that look like a command: backticked, dotted, and
# starting with a declared surface. Narrow enough that ordinary prose such as
# `app.css` or `chromium.googlesource.com` is not mistaken for a command.
DOC_TOKEN = re.compile(r"`([a-z][a-z0-9_]*(?:\.[a-z][a-z0-9_]*)+)`")
CHROMIUM_OWNER = "chromium"


class CommandRegistryError(ValueError):
    pass


def expected_telemetry(command_id: str) -> str:
    """Derive the telemetry name so it cannot drift from the identifier."""

    words = command_id.replace(".", "_").split("_")
    return "Sunshine.Command." + "".join(word.capitalize() for word in words)


def load(path: Path = REGISTRY) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or payload.get("schema_version") != 1:
        raise CommandRegistryError("command registry schema_version must be 1")
    surfaces = payload.get("surfaces")
    if not isinstance(surfaces, list) or not surfaces:
        raise CommandRegistryError("surfaces must be a non-empty list")
    if surfaces != sorted(set(surfaces)):
        raise CommandRegistryError("surfaces must be unique and sorted")
    if any(not isinstance(s, str) or not SEGMENT.fullmatch(s) for s in surfaces):
        raise CommandRegistryError("surfaces must be lowercase identifiers")
    commands = payload.get("commands")
    if not isinstance(commands, list) or not commands:
        raise CommandRegistryError("commands must be a non-empty list")
    return payload


def module_ids(root: Path = ROOT) -> set[str]:
    registry = json.loads((root / "first_party/registry.json").read_text(encoding="utf-8"))
    ids: set[str] = set()
    for entry in registry["modules"]:
        manifest = json.loads((root / entry).read_text(encoding="utf-8"))
        ids.add(manifest["id"])
    return ids


def command_entrypoints(root: Path = ROOT) -> dict[str, str]:
    """Map each native_command entrypoint target to the module that declares it."""

    registry = json.loads((root / "first_party/registry.json").read_text(encoding="utf-8"))
    owners: dict[str, str] = {}
    for entry in registry["modules"]:
        manifest = json.loads((root / entry).read_text(encoding="utf-8"))
        for entrypoint in manifest["entrypoints"]:
            if entrypoint["type"] == "native_command":
                owners[entrypoint["target"]] = manifest["id"]
    return owners


def validate_command(command: object, surfaces: list[str], modules: set[str]) -> str:
    if not isinstance(command, dict):
        raise CommandRegistryError("command entries must be objects")
    missing = sorted(REQUIRED_KEYS - command.keys())
    unknown = sorted(command.keys() - REQUIRED_KEYS)
    if missing or unknown:
        raise CommandRegistryError(f"command keys missing={missing}, unknown={unknown}")

    command_id = command["id"]
    if not isinstance(command_id, str):
        raise CommandRegistryError("command id must be a string")
    segments = command_id.split(".")
    if len(segments) < 2 or any(not SEGMENT.fullmatch(part) for part in segments):
        raise CommandRegistryError(f"invalid command id: {command_id}")
    if segments[0] not in surfaces:
        raise CommandRegistryError(f"command id uses an undeclared surface: {command_id}")

    summary = command["summary"]
    if not isinstance(summary, str) or not summary.strip() or not summary.endswith("."):
        raise CommandRegistryError(f"{command_id}: summary must be a sentence ending in a period")

    owner = command["owner"]
    if owner != CHROMIUM_OWNER and owner not in modules:
        raise CommandRegistryError(f"{command_id}: owner must be chromium or a registered module")

    availability = command["availability"]
    if not isinstance(availability, str) or not availability.strip() or not availability.endswith("."):
        raise CommandRegistryError(f"{command_id}: availability must be a sentence ending in a period")

    guard = command["guard"]
    if guard is not None:
        if not isinstance(guard, str) or not GUARD.fullmatch(guard):
            raise CommandRegistryError(f"{command_id}: guard must look like scripts.module:callable")
        module_name, _, attribute = guard.partition(":")
        try:
            resolved = getattr(importlib.import_module(module_name), attribute)
        except (ImportError, AttributeError) as error:
            raise CommandRegistryError(f"{command_id}: guard does not resolve: {error}") from error
        if not callable(resolved):
            raise CommandRegistryError(f"{command_id}: guard is not callable")
        if owner == CHROMIUM_OWNER:
            raise CommandRegistryError(f"{command_id}: a Chromium-owned command cannot carry a Sunshine guard")

    telemetry = command["telemetry"]
    if not isinstance(telemetry, str) or not TELEMETRY.fullmatch(telemetry):
        raise CommandRegistryError(f"{command_id}: invalid telemetry name")
    if telemetry != expected_telemetry(command_id):
        raise CommandRegistryError(
            f"{command_id}: telemetry must be {expected_telemetry(command_id)}, not {telemetry}"
        )

    errors = command["errors"]
    if not isinstance(errors, list) or any(not isinstance(e, str) or not SEGMENT.fullmatch(e) for e in errors):
        raise CommandRegistryError(f"{command_id}: errors must be snake_case tokens")
    if len(errors) != len(set(errors)):
        raise CommandRegistryError(f"{command_id}: duplicate error result")
    return command_id


def documented_commands(surfaces: list[str], docs: Path = DOCS) -> set[str]:
    found: set[str] = set()
    for path in sorted(docs.rglob("*.md")):
        for token in DOC_TOKEN.findall(path.read_text(encoding="utf-8")):
            if token.split(".")[0] in surfaces:
                found.add(token)
    return found


def validate(root: Path = ROOT) -> int:
    payload = load(root / "first_party/commands.json")
    surfaces = payload["surfaces"]
    modules = module_ids(root)

    ids: list[str] = []
    telemetry_names: set[str] = set()
    for command in payload["commands"]:
        command_id = validate_command(command, surfaces, modules)
        if command_id in ids:
            raise CommandRegistryError(f"duplicate command id: {command_id}")
        if command["telemetry"] in telemetry_names:
            raise CommandRegistryError(f"duplicate telemetry name: {command['telemetry']}")
        ids.append(command_id)
        telemetry_names.add(command["telemetry"])
    if ids != sorted(ids):
        raise CommandRegistryError("commands must be sorted by id")

    registered = set(ids)
    owned_by = {c["id"]: c["owner"] for c in payload["commands"]}

    # A Sunshine-owned command must be claimed by exactly one module. The module
    # validator already rejects duplicate entrypoint targets, so declaring the
    # command there is what makes "one authoritative implementation" enforceable.
    entrypoints = command_entrypoints(root)
    for command_id, owner in owned_by.items():
        if owner == CHROMIUM_OWNER:
            if command_id in entrypoints:
                raise CommandRegistryError(f"{command_id}: Chromium-owned commands must not be module entrypoints")
            continue
        declared = entrypoints.get(command_id)
        if declared is None:
            raise CommandRegistryError(f"{command_id}: owning module declares no native_command entrypoint")
        if declared != owner:
            raise CommandRegistryError(f"{command_id}: declared by {declared} but owned by {owner}")
    unregistered = sorted(set(entrypoints) - registered)
    if unregistered:
        raise CommandRegistryError(f"module entrypoints for unregistered commands: {unregistered}")

    # Only one direction is checked. Requiring every command to also appear in
    # prose would force the duplicated lists this registry exists to replace;
    # the registry entry is the command's documentation. What must not happen is
    # a document naming a command that does not exist, which is how
    # `view.split.toggle` outlived the split-view contract that replaced it.
    unknown_in_docs = sorted(documented_commands(surfaces, root / "docs") - registered)
    if unknown_in_docs:
        raise CommandRegistryError(f"docs reference unregistered commands: {unknown_in_docs}")

    return len(ids)


def main() -> int:
    try:
        count = validate()
    except (OSError, json.JSONDecodeError, CommandRegistryError) as error:
        print(error, file=sys.stderr)
        return 1
    print(f"Command registry passed: {count} command(s).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
