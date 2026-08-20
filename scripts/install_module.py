#!/usr/bin/env python3
"""Install a Sunshine module package from a zip or a folder.

This is the install pipeline `docs/MODULE_PACKAGE_CONTRACT.md` describes, with a
command line on it instead of a button. The button is one Chromium patch away
and the pipeline behind it is the same one: `scripts/module_package.py` decides
what a package is, what installing does, and what is refused, and both front
ends call it rather than each implementing half of it.

    scripts/install_module.py validate first_party/templates/module-package
    scripts/install_module.py install ~/Downloads/notes.zip --profile <profile>
    scripts/install_module.py install ./my-module --unpacked --profile <profile>
    scripts/install_module.py list --profile <profile>
    scripts/install_module.py disable acme.notes --profile <profile>
    scripts/install_module.py remove acme.notes --profile <profile>
    scripts/install_module.py verify --profile <profile>

`--profile` is a Chromium profile directory -- the one holding `Preferences` --
because an installed module is profile state. It defaults to `$SUNSHINE_PROFILE`
when that is set, and there is no built-in default beyond it: guessing a path
and writing into it is the one mistake an installer cannot take back.

Exit status is 0 when the command succeeded, 1 when it was refused (the refusal
code is the first word of the message), and 2 when the invocation was wrong.
"""

from __future__ import annotations

import argparse
import importlib.util
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]

_MODEL = None


def _model():
    """The one loaded copy of the model.

    Cached rather than loaded per call, and not for speed: `PackageError` raised
    by one execution of the module is a different class from the same name in
    another, so a second load would make `except model.PackageError` in main()
    stop catching the refusals every command raises.
    """

    global _MODEL
    if _MODEL is not None:
        return _MODEL
    path = ROOT / "scripts/module_package.py"
    spec = importlib.util.spec_from_file_location("module_package", path)
    if spec is None or spec.loader is None:  # pragma: no cover - packaging error
        raise RuntimeError("unable to load scripts/module_package.py")
    module = importlib.util.module_from_spec(spec)
    # Registered before it is executed: a dataclass defined in a module that is
    # not in sys.modules cannot resolve its own annotations, and fails at import
    # rather than at use.
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    _MODEL = module
    return module


def _profile(arguments: argparse.Namespace, parser: argparse.ArgumentParser) -> Path:
    chosen = arguments.profile or os.environ.get("SUNSHINE_PROFILE")
    if not chosen:
        parser.error("a profile directory is required: pass --profile or set SUNSHINE_PROFILE")
    return Path(chosen).expanduser()


def _describe(package, model) -> str:
    summary = model.consent_summary(package)
    grants = summary["grants"]
    lines = [
        f"{summary['display_name']} {summary['version']}  ({summary['id']})",
        f"  {summary['description']}",
        f"  from      {summary['source_path']}",
        f"  contents  {summary['file_count']} files, {summary['total_bytes']} bytes",
        f"  served at {summary['origin']}",
        f"  integrity {summary['integrity']}",
        "  it cannot:",
        f"    use a browser capability   (declares {len(grants['browser_capabilities'])})",
        f"    reach the network          (network: {grants['network']})",
        f"    read or write your files   (filesystem: {grants['filesystem']})",
        f"    hold a credential          (direct access: {grants['credentials']})",
    ]
    return "\n".join(lines)


def command_validate(arguments: argparse.Namespace, parser: argparse.ArgumentParser) -> int:
    model = _model()
    package = model.read_package(Path(arguments.package).expanduser())
    print(_describe(package, model))
    print("\nThis package can be installed.")
    return 0


def command_install(arguments: argparse.Namespace, parser: argparse.ArgumentParser) -> int:
    model = _model()
    profile = _profile(arguments, parser)
    source = Path(arguments.package).expanduser()
    package = model.read_package(source)
    print(_describe(package, model))
    module = model.install(
        source,
        profile,
        unpacked=arguments.unpacked,
        reinstall=arguments.reinstall,
        enabled=not arguments.disabled,
    )
    where = model.InstallStore(profile).directory(module)
    print(f"\nInstalled {module.id} {module.version} ({module.source}) into {where}")
    return 0


def command_list(arguments: argparse.Namespace, parser: argparse.ArgumentParser) -> int:
    model = _model()
    store = model.InstallStore(_profile(arguments, parser))
    modules = store.read()
    if not modules:
        print("No modules are installed in this profile.")
        return 0
    for module in modules:
        mark = "on " if module.enabled else "off"
        print(f"[{mark}] {module.id:32} {module.version:10} {module.source:8} {module.display_name}")
    return 0


def command_remove(arguments: argparse.Namespace, parser: argparse.ArgumentParser) -> int:
    model = _model()
    module = model.uninstall(arguments.id, _profile(arguments, parser))
    kept = " (its folder was left where it is)" if module.source == "unpacked" else ""
    print(f"Removed {module.id} {module.version}{kept}")
    return 0


def command_enable(arguments: argparse.Namespace, parser: argparse.ArgumentParser) -> int:
    model = _model()
    module = model.set_enabled(arguments.id, _profile(arguments, parser), arguments.enabled)
    print(f"{module.id} is now {'enabled' if module.enabled else 'disabled'}")
    return 0


def command_verify(arguments: argparse.Namespace, parser: argparse.ArgumentParser) -> int:
    model = _model()
    problems = model.verify_installed(_profile(arguments, parser))
    if problems:
        print("\n".join(problems), file=sys.stderr)
        return 1
    print("Every installed module still matches what was installed.")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    subcommands = parser.add_subparsers(dest="command", required=True)

    # `validate` is the one command that reads a package without touching a
    # profile, so it is also the one command that does not take --profile.
    # Every other subcommand inherits the flag from here rather than declaring
    # it, which keeps the default (and $SUNSHINE_PROFILE) in one place.
    profile = argparse.ArgumentParser(add_help=False)
    profile.add_argument("--profile", help="the Chromium profile directory to install into")

    check = subcommands.add_parser("validate", help="check a package without installing it")
    check.add_argument("package", help="a package folder or zip")
    check.set_defaults(run=command_validate)

    add = subcommands.add_parser("install", help="validate a package and install it", parents=[profile])
    add.add_argument("package", help="a package folder or zip")
    add.add_argument("--unpacked", action="store_true",
                     help="serve the folder where it is instead of copying it (for authoring)")
    add.add_argument("--reinstall", action="store_true",
                     help="replace an installed module with the same or an older version")
    add.add_argument("--disabled", action="store_true", help="install without enabling")
    add.set_defaults(run=command_install)

    listing = subcommands.add_parser("list", help="what is installed in this profile", parents=[profile])
    listing.set_defaults(run=command_list)

    drop = subcommands.add_parser("remove", help="uninstall a module", parents=[profile])
    drop.add_argument("id")
    drop.set_defaults(run=command_remove)

    on = subcommands.add_parser("enable", help="serve an installed module again", parents=[profile])
    on.add_argument("id")
    on.set_defaults(run=command_enable, enabled=True)

    off = subcommands.add_parser("disable", help="stop serving an installed module", parents=[profile])
    off.add_argument("id")
    off.set_defaults(run=command_enable, enabled=False)

    audit = subcommands.add_parser("verify", help="re-check every installed module", parents=[profile])
    audit.set_defaults(run=command_verify)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    arguments = parser.parse_args(argv)
    model = _model()
    try:
        return arguments.run(arguments, parser)
    except model.PackageError as error:
        print(str(error), file=sys.stderr)
        return 1
    except OSError as error:
        print(f"REFUSED: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
