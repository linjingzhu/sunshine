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
import hashlib
import re
import shutil
import subprocess
import sys
from pathlib import Path

# The checker owns the definition of a file a repository owns. Copying by one
# definition while exempting by another lets a roadmap or a report written at
# the set's home reach every repository adopted after it. The two scripts
# travel together in `.ai/tools/`, so the import always resolves. Importing
# would otherwise leave a compiled cache beside the checker, in whatever
# repository the tool runs in — and the next copy would carry it on.
sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))
from check_policy_set import (  # noqa: E402
    INSTANCE_PATHS, LOCK, digest, is_instance, parse_front_matter, read_lock, removable,
)

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

# What an adopting repository owns, and an upgrade must hand back untouched.
#
# The dangerous one is the denylist. The set ships it with its own seed names,
# so copying `.ai/` over an adopted tree replaces the adopter's product names
# with another project's — and their portability check goes on passing while
# proving nothing, which is precisely what that file's own comment warns
# about. The instance files are the checker's own list, so the two cannot drift;
# `copy_set` never writes them, and holding them here as well costs nothing.
#
# The manager playbook is the set's seed, not its rule: it ships empty but for
# its promotion rule, and a repository writes its candidate lessons into it.
# Replacing it would discard those lessons on every release. Like the
# denylist, it is delivered once and then belongs to the repository.
#
# The lock is an instance file but is not preserved: every upgrade writes it
# anew, for what that upgrade delivered.
PRESERVED = (
    ".ai/tools/portability-denylist.txt",
    ".ai/memory/MANAGER_PLAYBOOK.md",
    *sorted(INSTANCE_PATHS - {LOCK}),
)

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


def owned_by_the_target(directory: str, names: list[str]) -> list[str]:
    """`copytree`'s ignore hook: skip every instance file at the source, and any
    bytecode cache a Python run left there, which belongs to no repository.

    `.gitkeep` is exempt. It is the set's placeholder that makes the reports
    directory exist, not a report.
    """
    here = Path(directory).relative_to(SET_ROOT)
    return [
        n for n in names
        if n == "__pycache__" or n.endswith(".pyc")
        or (n != ".gitkeep" and is_instance((here / n).as_posix()))
    ]


def copy_set(target: Path) -> list[str]:
    copied: list[str] = []
    for name in TRAVELS:
        source = SET_ROOT / name
        destination = target / name
        if source.is_dir():
            shutil.copytree(source, destination, dirs_exist_ok=True, ignore=owned_by_the_target)
        else:
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)
        copied.append(name)
    return copied


