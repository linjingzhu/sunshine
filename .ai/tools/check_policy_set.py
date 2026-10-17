#!/usr/bin/env python3
"""Structural checks on the policy set.

Each check below states the exact question it answers, and the report prints
that question beside the result. See `.ai/CORE.md` § The question each result
answers for why that matters more than the pass/fail.

These guards read structure — front matter, headings, references, paths — and
not prose, per LESSONS_FROM_PRACTICE.md entry 14. The one exception is the
portability denylist, which searches for proper nouns rather than for a rule,
and is opt-in per repository.

Python 3.11+ standard library only. Run from the repository root:

    python3 .ai/tools/check_policy_set.py [repository root]

The root defaults to the repository this file lives in; pass one to check a
copy, which is how `test_check_policy_set.py` proves each guard fails on the
defect it exists to catch.

Exit status is 0 when every check passes and 1 otherwise.
"""

from __future__ import annotations

import hashlib
import re
import subprocess
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
AI = ROOT / ".ai"

# Files that are allowed to know what the project is. Everything else in the
# set is written to survive being copied into an unrelated repository.
INSTANCE_PATHS = {
    ".ai/PROJECT_CONTEXT.md",
    ".ai/memory/PROJECT_LESSONS.md",
    # A roadmap names the features of one product, so it is an instance file
    # like the two above, not a policy document. The auto-dev skill writes it.
    ".ai/ROADMAP.md",
    # What this repository subscribed to, written by `adopt.py`. It records
    # one delivery, so it belongs to the repository that received it.
    ".ai/set.lock",
    # The set's home only: the repositories a release is sent to.
    ".ai/SUBSCRIBERS.md",
}
INSTANCE_DIRS = (".ai/reports/",)

# Files that exist only where the set itself lives, not in a repository that
# adopted it: adoption copies the policy and capabilities, not these files.
# In an adopting repository the root `README.md` is the adopter's own,
# names its product, and is not part of the set — so the checks read it, and
# resolve references to it, only at the set's home.
SET_HOME_FILES = ("README.md", "LESSONS_FROM_PRACTICE.md")

FRONT_MATTER_FIELDS = ("doc_id", "version", "canonical_path", "updated")
SEMVER = re.compile(r"^\d+\.\d+\.\d+$")
DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

# `path.md` § *Section name*  — the set's cross-reference form.
SECTION_REF = re.compile(r"`([A-Za-z0-9_./-]+\.md)`\s*§\s*\*([^*]+)\*")
# Backticked document and capability paths, including native Codex files.
PATH_REF = re.compile(r"`([A-Za-z0-9_./-]+\.(?:md|toml|yaml))`")
HEADING = re.compile(r"^(#{2,6})\s+(.+?)\s*$", re.M)


class Report:
    """Collects results, each labelled with the question its check asked."""

    def __init__(self) -> None:
        self.entries: list[tuple[str, str, list[str]]] = []
        self.skipped: list[tuple[str, str, str]] = []

    def add(self, name: str, question: str, failures: list[str]) -> None:
        self.entries.append((name, question, failures))

    def skip(self, name: str, question: str, reason: str) -> None:
        """A check that could not ask its question here. It prints with the
        reason and never as a pass: a pass for a question nobody asked is the
        failure `.ai/CORE.md` names."""
        self.skipped.append((name, question, reason))

    @property
    def failed(self) -> bool:
        return any(f for _, _, f in self.entries)

    def print(self) -> None:
        for name, question, failures in self.entries:
            status = "FAIL" if failures else "PASS"
            print(f"[{status}] {name}")
            print(f"        asks: {question}")
            for line in failures:
                print(f"        - {line}")
        for name, question, reason in self.skipped:
            print(f"[SKIP] {name}")
            print(f"        asks: {question}")
            print(f"        not asked: {reason}")
        print()
        if self.failed:
            n = sum(len(f) for _, _, f in self.entries)
            print(f"{n} problem(s). Nothing here checks whether a rule is *right* —")
            print("only whether the set still says it in one place. See NOT VERIFIED")
            print("in the docstring of each check.")
        else:
            print("All structural checks passed.")
        if self.skipped:
            print(f"{len(self.skipped)} check(s) not asked here — each is named above with why.")


def repo_files(pattern: str) -> list[Path]:
    return sorted(p for p in ROOT.glob(pattern) if ".git/" not in str(p))


def at_set_home() -> bool:
    """True where the set itself lives; false in a repository that adopted it."""
    return (ROOT / "LESSONS_FROM_PRACTICE.md").exists()


def policy_docs() -> list[Path]:
    """The policy, harness entry points and committed capability definitions,
    plus the set-home files where the set itself lives.

    The capability definitions are in this list for their references. An agent
    definition or a skill is mostly pointers into `.ai/`, and a pointer nothing
    resolves is a pointer that rots between releases.
    """
    docs = [ROOT / name for name in ("CLAUDE.md", "AGENTS.md") if (ROOT / name).exists()]
    if at_set_home():
        docs += [ROOT / name for name in SET_HOME_FILES if (ROOT / name).exists()]
    for pattern in (
        ".ai/**/*.md", ".claude/**/*.md", ".agents/skills/**/*.md",
        ".agents/skills/**/agents/openai.yaml", ".codex/agents/*.toml",
    ):
        docs += repo_files(pattern)
    return sorted(set(docs))


