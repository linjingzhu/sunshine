#!/usr/bin/env python3
"""Enforce the source-checkable half of the design-system contract.

`docs/DESIGN_SYSTEM_CONTRACT.md` §9.1 states twelve checks, S1 to S12, over
"Sunshine-authored CSS in the patch stack". Everything here turns on what that
phrase denotes, because a patch hunk carries three kinds of line: added lines,
which are Sunshine's; removed lines, which are gone; and context lines, which
are upstream's own CSS quoted so the hunk can be located. Upstream's New Tab
stylesheet is full of `px` sizes and literal colours -- a check that judged
context lines would fail the build on Chromium's code and would be deleted by
the next person to read it.

So the checks work in two passes. The post-image of each hunk (context plus
added, in order) is parsed as CSS to recover the structure a declaration sits
in: its rule, its enclosing at-rules, the comments attached to that rule. Only
then is authorship applied -- a declaration is judged when a line it spans was
added by Sunshine. That keeps `#logo { margin-bottom: ... }` in the context of
patch 0002 unjudged while the `#sunshineWordmark` rule directly beneath it is
judged in full, and it lets a rule-level rule ("declare `direction` on the same
element") see upstream declarations that satisfy it.

Two consequences of reading a hunk rather than a file are worth stating. A rule
can be cut in half by the hunk boundary, so satisfaction-style checks (S9, S11,
S12) only run when both braces of the rule were observed; a truncated rule is
skipped rather than guessed at. And a hunk header's trailing text -- git's
`@@ ... @@ cr-most-visited {` -- is upstream context, not an added line, so it
seeds the enclosing rule without ever being judged.

S1 is the one check that needs the pinned Chromium sources. It lives in
`check_token_provenance`, apart from `validate`, reading through
`scripts/verify_pinned_upstream.py`'s fetcher so there is one place that knows
how a pinned file is read. `validate` touches no network, which is what lets the
test suite inject violations and run offline.

Enforces: design-system contract §9.1, checks S1 through S13.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass, field
from pathlib import Path
import re
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))

import patch_manifest as manifest  # noqa: E402
import verify_pinned_upstream as upstream  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
PATCH_DIRECTORY = "downstream/patches"

# §6.3's own worked example computes the wordmark's fluid band as 533-933px from
# `clamp(2rem, 6vw, 3.5rem)`, which is 16px per rem. The same constant is used
# here so the tool and the contract agree on the arithmetic.
ROOT_FONT_PX = 16.0

# Only the `/* */` form: CSS has no `//` comment, and every url() in these
# stylesheets begins `//resources/...`.
CSS_COMMENTS = re.compile(r"/\*.*?\*/", re.S)

# §9.1 S2 names exactly these properties. `background` and `box-shadow` are not
# in the list; widening it is a contract amendment, not a tool decision.
COLOUR_PROPERTIES = ("color", "background-color", "border-color", "outline-color", "fill", "stroke")

# §2.2(3): a `--sun-color-*` token's value must be a reference, never a literal.
SUNSHINE_COLOUR_PREFIX = "--sun-color-"

# The token families §2.1 says Sunshine may read but never define.
UPSTREAM_TOKEN_PREFIXES = ("--color-", "--cr-", "--ntp-")

# §9.1 S2's literal forms, plus the alpha and CIE spellings of the same thing.
# `color-mix()` is deliberately absent: §2.2(3) permits composing references
# through it, and it contains no literal of its own.
LITERAL_COLOUR_SYNTAX = (
    "#", "rgb(", "rgba(", "hsl(", "hsla(", "hwb(", "lab(", "lch(", "oklab(", "oklch(",
)

# The CSS named colours. `transparent`, `currentColor` and the system colours
# (`Canvas`, `CanvasText`, `Highlight`, `LinkText`) are absent on purpose: §2.1
# lists system colours as a family Sunshine may read.
NAMED_COLOURS = frozenset("""
aliceblue antiquewhite aqua aquamarine azure beige bisque black blanchedalmond blue blueviolet
brown burlywood cadetblue chartreuse chocolate coral cornflowerblue cornsilk crimson cyan darkblue
darkcyan darkgoldenrod darkgray darkgreen darkgrey darkkhaki darkmagenta darkolivegreen darkorange
darkorchid darkred darksalmon darkseagreen darkslateblue darkslategray darkslategrey darkturquoise
darkviolet deeppink deepskyblue dimgray dimgrey dodgerblue firebrick floralwhite forestgreen fuchsia
gainsboro ghostwhite gold goldenrod gray green greenyellow grey honeydew hotpink indianred indigo
ivory khaki lavender lavenderblush lawngreen lemonchiffon lightblue lightcoral lightcyan
lightgoldenrodyellow lightgray lightgreen lightgrey lightpink lightsalmon lightseagreen
lightskyblue lightslategray lightslategrey lightsteelblue lightyellow lime limegreen linen magenta
maroon mediumaquamarine mediumblue mediumorchid mediumpurple mediumseagreen mediumslateblue
mediumspringgreen mediumturquoise mediumvioletred midnightblue mintcream mistyrose moccasin
navajowhite navy oldlace olive olivedrab orange orangered orchid palegoldenrod palegreen
paleturquoise palevioletred papayawhip peachpuff peru pink plum powderblue purple rebeccapurple red
rosybrown royalblue saddlebrown salmon sandybrown seagreen seashell sienna silver skyblue slateblue
slategray slategrey snow springgreen steelblue tan teal thistle tomato turquoise violet wheat white
whitesmoke yellow yellowgreen
""".split())

# §2.3: a non-colour token's fallback is required and must equal the documented
# upstream default. The only such default the contract states is §3's row for
# the logo margin, which upstream's own `#logo` rule proves in the patch context.
# A token with no documented default is not decidable here and is left alone.
DOCUMENTED_DEFAULTS = {"--ntp-logo-margin-bottom": "38px"}

# §6.2's scale, in rem. `display` is the fluid step and is checked by S7.
TYPE_SCALE_REM = (0.6875, 0.75, 0.875, 1.0, 1.25, 1.5, 2.0)
SMALLEST_REM = 0.6875
DISPLAY_BOUNDS_REM = (2.0, 3.5)

# §6.2: weights are drawn from this set; anything else needs a recorded R10.
RESOLVABLE_WEIGHTS = {"400", "500", "600", "700"}
WEIGHT_KEYWORDS = {"normal": "400", "bold": "700"}

# §6.2 forbids `!important` on a typography declaration; S6 names `font-size`.
TYPOGRAPHY_PROPERTIES = ("font-size", "font-weight", "font-family", "line-height")

# §7.2 enumerates the non-translated lockups so a source check can verify each
# one declares `direction`. Today the set is exactly one member.
LOCKUP_SET = ("#sunshineWordmark",)

LOGICAL_INLINE_PROPERTIES = (
    "padding-inline", "padding-inline-start", "padding-inline-end",
    "margin-inline", "margin-inline-start", "margin-inline-end",
    "inset-inline", "inset-inline-start", "inset-inline-end",
    "border-inline", "border-inline-start", "border-inline-end",
)

# §8.1's checkable form covers motion declarations and smooth scrolling.
MOTION_PREFIXES = ("animation", "transition")

# Declarations that count as reintroducing appearance inside a forced-colours or
# increased-contrast block (§5.2), beyond the colour properties themselves.
SHADOW_PROPERTIES = ("text-shadow", "box-shadow")

# Where the token families are defined at the pinned revision. `--color-*` is
# not declared in any stylesheet -- Chromium emits it from the colour IDs and
# serves it through chrome://theme -- so each family is looked up in the source
# that actually defines it. Verified against 152.0.7977.42: `--ntp-*` is
# declared in app.css (18 declarations) and logo.css (2).
COLOUR_ID_HEADERS = (
    "ui/color/color_id.h",
    "chrome/browser/ui/color/chrome_color_id.h",
)
NTP_STYLESHEETS = (
    "chrome/browser/resources/new_tab_page/app.css",
    "chrome/browser/resources/new_tab_page/logo.css",
)
CR_STYLESHEETS = ("ui/webui/resources/cr_elements/cr_shared_vars.css",)

HUNK_HEADER = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@ ?(.*)$")
TARGET_LINE = re.compile(r"^\+\+\+ b/(.+?)\s*$")
PROPERTY_NAME = re.compile(r"-{0,2}[A-Za-z][A-Za-z0-9-]*")
REM_VALUE = re.compile(r"^(\d*\.?\d+)rem$")
VIEWPORT_VALUE = re.compile(r"^(\d*\.?\d+)(vw|vi)$")
PX_IN_VALUE = re.compile(r"(?<![\w-])\d*\.?\d+px(?![\w-])")
TABINDEX = re.compile(r"tabindex\s*=\s*[\"']?(-?\d+)", re.I)
INLINE_STYLE = re.compile(r"style\s*=\s*\"([^\"]*)\"")


# --------------------------------------------------------------------------
# Patch reading
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class Line:
    origin: str  # "added" (Sunshine's) or "context" (upstream's, quoted)
    text: str
    number: int  # 1-based line number inside the patch file, for evidence


@dataclass(frozen=True)
class Hunk:
    patch: str
    path: str
    section: str  # git's trailing hunk-header text; upstream context, never added
    lines: tuple[Line, ...]


def read_hunks(root: Path) -> list[Hunk]:
    """Every hunk in the patch stack, as its post-image with authorship kept.

    The hunk header's line counts bound the body, so a body line that happens to
    begin with `---` or `+++` is not mistaken for a file header.
    """

    hunks: list[Hunk] = []
    directory = root / PATCH_DIRECTORY
    if not directory.is_dir():
        return hunks

    for patch in sorted(directory.glob("*.patch")):
        text = patch.read_text(encoding="utf-8").splitlines()
        path = ""
        index = 0
        while index < len(text):
            target = TARGET_LINE.match(text[index])
            if target:
                path = target.group(1)
                index += 1
                continue
            header = HUNK_HEADER.match(text[index])
            if not header:
                index += 1
                continue
            remaining_old = int(header.group(2) or 1)
            remaining_new = int(header.group(4) or 1)
            body: list[Line] = []
            index += 1
            while index < len(text) and (remaining_old > 0 or remaining_new > 0):
                raw = text[index]
                index += 1
                marker = raw[:1]
                if marker == "\\":  # "\ No newline at end of file"
                    continue
                if marker == "+":
                    remaining_new -= 1
                    body.append(Line("added", raw[1:], index))
                elif marker == "-":
                    remaining_old -= 1
                elif marker == " " or raw == "":
                    remaining_old -= 1
                    remaining_new -= 1
                    body.append(Line("context", raw[1:], index))
                else:
                    index -= 1
                    break
            hunks.append(Hunk(patch.name, path, header.group(5), tuple(body)))
    return hunks


# --------------------------------------------------------------------------
# CSS structure
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class Declaration:
    patch: str
    path: str
    number: int
    property: str
    value: str
    selector: str
    at_rules: tuple[str, ...]
    authored: bool

    @property
    def where(self) -> str:
        return f"{self.patch}:{self.number}"

    def cleaned(self) -> str:
        return re.sub(r"\s*!\s*important\s*$", "", self.value).strip()

    @property
    def important(self) -> bool:
        return bool(re.search(r"!\s*important", self.value))


@dataclass
class Rule:
    patch: str
    path: str
    selector: str
    at_rules: tuple[str, ...]
    comments: list[str] = field(default_factory=list)
    declarations: list[Declaration] = field(default_factory=list)
    opened: bool = True  # the `{` was observed in this hunk
    closed: bool = False  # the `}` was observed in this hunk

    @property
    def complete(self) -> bool:
        return self.opened and self.closed

    @property
    def authored(self) -> bool:
        return any(declaration.authored for declaration in self.declarations)


def _split_declaration(text: str) -> tuple[str, str] | None:
    if ":" not in text:
        return None
    name, _, value = text.partition(":")
    name = name.strip()
    if not PROPERTY_NAME.fullmatch(name):
        return None
    return name, " ".join(value.split())


def scan_css(hunk: Hunk) -> tuple[list[Declaration], list[Rule]]:
    """Parse a hunk's post-image, keeping each declaration's authorship."""

    stream = [
        (character, line.number, line.origin)
        for line in hunk.lines
        for character in line.text + "\n"
    ]

    declarations: list[Declaration] = []
    rules: list[Rule] = []
    stack: list[Rule] = []
    pending_comments: list[str] = []

    buffer = ""
    buffer_added = False
    buffer_number = 0
    seed = hunk.section.strip()

    def at_rules() -> tuple[str, ...]:
        return tuple(rule.selector for rule in stack if rule.selector.startswith("@"))

    def ensure_rule() -> Rule:
        """A hunk can begin inside a rule; git's header names it when it does."""

        if not stack:
            selector = seed[:-1].strip() if seed.endswith("{") else ""
            stack.append(Rule(hunk.patch, hunk.path, selector, (), opened=False))
        return stack[-1]

    def flush() -> None:
        nonlocal buffer, buffer_added, buffer_number
        text = " ".join(buffer.split())
        buffer, added, number = "", buffer_added, buffer_number
        buffer_added, buffer_number = False, 0
        if not text or text.startswith("@"):
            return
        split = _split_declaration(text)
        if split is None:
            return
        rule = ensure_rule()
        declaration = Declaration(
            hunk.patch, hunk.path, number, split[0].lower(), split[1],
            rule.selector, at_rules(), added,
        )
        declarations.append(declaration)
        rule.declarations.append(declaration)

    index = 0
    in_comment = False
    comment = ""
    quote = ""
    parens = 0
    while index < len(stream):
        character, number, origin = stream[index]
        index += 1
        if in_comment:
            if character == "*" and index < len(stream) and stream[index][0] == "/":
                index += 1
                in_comment = False
                pending_comments.append(comment)
                if stack:
                    stack[-1].comments.append(comment)
                comment = ""
            else:
                comment += character
            continue
        if quote:
            buffer += character
            if character == quote:
                quote = ""
            continue
        if character in "\"'":
            quote = character
            buffer += character
            continue
        if character == "/" and index < len(stream) and stream[index][0] == "*":
            index += 1
            in_comment = True
            continue
        if character == "(":
            parens += 1
        elif character == ")":
            parens = max(0, parens - 1)

        if parens == 0 and character in "{};":
            if character == "{":
                prelude = " ".join(buffer.split())
                opened = Rule(hunk.patch, hunk.path, prelude, at_rules(),
                              comments=list(pending_comments))
                pending_comments.clear()
                stack.append(opened)
                buffer, buffer_added, buffer_number = "", False, 0
            elif character == ";":
                flush()
                pending_comments.clear()
            else:
                flush()
                pending_comments.clear()
                if stack:
                    closing = stack.pop()
                    closing.closed = True
                    rules.append(closing)
            continue

        buffer += character
        if not character.isspace():
            if not buffer_number:
                buffer_number = number
            if origin == "added":
                buffer_added = True

    while stack:
        rules.append(stack.pop())
    return declarations, rules


