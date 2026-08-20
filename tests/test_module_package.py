"""What installing a Sunshine module package does, and what it refuses.

The install pipeline is the one part of ADR 0013 that can be run before the
browser can run anything, so it is the part that gets tested rather than
described. Every refusal below is a package a user could plausibly be handed --
an archive that escapes its own directory, a half-built source tree, a page that
pulls a script off the network -- and the test names the code the surface will
show for it.

Enforces: SEC-4, SEC-14.
"""

from pathlib import Path
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
import zipfile

ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / "first_party/templates/module-package"


def load(name: str):
    path = ROOT / "scripts" / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"unable to load scripts/{name}.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


MANIFEST = {
    "schema_version": 3,
    "id": "acme.notes",
    "display_name": "Notes",
    "version": "1.0.0",
    "description": "A test package.",
    "owner": "third_party",
    "kind": "package",
    "entry": "index.html",
    "capabilities": [],
    "security": {
        "remote_content": False,
        "requires_user_activation": True,
        "profile_modes": ["regular"],
        "network": {"access": "deny", "allow": []},
        "filesystem": {"access": "none"},
        "credentials": {"direct_access": False},
    },
}

INDEX = "<!doctype html>\n<html><head><title>Notes</title></head><body></body></html>\n"


class PackageTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.model = load("module_package")
        self.workspace = tempfile.TemporaryDirectory()
        self.addCleanup(self.workspace.cleanup)
        self.root = Path(self.workspace.name)
        self.profile = self.root / "profile"

    # -- helpers

    def folder(self, *, manifest: dict | None = MANIFEST, files: dict | None = None) -> Path:
        """A package folder. `manifest=None` writes no manifest at all."""

        where = Path(tempfile.mkdtemp(dir=self.root))
        if manifest is not None:
            (where / "module.json").write_text(json.dumps(manifest), encoding="utf-8")
        for name, body in ({"index.html": INDEX} | (files or {})).items():
            target = where / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(body, encoding="utf-8")
        return where

    def archive(self, entries: dict[str, str | bytes]) -> Path:
        path = Path(tempfile.mkdtemp(dir=self.root)) / "package.zip"
        with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
            for name, body in entries.items():
                archive.writestr(name, body)
        return path

    def default_archive(self, **overrides) -> Path:
        entries: dict[str, str | bytes] = {
            "module.json": json.dumps(MANIFEST),
            "index.html": INDEX,
        }
        entries.update(overrides)
        return self.archive(entries)

    def refusal(self, source: Path) -> str:
        with self.assertRaises(self.model.PackageError) as caught:
            self.model.read_package(source)
        return caught.exception.code


class ShippedExampleTests(PackageTestCase):
    def test_the_example_package_installs_as_shipped(self) -> None:
        package = self.model.read_package(EXAMPLE)
        self.assertEqual(package.id, "example.scratchpad")
        self.assertEqual(package.manifest["entry"], "index.html")
        self.assertFalse(package.packed)
        self.assertTrue(package.integrity.startswith("sha256:"))

    def test_the_example_is_served_from_an_untrusted_chromium_origin(self) -> None:
        """SEC-13: the origin is Chromium's own scheme with a host inside it."""

        package = self.model.read_package(EXAMPLE)
        self.assertEqual(
            package.url(),
            "chrome-untrusted://sunshine-module/example.scratchpad/index.html",
        )

    def test_the_example_needs_no_build_step(self) -> None:
        shipped = {path.name for path in EXAMPLE.iterdir()}
        self.assertEqual(
            shipped,
            {"module.json", "index.html", "app.css", "app.js", "icon.svg", "README.md"},
        )