def rel(p: Path) -> str:
    return p.relative_to(ROOT).as_posix()


def is_instance(path: str) -> bool:
    return path in INSTANCE_PATHS or path.startswith(INSTANCE_DIRS)


def parse_front_matter(text: str) -> dict[str, str] | None:
    if not text.startswith("---\n"):
        return None
    end = text.find("\n---\n", 4)
    if end == -1:
        return None
    fields = {}
    for line in text[4:end].splitlines():
        if ":" in line:
            key, _, value = line.partition(":")
            fields[key.strip()] = value.strip()
    return fields


def strip_code_fences(text: str) -> str:
    """Blank out fenced blocks, keeping line numbering intact.

    A `##` inside a fence is an example of a heading, not a heading, and the
    format template in the changelog is written as one. Scanning the raw text
    reads those examples as real structure.
    """
    out, fenced = [], False
    for line in text.splitlines(keepends=True):
        if line.lstrip().startswith("```"):
            fenced = not fenced
            out.append("\n")
            continue
        out.append("\n" if fenced else line)
    return "".join(out)


def headings_of(text: str) -> set[str]:
    return {m.group(2).strip().lower() for m in HEADING.finditer(strip_code_fences(text))}


# --------------------------------------------------------------------------
# Check 1 — front matter
#
# Question: does every policy document carry the four fields `CHANGELOG.md` §
# Document versioning requires, addressed by an id nothing else claims?
#
# NOT VERIFIED: whether a version number was bumped correctly. Policy impact is
# a judgement no script can make; this only checks the field is well-formed.
# --------------------------------------------------------------------------
def check_front_matter(report: Report) -> None:
    failures: list[str] = []
    seen_ids: dict[str, str] = {}

    for path in repo_files(".ai/**/*.md"):
        name = rel(path)
        if is_instance(name):
            continue
        fields = parse_front_matter(path.read_text(encoding="utf-8"))
        if fields is None:
            failures.append(f"{name}: no front matter block")
            continue

        for field in FRONT_MATTER_FIELDS:
            if not fields.get(field):
                failures.append(f"{name}: missing `{field}`")

        version = fields.get("version", "")
        if version and not SEMVER.match(version):
            failures.append(f"{name}: version `{version}` is not MAJOR.MINOR.PATCH")

        updated = fields.get("updated", "")
        if updated and not DATE.match(updated):
            failures.append(f"{name}: updated `{updated}` is not YYYY-MM-DD")

        doc_id = fields.get("doc_id", "")
        if doc_id:
            if doc_id in seen_ids:
                failures.append(f"{name}: doc_id `{doc_id}` also claimed by {seen_ids[doc_id]}")
            else:
                seen_ids[doc_id] = name

        # A template is addressed by the path of the instance it produces.
        expected = name.replace(".template.md", ".md")
        canonical = fields.get("canonical_path", "")
        if canonical and canonical != expected:
            failures.append(f"{name}: canonical_path is `{canonical}`, expected `{expected}`")

    report.add(
        "front matter",
        "does every policy document carry the four required fields, with a "
        "unique doc_id and a canonical_path that matches where it lives?",
        failures,
    )


# --------------------------------------------------------------------------
# Check 2 — cross-references
#
# Question: does every `file.md` and every `file.md` § *Section* reference
# point at something that exists?
#
# Run reports under `.ai/reports/` are not read. A report records what was true
# when it was written; a file it named may since have moved or gone, and the
# only way to make that pointer resolve would be to rewrite the record. Until
# 3.4.2 they were excused by accident, through a guess beside the report that
# landed inside the instance folder; they are now excluded on purpose.
#
# NOT VERIFIED: whether the pointed-at section actually says what the pointer
# claims. A resolving reference can still be a wrong one.
# --------------------------------------------------------------------------
# Project capabilities the set ships and that travel, but that an adopting
# repository may not have: it can delete one, or never have taken it. Referring
# to one is therefore like referring to an instance file — resolved where the
# set lives, tolerated where it does not. This is the same set-home distinction
# as SET_HOME_FILES, reached from the other direction.
#
# In a subscriber the lock says which capabilities were delivered, so the
# tolerance is exact there: a reference into a capability folder is excused
# only when it names a capability the repository removed — one the lock
# records as removed, or lists as delivered and is now gone — or one the lock
# records as kept, because the repository holds its own in that place.
# Anything else that does not resolve is a broken pointer, as at the set's
# home.
#
# Without a lock, a repository adopted before 4.0.0, nothing tells a removed
# capability from one that never existed, and every reference into a
# capability folder is still excused. That blind spot closes at its next
# upgrade, which writes the lock. A pointer written *inside* a capability is
# checked either way; see `resolve()`.
TRAVELLING_DIRS = (
    ".claude/agents/", ".claude/skills/", ".codex/agents/", ".agents/skills/",
)


def removed_capability(path: str) -> bool:
    """Whether `path` names a capability the set ships and this repository does
    not hold as the set's: one it removed, or one in a place it keeps its own.
    Either is its choice, and leaves the set's pointers to it dangling. True
    for every path where no lock says what was delivered."""
    lock = ROOT / LOCK
    if not lock.is_file():
        return True
    _, entries, marks, _ = read_lock(lock.read_text(encoding="utf-8"))
    return path in marks or (path in entries and not (ROOT / path).exists())


