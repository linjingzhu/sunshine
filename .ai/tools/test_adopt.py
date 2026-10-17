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

import re
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


def upgrade(target: Path, *extra: str) -> tuple[int, str]:
    result = subprocess.run(
        [sys.executable, str(ADOPT), "--upgrade", "--into", str(target), *extra],
        capture_output=True, text=True, check=False,
    )
    return result.returncode, result.stdout + result.stderr


def adopt(target: Path, facts: dict[str, str] | None = None, *extra: str) -> tuple[int, str]:
    argv = [sys.executable, str(ADOPT), "--into", str(target), *extra]
    for key, value in (facts or {}).items():
        argv += ["--set", f"{key}={value}"]
    result = subprocess.run(argv, capture_output=True, text=True, check=False)
    return result.returncode, result.stdout + result.stderr


TEMPLATE_ONLY = (
    '"Use this template" copies the set\'s own repository, '
    "and a copy of an adopting repository is not that tree"
)
# Tests skipped in a repository that adopted the set, each with its reason.
# They run unconditionally at the set's home. Every other test must pass in an
# adopter too, and a test is listed only because its subject exists only at
# the set's home — never to make a suite green. The guard suite's list says the
# same, and may also name a known blind spot with the roadmap item tracking it.
# This list is the one place a reviewer has to read.
NEEDS_THE_SETS_HOME = {
    "test_template_tree_fails_before_the_mode_runs": TEMPLATE_ONLY,
    "test_from_template_makes_it_pass": TEMPLATE_ONLY,
    "test_from_template_reseeds_the_denylist": TEMPLATE_ONLY,
    "test_from_template_warns_that_the_readme_is_still_the_sets": TEMPLATE_ONLY,
    "test_from_template_without_a_name_warns_instead_of_silently_keeping_seeds": TEMPLATE_ONLY,
    "test_from_template_removes_only_the_marker": TEMPLATE_ONLY,
    "test_an_unfinished_template_copy_is_named": TEMPLATE_ONLY,
}
AT_SET_HOME = (ROOT / "LESSONS_FROM_PRACTICE.md").exists()


