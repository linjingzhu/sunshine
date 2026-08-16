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
        manifest["security"]["network_access"] = True
        with self.assertRaisesRegex(self.validator.ModuleValidationError, "host-allowlist"):
            self.validator.validate_manifest(manifest, "fixture")

    def test_capabilities_require_chromium_namespace(self) -> None:
        manifest = json.loads(
            (ROOT / "first_party/templates/module.example.json").read_text(encoding="utf-8")
        )
        manifest["capabilities"] = [{"name": "sunshine.ambient_tabs", "access": "read"}]
        with self.assertRaisesRegex(self.validator.ModuleValidationError, "chromium"):
            self.validator.validate_manifest(manifest, "fixture")

    def test_unregistered_manifest_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "first_party/modules/one").mkdir(parents=True)
            (root / "first_party/modules/two").mkdir(parents=True)
            template = (ROOT / "first_party/templates/module.example.json").read_text(encoding="utf-8")
            (root / "first_party/modules/one/module.json").write_text(template, encoding="utf-8")
            (root / "first_party/modules/two/module.json").write_text(template, encoding="utf-8")
            (root / "first_party/registry.json").write_text(
                json.dumps({"schema_version": 1, "modules": ["first_party/modules/one/module.json"]}),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(self.validator.ModuleValidationError, "unregistered"):
                self.validator.registered_paths(root)


if __name__ == "__main__":
    unittest.main()