def resolve(ref: str, source: Path) -> tuple[Path | None, bool]:
    """Resolve a reference the way a reader would.

    Documents refer to siblings in short form — `CORE.md` from inside `.ai/`,
    `PROJECT_LESSONS.md` from inside `.ai/memory/`. Try the repository root, the
    referring document's own directory, and `.ai/`, in that order.

    The second is tried only for a reference written relative to its document:
    a bare name, or one starting `./` or `../`. A reference that names its own
    directory, like `.ai/CORE.md`, means that directory. Guessing it relative to
    the referring file invents a path inside that file's own folder — and inside
    a capability folder, which an adopter may lack, the invented path is
    tolerated, hiding every dangling pointer the capability contains.

    For the same reason, a guess beside a document that itself lives in a
    capability folder is never excused as an absent capability: the folder is
    evidently there, so a missing neighbour is a broken pointer.

    Returns the resolved path (or None) and whether the reference names one of
    the per-project instance files, which do not exist in the set as shipped.
    """
    in_capability = rel(source).startswith(TRAVELLING_DIRS)
    candidates = [(ROOT / ref, False)]
    if "/" not in ref or ref.startswith(("./", "../")):
        candidates.append((source.parent / ref, in_capability))
    candidates.append((AI / ref, False))
    for candidate, beside_capability in candidates:
        try:
            as_rel = candidate.resolve().relative_to(ROOT).as_posix()
        except ValueError:
            continue
        # A pointer at the set's home files from inside an adopting
        # repository: the target is the set's, not the adopter's file of the
        # same name (its README), so it is neither resolved nor reported.
        if as_rel in SET_HOME_FILES and not at_set_home():
            return None, True
        if candidate.exists():
            return candidate, False
        if is_instance(as_rel):
            return None, True
        if (as_rel.startswith(TRAVELLING_DIRS) and not at_set_home()
                and not beside_capability and removed_capability(as_rel)):
            return None, True
    return None, False


def check_references(report: Report) -> None:
    failures: list[str] = []
    docs = policy_docs()
    heading_cache: dict[Path, set[str]] = {}

    for path in docs:
        name = rel(path)
        if name.startswith(INSTANCE_DIRS):
            continue  # a record, not a pointer that must stay current
        text = path.read_text(encoding="utf-8")

        for match in PATH_REF.finditer(text):
            target = match.group(1)
            resolved, instance = resolve(target, path)
            if resolved is None and not instance:
                failures.append(f"{name}: references `{target}`, which does not exist")

        for match in SECTION_REF.finditer(text):
            target, section = match.group(1), re.sub(r"\s+", " ", match.group(2)).strip().lower()
            resolved, instance = resolve(target, path)
            if resolved is None:
                if not instance:
                    failures.append(f"{name}: § reference into missing file `{target}`")
                continue
            if resolved not in heading_cache:
                heading_cache[resolved] = headings_of(resolved.read_text(encoding="utf-8"))
            if section not in heading_cache[resolved]:
                failures.append(f"{name}: `{target}` has no section *{match.group(2)}*")

    report.add(
        "cross-references",
        "does every referenced file and every `file § *Section*` pointer "
        "resolve to something that exists?",
        failures,
    )


# --------------------------------------------------------------------------
# Check 3 — one owner per heading
#
# Question: is any section heading claimed by two policy documents?
#
# This is the structural proxy for "each rule is stated in exactly one file".
# Re-duplicating a rule almost always means re-adding its heading somewhere.
#
# NOT VERIFIED: prose that restates another file's rule *without* reusing its
# heading. Nothing here detects a pointer that grew back into a summary; that
# stays a convention, enforced by review.
# --------------------------------------------------------------------------
def check_heading_ownership(report: Report) -> None:
    owners: dict[str, list[str]] = {}
    for path in repo_files(".ai/**/*.md"):
        name = rel(path)
        if is_instance(name):
            continue
        for heading in headings_of(path.read_text(encoding="utf-8")):
            owners.setdefault(heading, []).append(name)

    failures = [
        f"*{heading}* is claimed by {', '.join(sorted(files))}"
        for heading, files in sorted(owners.items())
        if len(set(files)) > 1
    ]
    report.add(
        "one owner per heading",
        "is any section heading claimed by two policy documents?",
        failures,
    )


# --------------------------------------------------------------------------
# Check 4 — portability denylist
#
# Question: does any term the repository has declared project-specific appear
# outside the files allowed to know what the project is?
#
# This is the one guard here that reads words rather than structure. It is
# limited to proper nouns a human listed on purpose — the "refuse a second
# spelling" check of LESSONS_FROM_PRACTICE.md entry 6 — and not to rules.
#
# NOT VERIFIED: project-specific facts that use no denylisted word. An empty
# denylist makes this check vacuous, and it says so rather than passing quietly.
# --------------------------------------------------------------------------
def check_portability(report: Report) -> None:
    denylist_path = AI / "tools" / "portability-denylist.txt"
    failures: list[str] = []

    if not denylist_path.exists():
        report.add(
            "portability",
            "does any project-specific term appear outside the instance files?",
            [f"{rel(denylist_path)} is missing"],
        )
        return

    terms = [
        line.strip()
        for line in denylist_path.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]
    if not terms:
        print("[note] portability denylist is empty; that check proves nothing.")

    patterns = [(t, re.compile(rf"\b{re.escape(t)}\b", re.I)) for t in terms]
    for path in policy_docs():
        name = rel(path)
        if is_instance(name) or name == rel(denylist_path):
            continue
        text = path.read_text(encoding="utf-8")
        for term, pattern in patterns:
            hits = len(pattern.findall(text))
            if hits:
                failures.append(f"{name}: {hits}x `{term}`")

    report.add(
        "portability",
        f"does any of the {len(terms)} declared project-specific terms appear "
        "outside the files allowed to know what the project is?",
        failures,
    )