def inline_declarations(hunk: Hunk) -> list[Declaration]:
    """`style="..."` on an added markup line is Sunshine-authored CSS too.

    It has no rule and no at-rule context, so only the declaration-level checks
    apply to it. Reading it closes the obvious way around a stylesheet check.
    """

    if not hunk.path.endswith((".html", ".ts", ".js")):
        return []
    found: list[Declaration] = []
    for line in hunk.lines:
        if line.origin != "added":
            continue
        for match in INLINE_STYLE.finditer(line.text):
            for piece in match.group(1).split(";"):
                split = _split_declaration(piece)
                if split is None:
                    continue
                found.append(Declaration(
                    hunk.patch, hunk.path, line.number, split[0].lower(), split[1],
                    "(inline style attribute)", (), True,
                ))
    return found


@dataclass
class Stylesheet:
    declarations: list[Declaration] = field(default_factory=list)
    rules: list[Rule] = field(default_factory=list)
    hunks: list[Hunk] = field(default_factory=list)

    def authored(self) -> list[Declaration]:
        return [declaration for declaration in self.declarations if declaration.authored]


def read_stylesheets(root: Path) -> Stylesheet:
    sheet = Stylesheet()
    for hunk in read_hunks(root):
        sheet.hunks.append(hunk)
        if hunk.path.endswith(".css"):
            declarations, rules = scan_css(hunk)
            sheet.declarations.extend(declarations)
            sheet.rules.extend(rules)
        sheet.declarations.extend(inline_declarations(hunk))
    return sheet


