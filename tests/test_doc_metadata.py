"""Tests for the policy-document versioning scheme.

Stable identity, mutable version: a document is addressed by `doc_id` and
canonical path, and neither changes because its contents did. The failure this
guards against is silent -- a reference keeps resolving to a path that has
moved, or stops resolving at all, and an agent follows it to a policy that no
longer says what it used to. So these tests inject each violation and require
the validator to catch it; a checker that only ever passes proves nothing.
"""

from pathlib import Path
import shutil
import sys
import tempfile
import unittest

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY_ROOT / "scripts"))

import validate_doc_metadata as checker  # noqa: E402


class DocMetadataTests(unittest.TestCase):
    def setUp(self) -> None:
        directory = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, directory, True)
        self.root = Path(directory) / "repo"
        shutil.copytree(
            REPOSITORY_ROOT,
            self.root,
            ignore=shutil.ignore_patterns(".git", "__pycache__", "chromium"),
        )

    def failures(self) -> list[str]:
        _, failures = checker.validate(self.root)
        return failures

    def assertRejected(self, needle: str) -> None:
        failures = self.failures()
        self.assertTrue(failures, "the violation was accepted")
        self.assertTrue(
            any(needle in failure for failure in failures),
            f"{needle!r} not named in {failures}",
        )

    def test_the_repository_satisfies_its_own_scheme(self) -> None:
        count, failures = checker.validate(REPOSITORY_ROOT)
        self.assertEqual([], failures)
        self.assertEqual(len(checker.VERSIONED), count)

    def test_a_versioned_filename_is_rejected(self) -> None:
        """`MANAGER_v2.md` puts the version where every citing document must
        know it, so a bump becomes an edit to every file that cites it."""

        shutil.copy(self.root / ".ai/MANAGER.md", self.root / ".ai/MANAGER_v2.md")
        self.assertRejected("filename carries a version")

    def test_a_reference_to_a_versioned_filename_is_rejected(self) -> None:
        path = self.root / ".ai/MANAGER.md"
        path.write_text(path.read_text(encoding="utf-8") + "\nSee `.ai/EXECUTION_1.3.0.md`.\n", encoding="utf-8")
        self.assertRejected("references a versioned filename")

    def test_a_duplicate_doc_id_is_rejected(self) -> None:
        """Two documents with one identity make the identity useless."""

        path = self.root / ".ai/UX.md"
        path.write_text(path.read_text(encoding="utf-8").replace("doc_id: ai-ux", "doc_id: ai-manager", 1), encoding="utf-8")
        self.assertRejected("already used by")

    def test_a_canonical_path_that_is_not_the_real_path_is_rejected(self) -> None:
        """A document's own address must be where it actually lives."""

        path = self.root / ".ai/REVIEW.md"
        path.write_text(
            path.read_text(encoding="utf-8").replace(
                "canonical_path: .ai/REVIEW.md", "canonical_path: .ai/REVIEW_OLD.md", 1
            ),
            encoding="utf-8",
        )
        self.assertRejected("canonical_path says")

    def test_a_reference_that_does_not_resolve_is_rejected(self) -> None:
        path = self.root / ".ai/MANAGER.md"
        path.write_text(path.read_text(encoding="utf-8") + "\nSee `.ai/NOPE.md`.\n", encoding="utf-8")
        self.assertRejected("does not resolve")

    def test_missing_metadata_is_rejected(self) -> None:
        path = self.root / ".ai/UX.md"
        path.write_text(path.read_text(encoding="utf-8").split("---\n", 2)[2], encoding="utf-8")
        self.assertRejected("no metadata block")

    def test_a_version_that_is_not_semver_is_rejected(self) -> None:
        path = self.root / ".ai/UX.md"
        path.write_text(path.read_text(encoding="utf-8").replace("version: 1.0.0", "version: 1.0", 1), encoding="utf-8")
        self.assertRejected("MAJOR.MINOR.PATCH")

    def test_append_only_memory_must_not_carry_a_version(self) -> None:
        """Appending a lesson is not a policy revision."""

        path = self.root / ".ai/memory/PROJECT_LESSONS.md"
        path.write_text(
            "---\ndoc_id: x\nversion: 1.0.0\ncanonical_path: y\nupdated: 2026-01-01\n---\n\n"
            + path.read_text(encoding="utf-8"),
            encoding="utf-8",
        )
        self.assertRejected("must not carry a version")

    def test_the_versioning_policy_has_one_home(self) -> None:
        """Copying the rules into every document is the drift they prevent."""

        homes = [
            relative
            for relative in checker.VERSIONED
            if "MUST use stable canonical paths" in (REPOSITORY_ROOT / relative).read_text(encoding="utf-8")
        ]
        self.assertEqual([".ai/CORE.md"], homes)

    def test_versioning_does_not_become_reporting(self) -> None:
        """The scheme tracks documents; it does not add anything to say.

        The reporting contract is unchanged, and the policy has to say so by
        pointing at it, or the next agent narrates every bump. Naming the
        document by canonical path also puts that claim under the reference
        check, so it cannot outlive the file it cites.
        """

        core = (REPOSITORY_ROOT / ".ai/CORE.md").read_text(encoding="utf-8")
        self.assertIn("do not announce version bumps", core)
        self.assertIn("`.ai/REPORTING.md`", core)
        self.assertIn("history is the source of truth", " ".join(core.split()))


    def test_the_reporting_policy_has_one_home(self) -> None:
        """Silent execution is stated once and referenced elsewhere.

        `.ai/CORE.md` carries the standing default because it is always loaded;
        `.ai/MANAGER.md` carries a pointer. Only `.ai/REPORTING.md` carries the
        escalation exceptions and the report shapes, so there is one place to
        change when they change.
        """

        homes = [
            relative
            for relative in checker.VERSIONED
            if "Mission scope must change" in (REPOSITORY_ROOT / relative).read_text(encoding="utf-8")
        ]
        self.assertEqual([".ai/REPORTING.md"], homes)

        for relative in (".ai/CORE.md", ".ai/MANAGER.md"):
            with self.subTest(document=relative):
                self.assertIn("`.ai/REPORTING.md`", (REPOSITORY_ROOT / relative).read_text(encoding="utf-8"))

    def test_suppression_never_reaches_verification(self) -> None:
        """The rule that keeps this policy from becoming a quality cut.

        Reporting less is only safe while the evidence behind the report is
        still gathered, so the policy has to say so in terms an agent cannot
        read as permission to skip work.
        """

        reporting = " ".join((REPOSITORY_ROOT / ".ai/REPORTING.md").read_text(encoding="utf-8").split())
        self.assertIn("MUST NOT reduce engineering rigor", reporting)
        self.assertIn("Less reporting is not less verification", reporting)
        self.assertIn("Printing less of a log is not reading less of it", reporting)

    def test_escalation_survives_the_silence(self) -> None:
        """Silence is the default, not the rule. The three exceptions are what
        stop it from swallowing a decision the user has to make."""

        reporting = " ".join((REPOSITORY_ROOT / ".ai/REPORTING.md").read_text(encoding="utf-8").split())
        for exception in (
            "A user decision is required",
            "A critical risk appears",
            "Mission scope must change",
        ):
            with self.subTest(exception=exception):
                self.assertIn(exception, reporting)


if __name__ == "__main__":
    unittest.main()
