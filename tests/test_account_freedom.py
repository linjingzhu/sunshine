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
        """Enforces: PO-A1, PO-A2, PO-A3, PO-A17."""

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

    # --- PO-A16: Sunshine's own credential name carries no value -------------

    def test_a_placeholder_client_id_is_rejected(self) -> None:
        """The failure PO-A1 cannot see.

        This value is not shaped like a Google client id and sets none of
        Chrome's build arguments, so every rule that existed before PO-A16
        accepts it -- and it makes `LinkAvailable()` true in every build made
        from this tree, which is the one state section 5 of the plan says
        cannot exist.
        """

        (self.root / "first_party/creds.h").write_text(
            '#define SUNSHINE_ACCOUNT_CLIENT_ID "test-1234"\n', encoding="utf-8"
        )
        self.assertRejected("PO-A16")

    def test_a_build_argument_spelling_of_the_same_value_is_rejected(self) -> None:
        (self.root / "config/args.gn").write_text(
            'sunshine_account_client_id = "1234-abc.apps.example"\n', encoding="utf-8"
        )
        self.assertRejected("PO-A16")

    def test_declaring_the_name_without_a_value_is_accepted(self) -> None:
        """The name has to be usable here or the feature cannot be written.

        This is exactly the line `chrome/browser/ui/sunshine/account_link.cc`
        carries today, and a rule that rejected it would forbid the design it
        is meant to protect.
        """

        (self.root / "first_party/creds.h").write_text(
            "constexpr char kClientId[] = SUNSHINE_ACCOUNT_CLIENT_ID;\n", encoding="utf-8"
        )
        self.assertEqual([], checker.validate(self.root))

    def test_an_empty_value_is_accepted(self) -> None:
        """An empty define leaves the link absent, which is the correct state
        for a build with no credential -- there is nothing to prohibit."""

        (self.root / "first_party/creds.h").write_text(
            '#define SUNSHINE_ACCOUNT_CLIENT_ID ""\n', encoding="utf-8"
        )
        self.assertEqual([], checker.validate(self.root))

    # --- PO-A17: no reach into Chromium's identity surface -------------------

    def test_holding_an_identity_manager_is_rejected(self) -> None:
        """PO-A2 lets this through, which is why PO-A17 exists.

        The file below patches nothing upstream. It leaves every protected area
        untouched and still gives the profile a browser identity, because it
        calls into the machinery instead of editing it.
        """

        (self.root / "downstream/patches/0090-x.patch").write_text(
            "--- /dev/null\n"
            "+++ b/chrome/browser/ui/sunshine/account_link.cc\n"
            "+  auto* manager = IdentityManagerFactory::GetForProfile(profile);\n",
            encoding="utf-8",
        )
        self.assertEqual([], checker.check_patch_stack_avoids_identity(self.root, []) or [])
        self.assertRejected("PO-A17")

    def test_reading_the_cookie_jar_is_rejected(self) -> None:
        """Step 4 of the plan turns on the code arriving on Sunshine's own
        socket rather than out of the jar. Reading the jar is how the promise
        that nothing is promoted out of it would stop being true."""

        (self.root / "first_party/jar.ts").write_text(
            "const jar = new CookieManager();\n", encoding="utf-8"
        )
        self.assertRejected("cookie jar")

    def test_a_sync_reference_is_rejected(self) -> None:
        (self.root / "first_party/s.cc").write_text(
            "syncer::SyncService* s = nullptr;\n", encoding="utf-8"
        )
        self.assertRejected("PO-A17")

    def test_the_rule_covers_files_no_one_told_it_about(self) -> None:
        """The scope is a property, not a list of account files.

        A path-scoped version of this rule would pass here, because nothing
        about this filename says "account". That is the failure mode IU-15
        records: a guard that must be told where to look stops applying the
        moment someone adds a file it was not told about.
        """

        (self.root / "first_party/unrelated_helper.ts").write_text(
            "export const x = 'PrimaryAccount';\n", encoding="utf-8"
        )
        self.assertRejected("PO-A17")

    def test_a_removed_line_is_not_a_use(self) -> None:
        """A patch that deletes a call is the opposite of making one."""

        (self.root / "downstream/patches/0091-x.patch").write_text(
            "--- a/chrome/browser/ui/sunshine/x.cc\n"
            "+++ b/chrome/browser/ui/sunshine/x.cc\n"
            "-  auto* m = IdentityManagerFactory::GetForProfile(profile);\n"
            "+  return false;\n",
            encoding="utf-8",
        )
        self.assertEqual([], checker.validate(self.root))

    def test_a_patch_header_naming_an_upstream_path_is_not_a_use(self) -> None:
        """`+++ b/path` also begins with `+`, and every patch has one.

        This is the likeliest false positive in the check, and a `+++` header
        that happens to name a sync path must not read as a call into sync.
        """

        (self.root / "downstream/patches/0092-x.patch").write_text(
            "--- a/chrome/browser/ui/sunshine/x.cc\n"
            "+++ b/chrome/browser/ui/sunshine/sync_pb_helper.cc\n"
            "+  return false;\n",
            encoding="utf-8",
        )
        self.assertEqual([], checker.validate(self.root))

    def test_the_guard_does_not_scan_itself(self) -> None:
        """A guard names what it prohibits.

        `scripts/` is in scope, so without this the check's own symbol table
        would be its first violation -- and a check that cannot pass on a clean
        tree gets deleted rather than obeyed.
        """

        self.assertTrue(checker._is_guard(Path("verify_account_freedom.py")))
        labels = [label for label, _ in checker.sunshine_sources(REPOSITORY_ROOT)]
        self.assertNotIn("scripts/verify_account_freedom.py", labels)
        self.assertTrue(labels, "nothing was scanned at all")

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