# --------------------------------------------------------------------------
# Value helpers
# --------------------------------------------------------------------------


def _split_top_level(text: str, separator: str = ",") -> list[str]:
    parts, depth, current = [], 0, ""
    for character in text:
        if character == "(":
            depth += 1
        elif character == ")":
            depth -= 1
        if character == separator and depth == 0:
            parts.append(current)
            current = ""
            continue
        current += character
    parts.append(current)
    return [part.strip() for part in parts]


def var_calls(value: str) -> list[tuple[str, str | None]]:
    """Every `var()` in a value, as (token, fallback or None)."""

    calls: list[tuple[str, str | None]] = []
    for match in re.finditer(r"var\(", value):
        depth, index = 1, match.end()
        while index < len(value) and depth:
            if value[index] == "(":
                depth += 1
            elif value[index] == ")":
                depth -= 1
            index += 1
        inner = value[match.end(): index - 1 if depth == 0 else len(value)]
        head, _, tail = inner.partition(",")
        calls.append((head.strip(), tail.strip() if tail.strip() else None))
    return calls


def literal_colour(value: str) -> str | None:
    """The literal colour syntax in a value, or None if it is all references."""

    # Custom property names carry colour words (`--color-tomato-surface`) and
    # `url(#gradient)` is a legitimate SVG paint reference, not a hex literal.
    stripped = re.sub(r"--[A-Za-z0-9-]+", " ", value)
    stripped = re.sub(r"url\([^)]*\)", " ", stripped)
    for syntax in LITERAL_COLOUR_SYNTAX:
        if syntax in stripped:
            return syntax
    for token in re.findall(r"(?<![\w-])[A-Za-z]+(?![\w-])", stripped):
        if token.lower() in NAMED_COLOURS:
            return token
    return None


