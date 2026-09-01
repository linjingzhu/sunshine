"""Regression tests for the Sunshine first-party module contract."""

from pathlib import Path
import importlib.util
import json
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/validate_first_party_modules.py"


def load_validator():
    spec = importlib.util.spec_from_file_location("validate_first_party_modules", SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError("unable to load module validator")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class FirstPartyModuleTests(unittest.TestCase):
    def setUp(self) -> None:
        self.validator = load_validator()

    def test_repository_registry_is_valid(self) -> None:
        self.assertGreaterEqual(self.validator.validate(ROOT), 1)

    def test_new_tab_is_prepared_not_runtime_verified(self) -> None:
        manifest = json.loads(
            (ROOT / "first_party/modules/sunshine-new-tab/module.json").read_text(encoding="utf-8")
        )
        self.assertEqual("prepared", manifest["status"])
        self.assertEqual("pending", manifest["verification"]["native_build"])
        self.assertFalse(manifest["security"]["remote_content"])

    def test_runtime_claim_requires_native_evidence(self) -> None:
        manifest = json.loads(
            (ROOT / "first_party/templates/module.example.json").read_text(encoding="utf-8")
        )
        manifest["status"] = "runtime_verified"
        with self.assertRaisesRegex(self.validator.ModuleValidationError, "native build"):
            self.validator.validate_manifest(manifest, "fixture")

    # --- MH-7: both languages, or neither ---------------------------------

    def template(self) -> dict:
        return json.loads(
            (ROOT / "first_party/templates/module.example.json").read_text(encoding="utf-8")
        )

    def test_one_language_is_refused(self) -> None:
        """Enforces: MH-7.

        The defect this rule exists for. A fallback would make this manifest
        load, the switch would appear to work, and the missing paragraph would
        show the other language's text with nothing anywhere saying so.
        """

        for missing in ("ko", "en"):
            with self.subTest(missing=missing):
                manifest = self.template()
                del manifest["description"][missing]
                with self.assertRaisesRegex(
                        self.validator.ModuleValidationError, "exactly"):
                    self.validator.validate_manifest(manifest, "fixture")

    def test_a_third_language_is_refused(self) -> None:
        """Enforces: MH-7. Two languages is the rule, not a minimum."""

        manifest = self.template()
        manifest["description"]["ja"] = "説明"
        with self.assertRaisesRegex(self.validator.ModuleValidationError, "exactly"):
            self.validator.validate_manifest(manifest, "fixture")

    def test_a_description_that_is_a_bare_string_is_refused(self) -> None:
        """Enforces: MH-7. The pre-MH-7 shape must not pass silently."""

        manifest = self.template()
        manifest["description"] = "What this module does."
        with self.assertRaisesRegex(
                self.validator.ModuleValidationError, "object of languages"):
            self.validator.validate_manifest(manifest, "fixture")

    def test_an_empty_description_is_refused(self) -> None:
        """Enforces: MH-7. A present-but-blank key is a missing translation."""

        manifest = self.template()
        manifest["description"]["ko"] = "   "
        with self.assertRaisesRegex(self.validator.ModuleValidationError, "non-empty"):
            self.validator.validate_manifest(manifest, "fixture")

    def test_a_description_over_the_limit_is_refused(self) -> None:
        """Enforces: MH-7."""

        manifest = self.template()
        manifest["description"]["en"] = "a" * (self.validator.DESCRIPTION_LIMIT + 1)
        with self.assertRaisesRegex(self.validator.ModuleValidationError, "characters"):
            self.validator.validate_manifest(manifest, "fixture")

    def test_markup_in_a_description_is_refused(self) -> None:
        """Enforces: MH-7.

        The page places it with textContent, so a tag here is inert rather than
        dangerous. It is still refused: a description carrying markup is one
        somebody wrote expecting it to render, on a privileged surface.
        """

        manifest = self.template()
        manifest["description"]["en"] = "What this <b>module</b> does."
        with self.assertRaisesRegex(self.validator.ModuleValidationError, "markup"):
            self.validator.validate_manifest(manifest, "fixture")

    def test_every_shipped_module_carries_both(self) -> None:
        """Enforces: MH-7. The rule, against the modules that exist."""

        registry = json.loads(
            (ROOT / "first_party/registry.json").read_text(encoding="utf-8"))
        for relative in registry["modules"]:
            manifest = json.loads((ROOT / relative).read_text(encoding="utf-8"))
            with self.subTest(module=manifest["id"]):
                self.assertEqual({"en", "ko"}, set(manifest["description"]))
                self.assertNotEqual(
                    manifest["description"]["ko"], manifest["description"]["en"],
                    "neither language may be derived from the other")

    def test_remote_content_is_rejected(self) -> None:
        manifest = json.loads(
            (ROOT / "first_party/templates/module.example.json").read_text(encoding="utf-8")
        )
        manifest["security"]["remote_content"] = True
        with self.assertRaisesRegex(self.validator.ModuleValidationError, "remote content"):
            self.validator.validate_manifest(manifest, "fixture")

    def test_a_concrete_allowlist_is_admitted(self) -> None:
        """Enforces: HA-2, HA-4.

        This was a blanket refusal until ADR 0016. The refusal was a
        placeholder for `docs/HOST_ALLOWLIST_CONTRACT.md`, which now exists, so
        what replaced it is the contract's terms rather than nothing.
        """

        manifest = self._template()
        manifest["security"]["network"] = {
            "access": "allowlist", "allow": ["api.example.com"]
        }
        self.validator.validate_manifest(manifest, "fixture")

    def test_an_empty_allowlist_is_a_module_that_meant_deny(self) -> None:
        """Enforces: HA-4.

        Not pedantry: the module home shows the user what a module may reach,
        and `allowlist` with nothing on it reads as a capability held.
        """

        manifest = self._template()
        manifest["security"]["network"] = {"access": "allowlist", "allow": []}
        with self.assertRaisesRegex(self.validator.ModuleValidationError, "declare deny"):
            self.validator.validate_manifest(manifest, "fixture")

    def test_reaching_a_host_is_not_authenticating_to_one(self) -> None:
        """Enforces: HA-5.

        HA-5 says an allowlisted host is not an authenticated one. It is
        unreachable while SEC-7's rule is unconditional, and that is the point
        of this test: it pins *why* it is unreachable, so that moving SEC-7
        fails here rather than silently making HA-5 load-bearing and unchecked.
        """

        manifest = self._template()
        manifest["security"]["network"] = {
            "access": "allowlist", "allow": ["api.example.com"]
        }
        manifest["security"]["credentials"] = {"direct_access": True}
        with self.assertRaisesRegex(self.validator.ModuleValidationError, "credential"):
            self.validator.validate_manifest(manifest, "fixture")

    def test_capabilities_require_chromium_namespace(self) -> None:
        """Enforces: SEC-4.

        A capability outside `chromium.*` is a privilege Chromium did not
        grant, which makes it Sunshine interposing rather than integrating.
        """

        manifest = json.loads(
            (ROOT / "first_party/templates/module.example.json").read_text(encoding="utf-8")
        )
        manifest["capabilities"] = [{"name": "sunshine.ambient_tabs", "access": "read"}]
        with self.assertRaisesRegex(self.validator.ModuleValidationError, "chromium"):
            self.validator.validate_manifest(manifest, "fixture")

    def _template(self) -> dict:
        import json as _json
        return _json.loads(
            (ROOT / "first_party/templates/module.example.json").read_text(encoding="utf-8")
        )

    # --- Schema 2 module security contract ----------------------------------
    #
    # `docs/SECURITY_ARCHITECTURE_CONTRACT.md` requires every module to state
    # its network, filesystem and credential position rather than leaving it
    # implied. A manifest silent about credentials reads the same as one that
    # was never asked, which is why the keys are required rather than optional.

    def test_a_module_never_receives_a_credential_directly(self) -> None:
        """Enforces: SEC-7."""

        manifest = self._template()
        manifest["security"]["credentials"] = {"direct_access": True}
        with self.assertRaisesRegex(self.validator.ModuleValidationError, "credential"):
            self.validator.validate_manifest(manifest, "fixture")

    def test_scoped_file_access_is_admitted(self) -> None:
        """Enforces: SEC-8.

        Refused outright until ADR 0016, pending
        `docs/FILE_BROKER_CONTRACT.md`. That contract now exists, and nothing
        else about `user_selected` is decidable from a manifest: its terms are
        about a grant, and a manifest declares only that the module may ask for
        one. FB-9 -- declaring the capability is not holding it.
        """

        manifest = self._template()
        manifest["security"]["filesystem"] = {"access": "user_selected"}
        self.validator.validate_manifest(manifest, "fixture")

    def test_an_unknown_filesystem_value_is_still_refused(self) -> None:
        """Admitting one value is not admitting the field."""

        manifest = self._template()
        manifest["security"]["filesystem"] = {"access": "full"}
        with self.assertRaisesRegex(self.validator.ModuleValidationError, "filesystem access"):
            self.validator.validate_manifest(manifest, "fixture")

    def test_a_wildcard_host_is_not_a_host(self) -> None:
        """Enforces: SEC-6, HA-2.

        `*` and `*.com` are the shapes the allowlist exists to keep out, and
        since ADR 0016 lifted the blanket refusal this is the check that keeps
        an admitted allowlist meaningful. A wildcard hands the choice of host
        to whoever controls the zone, turning a decision the owner made into
        one an outside party makes.
        """

        for host in ("*", "*.com", "https://api.github.com", "api.github.com/repos"):
            with self.subTest(host=host):
                manifest = self._template()
                manifest["security"]["network"] = {"access": "allowlist", "allow": [host]}
                with self.assertRaisesRegex(self.validator.ModuleValidationError, "concrete host"):
                    self.validator.validate_manifest(manifest, "fixture")

    def test_denying_the_network_while_listing_hosts_is_incoherent(self) -> None:
        """Enforces: SEC-6."""

        manifest = self._template()
        manifest["security"]["network"] = {"access": "deny", "allow": ["api.github.com"]}
        with self.assertRaisesRegex(self.validator.ModuleValidationError, "deny but hosts"):
            self.validator.validate_manifest(manifest, "fixture")

    def test_a_missing_security_statement_is_rejected(self) -> None:
        """Enforces: SEC-5, SEC-6, SEC-7, SEC-8.

        Silence is not a default. Dropping any one key fails, so a module
        cannot acquire a position by omitting the question.
        """

        for key in ("network", "filesystem", "credentials", "remote_content"):
            with self.subTest(key=key):
                manifest = self._template()
                del manifest["security"][key]
                with self.assertRaisesRegex(
                    self.validator.ModuleValidationError, "invalid security declaration"
                ):
                    self.validator.validate_manifest(manifest, "fixture")

    def test_every_shipped_manifest_states_the_full_security_contract(self) -> None:
        """Enforces: SEC-5, SEC-6, SEC-7, SEC-8, SECA-7."""

        import json as _json
        for path in sorted((ROOT / "first_party/modules").glob("*/module.json")):
            with self.subTest(module=path.parent.name):
                security = _json.loads(path.read_text(encoding="utf-8"))["security"]
                self.assertFalse(security["remote_content"])
                self.assertEqual("deny", security["network"]["access"])
                self.assertEqual("none", security["filesystem"]["access"])
                self.assertFalse(security["credentials"]["direct_access"])

    def test_unregistered_manifest_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "first_party/modules/one").mkdir(parents=True)
            (root / "first_party/modules/two").mkdir(parents=True)
            template = (ROOT / "first_party/templates/module.example.json").read_text(encoding="utf-8")
            (root / "first_party/modules/one/module.json").write_text(template, encoding="utf-8")
            (root / "first_party/modules/two/module.json").write_text(template, encoding="utf-8")
            (root / "first_party/registry.json").write_text(
                json.dumps({"schema_version": 2, "modules": ["first_party/modules/one/module.json"]}),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(self.validator.ModuleValidationError, "unregistered"):
                self.validator.registered_paths(root)


if __name__ == "__main__":
    unittest.main()
