#!/usr/bin/env python3
"""Enforce what a New Tab background may be, and how that is decided.

The owner's rule is three sentences: a background may be PNG, JPEG or WebP,
including their animated forms; an animated asset loops for as long as it says
it does; and the animation must be visible-only, opt-in and self-contained.

Two of those are decidable from source and this checks them.

**The format rule is about bytes, not names.** A file called `.png` that
begins with `GIF89a` is a GIF, and Blink would decode it happily, because
Blink chooses its decoder by signature exactly as this rule does. So an
implementation that accepted files by extension would admit precisely the
formats the rule exists to refuse -- while looking, in the source, like it
was enforcing something.

**Neither animated form is a separate signature.** An APNG *is* a PNG and an
animated WebP *is* a WebP -- same signatures, same names, animation in chunks
a decoder either reads or skips. Code that tried to
detect it separately would be claiming to distinguish two things that are one
thing, and this check refuses that shape rather than tolerating it.

**Self-containment is the load-bearing half of PB-5a.** The permitted
animation is carried by the asset. The moment Sunshine owns a timer or a
frame callback driving it, PB-5a's third property is false and the amendment
that allowed the feature no longer covers it -- so the repeating-task symbols
are refused here too, in the background source specifically, rather than only
in the general sweep `scripts/verify_no_interposition.py` runs.

Enforces: NTB-1, NTB-2, NTB-3, NTB-4, NTB-5.
"""

from __future__ import annotations

from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]

SOURCE = "chrome/browser/ui/sunshine/newtab_background.cc"
HEADER = "chrome/browser/ui/sunshine/newtab_background.h"

# The signatures, as the source must spell them.
PNG_SIGNATURE = ("0x89", "0x50", "0x4E", "0x47", "0x0D", "0x0A", "0x1A", "0x0A")
JPEG_SIGNATURE = ("0xFF", "0xD8", "0xFF")

# WebP takes two, and needing two is the rule rather than a detail.
#
# `RIFF` is a container tag shared with WAV and AVI. What says WebP is the
# `WEBP` tag at offset 8. A source that declared the first without the second
# would accept a renamed WAV as a background while looking exactly like a
# signature check -- so declaring `RIFF` alone is refused below, by name.
RIFF_TAG = ("0x52", "0x49", "0x46", "0x46")
WEBP_TAG = ("0x57", "0x45", "0x42", "0x50")

# Signatures of formats the rule excludes. Present in the source as an
# accepted constant, each is a violation; named in a comment, each is
# documentation. The difference is whether it appears in a byte-array
# initialiser, so that is what is matched.
EXCLUDED_SIGNATURES = {
    "GIF": ("0x47", "0x49", "0x46"),
}

# A repeating task driving the animation would falsify PB-5a's third property.
REPEATING_SYMBOLS = (
    "base::RepeatingTimer",
    "base::DelayTimer",
    "base::MetronomeTimer",
    "RequestAnimationFrame",
    "setInterval(",
    "requestAnimationFrame(",
)


def added_lines_by_target(root: Path) -> dict[str, str]:
    """{upstream path: the text the stack adds to it}.

    Attribution by file, not by proximity in a concatenated blob. The first
    version of this check searched a text window around each symbol and asked
    whether the word "background" was nearby -- which is a vocabulary test
    wearing a scope's clothes, and it fired on an unrelated timer in an
    unrelated file because the New Tab page's own markup says "background"
    dozens of times. A symbol either lands in this feature's files or it does
    not; that is a fact, and this reads it.
    """

    result: dict[str, list[str]] = {}
    for patch in sorted((root / "downstream/patches").glob("*.patch")):
        target: str | None = None
        for line in patch.read_text(encoding="utf-8").splitlines():
            if line.startswith("+++ "):
                target = line[4:].strip()
                if target.startswith("b/"):
                    target = target[2:]
                continue
            if line.startswith("--- ") or line.startswith("diff --git"):
                continue
            if target and line.startswith("+"):
                result.setdefault(target, []).append(line[1:])
    return {path: "\n".join(lines) for path, lines in result.items()}