def is_colour_property(name: str) -> bool:
    return name in COLOUR_PROPERTIES or name.startswith(SUNSHINE_COLOUR_PREFIX)


def normalised_selector(selector: str) -> str:
    return " ".join(selector.split())


def in_at_rule(declaration: Declaration, needle: str) -> bool:
    return any(needle in "".join(prelude.split()).lower() for prelude in declaration.at_rules)


# --------------------------------------------------------------------------
# S2 - S12, all offline
# --------------------------------------------------------------------------


def check_no_literal_colours(sheet: Stylesheet, failures: list[str]) -> None:
    """S2, and §2.2(3) for `--sun-color-*` tokens, which are references only."""

    for declaration in sheet.authored():
        if not is_colour_property(declaration.property):
            continue
        literal = literal_colour(declaration.cleaned())
        if literal:
            failures.append(
                f"S2 {declaration.where}: `{declaration.property}` in "
                f"`{declaration.selector}` uses the literal colour {literal!r}; "
                "Sunshine reads colour from Chromium (§1, §2.2(3))"
            )


def check_no_token_reassignment(sheet: Stylesheet, failures: list[str]) -> None:
    """S3: assigning to a token family Sunshine does not own (§2.1)."""

    for declaration in sheet.authored():
        for prefix in UPSTREAM_TOKEN_PREFIXES:
            if declaration.property.startswith(prefix):
                failures.append(
                    f"S3 {declaration.where}: assigns `{declaration.property}` in "
                    f"`{declaration.selector}`; the `{prefix}*` family is Chromium's "
                    "and is read-only for Sunshine (§2.1)"
                )


def check_fallback_discipline(sheet: Stylesheet, failures: list[str]) -> None:
    """S4: colour fallbacks are prohibited; documented non-colour ones required.

    A token with no documented upstream default cannot be decided here -- §10
    lists those defaults as open -- so only the documented ones are enforced.
    """

    for declaration in sheet.authored():
        colour_context = is_colour_property(declaration.property)
        for token, fallback in var_calls(declaration.value):
            if fallback is not None and (colour_context or token.startswith("--color-")):
                failures.append(
                    f"S4 {declaration.where}: `var({token}, {fallback})` supplies a "
                    "fallback for a colour token; a missing colour token must fail "
                    "visibly rather than silently escape the theme (§2.3)"
                )
                continue
            documented = DOCUMENTED_DEFAULTS.get(token)
            if documented is None:
                continue
            if fallback is None:
                failures.append(
                    f"S4 {declaration.where}: `var({token})` omits the required "
                    f"fallback; §2.3 requires it to equal the documented default "
                    f"`{documented}`"
                )
            elif " ".join(fallback.split()) != documented:
                failures.append(
                    f"S4 {declaration.where}: `var({token}, {fallback})` differs from "
                    f"the documented upstream default `{documented}` (§2.3, §3)"
                )