# --------------------------------------------------------------------------
# Check 5 — changelog
#
# Question: does every release entry carry a semantic version, an ISO date and
# at least one improvement, newest first and each version recorded once?
#
# The three fields are mandatory because an entry that records a version and a
# date but not what changed is a result reported without the question it
# answers — the failure the whole set exists to prevent.
#
# NOT VERIFIED: whether the version level matches the change's actual policy
# impact, and whether the improvements listed are the ones that shipped. Both
# are judgements; this checks the entry is complete and ordered.
# --------------------------------------------------------------------------
# Every level-2 heading in the changelog is a release entry except these. A
# heading that does not parse is reported, never skipped: a malformed entry
# that simply vanishes from the scan is a check passing a question it was
# never asked.
NON_RELEASE_HEADINGS = {"format", "document versioning", "set version"}
LEVEL_2 = re.compile(r"^##\s+(.+?)\s*$", re.M)
RELEASE_TITLE = re.compile(r"^(\S+)\s+—\s+(.+)$")


def check_changelog(report: Report) -> None:
    path = AI / "CHANGELOG.md"
    failures: list[str] = []

    if not path.exists():
        report.add(
            "changelog",
            "does every release entry carry a version, a date and at least one improvement?",
            [f"{rel(path)} is missing"],
        )
        return

    text = strip_code_fences(path.read_text(encoding="utf-8"))
    headings = [m for m in LEVEL_2.finditer(text) if m.group(1).strip().lower() not in NON_RELEASE_HEADINGS]
    if not headings:
        failures.append("no release entries — expected `## MAJOR.MINOR.PATCH — YYYY-MM-DD`")

    seen: set[str] = set()
    previous: tuple[int, int, int] | None = None
    previous_date: str | None = None

    for index, match in enumerate(headings):
        title = match.group(1).strip()
        parsed = RELEASE_TITLE.match(title)
        if not parsed:
            failures.append(f"entry `{title}`: does not read as `VERSION — DATE`")
            continue

        version, date = parsed.group(1), parsed.group(2).strip()
        label = f"entry `{version}`"

        if not SEMVER.match(version):
            failures.append(f"{label}: version is not MAJOR.MINOR.PATCH")
        if not DATE.match(date):
            failures.append(f"{label}: date `{date}` is not YYYY-MM-DD")

        if version in seen:
            failures.append(f"{label}: recorded more than once")
        seen.add(version)

        # Improvements: bullet lines in the body before the next entry.
        end = headings[index + 1].start() if index + 1 < len(headings) else len(text)
        if not re.search(r"^\s*[-*]\s+\S", text[match.end() : end], re.M):
            failures.append(f"{label}: no improvements listed")

        if SEMVER.match(version):
            parts = tuple(int(p) for p in version.split("."))
            if previous is not None and parts >= previous:
                failures.append(f"{label}: not below the entry above it — newest goes first")
            previous = parts  # type: ignore[assignment]

        if DATE.match(date):
            if previous_date is not None and date > previous_date:
                failures.append(f"{label}: dated after the entry above it")
            previous_date = date

    report.add(
        "changelog",
        f"do all {len(headings)} release entries carry a version, a date and at "
        "least one improvement, newest first and each version recorded once?",
        failures,
    )


# --------------------------------------------------------------------------
# Check 6 — project context
#
# Question: does the filled-in `.ai/PROJECT_CONTEXT.md` carry every fact the
# set reads by name — one `key: value` line each, inside a fenced block — with
# no `<placeholder>` left in and no line copied from the template's own
# instructions? Where no instance exists (the set as shipped), does the
# template still declare every key, so an adopter cannot inherit a set that
# has quietly lost one?
#
# The keys are the facts other documents read by name: REPOSITORY.md reads
# `merge_deploys`, UX.md runs `runtime_gate`, CORE.md and EXECUTION.md read
# `generated`, `external_scripts` and `public_ids`, REPORTING.md reads
# `owner_ledger`. A missing key means a rule somewhere is reading nothing and
# passing.
#
# NOT VERIFIED: whether the values are true — whether `test_command` runs the
# tests, whether `generated` lists every artefact. A value is present or it is
# not; what it does is answered by running it.
# --------------------------------------------------------------------------
REQUIRED_CONTEXT_KEYS = (
    "repository_mode",
    "base_branch",
    "merge_deploys",
    "runtime_gate",
    "test_command",
    "lint_command",
    "build_command",
    "generated",
    "external_scripts",
    "public_ids",
    "owner_ledger",
)
CONTEXT_ENUMS = {
    "repository_mode": {"auto", "personal", "protected"},
    "merge_deploys": {"yes", "no"},
}
PLACEHOLDER = re.compile(r"<[^>]+>")
TEMPLATE_MARKERS = ("This is a template", "delete every instruction line")
KEY_LINE = re.compile(r"^([a-z_]+):\s*(.*)$")


