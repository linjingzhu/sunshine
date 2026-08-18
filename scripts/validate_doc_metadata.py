#!/usr/bin/env python3
"""Enforce stable identity and mutable version across the policy documents.

The failure this prevents is quiet: a document is renamed to carry its version,
or a reference is written against a path that later moves, and an agent follows
a stale pointer to a policy that no longer says what it used to. Nothing errors
at the time. `.ai/CORE.md` states the rule; this makes it enforceable.
"""

from __future__ import annotations

from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]

# Documents that carry policy, and therefore carry a version. Append-only memory
# and run reports are deliberately absent: appending a lesson is not a policy
# revision, and versioning an immutable record says nothing.
VERSIONED = (
    "CLAUDE.md",
    "AGENTS.md",
    ".ai/CORE.md",
    ".ai/EXECUTION.md",
    ".ai/MANAGER.md",
    ".ai/PROJECT_CONTEXT.md",
    ".ai/REPORTING.md",
    ".ai/REPOSITORY.md",
    ".ai/REVIEW.md",
    ".ai/UX.md",
    ".ai/memory/MANAGER_PLAYBOOK.md",
)

UNVERSIONED = (".ai/memory/PROJECT_LESSONS.md",)

FRONTMATTER = re.compile(r"\A---\n(.*?)\n---\n", re.DOTALL)
SEMVER = re.compile(r"^\d+\.\d+\.\d+$")
ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
DOC_ID = re.compile(r"^[a-z][a-z0-9]*(?:-[a-z0-9]+)*$")
REQUIRED = ("doc_id", "version", "canonical_path", "updated")

# A filename carrying a version: MANAGER_v2.md, EXECUTION_1.3.0.md. Prohibited
# because it puts the version in the one place every other document must know,
# so a bump becomes an edit to every file that cites it.
VERSIONED_FILENAME = re.compile(r"[A-Za-z0-9_]+(?:_v\d+|_\d+\.\d+(?:\.\d+)?)\.md")

# A repository-relative markdown reference, backticked or inline.
REFERENCE = re.compile(r"`((?:\.ai/|docs/)?[A-Za-z0-9_./-]+\.md)`")

# Reference checking covers the policy set only. `docs/` holds product
# contracts, which legitimately name a destination path in another repository
# and an external source baseline that does not live here; upstream citations in
# those documents are checked by scripts/verify_pinned_upstream.py instead.
SCOPE = (".ai/", "CLAUDE.md", "AGENTS.md")


class DocMetadataError(ValueError):
    pass


def frontmatter(path: Path, name: str) -> dict[str, str]:
    """Parse the metadata block. `name` is how the document is reported, which
    the caller already knows -- deriving it here would assume a fixed root and
    break whenever the validator is pointed at a copy of the tree."""

    match = FRONTMATTER.match(path.read_text(encoding="utf-8"))
    if not match:
        raise DocMetadataError(f"{name}: no metadata block")
    fields: dict[str, str] = {}
    for line in match.group(1).splitlines():
        if not line.strip():
            continue
        key, separator, value = line.partition(":")
        if not separator:
            raise DocMetadataError(f"{name}: malformed metadata line {line!r}")
        fields[key.strip()] = value.strip()
    return fields


def policy_documents(root: Path) -> list[Path]:
    """The policy set: `.ai/` plus the entry documents, minus run reports."""

    found = []
    for path in sorted(root.rglob("*.md")):
        relative = path.relative_to(root).as_posix()
        if ".git" in path.parts or relative.startswith(".ai/reports/"):
            continue
        if any(relative.startswith(prefix) for prefix in SCOPE):
            found.append(path)
    return found


def validate(root: Path = ROOT) -> tuple[int, list[str]]:
    failures: list[str] = []
    seen: dict[str, str] = {}

    for relative in VERSIONED:
        path = root / relative
        if not path.is_file():
            failures.append(f"{relative}: listed as versioned but missing")
            continue
        try:
            fields = frontmatter(path, relative)
        except DocMetadataError as error:
            failures.append(str(error))
            continue

        missing = [key for key in REQUIRED if key not in fields]
        unknown = sorted(set(fields) - set(REQUIRED))
        if missing or unknown:
            failures.append(f"{relative}: metadata missing={missing}, unknown={unknown}")
            continue

        if not DOC_ID.fullmatch(fields["doc_id"]):
            failures.append(f"{relative}: doc_id must be lowercase kebab-case")
        if fields["doc_id"] in seen:
            failures.append(
                f"{relative}: doc_id {fields['doc_id']!r} already used by {seen[fields['doc_id']]}"
            )
        else:
            seen[fields["doc_id"]] = relative

        if not SEMVER.fullmatch(fields["version"]):
            failures.append(f"{relative}: version must be MAJOR.MINOR.PATCH")
        if not ISO_DATE.fullmatch(fields["updated"]):
            failures.append(f"{relative}: updated must be YYYY-MM-DD")

        # The whole point of the scheme: the document's own address must be the
        # place it actually lives, or a reference that trusts it is wrong.
        if fields["canonical_path"] != relative:
            failures.append(
                f"{relative}: canonical_path says {fields['canonical_path']!r}"
            )

    for relative in UNVERSIONED:
        path = root / relative
        if path.is_file() and FRONTMATTER.match(path.read_text(encoding="utf-8")):
            failures.append(f"{relative}: append-only memory must not carry a version")

    versioned_paths = set(VERSIONED)
    for path in policy_documents(root):
        relative = path.relative_to(root).as_posix()
        text = path.read_text(encoding="utf-8")

        if VERSIONED_FILENAME.search(path.name):
            failures.append(f"{relative}: filename carries a version")

        for reference in REFERENCE.findall(text):
            # Prose in CORE.md quotes prohibited spellings to prohibit them.
            if relative == ".ai/CORE.md":
                break
            if VERSIONED_FILENAME.fullmatch(Path(reference).name):
                failures.append(f"{relative}: references a versioned filename {reference!r}")
            if reference in versioned_paths or (root / reference).is_file():
                continue
            failures.append(
                f"{relative}: reference does not resolve: {reference} "
                "(use the canonical path, not a relative one)"
            )

    return len(VERSIONED), failures


def main() -> int:
    try:
        count, failures = validate()
    except OSError as error:
        print(error, file=sys.stderr)
        return 1
    if failures:
        print("\n".join(failures), file=sys.stderr)
        return 1
    print(f"Document metadata passed: {count} versioned policy document(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