def check_no_typeface(sheet: Stylesheet, failures: list[str]) -> None:
    """S5: no `font-family` except the bare `monospace` keyword (§6.1)."""

    for declaration in sheet.authored():
        if declaration.property != "font-family":
            continue
        if declaration.cleaned() != "monospace":
            failures.append(
                f"S5 {declaration.where}: declares `font-family: "
                f"{declaration.cleaned()}` in `{declaration.selector}`; Chromium's "
                "WebUI font selection is localised and Sunshine must inherit it "
                "(§6.1). Only the bare keyword `monospace` is permitted"
            )


def check_type_scale(sheet: Stylesheet, failures: list[str]) -> None:
    """S6: font sizes come from §6.2's scale, in rem, without `!important`."""

    for declaration in sheet.authored():
        if declaration.property in TYPOGRAPHY_PROPERTIES and declaration.important:
            failures.append(
                f"S6 {declaration.where}: `!important` on the typography "
                f"declaration `{declaration.property}` (§6.2)"
            )
        if declaration.property != "font-size":
            continue
        value = declaration.cleaned()
        if value in ("inherit", "initial", "unset", "revert"):
            continue
        if value.startswith("clamp("):
            continue  # S7 owns the fluid step
        if PX_IN_VALUE.search(value):
            failures.append(
                f"S6 {declaration.where}: `font-size: {value}` is in px; it ignores "
                "the user's browser font-size setting and breaks WCAG 1.4.4 (§6.2)"
            )
            continue
        match = REM_VALUE.fullmatch(value)
        if not match:
            failures.append(
                f"S6 {declaration.where}: `font-size: {value}` is not a rem value "
                "from the §6.2 scale"
            )
            continue
        size = float(match.group(1))
        if size < SMALLEST_REM:
            failures.append(
                f"S6 {declaration.where}: `font-size: {value}` is below the "
                f"smallest permitted step, {SMALLEST_REM}rem (§6.2)"
            )
        elif not any(abs(size - step) < 1e-9 for step in TYPE_SCALE_REM):
            failures.append(
                f"S6 {declaration.where}: `font-size: {value}` is off the §6.2 "
                f"scale ({', '.join(f'{step:g}rem' for step in TYPE_SCALE_REM)})"
            )


def _states_the_band(rule: Rule | None) -> bool:
    """§6.3: the fluid band must be stated where the declaration lives.

    Deliberately loose about wording and strict about substance: a comment on
    the rule has to carry a px figure and a second number, which is the least a
    reader needs to check the band without deriving it.
    """

    if rule is None:
        return False
    for comment in rule.comments:
        if "px" in comment and len(re.findall(r"\d+(?:\.\d+)?", comment)) >= 2:
            return True
    return False


def check_clamp_bounding(sheet: Stylesheet, failures: list[str]) -> None:
    """S7: the four conditions of §6.3, plus the stated fluid band."""

    by_declaration = {
        id(declaration): rule
        for rule in sheet.rules
        for declaration in rule.declarations
    }

    for declaration in sheet.authored():
        value = declaration.cleaned()
        if declaration.property != "font-size" or not value.startswith("clamp("):
            continue
        parts = _split_top_level(value[len("clamp("):-1] if value.endswith(")") else value)
        if len(parts) != 3:
            failures.append(f"S7 {declaration.where}: `{value}` is not a three-term clamp()")
            continue
        low, preferred, high = parts

        bounds = [REM_VALUE.fullmatch(low), REM_VALUE.fullmatch(high)]
        if not all(bounds):
            failures.append(
                f"S7 {declaration.where}: `{value}` bounds must both be in rem; a "
                "viewport-unit bound is unbounded with respect to the user's "
                "font-size setting (§6.3.1)"
            )
            continue
        minimum, maximum = float(bounds[0].group(1)), float(bounds[1].group(1))

        fluid = VIEWPORT_VALUE.fullmatch(preferred)
        if not fluid:
            failures.append(
                f"S7 {declaration.where}: the preferred term `{preferred}` may use "
                "vw or vi and nothing else (§6.3.2)"
            )
            continue

        if minimum <= 0 or maximum < minimum:
            failures.append(f"S7 {declaration.where}: `{value}` has no ascending bounds")
            continue
        if maximum / minimum > 2:
            failures.append(
                f"S7 {declaration.where}: `{value}` spans max/min = "
                f"{maximum / minimum:.2f}; above 2 one declaration is serving two "
                "roles and should be two steps (§6.3.3)"
            )

        coefficient = float(fluid.group(1)) / 100.0
        band = (minimum * ROOT_FONT_PX / coefficient, maximum * ROOT_FONT_PX / coefficient)
        if band[0] >= 1920 or band[1] <= 360:
            failures.append(
                f"S7 {declaration.where}: `{value}` is fluid only between "
                f"{band[0]:.0f} and {band[1]:.0f} CSS px, which does not overlap the "
                "supported 360-1920 range; it is a constant written as a function "
                "(§6.3.4)"
            )

        if not _states_the_band(by_declaration.get(id(declaration))):
            failures.append(
                f"S7 {declaration.where}: `{value}` does not state its fluid band "
                f"where the declaration lives; it is fluid between {band[0]:.0f} and "
                f"{band[1]:.0f} CSS px at a {ROOT_FONT_PX:.0f}px root (§6.3)"
            )


