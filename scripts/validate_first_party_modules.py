#!/usr/bin/env python3
"""Validate Sunshine first-party module manifests without building Chromium."""

from __future__ import annotations

import json
from pathlib import Path, PurePosixPath
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
ID_PATTERN = re.compile(r"^sunshine\.[a-z0-9]+(?:[._-][a-z0-9]+)*$")
KINDS = {"surface", "service", "integration"}
LIFECYCLES = {"browser", "profile", "window", "tab"}
STATUSES = {"planned", "prepared", "runtime_verified"}
ENTRYPOINT_TYPES = {"chromium_webui", "chromium_webui_overlay", "native_command", "profile_service"}
PROFILE_MODES = {"regular", "incognito", "guest"}
VERIFICATION_STATES = {"pending", "passed", "failed", "not_applicable"}
CAPABILITY_ACCESS = {"read", "write", "decorate", "invoke"}
DATA_OWNERS = {"chromium", "sunshine"}
DATA_SCOPES = {"browser", "profile", "window", "tab"}
DATA_ACCESS = {"read", "write"}
DATA_RETENTION = {"none", "session", "persistent"}
NETWORK_ACCESS = {"deny", "allowlist"}
FILESYSTEM_ACCESS = {"none", "user_selected"}
# A concrete host. No scheme, no path, no wildcard: `*.com` and `*` are the
# shapes SEC-6 exists to keep out of a manifest, and a scheme or path here would
# mean the allowlist was being read as a URL matcher, which it is not.
HOST = re.compile(r"^(?!-)[a-z0-9-]+(?:\.(?!-)[a-z0-9-]+)+$")


class ModuleValidationError(ValueError):
    pass


