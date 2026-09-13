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


def runs_self_hosted(text: str) -> bool:
    """Whether a workflow actually runs on the physical machine.

    Read from `runs-on:` rather than from the word appearing anywhere. A hosted
    workflow that merely *mentions* the self-hosted one -- to say what it does
    not replace -- was being held to the physical machine's rules, which meant a
    sentence in a comment silently decided which rules applied to a file. The
    rule is about where the job runs.

    Comments are stripped first, so `# ... self-hosted ...` cannot make a
    workflow look like one either way.
    """

    for line in text.splitlines():
        stripped = line.split("#", 1)[0]
        if "runs-on:" in stripped and "self-hosted" in stripped:
            return True
    return False


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
            if not runs_self_hosted(text):
                continue
            for event in FORK_REACHABLE_EVENTS:
                with self.subTest(workflow=workflow.name, event=event):
                    self.assertNotIn(
                        event,
                        text,
                        f"{workflow.name} exposes a self-hosted runner to {event}",
                    )

    def test_self_hosted_is_decided_by_where_the_job_runs(self) -> None:
        """The predicate that selects which workflows the rule above binds."""

        self.assertTrue(
            runs_self_hosted("jobs:\n  x:\n    runs-on: [self-hosted, Windows, X64]\n")
        )
        self.assertTrue(runs_self_hosted("    runs-on: self-hosted\n"))
        self.assertFalse(
            runs_self_hosted("# same checks as the self-hosted guard\n    runs-on: ubuntu-latest\n")
        )
        self.assertFalse(runs_self_hosted("    runs-on: ubuntu-latest  # not self-hosted\n"))

    def test_the_repositorys_workflows_split_the_way_they_claim(self) -> None:
        """Reads the real files, so a workflow that changed runners without
        changing its rules fails here."""

        by_name = {
            path.name: runs_self_hosted(path.read_text(encoding="utf-8"))
            for path in sorted(WORKFLOW_DIR.glob("*.yml"))
        }
        self.assertTrue(by_name["native-chromium-windows.yml"])
        self.assertTrue(by_name["architecture-guard-self-hosted.yml"])
        self.assertFalse(by_name["patch-apply-hosted.yml"])
        # Named rather than looked up, because the point is that it is gone.
        # `architecture-guard-hosted.yml` was removed on 2026-09-13: it had not
        # been allocated a runner since 2026-09-08 and every push produced a red
        # check that meant nothing. It cost no coverage -- the self-hosted guard
        # runs all twenty-nine of its checks and one it did not.
        self.assertNotIn("architecture-guard-hosted.yml", by_name)

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