def recorded_r10_weights(root: Path) -> set[str]:
    """Weights a decision record settles by citing R10 (§11 change control)."""

    recorded: set[str] = set()
    directory = root / "docs/decisions"
    if not directory.is_dir():
        return recorded
    for document in sorted(directory.glob("*.md")):
        text = document.read_text(encoding="utf-8")
        if "R10" not in text:
            continue
        for weight in re.findall(r"(?<![\w.-])(\d{3})(?![\w.-])", text):
            recorded.add(weight)
    return recorded


def check_weight_resolvability(sheet: Stylesheet, root: Path, failures: list[str]) -> None:
    """S8: a weight outside {400, 500, 600, 700} without a recorded R10 result."""

    recorded = recorded_r10_weights(root)
    for declaration in sheet.authored():
        if declaration.property != "font-weight":
            continue
        value = declaration.cleaned().lower()
        if value in ("inherit", "initial", "unset", "revert"):
            continue
        weight = WEIGHT_KEYWORDS.get(value, value)
        if weight in RESOLVABLE_WEIGHTS or weight in recorded:
            continue
        failures.append(
            f"S8 {declaration.where}: `font-weight: {declaration.cleaned()}` in "
            f"`{declaration.selector}` is outside {{400, 500, 600, 700}} and no "
            "decision record reports an R10 result for it; if the UI font has no "
            "continuous weight axis the value snaps and the declaration is a lie "
            "about the rendered result (§6.2)"
        )


def check_direction_declared(sheet: Stylesheet, failures: list[str]) -> None:
    """S9: a lockup applying a logical inline property must declare `direction`.

    Judged per element rather than per rule: the contract says "on that same
    element", and two rules may target one lockup.
    """

    for lockup in LOCKUP_SET:
        pattern = re.compile(rf"(?<![\w-]){re.escape(lockup)}(?![\w-])")
        rules = [
            rule for rule in sheet.rules
            if rule.complete and rule.authored and pattern.search(rule.selector)
        ]
        if not rules:
            continue
        declarations = [d for rule in rules for d in rule.declarations]
        logical = [
            d for d in declarations
            if d.property in LOGICAL_INLINE_PROPERTIES
            or (d.property == "text-align" and d.cleaned() in ("start", "end"))
        ]
        if not logical:
            continue
        if any(d.property == "direction" for d in declarations):
            continue
        failures.append(
            f"S9 {logical[0].where}: `{lockup}` applies `{logical[0].property}` "
            "without declaring `direction` on the same element; a non-translated "
            "lockup that inherits direction from the UI locale mirrors its "
            "compensation and not its glyphs (§7.2)"
        )


def check_no_forced_colour_override(sheet: Stylesheet, failures: list[str]) -> None:
    """S10: forced colours and increased contrast are Chromium's to decide."""

    for declaration in sheet.authored():
        if declaration.property == "forced-color-adjust":
            failures.append(
                f"S10 {declaration.where}: declares `forced-color-adjust` in "
                f"`{declaration.selector}`; no Sunshine content outranks a user's "
                "stated accessibility need (§5.2)"
            )
            continue

        forced = in_at_rule(declaration, "forced-colors:active")
        contrast = in_at_rule(declaration, "prefers-contrast:more")
        scheme = in_at_rule(declaration, "prefers-color-scheme")
        # Only appearance is forbidden here. §5.2 explicitly permits a
        # non-colour response, such as taking a border from 1px to 2px, so a
        # `--sun-*` token that is not a colour token is left alone.
        appearance = (
            is_colour_property(declaration.property)
            or (forced and declaration.property in SHADOW_PROPERTIES)
        )
        if (forced or contrast) and appearance:
            block = "forced-colors: active" if forced else "prefers-contrast: more"
            failures.append(
                f"S10 {declaration.where}: `{declaration.property}` inside a "
                f"@media ({block}) block reintroduces Sunshine appearance where "
                "Chromium and the user agent own the palette (§5.2)"
            )
        elif scheme and declaration.property.startswith(SUNSHINE_COLOUR_PREFIX):
            failures.append(
                f"S10 {declaration.where}: `{declaration.property}` is overridden "
                "inside a @media (prefers-color-scheme) block; a token that needs a "
                "second palette is a reference failure, not a mode failure (§2.2(4))"
            )


