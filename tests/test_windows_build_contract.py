"""Static contract tests for the resource-intensive Windows Chromium build."""

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW_DIR = ROOT / ".github/workflows"
SCRIPT = ROOT / "scripts/build_chromium_windows.ps1"

class WindowsBuildContractTests(unittest.TestCase):
    def test_no_actions_workflows_are_present(self) -> None:
        self.assertEqual([], [path for path in WORKFLOW_DIR.rglob("*") if path.is_file()])

    def test_build_uses_native_chromium_targets(self) -> None:
        text = SCRIPT.read_text(encoding="utf-8")
        self.assertIn("bootstrap_chromium.py", text)
        self.assertIn("gn gen", text)
        self.assertIn("autoninja", text)
        self.assertIn('@("chrome", "mini_installer")', text)
        self.assertNotIn("electron", text.lower())

    def test_release_and_size_contracts_are_enforced(self) -> None:
        text = SCRIPT.read_text(encoding="utf-8")
        for marker in (
            "is_debug=false",
            "is_official_build=true",
            "is_component_build=false",
            "symbol_level=0",
            "MinimumFreeSpaceGB = 180",
            "size-report.json",
        ):
            self.assertIn(marker, text)

    def test_build_resets_the_build_owned_chromium_workspace(self) -> None:
        """Without --reset the previous wave's patch stack stops the next build.

        The workspace persists between runs on a self-hosted runner, so a changed
        patch stack would leave it dirty and require manual cleanup.
        """

        self.assertIn("bootstrap_chromium.py\") --workspace $workspacePath --reset", SCRIPT.read_text(encoding="utf-8"))

    def test_the_pwsh_requirement_is_documented_and_checked(self) -> None:
        """`shell: pwsh` needs PowerShell 7, which stock Windows does not have.

        GitHub-hosted images ship it, so the dependency stayed invisible until
        the pipeline first ran on a real machine and failed in a minute with
        `pwsh: command not found`.
        """

        script = SCRIPT.read_text(encoding="utf-8")
        self.assertIn("$PSVersionTable.PSVersion.Major -lt 7", script)
        self.assertIn("winget install Microsoft.PowerShell", script)

        doc = (ROOT / "docs/WINDOWS_CHROMIUM_BUILD.md").read_text(encoding="utf-8")
        self.assertIn("PowerShell 7 or newer", doc)

    def test_gn_arguments_travel_by_file_not_through_the_shell(self) -> None:
        """PowerShell strips embedded quotes from native-command arguments.

        `--args=... ffmpeg_branding="Chromium"` reached GN as
        `ffmpeg_branding=Chromium`, which it rejected as an undefined
        identifier. args.gn removes shell quoting from the path.
        """

        script = SCRIPT.read_text(encoding="utf-8")
        self.assertIn('Set-Content -Path (Join-Path $out "args.gn")', script)
        self.assertIn('gn gen "out/Sunshine"', script)
        self.assertNotIn("--args=", script)

    def test_a_compile_failure_prints_the_compiler_diagnostic(self) -> None:
        """siso keeps the failing command's output out of stdout.

        Run 10 reached the compile, ran 17.5 minutes, and failed one of 66,739
        steps. The log recorded `1 steps failed: exit=1` and nothing else --
        no target, no source file, no compiler message -- because siso had
        written all of it to out/Sunshine/siso_output on the runner. A compile
        failure that cannot be read from the log cannot be fixed from the log.
        """

        script = SCRIPT.read_text(encoding="utf-8")
        self.assertIn("siso_output", script)
        self.assertIn("siso_failed_commands.bat", script)

        # The dump has to precede the throw, or `throw` ends the script first.
        dump = script.index("siso_output")
        failure = script.index('throw "Chromium compilation failed."')
        self.assertLess(dump, failure)

    def test_compile_parallelism_is_capped_when_asked(self) -> None:
        """The runner is also the owner's workstation, so it must stay usable."""

        script = SCRIPT.read_text(encoding="utf-8")
        self.assertIn("SUNSHINE_NINJA_JOBS", script)
        self.assertIn('$ninjaArguments += @("-j", $NinjaJobs)', script)



class RunnerEncodingTests(unittest.TestCase):
    """Every file a tool reads is read as UTF-8, explicitly.

    `Path.read_text()` with no encoding uses the process's locale encoding.
    On the Korean Windows build workstation,
    that is `cp949`, not UTF-8, and the difference is not
    academic: build run `32250667556` died on
    `UnicodeDecodeError: 'cp949' codec can't decode byte 0xe2`, which was an em
    dash inside a comment in `0007-sunshine-modules-webui.patch`.

    The quieter half is the reason this is a test rather than a fix. The same
    reader had been mis-decoding `0006-sunshine-document-webui.patch` for as
    long as it existed -- a section sign there is `0xC2 0xA7`, which `cp949`
    accepts and turns into a different character entirely. It happened to be
    harmless because the mangled text was in a comment rather than in a
    `+++ b/` line. A defect that fails loudly is the lucky case; this rule is
    about the one that does not.

    Every prose file in this repository is UTF-8 and several deliberately
    contain typographic punctuation, so "avoid non-ASCII" is not the fix and
    never was.
    """

    def test_no_tool_reads_a_file_in_the_locale_encoding(self) -> None:
        for script in sorted((ROOT / "scripts").glob("*.py")):
            text = script.read_text(encoding="utf-8")
            with self.subTest(script=script.name):
                self.assertNotIn(
                    ".read_text()",
                    text,
                    f"{script.name} reads a file in the locale encoding; "
                    'pass encoding="utf-8"',
                )

    def test_no_tool_writes_a_file_in_the_locale_encoding(self) -> None:
        """The same hazard in the other direction, and the more damaging one:
        a file written in `cp949` is corrupt on disk rather than merely
        misread."""

        for script in sorted((ROOT / "scripts").glob("*.py")):
            text = script.read_text(encoding="utf-8")
            for index, line in enumerate(text.splitlines(), start=1):
                if ".write_text(" not in line:
                    continue
                with self.subTest(script=script.name, line=index):
                    self.assertIn(
                        "encoding=",
                        line,
                        f"{script.name}:{index} writes a file in the locale encoding",
                    )


if __name__ == "__main__":
    unittest.main()