def fenced_key_lines(text: str) -> dict[str, list[str]]:
    """`key: value` lines inside fenced blocks, keyed, all occurrences kept."""
    found: dict[str, list[str]] = {}
    fenced = False
    for line in text.splitlines():
        if line.lstrip().startswith("```"):
            fenced = not fenced
            continue
        if not fenced:
            continue
        m = KEY_LINE.match(line.strip())
        if m:
            found.setdefault(m.group(1), []).append(m.group(2).strip())
    return found


def check_project_context(report: Report) -> None:
    instance = AI / "PROJECT_CONTEXT.md"
    template = AI / "PROJECT_CONTEXT.template.md"
    failures: list[str] = []

    # The template must declare every key, instance or not: it is where an
    # adopter's instance comes from.
    if not template.exists():
        failures.append(f"{rel(template)} is missing")
    else:
        declared = fenced_key_lines(template.read_text(encoding="utf-8"))
        for key in REQUIRED_CONTEXT_KEYS:
            if key not in declared:
                failures.append(f"{rel(template)}: does not declare `{key}`")

    if not instance.exists():
        report.add(
            "project context",
            "no instance here (the set as shipped) — does the template still "
            f"declare all {len(REQUIRED_CONTEXT_KEYS)} facts a run reads by name?",
            failures,
        )
        return

    text = instance.read_text(encoding="utf-8")
    name = rel(instance)
    for marker in TEMPLATE_MARKERS:
        if marker in text:
            failures.append(f"{name}: still carries the template line `{marker}`")

    values = fenced_key_lines(text)
    for key in REQUIRED_CONTEXT_KEYS:
        got = values.get(key, [])
        if not got:
            failures.append(f"{name}: missing `{key}`")
            continue
        if len(got) > 1:
            failures.append(f"{name}: `{key}` is set {len(got)} times")
        value = got[0]
        if not value:
            failures.append(f"{name}: `{key}` has no value (`none` is a value)")
        elif PLACEHOLDER.search(value):
            failures.append(f"{name}: `{key}` still holds a placeholder: {value}")
        elif key in CONTEXT_ENUMS and value not in CONTEXT_ENUMS[key]:
            allowed = " | ".join(sorted(CONTEXT_ENUMS[key]))
            failures.append(f"{name}: `{key}` is `{value}`, expected one of {allowed}")

    report.add(
        "project context",
        f"does {name} carry all {len(REQUIRED_CONTEXT_KEYS)} facts the set reads "
        "by name, with no placeholder or template line left?",
        failures,
    )


# --------------------------------------------------------------------------
# Check 7 — capability definitions
#
# Question: does every committed capability — an agent definition, a skill —
# carry the two fields a harness needs to offer it: a `name` that can be
# written down, and a `description` that says when to reach for it, with the
# name matching where it lives?
#
# A Mission Packet names an agent (`.ai/HARNESS.md` § Tools a Mission Packet
# may assume) and a run invokes a skill by name. Either one declaring a
# different name, or none, asks for something the harness will not find. The
# two differ only in where the name must match: an agent is its file, a skill
# is its directory.
#
# NOT VERIFIED: whether the agent or skill is any good, whether its tool list
# is right, or whether the description triggers it at the moment it should.
# Those are answered by using it, not by reading it.
# --------------------------------------------------------------------------
AGENTS_DIR = Path(".claude/agents")
SKILLS_DIR = Path(".claude/skills")
CODEX_AGENTS_DIR = Path(".codex/agents")
CODEX_SKILLS_DIR = Path(".agents/skills")
CAPABILITY_DIRS = (AGENTS_DIR, SKILLS_DIR, CODEX_AGENTS_DIR, CODEX_SKILLS_DIR)
CAPABILITY_FIELDS = ("name", "description")


def capability_definitions() -> list[tuple[Path, str]]:
    """Every committed capability, paired with the name its front matter must
    declare: an agent definition is named by its file, a skill by its folder."""
    found = [(p, p.stem) for p in sorted((ROOT / AGENTS_DIR).glob("*.md"))]
    found += [(p, p.stem) for p in sorted((ROOT / CODEX_AGENTS_DIR).glob("*.toml"))]
    for directory in (SKILLS_DIR, CODEX_SKILLS_DIR):
        found += [(p, p.parent.name) for p in sorted((ROOT / directory).glob("*/SKILL.md"))]
    return found