def patched_lines_by_target(root: Path) -> dict[str, str]:
    """{upstream path: added *and* context lines, in order}.

    `added_lines_by_target` drops context, which is right for every rule that
    asks what the patch introduces. One rule asks where the patch introduces it
    -- relative to a line the patch does not touch -- and for that the context
    is the whole point.
    """

    result: dict[str, list[str]] = {}
    for patch in sorted((root / "downstream/patches").glob("*.patch")):
        target: str | None = None
        for line in patch.read_text(encoding="utf-8").splitlines():
            if line.startswith("+++ "):
                target = line[4:].strip()
                if target.startswith("b/"):
                    target = target[2:]
                continue
            if line.startswith(("--- ", "diff --git", "@@", "index ")):
                continue
            if target and line[:1] in ("+", " "):
                result.setdefault(target, []).append(line[1:])
    return {path: "\n".join(lines) for path, lines in result.items()}


# What makes a file part of this feature, decided from what it says rather than
# from a list someone has to remember to update. A file added tomorrow that
# serves or renders the background names one of these and is in scope by that
# fact alone.
FEATURE_MARKERS = ("newtab_background", "sunshineBackground",
                   "ReadInstalledBackground", "sunshine-background")


def feature_targets(added: dict[str, str]) -> dict[str, str]:
    return {
        path: text
        for path, text in added.items()
        if any(marker in text or marker in path for marker in FEATURE_MARKERS)
    }


def byte_arrays(text: str) -> list[tuple[str, ...]]:
    """Every byte-array initialiser in the text, normalised to `0xNN` strings.

    Hex, decimal and character literals all, because a reviewer got a GIF
    signature past the hex-only version three ways -- `{'G', 'I', 'F'}`,
    `{71, 73, 70, 56}`, and hex again in a file the scope missed. A rule that
    reads one notation is a rule about notation.
    """

    found = []
    for match in re.finditer(r"\{([^{}]+)\}", text):
        items = [item.strip() for item in match.group(1).split(",") if item.strip()]
        values = []
        for item in items:
            if re.fullmatch(r"0x[0-9A-Fa-f]{1,2}", item):
                values.append(int(item, 16))
            elif re.fullmatch(r"\d{1,3}", item):
                values.append(int(item))
            elif re.fullmatch(r"'\\?.'", item):
                values.append(ord(item.strip("'").lstrip("\\")))
            else:
                values = []
                break
        if values and all(0 <= value <= 255 for value in values):
            found.append(tuple(f"0x{value:02X}" for value in values))
    return found


def _webp_offsets(text: str) -> set[str]:
    """The offsets the source names for the WebP tag.

    Written narrowly on purpose: the check is that *some* named offset for the
    WebP tag exists and is 8, not that a particular spelling was used.
    """

    found = set()
    for match in re.finditer(r"kWebpTagOffset\s*=\s*(\d+)", text):
        found.add(match.group(1))
    for match in re.finditer(r"MatchesAt\([^,]+,\s*(\d+)\s*,\s*kWebpTag", text):
        found.add(match.group(1))
    return found


# Comments are not code. `byte_arrays()` reads text, so a signature commented
# out still satisfied NTB-1 -- the declaration was present and nothing asked
# whether it survived compilation.
COMMENT = re.compile(r"//[^\n]*|/\*.*?\*/", re.S)


def without_comments(text: str) -> str:
    return COMMENT.sub("", text)


