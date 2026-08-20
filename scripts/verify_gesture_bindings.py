#!/usr/bin/env python3
"""Hold the mouse-gesture patch to the contract that specifies it.

`docs/GESTURE_CONTRACT.md` is unusually specific for a document written before
any code: it names the commands a binding may resolve, the numbers that decide
recognition, the targets that suppress it, and -- in invariant 5 -- the one
thing the feature must never do, which is reach navigation itself. All of that
is decidable from the patch text, and none of it is decidable from a build.

What is checked, and which rule each check claims:

  * a binding resolves only commands `first_party/commands.json` registers,
    which invariant 6 makes a build failure rather than a special case;
  * the activation distance, its bounds and the direction ratio are the
    contract's numbers, not near-misses (section 3.2);
  * the suppression predicate consults every target category section 3.1 names,
    each by the ContextMenuParams field that carries it;
  * the recogniser reaches no navigation and no Chromium command identifier --
    invariant 5, and the three-stage separation in section 1;
  * dispatch asks the command layer whether the command is available before
    running it (invariant 7);
  * the recogniser observes and never consumes: its event entry point returns
    void, and nothing in the patch installs a handler that could swallow an
    event (section 1).

The last one is the one worth being explicit about. Chromium offers a hook that
*can* consume a mouse event -- `RenderWidgetHost::AddMouseEventCallback`, whose
callback returns bool -- and using it would have been the obvious way to
suppress a context menu. The contract forbids it, so this refuses it by name
rather than trusting that nobody reaches for it later.

Enforces: GA-16
"""

from __future__ import annotations

import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import verify_patch_references  # noqa: E402

HEADER = "chrome/browser/ui/sunshine/mouse_gesture.h"
SOURCE = "chrome/browser/ui/sunshine/mouse_gesture.cc"
BUILD = "chrome/browser/ui/sunshine/BUILD.gn"
# Dispatch lives in `Browser::HandleContextMenu`, which is upstream's own
# extension point for "the embedder wants to handle this menu".
#
# A cheaper hook was tried and rejected on evidence.
# `ChromeWebContentsViewDelegateViews::ShowContextMenu` sits in a file that did
# not change at all between the pinned revision and the next milestone, where
# browser.cc changed 1497 lines, and moving the decision there took the roll
# cost of this patch from four rejected hunks to two. It was still wrong:
# dispatching needs `chrome/browser/ui/browser_commands.h`, and that target's
# own BUILD.gn states it has no circular dependency back into
# //chrome/browser/ui:ui. Buying two hunks a milestone with a dependency cycle
# is not a trade, and `scripts/measure_rebase_cost.py` is what made the price
# of the correct answer a number rather than a worry.
DISPATCH = "chrome/browser/ui/browser.cc"
CONTRACT = "docs/GESTURE_CONTRACT.md"

# `inline constexpr char kBackCommand[] = "browser.back";`
COMMAND_LITERAL = re.compile(r'inline constexpr char k\w+Command\[\] = "([^"]+)";')

# The numbers section 3.2 fixes, and the constant each must be spelled as.
NUMBERS = {
    "kDefaultActivationDistance": 200,
    "kMinimumActivationDistance": 20,
    "kMaximumActivationDistance": 600,
    "kDirectionRatio": 2,
}
NUMBER = re.compile(r"inline constexpr int (?P<name>k\w+) = (?P<value>\d+);")

# Section 3.1's target list, and the ContextMenuParams field that answers for
# each. Written as pairs so a failure names the *rule* and not just a missing
# identifier -- "no check for a link" is actionable; "src_url missing" is not.
TARGETS = (
    ("a link", "link_url"),
    ("a link the renderer did not filter", "unfiltered_link_url"),
    ("an image or media source", "src_url"),
    ("image contents", "has_image_contents"),
    ("an editable field", "is_editable"),
    ("a form control", "form_control_type"),
    ("a selection", "selection_text"),
    ("a media element", "media_type"),
)

# Reaching navigation directly, in any of the shapes that would do it.
FORBIDDEN_IN_RECOGNISER = (
    "GoBack",
    "GoForward",
    "NavigationController",
    "GetController",
    "IDC_",
    "chrome/browser/ui/browser",
)

# The hook that can swallow an event. Named so that choosing it later is a
# failing check rather than a quiet change of contract.
CONSUMING_HOOK = "AddMouseEventCallback"


def added_lines(root: Path, path: str) -> str:
    """Every line the stack adds to one upstream file, in patch order."""

    collected: list[str] = []
    series = (root / "downstream/patches/series").read_text(encoding="utf-8").split()
    for name in series:
        text = (root / "downstream/patches" / name).read_text(encoding="utf-8")
        inside = False
        for line in text.splitlines():
            if line.startswith("diff --git "):
                inside = line.endswith(f" b/{path}")
                continue
            if inside and line.startswith("+") and not line.startswith("+++"):
                collected.append(line[1:])
    return "\n".join(collected)