def check_capability_definitions(report: Report) -> None:
    present = [d for d in CAPABILITY_DIRS if (ROOT / d).is_dir()]
    failures: list[str] = []

    if at_set_home():
        for directory in CAPABILITY_DIRS:
            if directory not in present:
                failures.append(
                    f"{directory.as_posix()} is missing, but the set ships the capabilities "
                    "`.ai/HARNESS.md` points at"
                )
        if not (ROOT / "AGENTS.md").is_file():
            failures.append("AGENTS.md is missing, but the set ships the Codex entry point")

    if not present:
        report.add(
            "capability definitions",
            "does the set still ship the capabilities it names?" if at_set_home()
            else "no Claude or Codex capabilities in this repository — nothing to check",
            failures,
        )
        return

    definitions = capability_definitions()
    for directory in present:
        if not any(path.is_relative_to(ROOT / directory) for path, _ in definitions):
            # A skill folder with no SKILL.md is the shape this catches: the
            # harness lists nothing, and the run that named it gets no error.
            failures.append(f"{directory.as_posix()} exists but ships no definition")

    for path, expected in definitions:
        name = rel(path)
        text = path.read_text(encoding="utf-8")
        if path.suffix == ".toml":
            try:
                fields = tomllib.loads(text)
            except tomllib.TOMLDecodeError as exc:
                failures.append(f"{name}: invalid TOML: {exc}")
                continue
            required = (*CAPABILITY_FIELDS, "developer_instructions")
            for field in ("model", "model_reasoning_effort", "sandbox_mode"):
                if field in fields and (not isinstance(fields[field], str) or not fields[field].strip()):
                    failures.append(f"{name}: `{field}` must be a non-empty string")
            if "sandbox_mode" in fields and fields["sandbox_mode"] not in (
                "read-only", "workspace-write", "danger-full-access",
            ):
                failures.append(f"{name}: invalid `sandbox_mode`")
        else:
            fields = parse_front_matter(text)
            if fields is None:
                failures.append(f"{name}: no front matter block")
                continue
            required = CAPABILITY_FIELDS
        for field in required:
            if field not in fields:
                failures.append(f"{name}: missing `{field}`")
            elif not isinstance(fields[field], str) or not fields[field].strip():
                failures.append(f"{name}: `{field}` must be a non-empty string")
        declared = fields.get("name", "")
        if declared and declared != expected:
            failures.append(
                f"{name}: declares `{declared}`, so anything naming "
                f"`{expected}` would not find it"
            )

    report.add(
        "capability definitions",
        f"do all {len(definitions)} capability definitions carry a name "
        "matching where they live, and a description saying when to use them?",
        failures,
    )


# --------------------------------------------------------------------------
# Check 8 — document versions
#
# Question: has every policy document whose text changed since the previous
# release been bumped, and bumped exactly once?
#
# `.ai/CHANGELOG.md` § Document versioning is the rule: one bump per release,
# sized by policy impact. The previous release is the oldest commit, walking
# first parents back from HEAD, in which its entry stood at the top of the
# changelog, with merges read as `previous_release_commit()` describes. Every
# commit of the
# release being made, before its entry was written or after, is compared with
# that one state, so a committed change is caught exactly as one still in the
# working tree is. `previous_release_commit()` is the detail.
#
# The changelog is compared without its release entries. They grow every
# release; its version describes its rules, not its record.
#
# Asked only at the set's home. An adopter cannot fix the set's history, and
# its commits are not the set's releases.
#
# NOT VERIFIED: whether the level matches the change's policy impact, which is
# a judgement, and anything before the previous release. A change committed
# without a release entry is counted in the next release that records one.
# --------------------------------------------------------------------------
VERSIONS_QUESTION = (
    "has every policy document whose text changed since the previous release "
    "been bumped, exactly once?"
)


def release_versions(text: str) -> list[str]:
    """Release versions in the order the changelog lists them, newest first."""
    versions = []
    for match in LEVEL_2.finditer(strip_code_fences(text)):
        title = match.group(1).strip()
        if title.lower() in NON_RELEASE_HEADINGS:
            continue
        parsed = RELEASE_TITLE.match(title)
        if parsed and SEMVER.match(parsed.group(1)):
            versions.append(parsed.group(1))
    return versions


def semver(version: str) -> tuple[int, int, int]:
    major, minor, patch = (int(n) for n in version.split("."))
    return major, minor, patch


def one_bump_from(version: str) -> set[tuple[int, int, int]]:
    major, minor, patch = semver(version)
    return {(major + 1, 0, 0), (major, minor + 1, 0), (major, minor, patch + 1)}


def comparable_text(name: str, text: str) -> str:
    """What a document's version describes: its body without front matter,
    and for the changelog, without its release entries."""
    if text.startswith("---\n"):
        end = text.find("\n---\n", 4)
        if end != -1:
            text = text[end + 5 :]
    if name != ".ai/CHANGELOG.md":
        return text
    kept, in_entry, fenced = [], False, False
    for line in text.splitlines(keepends=True):
        if line.lstrip().startswith("```"):
            fenced = not fenced
        if not fenced and line.startswith("## "):
            parsed = RELEASE_TITLE.match(line[3:].strip())
            in_entry = bool(parsed and SEMVER.match(parsed.group(1)))
        if not in_entry:
            kept.append(line)
    return "".join(kept)


def git(*args: str) -> str | None:
    try:
        result = subprocess.run(
            ["git", "-C", str(ROOT), *args],
            capture_output=True, text=True, encoding="utf-8", check=False,
        )
    except OSError:
        return None
    return result.stdout if result.returncode == 0 else None