# The path the browser serves the asset at. It has to appear twice in
# untrusted_source.cc -- once in the allowlist `ShouldServiceRequest` checks,
# once in the branch `StartDataRequest` runs -- and naming it twice is exactly
# how this shipped broken: the branch existed, the allowlist did not, every
# request was refused with ERR_INVALID_URL, and the handler was unreachable.
# Nothing objected: it compiled, the build went green, and this guard passed,
# because none of them knew the two had to agree.
SERVED_PATH = "sunshine-background.png"
SOURCE_FILE = "chrome/browser/ui/webui/new_tab_page/untrusted_source.cc"
PAGE_FILE = "chrome/browser/resources/new_tab_page/app.ts"
PAGE_STYLE = "chrome/browser/resources/new_tab_page/app.css"
PAGE_MARKUP = "chrome/browser/resources/new_tab_page/app.html"
SERVED_CONSTANT = "kSunshineBackgroundPath"


def check_served_path_is_reachable(added: dict[str, str], failures: list[str]) -> None:
    """NTB-5: the path the handler answers is a path the source will service.

    Checked by counting uses of the named constant, not by looking for
    `ShouldServiceRequest`. The function's name sits on a context line -- an
    edit to the allowlist changes the `return` chain, not the signature -- so
    a rule that searched for the name would fail on a correct patch. What a
    correct patch does show is the constant appearing three times in its added
    lines: once declared, once in the handler, once in the allowlist.
    """

    source = added.get(SOURCE_FILE)
    if source is None:
        failures.append(f"NTB-5 {SOURCE_FILE} is not in the patch stack")
        return
    code = without_comments(source)

    literals = code.count(f'"{SERVED_PATH}"')
    if literals != 1:
        failures.append(
            f"NTB-5 the path {SERVED_PATH!r} is written as a literal {literals} "
            "time(s); it must be one named constant, because the allowlist and "
            "the handler both name it and two literals can disagree"
        )

    uses = code.count(SERVED_CONSTANT)
    if uses < 3:
        failures.append(
            f"NTB-5 {SERVED_CONSTANT} appears {uses} time(s) in the added lines; "
            "a served path needs three -- declared, matched in the handler, and "
            "listed in the allowlist. Two means the handler exists and the "
            "allowlist does not, which is unreachable code that compiles"
        )


def check_resting_is_bounded(added: dict[str, str], failures: list[str]) -> None:
    """NTB-6, NTB-7, NTB-8: the resting state cannot run away.

    Three things can go wrong with "hide the page three seconds after focus
    leaves", and each is checkable in the added lines rather than at runtime:

    - it hides on a build with no background, leaving a blank page;
    - the delay becomes a repeating task, which is the one thing PB-5a's third
      property forbids outright;
    - the timer is armed and never cancelled, so a page that regained focus
      rests anyway a moment later.
    """

    page = added.get(PAGE_FILE)
    if page is None:
        return  # The page patch is checked elsewhere; absence is not this rule.
    code = without_comments(page)
    if "sunshine-resting" not in code:
        return  # The feature is not present. Nothing to hold to its rules.

    if "sunshineBackgroundAvailable_" not in code.split("shouldRest")[-1][:400] \
            and "sunshineBackgroundAvailable_" not in code:
        failures.append(
            "NTB-6 the resting state does not consult "
            "sunshineBackgroundAvailable_; hiding the page on a build with no "
            "background leaves an empty New Tab, which is not a feature"
        )

    if "setInterval(" in code or "requestAnimationFrame(" in code:
        failures.append(
            "NTB-7 the page arms a repeating task; the rest delay is one-shot, "
            "and a repeating timer is what PB-5a's third property refuses"
        )

    # Two call sites are required, and counting them against the number of
    # `setTimeout`s does not express that: one cancel satisfies one arm while
    # leaving the other path uncovered, which is how the first version of this
    # rule passed a patch with the important cancel deleted.
    #
    #   1. the recompute -- focus returned, or the window was hidden, before
    #      the three seconds elapsed;
    #   2. teardown -- the element is removed while a timer is armed.
    #
    # Neither substitutes for the other.
    arms = code.count("setTimeout(")
    cancels = code.count("clearTimeout(")
    if arms and cancels < 2:
        failures.append(
            f"NTB-7 setTimeout appears {arms} time(s) and clearTimeout "
            f"{cancels}; a pending rest timer has two paths out -- the state "
            "being recomputed and the element being torn down -- and each "
            "needs its own cancel"
        )

    # The rule lives in the stylesheet, not in the script -- which is where
    # the first version of this check looked, and it fired on a correct patch.
    style = added.get(PAGE_STYLE, "")
    resting_rule = ""
    marker = "[sunshine-resting]"
    if marker in style:
        start = style.index(marker)
        end = style.find("}", start)
        resting_rule = style[start:end if end != -1 else len(style)]
    if "pointer-events" not in resting_rule:
        failures.append(
            "NTB-8 the [sunshine-resting] rule does not set pointer-events; "
            "content faded to nothing still answers a click, and the click "
            "that restores focus would land on an invisible control"
        )

    if "hasFocus()" not in code:
        failures.append(
            "NTB-6 resting is not derived from document.hasFocus(); an "
            "unfocused window is still visible, so visibilityState cannot "
            "decide this on its own"
        )


