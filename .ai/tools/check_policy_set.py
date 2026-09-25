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

import re
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

    def add(self, name: str, question: str, failures: list[str]) -> None:
        self.entries.append((name, question, failures))

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
        print()
        if self.failed:
            n = sum(len(f) for _, _, f in self.entries)
            print(f"{n} problem(s). Nothing here checks whether a rule is *right* —")
            print("only whether the set still says it in one place. See NOT VERIFIED")
            print("in the docstring of each check.")
        else:
            print("All structural checks passed.")


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
# NOT VERIFIED: whether the pointed-at section actually says what the pointer
# claims. A resolving reference can still be a wrong one.
# --------------------------------------------------------------------------
# Project capabilities the set ships and that travel, but that an adopting
# repository may not have: it can delete one, or never have taken it. Referring
# to one is therefore like referring to an instance file — resolved where the
# set lives, tolerated as absent where it does not. This is the same set-home
# distinction as SET_HOME_FILES, reached from the other direction.
TRAVELLING_DIRS = (
    ".claude/agents/", ".claude/skills/", ".codex/agents/", ".agents/skills/",
)


def resolve(ref: str, source: Path) -> tuple[Path | None, bool]:
    """Resolve a reference the way a reader would.

    Documents refer to siblings in short form — `CORE.md` from inside `.ai/`,
    `PROJECT_LESSONS.md` from inside `.ai/memory/`. Try the repository root, the
    referring document's own directory, and `.ai/`, in that order.

    Returns the resolved path (or None) and whether the reference names one of
    the per-project instance files, which do not exist in the set as shipped.
    """
    for candidate in (ROOT / ref, source.parent / ref, AI / ref):
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
        if as_rel.startswith(TRAVELLING_DIRS) and not at_set_home():
            return None, True
    return None, False


def check_references(report: Report) -> None:
    failures: list[str] = []
    docs = policy_docs()
    heading_cache: dict[Path, set[str]] = {}

    for path in docs:
        name = rel(path)
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
    report.print()
    return 1 if report.failed else 0


if __name__ == "__main__":
    sys.exit(main())