class AdoptTests(unittest.TestCase):
    def setUp(self) -> None:
        reason = NEEDS_THE_SETS_HOME.get(self._testMethodName)
        if reason and not AT_SET_HOME:
            self.skipTest(f"needs the set's home: {reason}")
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
        # The set's documents point at the file it withheld; the lock says the
        # repository keeps its own skill there, which excuses that pointer.
        self.assertIn("kept: .agents/skills/auto-dev/agents/openai.yaml",
                      (self.target / ".ai" / "set.lock").read_text(encoding="utf-8"))

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

    # -- upgrading a repository that already adopted the set ---------------
    def test_re_running_adoption_destroys_the_adopters_denylist(self) -> None:
        """The defect --upgrade exists for, asserted before the fix is used.

        Plain adoption copies `.ai/` wholesale, and the set ships its own
        denylist. Re-running it over a lived-in tree replaces that repository's
        product names with the set's seeds, and its portability check goes on
        passing while proving nothing.
        """
        adopt(self.target, FACTS)
        denylist = self.target / ".ai" / "tools" / "portability-denylist.txt"
        denylist.write_text("Widget\nWidgetCorp\n", encoding="utf-8")
        adopt(self.target, FACTS)
        self.assertNotIn("Widget", denylist.read_text(encoding="utf-8"))

    def test_upgrade_keeps_what_the_repository_owns(self) -> None:
        adopt(self.target, FACTS)
        denylist = self.target / ".ai" / "tools" / "portability-denylist.txt"
        lessons = self.target / ".ai" / "memory" / "PROJECT_LESSONS.md"
        roadmap = self.target / ".ai" / "ROADMAP.md"
        denylist.write_text("Widget\nWidgetCorp\n", encoding="utf-8")
        roadmap.write_text("# Roadmap\n\n## Widget importer\n", encoding="utf-8")
        lessons.write_text(lessons.read_text(encoding="utf-8") + "\n## Widget parser\n", encoding="utf-8")
        context = self.context()

        code, out = upgrade(self.target)
        self.assertEqual(code, 0, out)
        self.assertEqual(denylist.read_text(encoding="utf-8"), "Widget\nWidgetCorp\n")
        self.assertIn("Widget importer", roadmap.read_text(encoding="utf-8"))
        self.assertIn("Widget parser", lessons.read_text(encoding="utf-8"))
        self.assertEqual(self.context(), context)

    def test_upgrade_updates_the_policy_documents(self) -> None:
        # The other half: keeping the repository's files is only useful if the
        # set's own documents actually move.
        adopt(self.target, FACTS)
        core = self.target / ".ai" / "CORE.md"
        core.write_text("---\ndoc_id: ai-core\nversion: 0.0.1\n"
                        "canonical_path: .ai/CORE.md\nupdated: 2020-01-01\n---\n\n# Stale\n",
                        encoding="utf-8")
        upgrade(self.target)
        self.assertEqual(
            core.read_text(encoding="utf-8"),
            (ROOT / ".ai" / "CORE.md").read_text(encoding="utf-8"),
        )

    def test_upgrade_reports_the_version_it_moved(self) -> None:
        adopt(self.target, FACTS)
        _, out = upgrade(self.target)
        self.assertIn("[upgrade]", out)

    def test_upgrade_leaves_a_diverged_capability_alone_and_says_so(self) -> None:
        # The repository's own agent, there before adoption: never the set's.
        agent = self.target / ".claude" / "agents" / "fast-explorer.md"
        mine = "---\nname: fast-explorer\ndescription: mine\n---\n\nMine.\n"
        agent.parent.mkdir(parents=True)
        agent.write_text(mine, encoding="utf-8")
        adopt(self.target, FACTS)
        _, out = upgrade(self.target)
        self.assertEqual(agent.read_text(encoding="utf-8"), mine)
        self.assertIn("[stale]", out)

    def test_refresh_capabilities_replaces_a_diverged_one(self) -> None:
        adopt(self.target, FACTS)
        agent = self.target / ".claude" / "agents" / "fast-explorer.md"
        agent.write_text("---\nname: fast-explorer\ndescription: mine\n---\n", encoding="utf-8")
        upgrade(self.target, "--refresh-capabilities")
        self.assertEqual(
            agent.read_text(encoding="utf-8"),
            (ROOT / ".claude" / "agents" / "fast-explorer.md").read_text(encoding="utf-8"),
        )

    def test_upgrade_refuses_a_tree_that_never_adopted(self) -> None:
        code, out = upgrade(self.target)
        self.assertNotEqual(code, 0)
        self.assertIn("has not adopted the set", out)

    def test_upgrade_refuses_the_sets_own_home(self) -> None:
        code, out = upgrade(ROOT)
        self.assertNotEqual(code, 0)
        self.assertIn("not the set itself", out)

    # -- instance files never travel ---------------------------------------
    # A run at the set's home can write a roadmap or a report there. Those are
    # the set's own records; copying `.ai/` must not hand them to every
    # repository adopted or upgraded afterwards as if they were its own.
    def source_with_instances(self) -> Path:
        source = self.tmp / "set"
        shutil.copytree(ROOT, source, ignore=shutil.ignore_patterns(".git", "__pycache__"))
        ai = source / ".ai"
        (ai / "ROADMAP.md").write_text("# Roadmap\n\n## THE SET'S OWN ITEM\n", encoding="utf-8")
        (ai / "reports" / "2026-10-09-the-sets-run.md").write_text("# THE SET'S OWN REPORT\n", encoding="utf-8")
        (ai / "PROJECT_CONTEXT.md").write_text("# THE SET'S OWN CONTEXT\n", encoding="utf-8")
        (ai / "memory" / "PROJECT_LESSONS.md").write_text("# THE SET'S OWN LESSONS\n", encoding="utf-8")
        return source

    def run_from(self, source: Path, *argv: str) -> tuple[int, str]:
        result = subprocess.run(
            [sys.executable, str(source / ".ai" / "tools" / "adopt.py"), *argv],
            capture_output=True, text=True, check=False,
        )
        return result.returncode, result.stdout + result.stderr

    def assert_none_of_the_sets_records(self) -> None:
        ai = self.target / ".ai"
        self.assertFalse((ai / "ROADMAP.md").exists(), "the set's roadmap travelled")
        self.assertFalse((ai / "reports" / "2026-10-09-the-sets-run.md").exists(), "the set's report travelled")
        self.assertNotIn("THE SET'S OWN CONTEXT", self.context())
        self.assertNotIn("THE SET'S OWN LESSONS",
                         (ai / "memory" / "PROJECT_LESSONS.md").read_text(encoding="utf-8"))

    def test_adoption_does_not_carry_the_sources_instance_files(self) -> None:
        source = self.source_with_instances()
        facts = [a for k, v in FACTS.items() for a in ("--set", f"{k}={v}")]
        code, out = self.run_from(source, "--into", str(self.target), *facts)
        self.assertEqual(code, 0, out)
        self.assert_none_of_the_sets_records()

    def test_upgrade_does_not_carry_the_sources_instance_files(self) -> None:
        adopt(self.target, FACTS)
        code, out = self.run_from(self.source_with_instances(), "--upgrade", "--into", str(self.target))
        self.assertEqual(code, 0, out)
        self.assert_none_of_the_sets_records()

    def test_running_the_tools_leaves_no_bytecode_behind(self) -> None:
        # `adopt.py` imports the checker, and Python caches what it imports.
        # A tool that travels into other people's repositories must not leave
        # a compiled cache in them, or carry one from the source into the next
        # repository it adopts.
        source = self.source_with_instances()
        facts = [a for k, v in FACTS.items() for a in ("--set", f"{k}={v}")]
        self.run_from(source, "--into", str(self.target), *facts)
        self.assertFalse((source / ".ai" / "tools" / "__pycache__").exists(),
                         "running adopt.py wrote a bytecode cache at the source")
        (source / ".ai" / "tools" / "__pycache__").mkdir()
        (source / ".ai" / "tools" / "__pycache__" / "stale.cpython-311.pyc").write_bytes(b"x")
        second = self.tmp / "second"
        self.run_from(source, "--into", str(second), *facts)
        self.assertFalse((second / ".ai" / "tools" / "__pycache__").exists(),
                         "a bytecode cache at the source travelled into the target")

    def test_keep_is_reported_only_for_what_the_target_already_had(self) -> None:
        # The upgrade report once claimed a roadmap it had just copied in was
        # "this repository's". It may say so only of a file that was there.
        adopt(self.target, FACTS)
        source = self.source_with_instances()
        _, out = self.run_from(source, "--upgrade", "--into", str(self.target))
        self.assertNotIn("[keep] .ai/ROADMAP.md", out)
        roadmap = self.target / ".ai" / "ROADMAP.md"
        roadmap.write_text("# Roadmap\n\n## THIS REPOSITORY'S ITEM\n", encoding="utf-8")
        _, out = self.run_from(source, "--upgrade", "--into", str(self.target))
        self.assertIn("[keep] .ai/ROADMAP.md", out)
        self.assertIn("THIS REPOSITORY'S ITEM", roadmap.read_text(encoding="utf-8"))

    def test_every_home_only_test_exists(self) -> None:
        stale = [name for name in NEEDS_THE_SETS_HOME
                 if not any(hasattr(suite, name) for suite in (AdoptTests, PropagateTests))]
        self.assertEqual(stale, [], "listed as needing the set's home, but no such test")

    # -- an adopter's own edit to a policy document is named before it goes --
    # An upgrade overwrites the set's documents. One the adopter edited would
    # go with it, visible only in a diff nobody was told to read.
    def edit_doc(self, rel: str, *, version: str | None = None) -> None:
        path = self.target / rel
        text = path.read_text(encoding="utf-8")
        if version is not None:
            text = re.sub(r"^version: .*$", f"version: {version}", text, count=1, flags=re.M)
        path.write_text(text + "\nA rule this repository added for itself.\n", encoding="utf-8")

    def test_upgrade_names_an_unbumped_local_edit(self) -> None:
        adopt(self.target, FACTS)
        self.edit_doc(".ai/REVIEW.md")
        _, out = upgrade(self.target)
        self.assertIn("[local] .ai/REVIEW.md", out)

    def test_upgrade_names_a_local_edit_that_bumped_its_version(self) -> None:
        # The adopter who followed the versioning rule must not be the one
        # whose edit disappears without a word.
        adopt(self.target, FACTS)
        self.edit_doc(".ai/REVIEW.md", version="99.0.0")
        _, out = upgrade(self.target)
        self.assertIn("[local] .ai/REVIEW.md", out)

    def before_subscriptions(self) -> None:
        """Make the target a repository adopted before 4.0.0, which has no lock
        and so leaves the upgrade only versions to judge an edit by."""
        (self.target / ".ai" / "set.lock").unlink()

    def test_upgrade_does_not_flag_a_document_that_is_merely_older(self) -> None:
        adopt(self.target, FACTS)
        self.before_subscriptions()
        self.edit_doc(".ai/REVIEW.md", version="0.0.1")
        _, out = upgrade(self.target)
        self.assertNotIn("[local] .ai/REVIEW.md", out)

    def test_an_untouched_upgrade_flags_nothing(self) -> None:
        adopt(self.target, FACTS)
        _, out = upgrade(self.target)
        self.assertNotIn("[local]", out)

    def test_an_older_changelog_is_not_mistaken_for_a_local_edit(self) -> None:
        # The release record grows every release while its own version stays
        # put, so every older copy of it has the same version and other text.
        adopt(self.target, FACTS)
        self.before_subscriptions()
        changelog = self.target / ".ai" / "CHANGELOG.md"
        text = changelog.read_text(encoding="utf-8")
        first = text.index("\n## ", text.index("\n---\n"))
        second = text.index("\n## ", first + 1)
        changelog.write_text(text[:first] + text[second:], encoding="utf-8")
        _, out = upgrade(self.target)
        self.assertNotIn("[local] .ai/CHANGELOG.md", out)

    def test_a_local_flag_says_what_it_cannot_tell(self) -> None:
        adopt(self.target, FACTS)
        self.before_subscriptions()
        self.edit_doc(".ai/REVIEW.md")
        _, out = upgrade(self.target)
        self.assertIn("cannot tell", out)

    # -- the subscription ---------------------------------------------------
    def lock_entries(self) -> dict[str, str]:
        entries = {}
        for line in (self.target / ".ai" / "set.lock").read_text(encoding="utf-8").splitlines():
            m = re.match(r"^([0-9a-f]{64})  (.+)$", line)
            if m:
                entries[m.group(2)] = m.group(1)
        return entries

    def test_adoption_locks_what_it_delivered_and_nothing_it_did_not(self) -> None:
        code, out = adopt(self.target, FACTS)
        self.assertEqual(code, 0, out)
        self.assertIn("[PASS] subscribed copy", out)
        entries = self.lock_entries()
        for name in ("CLAUDE.md", "AGENTS.md", ".ai/CORE.md", ".ai/CHANGELOG.md",
                     ".ai/tools/adopt.py", ".claude/agents/fast-explorer.md"):
            self.assertIn(name, entries, f"{name} was delivered")
        for name in (".ai/PROJECT_CONTEXT.md", ".ai/memory/PROJECT_LESSONS.md",
                     ".ai/tools/portability-denylist.txt", ".ai/memory/MANAGER_PLAYBOOK.md",
                     ".ai/reports/.gitkeep", ".ai/set.lock"):
            self.assertNotIn(name, entries, f"{name} belongs to the repository")
        lock = (self.target / ".ai" / "set.lock").read_text(encoding="utf-8")
        version = re.search(r"^## (\d+\.\d+\.\d+)", (ROOT / ".ai" / "CHANGELOG.md").read_text(encoding="utf-8"), re.M)
        self.assertIn(f"version: {version.group(1)}", lock)
        self.assertRegex(lock, r"(?m)^source: \S")
        self.assertRegex(lock, r"(?m)^commit: \S")

    def test_a_capability_the_adopter_already_had_is_not_subscribed(self) -> None:
        agent = self.target / ".claude" / "agents" / "fast-explorer.md"
        agent.parent.mkdir(parents=True)
        agent.write_text("---\nname: fast-explorer\ndescription: ours\n---\n\nOurs.\n", encoding="utf-8")
        adopt(self.target, FACTS)
        self.assertNotIn(".claude/agents/fast-explorer.md", self.lock_entries())
        self.assertIn(".claude/agents/adversarial-reviewer.md", self.lock_entries())

    def test_an_edit_to_a_subscribed_file_fails_the_adopters_check(self) -> None:
        adopt(self.target, FACTS)
        self.edit_doc(".ai/REVIEW.md")
        code, out = run_checker_in(self.target)
        self.assertEqual(code, 1, out)
        self.assertIn(".ai/REVIEW.md: edited here", out)

    def test_with_a_lock_even_an_older_document_is_an_edit(self) -> None:
        # The lock says what was delivered, so a difference is an edit whatever
        # the version says — and the report says the flag is exact.
        adopt(self.target, FACTS)
        self.edit_doc(".ai/REVIEW.md", version="0.0.1")
        _, out = upgrade(self.target)
        self.assertIn("[local] .ai/REVIEW.md", out)
        self.assertIn("[local] is exact here", out)
        self.assertNotIn("cannot tell", out)

    def test_an_upgrade_subscribes_a_repository_adopted_before_subscriptions(self) -> None:
        adopt(self.target, FACTS)
        self.before_subscriptions()
        code, out = upgrade(self.target)
        self.assertEqual(code, 0, out)
        self.assertIn("[lock] .ai/set.lock", out)
        self.assertIn("[PASS] subscribed copy", out)
        self.assertNotIn("[keep] .ai/set.lock", out)

    def test_upgrade_keeps_the_manager_playbook(self) -> None:
        # A repository writes its candidate lessons there.
        adopt(self.target, FACTS)
        playbook = self.target / ".ai" / "memory" / "MANAGER_PLAYBOOK.md"
        playbook.write_text(playbook.read_text(encoding="utf-8") + "\n- candidate: a lesson\n", encoding="utf-8")
        code, out = upgrade(self.target)
        self.assertEqual(code, 0, out)
        self.assertIn("candidate: a lesson", playbook.read_text(encoding="utf-8"))
        self.assertNotIn("[local] .ai/memory/MANAGER_PLAYBOOK.md", out)

    def test_an_earlier_version_the_set_shipped_is_refreshed(self) -> None:
        # Before 4.0.0 nothing recorded a delivery, so a capability holding a
        # version the set once shipped looked like the repository's own, and
        # the Codex entry point stayed at whatever version first arrived.
        log = subprocess.run(["git", "-C", str(ROOT), "log", "--format=%H", "HEAD", "--", "AGENTS.md"],
                             capture_output=True, text=True).stdout.split()
        current = (ROOT / "AGENTS.md").read_bytes()
        older = next((b for b in (subprocess.run(["git", "-C", str(ROOT), "show", f"{c}:AGENTS.md"],
                                                 capture_output=True).stdout for c in log[1:]) if b and b != current), None)
        if older is None:
            self.skipTest("this clone holds no earlier version of AGENTS.md")
        adopt(self.target, FACTS)
        self.before_subscriptions()
        (self.target / "AGENTS.md").write_bytes(older)
        code, out = upgrade(self.target)
        self.assertEqual(code, 0, out)
        self.assertEqual((self.target / "AGENTS.md").read_bytes(), current)
        self.assertNotIn("[stale] AGENTS.md", out)
        self.assertIn("AGENTS.md", self.lock_entries())

    def test_a_kept_playbook_is_not_named_as_a_local_edit_either(self) -> None:
        adopt(self.target, FACTS)
        self.before_subscriptions()
        playbook = self.target / ".ai" / "memory" / "MANAGER_PLAYBOOK.md"
        playbook.write_text(playbook.read_text(encoding="utf-8") + "\n- candidate: a lesson\n", encoding="utf-8")
        _, out = upgrade(self.target)
        self.assertNotIn("[local] .ai/memory/MANAGER_PLAYBOOK.md", out)

    def test_a_capability_the_repository_removed_is_not_delivered_again(self) -> None:
        adopt(self.target, FACTS)
        agent = self.target / ".claude" / "agents" / "fast-explorer.md"
        agent.unlink()
        code, out = upgrade(self.target)
        self.assertEqual(code, 0, out)
        self.assertFalse(agent.exists(), "removing a capability is the repository's choice")

    def test_a_subscribed_capability_edited_here_is_replaced_and_named(self) -> None:
        # The lock says the set delivered it, so an edit is an edit to the
        # set's file: replaced like a policy document, and named. Keeping it
        # while saying it was replaced, and then dropping it from the lock,
        # turned the check's failure into a pass.
        adopt(self.target, FACTS)
        agent = self.target / ".claude" / "agents" / "fast-explorer.md"
        agent.write_text(agent.read_text(encoding="utf-8") + "\nA local line.\n", encoding="utf-8")
        code, out = upgrade(self.target)
        self.assertEqual(code, 0, out)
        self.assertEqual(agent.read_bytes(), (ROOT / ".claude" / "agents" / "fast-explorer.md").read_bytes())
        self.assertIn("[local] .claude/agents/fast-explorer.md", out)
        self.assertNotIn("[stale] .claude/agents/fast-explorer.md", out)
        self.assertIn(".claude/agents/fast-explorer.md", self.lock_entries())

    def test_a_removal_outlives_the_upgrade_that_saw_it(self) -> None:
        adopt(self.target, FACTS)
        agent = self.target / ".claude" / "agents" / "fast-explorer.md"
        agent.unlink()
        for _ in range(2):
            code, out = upgrade(self.target)
            self.assertEqual(code, 0, out)
            self.assertFalse(agent.exists(), out)
        self.assertIn("removed: .claude/agents/fast-explorer.md",
                      (self.target / ".ai" / "set.lock").read_text(encoding="utf-8"))
        self.assertIn("1 removed capabilities excused", out)

    def test_without_a_lock_a_removed_capability_cannot_be_told_apart(self) -> None:
        # Before 4.0.0 nothing recorded the delivery, so a missing capability
        # looks like one never delivered, and the upgrade delivers it.
        adopt(self.target, FACTS)
        self.before_subscriptions()
        agent = self.target / ".claude" / "agents" / "fast-explorer.md"
        agent.unlink()
        upgrade(self.target)
        self.assertTrue(agent.exists())

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
        code, out = self.from_template(tree, "--name", "Acme Web")
        # Without this the test passes when the mode refuses to run at all:
        # the marker was never there to remove.
        self.assertEqual(code, 0, out)
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