def check_reduced_motion(sheet: Stylesheet, failures: list[str]) -> None:
    """S11: every motion declaration needs a neutralising counterpart.

    The counterpart's value is not judged -- "reduced to an opacity or colour
    change of at most 200 ms" is not decidable from the declaration alone -- only
    that the same selector redeclares the same property under reduce.
    """

    reduce_blocks: dict[str, set[str]] = {}
    for rule in sheet.rules:
        if not any("prefers-reduced-motion:reduce" in "".join(p.split()).lower()
                   for p in rule.at_rules):
            continue
        target = reduce_blocks.setdefault(normalised_selector(rule.selector), set())
        target.update(declaration.property for declaration in rule.declarations)

    for declaration in sheet.authored():
        motion = declaration.property.startswith(MOTION_PREFIXES)
        smooth = declaration.property == "scroll-behavior" and declaration.cleaned() == "smooth"
        if not (motion or smooth):
            continue
        if motion and declaration.cleaned().lower() in ("none", "0s", "0ms", "initial", "unset"):
            continue  # a declaration that switches motion off is not motion
        if in_at_rule(declaration, "prefers-reduced-motion:reduce"):
            continue
        selector = normalised_selector(declaration.selector)
        neutralisers = reduce_blocks.get(selector, set())
        if smooth:
            satisfied = "scroll-behavior" in neutralisers
        else:
            satisfied = any(
                other.startswith(MOTION_PREFIXES) and other.split("-")[0] == declaration.property.split("-")[0]
                for other in neutralisers
            )
        if not satisfied:
            failures.append(
                f"S11 {declaration.where}: `{declaration.property}` on `{selector}` "
                "has no neutralising declaration under @media "
                "(prefers-reduced-motion: reduce) (§8.1)"
            )


def check_focus_not_suppressed(sheet: Stylesheet, failures: list[str]) -> None:
    """S12: no suppressed focus indicator, and no positive tabindex (§8.2)."""

    for rule in sheet.rules:
        for declaration in rule.declarations:
            if not declaration.authored or declaration.property != "outline":
                continue
            if declaration.cleaned() not in ("none", "0"):
                continue
            if not rule.complete:
                continue  # the replacement may sit outside the hunk window
            replacement = any(
                other is not declaration
                and (
                    other.property == "box-shadow"
                    or (other.property.startswith("outline")
                        and other.cleaned() not in ("none", "0"))
                )
                for other in rule.declarations
            )
            if not replacement:
                failures.append(
                    f"S12 {declaration.where}: `outline: {declaration.cleaned()}` in "
                    f"`{rule.selector}` removes the focus indicator with no at-least-"
                    "as-visible replacement in the same rule (§8.2)"
                )

    for hunk in sheet.hunks:
        for line in hunk.lines:
            if line.origin != "added":
                continue
            for value in TABINDEX.findall(line.text):
                if int(value) > 0:
                    failures.append(
                        f"S12 {hunk.patch}:{line.number}: sets tabindex={value} in "
                        f"{hunk.path}; positive tabindex is prohibited, focus order "
                        "is DOM order (§8.2)"
                    )


def validate(root: Path = ROOT) -> list[str]:
    """S2 through S12. Offline by construction: nothing here reads the network."""

    sheet = read_stylesheets(root)
    failures: list[str] = []
    check_no_literal_colours(sheet, failures)
    check_no_token_reassignment(sheet, failures)
    check_fallback_discipline(sheet, failures)
    check_no_typeface(sheet, failures)
    check_type_scale(sheet, failures)
    check_clamp_bounding(sheet, failures)
    check_weight_resolvability(sheet, root, failures)
    check_direction_declared(sheet, failures)
    check_no_forced_colour_override(sheet, failures)
    check_reduced_motion(sheet, failures)
    check_focus_not_suppressed(sheet, failures)
    return failures


# --------------------------------------------------------------------------
# S1, the one check that needs the pinned sources
# --------------------------------------------------------------------------


def consumed_tokens(root: Path = ROOT) -> dict[str, set[str]]:
    """Upstream tokens Sunshine CSS reads, mapped to where each is read."""

    consumed: dict[str, set[str]] = {}
    for declaration in read_stylesheets(root).authored():
        for token, _fallback in var_calls(declaration.value):
            if token.startswith(UPSTREAM_TOKEN_PREFIXES):
                consumed.setdefault(token, set()).add(declaration.where)
    return consumed


def colour_id_for(token: str) -> str:
    """`--color-new-tab-page-primary-foreground` -> `kColorNewTabPagePrimaryForeground`.

    Chromium generates the CSS custom property from the `ColorId` enumerator, so
    the enumerator is where existence is proven. The stylesheet is not: a
    `--color-*` token can be entirely valid while appearing in no CSS file at
    all, which is the false positive `verify_pinned_upstream` was written to
    avoid.
    """

    return "kColor" + "".join(part.capitalize() for part in token[len("--color-"):].split("-"))


def token_sources(token: str) -> tuple[tuple[str, ...], str]:
    if token.startswith("--color-"):
        return COLOUR_ID_HEADERS, colour_id_for(token)
    if token.startswith("--ntp-"):
        return NTP_STYLESHEETS, f"{token}:"
    return CR_STYLESHEETS, f"{token}:"


def authored_selectors(root: Path = ROOT) -> dict[str, set[tuple[str, str]]]:
    """Per stylesheet, the (selector, where) of every rule Sunshine adds whole.

    A rule counts only when its opening brace was added rather than quoted as
    context -- a declaration Sunshine adds inside an upstream rule is not a new
    selector and cannot duplicate anything.
    """

    found: dict[str, set[tuple[str, str]]] = {}
    for rule in read_stylesheets(root).rules:
        if not rule.authored or not rule.complete or rule.at_rules:
            continue
        opened_by_sunshine = any(
            line.origin == "added" and "{" in line.text and rule.selector.split()[0] in line.text
            for hunk in [h for h in read_stylesheets(root).hunks if h.path == rule.path]
            for line in hunk.lines
        )
        if not opened_by_sunshine:
            continue
        for part in rule.selector.split(","):
            part = normalised_selector(part)
            if part:
                found.setdefault(rule.path, set()).add((part, rule.patch))
    return found


