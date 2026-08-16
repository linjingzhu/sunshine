"""Static contract tests for the resource-intensive Windows Chromium build."""

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/native-chromium-windows.yml"
SCRIPT = ROOT / "scripts/build_chromium_windows.ps1"


class WindowsBuildContractTests(unittest.TestCase):
    def test_workflow_requires_dedicated_self_hosted_runner(self) -> None:
        text = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("runs-on: [self-hosted, Windows, X64, sunshine-chromium]", text)
        self.assertNotIn("windows-latest", text)
        self.assertIn("timeout-minutes: 720", text)

    def test_workflow_is_explicitly_dispatched(self) -> None:
        text = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("workflow_dispatch:", text)
        self.assertNotIn("pull_request:", text)
        self.assertNotIn("push:", text)

    def test_build_uses_native_chromium_targets(self) -> None:
        text = SCRIPT.read_text(encoding="utf-8")
        self.assertIn("bootstrap_chromium.py", text)
        self.assertIn("gn gen", text)
        self.assertIn("autoninja", text)
        self.assertIn("chrome mini_installer", text)
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


if __name__ == "__main__":
    unittest.main()