def registered_paths(root: Path = ROOT) -> list[Path]:
    registry_path = root / "first_party/registry.json"
    try:
        registry = json.loads(registry_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ModuleValidationError(f"cannot read module registry: {error}") from error
    if not isinstance(registry, dict) or registry.get("schema_version") != 2:
        raise ModuleValidationError("registry schema_version must be 2")
    entries = registry.get("modules")
    if not isinstance(entries, list) or not entries:
        raise ModuleValidationError("registry modules must be a non-empty list")
    if len(entries) != len(set(entries)):
        raise ModuleValidationError("registry contains duplicate module paths")
    paths: list[Path] = []
    for entry in entries:
        if not isinstance(entry, str):
            raise ModuleValidationError("module registry paths must be strings")
        pure = PurePosixPath(entry)
        if pure.is_absolute() or ".." in pure.parts or not entry.startswith("first_party/modules/"):
            raise ModuleValidationError(f"invalid module path: {entry}")
        path = root / pure
        if path.name != "module.json" or not path.is_file():
            raise ModuleValidationError(f"registered module manifest missing: {entry}")
        paths.append(path)
    inventory = set((root / "first_party/modules").glob("*/module.json"))
    if set(paths) != inventory:
        missing = sorted(path.relative_to(root).as_posix() for path in inventory - set(paths))
        raise ModuleValidationError(f"unregistered module manifests: {missing}")
    return paths



def validate_security(security: object, source: str) -> None:
    """The module security contract -- SEC-5, SEC-6, SEC-7, SEC-8.

    Schema 2 replaced the `network_access` boolean with a structured
    declaration, and added the filesystem and credential statements that
    `docs/SECURITY_ARCHITECTURE_CONTRACT.md` requires every module to make.
    They are stated per module rather than assumed globally because a manifest
    that is silent about credentials reads the same as one that was never asked.

    `allowlist` and `user_selected` were expressible and refused outright,
    "pending a contract". `docs/decisions/0016-relaxations-for-porting.md` is
    where that ended: the refusal was a placeholder for work nobody had done
    rather than a security position, so the contracts were written and the
    refusals lifted. `docs/HOST_ALLOWLIST_CONTRACT.md` and
    `docs/FILE_BROKER_CONTRACT.md` now carry the terms, and what is checkable
    in a manifest is checked below.

    **This is weaker in kind than what it replaces**, and ADR 0016 says so: a
    value that cannot be declared cannot be misused, and a value that is checked
    can be. The compensation is that the terms are specific and tested rather
    than described, and that neither capability exists in the browser yet -- a
    manifest may now claim them, and nothing acts on the claim.

    Enforces: SEC-5, SEC-6, SEC-7, SEC-8, HA-2, HA-4, HA-5.
    """

    keys = {"remote_content", "requires_user_activation", "profile_modes",
            "network", "filesystem", "credentials"}
    if not isinstance(security, dict) or set(security) != keys:
        raise ModuleValidationError(f"{source}: invalid security declaration")

    for flag in ("remote_content", "requires_user_activation"):
        if not isinstance(security[flag], bool):
            raise ModuleValidationError(f"{source}: security flags must be booleans")
    if security["remote_content"]:
        raise ModuleValidationError(f"{source}: first-party privileged surfaces cannot host remote content")

    modes = security["profile_modes"]
    if not isinstance(modes, list) or not modes or not set(modes) <= PROFILE_MODES:
        raise ModuleValidationError(f"{source}: invalid profile modes")

    network = security["network"]
    if not isinstance(network, dict) or set(network) != {"access", "allow"}:
        raise ModuleValidationError(f"{source}: invalid network declaration")
    if network["access"] not in NETWORK_ACCESS:
        raise ModuleValidationError(f"{source}: network access must be one of {sorted(NETWORK_ACCESS)}")
    allow = network["allow"]
    if not isinstance(allow, list) or any(not isinstance(host, str) for host in allow):
        raise ModuleValidationError(f"{source}: network allow must be a list of hosts")
    if network["access"] == "deny" and allow:
        raise ModuleValidationError(f"{source}: network access is deny but hosts are listed")
    for host in allow:
        if not HOST.fullmatch(host):
            raise ModuleValidationError(f"{source}: not a concrete host: {host!r}")
    # HA-4. `allowlist` with nothing on it is not a narrower allowlist, it is a
    # module that should have said `deny` -- and the difference matters because
    # the module home shows the user what a module may reach.
    if network["access"] == "allowlist" and not allow:
        raise ModuleValidationError(
            f"{source}: network access is allowlist with no hosts; declare deny instead"
        )

    filesystem = security["filesystem"]
    if not isinstance(filesystem, dict) or set(filesystem) != {"access"}:
        raise ModuleValidationError(f"{source}: invalid filesystem declaration")
    if filesystem["access"] not in FILESYSTEM_ACCESS:
        raise ModuleValidationError(f"{source}: filesystem access must be one of {sorted(FILESYSTEM_ACCESS)}")
    # `user_selected` is admitted by docs/FILE_BROKER_CONTRACT.md. Nothing else
    # about it is decidable from a manifest: the contract's terms are about a
    # grant, and a manifest declares only that the module may ask for one.
    # FB-9 -- declaring the capability is not holding it.

    credentials = security["credentials"]
    if not isinstance(credentials, dict) or set(credentials) != {"direct_access"}:
        raise ModuleValidationError(f"{source}: invalid credentials declaration")
    # SEC-7, and HA-5 with it: reaching a host is not authenticating to one, so
    # an allowlist does not become an exemption from this. The rule below is
    # unconditional, which is what makes HA-5 unreachable rather than merely
    # unviolated -- `tests/test_first_party_modules.py` pins that.
    if credentials["direct_access"] is not False:
        raise ModuleValidationError(f"{source}: a module never receives a credential directly")


def validate_manifest(manifest: dict, source: str) -> tuple[str, set[str]]:
    required = {"schema_version", "id", "display_name", "owner", "kind", "lifecycle", "status",
                "entrypoints", "capabilities", "data", "security", "verification"}
    missing = sorted(required - manifest.keys())
    unknown = sorted(manifest.keys() - required)
    if missing or unknown:
        raise ModuleValidationError(f"{source}: missing={missing}, unknown={unknown}")
    if manifest["schema_version"] != 2:
        raise ModuleValidationError(f"{source}: schema_version must be 2")
    module_id = manifest["id"]
    if not isinstance(module_id, str) or not ID_PATTERN.fullmatch(module_id):
        raise ModuleValidationError(f"{source}: invalid Sunshine module id")
    if manifest["owner"] != "sunshine":
        raise ModuleValidationError(f"{source}: first-party owner must be sunshine")
    if not isinstance(manifest["display_name"], str) or not manifest["display_name"].strip():
        raise ModuleValidationError(f"{source}: display_name must be non-empty")
    if manifest["kind"] not in KINDS or manifest["lifecycle"] not in LIFECYCLES:
        raise ModuleValidationError(f"{source}: invalid kind or lifecycle")
    if manifest["status"] not in STATUSES:
        raise ModuleValidationError(f"{source}: invalid status")
    entrypoints = manifest["entrypoints"]
    if not isinstance(entrypoints, list) or not entrypoints:
        raise ModuleValidationError(f"{source}: entrypoints must be a non-empty list")
    targets: set[str] = set()
    for entrypoint in entrypoints:
        if not isinstance(entrypoint, dict) or set(entrypoint) != {"type", "target"}:
            raise ModuleValidationError(f"{source}: invalid entrypoint shape")
        if entrypoint["type"] not in ENTRYPOINT_TYPES:
            raise ModuleValidationError(f"{source}: invalid entrypoint type")
        target = entrypoint["target"]
        if not isinstance(target, str) or not target:
            raise ModuleValidationError(f"{source}: entrypoint target must be non-empty")
        if entrypoint["type"].startswith("chromium_webui") and not target.startswith("chrome://"):
            raise ModuleValidationError(f"{source}: WebUI entrypoints must use chrome://")
        if target in targets:
            raise ModuleValidationError(f"{source}: duplicate entrypoint target: {target}")
        targets.add(target)
    if not isinstance(manifest["capabilities"], list) or not isinstance(manifest["data"], list):
        raise ModuleValidationError(f"{source}: capabilities and data must be lists")
    capability_names: set[str] = set()
    for capability in manifest["capabilities"]:
        if not isinstance(capability, dict) or set(capability) != {"name", "access"}:
            raise ModuleValidationError(f"{source}: invalid capability declaration")
        name = capability["name"]
        if not isinstance(name, str) or not name.startswith("chromium."):
            raise ModuleValidationError(f"{source}: capabilities must use the chromium.* namespace")
        if capability["access"] not in CAPABILITY_ACCESS:
            raise ModuleValidationError(f"{source}: invalid capability access")
        if name in capability_names:
            raise ModuleValidationError(f"{source}: duplicate capability: {name}")
        capability_names.add(name)
    for data in manifest["data"]:
        if not isinstance(data, dict) or set(data) != {"owner", "scope", "access", "retention"}:
            raise ModuleValidationError(f"{source}: invalid data declaration")
        if (data["owner"] not in DATA_OWNERS or data["scope"] not in DATA_SCOPES
                or data["access"] not in DATA_ACCESS or data["retention"] not in DATA_RETENTION):
            raise ModuleValidationError(f"{source}: invalid data ownership or lifetime")
    validate_security(manifest["security"], source)
    verification = manifest["verification"]
    if not isinstance(verification, dict) or set(verification) != {"native_build", "runtime", "visual"}:
        raise ModuleValidationError(f"{source}: invalid verification declaration")
    if any(value not in VERIFICATION_STATES for value in verification.values()):
        raise ModuleValidationError(f"{source}: invalid verification state")
    if manifest["status"] == "runtime_verified" and (
        verification["native_build"] != "passed" or verification["runtime"] != "passed"
    ):
        raise ModuleValidationError(f"{source}: runtime_verified requires native build and runtime evidence")
    return module_id, targets


def validate(root: Path = ROOT) -> int:
    ids: set[str] = set()
    targets: set[str] = set()
    for path in registered_paths(root):
        manifest = json.loads(path.read_text(encoding="utf-8"))
        module_id, module_targets = validate_manifest(manifest, path.relative_to(root).as_posix())
        if module_id in ids:
            raise ModuleValidationError(f"duplicate module id: {module_id}")
        overlap = targets & module_targets
        if overlap:
            raise ModuleValidationError(f"duplicate entrypoint targets: {sorted(overlap)}")
        ids.add(module_id)
        targets.update(module_targets)
    return len(ids)


def main() -> int:
    try:
        count = validate()
    except (OSError, json.JSONDecodeError, ModuleValidationError) as error:
        print(error, file=sys.stderr)
        return 1
    print(f"First-party module registry passed: {count} module(s).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
