"""Tests for the New Tab background format check.

The rule is that a background is PNG, JPEG or WebP, decided from the file's
own bytes. Every way of getting that wrong looks correct in a diff -- an
extension check reads like a format check, a GIF signature reads like one more
constant, and a timer driving frames reads like an implementation detail
rather than the thing that falsifies PB-5a. So each is injected here, because
a check that only ever passes proves nothing.
"""

from pathlib import Path
import shutil
import sys
import tempfile
import unittest

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY_ROOT / "scripts"))

import verify_newtab_background as checker  # noqa: E402

PATCH = "downstream/patches/0020-sunshine-newtab-background-format.patch"
SEARCHBOX_PATCH = "downstream/patches/0022-sunshine-searchbox-state.patch"
SETTINGS_PATCH = "downstream/patches/0024-sunshine-settings-surface.patch"


class NewTabBackgroundTests(unittest.TestCase):
    def setUp(self) -> None:
        directory = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, directory, True)
        self.root = Path(directory) / "repo"
        shutil.copytree(
            REPOSITORY_ROOT,
            self.root,
            ignore=shutil.ignore_patterns(".git", "__pycache__", "chromium"),
        )
        self.patch = self.root / PATCH

    def edit(self, old: str, new: str) -> None:
        text = self.patch.read_text(encoding="utf-8")
        self.assertIn(old, text, f"{old!r} is not in the patch to edit")
        self.patch.write_text(text.replace(old, new), encoding="utf-8")

    def assertRejected(self, needle: str) -> None:
        failures = checker.validate(self.root)
        self.assertTrue(failures, "the violation was accepted")
        self.assertTrue(any(needle in f for f in failures), f"{needle!r} not in {failures}")

    def test_the_repository_passes_today(self) -> None:
        """Enforces: NTB-1, NTB-2, NTB-3."""

        self.assertEqual([], checker.validate(REPOSITORY_ROOT))

    # --- NTB-1: both permitted signatures are declared ----------------------

    def test_dropping_the_png_signature_is_rejected(self) -> None:
        self.edit("0x89, 0x50, 0x4E, 0x47", "0x89, 0x50, 0x4E, 0x48")
        self.assertRejected("PNG signature")

    def test_dropping_the_jpeg_signature_is_rejected(self) -> None:
        self.edit("0xFF, 0xD8, 0xFF", "0xFF, 0xD9, 0xFF")
        self.assertRejected("JPEG signature")

    # --- NTB-2: no excluded format, and no decision by name -----------------

    def test_accepting_gif_is_rejected(self) -> None:
        """The format the owner excluded, added the way it would really be
        added: as one more constant beside the two that belong."""

        self.edit(
            "constexpr uint8_t kJpegSignature[] = {0xFF, 0xD8, 0xFF};",
            "constexpr uint8_t kJpegSignature[] = {0xFF, 0xD8, 0xFF};\n"
            "+constexpr uint8_t kGifSignature[] = {0x47, 0x49, 0x46};",
        )
        self.assertRejected("GIF signature")

    def test_dropping_the_riff_tag_is_rejected(self) -> None:
        self.edit("0x52, 0x49, 0x46, 0x46", "0x52, 0x49, 0x46, 0x47")
        self.assertRejected("RIFF tag")

    # --- NTB-4: WebP is two tags at two offsets -----------------------------

    def test_the_riff_tag_without_the_webp_tag_is_rejected(self) -> None:
        """The bug that looks like a signature check.

        `RIFF` is a container tag, shared with WAV and AVI. A source that
        checked it alone would accept a renamed WAV as a New Tab background
        while reading, in the diff, exactly like a format check -- the same
        failure shape as deciding by extension, one layer down.
        """

        self.edit(
            "constexpr uint8_t kWebpTag[] = {0x57, 0x45, 0x42, 0x50};",
            "constexpr uint8_t kWebpTag[] = {0x57, 0x45, 0x42, 0x51};",
        )
        self.assertRejected("without the WEBP tag")

    def test_never_checking_the_webp_tag_offset_is_rejected(self) -> None:
        """Declaring the tag is not checking it.

        A constant that nothing reads at offset 8 leaves the RIFF-alone bug in
        place, with the evidence of correctness sitting beside it.
        """

        self.edit("constexpr size_t kWebpTagOffset = 8;",
                  "constexpr size_t kWebpTagOffset = 0;")
        self.assertRejected("never checked at offset 8")

    def test_deciding_the_format_from_the_name_is_rejected(self) -> None:
        """The failure that looks most like success.

        `MatchesExtension` reads, in a diff, exactly like a format check. It
        decides nothing about the bytes, so a GIF named `.png` passes it --
        and Blink then decodes the GIF, because Blink reads the same
        signature this rule was supposed to read.
        """

        self.edit(
            "Format DetectFormat(base::span<const uint8_t> head) {",
            "bool LooksLikePng(const base::FilePath& path) {\n"
            "+  return path.MatchesExtension(FILE_PATH_LITERAL(\".png\"));\n"
            "+}\n"
            "+\n"
            "+Format DetectFormat(base::span<const uint8_t> head) {",
        )
        self.assertRejected("decides a background's format from its name")

    # --- NTB-3: the asset carries the animation -----------------------------

    def test_a_timer_driving_the_animation_is_rejected(self) -> None:
        """Not a style rule. PB-5a permits this feature only while the asset
        animates itself; a Sunshine-owned timer falsifies the third property
        and the amendment stops covering the feature."""

        self.edit(
            "Format DetectFormat(base::span<const uint8_t> head) {",
            "base::RepeatingTimer* g_newtab_background_frames = nullptr;\n"
            "+\n"
            "+Format DetectFormat(base::span<const uint8_t> head) {",
        )
        self.assertRejected("NTB-3")

    # --- What must stay accepted --------------------------------------------

    def test_naming_an_excluded_format_in_a_comment_is_accepted(self) -> None:
        """The document has to be able to say what it refuses.

        The source already names GIF, WebP and AVIF in a comment explaining
        why they are absent. A rule that could not tell prose from a constant
        would forbid the explanation and leave the next reader guessing.
        """

        self.edit(
            "namespace {",
            "namespace {\n"
            "+\n"
            "+// A GIF begins 0x47 0x49 0x46 and is refused.",
        )
        self.assertEqual([], checker.validate(self.root))

    def test_an_unrelated_timer_elsewhere_in_the_stack_is_accepted(self) -> None:
        """NTB-3 is about the background, not about the whole tree.

        `scripts/verify_no_interposition.py` already sweeps everything for
        repeating tasks. If this check also failed on any timer anywhere, the
        two would be the same check and this one would be noise.
        """

        other = self.root / "downstream/patches/0099-unrelated.patch"
        other.write_text(
            "--- /dev/null\n"
            "+++ b/chrome/browser/ui/sunshine/unrelated.cc\n"
            "+// base::RepeatingTimer timer_;\n",
            encoding="utf-8",
        )
        self.assertEqual([], checker.validate(self.root))


