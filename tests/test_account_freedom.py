"""Tests for the account-freedom check.

The chain that makes Sunshine local-only is upstream and conditional: no OAuth
client means no Dice, which means signin-allowed is false, which means the
first-run experience is skipped. Every link holds only while this repository
ships no credential and patches none of the identity machinery. These tests
inject each violation, because a check that only ever passes proves nothing.
"""

from pathlib import Path
import json
import shutil
import sys
import tempfile
import unittest

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY_ROOT / "scripts"))

import verify_account_freedom as checker  # noqa: E402


class AccountFreedomTests(unittest.TestCase):
    def setUp(self) -> None:
        directory = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, directory, True)
        self.root = Path(directory) / "repo"
        shutil.copytree(
            REPOSITORY_ROOT,
            self.root,
            ignore=shutil.ignore_patterns(".git", "__pycache__", "chromium"),
        )

    def assertRejected(self, needle: str) -> None:
        failures = checker.validate(self.root)
        self.assertTrue(failures, "the violation was accepted")
        self.assertTrue(any(needle in f for f in failures), f"{needle!r} not in {failures}")

    def test_the_repository_is_account_free_today(self) -> None:
        """Enforces: PO-A1, PO-A2, PO-A3."""

        self.assertEqual([], checker.validate(REPOSITORY_ROOT))

    def test_a_plain_api_key_is_rejected(self) -> None:
        (self.root / "config/keys.txt").write_text(
            "AIza" + "B" * 35 + "\n", encoding="utf-8"
        )
        self.assertRejected("Google API key")

    def test_a_base64_encoded_client_id_is_rejected(self) -> None:
        """The criterion says "in any encoding", so the obvious hiding place
        has to be covered or the check is theatre."""

        import base64

        secret = "123456789012-abcdefghijklmnopqrstuvwxyz01.apps.googleusercontent.com"
        blob = base64.b64encode(secret.encode()).decode()
        (self.root / "config/blob.txt").write_text(blob + "\n", encoding="utf-8")
        self.assertRejected("OAuth client id")

    def test_a_build_argument_configuring_a_key_is_rejected(self) -> None:
        """A key need not be committed to be configured."""

        script = self.root / "scripts/build_chromium_windows.ps1"
        script.write_text(
            script.read_text(encoding="utf-8") + '\n# google_api_key = "x"\n', encoding="utf-8"
        )
        self.assertRejected("google_api_key")

    def test_patching_the_identity_machinery_is_rejected(self) -> None:
        """Restoring sign-in by patching upstream would bypass the whole chain,
        including the testing setter that ignores a missing OAuth client."""

        (self.root / "downstream/patches/0003-x.patch").write_text(
            "--- a/chrome/browser/signin/account_consistency_mode_manager.cc\n"
            "+++ b/chrome/browser/signin/account_consistency_mode_manager.cc\n",
            encoding="utf-8",
        )
        self.assertRejected("protected area")

    def test_registering_an_account_command_is_rejected(self) -> None:
        path = self.root / "first_party/commands.json"
        registry = json.loads(path.read_text(encoding="utf-8"))
        entry = dict(registry["commands"][0])
        entry["id"] = "browser.signin.start"
        registry["commands"].append(entry)
        path.write_text(json.dumps(registry, indent=2), encoding="utf-8")
        self.assertRejected("account or profile-lifecycle action")


if __name__ == "__main__":
    unittest.main()