def copy_capabilities(target: Path, removed: frozenset[str] = frozenset()) -> tuple[list[str], list[str]]:
    """Copy the Codex entry point and shipped capabilities without replacing
    an adopter's own entry point, agent definition, or skill directory.

    Returns (written, kept). A file the adopter already has is theirs, with or
    without `--force`: their `fast-explorer.md` is their harness, not a stale
    copy of ours. A file in `removed` was delivered before and taken out by the
    repository, which is its choice, so it is not delivered again.
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
            if relative.as_posix() in removed:
                continue
            if destination.exists() or skill_exists:
                kept.append(relative.as_posix())
                continue
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, destination)
            written.append(relative.as_posix())
    return written, kept


def set_version(root: Path) -> str:
    """The newest release the changelog at `root` records, or `unknown`."""
    changelog = root / ".ai" / "CHANGELOG.md"
    if not changelog.exists():
        return "unknown"
    for line in changelog.read_text(encoding="utf-8").splitlines():
        if line.startswith("## ") and line[3:4].isdigit():
            return line[3:].split("—")[0].strip()
    return "unknown"


def shipped_before(name: str) -> set[str]:
    """Git blob ids of every version of `name` the set has committed."""
    raw = git_at_set("log", "--format=", "--raw", "--no-abbrev", "HEAD", "--", name) or ""
    return {
        blob for line in raw.splitlines() if line.startswith(":")
        for blob in line.split()[2:4] if blob.strip("0")
    }


def blob_ids(data: bytes) -> set[str]:
    """The ids git would give this content, as checked out and as committed."""
    return {
        hashlib.sha1(b"blob %d\0" % len(d) + d).hexdigest()
        for d in (data, data.replace(b"\r\n", b"\n"))
    }


def earlier_deliveries(target: Path, kept: list[str]) -> list[str]:
    """Of the capabilities left in place, the ones holding a version the set
    itself once shipped. They are the set's, only older: before 4.0.0 nothing
    recorded a delivery, and without this the entry point every Codex run
    reads would stay at whatever version first arrived."""
    return [
        name for name in kept
        if (target / name).is_file() and (SET_ROOT / name).is_file()
        and (target / name).read_bytes() != (SET_ROOT / name).read_bytes()
        and blob_ids((target / name).read_bytes()) & shipped_before(name)
    ]


def stale_capabilities(target: Path, kept: list[str]) -> list[str]:
    """Of the capabilities left in place, the ones whose content is not the
    set's. An identical copy is not worth a line; a different one is, because
    the repository will go on running the older definition."""
    return [
        name for name in kept
        if (SET_ROOT / name).is_file()
        and (target / name).is_file()
        and (target / name).read_bytes() != (SET_ROOT / name).read_bytes()
    ]


# The release record grows every release, while its own version moves only
# when its rules do. An older copy with the same rules has the same version and
# other text, and would be named as a local edit on every upgrade. Nobody edits the set's record in an adopter.
NOT_JUDGED = (".ai/CHANGELOG.md",)
SEMVER = re.compile(r"^(\d+)\.(\d+)\.(\d+)$")


def version_of(text: str) -> tuple[int, ...] | None:
    match = SEMVER.match((parse_front_matter(text) or {}).get("version", ""))
    return tuple(int(n) for n in match.groups()) if match else None


def local_edits(target: Path) -> list[str]:
    """Policy documents the upgrade is about to overwrite that were edited here.

    A document whose text differs from the set's is either stale or edited.
    Stale means its version is lower. Same or higher means the change was made
    in this repository — including by an adopter who followed the versioning
    rule and bumped it, who must not be the one whose edit vanishes silently.
    """
    edits: list[str] = []
    for source in sorted((SET_ROOT / ".ai").rglob("*.md")):
        name = source.relative_to(SET_ROOT).as_posix()
        here = target / name
        if is_instance(name) or name in NOT_JUDGED or name in PRESERVED or not here.is_file():
            continue
        theirs, ours = here.read_text(encoding="utf-8"), source.read_text(encoding="utf-8")
        if theirs == ours:
            continue
        their_version, our_version = version_of(theirs), version_of(ours)
        if their_version is None or our_version is None or their_version >= our_version:
            edits.append(name)
    return edits


def git_at_set(*args: str) -> str | None:
    try:
        done = subprocess.run(["git", "-C", str(SET_ROOT), *args], capture_output=True, text=True)
    except OSError:
        return None
    return done.stdout.strip() if done.returncode == 0 else None


def set_source() -> tuple[str, str]:
    """`owner/repo` and commit of the set being delivered, or `unknown`.

    The commit says exactly what was delivered; a set with uncommitted changes
    to what it delivers says so rather than naming a commit that does not hold
    them."""
    url = git_at_set("remote", "get-url", "origin") or ""
    parts = [p for p in re.split(r"[/:]", url.removesuffix(".git")) if p]
    source = "/".join(parts[-2:]) if len(parts) >= 2 else "unknown"
    commit = git_at_set("rev-parse", "HEAD") or "unknown"
    if commit != "unknown" and git_at_set("status", "--porcelain", "--", *TRAVELS, *CAPABILITIES):
        commit += " plus uncommitted changes"
    return source, commit


def subscribed_files(target: Path) -> list[str]:
    """What the set delivered into `target` and still owns there.

    Every travelling file except the instance and preserved files, and each
    shipped capability the target holds exactly as the set ships it. A
    capability that differs is the repository's own, not a subscribed copy.
    """
    names: list[str] = []
    for top in TRAVELS:
        source = SET_ROOT / top
        for path in ([source] if source.is_file() else sorted(source.rglob("*"))):
            name = path.relative_to(SET_ROOT).as_posix()
            if (not path.is_file() or "__pycache__" in path.parts or path.suffix == ".pyc"
                    or is_instance(name) or name in PRESERVED):
                continue
            names.append(name)
    for top in CAPABILITIES:
        source = SET_ROOT / top
        if not source.exists():
            continue
        for path in ([source] if source.is_file() else sorted(source.rglob("*"))):
            name = path.relative_to(SET_ROOT).as_posix()
            here = target / name
            if path.is_file() and here.is_file() and digest(here.read_bytes()) == digest(path.read_bytes()):
                names.append(name)
    return sorted(names)


def write_lock(target: Path, in_place: bool = False, removed: frozenset[str] = frozenset()) -> int:
    """Record what this delivery left in `target`, and the capabilities the
    repository removed that the set still ships. Returns how many files."""
    source, commit = ("unknown (adopted in place)", "unknown") if in_place else set_source()
    names = subscribed_files(target)
    gone = sorted(n for n in removed if not (target / n).exists() and (SET_ROOT / n).is_file())
    # Every other capability the set ships and this delivery did not leave
    # here as the set's: the repository holds its own in that place.
    kept = sorted(
        path.relative_to(SET_ROOT).as_posix()
        for top in CAPABILITIES if (SET_ROOT / top).exists()
        for path in ([SET_ROOT / top] if (SET_ROOT / top).is_file() else sorted((SET_ROOT / top).rglob("*")))
        if path.is_file() and path.relative_to(SET_ROOT).as_posix() not in set(names) | set(gone)
    )
    lines = [
        "# Written by .ai/tools/adopt.py. The files below are this repository's",
        "# subscription to the policy set: they are replaced on every upgrade, so",
        "# change them at the set's home, never here. A rule only this repository",
        "# needs goes in .ai/PROJECT_CONTEXT.md, under Local rules.",
        f"source: {source}",
        f"version: {set_version(SET_ROOT)}",
        f"commit: {commit}",
        "",
        *(f"{digest((target / name).read_bytes())}  {name}" for name in names),
        *(f"removed: {name}" for name in gone),
        *(f"kept: {name}" for name in kept),
    ]
    (target / LOCK).write_text("\n".join(lines) + "\n", encoding="utf-8")
    return len(names)


def locked_state(target: Path) -> tuple[list[str], frozenset[str]] | None:
    """From the target's lock: the subscribed files edited there, and the
    capabilities removed there. None when the target has no lock."""
    lock = target / LOCK
    if not lock.is_file():
        return None
    _, entries, marks, _ = read_lock(lock.read_text(encoding="utf-8"))
    edited, removed = [], {
        n for n, mark in marks.items()
        if mark == "removed" and removable(n) and not (target / n).exists()
    }
    for name, want in sorted(entries.items()):
        here = target / name
        if here.is_file():
            if digest(here.read_bytes()) != want:
                edited.append(name)
        elif removable(name):
            removed.add(name)
    return edited, frozenset(removed)


def upgrade(target: Path, refresh_capabilities: bool = False) -> tuple[list[str], list[str], str, str, list[str], list[str], bool]:
    """Refresh the set in a repository that already adopted it.

    Adoption and upgrade differ in one thing that matters: an upgrade runs
    against a tree that has been lived in. Everything in `PRESERVED` is read
    before the copy and written back after, so the copy cannot quietly take
    the repository's own facts with it.

    Returns (written capabilities, kept capabilities, version before, after,
    the preserved files the target actually had, the subscribed files edited
    there, and whether that last list is exact). It is exact when the target
    has a lock: the lock says what was delivered, so any difference is an
    edit. Without one, versions are all there is to judge by.
    """
    if not (target / ".ai" / "CORE.md").exists():
        raise SystemExit(
            f"{target} has not adopted the set — there is nothing to upgrade.\n"
            "Run without --upgrade to adopt it, which needs the project's facts."
        )

    held = {
        name: (target / name).read_bytes()
        for name in PRESERVED
        if (target / name).is_file()
    }
    before = set_version(target)
    state = locked_state(target)
    edited, removed = state if state else (local_edits(target), frozenset())

    copy_set(target)
    written, kept = copy_capabilities(target, removed)

    if refresh_capabilities:
        for name in kept:
            source = SET_ROOT / name
            if source.is_file():
                (target / name).write_bytes(source.read_bytes())
        written, kept = sorted(written + kept), []
    else:
        # A subscribed capability edited here is the set's, so it is replaced
        # like a policy document; one holding a version the set once shipped
        # is the set's too, only older.
        replace = [n for n in kept if n in edited] + earlier_deliveries(target, kept)
        for name in replace:
            if (SET_ROOT / name).is_file():
                (target / name).write_bytes((SET_ROOT / name).read_bytes())
        written, kept = sorted(set(written) | set(replace)), [n for n in kept if n not in replace]

    for name, blob in held.items():
        (target / name).write_bytes(blob)
    write_lock(target, removed=removed)
    # Only what was in fact replaced; a capability the set stopped shipping
    # stays, and saying it was replaced would hide the edit.
    edited = [
        n for n in edited
        if (SET_ROOT / n).is_file() and (target / n).is_file()
        and (target / n).read_bytes() == (SET_ROOT / n).read_bytes()
    ]

    return written, kept, before, set_version(target), sorted(held), edited, state is not None


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
    parser.add_argument("--upgrade", action="store_true",
                        help="refresh the set in a repository that already adopted it, "
                             "keeping every file that repository owns")
    parser.add_argument("--refresh-capabilities", action="store_true",
                        help="with --upgrade, also replace the agent definitions and skills "
                             "this repository changed itself, losing those changes; without it, "
                             "only the set's own earlier or subscribed versions are replaced")
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

    if args.upgrade:
        if not args.into:
            raise SystemExit("--upgrade needs --into: it refreshes another repository.")
        if target == SET_ROOT:
            raise SystemExit("--upgrade refreshes a repository that adopted the set, not the set itself.")
        if args.from_template:
            raise SystemExit("--upgrade and --from-template are different jobs; run one.")

        written, kept, before, after, had, edited, exact = upgrade(target, args.refresh_capabilities)
        print(f"[upgrade] {target}: {before} → {after}")
        for path in edited:
            print(f"[local] {path} was edited in this repository and has been replaced "
                  f"by the set's — read its diff before committing")
        if edited and exact:
            print(f"        [local] is exact here: {LOCK} recorded what the set delivered.")
            print("        Carry anything worth keeping into the project context's Local rules.")
        elif edited:
            print("        [local] cannot tell a local edit from a set change that never moved")
            print("        its version, nor see a local edit to a document the set has also")
            print("        bumped since. Read every flagged diff; an unflagged one may hide one too.")
        for path in had:
            print(f"[keep] {path} is this repository's; the set did not write over it")
        for path in written:
            print(f"[copy] {path}")
        print(f"[lock] {LOCK} records what this upgrade delivered; "
              "those files are now a subscribed copy")

        stale = stale_capabilities(target, kept)
        for path in stale:
            print(f"[stale] {path} differs from the set's and was left alone — "
                  f"this repository keeps running its own version")
        if stale:
            print("        --refresh-capabilities replaces them, losing those local changes.")

        # The report above has to be read before the result below. Piped, a
        # parent's buffer flushes at exit, after the child's output.
        print(flush=True)
        return subprocess.run(
            [sys.executable, str(target / ".ai" / "tools" / "check_policy_set.py"), str(target)],
            check=False,
        ).returncode

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
    if not (target / SET_HOME_MARKER).exists():
        write_lock(target, in_place=target == SET_ROOT)
        print(f"[lock] {LOCK} records what was delivered; those files are a subscribed copy")

    context = target / ".ai" / "PROJECT_CONTEXT.md"
    still_open = unanswered_facts(context.read_text(encoding="utf-8")) if context.exists() else []

    print(flush=True)
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