class SearchboxStateTests(unittest.TestCase):
    """NTB-12 and NTB-13: the searchbox's normal state, and its two halves.

    Every mutation below leaves the patch applying cleanly and the page
    rendering. Three of them leave a searchbox that is translucent while it is
    being typed into -- the feature inverted -- and the fourth leaves a rule
    that is valid CSS matching an attribute nothing ever sets. None of them is
    visible to a compiler, to the design-system checks, or to a green build.
    """

    def setUp(self) -> None:
        directory = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, directory, True)
        self.root = Path(directory) / "repo"
        shutil.copytree(
            REPOSITORY_ROOT,
            self.root,
            ignore=shutil.ignore_patterns(".git", "__pycache__", "chromium"),
        )
        self.patch = self.root / SEARCHBOX_PATCH

    def edit(self, old: str, new: str) -> None:
        text = self.patch.read_text(encoding="utf-8")
        self.assertIn(old, text, f"{old!r} is not in the patch to edit")
        self.patch.write_text(text.replace(old, new), encoding="utf-8")

    def assertRejected(self, needle: str) -> None:
        failures = checker.validate(self.root)
        self.assertTrue(failures, "the violation was accepted")
        self.assertTrue(any(needle in f for f in failures), f"{needle!r} not in {failures}")

    def test_the_repository_passes_today(self) -> None:
        """Enforces: NTB-12, NTB-13."""

        self.assertEqual([], checker.validate(REPOSITORY_ROOT))

    def test_inverting_the_state_is_rejected(self) -> None:
        """The whole feature, written backwards, and still valid CSS."""

        self.edit(
            "+:host(:not([has-user-input_])) #inputWrapper:not(:focus-within) {",
            "+:host([has-user-input_]) #inputWrapper:focus-within {",
        )
        self.assertRejected("NTB-12")

    def test_dropping_the_focus_arm_is_rejected(self) -> None:
        self.edit("#inputWrapper:not(:focus-within) {", "#inputWrapper {")
        self.assertRejected(":not(:focus-within)")

    def test_dropping_the_text_arm_is_rejected(self) -> None:
        self.edit(
            "+:host(:not([has-user-input_])) #inputWrapper:not(:focus-within) {",
            "+#inputWrapper:not(:focus-within) {",
        )
        self.assertRejected(":not([has-user-input_])")

    def test_deleting_the_reflection_is_rejected(self) -> None:
        """The dead-arm case: the rule survives, the attribute never arrives.

        This is the defect that shipped once already in this feature, in a
        different file -- a branch that compiled and could not be reached
        because the gate deciding whether it was reached never named it.
        """

        self.edit("+        reflect: true,\n", "")
        self.assertRejected("NTB-13")

    def test_reflecting_without_reading_is_rejected(self) -> None:
        """The mirror image, and the one a roll is likelier to produce.

        A conflict in the stylesheet is resolved by taking upstream's side; the
        script half applies cleanly and stays. What is left is an attribute
        Sunshine puts on an upstream element that nothing reads.
        """

        self.edit(":host(:not([has-user-input_]))", ":host(:not([sunshine-idle]))")
        self.assertRejected("NTB-13")

    def test_an_unrelated_color_mix_is_accepted(self) -> None:
        """NTB-12 judges the searchbox surface, not every derived colour.

        A rule elsewhere in the same stylesheet composing some other token
        through `color-mix()` has nothing to do with which state is written,
        and a check that fired on it would be a check about `color-mix()`.
        """

        self.edit(
            "+:host(:not([has-user-input_])) #inputWrapper:not(:focus-within) {",
            "+.searchbox-icon-button-container:hover {\n"
            "+  background-color: color-mix(in srgb, var(--color-searchbox-foreground) 12%, transparent);\n"
            "+}\n"
            "+\n"
            "+:host(:not([has-user-input_])) #inputWrapper:not(:focus-within) {",
        )
        self.assertEqual([], checker.validate(self.root))



