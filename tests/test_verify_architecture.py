"""Regression tests for the native Chromium architecture guard."""

from __future__ import annotations

import contextlib
import importlib.util
import io
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
VERIFY_SCRIPT = REPOSITORY_ROOT / "scripts" / "verify_architecture.py"
BOOTSTRAP_SCRIPT = REPOSITORY_ROOT / "scripts" / "bootstrap_chromium.py"


def load_verifier():
    spec = importlib.util.spec_from_file_location("verify_architecture", VERIFY_SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load architecture verifier: {VERIFY_SCRIPT}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_bootstrap():
    spec = importlib.util.spec_from_file_location("bootstrap_chromium", BOOTSTRAP_SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load Chromium bootstrap: {BOOTSTRAP_SCRIPT}")
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
        self._write(
            "downstream/patches/series",
            "0001-sunshine-branding.patch\n"
            "0002-sunshine-new-tab.patch\n",
        )
        self._write(
            "downstream/patches/0001-sunshine-branding.patch",
            "Subject: [PATCH] Add Sunshine branding\n",
        )
        self._write(
            "downstream/patches/0002-sunshine-new-tab.patch",
            "chrome/browser/resources/new_tab_page/app.html\n"
            "chrome/browser/resources/new_tab_page/app.css\n"
            '<div id="sunshineWordmark" aria-label="Sunshine OS"\n'
            '    ?hidden="${!this.logoEnabled_}">SUNSHINE</div>\n'
            "margin-bottom: var(--ntp-logo-margin-bottom, 38px);\n"
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

    def test_wrapper_runtime_design_in_a_specification_fails(self) -> None:
        """The guard must read specifications, not only code.

        A wrapper architecture survived in an active handoff document while the
        code tree was already clean, because documentation was not scanned.
        """

        webpreference = "node" + "Integration"
        self._write(
            "docs/HANDOFF.md",
            f"Remote pages must have `{webpreference}: false`.\n",
        )

        result, _, stderr = self._run()

        self.assertEqual(1, result)
        self.assertIn("wrapper-runtime design marker", stderr)
        self.assertIn("docs/HANDOFF.md", stderr)

    def test_wrapper_runtime_design_in_code_fails(self) -> None:
        bridge = "ipc" + "Renderer"
        self._write("src/bridge.cc", f"// {bridge} bridge\n")

        result, _, stderr = self._run()

        self.assertEqual(1, result)
        self.assertIn("wrapper-runtime design marker", stderr)

    def test_prohibiting_a_wrapper_runtime_by_name_is_allowed(self) -> None:
        """Removing the runtime must not delete the rule that forbids it."""

        self._write(
            "docs/decisions/0002-native-chromium-downstream.md",
            "Do not add Electron, CEF, Qt WebEngine, Tauri, or platform WebView wrappers.\n",
        )

        result, stdout, stderr = self._run()

        self.assertEqual(0, result, stderr)
        self.assertIn("Architecture check passed", stdout)

    def test_documentation_may_quote_the_startup_url_it_forbids(self) -> None:
        self._write(
            "docs/CHROMIUM_MACOS_BUILD.md",
            f"- A native New Tab Page opens; `{self.verifier.GOOGLE_STARTUP_URL}/` is not forced.\n",
        )

        result, _, stderr = self._run()

        self.assertEqual(0, result, stderr)

    def test_code_still_rejects_a_hardcoded_startup_url(self) -> None:
        self._write("src/startup.cc", f'const char kStartup[] = "{self.verifier.GOOGLE_STARTUP_URL}";\n')

        result, _, stderr = self._run()

        self.assertEqual(1, result)
        self.assertIn("hardcoded Google startup URL", stderr)

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

    def test_new_tab_patch_must_preserve_browser_first_markers(self) -> None:
        patch = self.root / "downstream/patches/0002-sunshine-new-tab.patch"
        patch.write_text(
            '<div id="sunshineWordmark">SUNSHINE</div>\n',
            encoding="utf-8",
        )

        result, _, stderr = self._run()

        self.assertEqual(1, result)
        self.assertIn("New Tab patch missing required marker", stderr)

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


class ChromiumBootstrapTests(unittest.TestCase):
    def setUp(self) -> None:
        self.bootstrap = load_bootstrap()
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary_directory.name)
        self.source = self.root / "src"
        self.source.mkdir()
        subprocess.run(("git", "init", "--quiet"), cwd=self.source, check=True)
        branding = self.source / "chrome/app/theme/chromium/BRANDING"
        branding.parent.mkdir(parents=True)
        branding.write_text("PRODUCT_FULLNAME=Chromium\n", encoding="utf-8")
        subprocess.run(("git", "add", "."), cwd=self.source, check=True)
        subprocess.run(
            (
                "git",
                "-c",
                "user.name=test",
                "-c",
                "user.email=test@localhost",
                "commit",
                "--quiet",
                "-m",
                "base",
            ),
            cwd=self.source,
            check=True,
        )
        patches = self.root / "downstream/patches"
        patches.mkdir(parents=True)
        (patches / "branding.patch").write_text(
            "diff --git a/chrome/app/theme/chromium/BRANDING "
            "b/chrome/app/theme/chromium/BRANDING\n"
            "--- a/chrome/app/theme/chromium/BRANDING\n"
            "+++ b/chrome/app/theme/chromium/BRANDING\n"
            "@@ -1 +1 @@\n"
            "-PRODUCT_FULLNAME=Chromium\n"
            "+PRODUCT_FULLNAME=Sunshine OS\n",
            encoding="utf-8",
        )

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def test_applied_patch_stack_is_recognized_for_idempotent_rerun(self) -> None:
        patch = self.root / "downstream/patches/branding.patch"
        subprocess.run(("git", "apply", str(patch)), cwd=self.source, check=True)

        with mock.patch.object(self.bootstrap, "ROOT", self.root):
            self.assertTrue(
                self.bootstrap.patch_stack_is_applied(self.source, ["branding.patch"])
            )

    def test_tools_are_launched_by_resolved_path(self) -> None:
        """depot_tools ships .bat shims and Windows CreateProcess ignores PATHEXT.

        Passing a bare name raised `FileNotFoundError: [WinError 2]` on the first
        real Windows build, even though the shim was on PATH and the PowerShell
        preflight found it with Get-Command.
        """

        shim = r"F:\depot_tools\fetch.bat"
        with (
            mock.patch.object(self.bootstrap.shutil, "which", return_value=shim),
            mock.patch.object(self.bootstrap.subprocess, "run") as launched,
        ):
            self.bootstrap.run("fetch", "--nohooks", "chromium")

        self.assertEqual((shim, "--nohooks", "chromium"), launched.call_args[0][0])

    def test_a_missing_tool_names_itself(self) -> None:
        with mock.patch.object(self.bootstrap.shutil, "which", return_value=None):
            with self.assertRaisesRegex(SystemExit, "gclient"):
                self.bootstrap.run("gclient", "sync")

    def test_sync_concurrency_is_bounded(self) -> None:
        """gclient defaults to one job per core, which googlesource rejects.

        A 24-thread runner opened 24 anonymous clones and the server answered
        HTTP 429 `shared/shared_anonymous` after 53 minutes of syncing.
        """

        source = BOOTSTRAP_SCRIPT.read_text(encoding="utf-8")
        self.assertIn("DEFAULT_SYNC_JOBS = 8", source)
        self.assertIn('jobs = f"-j{args.jobs}"', source)
        self.assertIn('run("gclient", "sync", "--nohooks", jobs, cwd=workspace)', source)
        self.assertIn('run("gclient", "sync", jobs, cwd=workspace)', source)

        result = subprocess.run(
            (sys.executable, str(BOOTSTRAP_SCRIPT), "--help"),
            capture_output=True,
            text=True,
            check=True,
        )
        self.assertIn("--jobs", result.stdout)

    def test_fetch_is_replaced_by_the_two_steps_it_performs(self) -> None:
        """`fetch chromium` cannot bound concurrency, so it is expanded inline."""

        source = BOOTSTRAP_SCRIPT.read_text(encoding="utf-8")
        self.assertIn('run("gclient", "config", "--spec", CHROMIUM_SPEC, cwd=workspace)', source)
        self.assertIn("https://chromium.googlesource.com/chromium/src.git", source)
        self.assertNotIn('run("fetch"', source)

    def test_reset_exists_and_is_opt_in(self) -> None:
        """Bootstrapping a human's workspace must still refuse to discard work."""

        result = subprocess.run(
            (sys.executable, str(BOOTSTRAP_SCRIPT), "--help"),
            capture_output=True,
            text=True,
            check=True,
        )

        self.assertIn("--reset", result.stdout)
        self.assertIn("build-owned workspace", result.stdout)

    def test_forced_checkout_discards_patches_but_keeps_build_output(self) -> None:
        """The whole --reset design rests on this git behaviour.

        A build workspace carries the previous wave's patch stack plus tens of
        gigabytes of untracked output under out/. Resetting must drop the first
        and keep the second, or every patch change costs a full rebuild.
        """

        patch = self.root / "downstream/patches/branding.patch"
        subprocess.run(("git", "apply", str(patch)), cwd=self.source, check=True)
        build_output = self.source / "out/Sunshine/chrome.exe"
        build_output.parent.mkdir(parents=True)
        build_output.write_text("expensive incremental build\n", encoding="utf-8")

        subprocess.run(
            ("git", "checkout", "--detach", "--force", "HEAD"),
            cwd=self.source,
            check=True,
            capture_output=True,
        )

        branding = self.source / "chrome/app/theme/chromium/BRANDING"
        self.assertEqual("PRODUCT_FULLNAME=Chromium\n", branding.read_text(encoding="utf-8"))
        self.assertTrue(build_output.is_file(), "untracked build output must survive a reset")

    def test_unrelated_dirty_file_is_not_accepted_as_patch_stack(self) -> None:
        patch = self.root / "downstream/patches/branding.patch"
        subprocess.run(("git", "apply", str(patch)), cwd=self.source, check=True)
        (self.source / "unrelated.txt").write_text("do not overwrite\n", encoding="utf-8")

        with mock.patch.object(self.bootstrap, "ROOT", self.root):
            self.assertFalse(
                self.bootstrap.patch_stack_is_applied(self.source, ["branding.patch"])
            )


if __name__ == "__main__":
    unittest.main()
