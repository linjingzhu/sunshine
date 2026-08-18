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

    def test_remote_content_is_rejected(self) -> None:
        manifest = json.loads(
            (ROOT / "first_party/templates/module.example.json").read_text(encoding="utf-8")
        )
        manifest["security"]["remote_content"] = True
        with self.assertRaisesRegex(self.validator.ModuleValidationError, "remote content"):
            self.validator.validate_manifest(manifest, "fixture")

    def test_network_access_is_fail_closed_until_allowlists_exist(self) -> None:
        manifest = json.loads(
            (ROOT / "first_party/templates/module.example.json").read_text(encoding="utf-8")
        )
        manifest["security"]["network"] = {"access": "allowlist", "allow": ["api.example.com"]}
        with self.assertRaisesRegex(self.validator.ModuleValidationError, "host-allowlist"):
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

    def test_scoped_file_access_is_refused_until_a_broker_exists(self) -> None:
        """Enforces: SEC-8."""

        manifest = self._template()
        manifest["security"]["filesystem"] = {"access": "user_selected"}
        with self.assertRaisesRegex(self.validator.ModuleValidationError, "file-broker"):
            self.validator.validate_manifest(manifest, "fixture")

    def test_a_wildcard_host_is_not_a_host(self) -> None:
        """Enforces: SEC-6.

        `*` and `*.com` are the shapes the allowlist exists to keep out. They
        are rejected on their shape, before the allowlist gate, so the message
        names the real problem rather than the missing contract.
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