class PickerTests(unittest.TestCase):
    """NTB-11 and NTB-14: the picker, and the names it may write under.

    Both rules span files that no compiler reads together. NTB-14 is three
    lists in one C++ file that have to agree about what a background is called;
    NTB-11 is a refusal travelling from a C++ enum through a .mojom to a
    sentence in TypeScript, and stopping one short of the page is not a build
    error -- it is a person who is told nothing, which is the silence §5 says
    this feature already produces too often.

    Every mutation below compiles, applies, and leaves a picker that appears to
    work.
    """

    def setUp(self) -> None:
        directory = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, directory, True)
        self.root = Path(directory) / "repo"
        shutil.copytree(
            REPOSITORY_ROOT,
            self.root,
            ignore=shutil.ignore_patterns(".git", "__pycache__", "chromium"),
        )
        self.patch = self.root / SETTINGS_PATCH

    def edit(self, old: str, new: str) -> None:
        text = self.patch.read_text(encoding="utf-8")
        self.assertIn(old, text, f"{old!r} is not in the patch to edit")
        self.patch.write_text(text.replace(old, new), encoding="utf-8")

    def assertRejected(self, needle: str) -> None:
        failures = checker.validate(self.root)
        self.assertTrue(failures, "the violation was accepted")
        self.assertTrue(any(needle in f for f in failures), f"{needle!r} not in {failures}")

    def test_the_repository_passes_today(self) -> None:
        """Enforces: NTB-11, NTB-14."""

        self.assertEqual([], checker.validate(REPOSITORY_ROOT))

    # --- NTB-14: the three lists that name a background ---------------------

    def test_a_format_mapped_to_the_wrong_name_is_rejected(self) -> None:
        """The picker writes a WebP as .png; the reader then refuses its bytes,
        and the whole feature fails as "the picker did nothing"."""

        self.edit(
            "    case Format::kWebp:\n+      return kAssetFileNames[2];",
            "    case Format::kWebp:\n+      return kAssetFileNames[0];",
        )
        self.assertRejected("NTB-14")

    def test_an_extension_that_does_not_match_its_name_is_rejected(self) -> None:
        """The dialog offers `jpeg` where the reader looks for `.jpg`, so the
        filter hides the file it exists to show."""

        self.edit('FILE_PATH_LITERAL("jpg")', 'FILE_PATH_LITERAL("jpeg")')
        self.assertRejected("NTB-14")

    def test_a_format_with_no_name_is_rejected(self) -> None:
        self.edit(
            "+    case Format::kJpeg:\n+      return kAssetFileNames[1];\n", "")
        self.assertRejected("NTB-14")

    # --- NTB-11: byte for byte, before it lands, and a reason shown ---------

    def test_a_refusal_the_page_cannot_describe_is_rejected(self) -> None:
        """The browser can produce it; nobody is ever told."""

        self.edit(
            "    case BackgroundOutcome.kWriteFailed:",
            "    case BackgroundOutcome.kNeverMentioned:",
        )
        self.assertRejected("has no sentence for")

    def test_a_result_the_handler_cannot_translate_is_rejected(self) -> None:
        self.edit(
            "+    case sunshine::background::InstallResult::kTooLarge:\n"
            "+      return BackgroundOutcome::kTooLarge;\n",
            "",
        )
        self.assertRejected("does not translate")

    def test_re_encoding_instead_of_copying_is_rejected(self) -> None:
        """A converting picker turns an APNG into a photograph and says
        nothing. It reads, in the diff, exactly like a copy."""

        self.edit(
            "+  if (!base::CopyFile(source, destination)) {",
            "+  if (!gfx::PNGCodec::EncodeBGRA(source, destination)) {",
        )
        self.assertRejected("NTB-11")

    def test_validating_after_the_copy_is_rejected(self) -> None:
        """The subtle one, and the reason the check reads the *last* mention.

        `kUnsupportedFormat` is decided twice -- a file shorter than a
        signature, and a file whose signature is wrong. Moving only the second
        below the copy leaves the first above it, so a check that read the
        first mention accepted a picker that wrote the file and then decided it
        was not allowed.
        """

        self.edit(
            "+  const Format format = DetectFormat(base::as_byte_span(head));\n"
            "+  if (format == Format::kNone) {\n"
            "+    outcome.result = InstallResult::kUnsupportedFormat;\n"
            "+    return outcome;\n"
            "+  }\n",
            "+  const Format format = DetectFormat(base::as_byte_span(head));\n",
        )
        self.edit(
            "+  outcome.result = InstallResult::kInstalled;",
            "+  if (format == Format::kNone) {\n"
            "+    outcome.result = InstallResult::kUnsupportedFormat;\n"
            "+    return outcome;\n"
            "+  }\n"
            "+  outcome.result = InstallResult::kInstalled;",
        )
        self.assertRejected("after base::CopyFile")


if __name__ == "__main__":
    unittest.main()
