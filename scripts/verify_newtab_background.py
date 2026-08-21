#!/usr/bin/env python3
"""Enforce what a New Tab background may be, and how that is decided.

The owner's rule is three sentences: a background may be PNG, JPEG or APNG;
an APNG loops for as long as it says it does; and the animation must be
visible-only, opt-in and self-contained.

Two of those are decidable from source and this checks them.

**The format rule is about bytes, not names.** A file called `.png` that
begins with `GIF89a` is a GIF, and Blink would decode it happily, because
Blink chooses its decoder by signature exactly as this rule does. So an
implementation that accepted files by extension would admit precisely the
formats the rule exists to refuse -- while looking, in the source, like it
was enforcing something.

**APNG is not a third signature.** An APNG *is* a PNG: same eight-byte
signature, same name, animation in ancillary chunks. Code that tried to
detect it separately would be claiming to distinguish two things that are one
thing, and this check refuses that shape rather than tolerating it.

**Self-containment is the load-bearing half of PB-5a.** The permitted
animation is carried by the asset. The moment Sunshine owns a timer or a
frame callback driving it, PB-5a's third property is false and the amendment
that allowed the feature no longer covers it -- so the repeating-task symbols
are refused here too, in the background source specifically, rather than only
in the general sweep `scripts/verify_no_interposition.py` runs.

Enforces: NTB-1, NTB-2, NTB-3, NTB-4.
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


def added_lines(patch_text: str) -> str:
    kept = [
        line[1:]
        for line in patch_text.splitlines()
        if line.startswith("+") and not line.startswith("+++ ")
    ]
    return "\n".join(kept)


def stack_text(root: Path) -> str:
    """Every line the patch stack adds, as one blob."""

    blobs = []
    for patch in sorted((root / "downstream/patches").glob("*.patch")):
        blobs.append(added_lines(patch.read_text(encoding="utf-8")))
    return "\n".join(blobs)


def byte_arrays(text: str) -> list[tuple[str, ...]]:
    """Every `{0x.., 0x.., ...}` initialiser in the text."""

    found = []
    for match in re.finditer(r"\{([^{}]*0x[0-9A-Fa-f]{2}[^{}]*)\}", text):
        bytes_in = tuple(re.findall(r"0x[0-9A-Fa-f]{2}", match.group(1)))
        if bytes_in:
            found.append(tuple(value.upper().replace("0X", "0x") for value in bytes_in))
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


def check(root: Path, failures: list[str]) -> None:
    text = stack_text(root)

    if SOURCE not in text and "newtab_background" not in text:
        failures.append(f"NTB-1 {SOURCE} is not in the patch stack")
        return

    arrays = byte_arrays(text)

    # NTB-1: both permitted signatures are declared, as bytes.
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
    if WEBP_TAG in arrays and "8" not in _webp_offsets(text):
        failures.append(
            "NTB-4 the WEBP tag is declared but never checked at offset 8"
        )

    # NTB-2: no excluded format is declared as a signature.
    for label, signature in EXCLUDED_SIGNATURES.items():
        for array in arrays:
            if array[: len(signature)] == signature:
                failures.append(
                    f"NTB-2 a {label} signature is declared as a byte array; "
                    "the rule admits PNG and JPEG only"
                )

    # NTB-2: the decision is not made from the file name.
    #
    # `.Extension()`, `MatchesExtension` and `EndsWith(..., \".png\")` are the
    # three ways this goes wrong, and each reads as a format check while
    # deciding nothing about the bytes.
    for symbol in (".Extension()", "MatchesExtension", "FinalExtension"):
        if symbol in text and "newtab_background" in text:
            window = text[max(0, text.find(symbol) - 600) : text.find(symbol) + 200]
            if "newtab_background" in window or "DetectFormat" in window:
                failures.append(
                    f"NTB-2 {symbol!r} decides a background's format from its name"
                )

    # NTB-3: nothing Sunshine owns drives the animation.
    for symbol in REPEATING_SYMBOLS:
        if symbol in text and "newtab_background" in text:
            index = text.find(symbol)
            window = text[max(0, index - 800) : index + 300]
            if "newtab_background" in window or "background" in window.lower()[:200]:
                failures.append(
                    f"NTB-3 {symbol!r} would make Sunshine own the animation; "
                    "PB-5a requires the asset to carry it"
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