class RunnerEncodingTests(unittest.TestCase):
    """Every file a tool reads is read as UTF-8, explicitly.

    `Path.read_text()` with no encoding uses the process's locale encoding.
    On the machine that is this project's only CI -- a Korean Windows
    workstation -- that is `cp949`, not UTF-8, and the difference is not
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


class SelfHostedGuardTests(unittest.TestCase):
    """The self-hosted guard is not a fallback any more -- it is the only CI.

    It replaced a hosted guard that could not be allocated a runner for a full
    day, which made the repository's verification depend on an account
    allowance it cannot influence. The rules below are what keep a guard that
    now stands alone from quietly checking less than the repository contains.

    Parsed with the standard library on purpose: a YAML dependency here would
    make the guard's own tests need a package the guard does not install.
    """

    GUARD = WORKFLOW_DIR / "architecture-guard-self-hosted.yml"

    RUN_STEP = re.compile(r"^\s+run: (.+)$", re.MULTILINE)
    USES_STEP = re.compile(r"^\s+uses: (.+)$", re.MULTILINE)

    # Scripts that are checks. `bootstrap_chromium.py` and `workspace_model.py`
    # are not -- one is build tooling, the other is a model the checks read.
    GUARD_PREFIXES = ("verify_", "validate_")
    GUARD_NAMES = ("patch_manifest.py", "trace_invariants.py", "compile_check.py")

    def _commands(self, path: Path) -> list[str]:
        """Single-line `run:` values. A `run: |` block yields "|", not a command."""

        found = [line.strip() for line in self.RUN_STEP.findall(path.read_text(encoding="utf-8"))]
        return [command for command in found if command != "|"]

    def test_no_workflow_downloads_a_third_party_action(self) -> None:
        """`uses:` is fetched from codeload.github.com during `Set up job`.

        This account is rate-limited there. Build runs 13 and 14 both failed
        with HTTP 429 after three retries, before any step of ours executed --
        so an action is not a convenience the job can degrade without, it is a
        remote dependency that can kill the job outright. git and python are
        already required on this machine by the Chromium build itself.
        """

        for workflow in sorted(WORKFLOW_DIR.glob("*.yml")) + sorted(WORKFLOW_DIR.glob("*.yaml")):
            with self.subTest(workflow=workflow.name):
                self.assertEqual(
                    [],
                    self.USES_STEP.findall(workflow.read_text(encoding="utf-8")),
                    f"{workflow.name} depends on an action download",
                )

    def test_some_workflow_runs_every_check_the_repository_has(self) -> None:
        """A guard script that no workflow invokes is a check nobody runs.

        Enumerated from disk rather than listed here, so adding
        `scripts/verify_something.py` without wiring it in fails immediately
        instead of passing silently for as long as nobody notices.

        Both workflows count. `verify_installed_build.py` reads the build
        output, so it belongs to the build job rather than the guard job --
        running it where no browser exists would report NOT AVAILABLE for
        everything it is for.
        """

        commands = " ".join(self._commands(self.GUARD) + self._commands(WORKFLOW))
        for script in sorted((ROOT / "scripts").glob("*.py")):
            name = script.name
            if not (name.startswith(self.GUARD_PREFIXES) or name in self.GUARD_NAMES):
                continue
            with self.subTest(script=name):
                self.assertIn(name, commands, f"{name} is never run by the guard")

        self.assertIn("unittest discover -s tests", commands)

    def test_every_check_step_invokes_python_directly(self) -> None:
        """The runner is a Windows workstation. A check that needs a bash which
        happens to be on its PATH fails for a reason unrelated to what it is
        checking. The checkout step is the one exception and is a `run: |`
        block, so it is not among the single-line commands.
        """

        for command in self._commands(self.GUARD):
            self.assertTrue(command.startswith("python"), command)

    def test_the_guard_is_dispatch_only(self) -> None:
        """Asserted separately from the fork rule because this is the single
        property that makes running a guard on a physical machine safe."""

        text = self.GUARD.read_text(encoding="utf-8")
        self.assertIn("on:\n  workflow_dispatch:\n", text)
        for event in ("pull_request", "push:", "schedule:"):
            with self.subTest(event=event):
                self.assertNotIn(f"  {event}", text)

    def test_the_checkout_step_leaves_no_credential_on_disk(self) -> None:
        """The runner is a physical machine that outlives the job.

        The token travels in the fetch URL, which lives only in that process's
        arguments. `git remote add` or an `extraheader` config would write it
        into `.git/config`, where it would remain after the job ended.
        """

        for workflow in (self.GUARD, WORKFLOW):
            with self.subTest(workflow=workflow.name):
                text = workflow.read_text(encoding="utf-8")
                self.assertIn("git fetch", text)
                self.assertNotIn("git remote add", text)
                self.assertNotIn("extraheader", text)
                self.assertNotIn("git config", text)


class InstallerDeliveryTests(unittest.TestCase):
    """The runner is the owner's own machine, so the installer is already where
    it needs to be when the build ends. Uploading it to GitHub storage, which a
    private repository is billed for, and downloading it back to the machine
    that produced it, is cost with no delivery.
    """

    def test_the_build_reports_the_installer_instead_of_uploading_it(self) -> None:
        text = WORKFLOW.read_text(encoding="utf-8")
        self.assertNotIn("upload-artifact", text)
        self.assertIn("sunshine-installer-windows-x64.exe", text)
        self.assertIn("size-report.json", text)


if __name__ == "__main__":
    unittest.main()