class ManifestTests(PackageTestCase):
    def test_a_missing_manifest_is_named_as_such(self) -> None:
        where = self.folder(manifest=None)
        self.assertEqual(self.refusal(where), "MANIFEST_MISSING")

    def test_a_manifest_missing_a_key_is_refused(self) -> None:
        manifest = {key: value for key, value in MANIFEST.items() if key != "description"}
        self.assertEqual(self.refusal(self.folder(manifest=manifest)), "MANIFEST_INVALID")

    def test_an_unknown_key_is_refused(self) -> None:
        self.assertEqual(
            self.refusal(self.folder(manifest=MANIFEST | {"permissions": ["tabs"]})),
            "MANIFEST_INVALID",
        )

    def test_the_first_party_namespace_cannot_be_installed_into(self) -> None:
        """A package may not claim to be one of the compiled capabilities."""

        manifest = MANIFEST | {"id": "sunshine.workspace"}
        self.assertEqual(self.refusal(self.folder(manifest=manifest)), "ID_RESERVED")

    def test_a_package_declares_no_browser_capability(self) -> None:
        """Enforces: SEC-4."""

        manifest = MANIFEST | {"capabilities": [{"name": "chromium.tabs.strip_model",
                                                 "access": "read"}]}
        self.assertEqual(self.refusal(self.folder(manifest=manifest)), "MANIFEST_INVALID")

    def test_network_access_is_refused_by_the_schema_two_rule(self) -> None:
        """The security block is checked by the first-party validator itself."""

        security = MANIFEST["security"] | {"network": {"access": "allowlist",
                                                       "allow": ["example.com"]}}
        manifest = MANIFEST | {"security": security}
        self.assertEqual(self.refusal(self.folder(manifest=manifest)), "MANIFEST_INVALID")

    def test_file_access_is_refused_by_the_schema_two_rule(self) -> None:
        security = MANIFEST["security"] | {"filesystem": {"access": "user_selected"}}
        manifest = MANIFEST | {"security": security}
        self.assertEqual(self.refusal(self.folder(manifest=manifest)), "MANIFEST_INVALID")

    def test_a_version_that_is_not_semver_is_refused(self) -> None:
        self.assertEqual(self.refusal(self.folder(manifest=MANIFEST | {"version": "1.0"})),
                         "MANIFEST_INVALID")

    def test_the_entry_document_has_to_exist(self) -> None:
        manifest = MANIFEST | {"entry": "missing.html"}
        self.assertEqual(self.refusal(self.folder(manifest=manifest)), "ENTRY_MISSING")

    def test_a_declared_icon_has_to_exist(self) -> None:
        manifest = MANIFEST | {"icon": "icon.png"}
        self.assertEqual(self.refusal(self.folder(manifest=manifest)), "ICON_MISSING")