def check(root: Path = ROOT) -> list[str]:
    failures: list[str] = []
    files = verify_patch_references.stack_files(root)

    for path in (HEADER, SOURCE, BUILD):
        if path not in files:
            failures.append(f"{path}: the patch stack does not create it")
    if failures:
        return failures

    header = "\n".join(files[HEADER])
    source = "\n".join(files[SOURCE])
    build = "\n".join(files[BUILD])
    # `stack_files` replays only the files the stack creates -- it has no copy
    # of upstream to replay a modification against. The dispatch lives in an
    # upstream file, so what is read here is what the patch *adds* to it, which
    # is the whole of Sunshine's part of that file and the only part these
    # rules speak about.
    dispatch = added_lines(root, DISPATCH)
    if not dispatch:
        failures.append(f"{DISPATCH}: the patch stack adds nothing to it")
        return failures

    # -- invariant 6: a binding names a registered command --------------------
    registered = {
        command["id"]
        for command in json.loads(
            (root / "first_party/commands.json").read_text(encoding="utf-8")
        )["commands"]
    }
    bound = set(COMMAND_LITERAL.findall(header))
    if not bound:
        failures.append(f"{HEADER}: declares no command literal, so nothing binds")
    for command in sorted(bound - registered):
        failures.append(
            f"{HEADER}: binds {command!r}, which first_party/commands.json does "
            "not register; GESTURE invariant 6"
        )

    # The contract's section 4 is the complete binding set for this wave, so a
    # third command in the header is a binding the document has not agreed to.
    documented = set(
        re.findall(r"`(browser\.\w+)`", _section(root, "## 4. Bindings"))
    )
    if bound != documented:
        failures.append(
            f"{CONTRACT} section 4 binds {sorted(documented)}, {HEADER} declares "
            f"{sorted(bound)}"
        )

    # -- section 3.2: the numbers are the contract's --------------------------
    found = {
        match.group("name"): int(match.group("value"))
        for match in NUMBER.finditer(header)
    }
    for name, expected in NUMBERS.items():
        if found.get(name) != expected:
            failures.append(
                f"{HEADER}: {name} is {found.get(name)}, and GESTURE section 3.2 "
                f"says {expected}"
            )

    # -- section 3.1: every target category is consulted ----------------------
    for rule, field in TARGETS:
        if field not in source:
            failures.append(
                f"{SOURCE}: nothing suppresses on {rule} -- no use of "
                f"`{field}`; GESTURE section 3.1"
            )

    # -- invariant 5 and section 1: the recogniser reaches nothing ------------
    for forbidden in FORBIDDEN_IN_RECOGNISER:
        for path, text in ((HEADER, header), (SOURCE, source)):
            if forbidden in text:
                failures.append(
                    f"{path}: names {forbidden!r}. Recognition and binding may "
                    "not reach navigation or a Chromium command identifier; "
                    "GESTURE invariant 5"
                )
    # Quoted entries only. The comment in that file explains that it depends on
    # no part of //chrome/browser/ui, and reading prose would make the
    # explanation trip the rule it explains.
    for dependency in re.findall(r'"(//[^"]+)"', build):
        if dependency.startswith("//chrome/browser/ui"):
            failures.append(
                f"{BUILD}: depends on {dependency}. A target that can see "
                "Browser can navigate one; GESTURE section 1"
            )

    # -- section 1: it observes, and cannot consume ---------------------------
    if CONSUMING_HOOK in source or CONSUMING_HOOK in dispatch:
        failures.append(
            f"mouse gesture: uses {CONSUMING_HOOK}, whose callback returns bool "
            "and can swallow an event. Section 1 yields event delivery to "
            "Chromium"
        )
    if not re.search(r"void MouseGesture::OnMouseEvent\(", source):
        failures.append(
            f"{SOURCE}: the event entry point must return void, so that "
            "observation cannot become consumption; GESTURE section 1"
        )

    # -- invariant 7: availability is the command layer's to decide -----------
    if "IsCommandEnabled" not in dispatch:
        failures.append(
            f"{DISPATCH}: dispatches without asking the command layer whether "
            "the command is available; GESTURE invariant 7"
        )

    print(f"mouse gesture: {len(bound)} binding(s), all registered.")
    return failures


def _section(root: Path, heading: str) -> str:
    text = (root / CONTRACT).read_text(encoding="utf-8")
    start = text.index(heading) + len(heading)
    following = text.find("\n## ", start)
    return text[start:] if following == -1 else text[start:following]


def main() -> int:
    failures = check()
    for failure in failures:
        print(failure)
    if failures:
        print(f"{len(failures)} mouse gesture failure(s).")
        return 1
    print("Mouse gesture bindings passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