def check_resting_cannot_fade_the_background(added: dict[str, str],
                                             patched: dict[str, str],
                                             failures: list[str]) -> None:
    """The background must not be inside anything the resting rule fades.

    This rule exists because its absence shipped a defect. Resting fades every
    child of the host except the background, and `opacity` applies to a whole
    subtree -- so a background nested inside `#content` faded with the page
    instead of being what remained. The feature did the opposite of its own
    description, and the four rules written beside it all passed: each asked
    whether the CSS and the timer were correct, and none asked where the
    element was.

    The checkable property is position. `#sunshineBackground` must appear in
    the markup before `<div id="content"`, which is what makes it a sibling of
    the thing that fades rather than a descendant of it.
    """

    markup = patched.get(PAGE_MARKUP)
    if markup is None or "sunshine-resting" not in "".join(added.values()):
        return
    if 'id="sunshineBackground"' not in markup:
        return

    background = markup.index('id="sunshineBackground"')
    content = markup.find('<div id="content"')
    if content == -1:
        failures.append(
            "NTB-10 the page markup no longer contains #content, so the "
            "position of the background relative to the faded subtree cannot "
            "be decided; this rule needs rewriting rather than removing"
        )
        return
    if background > content:
        failures.append(
            "NTB-10 #sunshineBackground appears after <div id=\"content\">, "
            "which makes it a descendant of the element resting fades. opacity "
            "applies to the whole subtree, so the background would fade with "
            "the page instead of being what remains -- the feature doing the "
            "opposite of its description"
        )

    status = markup.find('id="sunshineStatus"')
    if status != -1 and status > content:
        failures.append(
            "NTB-10 #sunshineStatus appears after <div id=\"content\">; the "
            "clock has to survive resting, and anything inside the faded "
            "subtree cannot"
        )