def previous_release_commit() -> tuple[str | None, str]:
    """The commit holding the previous release and that release's version, or
    None and the reason there is nothing to compare with.

    Walk first parents back from HEAD over the commits that changed the
    changelog, and take the oldest commit of the run that has the previous
    release on top: every commit of a release, before its entry or after,
    is then held to one bump.

    A merge complicates that, because the run can reach a release through a
    merge from another side. When the merge's `.ai/` equals that side's, the two
    readings agree and the merge is taken. When they differ, the merge is
    either the release landing on the base branch, so the merge is the
    release, or a branch already at work taking the release in, so the merge
    also holds that work and the release is the other side. Only the base
    branch tells them apart. It is read from `origin/HEAD`, and without it
    the check says it cannot tell rather than guess. A release on top on
    more than one side of a merge is reported the same way.
    """
    top = git("rev-parse", "--show-toplevel")
    if top is None or Path(top.strip()).resolve() != ROOT.resolve():
        return None, "this tree is not a git repository of its own, so it holds no previous release"
    if (git("rev-parse", "--is-shallow-repository") or "").strip() == "true":
        return None, "a shallow clone may have cut the previous release off; fetch the full history"

    path = AI / "CHANGELOG.md"
    versions = release_versions(path.read_text(encoding="utf-8")) if path.exists() else []
    if len(versions) < 2:
        return None, "the changelog records fewer than two releases"
    previous = versions[1]

    tops: dict[str, str | None] = {}

    def on_top(commit: str) -> str | None:
        if commit not in tops:
            shown = git("show", f"{commit}:.ai/CHANGELOG.md")
            found = release_versions(shown) if shown is not None else []
            tops[commit] = found[0] if found else None
        return tops[commit]

    base_ref = (git("rev-parse", "--verify", "-q", "refs/remotes/origin/HEAD") or "").strip()
    base_line = set((git("rev-list", "--first-parent", base_ref) or "").split()) if base_ref else set()

    class Undecidable(Exception):
        pass

    def walk(start: str) -> str | None:
        found = None
        log = git("log", "--first-parent", "--format=%H", start, "--", ".ai/CHANGELOG.md") or ""
        for commit in log.split():
            top_here = on_top(commit)
            first, *others = (git("show", "-s", "--format=%P", commit) or "").split() or [""]
            first_has_it = bool(first) and on_top(first) == previous
            merged_in = [parent for parent in others if on_top(parent) == previous]
            if len(merged_in) > 1 or (merged_in and first_has_it and top_here != previous):
                raise Undecidable(f"release {previous} stands on top on more than one side of merge {commit[:7]}")
            if top_here is not None and top_here != previous and semver(top_here) > semver(previous):
                if found is not None:
                    break
                if merged_in:
                    return walk(merged_in[0])
                continue
            if top_here != previous:
                break
            if merged_in and not first_has_it:
                side = merged_in[0]
                if git("diff", "--quiet", side, commit, "--", ".ai") is not None or commit in base_line:
                    return commit
                if base_ref and first and git("merge-base", "--is-ancestor", base_ref, first) is not None:
                    raise Undecidable(
                        f"merge {commit[:7]} brought release {previous} in on a line `origin/HEAD` has "
                        "not reached yet; fetch, or push the base branch, so that it can tell"
                    )
                if not base_ref:
                    raise Undecidable(
                        f"merge {commit[:7]} brought release {previous} in and changed `.ai/` beyond it; "
                        "whether it is the release or a branch taking it in depends on the base branch, "
                        "which `origin/HEAD` would name (git remote set-head origin --auto)"
                    )
                return walk(side)
            found = commit
        return found

    try:
        base = walk("HEAD")
    except Undecidable as reason:
        return None, str(reason)
    if base is None:
        return None, f"release {previous} never stood at the top of the changelog in this history"
    return base, previous


def check_document_versions(report: Report) -> None:
    if not at_set_home():
        report.skip(
            "document versions", VERSIONS_QUESTION,
            "asked only where the set lives; an adopter cannot fix the set's history",
        )
        return
    base, previous = previous_release_commit()
    if base is None:
        report.skip("document versions", VERSIONS_QUESTION, previous)
        return

    failures: list[str] = []
    changed = 0
    for path in repo_files(".ai/**/*.md"):
        name = rel(path)
        if is_instance(name):
            continue
        before = git("show", f"{base}:{name}")
        if before is None:
            continue  # new since the previous release: any version is its first
        now = path.read_text(encoding="utf-8")
        if comparable_text(name, before) == comparable_text(name, now):
            continue
        changed += 1
        old = (parse_front_matter(before) or {}).get("version", "")
        new = (parse_front_matter(now) or {}).get("version", "")
        if not (SEMVER.match(old) and SEMVER.match(new)):
            continue  # a malformed version is check 1's to report
        if semver(new) == semver(old):
            failures.append(f"{name}: text changed since {previous}, version still {new}")
        elif semver(new) < semver(old):
            failures.append(f"{name}: version went backwards since {previous}, {old} → {new}")
        elif semver(new) not in one_bump_from(old):
            failures.append(
                f"{name}: {old} → {new} since {previous} is more than one bump — "
                "a release bumps a document once, at the level its largest change earns"
            )

    report.add(
        "document versions",
        f"has each of the {changed} policy documents whose text changed since "
        f"release {previous} been bumped, exactly once?",
        failures,
    )


# --------------------------------------------------------------------------
# Check 9 — subscribed copy
#
# Question: does every file the subscription lock names still hold what the
# set delivered?
#
# An adopting repository does not own the set's files; it subscribes to them.
# `adopt.py` writes `.ai/set.lock`, a digest of each file it delivered, and the
# next upgrade replaces them all. An edit made here is therefore lost on the
# next release, and until then it is a rule that exists in one repository
# while claiming to be the set's. The place for a rule only this repository
# needs is its project context, `.ai/PROJECT_CONTEXT.template.md` § *Local rules*.
#
# A capability the repository removed is not a failure: removing one is the
# adopter's choice (`.ai/HARNESS.md` § *Where harness configuration belongs*).
# A removed policy document is, because the documents point at each other.
#
# Asked only where a lock exists. The set's home is what others subscribe to,
# and a repository adopted before 4.0.0 has no lock until its next upgrade.
#
# NOT VERIFIED: files the lock does not name. A document added to `.ai/` here
# is not reported, and a capability the adopter already had is its own.
# --------------------------------------------------------------------------
LOCK = ".ai/set.lock"
LOCK_HEADER = ("source", "version", "commit")
LOCK_ENTRY = re.compile(r"^([0-9a-f]{64})  (\S.*)$")
SUBSCRIPTION_QUESTION = (
    "does every file the subscription lock names still hold what the set delivered?"
)


