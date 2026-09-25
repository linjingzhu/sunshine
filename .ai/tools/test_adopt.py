#!/usr/bin/env python3
"""Prove adoption produces a repository that starts green, or says why not.

The acceptance test is the first one: a fully specified adoption passes every
check in the adopted tree. Everything else here is a way that has already gone
wrong or could — a template instruction surviving into the instance, an
adopter's own file being overwritten, a half-filled context that looks finished.

Standard library only:

    python3 .ai/tools/test_adopt.py
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ADOPT = Path(__file__).resolve().parent / "adopt.py"

FACTS = {
    "repository_mode": "personal",
    "base_branch": "main",
    "merge_deploys": "no",
    "runtime_gate": "none",
    "test_command": "npm test",
    "lint_command": "npm run lint",
    "build_command": "npm run build",
    "generated": "none",
    "external_scripts": "none",
    "public_ids": "none",
    "owner_ledger": "docs/OWNER_ACTIONS.md",
}


def run_checker_in(root: Path) -> tuple[int, str]:
    result = subprocess.run(
        [sys.executable, str(root / ".ai" / "tools" / "check_policy_set.py"), str(root)],
        capture_output=True, text=True, check=False,
    )
    return result.returncode, result.stdout + result.stderr


def adopt(target: Path, facts: dict[str, str] | None = None, *extra: str) -> tuple[int, str]:
    argv = [sys.executable, str(ADOPT), "--into", str(target), *extra]
    for key, value in (facts or {}).items():
        argv += ["--set", f"{key}={value}"]
    result = subprocess.run(argv, capture_output=True, text=True, check=False)
    return result.returncode, result.stdout + result.stderr


class AdoptTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="adopt-"))
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.target = self.tmp / "project"

    def context(self) -> str:
        return (self.target / ".ai" / "PROJECT_CONTEXT.md").read_text(encoding="utf-8")

    # -- the acceptance test ----------------------------------------------
    def test_fully_specified_adoption_starts_green(self) -> None:
        code, out = adopt(self.target, FACTS, "--name", "Acme")
        self.assertEqual(code, 0, f"an adopted repository must pass its own checks:\n{out}")
        self.assertIn("All structural checks passed.", out)

    # -- what travels, and what must not ----------------------------------
    def test_what_travels(self) -> None:
        adopt(self.target, FACTS)
        for name in ("CLAUDE.md", "AGENTS.md", ".ai/CORE.md", ".ai/tools/adopt.py"):
            self.assertTrue((self.target / name).exists(), f"{name} should travel")

    def test_set_home_files_do_not_travel(self) -> None:
        # `README.md` would overwrite the adopter's own front page.
        # `LESSONS_FROM_PRACTICE.md` is how check_policy_set.py tells the set's
        # home from an adopting repository: copying it would make the adopted
        # tree claim to be the set, and the checks would then read the
        # adopter's README as this one's. That is the 2.2.1 defect.
        adopt(self.target, FACTS)
        self.assertFalse((self.target / "README.md").exists())
        self.assertFalse((self.target / "LESSONS_FROM_PRACTICE.md").exists())

    def test_adopted_tree_does_not_read_the_adopters_readme(self) -> None:
        # The end-to-end version of the rule above: an adopter whose own README
        # names their product must still pass.
        adopt(self.target, FACTS)
        (self.target / "README.md").write_text(
            "# Sunshine\n\nOur product.\n", encoding="utf-8"
        )
        code, out = run_checker_in(self.target)
        self.assertEqual(code, 0, f"the adopter's own README is not the set's:\n{out}")

    def test_agent_definitions_travel(self) -> None:
        # HARNESS.md calls these project capabilities: they change what any run
        # on the repository can do, so they are committed, not machine-local.
        adopt(self.target, FACTS)
        for name in ("fast-explorer", "adversarial-reviewer"):
            self.assertTrue(
                (self.target / ".claude" / "agents" / f"{name}.md").exists(),
                f"{name} should travel",
            )
            self.assertTrue(
                (self.target / ".codex" / "agents" / f"{name}.toml").exists(),
                f"Codex {name} should travel",
            )

    def test_existing_codex_entry_and_agent_are_kept_even_with_force(self) -> None:
        agent = self.target / ".codex" / "agents" / "fast-explorer.toml"
        agent.parent.mkdir(parents=True)
        entry = self.target / "AGENTS.md"
        entry_text = "# Local instructions\n\nUse this repository's conventions.\n"
        agent_text = (
            'name = "fast-explorer"\ndescription = "Local explorer"\n'
            'developer_instructions = "Report local facts."\n'
        )
        entry.write_text(entry_text, encoding="utf-8")
        agent.write_text(agent_text, encoding="utf-8")
        code, out = adopt(self.target, FACTS, "--force")
        self.assertEqual(code, 0, out)
        self.assertEqual(entry.read_text(encoding="utf-8"), entry_text)
        self.assertEqual(agent.read_text(encoding="utf-8"), agent_text)
        self.assertIn("[keep] AGENTS.md", out)
        self.assertIn("[keep] .codex/agents/fast-explorer.toml", out)
        self.assertTrue((agent.parent / "adversarial-reviewer.toml").is_file())

    def test_adoption_does_not_replace_codex_configuration(self) -> None:
        config = self.target / ".codex" / "config.toml"
        config.parent.mkdir(parents=True)
        theirs = 'model = "my-configured-model"\n'
        config.write_text(theirs, encoding="utf-8")
        adopt(self.target, FACTS, "--force")
        self.assertEqual(config.read_text(encoding="utf-8"), theirs)

    def test_an_adopters_own_agent_is_never_overwritten(self) -> None:
        agents = self.target / ".claude" / "agents"
        agents.mkdir(parents=True)
        mine = agents / "fast-explorer.md"
        mine.write_text("---\nname: fast-explorer\ndescription: mine\n---\n", encoding="utf-8")
        _, out = adopt(self.target, FACTS)
        self.assertEqual(mine.read_text(encoding="utf-8"), "---\nname: fast-explorer\ndescription: mine\n---\n")
        self.assertIn("is yours", out)
        # The one they do not have is still written.
        self.assertTrue((agents / "adversarial-reviewer.md").exists())

    def test_the_skill_travels(self) -> None:
        # A procedure repeated across runs belongs in a committed skill
        # (`.ai/HARNESS.md` § Where harness configuration belongs), which means
        # an adopting repository gets it or the procedure is not repeatable.
        adopt(self.target, FACTS)
        skill = self.target / ".claude" / "skills" / "auto-dev" / "SKILL.md"
        self.assertTrue(skill.exists(), "the auto-dev skill should travel")
        self.assertIn("name: auto-dev", skill.read_text(encoding="utf-8"))
        codex_skill = self.target / ".agents" / "skills" / "auto-dev"
        self.assertTrue((codex_skill / "SKILL.md").is_file())
        self.assertTrue((codex_skill / "agents" / "openai.yaml").is_file())

    def test_an_adopters_own_skill_is_never_overwritten(self) -> None:
        skill = self.target / ".claude" / "skills" / "auto-dev" / "SKILL.md"
        skill.parent.mkdir(parents=True)
        theirs = "---\nname: auto-dev\ndescription: theirs\n---\n"
        skill.write_text(theirs, encoding="utf-8")
        _, out = adopt(self.target, FACTS)
        self.assertEqual(skill.read_text(encoding="utf-8"), theirs)
        self.assertIn("is yours", out)

    def test_existing_codex_skill_does_not_receive_packaged_metadata(self) -> None:
        skill = self.target / ".agents" / "skills" / "auto-dev" / "SKILL.md"
        skill.parent.mkdir(parents=True)
        theirs = "---\nname: auto-dev\ndescription: My explicit procedure\n---\n"
        skill.write_text(theirs, encoding="utf-8")
        code, out = adopt(self.target, FACTS, "--force")
        self.assertEqual(code, 0, out)
        self.assertEqual(skill.read_text(encoding="utf-8"), theirs)
        self.assertFalse((skill.parent / "agents" / "openai.yaml").exists())
        self.assertIn("[keep] .agents/skills/auto-dev/", out)

    def test_an_adopted_tree_passes_with_the_capabilities_it_received(self) -> None:
        # The end-to-end question: adoption copies agents and a skill, and the
        # checks in the new tree read them. A capability that travels but does
        # not pass there is one the adopter has to fix before starting.
        adopt(self.target, FACTS)
        code, out = run_checker_in(self.target)
        self.assertEqual(code, 0, out)
        self.assertIn("capability definitions", out)

    def test_adoption_does_not_create_workflows(self) -> None:
        code, out = adopt(self.target, FACTS)
        self.assertEqual(code, 0, out)
        self.assertFalse((self.target / ".github/workflows").exists())

    def test_existing_adopter_workflows_are_kept_even_with_force(self) -> None:
        workflows = self.target / ".github" / "workflows"
        workflows.mkdir(parents=True)
        existing = {
            "policy-set.yml": b"name: Local policy checks\r\non: push\r\n",
            "build.yaml": b"name: Local build\non: push\n",
        }
        for name, content in existing.items():
            (workflows / name).write_bytes(content)
        for extra in ((), ("--force",)):
            with self.subTest(extra=extra):
                code, out = adopt(self.target, FACTS, *extra)
                self.assertEqual(code, 0, out)
                self.assertEqual(
                    {path.name: path.read_bytes() for path in workflows.iterdir()},
                    existing,
                )

    # -- the instance files ------------------------------------------------
    def test_template_instructions_do_not_survive(self) -> None:
        adopt(self.target, FACTS)
        text = self.context()
        self.assertNotIn("This is a template", text)
        self.assertNotIn("delete every instruction line", text)
        self.assertNotIn("\n>", text, "instruction blockquotes should be gone")

    def test_facts_are_written_and_fences_survive(self) -> None:
        adopt(self.target, FACTS)
        text = self.context()
        for key, value in FACTS.items():
            self.assertIn(f"{key}: {value}", text)
        self.assertIn("```text", text, "the fenced block the checks read must remain")

    def test_name_sets_the_title(self) -> None:
        adopt(self.target, FACTS, "--name", "Acme Web")
        self.assertIn("# Acme Web Context", self.context())

    def test_project_lessons_instance_is_created_empty(self) -> None:
        adopt(self.target, FACTS)
        lessons = (self.target / ".ai" / "memory" / "PROJECT_LESSONS.md").read_text(encoding="utf-8")
        self.assertIn("None recorded yet", lessons)
        self.assertNotIn("This is a template", lessons)

    # -- a half-finished adoption must fail loudly -------------------------
    def test_missing_facts_fail_and_are_named(self) -> None:
        code, out = adopt(self.target, {"base_branch": "main"})
        self.assertEqual(code, 1, "an unfinished context must not report success")
        self.assertIn("Facts still unanswered", out)
        for key in ("repository_mode", "test_command", "owner_ledger"):
            self.assertIn(f"- {key}", out)
        self.assertNotIn("- base_branch", out, "a supplied fact is not unanswered")

    def test_enum_menu_left_in_place_counts_as_unanswered(self) -> None:
        # `merge_deploys: yes | no` is the template's menu, not a choice.
        code, out = adopt(self.target, {k: v for k, v in FACTS.items() if k != "merge_deploys"})
        self.assertEqual(code, 1)
        self.assertIn("- merge_deploys", out)

    # -- do not destroy an adopter's work ----------------------------------
    def test_existing_instance_is_kept_without_force(self) -> None:
        adopt(self.target, FACTS)
        marker = "# Hand written by the adopter\n"
        (self.target / ".ai" / "PROJECT_CONTEXT.md").write_text(marker, encoding="utf-8")
        code, out = adopt(self.target, FACTS)
        self.assertIn("[keep] .ai/PROJECT_CONTEXT.md already exists", out)
        self.assertEqual(self.context(), marker, "an existing instance must not be overwritten")
        self.assertEqual(code, 1, "and the checks must then fail on it, not pass quietly")

    def test_force_overwrites(self) -> None:
        adopt(self.target, FACTS)
        (self.target / ".ai" / "PROJECT_CONTEXT.md").write_text("# gone\n", encoding="utf-8")
        code, _ = adopt(self.target, FACTS, "--force")
        self.assertEqual(code, 0)
        self.assertIn("base_branch: main", self.context())

    # -- --from-template: GitHub's "Use this template" ---------------------
    def template_tree(self) -> Path:
        """A copy of every tracked file, which is what "Use this template" makes."""
        tree = self.tmp / "from-template"
        shutil.copytree(ROOT, tree, ignore=shutil.ignore_patterns(".git", "__pycache__"))
        return tree

    def from_template(self, tree: Path, *extra: str, facts: dict[str, str] | None = FACTS) -> tuple[int, str]:
        argv = [sys.executable, str(tree / ".ai" / "tools" / "adopt.py"), "--from-template", *extra]
        for key, value in (facts or {}).items():
            argv += ["--set", f"{key}={value}"]
        result = subprocess.run(argv, capture_output=True, text=True, check=False)
        return result.returncode, result.stdout + result.stderr

    def test_template_tree_fails_before_the_mode_runs(self) -> None:
        # The defect this mode exists for: the copied LESSONS_FROM_PRACTICE.md
        # makes the tree claim to be the set, so the checks read the
        # repository's own README as the set's and a pointer cannot resolve.
        tree = self.template_tree()
        (tree / "README.md").write_text("# Acme Web\n\nOur product.\n", encoding="utf-8")
        code, out = run_checker_in(tree)
        self.assertEqual(code, 1, f"expected the known failure, got:\n{out}")
        self.assertIn("README.md", out)

    def test_from_template_makes_it_pass(self) -> None:
        tree = self.template_tree()
        (tree / "README.md").write_text("# Acme Web\n\nOur product.\n", encoding="utf-8")
        code, out = self.from_template(tree, "--name", "Acme Web")
        self.assertEqual(code, 0, f"the finished tree must pass its own checks:\n{out}")
        self.assertIn("All structural checks passed.", out)

    def test_from_template_removes_only_the_marker(self) -> None:
        tree = self.template_tree()
        self.from_template(tree, "--name", "Acme Web")
        self.assertFalse((tree / "LESSONS_FROM_PRACTICE.md").exists())
        # The adopter's front page is reported, never deleted.
        self.assertTrue((tree / "README.md").exists())

    def test_from_template_warns_that_the_readme_is_still_the_sets(self) -> None:
        tree = self.template_tree()
        _, out = self.from_template(tree, "--name", "Acme Web")
        self.assertIn("README.md is still this set's front page", out)

    def test_from_template_reseeds_the_denylist(self) -> None:
        tree = self.template_tree()
        self.from_template(tree, "--name", "Acme Web")
        denylist = (tree / ".ai" / "tools" / "portability-denylist.txt").read_text(encoding="utf-8")
        self.assertIn("Acme Web", denylist)
        for seeded in ("Sunshine", "Marvelous", "Webium"):
            self.assertNotIn(seeded, denylist, "another project's names prove nothing here")

    def test_from_template_without_a_name_warns_instead_of_silently_keeping_seeds(self) -> None:
        tree = self.template_tree()
        _, out = self.from_template(tree, facts=FACTS)
        self.assertIn("still holds the set's names", out)

    def test_from_template_refuses_a_tree_that_is_not_one(self) -> None:
        # An ordinary adopted repository has no marker to remove; saying so beats
        # deleting something else that looks close enough.
        adopt(self.target, FACTS)
        code, out = self.from_template(self.target, "--name", "Acme")
        self.assertNotEqual(code, 0)
        self.assertIn("is not here", out)

    def test_from_template_rejects_into(self) -> None:
        tree = self.template_tree()
        code, out = self.from_template(tree, "--into", str(self.tmp / "elsewhere"))
        self.assertNotEqual(code, 0)
        self.assertIn("works in place", out)

    # -- argument handling -------------------------------------------------
    def test_removed_with_ci_is_rejected_before_creating_target(self) -> None:
        code, out = adopt(self.target, FACTS, "--with-ci")
        self.assertEqual(code, 2, out)
        self.assertIn("unrecognized arguments: --with-ci", out)
        self.assertFalse(self.target.exists())

    def test_malformed_set_is_rejected(self) -> None:
        result = subprocess.run(
            [sys.executable, str(ADOPT), "--into", str(self.target), "--set", "no_equals_sign"],
            capture_output=True, text=True, check=False,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("--set expects key=value", result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main(verbosity=2)