def check(root: Path, failures: list[str]) -> None:
    added = added_lines_by_target(root)
    check_served_path_is_reachable(added, failures)
    check_resting_is_bounded(added, failures)
    check_resting_cannot_fade_the_background(
        added, patched_lines_by_target(root), failures)

    source = added.get(SOURCE)
    if source is None:
        failures.append(f"NTB-1 {SOURCE} is not in the patch stack")
        return

    code = without_comments(source)
    arrays = byte_arrays(code)

    # NTB-1: a declared signature that nothing reads is decoration. Each
    # constant must appear again outside its own declaration.
    for name in ("kPngSignature", "kJpegSignature", "kRiffTag", "kWebpTag"):
        if code.count(name) < 2:
            failures.append(
                f"NTB-1 {name} is declared but never read; a signature nothing "
                "compares against decides nothing"
            )

    # NTB-1: every permitted signature is declared, as bytes.
    if PNG_SIGNATURE not in arrays:
        failures.append("NTB-1 the PNG signature is not declared as a byte array")
    if JPEG_SIGNATURE not in arrays:
        failures.append("NTB-1 the JPEG signature is not declared as a byte array")
    if RIFF_TAG not in arrays:
        failures.append("NTB-1 the RIFF tag is not declared as a byte array")

    # NTB-4: WebP is two tags at two offsets, or it is not WebP.
    if RIFF_TAG in arrays and WEBP_TAG not in arrays:
        failures.append(
            "NTB-4 the RIFF tag is declared without the WEBP tag; RIFF alone is "
            "shared with WAV and AVI, so this accepts a renamed WAV"
        )
    if WEBP_TAG in arrays and "8" not in _webp_offsets(source):
        failures.append(
            "NTB-4 the WEBP tag is declared but never checked at offset 8"
        )

    # NTB-2: no excluded format is declared as a signature.
    for label, signature in EXCLUDED_SIGNATURES.items():
        for array in arrays:
            if array[: len(signature)] == signature:
                failures.append(
                    f"NTB-2 a {label} signature is declared as a byte array; "
                    "the rule admits PNG, JPEG and WebP only"
                )

    # NTB-2: the decision is not made from the file name.
    # NTB-2: the decision is not made from the file name.
    #
    # Two scopes, because two different jobs use the same vocabulary. Deciding
    # *what a file is* from its name is the defect; deciding a MIME header from
    # a URL path is not, and `untrusted_source.cc` legitimately does the second
    # in `GetMimeType`. So the string-suffix symbols are checked only in the
    # file that decides the format, while the FilePath symbols -- which can
    # only be asking about a name on disk -- are refused anywhere in the
    # feature.
    for symbol in (".Extension()", "MatchesExtension", "FinalExtension"):
        for path, text in feature_targets(added).items():
            if symbol in without_comments(text):
                failures.append(
                    f"NTB-2 {path}: {symbol!r} decides a background's format "
                    "from its name"
                )
    # `EndsWith` is here because an adversarial reviewer got a name-based
    # DetectFormat past this check with it, while the byte arrays sat unused
    # beside it and NTB-1 was satisfied by their mere presence.
    for symbol in ("EndsWith(", "ends_with(", "extension()"):
        if symbol in code:
            failures.append(
                f"NTB-2 {SOURCE}: {symbol!r} decides a background's format "
                "from its name; the rule is about the bytes"
            )

    # NTB-2: the enum may not grow a format the rule does not admit.
    fmt = without_comments(added.get(HEADER, ""))
    body = re.search(r"enum class Format\s*\{([^}]*)\}", fmt)
    declared = set(re.findall(r"\bk([A-Za-z0-9]+)\b", body.group(1))) if body else set()
    if body is None:
        failures.append("NTB-2 the Format enum is not declared in the added lines")
    unexpected = declared - {"None", "Png", "Jpeg", "Webp"}
    if unexpected:
        failures.append(
            "NTB-2 the Format enum declares "
            + ", ".join(sorted("k" + name for name in unexpected))
            + "; the rule admits PNG, JPEG and WebP only"
        )

    # NTB-3: nothing Sunshine owns drives the animation.
    for path, text in feature_targets(added).items():
        for symbol in REPEATING_SYMBOLS:
            if symbol in text:
                failures.append(
                    f"NTB-3 {path}: {symbol!r} would make Sunshine own the "
                    "animation; PB-5a requires the asset to carry it"
                )


def validate(root: Path = ROOT) -> list[str]:
    failures: list[str] = []
    check(root, failures)
    return failures


def main() -> int:
    failures = validate()
    if failures:
        print("\n".join(failures), file=sys.stderr)
        return 1
    print(
        "New Tab background check passed: PNG, JPEG and WebP by signature, "
        "WebP by both of its tags, no excluded format, no Sunshine-owned "
        "animation driver."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
