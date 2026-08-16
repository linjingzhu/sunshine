"""Regression tests for the native Chromium architecture guard."""

from __future__ import annotations

import contextlib
import importlib.util
import io
from pathlib import Path
import tempfile
import unittest
from unittest import mock


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
VERIFY_SCRIPT = REPOSITORY_ROOT / "scripts" / "verify_architecture.py"


def load_verifier():
    spec = importlib.util.spec_from_file_location("verify_architecture", VERIFY_SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load architecture verifier: {VERIFY_SCRIPT}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class ArchitectureVerifierTests(unittest.TestCase):
    def setUp(self) -> None:
        self.verifier = load_verifier()
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary_directory.name)
        self._write_valid_chromium_downstream()

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def _write(self, relative_path: str, content: str) -> Path:
        path = self.root / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return path

    def _write_valid_chromium_downstream(self) -> None:
        self._write(
            "config/chromium.version",
            "# Updated only through upstream-roll review.\n"
            "CHROMIUM_REVISION=refs/tags/148.0.7741.0\n",
        )
        self._write("downstream/patches/series", "0001-sunshine-branding.patch\n")
        self._write(
            "downstream/patches/0001-sunshine-branding.patch",
            "Subject: [PATCH] Add Sunshine branding\n",
        )
        self._write("src/browser_main.cc", "int main() { return 0; }\n")

    def _run(self) -> tuple[int, str, str]:
        stdout = io.StringIO()
        stderr = io.StringIO()
        with (
            mock.patch.object(self.verifier, "ROOT", self.root),
            contextlib.redirect_stdout(stdout),
            contextlib.redirect_stderr(stderr),
        ):
            result = self.verifier.main()
        return result, stdout.getvalue(), stderr.getvalue()

    def test_valid_native_chromium_downstream_passes(self) -> None:
        result, stdout, stderr = self._run()

        self.assertEqual(0, result, stderr)
        self.assertIn("Architecture check passed", stdout)

    def test_excluded_runtime_marker_fails(self) -> None:
        excluded_import = "from \"" + "electron" + "\""
        self._write("src/legacy-wrapper.js", excluded_import + "\n")

        result, _, stderr = self._run()

        self.assertEqual(1, result)
        self.assertIn("excluded runtime marker", stderr)
        self.assertIn("src/legacy-wrapper.js", stderr)

    def test_excluded_wrapper_manifest_fails(self) -> None:
        manifest_name = "package" + ".json"
        self._write(manifest_name, "{}\n")

        result, _, stderr = self._run()

        self.assertEqual(1, result)
        self.assertIn("excluded wrapper manifest", stderr)
        self.assertIn(manifest_name, stderr)

    def test_hardcoded_google_startup_url_fails(self) -> None:
        google_url = "https://www." + "google.com"
        self._write("src/startup.cc", f'const char* startup = "{google_url}";\n')

        result, _, stderr = self._run()

        self.assertEqual(1, result)
        self.assertIn("Google", stderr)
        self.assertIn("src/startup.cc", stderr)

    def test_series_entry_must_reference_an_existing_patch(self) -> None:
        (self.root / "downstream/patches/0001-sunshine-branding.patch").unlink()

        result, _, stderr = self._run()

        self.assertEqual(1, result)
        self.assertIn("0001-sunshine-branding.patch", stderr)
        self.assertIn("missing", stderr.lower())

    def test_chromium_revision_must_be_a_pinned_version_tag(self) -> None:
        invalid_revisions = (
            "CHROMIUM_REVISION=main\n",
            "CHROMIUM_REVISION=refs/heads/main\n",
            "CHROMIUM_REVISION=refs/tags/latest\n",
            "CHROMIUM_REVISION=refs/tags/148.0.7741\n",
        )

        for revision in invalid_revisions:
            with self.subTest(revision=revision.strip()):
                self._write("config/chromium.version", revision)
                result, _, stderr = self._run()
                self.assertEqual(1, result)
                self.assertIn("CHROMIUM_REVISION", stderr)


if __name__ == "__main__":
    unittest.main()
