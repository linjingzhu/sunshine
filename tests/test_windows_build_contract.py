"""Static contract tests for the resource-intensive Windows Chromium build."""

from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW_DIR = ROOT / ".github/workflows"
WORKFLOW = WORKFLOW_DIR / "native-chromium-windows.yml"
SCRIPT = ROOT / "scripts/build_chromium_windows.ps1"

# Events a fork pull request can raise. A self-hosted runner reachable from one
# of these would execute a stranger's code on the machine hosting the runner.
FORK_REACHABLE_EVENTS = (
    "pull_request:",
    "pull_request_target:",
    "issue_comment:",
    "workflow_call:",
)


class WindowsBuildContractTests(unittest.TestCase):
    def test_workflow_requires_dedicated_self_hosted_runner(self) -> None:
        text = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("runs-on: [self-hosted, Windows, X64, sunshine-chromium]", text)
        self.assertNotIn("windows-latest", text)
        # Source acquisition shares this budget with the build, so it must stay
        # well above the compile time alone.
        self.assertIn("timeout-minutes: 1440", text)

    def test_workflow_is_explicitly_dispatched(self) -> None:
        text = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("workflow_dispatch:", text)
        self.assertNotIn("pull_request:", text)
        self.assertNotIn("push:", text)

    def test_no_self_hosted_workflow_is_reachable_from_a_fork(self) -> None:
        """The runner is a physical machine, so this holds for every workflow.

        `test_workflow_is_explicitly_dispatched` pins the one workflow that
        exists today; this pins the rule for any workflow added later.
        """

        for workflow in sorted(WORKFLOW_DIR.glob("*.yml")) + sorted(WORKFLOW_DIR.glob("*.yaml")):
            text = workflow.read_text(encoding="utf-8")
            if "self-hosted" not in text:
                continue
            for event in FORK_REACHABLE_EVENTS:
                with self.subTest(workflow=workflow.name, event=event):
                    self.assertNotIn(
                        event,
                        text,
                        f"{workflow.name} exposes a self-hosted runner to {event}",
                    )

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

        self.assertIn("shell: pwsh", WORKFLOW.read_text(encoding="utf-8"))

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

        workflow = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("ninja_jobs:", workflow)
        self.assertIn("SUNSHINE_NINJA_JOBS: ${{ inputs.ninja_jobs }}", workflow)


class ArchitectureGuardParityTests(unittest.TestCase):
    """The self-hosted guard exists because a hosted runner can stop being
    allocated -- an allowance condition the repository cannot fix from inside.
    A fallback that checks less than the thing it stands in for is worse than no
    fallback, because it reports green for a smaller claim.

    Parsed with the standard library on purpose: a YAML dependency here would
    make the guard's own tests need a package the guard does not install.
    """

    HOSTED = WORKFLOW_DIR / "chromium-architecture-check.yml"
    SELF_HOSTED = WORKFLOW_DIR / "architecture-guard-self-hosted.yml"

    RUN_STEP = re.compile(r"^\s+run: (.+)$", re.MULTILINE)
    SHELL_STEP = re.compile(r"^\s+shell: (.+)$", re.MULTILINE)

    def _runs(self, path: Path) -> list[str]:
        return [line.strip() for line in self.RUN_STEP.findall(path.read_text(encoding="utf-8"))]

    def test_both_guards_run_the_same_checks(self) -> None:
        self.assertEqual(self._runs(self.HOSTED), self._runs(self.SELF_HOSTED))
        # A guard that runs nothing would satisfy equality.
        self.assertGreaterEqual(len(self._runs(self.HOSTED)), 8)

    def test_the_self_hosted_guard_is_dispatch_only(self) -> None:
        """Asserted separately from the fork rule because this is the single
        property that makes running a guard on a physical machine safe."""

        text = self.SELF_HOSTED.read_text(encoding="utf-8")
        self.assertIn("on:\n  workflow_dispatch:\n", text)
        for event in ("pull_request", "push:", "schedule:"):
            with self.subTest(event=event):
                self.assertNotIn(f"  {event}", text)

    def test_neither_guard_depends_on_a_shell(self) -> None:
        """The self-hosted runner is a Windows workstation. A check needing a
        bash that happens to be on its PATH fails for a reason unrelated to what
        it is checking, so every step invokes Python directly.
        """

        for path in (self.HOSTED, self.SELF_HOSTED):
            with self.subTest(workflow=path.name):
                text = path.read_text(encoding="utf-8")
                self.assertEqual([], self.SHELL_STEP.findall(text))
                for command in self._runs(path):
                    self.assertTrue(command.startswith("python"), command)


if __name__ == "__main__":
    unittest.main()
