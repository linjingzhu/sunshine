#!/usr/bin/env python3
"""Prove each guard fails on the defect it exists to catch.

LESSONS_FROM_PRACTICE.md entry 15: a guard is code, and a guard that has never
failed on purpose has not been tested. Every test here copies the tree, breaks
exactly one thing, and asserts that the matching check reports it — plus one
test that the untouched tree is clean, so a guard cannot pass by failing on
everything.

Standard library only:

    python3 .ai/tools/test_check_policy_set.py
"""

from __future__ import annotations

import hashlib
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CHECKER = Path(__file__).resolve().parent / "check_policy_set.py"


def first_denylisted_term(root: Path) -> str:
    """The first term the repository's own denylist declares — the tests do
    not assume the set's seed names, so they also run where the set was adopted
    and the denylist holds that project's names."""
    for line in (root / ".ai" / "tools" / "portability-denylist.txt").read_text(encoding="utf-8").splitlines():
        if line.strip() and not line.lstrip().startswith("#"):
            return line.strip()
    raise AssertionError("the denylist declares no term")


def delivered_digest(path: Path) -> str:
    """What a lock records for a file, worked out here rather than borrowed
    from the checker, so the two cannot agree by sharing a mistake."""
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def run_checker(root: Path) -> tuple[int, str]:
    result = subprocess.run(
        [sys.executable, str(CHECKER), str(root)],
        capture_output=True,
        text=True,
        check=False,
    )
    return result.returncode, result.stdout + result.stderr


# Tests skipped in a repository that adopted the set, each with its reason.
# They run unconditionally at the set's home. Every other test must pass in an
# adopter too, and a test is listed for one of two reasons only, which its entry
# names:
#   - its subject exists only at the set's home;
#   - it exposes a KNOWN BLIND SPOT of the check in an adopter. Each such entry
#     names the roadmap item that tracks the blind spot, so that a skip never
#     stands in for a fix nobody owns.
# Never to make a suite green. This list is the one place a reviewer has to read.
NEEDS_THE_SETS_HOME = {
    "test_the_set_must_keep_shipping_its_agents":
        "the set must ship its agent definitions; an adopter may remove them",
    "test_missing_codex_entry_is_reported_at_set_home":
        "the set must ship AGENTS.md; an adopter need not",
    "test_missing_codex_capabilities_are_reported_at_set_home":
        "the set must ship its Codex capabilities; an adopter may remove them",
    "test_codex_entry_references_are_checked":
        "KNOWN BLIND SPOT, only in a repository adopted before 4.0.0 — without "
        "`.ai/set.lock` a reference into a capability folder is not checked, "
        "because nothing tells a removed capability from one that never "
        "existed. Its next upgrade writes the lock, and the test then runs",
}
AT_SET_HOME = (ROOT / "LESSONS_FROM_PRACTICE.md").exists()


