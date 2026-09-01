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

    def test_sunshine_implementations_resolve_to_real_callables(self) -> None:
        """`implementation` names the code that performs the command."""

        implemented = {i: c["implementation"] for i, c in self.commands.items() if c["implementation"]}
        self.assertIn("workspace.close", implemented)
        self.assertIn("workspace.tab.move", implemented)
        for command_id, reference in implemented.items():
            with self.subTest(command=command_id):
                module_name, _, attribute = reference.partition(":")
                module = importlib.import_module(module_name)
                self.assertTrue(callable(getattr(module, attribute)))

    def test_a_predicate_only_returns_reasons_it_declared(self) -> None:
        """The check the old `guard` field could not support.

        A predicate answers whether a command may be offered, and the surface
        shows its return value to the user. A token it returns but never
        declared is a reason with no copy, no translation and no review. This
        calls each predicate with inputs chosen to make it refuse.
        """

        import workspace_model as workspace

        empty = workspace.default_catalog()
        only = empty.workspaces[0].id
        absent = "00000000-0000-4000-8000-000000000000"

        refusals = {
            "workspace.close": workspace.can_close_workspace(empty, only),
            "workspace.tab.move": workspace.can_move_tabs(empty, absent),
        }

        for command_id, reason in refusals.items():
            with self.subTest(command=command_id):
                declared = self.commands[command_id]["unavailable_reasons"]
                self.assertIsNotNone(reason, "the predicate was expected to refuse this input")
                self.assertIn(reason, declared)

    def test_a_predicate_returns_none_when_the_command_is_available(self) -> None:
        """None means available. A predicate that never says yes disables a
        command permanently, which no test of its refusals would catch."""

        import workspace_model as workspace

        catalog = workspace.default_catalog()
        self.assertIsNone(workspace.can_move_tabs(catalog, catalog.workspaces[0].id))

    def test_chromium_owned_commands_carry_no_sunshine_code(self) -> None:
        """No Sunshine *code*. Declarations are a different thing.

        This asserted an empty `unavailable_reasons` until 2026-08-31, which
        made the palette contract's §4.2 unsatisfiable for twenty of the
        twenty-six commands: their availability is evaluated on the Chromium
        side, and that section requires the verdicts to be drawn from a token
        set the registry declares. Refusing the declaration because the code is
        elsewhere confused where a thing is evaluated with whether it is
        described.
        """

        for command_id, command in self.commands.items():
            if command["owner"] != "chromium":
                continue
            with self.subTest(command=command_id):
                self.assertIsNone(command["implementation"])
                self.assertIsNone(command["predicate"])
                self.assertTrue(command["unavailable_reasons"], command_id)

    def test_each_sunshine_command_has_exactly_one_owning_module(self) -> None:
        entrypoints = self.validator.command_entrypoints(ROOT)
        for command_id, command in self.commands.items():
            owner = command["owner"]
            with self.subTest(command=command_id):
                if owner == "chromium":
                    self.assertNotIn(command_id, entrypoints)
                else:
                    self.assertEqual(owner, entrypoints.get(command_id))

    @staticmethod
    def _command(payload: dict, command_id: str) -> dict:
        """The entry for one id, so a mutation targets the command it means to."""

        for command in payload["commands"]:
            if command["id"] == command_id:
                return command
        raise AssertionError(f"{command_id} is not in the registry")

    def _payload(self) -> dict:
        return copy.deepcopy(self.registry)

    def _validate(self, payload: dict) -> None:
        surfaces = payload["surfaces"]
        modules = self.validator.module_ids(ROOT)
        for command in payload["commands"]:
            self.validator.validate_command(command, surfaces, modules)

    def _rejects(self, mutate) -> None:
        payload = self._payload()
        mutate(payload)
        with self.assertRaises(self.validator.CommandRegistryError):
            self._validate(payload)

    def _accepts(self, payload: dict) -> None:
        """A mutation the validator must *not* refuse.

        Every other helper here proves a rule fires. This one proves a rule
        does not, which is the half a guard loses when it is tightened without
        anyone asking what it now forbids.
        """

        self._validate(payload)

    def test_a_drifting_telemetry_name_is_rejected(self) -> None:
        self._rejects(lambda p: p["commands"][0].update(telemetry="Sunshine.Command.Wrong"))

    def test_an_undeclared_surface_is_rejected(self) -> None:
        self._rejects(lambda p: p["commands"][0].update(id="gadget.launch"))

    def test_an_unknown_owner_is_rejected(self) -> None:
        self._rejects(lambda p: p["commands"][0].update(owner="sunshine.nonexistent"))

    def test_an_implementation_that_does_not_resolve_is_rejected(self) -> None:
        self._rejects(
            lambda p: p["commands"][0].update(
                owner="sunshine.workspace", implementation="scripts.workspace_model:nope"
            )
        )

    def test_a_predicate_without_declared_reasons_is_rejected(self) -> None:
        """Half the availability contract is not a contract.

        A predicate with nothing declared cannot explain a disabled command,
        which is the reason the field exists.
        """

        self._rejects(lambda p: self._command(p, "workspace.tab.move").update(unavailable_reasons=[]))

    def test_declared_reasons_without_a_predicate_are_accepted(self) -> None:
        """The coupling runs one way, and it used to run both.

        A predicate must declare what it can return. Reasons without a
        predicate are not a promise nothing can keep -- they are the twenty
        Chromium-owned commands, whose evaluation lives where this repository
        has no Python to point at.
        """

        payload = self._payload()
        self._command(payload, "workspace.tab.move").update(predicate=None)
        self._accepts(payload)

    def test_a_command_with_no_declared_reason_is_rejected(self) -> None:
        """§4.2(6): a disabled row with no reason is a build failure."""

        self._rejects(
            lambda p: self._command(p, "browser.reload").update(unavailable_reasons=[]))

    # --- §2.4: selection must be declared -----------------------------------

    def test_selection_kinds_are_a_closed_set(self) -> None:
        """§2.1: a kind whose values come from a renderer is a payload.

        Widening this set is the security decision §2.2 forbids, so a new kind
        must fail here before it can be spelled in the registry.
        """

        self._rejects(
            lambda p: self._command(p, "workspace.switch").update(
                selection={"kind": "url", "enumerated_by": "sunshine.workspace"}))

    def test_a_selection_enumerated_by_someone_other_than_the_owner_is_rejected(self) -> None:
        """§2.4(2): one owner enumerates and one owner executes."""

        self._rejects(
            lambda p: self._command(p, "workspace.switch").update(
                selection={"kind": "workspace", "enumerated_by": "sunshine.security"}))

    def test_a_chromium_owned_command_cannot_declare_a_selection(self) -> None:
        """Nothing on the Sunshine side enumerates candidates for one."""

        self._rejects(
            lambda p: self._command(p, "tab.close").update(
                selection={"kind": "tab", "enumerated_by": "chromium"}))

    def test_the_three_selection_bearing_commands_are_the_ones_the_contract_names(self) -> None:
        """§2.1's table names them, and a fourth appearing silently is the
        drift that made `workspace.switch` unrenderable in the first place."""

        bearing = {
            command_id
            for command_id, command in self.commands.items()
            if command["selection"] != "none"
        }
        self.assertEqual(
            {"workspace.switch", "workspace.close", "workspace.tab.move"}, bearing)

    # --- Ruling 2: one row, one outcome -------------------------------------

    def test_reload_and_stop_are_separate_commands(self) -> None:
        """§3: a palette row is a static string and cannot show which of two
        opposite outcomes it will produce. One re-fetches, discarding
        uncommitted state; the other preserves what has arrived."""

        self.assertIn("browser.reload", self.commands)
        self.assertIn("browser.stop", self.commands)
        reload_summary = self.commands["browser.reload"]["summary"]
        self.assertNotIn("stop", reload_summary.lower())
        self.assertNotIn(" or ", reload_summary.lower())

    def test_reload_is_available_whenever_a_tab_is(self) -> None:
        """§3: reload means reload in every state, including during a load,
        where it restarts one. Its only unavailable state is having no tab."""

        self.assertEqual(
            ["no_active_tab"], self.commands["browser.reload"]["unavailable_reasons"])

    def test_a_token_that_is_both_a_reason_and_an_error_is_rejected(self) -> None:
        """A reason says it cannot start; an error says it did not finish."""

        self._rejects(
            lambda p: self._command(p, "workspace.tab.move").update(errors=["no_destination_workspace"])
        )

    def test_documentation_naming_an_unregistered_command_is_rejected(self) -> None:
        """This is how a superseded split-view command outlived its contract."""

        documented = self.validator.documented_commands(self.registry["surfaces"], ROOT / "docs")
        self.assertLessEqual(documented, set(self.commands))
        self.assertIn("workspace.tab.move", documented)

    def test_the_contract_table_and_the_registry_agree(self) -> None:
        contract = (ROOT / "docs/TAB_WORKSPACE_SPLIT_CONTRACT.md").read_text(encoding="utf-8")
        for command_id in (
            "tab.group.create",
            "tab.group.ungroup",
            "workspace.create",
            "workspace.switch",
            "workspace.tab.move",
            "workspace.close",
        ):
            with self.subTest(command=command_id):
                self.assertIn(f"`{command_id}`", contract)
                self.assertIn(command_id, self.commands)

    def test_no_split_command_survives_the_native_derivation(self) -> None:
        """ADR 0002: splits are tab-strip state at the pinned revision.

        Chromium owns split identity, layout, ratio, swap, close and session
        persistence (`SessionTab::split_id`, `SessionSplitTab`). Sunshine
        registering its own split commands would put a second owner in front of
        them, and the native swap is strictly larger than the metadata-only one
        Sunshine had -- it reorders the view hierarchy and the active index.
        """

        self.assertFalse([i for i in self.commands if i.startswith("view.split.")])
        self.assertNotIn("view", self.registry["surfaces"])


    def test_an_error_is_not_excluded_by_its_own_availability(self) -> None:
        """An error a command can never reach is not a contract, it is decoration.

        `tab.group.create` declared availability "At least one tab is selected in
        one window." alongside the error `selection_spans_windows`. The
        availability made the error unreachable: if the predicate is enforced,
        the failure it names cannot occur. Availability says when the command is
        offered; errors say how an offered command fails.
        """

        registry = json.loads((ROOT / "first_party/commands.json").read_text(encoding="utf-8"))
        commands = {entry["id"]: entry for entry in registry["commands"]}

        create = commands["tab.group.create"]
        self.assertIn("selection_spans_windows", create["errors"])
        self.assertNotIn("in one window", create["availability"])


if __name__ == "__main__":
    unittest.main()
