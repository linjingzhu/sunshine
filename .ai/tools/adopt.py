#!/usr/bin/env python3
"""Adopt this policy set into a repository, or start a new one from it.

Copying the policy and harness entry points is the easy half. The half people get wrong is
the instance files: `PROJECT_CONTEXT.md` and `memory/PROJECT_LESSONS.md` must
exist, must carry every fact the checks read, and must not still contain the
template's own instructions. This does that half, then runs the checks so the
adopting repository starts green instead of starting broken.

    # adopt into a new repository, filling the facts non-interactively
    python3 .ai/tools/adopt.py --into ../my-project \\
        --name "My Project" \\
        --set repository_mode=personal --set base_branch=main \\
        --set merge_deploys=no --set runtime_gate=none \\
        --set test_command="npm test" --set lint_command="npm run lint" \\
        --set build_command="npm run build" --set generated=none \\
        --set external_scripts=none --set public_ids=none \\
        --set owner_ledger=docs/OWNER_ACTIONS.md

    # adopt in place, and be told which facts are still missing
    python3 .ai/tools/adopt.py

    # finish a repository made with GitHub's "Use this template", which copies
    # every file including the two that must not travel
    python3 .ai/tools/adopt.py --from-template --name "My Project" --set ...

Facts not supplied are left as the template's placeholder, and the run ends by
naming them: an adopter is told exactly what is unanswered rather than being
handed a file that looks finished. Standard library only.

Exit status is 0 when the target passes every check, 1 otherwise.
"""

from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
from pathlib import Path

SET_ROOT = Path(__file__).resolve().parents[2]

# What travels into an adopting repository, and nothing else.
#
# `README.md` and `LESSONS_FROM_PRACTICE.md` deliberately stay behind. The
# first would overwrite the adopter's own front page. The second is what
# `check_policy_set.py` uses to tell the set's home from a repository that
# adopted it, so copying it would make an adopted tree claim to be the set
# itself — and the checks would start reading the adopter's `README.md` as if
# it were this one's, which is the defect 2.2.1 fixed.
TRAVELS = ("CLAUDE.md", ".ai")

# Project capabilities travel too, but never over an adopter's own: a
# repository may already have agents of its own, and overwriting one because
# the set happens to ship a file of that name destroys work nobody asked about.
# `.ai/HARNESS.md` § Where harness configuration belongs is the rule; this is
# the half of it a tool can enforce.
CAPABILITIES = (
    "AGENTS.md",
    ".claude/agents",
    ".claude/skills",
    ".codex/agents",
    ".agents/skills",
)

TEMPLATES = {
    ".ai/PROJECT_CONTEXT.template.md": ".ai/PROJECT_CONTEXT.md",
    ".ai/memory/PROJECT_LESSONS.template.md": ".ai/memory/PROJECT_LESSONS.md",
}

KEY_LINE = re.compile(r"^([a-z_]+):\s*(.*)$")
PLACEHOLDER = re.compile(r"<[^>]+>")


def strip_instructions(text: str) -> str:
    """Remove the template's own instruction lines.

    They are written as blockquotes, which is what makes this mechanical: an
    instruction is a line the reader of the instance should never see, and every
    one of them starts with `>`. Blank lines left behind are collapsed so the
    result does not read as a file with holes in it.
    """
    kept: list[str] = []
    fenced = False
    for line in text.splitlines():
        if line.lstrip().startswith("```"):
            fenced = not fenced
        if not fenced and line.lstrip().startswith(">"):
            continue
        kept.append(line)

    out: list[str] = []
    for line in kept:
        if not line.strip() and out and not out[-1].strip():
            continue
        out.append(line)
    return "\n".join(out).strip() + "\n"


def apply_facts(text: str, facts: dict[str, str]) -> tuple[str, list[str]]:
    """Set `key: value` lines inside fenced blocks. Returns text and keys used."""
    used: list[str] = []
    out: list[str] = []
    fenced = False
    for line in text.splitlines():
        if line.lstrip().startswith("```"):
            fenced = not fenced
            out.append(line)
            continue
        if fenced:
            m = KEY_LINE.match(line.strip())
            if m and m.group(1) in facts:
                out.append(f"{m.group(1)}: {facts[m.group(1)]}")
                used.append(m.group(1))
                continue
        out.append(line)
    return "\n".join(out) + "\n", used