def upstream_selectors(text: str) -> set[str]:
    """Every selector the upstream stylesheet declares, at-rule bodies included.

    Deliberately textual, in the same spirit as `byte_arrays()`: the question is
    what stylelint will see as a repeated selector, and stylelint reads text.
    """

    found = set()
    for match in re.finditer(r"([^{}]+)\{[^{}]*\}", CSS_COMMENTS.sub("", text)):
        prelude = match.group(1).rsplit("}", 1)[-1].rsplit(";", 1)[-1]
        if "@" in prelude:
            continue
        for part in prelude.split(","):
            part = normalised_selector(part)
            if part:
                found.add(part)
    return found


def check_no_duplicate_selectors(
    root: Path = ROOT,
    read: object = None,
    source: str = "googlesource",
) -> list[str]:
    """S13: a rule Sunshine adds must not repeat a selector upstream declares.

    **This check exists because its absence cost a build.** Patch 0022 added a
    second `#inputWrapper { }` to `ntp_searchbox.css` -- deliberately, so that
    no upstream line was edited and the hunk survived a roll. Every guard in
    this repository passed. `verify_pinned_upstream` proved the patch applies to
    the real pinned tree. S1 through S12 passed. The native build then failed in
    twenty seconds:

        Unexpected duplicate selector "#inputWrapper", first used at line 84
        no-duplicate-selectors

    Chromium lints Sunshine's CSS with its own stylelint config, and nothing
    here had ever asked whether Chromium would accept what Sunshine wrote. Every
    check answered the question it was asked and none of them was that one.

    The scope is honest about what it covers: this is `no-duplicate-selectors`
    against the pinned upstream file, not a local stylelint. It catches the
    defect that happened, at the cost of one HTTP read per patched stylesheet.
    """

    if read is None:
        version = upstream.pinned_version(root)

        def read(path: str) -> str:  # noqa: A001 - the parameter is the seam
            return upstream.fetch(source, version, path)

    # Only stylesheets upstream has. A `.css` the stack creates is Sunshine's
    # own file, has no upstream to duplicate, and asking for one returns 404 --
    # which is how the first run of this check failed on the account surface.
    created = manifest.created_paths(root, manifest.read_manifest(root))

    failures: list[str] = []
    for path, selectors in sorted(authored_selectors(root).items()):
        if path in created:
            continue
        existing = upstream_selectors(read(path))
        for selector, patch in sorted(selectors):
            if selector in existing:
                failures.append(
                    f"S13 {patch}: adds a rule for `{selector}` to {path}, which "
                    "the upstream stylesheet already declares. Chromium's "
                    "stylelint config runs `no-duplicate-selectors` over this "
                    "folder and fails the build on it -- add the declarations to "
                    "the existing rule instead"
                )
    return failures


def check_token_provenance(
    root: Path = ROOT,
    read: object = None,
    source: str = "googlesource",
) -> list[str]:
    """S1: every upstream token Sunshine reads exists at the pinned revision.

    `read` is a `path -> text` callable; the default reads the pinned revision
    through `verify_pinned_upstream.fetch`, which is the mechanism CI already
    trusts. Passing a stub is what keeps the test suite offline.
    """

    if read is None:
        version = upstream.pinned_version(root)

        def read(path: str) -> str:  # noqa: A001 - the parameter is the seam
            return upstream.fetch(source, version, path)

    failures: list[str] = []
    cache: dict[str, str] = {}
    for token, sites in sorted(consumed_tokens(root).items()):
        paths, needle = token_sources(token)
        for path in paths:
            if path not in cache:
                cache[path] = read(path)
            if needle in cache[path]:
                break
        else:
            failures.append(
                f"S1 {token}: consumed by Sunshine CSS ({', '.join(sorted(sites))}) "
                f"but absent from the pinned revision; looked for {needle!r} in "
                f"{', '.join(paths)}"
            )
    return failures


def main() -> int:
    parser = argparse.ArgumentParser(description="Design-system source checks S1-S13.")
    parser.add_argument(
        "--source",
        choices=sorted(upstream.SOURCES),
        default="googlesource",
        help="where to read the pinned revision for S1; the default is authoritative",
    )
    parser.add_argument(
        "--offline",
        action="store_true",
        help="run S2-S12 only, skipping the pinned-source checks S1 and S13",
    )
    arguments = parser.parse_args()

    failures = validate()
    checked = "S2-S12"
    unreachable = ""
    if not arguments.offline:
        try:
            failures += check_token_provenance(source=arguments.source)
            failures += check_no_duplicate_selectors(source=arguments.source)
            checked = "S1-S13"
        except upstream.UpstreamCheckError as error:
            # Report what the offline checks found regardless; an unreachable
            # pinned source is a reason S1 has no verdict, not a reason to
            # withhold the eleven verdicts already in hand.
            unreachable = f"S1 could not read the pinned revision: {error}"

    if failures or unreachable:
        print("\n".join(failures + ([unreachable] if unreachable else [])), file=sys.stderr)
        print(f"\n{len(failures)} design-system criteria failing.", file=sys.stderr)
        return 1
    print(f"Design-system check passed: {checked} over Sunshine-authored CSS in the patch stack.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
