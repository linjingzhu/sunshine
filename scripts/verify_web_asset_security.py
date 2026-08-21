#!/usr/bin/env python3
"""Hold Sunshine-authored web assets to the rules a privileged surface needs.

Sunshine's web assets are not ordinary page content. They are patched into
Chromium's own WebUI, which runs at a privilege level no website has, so the
usual "it is first-party, it is fine" reasoning is exactly backwards: being
first-party is what makes a mistake here expensive.

    SEC-14  no dynamically constructed code, and no remote resource, in a
            Sunshine-authored web asset

Two families, both decidable from source.

**Dynamic code.** `eval`, `new Function`, and the string forms of `setTimeout`
and `setInterval` turn data into code. So does assigning to `innerHTML`, which
is why Chromium's WebUI enforces Trusted Types and would reject it at runtime --
this check moves that rejection to review time, where it is cheap.

**Remote resources.** A privileged surface that loads a script, stylesheet or
font from the network has handed its privilege to whoever controls that host,
and to anyone who can intercept the connection. Sunshine's surfaces ship with
the browser and have no reason to fetch anything.

Enforces: SEC-14, SECA-9, WA-1, WA-2.
"""

from __future__ import annotations

from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]

SEARCHED = ("first_party", "downstream")
GUARD_PREFIXES = ("verify_", "validate_", "test_")
WEB_SUFFIXES = (".ts", ".js", ".css", ".html")

# A patch is mostly upstream. Only added lines are Sunshine's, and the file the
# hunk targets decides whether the added lines are a web asset at all.
PATCH_FILE = re.compile(r"^\+\+\+ b/(.+)$")

DYNAMIC_CODE = (
    (re.compile(r"\beval\s*\("), "eval() turns data into code"),
    (re.compile(r"\bnew\s+Function\s*\("), "new Function() turns data into code"),
    (re.compile(r"\bset(?:Timeout|Interval)\s*\(\s*[\"']"), "a string timer body is eval by another name"),
    (re.compile(r"\.innerHTML\s*="), "innerHTML assignment; Chromium WebUI enforces Trusted Types"),
    (re.compile(r"\.outerHTML\s*="), "outerHTML assignment; Chromium WebUI enforces Trusted Types"),
    (re.compile(r"document\.write\s*\("), "document.write() parses a string as markup"),
)

# A remote URL anywhere in a web asset. `chrome://` and `chrome-untrusted://`
# are Chromium's own internal surfaces and are not remote; `data:` is inline.
REMOTE_URL = re.compile(r"""["'(\s](https?://[^"'\s)]+)""")
ALLOWED_REMOTE_CONTEXT = re.compile(r"^\s*(?://|/\*|\*|#|<!--)")


def _is_guard(path: Path) -> bool:
    return path.name.startswith(GUARD_PREFIXES)


def web_assets(root: Path) -> list[tuple[str, str]]:
    """(label, text) for every Sunshine-authored web asset.

    Patch files contribute only their added lines, and only for hunks whose
    target file is itself a web asset -- an added line in a `.cc` file is not
    JavaScript however much it looks like it.
    """

    assets: list[tuple[str, str]] = []
    for directory in SEARCHED:
        base = root / directory
        if not base.is_dir():
            continue
        for path in sorted(base.rglob("*")):
            if not path.is_file() or _is_guard(path):
                continue
            if path.suffix in WEB_SUFFIXES:
                assets.append((path.relative_to(root).as_posix(), path.read_text(encoding="utf-8")))
            elif path.suffix == ".patch":
                assets.extend(patch_web_assets(path, path.relative_to(root).as_posix()))
    return assets


def patch_web_assets(path: Path, label: str) -> list[tuple[str, str]]:
    collected: dict[str, list[str]] = {}
    target: str | None = None
    for line in path.read_text(encoding="utf-8").splitlines():
        header = PATCH_FILE.match(line)
        if header:
            candidate = header.group(1)
            target = candidate if candidate.endswith(WEB_SUFFIXES) else None
            continue
        if target and line.startswith("+"):
            collected.setdefault(target, []).append(line[1:])
    return [(f"{label} -> {name}", "\n".join(lines)) for name, lines in collected.items()]