def unanswered_facts(text: str) -> list[str]:
    """Fenced keys whose value is still a placeholder or an enum menu."""
    open_keys: list[str] = []
    fenced = False
    for line in text.splitlines():
        if line.lstrip().startswith("```"):
            fenced = not fenced
            continue
        if not fenced:
            continue
        m = KEY_LINE.match(line.strip())
        if not m:
            continue
        value = m.group(2).strip()
        if not value or PLACEHOLDER.search(value) or "|" in value:
            open_keys.append(m.group(1))
    return open_keys


# GitHub's "Use this template" copies every tracked file, including the two
# `TRAVELS` deliberately leaves behind. `LESSONS_FROM_PRACTICE.md` is the one
# that breaks things: `check_policy_set.py` reads its presence as "this tree is
# the set's home", and then reads the repository's `README.md` as the set's own.
# Removing it is the whole correctness fix — verified, and the reason this mode
# does not touch `README.md`.
SET_HOME_MARKER = Path("LESSONS_FROM_PRACTICE.md")
DENYLIST = Path(".ai/tools/portability-denylist.txt")
# The set's own front page title. Matching it is a heuristic, and the only
# thing it decides is whether to print a warning — never whether to delete.
SET_README_TITLE = "# ai-dev-rule"


def finish_template_copy(target: Path, name: str | None) -> list[str]:
    """Make a tree produced by "Use this template" stop claiming to be the set.

    Returns the notes to print. Removes exactly one file and rewrites one; the
    adopter's `README.md` is reported, never deleted — a tool that deletes a
    repository's front page because it recognised the text is a tool nobody
    should run twice.
    """
    notes: list[str] = []
    marker = target / SET_HOME_MARKER

    if not marker.exists():
        raise SystemExit(
            f"--from-template: {SET_HOME_MARKER} is not here, so this is not a "
            "tree made with \"Use this template\". Adopt with --into instead."
        )

    marker.unlink()
    notes.append(f"[remove] {SET_HOME_MARKER} — the tree no longer claims to be the set")

    denylist = target / DENYLIST
    if name:
        denylist.parent.mkdir(parents=True, exist_ok=True)
        denylist.write_text(
            "# Terms that must not appear outside the files allowed to know\n"
            "# what the project is. One per line; `#` starts a comment.\n"
            "#\n"
            "# Seeded from --name. Add your organisation, and any other name\n"
            "# whose appearance in a policy document would mean it had stopped\n"
            "# being portable.\n"
            f"{name}\n",
            encoding="utf-8",
        )
        notes.append(f"[write]  {DENYLIST} — seeded with `{name}`, replacing the set's own names")
    else:
        notes.append(
            f"[warn]   {DENYLIST} still holds the set's names. Replace them with "
            "yours, or the portability check proves nothing here."
        )

    readme = target / "README.md"
    if readme.exists() and SET_README_TITLE in readme.read_text(encoding="utf-8"):
        notes.append(
            "[warn]   README.md is still this set's front page, not your project's. "
            "Nothing here rewrites it — replace it yourself."
        )
    return notes


def copy_set(target: Path) -> list[str]:
    copied: list[str] = []
    for name in TRAVELS:
        source = SET_ROOT / name
        destination = target / name
        if source.is_dir():
            shutil.copytree(source, destination, dirs_exist_ok=True)
        else:
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)
        copied.append(name)
    return copied


