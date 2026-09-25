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


def run_checker(root: Path) -> tuple[int, str]:
    result = subprocess.run(
        [sys.executable, str(CHECKER), str(root)],
        capture_output=True,
        text=True,
        check=False,
    )
    return result.returncode, result.stdout + result.stderr


class GuardTests(unittest.TestCase):
    def setUp(self) -> None:
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
        (self.copy / "LESSONS_FROM_PRACTICE.md").unlink()
        code, out = run_checker(self.copy)
        self.assertEqual(code, 0, out)
        self.assertIn("nothing to check", out)

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