class StructureTests(PackageTestCase):
    def test_an_archive_cannot_escape_its_own_directory(self) -> None:
        archive = self.default_archive(**{"../escaped.html": INDEX})
        self.assertEqual(self.refusal(archive), "PATH_UNSAFE")

    def test_an_absolute_path_is_refused(self) -> None:
        archive = self.default_archive(**{"/etc/passwd": "x"})
        self.assertEqual(self.refusal(archive), "PATH_UNSAFE")

    def test_a_windows_separator_is_refused(self) -> None:
        archive = self.default_archive(**{"nested\\app.js": "const a = 1;\n"})
        self.assertEqual(self.refusal(archive), "PATH_UNSAFE")

    def test_a_symbolic_link_in_a_folder_is_refused(self) -> None:
        where = self.folder()
        os.symlink("/etc/passwd", where / "secret.txt")
        self.assertEqual(self.refusal(where), "PATH_UNSAFE")

    def test_a_symbolic_link_in_an_archive_is_refused(self) -> None:
        path = Path(tempfile.mkdtemp(dir=self.root)) / "package.zip"
        with zipfile.ZipFile(path, "w") as archive:
            archive.writestr("module.json", json.dumps(MANIFEST))
            archive.writestr("index.html", INDEX)
            info = zipfile.ZipInfo("secret.txt")
            info.external_attr = (0o120777 << 16)
            archive.writestr(info, "/etc/passwd")
        self.assertEqual(self.refusal(path), "PATH_UNSAFE")

    def test_an_executable_is_not_a_web_asset(self) -> None:
        self.assertEqual(self.refusal(self.default_archive(**{"tool.exe": "MZ"})),
                         "TYPE_NOT_ALLOWED")

    def test_a_build_input_says_the_package_was_not_finished(self) -> None:
        archive = self.default_archive(**{"tsconfig.json": "{}"})
        self.assertEqual(self.refusal(archive), "BUILD_INPUT")

    def test_a_source_directory_is_refused(self) -> None:
        archive = self.default_archive(**{"src/app.js": "const a = 1;\n"})
        self.assertEqual(self.refusal(archive), "BUILD_INPUT")

    def test_a_file_larger_than_the_limit_is_refused(self) -> None:
        body = "x" * (self.model.MAX_FILE_BYTES + 1)
        self.assertEqual(self.refusal(self.default_archive(**{"big.txt": body})), "TOO_LARGE")

    def test_a_decompression_bomb_is_refused(self) -> None:
        """Stored size, not unpacked size, is what an archive can lie with."""

        body = "\0" * (self.model.MAX_FILE_BYTES // 2)
        self.assertEqual(self.refusal(self.default_archive(**{"bomb.txt": body})), "TOO_LARGE")

    def test_something_that_is_not_a_package_at_all(self) -> None:
        stray = Path(tempfile.mkdtemp(dir=self.root)) / "notes.txt"
        stray.write_text("hello", encoding="utf-8")
        self.assertEqual(self.refusal(stray), "NOT_A_PACKAGE")


class WebAssetTests(PackageTestCase):
    def test_dynamic_code_is_refused(self) -> None:
        """Enforces: SEC-14."""

        archive = self.default_archive(**{"app.js": "const run = () => eval('1 + 1');\n"})
        self.assertEqual(self.refusal(archive), "DYNAMIC_CODE")

    def test_markup_assignment_is_refused(self) -> None:
        """Enforces: SEC-14."""

        archive = self.default_archive(**{"app.js": "document.body.innerHTML = data;\n"})
        self.assertEqual(self.refusal(archive), "DYNAMIC_CODE")

    def test_a_remote_script_is_refused(self) -> None:
        """Enforces: SEC-14."""

        page = '<!doctype html>\n<script src="https://cdn.example.com/a.js"></script>\n'
        archive = self.default_archive(**{"index.html": page})
        self.assertEqual(self.refusal(archive), "REMOTE_RESOURCE")

    def test_a_url_in_a_comment_is_documentation(self) -> None:
        body = "// see https://example.com/spec\nconst a = 1;\n"
        package = self.model.read_package(self.default_archive(**{"app.js": body}))
        self.assertEqual(package.id, "acme.notes")


class InstallTests(PackageTestCase):
    def install(self, source: Path, **options):
        return self.model.install(source, self.profile, **options)

    def test_installing_a_zip_writes_the_files_and_the_record(self) -> None:
        module = self.install(self.default_archive())
        installed = self.profile / "Sunshine/Modules/acme.notes"
        self.assertTrue((installed / "index.html").is_file())
        self.assertEqual(module.source, "packed")
        store = self.model.InstallStore(self.profile)
        self.assertEqual([item.id for item in store.read()], ["acme.notes"])

    def test_a_refused_package_writes_nothing(self) -> None:
        with self.assertRaises(self.model.PackageError):
            self.install(self.default_archive(**{"tool.exe": "MZ"}))
        self.assertFalse((self.profile / "Sunshine/Modules/acme.notes").exists())

    def test_installing_the_same_version_twice_is_refused(self) -> None:
        self.install(self.default_archive())
        with self.assertRaises(self.model.PackageError) as caught:
            self.install(self.default_archive())
        self.assertEqual(caught.exception.code, "ALREADY_INSTALLED")

    def test_an_older_version_is_refused_unless_asked_for(self) -> None:
        self.install(self.default_archive(**{"module.json": json.dumps(
            MANIFEST | {"version": "2.0.0"})}))
        with self.assertRaises(self.model.PackageError) as caught:
            self.install(self.default_archive())
        self.assertEqual(caught.exception.code, "VERSION_NOT_NEWER")
        self.install(self.default_archive(), reinstall=True)
        self.assertEqual(self.model.InstallStore(self.profile).find("acme.notes").version, "1.0.0")

    def test_an_upgrade_leaves_no_file_from_the_old_version(self) -> None:
        self.install(self.default_archive(**{"old.js": "const a = 1;\n"}))
        self.install(self.default_archive(**{
            "module.json": json.dumps(MANIFEST | {"version": "1.1.0"}),
            "new.js": "const b = 2;\n",
        }))
        installed = self.profile / "Sunshine/Modules/acme.notes"
        self.assertTrue((installed / "new.js").is_file())
        self.assertFalse((installed / "old.js").exists())

    def test_an_unpacked_install_is_served_where_it_lies(self) -> None:
        where = self.folder()
        module = self.install(where, unpacked=True)
        self.assertEqual(module.source, "unpacked")
        self.assertEqual(Path(module.location), where.resolve())
        self.assertFalse((self.profile / "Sunshine/Modules/acme.notes").exists())

    def test_an_unpacked_install_needs_a_folder(self) -> None:
        with self.assertRaises(self.model.PackageError) as caught:
            self.install(self.default_archive(), unpacked=True)
        self.assertEqual(caught.exception.code, "NOT_A_PACKAGE")

    def test_uninstalling_removes_the_copy_this_profile_owns(self) -> None:
        self.install(self.default_archive())
        self.model.uninstall("acme.notes", self.profile)
        self.assertFalse((self.profile / "Sunshine/Modules/acme.notes").exists())
        self.assertEqual(self.model.InstallStore(self.profile).read(), ())

    def test_uninstalling_an_unpacked_module_leaves_the_folder_alone(self) -> None:
        where = self.folder()
        self.install(where, unpacked=True)
        self.model.uninstall("acme.notes", self.profile)
        self.assertTrue((where / "index.html").is_file())

    def test_uninstalling_something_that_is_not_installed(self) -> None:
        with self.assertRaises(self.model.PackageError) as caught:
            self.model.uninstall("acme.notes", self.profile)
        self.assertEqual(caught.exception.code, "NOT_INSTALLED")

    def test_disabling_keeps_the_files_and_stops_the_serving(self) -> None:
        self.install(self.default_archive())
        self.model.set_enabled("acme.notes", self.profile, False)
        self.assertTrue((self.profile / "Sunshine/Modules/acme.notes/index.html").is_file())
        self.assertEqual(self.model.serve_map(self.profile), {})
        self.model.set_enabled("acme.notes", self.profile, True)
        self.assertEqual(list(self.model.serve_map(self.profile)), ["acme.notes"])


class IntegrityTests(PackageTestCase):
    def test_a_modified_copy_is_reported(self) -> None:
        self.model.install(self.default_archive(), self.profile)
        page = self.profile / "Sunshine/Modules/acme.notes/index.html"
        page.write_text(INDEX + "<!-- changed -->\n", encoding="utf-8")
        problems = self.model.verify_installed(self.profile)
        self.assertEqual(len(problems), 1)
        self.assertIn("INTEGRITY_MISMATCH", problems[0])

    def test_a_module_whose_files_are_gone_is_reported(self) -> None:
        self.model.install(self.default_archive(), self.profile)
        shutil.rmtree(self.profile / "Sunshine/Modules/acme.notes")
        problems = self.model.verify_installed(self.profile)
        self.assertEqual(len(problems), 1)
        self.assertIn("MISSING", problems[0])

    def test_an_unpacked_module_may_change_but_not_break_the_rules(self) -> None:
        where = self.folder()
        self.model.install(where, self.profile, unpacked=True)
        (where / "app.js").write_text("const a = 1;\n", encoding="utf-8")
        self.assertEqual(self.model.verify_installed(self.profile), [])
        (where / "app.js").write_text("eval('1');\n", encoding="utf-8")
        problems = self.model.verify_installed(self.profile)
        self.assertEqual(len(problems), 1)
        self.assertIn("DYNAMIC_CODE", problems[0])


class RecordStoreTests(PackageTestCase):
    def test_a_record_from_a_later_browser_is_preserved(self) -> None:
        store = self.model.InstallStore(self.profile)
        store.root.mkdir(parents=True)
        payload = '{"schema_version": 9, "modules": []}'
        store.record_path.write_text(payload, encoding="utf-8")
        with self.assertRaises(self.model.PackageError) as caught:
            store.read()
        self.assertEqual(caught.exception.code, "RECORD_FROM_A_LATER_VERSION")
        self.assertEqual(store.record_path.read_text(encoding="utf-8"), payload)

    def test_an_unreadable_record_recovers_the_installs_on_disk(self) -> None:
        self.model.install(self.default_archive(), self.profile)
        store = self.model.InstallStore(self.profile)
        store.record_path.write_text("{ this is not json", encoding="utf-8")
        recovered = store.read()
        self.assertEqual([item.id for item in recovered], ["acme.notes"])
        self.assertEqual(json.loads(store.record_path.read_text(encoding="utf-8"))["schema_version"],
                         self.model.RECORD_SCHEMA_VERSION)

    def test_recovery_ignores_a_directory_that_is_not_a_package(self) -> None:
        self.model.install(self.default_archive(), self.profile)
        store = self.model.InstallStore(self.profile)
        (store.root / "leftovers").mkdir()
        store.record_path.write_text("{}", encoding="utf-8")
        self.assertEqual([item.id for item in store.read()], ["acme.notes"])

    def test_no_record_at_all_is_an_empty_profile(self) -> None:
        self.assertEqual(self.model.InstallStore(self.profile).read(), ())


class ConsentTests(PackageTestCase):
    def test_the_prompt_states_what_validation_established(self) -> None:
        package = self.model.read_package(EXAMPLE)
        summary = self.model.consent_summary(package)
        self.assertEqual(summary["grants"]["browser_capabilities"], [])
        self.assertEqual(summary["grants"]["network"], "deny")
        self.assertEqual(summary["grants"]["filesystem"], "none")
        self.assertIs(summary["grants"]["credentials"], False)
        self.assertEqual(summary["origin"], "chrome-untrusted://sunshine-module/example.scratchpad/")


class CommandLineTests(PackageTestCase):
    def run_cli(self, *arguments: str) -> subprocess.CompletedProcess:
        return subprocess.run(
            [sys.executable, str(ROOT / "scripts/install_module.py"), *arguments],
            capture_output=True, text=True, check=False,
        )

    def test_validating_the_shipped_example_succeeds(self) -> None:
        result = self.run_cli("validate", str(EXAMPLE))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("can be installed", result.stdout)

    def test_a_refusal_exits_one_and_names_its_code(self) -> None:
        archive = self.default_archive(**{"tool.exe": "MZ"})
        result = self.run_cli("validate", str(archive))
        self.assertEqual(result.returncode, 1)
        self.assertTrue(result.stderr.startswith("TYPE_NOT_ALLOWED:"), result.stderr)

    def test_installing_and_listing_through_the_command_line(self) -> None:
        archive = self.default_archive()
        installed = self.run_cli("install", str(archive), "--profile", str(self.profile))
        self.assertEqual(installed.returncode, 0, installed.stderr)
        listed = self.run_cli("list", "--profile", str(self.profile))
        self.assertIn("acme.notes", listed.stdout)

    def test_a_profile_is_never_guessed(self) -> None:
        environment = dict(os.environ)
        environment.pop("SUNSHINE_PROFILE", None)
        result = subprocess.run(
            [sys.executable, str(ROOT / "scripts/install_module.py"), "list"],
            capture_output=True, text=True, check=False, env=environment,
        )
        self.assertEqual(result.returncode, 2)
        self.assertIn("--profile", result.stderr)


if __name__ == "__main__":
    unittest.main()
