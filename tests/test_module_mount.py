"""Regression tests for the module mount port.

The port is the seam where a module app -- authored outside this repository,
around data fetched from outside it -- meets a page running at browser
privilege. `scripts/verify_module_mount.py` reads the shipped source and says
whether it holds; these tests inject the violations, so that the guard is known
to fail when it should rather than only known to pass today.
"""

from pathlib import Path
import importlib.util
import json
import unittest

ROOT = Path(__file__).resolve().parents[1]


def load(name: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / f"scripts/{name}.py")
    if spec is None or spec.loader is None:
        raise RuntimeError(f"unable to load {name}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class ModuleMountGuardTests(unittest.TestCase):
    def setUp(self) -> None:
        self.guard = load("verify_module_mount")

    def test_the_repository_passes(self) -> None:
        self.assertEqual([], self.guard.check(ROOT))


class MountDeclarationTests(unittest.TestCase):
    """The manifest half. Enforces: MM-1, MM-2."""

    def setUp(self) -> None:
        self.validator = load("validate_first_party_modules")

    def _template(self) -> dict:
        return json.loads(
            (ROOT / "first_party/templates/module.example.json").read_text(encoding="utf-8")
        )

    def test_a_content_url_is_admitted(self) -> None:
        """Enforces: MM-1."""

        manifest = self._template()
        manifest["kind"] = "surface"
        manifest["mount"] = {"content_url": "chrome-untrusted://sunshine-marketpick-app/"}
        self.validator.validate_manifest(manifest, "fixture")

    def test_the_shape_is_the_whole_rule(self) -> None:
        """Enforces: MM-1.

        Each of these is a URL that would resolve to something in a browser,
        and none of them is the one shape the shell navigates to. A deeper path
        or a query is the beginning of a module choosing where it is loaded
        from, which is the choice the registry makes.
        """

        for url in (
            "chrome://sunshine-app/",
            "chrome-untrusted://sunshine-app",
            "chrome-untrusted://sunshine-app/index.html",
            "chrome-untrusted://sunshine-app/?tab=1",
            "chrome-untrusted://sunshine-app/#top",
            "chrome-untrusted://-app/",
            "chrome-untrusted://Sunshine-App/",
            "https://example.com/",
            "",
        ):
            with self.subTest(url=url):
                manifest = self._template()
                manifest["kind"] = "surface"
                manifest["mount"] = {"content_url": url}
                with self.assertRaisesRegex(
                    self.validator.ModuleValidationError, "content_url"
                ):
                    self.validator.validate_manifest(manifest, "fixture")

    def test_only_a_surface_mounts(self) -> None:
        """Enforces: MM-2.

        A service has no UI of its own. Letting one declare a mount would put
        something in D that nothing in the registry says exists.
        """

        manifest = self._template()
        manifest["kind"] = "service"
        manifest["mount"] = {"content_url": "chrome-untrusted://sunshine-app/"}
        with self.assertRaisesRegex(self.validator.ModuleValidationError, "only a surface"):
            self.validator.validate_manifest(manifest, "fixture")

    def test_an_extra_key_in_the_mount_block_is_refused(self) -> None:
        """Enforces: MM-1.

        The block holds one key. A second one would be a capability arriving
        through the declaration rather than through the port.
        """

        manifest = self._template()
        manifest["kind"] = "surface"
        manifest["mount"] = {
            "content_url": "chrome-untrusted://sunshine-app/",
            "privileged": True,
        }
        with self.assertRaisesRegex(self.validator.ModuleValidationError, "invalid mount"):
            self.validator.validate_manifest(manifest, "fixture")

    def test_a_mount_is_optional_and_an_unknown_key_still_is_not(self) -> None:
        """Most modules declare none, and that is not a defect. But admitting
        one optional key is not admitting the shape of the manifest."""

        manifest = self._template()
        self.validator.validate_manifest(manifest, "fixture")

        manifest["shell"] = {"content_url": "chrome-untrusted://sunshine-app/"}
        with self.assertRaisesRegex(self.validator.ModuleValidationError, "unknown"):
            self.validator.validate_manifest(manifest, "fixture")


class MountPortSourceTests(unittest.TestCase):
    """The TypeScript half, read as source. The build cannot run here."""

    def setUp(self) -> None:
        self.references = load("verify_patch_references")
        self.files = self.references.stack_files(ROOT)
        self.port = "\n".join(
            self.files["chrome/browser/resources/sunshine/shell/mount_port.ts"]
        )
        self.mount = "\n".join(
            self.files["chrome/browser/resources/sunshine/shell/mount.ts"]
        )
        self.app = "\n".join(self.files["chrome/browser/resources/sunshine/shell/app.ts"])

    def test_the_port_imports_nothing(self) -> None:
        """Enforces: MM-3.

        The value of a port is that a second host implements it by copying one
        file. An import makes the copy drag something with it, and the copy is
        what `docs/decisions/0013-module-data-portability.md` exists for.
        """

        for line in self.port.splitlines():
            self.assertFalse(line.strip().startswith("import "), line)

    def test_every_validator_can_refuse(self) -> None:
        """Enforces: MM-5.

        A validator that never returns null is a validator that admits
        everything. Each of these is the total function the port promises, and
        the check is structural: it must have a `return null` in it.
        """

        for name in ("identifier", "label", "icon", "moduleMessage", "hostMessage", "contentUrl"):
            with self.subTest(function=name):
                start = self.port.index(f"function {name}(")
                body = self.port[start : self.port.index("\n}\n", start)]
                self.assertIn("null", body)

    def test_the_shell_never_broadcasts(self) -> None:
        """Enforces: MM-6.

        `postMessage(message, '*')` sends to whatever the frame has become. A
        frame that navigated away would be handed the shell's messages on its
        way out.
        """

        import re

        for call in re.findall(r"postMessage\([^)]*\)", self.mount):
            self.assertNotIn("'*'", call, call)
        self.assertIn("postMessage(message, this.origin)", self.mount)

    def test_the_panel_cannot_describe(self) -> None:
        """Enforces: MM-8.

        E may hold a module. The header and the tab list belong to D's module,
        and a panel that could rewrite them would be E deciding what D is.
        """

        self.assertIn("describe: () => {},", self.app)

    def test_the_tab_list_is_built_as_nodes(self) -> None:
        """Enforces: MM-7.

        Every label in C came from a module. `textContent` is the whole
        difference between drawing it and running it.
        """

        self.assertIn("label.textContent = tab.label;", self.app)
        self.assertNotIn("innerHTML", self.app)


if __name__ == "__main__":
    unittest.main()
