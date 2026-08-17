"""Contract tests for the Sunshine command registry."""

from __future__ import annotations

import copy
import importlib.util
import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "validate_commands.py"


def load_validator():
    spec = importlib.util.spec_from_file_location("validate_commands", SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load command registry validator: {SCRIPT}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class CommandRegistryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.validator = load_validator()
        self.registry = json.loads((ROOT / "first_party/commands.json").read_text(encoding="utf-8"))
        self.commands = {command["id"]: command for command in self.registry["commands"]}

    def test_the_real_registry_validates(self) -> None:
        self.assertEqual(len(self.commands), self.validator.validate(ROOT))

    def test_every_command_carries_what_the_rule_requires(self) -> None:
        """One implementation, an availability predicate, telemetry, an error result."""

        for command_id, command in self.commands.items():
            with self.subTest(command=command_id):
                self.assertTrue(command["owner"])
                self.assertTrue(command["availability"].endswith("."))
                self.assertTrue(command["telemetry"])
                self.assertIsInstance(command["errors"], list)

    def test_telemetry_is_derived_so_it_cannot_drift(self) -> None:
        for command_id, command in self.commands.items():
            with self.subTest(command=command_id):
                self.assertEqual(self.validator.expected_telemetry(command_id), command["telemetry"])

    def test_sunshine_guards_resolve_to_real_callables(self) -> None:
        """A guard names the code that enforces the command's availability."""

        guarded = {i: c["guard"] for i, c in self.commands.items() if c["guard"]}
        self.assertIn("view.split.open", guarded)
        self.assertIn("workspace.close", guarded)
        for command_id, guard in guarded.items():
            with self.subTest(command=command_id):
                module_name, _, attribute = guard.partition(":")
                module = importlib.import_module(module_name)
                self.assertTrue(callable(getattr(module, attribute)))

    def test_chromium_owned_commands_carry_no_sunshine_implementation(self) -> None:
        for command_id, command in self.commands.items():
            if command["owner"] != "chromium":
                continue
            with self.subTest(command=command_id):
                self.assertIsNone(command["guard"])

    def test_each_sunshine_command_has_exactly_one_owning_module(self) -> None:
        entrypoints = self.validator.command_entrypoints(ROOT)
        for command_id, command in self.commands.items():
            owner = command["owner"]
            with self.subTest(command=command_id):
                if owner == "chromium":
                    self.assertNotIn(command_id, entrypoints)
                else:
                    self.assertEqual(owner, entrypoints.get(command_id))

    def _rejects(self, mutate) -> None:
        payload = copy.deepcopy(self.registry)
        mutate(payload)
        surfaces = payload["surfaces"]
        modules = self.validator.module_ids(ROOT)
        with self.assertRaises(self.validator.CommandRegistryError):
            for command in payload["commands"]:
                self.validator.validate_command(command, surfaces, modules)

    def test_a_drifting_telemetry_name_is_rejected(self) -> None:
        self._rejects(lambda p: p["commands"][0].update(telemetry="Sunshine.Command.Wrong"))

    def test_an_undeclared_surface_is_rejected(self) -> None:
        self._rejects(lambda p: p["commands"][0].update(id="gadget.launch"))

    def test_an_unknown_owner_is_rejected(self) -> None:
        self._rejects(lambda p: p["commands"][0].update(owner="sunshine.nonexistent"))

    def test_a_guard_that_does_not_resolve_is_rejected(self) -> None:
        self._rejects(
            lambda p: p["commands"][0].update(owner="sunshine.workspace", guard="scripts.workspace_model:nope")
        )

    def test_documentation_naming_an_unregistered_command_is_rejected(self) -> None:
        """This is how a superseded split-view command outlived its contract."""

        documented = self.validator.documented_commands(self.registry["surfaces"], ROOT / "docs")
        self.assertLessEqual(documented, set(self.commands))
        self.assertIn("view.split.open", documented)

    def test_the_contract_table_and_the_registry_agree(self) -> None:
        contract = (ROOT / "docs/TAB_WORKSPACE_SPLIT_CONTRACT.md").read_text(encoding="utf-8")
        for command_id in (
            "tab.group.create",
            "tab.group.ungroup",
            "workspace.create",
            "workspace.switch",
            "workspace.tab.move",
            "workspace.close",
            "view.split.open",
            "view.split.swap",
            "view.split.close",
        ):
            with self.subTest(command=command_id):
                self.assertIn(f"`{command_id}`", contract)
                self.assertIn(command_id, self.commands)


if __name__ == "__main__":
    unittest.main()