class GuardTests(unittest.TestCase):
    def setUp(self) -> None:
        reason = NEEDS_THE_SETS_HOME.get(self._testMethodName)
        if reason and reason.startswith("KNOWN BLIND SPOT") and (ROOT / ".ai" / "set.lock").exists():
            reason = None  # a subscriber's lock closes the blind spot
        if reason and not AT_SET_HOME:
            # A blind spot does not need the set's home; it names itself.
            blind_spot = reason.startswith("KNOWN BLIND SPOT")
            self.skipTest(reason if blind_spot else f"needs the set's home: {reason}")
        self.tmp = Path(tempfile.mkdtemp(prefix="policy-set-"))
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.copy = self.tmp / "repo"
        shutil.copytree(
            ROOT,
            self.copy,
            ignore=shutil.ignore_patterns(".git", "__pycache__"),
        )

    def edit(self, relative: str, transform) -> None:
        path = self.copy / relative
        path.write_text(transform(path.read_text(encoding="utf-8")), encoding="utf-8")

    def assert_fails_with(self, fragment: str) -> None:
        code, out = run_checker(self.copy)
        self.assertEqual(code, 1, f"expected a failure, got a clean run:\n{out}")
        self.assertIn(fragment, out, f"expected {fragment!r} in:\n{out}")

    # -- the control: an untouched copy must be clean ----------------------
    def test_unmodified_tree_passes(self) -> None:
        code, out = run_checker(self.copy)
        self.assertEqual(code, 0, f"the tree itself does not pass:\n{out}")

    # -- check 1: front matter --------------------------------------------
    def test_missing_front_matter_field(self) -> None:
        self.edit(".ai/UX.md", lambda t: t.replace("version: ", "revision: ", 1))
        self.assert_fails_with("missing `version`")

    def test_duplicate_doc_id(self) -> None:
        self.edit(".ai/UX.md", lambda t: t.replace("doc_id: ai-ux", "doc_id: ai-core", 1))
        self.assert_fails_with("also claimed by")

    def test_canonical_path_not_matching_location(self) -> None:
        self.edit(
            ".ai/UX.md",
            lambda t: t.replace("canonical_path: .ai/UX.md", "canonical_path: .ai/UI.md", 1),
        )
        self.assert_fails_with("canonical_path is")

    def test_version_not_semver(self) -> None:
        self.edit(".ai/UX.md", lambda t: t.replace("version: 1.1.0", "version: 1.0", 1))
        self.assert_fails_with("is not MAJOR.MINOR.PATCH")

    # -- check 2: cross-references ----------------------------------------
    def test_reference_to_missing_section(self) -> None:
        self.edit(
            ".ai/MANAGER.md",
            lambda t: t.replace("§ *Conflict prevention*", "§ *Conflict Maps*", 1),
        )
        self.assert_fails_with("has no section")

    def test_reference_to_missing_file(self) -> None:
        self.edit(
            ".ai/MANAGER.md",
            lambda t: t.replace("`.ai/EXECUTION.md`", "`.ai/EXECUTION_PLAN.md`", 1),
        )
        self.assert_fails_with("which does not exist")

    def test_a_run_report_may_name_a_file_that_has_since_gone(self) -> None:
        # Found in two adopters: a report that preserved an old entry file
        # named documents the repository later removed.
        reports = self.copy / ".ai" / "reports"
        reports.mkdir(parents=True, exist_ok=True)
        (reports / "2026-01-01-run.md").write_text(
            "# Run report\n\nRead `docs/GONE.md` and `.ai/GONE.md` § *Anything*.\n",
            encoding="utf-8",
        )
        code, out = run_checker(self.copy)
        self.assertEqual(code, 0, out)

    def test_a_document_still_in_force_may_not(self) -> None:
        # The exclusion is the reports folder, not every instance file: a
        # project's lessons are read at every run and must point somewhere.
        lessons = self.copy / ".ai" / "memory" / "PROJECT_LESSONS.md"
        lessons.write_text("# Lessons\n\nSee `docs/GONE.md`.\n", encoding="utf-8")
        self.assert_fails_with("references `docs/GONE.md`")

    # -- check 3: one owner per heading ------------------------------------
    def test_rule_reduplicated_into_a_second_file(self) -> None:
        self.edit(
            ".ai/MANAGER.md",
            lambda t: t + "\n## Compile and build ladder\n\nEdit → check → compile.\n",
        )
        self.assert_fails_with("is claimed by")

    # -- check 4: portability ---------------------------------------------
    def test_denylisted_name_in_a_portable_file(self) -> None:
        term = first_denylisted_term(self.copy)
        self.edit(".ai/CORE.md", lambda t: t + f"\nBuilt for {term} by default.\n")
        self.assert_fails_with(f"`{term}`")

    def test_denylisted_name_is_allowed_in_the_instance_files(self) -> None:
        term = first_denylisted_term(self.copy)
        instance = self.copy / ".ai" / "PROJECT_CONTEXT.md"
        instance.write_text(
            "---\ndoc_id: ai-project-context\nversion: 1.0.0\n"
            "canonical_path: .ai/PROJECT_CONTEXT.md\nupdated: 2026-09-03\n---\n\n"
            f"# {term} Project Context\n\n{term} is the product.\n\n"
            "## Facts the checks read\n\n```text\nrepository_mode: personal\nbase_branch: main\n"
            "merge_deploys: no\nruntime_gate: none\ntest_command: npm test\nlint_command: none\n"
            "build_command: none\ngenerated: none\nexternal_scripts: none\npublic_ids: none\n"
            "owner_ledger: docs/OWNER_ACTIONS.md\n```\n",
            encoding="utf-8",
        )
        code, out = run_checker(self.copy)
        self.assertEqual(code, 0, f"instance files must be allowed to name the project:\n{out}")

    def test_missing_denylist_is_reported_not_ignored(self) -> None:
        (self.copy / ".ai" / "tools" / "portability-denylist.txt").unlink()
        self.assert_fails_with("is missing")

    # -- check 5: changelog -----------------------------------------------
    def test_release_without_improvements(self) -> None:
        self.edit(
            ".ai/CHANGELOG.md",
            lambda t: t.replace("## 2.1.0 — 2026-09-03", "## 2.2.0 — 2026-09-04\n\n## 2.1.0 — 2026-09-03", 1),
        )
        self.assert_fails_with("no improvements listed")

    def test_release_with_a_malformed_version(self) -> None:
        self.edit(".ai/CHANGELOG.md", lambda t: t.replace("## 2.1.0 —", "## 2.1 —", 1))
        self.assert_fails_with("version is not MAJOR.MINOR.PATCH")

    def test_release_with_a_malformed_date(self) -> None:
        self.edit(".ai/CHANGELOG.md", lambda t: t.replace("— 2026-09-03", "— Sept 2026", 1))
        self.assert_fails_with("is not YYYY-MM-DD")

    def test_releases_out_of_order(self) -> None:
        self.edit(
            ".ai/CHANGELOG.md",
            lambda t: t.replace("## 2.1.0 — 2026-09-03", "## 1.9.0 — 2026-09-03", 1),
        )
        self.assert_fails_with("newest goes first")

    def test_version_recorded_twice(self) -> None:
        self.edit(
            ".ai/CHANGELOG.md",
            lambda t: t.replace(
                "## 2.0.1 — 2026-09-03",
                "## 2.1.0 — 2026-09-03\n\n- a second entry claiming a version already used\n\n## 2.0.1 — 2026-09-03",
                1,
            ),
        )
        self.assert_fails_with("recorded more than once")

    def test_missing_changelog(self) -> None:
        (self.copy / ".ai" / "CHANGELOG.md").unlink()
        self.assert_fails_with("is missing")

    def test_format_example_in_a_code_fence_is_not_a_release(self) -> None:
        # The changelog documents its own format inside a fence. Reading that
        # as a real entry was the guard's own first false positive here.
        #
        # The expected count is read from the changelog rather than written
        # here: a number kept in two places drifts, and this one would drift on
        # every release (entry 6).
        text = (self.copy / ".ai" / "CHANGELOG.md").read_text(encoding="utf-8")
        releases = len(re.findall(r"^## \d+\.\d+\.\d+ — ", text, re.M))
        self.assertGreater(releases, 0, "no release entries to count")

        code, out = run_checker(self.copy)
        self.assertEqual(code, 0, out)
        self.assertIn(f"{releases} release entries", out)

    # -- check 7: capability definitions -----------------------------------
    def test_agent_definition_without_front_matter(self) -> None:
        agent = self.copy / ".claude" / "agents" / "fast-explorer.md"
        agent.write_text("Just prose, no front matter.\n", encoding="utf-8")
        self.assert_fails_with("no front matter block")

    def test_agent_definition_missing_description(self) -> None:
        agent = self.copy / ".claude" / "agents" / "fast-explorer.md"
        text = agent.read_text(encoding="utf-8")
        agent.write_text(text.replace("description:", "summary:", 1), encoding="utf-8")
        self.assert_fails_with("missing `description`")

    def test_agent_name_not_matching_its_file(self) -> None:
        # A Mission Packet names the agent by file; a definition declaring a
        # different name is one the harness will not find.
        agent = self.copy / ".claude" / "agents" / "fast-explorer.md"
        text = agent.read_text(encoding="utf-8")
        agent.write_text(text.replace("name: fast-explorer", "name: explorer", 1), encoding="utf-8")
        self.assert_fails_with("would not find it")

    def test_agents_directory_present_but_empty(self) -> None:
        for path in (self.copy / ".claude" / "agents").glob("*.md"):
            path.unlink()
        self.assert_fails_with("ships no definition")

    def test_the_set_must_keep_shipping_its_agents(self) -> None:
        # At the set's home the definitions are not optional: HARNESS.md names
        # them, so losing them silently would leave that pointer dangling.
        shutil.rmtree(self.copy / ".claude")
        self.assert_fails_with("the set ships the capabilities")

    def test_skill_without_front_matter(self) -> None:
        skill = self.copy / ".claude" / "skills" / "auto-dev" / "SKILL.md"
        skill.write_text("Just prose, no front matter.\n", encoding="utf-8")
        self.assert_fails_with("no front matter block")

    def test_skill_name_not_matching_its_directory(self) -> None:
        # A skill is invoked by the name of its folder, not of its file — every
        # one of them is called SKILL.md, so the folder is the only name there
        # is. A definition declaring a different one cannot be reached.
        skill = self.copy / ".claude" / "skills" / "auto-dev" / "SKILL.md"
        text = skill.read_text(encoding="utf-8")
        skill.write_text(text.replace("name: auto-dev", "name: autodev", 1), encoding="utf-8")
        self.assert_fails_with("would not find it")

    def test_skill_directory_without_a_skill_file(self) -> None:
        # The quiet shape: a folder that looks like a skill and offers nothing.
        for path in (self.copy / ".claude" / "skills").glob("*/SKILL.md"):
            path.unlink()
        self.assert_fails_with("ships no definition")

    def test_a_capability_pointer_that_resolves_to_nothing(self) -> None:
        # A skill is mostly pointers into `.ai/`. They are checked for the same
        # reason the policy documents' are: nothing else notices when one rots.
        skill = self.copy / ".claude" / "skills" / "auto-dev" / "SKILL.md"
        text = skill.read_text(encoding="utf-8")
        skill.write_text(text.replace("`.ai/LOOP.md`", "`.ai/CADENCE.md`"), encoding="utf-8")
        self.assert_fails_with("which does not exist")

    def test_an_adopted_tree_without_agents_is_not_a_failure(self) -> None:
        # The same tree minus the set-home marker is an adopting repository,
        # which may never have taken the agents. Absent is not broken there,
        # and the references into them are not dangling either.
        shutil.rmtree(self.copy / ".claude")
        shutil.rmtree(self.copy / ".codex" / "agents")
        shutil.rmtree(self.copy / ".agents" / "skills")
        (self.copy / "LESSONS_FROM_PRACTICE.md").unlink(missing_ok=True)
        code, out = run_checker(self.copy)
        self.assertEqual(code, 0, out)
        self.assertIn("nothing to check", out)

    def test_a_dangling_capability_reference_fails_in_an_adopted_tree(self) -> None:
        # A pointer written *inside* a capability is checked in an adopting
        # repository like anywhere else. The resolver's guess relative to the
        # referring file lands inside that file's own capability folder; read
        # as a reference into the folder, it makes every dangling pointer inside
        # an agent definition or skill pass in an adopter while the identical
        # edit fails at the set's home. One file per place a capability lives.
        (self.copy / "LESSONS_FROM_PRACTICE.md").unlink(missing_ok=True)
        for name in (
            ".claude/agents/fast-explorer.md",
            ".claude/skills/auto-dev/SKILL.md",
            ".codex/agents/fast-explorer.toml",
            ".agents/skills/auto-dev/SKILL.md",
            ".agents/skills/auto-dev/agents/openai.yaml",
        ):
            # A path naming a directory, and a sibling written bare or `./`.
            for ref in (".ai/MISSING.md", "MISSING.md", "./MISSING.md"):
                with self.subTest(capability=name, reference=ref):
                    path = self.copy / name
                    original = path.read_text(encoding="utf-8")
                    path.write_text(original + f"\n# Read `{ref}` first.\n", encoding="utf-8")
                    try:
                        code, out = run_checker(self.copy)
                        self.assertNotEqual(code, 0, f"{name}: `{ref}` passed:\n{out}")
                        self.assertIn(f"{name}: references `{ref}`, which does not exist", out)
                    finally:
                        path.write_text(original, encoding="utf-8")

    def test_every_home_only_test_exists(self) -> None:
        # A stale name would leave the list claiming an exemption nobody uses.
        stale = [name for name in NEEDS_THE_SETS_HOME if not hasattr(self, name)]
        self.assertEqual(stale, [], "listed as needing the set's home, but no such test")

    def test_missing_codex_entry_is_reported_at_set_home(self) -> None:
        (self.copy / "AGENTS.md").unlink()
        self.assert_fails_with("AGENTS.md is missing")

    def test_missing_codex_capabilities_are_reported_at_set_home(self) -> None:
        shutil.rmtree(self.copy / ".codex" / "agents")
        self.assert_fails_with(".codex/agents is missing")

    def test_codex_skill_name_must_match_its_directory(self) -> None:
        self.edit(
            ".agents/skills/auto-dev/SKILL.md",
            lambda t: t.replace("name: auto-dev", "name: other-skill", 1),
        )
        self.assert_fails_with("would not find it")

    def test_native_agent_invalid_toml_is_reported(self) -> None:
        self.edit(".codex/agents/fast-explorer.toml", lambda t: t + '\nname = "duplicate"\n')
        self.assert_fails_with("invalid TOML")

    def test_native_agent_missing_instructions_is_reported(self) -> None:
        self.edit(
            ".codex/agents/fast-explorer.toml",
            lambda t: t.replace("developer_instructions", "instructions", 1),
        )
        self.assert_fails_with("missing `developer_instructions`")

    def test_native_agent_name_must_match_its_file(self) -> None:
        self.edit(
            ".codex/agents/fast-explorer.toml",
            lambda t: t.replace('name = "fast-explorer"', 'name = "other-explorer"', 1),
        )
        self.assert_fails_with("would not find it")

    def test_native_agent_non_string_description_is_reported(self) -> None:
        self.edit(
            ".codex/agents/fast-explorer.toml",
            lambda t: re.sub(r'^description = .*$', 'description = 123', t, count=1, flags=re.M),
        )
        self.assert_fails_with("`description` must be a non-empty string")

    def test_native_agent_model_is_optional(self) -> None:
        # The edit is the point here, not a drift from the set: in a subscriber
        # the lock would rightly report it, so the lock goes from the copy.
        (self.copy / ".ai" / "set.lock").unlink(missing_ok=True)
        self.edit(
            ".codex/agents/fast-explorer.toml",
            lambda t: re.sub(r'^model = .*\n', '', t, count=1, flags=re.M),
        )
        code, out = run_checker(self.copy)
        self.assertEqual(code, 0, out)

    def test_native_agent_invalid_sandbox_is_reported(self) -> None:
        self.edit(
            ".codex/agents/fast-explorer.toml",
            lambda t: re.sub(r'^sandbox_mode = .*$', 'sandbox_mode = "readonly"', t, count=1, flags=re.M),
        )
        self.assert_fails_with("invalid `sandbox_mode`")

    def test_codex_entry_references_are_checked(self) -> None:
        self.edit("AGENTS.md", lambda t: t + "\nRead `.codex/agents/missing.toml`.\n")
        self.assert_fails_with("references `.codex/agents/missing.toml`, which does not exist")

    def test_native_agent_references_are_checked(self) -> None:
        self.edit(".codex/agents/fast-explorer.toml", lambda t: t + '\n# Read `.ai/MISSING.md`.\n')
        self.assert_fails_with(".codex/agents/fast-explorer.toml: references `.ai/MISSING.md`")

    def test_codex_skill_references_are_checked(self) -> None:
        self.edit(".agents/skills/auto-dev/SKILL.md", lambda t: t + "\nRead `.ai/MISSING.md`.\n")
        self.assert_fails_with(".agents/skills/auto-dev/SKILL.md: references `.ai/MISSING.md`")

    def test_codex_skill_metadata_references_are_checked(self) -> None:
        self.edit(
            ".agents/skills/auto-dev/agents/openai.yaml",
            lambda t: t + "\n# Read `.ai/MISSING.md`.\n",
        )
        self.assert_fails_with("agents/openai.yaml: references `.ai/MISSING.md`")

    def test_codex_entry_and_capabilities_are_portable(self) -> None:
        term = first_denylisted_term(self.copy)
        paths = (
            "AGENTS.md", ".codex/agents/fast-explorer.toml",
            ".agents/skills/auto-dev/SKILL.md", ".agents/skills/auto-dev/agents/openai.yaml",
        )
        for path in paths:
            self.edit(path, lambda t: t + f"\n# {term}\n")
        code, out = run_checker(self.copy)
        self.assertEqual(code, 1, out)
        for path in paths:
            self.assertIn(f"{path}: 1x `{term}`", out)

    # -- check 4: the roadmap is an instance file --------------------------
    def test_the_roadmap_may_name_the_project(self) -> None:
        # A roadmap lists one product's features by name. It is an instance
        # file for the same reason the project context is, and a check that
        # forbade the name would forbid the file.
        term = first_denylisted_term(self.copy)
        (self.copy / ".ai" / "ROADMAP.md").write_text(
            f"# Roadmap\n\n## Ship the {term} importer\n\nstate: proposed\n",
            encoding="utf-8",
        )
        code, out = run_checker(self.copy)
        self.assertEqual(code, 0, out)

    # -- check 6: project context -----------------------------------------
    FILLED_CONTEXT = (
        "---\ndoc_id: ai-project-context\nversion: 1.0.0\n"
        "canonical_path: .ai/PROJECT_CONTEXT.md\nupdated: 2026-09-03\n---\n\n"
        "# Example Context\n\n## Facts the checks read\n\n```text\nrepository_mode: personal\nbase_branch: main\n"
        "merge_deploys: no\nruntime_gate: none\ntest_command: npm test\n"
        "lint_command: none\nbuild_command: none\ngenerated: none\n"
        "external_scripts: none\npublic_ids: none\nowner_ledger: docs/OWNER_ACTIONS.md\n```\n"
    )

    def write_context(self, text: str) -> None:
        (self.copy / ".ai" / "PROJECT_CONTEXT.md").write_text(text, encoding="utf-8")

    def test_filled_context_passes(self) -> None:
        self.write_context(self.FILLED_CONTEXT)
        code, out = run_checker(self.copy)
        self.assertEqual(code, 0, f"a complete context must pass:\n{out}")

    def test_context_missing_a_key(self) -> None:
        self.write_context(self.FILLED_CONTEXT.replace("runtime_gate: none\n", ""))
        self.assert_fails_with("missing `runtime_gate`")

    def test_context_with_a_placeholder_left(self) -> None:
        self.write_context(self.FILLED_CONTEXT.replace("base_branch: main", "base_branch: <branch>"))
        self.assert_fails_with("still holds a placeholder")

    def test_context_with_a_template_line_left(self) -> None:
        self.write_context(self.FILLED_CONTEXT + "\n> **This is a template.**\n")
        self.assert_fails_with("still carries the template line")

    def test_context_with_a_value_outside_its_enum(self) -> None:
        self.write_context(self.FILLED_CONTEXT.replace("merge_deploys: no", "merge_deploys: sometimes"))
        self.assert_fails_with("expected one of")

    def test_template_that_lost_a_key(self) -> None:
        self.edit(".ai/PROJECT_CONTEXT.template.md", lambda t: t.replace("generated: ", "generated_files: ", 1))
        self.assert_fails_with("does not declare `generated`")

    # -- check 8: document versions ----------------------------------------
    # The copy is made a repository whose one commit is the newest release,
    # then a release entry above it opens the release under test. The check
    # asks only where the set lives, so in an adopter the copy is made to look
    # like the set's home: these tests then run there too, rather than skip.
    def as_the_sets_home(self) -> None:
        lessons = self.copy / "LESSONS_FROM_PRACTICE.md"
        if not lessons.exists():
            lessons.write_text("# Lessons\n", encoding="utf-8")
    def git(self, *args: str) -> str:
        return subprocess.run(
            ["git", "-c", "user.name=test", "-c", "user.email=test@example.invalid",
             "-c", "commit.gpgsign=false", "-C", str(self.copy), *args],
            capture_output=True, text=True, check=True,
        ).stdout

    def commit(self, message: str) -> None:
        self.git("add", "-A")
        self.git("commit", "-q", "-m", message)

    def release_then_open_the_next(self) -> None:
        self.as_the_sets_home()
        self.git("init", "-q")
        self.commit("the previous release")
        self.open_a_release()

    def open_a_release(self, version: str = "99.0.0", day: str = "01") -> None:
        self.edit(
            ".ai/CHANGELOG.md",
            lambda t: re.sub(
                r"^(## \d+\.\d+\.\d+ — )",
                f"## {version} — 2099-01-{day}\n\n- the release {version}\n\n---\n\n\\1",
                t, count=1, flags=re.M,
            ),
        )

    def correct_an_old_entry(self) -> None:
        def correct(text: str) -> str:
            older = list(re.finditer(r"^## \d+\.\d+\.\d+ — ", text, re.M))[2]
            bullet = text.index("\n- ", older.end())
            return text[:bullet] + "\n- (corrected)" + text[bullet + 2 :]
        self.edit(".ai/CHANGELOG.md", correct)

    def change(self, relative: str = ".ai/UX.md") -> None:
        self.edit(relative, lambda t: t + "\nA sentence the release under test added.\n")

    def bump(self, relative: str = ".ai/UX.md", level: int = 2) -> None:
        def raise_version(text: str) -> str:
            found = re.search(r"^version: (\d+)\.(\d+)\.(\d+)$", text, re.M)
            parts = [int(n) for n in found.groups()]
            parts[level] += 1
            parts[level + 1 :] = [0] * (2 - level)
            return text.replace(found.group(0), "version: " + ".".join(map(str, parts)), 1)
        self.edit(relative, raise_version)

    def assert_versions_pass(self) -> None:
        # Only this check's line: in an adopter made to look like the set's
        # home, the set-home checks fail on files an adopter never had.
        _, out = run_checker(self.copy)
        self.assertIn("[PASS] document versions", out)

    # A branch whose work began before a release, and that merges the base
    # branch in: the merge holds the branch's work too, so the release is the
    # side the merge brought in.
    def branch_off_the_previous_release(self) -> None:
        self.as_the_sets_home()
        self.git("init", "-q", "-b", "base")
        self.commit("the release before")
        self.git("checkout", "-q", "-b", "work")

    def release_on_the_base_branch(self) -> None:
        self.git("checkout", "-q", "base")
        self.open_a_release("99.0.0", "01")
        self.change(".ai/EXECUTION.md")
        self.bump(".ai/EXECUTION.md")
        self.commit("release 99.0.0")
        self.git("checkout", "-q", "work")

    def merge_the_base_branch(self, changelog: str | None = None) -> None:
        subprocess.run(
            ["git", "-c", "user.name=test", "-c", "user.email=test@example.invalid",
             "-C", str(self.copy), "merge", "-q", "--no-edit", "--no-commit", "base"],
            capture_output=True, check=False,
        )
        if changelog is not None:
            (self.copy / ".ai" / "CHANGELOG.md").write_text(changelog, encoding="utf-8")
        self.commit("merge the base branch")

    def name_the_base_branch(self) -> None:
        # What a clone records as `origin/HEAD`, without a remote to clone from.
        self.git("update-ref", "refs/remotes/origin/base", "base")
        self.git("symbolic-ref", "refs/remotes/origin/HEAD", "refs/remotes/origin/base")

    def work_begun_before_a_release_then_merged_with_it(self) -> None:
        self.branch_off_the_previous_release()
        self.change()
        self.commit("work, unbumped")
        self.release_on_the_base_branch()
        self.merge_the_base_branch()
        self.open_a_release("100.0.0", "02")
        self.commit("the entry")

    def test_work_begun_before_a_release_and_merged_with_it_is_still_judged(self) -> None:
        self.work_begun_before_a_release_then_merged_with_it()
        self.name_the_base_branch()
        self.assert_fails_with(".ai/UX.md: text changed since 99.0.0")

    def test_without_the_base_branch_such_a_merge_is_not_guessed(self) -> None:
        # The same graph as a release that landed on the base branch after an
        # entry-less change did; only the base branch tells them apart.
        self.work_begun_before_a_release_then_merged_with_it()
        _, out = run_checker(self.copy)
        self.assertIn("[SKIP] document versions", out)
        self.assertIn("origin/HEAD", out)

    def test_a_change_that_landed_before_a_release_merged_belongs_to_that_release(self) -> None:
        # An entry-less change reached the base branch while a release was in
        # review. It shipped with that release, so the next release bumping
        # the same document once has bumped it once.
        self.as_the_sets_home()
        self.git("init", "-q", "-b", "base")
        self.commit("the release before")
        self.git("checkout", "-q", "-b", "release")
        self.change()
        self.bump()
        self.open_a_release("99.0.0", "01")
        self.commit("release 99.0.0")
        self.git("checkout", "-q", "-b", "hotfix", "base")
        self.change(".ai/EXECUTION.md")
        self.bump(".ai/EXECUTION.md")
        self.commit("an entry-less change")
        self.git("checkout", "-q", "base")
        self.git("merge", "-q", "--no-ff", "--no-edit", "hotfix")
        self.git("merge", "-q", "--no-ff", "--no-edit", "release")
        self.name_the_base_branch()
        self.git("checkout", "-q", "-b", "next")
        self.edit(".ai/EXECUTION.md", lambda t: t + "\nAnother sentence, in the next release.\n")
        self.bump(".ai/EXECUTION.md")
        self.open_a_release("100.0.0", "02")
        self.commit("release 100.0.0")
        self.assert_versions_pass()

    def test_a_release_merged_in_under_a_newer_entry_is_found(self) -> None:
        # The shape of a real merge in this set's history: the branch had its
        # own entry on top when it merged the base branch's release.
        self.branch_off_the_previous_release()
        self.change()
        self.open_a_release("100.0.0", "02")
        self.commit("work with its entry, unbumped")
        self.release_on_the_base_branch()
        released = self.git("show", "base:.ai/CHANGELOG.md")
        both = re.sub(r"^(## 99\.0\.0 — )",
                      "## 100.0.0 — 2099-01-02\n\n- the release 100.0.0\n\n---\n\n\\1",
                      released, count=1, flags=re.M)
        self.merge_the_base_branch(both)
        self.assert_fails_with(".ai/UX.md: text changed since 99.0.0")

    def test_a_base_branch_behind_the_release_merge_is_not_trusted(self) -> None:
        # The release was merged locally and `origin/HEAD` has not seen it yet:
        # the merge is not on the remote line, yet it is the release.
        self.test_a_change_that_landed_before_a_release_merged_belongs_to_that_release()
        self.git("update-ref", "refs/remotes/origin/base", "base~1")
        _, out = run_checker(self.copy)
        self.assertIn("[SKIP] document versions", out)
        self.assertIn("has not reached yet", out)

    def test_an_ordinary_release_merge_needs_no_base_branch(self) -> None:
        # The merge holds exactly what the release branch did, so both
        # readings agree and nothing has to be told apart.
        self.as_the_sets_home()
        self.git("init", "-q", "-b", "base")
        self.commit("the release before")
        self.git("checkout", "-q", "-b", "release")
        self.change()
        self.bump()
        self.open_a_release("99.0.0", "01")
        self.commit("release 99.0.0")
        self.git("checkout", "-q", "base")
        self.git("merge", "-q", "--no-ff", "--no-edit", "release")
        self.git("checkout", "-q", "-b", "next")
        self.change(".ai/EXECUTION.md")
        self.bump(".ai/EXECUTION.md")
        self.open_a_release("100.0.0", "02")
        self.commit("release 100.0.0")
        self.assert_versions_pass()

    def test_a_change_after_a_merged_in_release_still_counts_toward_the_next(self) -> None:
        # The base branch took an entry-less change after its release; a branch
        # with its own entry on top then merged it in. That change belongs to
        # the next release, so the release is where it first stood, not the tip.
        self.branch_off_the_previous_release()
        self.open_a_release("100.0.0", "02")
        self.commit("work with its entry")
        self.release_on_the_base_branch()
        self.git("checkout", "-q", "base")
        self.change(".ai/REVIEW.md")
        self.commit("an entry-less change after the release, unbumped")
        self.git("checkout", "-q", "work")
        released = self.git("show", "base:.ai/CHANGELOG.md")
        both = re.sub(r"^(## 99\.0\.0 — )",
                      "## 100.0.0 — 2099-01-02\n\n- the release 100.0.0\n\n---\n\n\\1",
                      released, count=1, flags=re.M)
        self.merge_the_base_branch(both)
        self.assert_fails_with(".ai/REVIEW.md: text changed since 99.0.0")

    def test_a_release_on_both_sides_of_a_merge_is_not_guessed(self) -> None:
        self.branch_off_the_previous_release()
        self.change()
        self.open_a_release("99.0.0", "01")
        self.commit("work that numbered itself 99.0.0")
        self.release_on_the_base_branch()
        released = self.git("show", "base:.ai/CHANGELOG.md")
        renumbered = re.sub(r"^(## 99\.0\.0 — )",
                            "## 100.0.0 — 2099-01-02\n\n- the release 100.0.0\n\n---\n\n\\1",
                            released, count=1, flags=re.M)
        self.merge_the_base_branch(renumbered)
        _, out = run_checker(self.copy)
        self.assertIn("[SKIP] document versions", out)
        self.assertIn("more than one side of merge", out)

    def test_a_front_matter_edit_alone_is_not_a_change(self) -> None:
        self.release_then_open_the_next()
        self.edit(".ai/UX.md", lambda t: re.sub(r"^updated: .*$", "updated: 2099-01-01", t, count=1, flags=re.M))
        self.assert_versions_pass()

    def test_a_change_without_a_bump_fails(self) -> None:
        self.release_then_open_the_next()
        self.change()
        self.assert_fails_with(".ai/UX.md: text changed since")

    def test_a_committed_change_without_a_bump_fails(self) -> None:
        self.release_then_open_the_next()
        self.change()
        self.commit("the release under test")
        self.assert_fails_with(".ai/UX.md: text changed since")

    def test_one_bump_covers_every_commit_of_a_release(self) -> None:
        # Changed and bumped before the entry was written, changed again after
        # it was committed: one release, one bump. The work before the entry
        # also touches the changelog, so the previous release is the older of
        # two commits with it on top, and the check must take the older.
        self.as_the_sets_home()
        self.git("init", "-q")
        self.commit("the previous release")
        self.change()
        self.bump()
        self.correct_an_old_entry()
        self.commit("work before the entry")
        self.open_a_release()
        self.commit("the entry")
        self.edit(".ai/UX.md", lambda t: t + "\nA second sentence, after the entry.\n")
        self.commit("work after the entry")
        self.assert_versions_pass()

    def test_a_second_bump_in_one_release_fails(self) -> None:
        self.release_then_open_the_next()
        self.change()
        self.bump()
        self.bump()
        self.assert_fails_with("is more than one bump")

    def test_a_version_that_went_backwards_fails(self) -> None:
        self.release_then_open_the_next()
        self.change()
        self.edit(".ai/UX.md", lambda t: re.sub(r"^version: .*$", "version: 0.0.1", t, count=1, flags=re.M))
        self.assert_fails_with("version went backwards")

    def test_a_release_entry_alone_does_not_bump_the_changelog(self) -> None:
        # Its version describes its rules. A new entry, and a correction to an
        # old one, change its record.
        self.release_then_open_the_next()
        self.edit(".ai/CHANGELOG.md", lambda t: t.replace("- the release under test", "- the release under test, corrected"))
        self.correct_an_old_entry()
        self.assert_versions_pass()

    def test_a_changelog_rule_change_without_a_bump_fails(self) -> None:
        self.release_then_open_the_next()
        self.edit(".ai/CHANGELOG.md", lambda t: t.replace("## Set version\n", "## Set version\n\nA rule added.\n", 1))
        self.assert_fails_with(".ai/CHANGELOG.md: text changed since")

    def test_an_instance_file_is_not_judged(self) -> None:
        roadmap = self.copy / ".ai" / "ROADMAP.md"
        roadmap.write_text("---\ndoc_id: ai-roadmap\nversion: 1.0.0\ncanonical_path: .ai/ROADMAP.md\n"
                           "updated: 2026-10-09\n---\n\n# Roadmap\n", encoding="utf-8")
        self.release_then_open_the_next()
        self.change(".ai/ROADMAP.md")
        self.assert_versions_pass()

    def test_without_history_nothing_is_compared_and_nothing_passes(self) -> None:
        self.as_the_sets_home()
        _, out = run_checker(self.copy)
        self.assertIn("[SKIP] document versions", out)
        self.assertIn("not a git repository of its own", out)
        self.assertNotIn("[PASS] document versions", out)

    def test_a_shallow_clone_says_it_cannot_see_the_release(self) -> None:
        self.release_then_open_the_next()
        self.commit("the release under test")
        clone = self.tmp / "shallow"
        subprocess.run(["git", "clone", "-q", "--depth", "1", self.copy.as_uri(), str(clone)],
                       capture_output=True, check=True)
        code, out = run_checker(clone)
        self.assertIn("[SKIP] document versions", out)
        self.assertIn("shallow clone", out)

    def test_an_adopter_is_not_asked_about_the_sets_history(self) -> None:
        self.release_then_open_the_next()
        self.change()
        (self.copy / "LESSONS_FROM_PRACTICE.md").unlink(missing_ok=True)
        code, out = run_checker(self.copy)
        self.assertIn("[SKIP] document versions", out)
        self.assertIn("asked only where the set lives", out)
        self.assertNotIn(".ai/UX.md: text changed since", out)

    # -- check 9: subscribed copy ------------------------------------------
    SUBSCRIBED = (".ai/CORE.md", ".ai/REVIEW.md", "CLAUDE.md", ".claude/agents/fast-explorer.md")

    def subscribe(self, names=SUBSCRIBED, header="source: owner/set\nversion: 9.9.9\ncommit: abc\n") -> Path:
        """Make the copy an adopter whose lock records `names` as delivered."""
        (self.copy / "LESSONS_FROM_PRACTICE.md").unlink(missing_ok=True)
        self.write_context(self.FILLED_CONTEXT)
        lines = [f"{delivered_digest(self.copy / n)}  {n}" for n in names]
        lock = self.copy / ".ai" / "set.lock"
        lock.write_text("# delivered\n" + header + "\n" + "\n".join(lines) + "\n", encoding="utf-8")
        return lock

    def test_an_untouched_subscription_passes(self) -> None:
        self.subscribe()
        code, out = run_checker(self.copy)
        self.assertEqual(code, 0, out)
        self.assertIn("[PASS] subscribed copy", out)
        self.assertIn("do the 4 files .ai/set.lock names, delivered as set 9.9.9", out)

    def test_a_subscribed_document_edited_here_fails(self) -> None:
        self.subscribe()
        self.edit(".ai/REVIEW.md", lambda t: t + "\nA rule only this repository has.\n")
        self.assert_fails_with(".ai/REVIEW.md: edited here")

    def test_a_subscribed_entry_file_edited_here_fails(self) -> None:
        self.subscribe()
        self.edit("CLAUDE.md", lambda t: t.replace("Primary Engineering Manager", "Lead", 1))
        self.assert_fails_with("CLAUDE.md: edited here")

    def test_a_subscribed_document_removed_here_fails(self) -> None:
        self.subscribe()
        (self.copy / ".ai" / "REVIEW.md").unlink()
        self.assert_fails_with(".ai/REVIEW.md: removed here")

    def test_a_removed_capability_is_the_repositorys_choice(self) -> None:
        self.subscribe()
        (self.copy / ".claude" / "agents" / "fast-explorer.md").unlink()
        code, out = run_checker(self.copy)
        self.assertIn("[PASS] subscribed copy", out)
        self.assertIn("1 removed capabilities excused", out)

    def test_a_windows_checkout_is_not_an_edit(self) -> None:
        self.subscribe()
        path = self.copy / ".ai" / "REVIEW.md"
        path.write_bytes(path.read_bytes().replace(b"\n", b"\r\n"))
        code, out = run_checker(self.copy)
        self.assertIn("[PASS] subscribed copy", out)

    def test_a_lock_without_its_header_fails(self) -> None:
        self.subscribe(header="source: owner/set\nversion: 9.9.9\n")
        self.assert_fails_with("no `commit:` line")

    def test_a_lock_line_that_is_not_an_entry_fails(self) -> None:
        lock = self.subscribe()
        lock.write_text(lock.read_text(encoding="utf-8") + "deadbeef .ai/UX.md\n", encoding="utf-8")
        self.assert_fails_with("is neither a header field")

    def test_a_path_listed_twice_fails(self) -> None:
        lock = self.subscribe()
        lock.write_text(lock.read_text(encoding="utf-8") + "0" * 64 + "  .ai/CORE.md\n", encoding="utf-8")
        self.assert_fails_with("lists `.ai/CORE.md` a second time")

    def test_a_recorded_removal_is_excused(self) -> None:
        lock = self.subscribe()
        (self.copy / "AGENTS.md").unlink(missing_ok=True)
        lock.write_text(lock.read_text(encoding="utf-8") + "removed: AGENTS.md\n", encoding="utf-8")
        code, out = run_checker(self.copy)
        self.assertIn("[PASS] subscribed copy", out)
        self.assertIn("1 removed capabilities excused", out)

    def test_a_removal_outside_the_tree_fails(self) -> None:
        lock = self.subscribe()
        lock.write_text(lock.read_text(encoding="utf-8") + "removed: ../elsewhere.md\n", encoding="utf-8")
        self.assert_fails_with("records `../elsewhere.md` as removed, which the set never delivers")

    def test_a_policy_document_cannot_be_recorded_as_removed(self) -> None:
        lock = self.subscribe()
        lock.write_text(lock.read_text(encoding="utf-8") + "removed: .ai/UX.md\n", encoding="utf-8")
        self.assert_fails_with("records `.ai/UX.md` as removed, but only a capability may be")

    def test_a_lock_naming_an_instance_file_fails(self) -> None:
        self.subscribe(names=(".ai/CORE.md", ".ai/PROJECT_CONTEXT.md"))
        self.assert_fails_with("names `.ai/PROJECT_CONTEXT.md`, which the set never delivers")

    def test_a_lock_naming_a_path_outside_the_tree_fails(self) -> None:
        lock = self.subscribe()
        lock.write_text(lock.read_text(encoding="utf-8") + "0" * 64 + "  ../elsewhere.md\n", encoding="utf-8")
        self.assert_fails_with("names `../elsewhere.md`")

    # -- check 2 in a subscriber: references into capability folders -------
    def test_in_a_subscriber_a_pointer_to_no_capability_fails(self) -> None:
        self.subscribe()
        self.edit("AGENTS.md", lambda t: t + "\nRead `.codex/agents/missing.toml`.\n")
        self.assert_fails_with("references `.codex/agents/missing.toml`, which does not exist")

    def test_in_a_subscriber_a_removed_capability_is_excused(self) -> None:
        # Delivered, as the lock records, then taken out: the set's own
        # documents still point at it, and that is the repository's choice.
        self.subscribe()
        (self.copy / ".claude" / "agents" / "fast-explorer.md").unlink()
        code, out = run_checker(self.copy)
        self.assertEqual(code, 0, out)
        self.assertIn("[PASS] cross-references", out)

    def excused_by_mark(self, mark: str, name: str) -> None:
        lock = self.subscribe()
        lock.write_text(lock.read_text(encoding="utf-8") + f"{mark}: {name}\n", encoding="utf-8")
        (self.copy / name).unlink()
        code, out = run_checker(self.copy)
        self.assertEqual(code, 0, out)

    def test_in_a_subscriber_a_recorded_removal_is_excused(self) -> None:
        self.excused_by_mark("removed", ".claude/agents/adversarial-reviewer.md")

    def test_in_a_subscriber_a_capability_kept_as_its_own_is_excused(self) -> None:
        # The repository had its own skill there, so the set withheld this file.
        self.excused_by_mark("kept", ".agents/skills/auto-dev/agents/openai.yaml")

    def test_in_a_subscriber_an_unrecorded_missing_capability_fails(self) -> None:
        # Never delivered and never recorded: the set points at nothing.
        self.subscribe()
        (self.copy / ".claude" / "agents" / "adversarial-reviewer.md").unlink()
        self.assert_fails_with("references `.claude/agents/adversarial-reviewer.md`, which does not exist")

    def test_without_a_lock_the_question_is_not_asked(self) -> None:
        self.subscribe()
        (self.copy / ".ai" / "set.lock").unlink()
        code, out = run_checker(self.copy)
        self.assertIn("[SKIP] subscribed copy", out)
        self.assertIn("before 4.0.0 made adoption a subscription", out)

    def test_the_sets_home_subscribes_to_nothing(self) -> None:
        if not AT_SET_HOME:
            self.skipTest("an adopter's copy is not the set's home")
        code, out = run_checker(self.copy)
        self.assertIn("[SKIP] subscribed copy", out)
        self.assertIn("this is the set itself", out)

    # -- adopting repository -----------------------------------------------
    def test_adopting_repository_without_set_home_files_passes(self) -> None:
        # Adoption copies the policy and capabilities, not the set-home files.
        # The adopter's README names its product and is not the set's.
        term = first_denylisted_term(self.copy)
        (self.copy / "LESSONS_FROM_PRACTICE.md").unlink(missing_ok=True)
        (self.copy / "README.md").write_text(f"# {term}\n\n{term} is our product.\n", encoding="utf-8")
        self.write_context(self.FILLED_CONTEXT)
        code, out = run_checker(self.copy)
        self.assertEqual(code, 0, f"an adopted copy must pass without the set-home files:\n{out}")


if __name__ == "__main__":
    unittest.main(verbosity=2)