class PropagateTests(unittest.TestCase):
    """`propagate.py` sends a release to every subscriber the registry names."""

    def setUp(self) -> None:
        reason = NEEDS_THE_SETS_HOME.get(self._testMethodName)
        if reason and not AT_SET_HOME:
            self.skipTest(f"needs the set's home: {reason}")
        self.tmp = Path(tempfile.mkdtemp(prefix="propagate-"))
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.source = self.tmp / "set"
        shutil.copytree(ROOT, self.source, ignore=shutil.ignore_patterns(".git", "__pycache__"))
        (self.source / "LESSONS_FROM_PRACTICE.md").touch()
        self.clones = self.tmp / "clones"
        self.clones.mkdir()

    def git(self, cwd: Path, *args: str) -> str:
        done = subprocess.run(["git", "-C", str(cwd), "-c", "user.name=t", "-c", "user.email=t@t",
                               "-c", "commit.gpgsign=false", *args], capture_output=True, text=True)
        self.assertEqual(done.returncode, 0, done.stderr)
        return done.stdout

    def subscriber(self, name: str, *, before_subscriptions: bool = True) -> Path:
        """A repository that adopted the set, pushed to a remote, and cloned."""
        work = self.tmp / "work" / name
        code, out = adopt(work, FACTS)
        self.assertEqual(code, 0, out)
        if before_subscriptions:
            (work / ".ai" / "set.lock").unlink()
        remote = self.tmp / "remotes" / f"{name}.git"
        self.git(self.tmp, "init", "-q", "--bare", "-b", "main", str(remote))
        self.git(work, "init", "-q", "-b", "main")
        self.git(work, "add", "-A")
        self.git(work, "commit", "-q", "-m", "adopt")
        self.git(work, "push", "-q", str(remote), "main")
        self.git(self.tmp, "clone", "-q", str(remote), str(self.clones / name))
        return remote

    def registry(self, *lines: str) -> None:
        (self.source / ".ai" / "SUBSCRIBERS.md").write_text(
            "# Subscribers\n\n```text\n" + "\n".join(lines) + "\n```\n", encoding="utf-8")

    def propagate(self, *extra: str) -> tuple[int, str]:
        done = subprocess.run(
            [sys.executable, str(self.source / ".ai" / "tools" / "propagate.py"), "--clones", str(self.clones), *extra],
            capture_output=True, text=True, check=False)
        return done.returncode, done.stdout + done.stderr

    def test_a_subscriber_is_upgraded_on_its_own_branch_with_a_body(self) -> None:
        remote = self.subscriber("acme")
        self.registry("owner/acme  main")
        code, out = self.propagate("--push", "--trailer", "Co-Authored-By: X <x@x>")
        self.assertEqual(code, 0, out)
        self.assertIn("[upgraded] owner/acme", out)
        branch = [b for b in self.git(remote, "branch", "--list", "claude/set-*").split() if b.startswith("claude/")]
        self.assertEqual(len(branch), 1, "the upgrade branch was pushed")
        message = self.git(remote, "log", "-1", "--format=%B", branch[0])
        self.assertIn("Co-Authored-By: X <x@x>", message)
        self.assertIn(".ai/set.lock", self.git(remote, "show", "--name-only", "--format=", branch[0]))
        body = (self.clones / "acme.pr.md").read_text(encoding="utf-8")
        self.assertIn("[PASS] subscribed copy", body)

    def test_an_unfinished_template_copy_is_named(self) -> None:
        self.subscriber("acme")
        clone = self.clones / "acme"
        for name in ("LESSONS_FROM_PRACTICE.md", "README.md"):
            shutil.copy2(ROOT / name if (ROOT / name).exists() else self.source / name, clone / name)
        self.git(clone, "add", "-A")
        self.git(clone, "commit", "-qm", "template copy")
        self.git(clone, "push", "-q", "origin", "main")
        self.registry("owner/acme  main")
        code, out = self.propagate()
        self.assertEqual(code, 0, out)
        self.assertIn("template copy never finished", out)
        self.assertIn("still looks like the set's own home", (self.clones / "acme.pr.md").read_text(encoding="utf-8"))

    def test_a_clone_with_uncommitted_work_is_not_upgraded(self) -> None:
        remote = self.subscriber("acme")
        (self.clones / "acme" / "scratch.txt").write_text("not the set's\n", encoding="utf-8")
        self.registry("owner/acme  main")
        code, out = self.propagate("--push")
        self.assertEqual(code, 1, out)
        self.assertIn("uncommitted changes", out)
        self.assertEqual(self.git(remote, "branch", "--list", "claude/*").strip(), "")

    def test_nothing_leaves_without_push(self) -> None:
        remote = self.subscriber("acme")
        self.registry("owner/acme  main")
        code, out = self.propagate()
        self.assertEqual(code, 0, out)
        self.assertEqual(self.git(remote, "branch", "--list", "claude/*").strip(), "")

    def test_a_subscriber_already_current_gets_no_commit(self) -> None:
        remote = self.subscriber("acme")
        self.registry("owner/acme  main")
        self.propagate("--push")
        branch = self.git(remote, "branch", "--list", "claude/set-*").split()[-1]
        self.git(remote, "update-ref", "refs/heads/main", branch)
        code, out = self.propagate("--push")
        self.assertEqual(code, 0, out)
        self.assertIn("[current]  owner/acme", out)

    def test_a_held_subscriber_is_named_and_skipped(self) -> None:
        self.registry("owner/paid  main  hold: a push runs paid Actions")
        code, out = self.propagate("--push")
        self.assertEqual(code, 0, out)
        self.assertIn("[hold]     owner/paid: a push runs paid Actions", out)

    def test_a_missing_clone_fails_the_run(self) -> None:
        self.registry("owner/absent  main")
        code, out = self.propagate()
        self.assertEqual(code, 1, out)
        self.assertIn("[no clone] owner/absent", out)

    def test_a_subscriber_whose_check_fails_is_not_committed(self) -> None:
        remote = self.subscriber("acme")
        clone = self.clones / "acme"
        context = clone / ".ai" / "PROJECT_CONTEXT.md"
        context.write_text(context.read_text(encoding="utf-8").replace("test_command:", "tests:"), encoding="utf-8")
        self.git(clone, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qam", "break")
        self.git(clone, "push", "-q", "origin", "main")
        self.registry("owner/acme  main")
        code, out = self.propagate("--push")
        self.assertEqual(code, 1, out)
        self.assertIn("[failed]   owner/acme", out)
        self.assertEqual(self.git(remote, "branch", "--list", "claude/*").strip(), "")

    def test_a_malformed_registry_line_is_refused(self) -> None:
        self.registry("acme main")
        code, out = self.propagate()
        self.assertNotEqual(code, 0)
        self.assertIn("expected `owner/repo  base [hold: why]`", out)

    def test_propagation_runs_only_where_the_registry_is(self) -> None:
        (self.source / ".ai" / "SUBSCRIBERS.md").unlink(missing_ok=True)
        code, out = self.propagate()
        self.assertNotEqual(code, 0)
        self.assertIn("propagation runs at the set's home", out)


if __name__ == "__main__":
    unittest.main(verbosity=2)