# A backtick in an HTML file the stack touches.
#
# Chromium preprocesses a Lit template's `.html` into a TypeScript file whose
# whole body is one template literal. Inside that literal a backtick **ends the
# string** and `${` starts an expression, so a backtick written as punctuation
# -- in a comment, even -- is a syntax error hundreds of lines away from
# anything that looks wrong.
#
# Build #38 died exactly there: an HTML comment in
# `chrome/browser/resources/new_tab_page/app.html` quoted an attribute name in
# backticks and `tsc` reported `TS1005: ';' expected` in generated
# `app.html.ts`, in a file no one had written. The upstream comment that patch
# replaced had been signalling the rule all along -- it wrote its own binding
# as a backslash-escaped dollar -- and the signal was not read.
#
# Scoped to every `.html` the stack touches rather than to Lit templates only.
# Deciding which files are templates needs the whole file, and a patch shows
# added lines; no HTML in this stack has ever wanted a backtick, so the broad
# rule costs nothing and cannot be outgrown by a file someone forgets to
# classify.
BACKTICK_IN_HTML = "`"


def check_no_backtick_in_html(root: Path, failures: list[str]) -> None:
    """WA-1: no line the stack adds to an HTML file contains a backtick."""

    for patch in sorted((root / "downstream/patches").glob("*.patch")):
        target: str | None = None
        for number, line in enumerate(
            patch.read_text(encoding="utf-8").splitlines(), start=1
        ):
            header = PATCH_FILE.match(line)
            if header:
                target = header.group(1)
                continue
            if not target or not target.endswith(".html"):
                continue
            if line.startswith("+") and BACKTICK_IN_HTML in line:
                failures.append(
                    f"{patch.name}:{number}: adds a backtick to {target}; that "
                    "file becomes a TypeScript template literal, where a "
                    "backtick ends the string (WA-1)"
                )


# A Lit binding the stack adds to an HTML template, and the reactive property
# declaration it requires in the sibling TypeScript.
#
# Chromium's `lit-reactive-properties` rule holds that every property a
# template reads is declared in `static get properties()`, and its companion
# `lit-property-accessor` then requires the `accessor` keyword on the field.
# Omit the declaration and both fire at once -- which is one omission seen from
# two sides, and is how build #38 failed its second time.
#
# Only bindings the stack *adds* are checked, against declarations the stack
# *adds*. Upstream's own bindings are already declared upstream, and a rule
# that demanded the stack re-declare them would fail on every patch that
# touches a template.
LIT_BINDING = re.compile(r"\$\{this\.([A-Za-z_][A-Za-z0-9_]*)\}")


def check_lit_bindings_are_declared(root: Path, failures: list[str]) -> None:
    """WA-2: a binding the stack adds has a reactive declaration it adds."""

    added: dict[str, list[str]] = {}
    for patch in sorted((root / "downstream/patches").glob("*.patch")):
        target: str | None = None
        for line in patch.read_text(encoding="utf-8").splitlines():
            header = PATCH_FILE.match(line)
            if header:
                target = header.group(1)
                continue
            if target and line.startswith("+") and not line.startswith("+++ "):
                added.setdefault(target, []).append(line[1:])

    for path, lines in added.items():
        if not path.endswith(".html"):
            continue
        sibling = path[: -len(".html")] + ".ts"
        declarations = "\n".join(added.get(sibling, []))
        for line in lines:
            for name in LIT_BINDING.findall(line):
                if f"{name}: {{type:" not in declarations:
                    failures.append(
                        f"{path}: binds {name!r}, which {sibling} does not "
                        "declare in its properties block (WA-2)"
                    )


def check(root: Path = ROOT) -> list[str]:
    failures: list[str] = []
    check_no_backtick_in_html(root, failures)
    check_lit_bindings_are_declared(root, failures)
    for label, text in web_assets(root):
        for number, line in enumerate(text.splitlines(), start=1):
            for pattern, why in DYNAMIC_CODE:
                if pattern.search(line):
                    failures.append(f"{label}:{number}: {why} (SEC-14)")
            # A URL inside a comment is documentation, not a load. The patch
            # stack cites upstream files by URL in its own comments, and a rule
            # that fired on those would be deleted the first week.
            if ALLOWED_REMOTE_CONTEXT.match(line):
                continue
            for url in REMOTE_URL.findall(line):
                failures.append(f"{label}:{number}: loads a remote resource {url!r} (SEC-14)")
    return failures


def main() -> int:
    failures = check()
    if failures:
        print("\n".join(failures), file=sys.stderr)
        return 1
    print("Web asset security check passed: no dynamic code, no remote resource.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