def digest(data: bytes) -> str:
    """The content a file holds wherever it is checked out. Line endings are
    normalised first, so a Windows checkout of an untouched file is not an
    edit."""
    return hashlib.sha256(data.replace(b"\r\n", b"\n")).hexdigest()


LOCK_MARKS = ("removed", "kept")


def read_lock(text: str) -> tuple[dict[str, str], dict[str, str], dict[str, str], list[str]]:
    """Returns the header fields, the digest of each delivered path, the
    capabilities the set ships but did not deliver here, and the lines that
    are none of these.

    The third maps a path to why it was not delivered: `removed` when the
    repository took out a capability it had been given, `kept` when it holds
    its own in that place. Both outlive the upgrade that first saw them."""
    header: dict[str, str] = {}
    entries: dict[str, str] = {}
    marks: dict[str, str] = {}
    problems: list[str] = []
    for number, line in enumerate(text.splitlines(), 1):
        if not line.strip() or line.startswith("#"):
            continue
        entry = LOCK_ENTRY.match(line)
        field = KEY_LINE.match(line)
        if entry or (field and field.group(1) in LOCK_MARKS):
            name = entry.group(2) if entry else field.group(2).strip()
            if name in entries or name in marks:
                problems.append(f"line {number} lists `{name}` a second time")
            elif entry:
                entries[name] = entry.group(1)
            else:
                marks[name] = field.group(1)
        elif field and field.group(1) in LOCK_HEADER:
            header[field.group(1)] = field.group(2).strip()
        else:
            problems.append(
                f"line {number} is neither a header field, `<sha256>  <path>`, "
                f"`removed: <path>` nor `kept: <path>`: {line}"
            )
    return header, entries, marks, problems


def removable(name: str) -> bool:
    """A capability, which an adopter may remove; not a policy document."""
    return not (name == "CLAUDE.md" or name.startswith(".ai/"))


def check_subscription(report: Report) -> None:
    if at_set_home():
        report.skip(
            "subscribed copy", SUBSCRIPTION_QUESTION,
            "asked only in a repository that subscribes to the set; this is the set itself",
        )
        return
    lock = ROOT / LOCK
    if not lock.is_file():
        report.skip(
            "subscribed copy", SUBSCRIPTION_QUESTION,
            f"no `{LOCK}`: the set was adopted here before 4.0.0 made adoption a "
            "subscription. `adopt.py --upgrade`, run from the set's home, writes one",
        )
        return

    header, entries, marks, problems = read_lock(lock.read_text(encoding="utf-8"))
    failures = [f"{LOCK}: {p}" for p in problems]
    failures += [f"{LOCK}: no `{key}:` line" for key in LOCK_HEADER if not header.get(key)]
    if not entries:
        failures.append(f"{LOCK}: names no file")

    removed = 0
    for name, mark in sorted(marks.items()):
        if is_instance(name) or ".." in Path(name).parts or Path(name).is_absolute():
            failures.append(f"{LOCK}: records `{name}` as {mark}, which the set never delivers")
        elif not removable(name):
            failures.append(f"{LOCK}: records `{name}` as {mark}, but only a capability may be")
        elif mark == "removed" and not (ROOT / name).exists():
            removed += 1
    for name, want in sorted(entries.items()):
        path = ROOT / name
        if is_instance(name) or ".." in Path(name).parts or Path(name).is_absolute():
            failures.append(f"{LOCK}: names `{name}`, which the set never delivers")
            continue
        if not path.is_file():
            if removable(name):
                removed += 1
            else:
                failures.append(f"{name}: removed here, but the set's documents point at it")
            continue
        if digest(path.read_bytes()) != want:
            failures.append(
                f"{name}: edited here. The set's files are a subscribed copy, replaced "
                "on every upgrade — make the change at the set's home, or write the "
                "rule this repository needs in its project context, under Local rules"
            )

    kept = f", {removed} removed capabilities excused" if removed else ""
    report.add(
        "subscribed copy",
        f"do the {len(entries)} files {LOCK} names, delivered as set "
        f"{header.get('version', '?')}, still hold what the set delivered{kept}?",
        failures,
    )


def main(argv: list[str] | None = None) -> int:
    global ROOT, AI
    argv = sys.argv[1:] if argv is None else argv
    if argv:
        ROOT = Path(argv[0]).resolve()
        AI = ROOT / ".ai"

    report = Report()
    check_front_matter(report)
    check_references(report)
    check_heading_ownership(report)
    check_portability(report)
    check_changelog(report)
    check_capability_definitions(report)
    check_project_context(report)
    check_document_versions(report)
    check_subscription(report)
    report.print()
    return 1 if report.failed else 0


if __name__ == "__main__":
    sys.exit(main())