def copy_capabilities(target: Path) -> tuple[list[str], list[str]]:
    """Copy the Codex entry point and shipped capabilities without replacing
    an adopter's own entry point, agent definition, or skill directory.

    Returns (written, kept). A file the adopter already has is theirs, with or
    without `--force`: their `fast-explorer.md` is their harness, not a stale
    copy of ours.
    """
    written: list[str] = []
    kept: list[str] = []
    for name in CAPABILITIES:
        source = SET_ROOT / name
        if not source.exists():
            continue
        paths = [source] if source.is_file() else sorted(source.rglob("*"))
        # A skill's metadata and references are part of the same capability.
        # Do not mix packaged metadata into an adopter's existing skill.
        existing_skills = (
            {p.name for p in source.iterdir() if (target / name / p.name).exists()}
            if source.is_dir() and source.name == "skills" else set()
        )
        for path in paths:
            if not path.is_file():
                continue
            relative = path.relative_to(SET_ROOT)
            destination = target / relative
            skill_exists = (
                source.is_dir() and source.name == "skills"
                and path.relative_to(source).parts[0] in existing_skills
            )
            if destination.exists() or skill_exists:
                kept.append(relative.as_posix())
                continue
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, destination)
            written.append(relative.as_posix())
    return written, kept


def write_instances(target: Path, facts: dict[str, str], name: str | None, force: bool) -> list[str]:
    written: list[str] = []
    for template_rel, instance_rel in TEMPLATES.items():
        template = target / template_rel
        instance = target / instance_rel
        if not template.exists():
            raise SystemExit(f"missing template: {template_rel}")
        if instance.exists() and not force:
            print(f"[keep] {instance_rel} already exists")
            continue

        text = strip_instructions(template.read_text(encoding="utf-8"))
        text, _ = apply_facts(text, facts)
        if name:
            text = re.sub(r"^# .*$", f"# {name} Context", text, count=1, flags=re.M)
        instance.parent.mkdir(parents=True, exist_ok=True)
        instance.write_text(text, encoding="utf-8")
        written.append(instance_rel)
    return written


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--into", type=Path, help="repository to adopt into (default: this one, in place)")
    parser.add_argument("--name", help="project name for the context file's title")
    parser.add_argument("--set", action="append", default=[], metavar="key=value",
                        help="a fact for the context file; repeatable")
    parser.add_argument("--force", action="store_true", help="overwrite instance files that already exist")
    parser.add_argument("--from-template", action="store_true",
                        help="finish a repository made with GitHub's \"Use this template\": "
                             "remove the file that makes the tree claim to be the set, and "
                             "reseed the portability denylist")
    args = parser.parse_args(sys.argv[1:] if argv is None else argv)

    facts: dict[str, str] = {}
    for pair in args.set:
        if "=" not in pair:
            raise SystemExit(f"--set expects key=value, got: {pair}")
        key, _, value = pair.partition("=")
        facts[key.strip()] = value.strip()

    target = (args.into or SET_ROOT).resolve()
    target.mkdir(parents=True, exist_ok=True)

    if args.from_template:
        if args.into:
            raise SystemExit("--from-template works in place; drop --into.")
        for note in finish_template_copy(target, args.name):
            print(note)
        print()

    if target != SET_ROOT:
        print(f"[copy] {', '.join(copy_set(target))} → {target}")
        written, kept = copy_capabilities(target)
        for path in written:
            print(f"[copy] {path}")
        for path in kept:
            print(f"[keep] {path} is yours; the set's copy was not written over it")

    written = write_instances(target, facts, args.name, args.force)
    for path in written:
        print(f"[write] {path}")

    context = target / ".ai" / "PROJECT_CONTEXT.md"
    still_open = unanswered_facts(context.read_text(encoding="utf-8")) if context.exists() else []

    print()
    result = subprocess.run(
        [sys.executable, str(target / ".ai" / "tools" / "check_policy_set.py"), str(target)],
        check=False,
    )

    if still_open:
        print()
        print("Facts still unanswered — the checks will fail until each has a value:")
        for key in still_open:
            print(f"  - {key}")
        print()
        print("`none` is a value; an empty one is not. Re-run with --force and")
        print("--set key=value, or edit .ai/PROJECT_CONTEXT.md directly.")

    return result.returncode


if __name__ == "__main__":
    sys.exit(main())
