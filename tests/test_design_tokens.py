"""Tests for the design-system source checks, S1 to S12.

The whole check turns on one distinction: an added line in a patch is
Sunshine-authored CSS, a context line is upstream's own stylesheet quoted so the
hunk can be located. Chromium's New Tab CSS declares px font sizes and literal
colours by the dozen, so a check that judged context lines would fail the build
on upstream's code and would rightly be deleted. Every criterion below is
therefore tested twice over the same CSS: once as context, where it must stay
silent, and once as an added line, where it must fire.

The fixtures are patches rather than stylesheets on purpose -- the hunk is the
unit the check reads, and its arithmetic, its header section text and its
removed lines are all part of what has to be got right.
"""

from pathlib import Path
import shutil
import sys
import tempfile
import unittest

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY_ROOT / "scripts"))

import patch_manifest as manifest  # noqa: E402
import verify_design_tokens as checker  # noqa: E402

APP_CSS = "chrome/browser/resources/new_tab_page/app.css"
NTP_SEARCHBOX_CSS = "chrome/browser/resources/new_tab_page/ntp_searchbox.css"

# What the pinned revision really contains, reduced to the needles S1 looks for.
# Verified at 152.0.7977.42: the colour ID is in chrome_color_id.h and in no
# stylesheet; both --ntp-* tokens are declared in New Tab Page CSS. The
# ui/color/color_id.h entry carries every enumerator the patch stack's CSS
# resolves to -- the New Tab wordmark reads one token, the Security Center
# reads five -- each copied from the line it occupies at that revision, so the
# stub cannot pass a token the real header would reject.
PINNED = {
    "ui/color/color_id.h": (
        "  E_CPONLY(kColorAlertHighSeverity) \\\n"
        "  E_CPONLY(kColorMidground) \\\n"
        "  E_CPONLY(kColorPrimaryForeground) \\\n"
        "  E_CPONLY(kColorSecondaryForeground) \\\n"
        "  E_CPONLY(kColorDialogBackground) \\\n"
    ),
    "chrome/browser/ui/color/chrome_color_id.h": (
        "  E_CPONLY(kColorNewTabPagePrimaryForeground) \\\n"
        "  E_CPONLY(kColorSearchboxBackground) \\\n"
    ),
    "chrome/browser/resources/new_tab_page/app.css": "  --ntp-theme-text-shadow: none;",
    "chrome/browser/resources/new_tab_page/logo.css": "  --ntp-logo-margin-bottom: 18px;",
    "ui/webui/resources/cr_elements/cr_shared_vars.css": "  --cr-focus-outline-color: blue;",
}


def pinned_reader(overrides=None):
    text = dict(PINNED)
    text.update(overrides or {})

    def read(path: str) -> str:
        return text[path]

    return read


class DesignTokenTests(unittest.TestCase):
    def setUp(self) -> None:
        directory = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, directory, True)
        self.directory = Path(directory)

    # -- fixtures ---------------------------------------------------------

    def write_patch(self, body, path=APP_CSS, section="", trailing="") -> Path:
        """A single-hunk patch whose header arithmetic matches its body."""

        root = self.directory / "repo"
        patches = root / "downstream/patches"
        patches.mkdir(parents=True, exist_ok=True)
        old = sum(1 for line in body if line[:1] in (" ", "-") or line == "")
        new = sum(1 for line in body if line[:1] in (" ", "+") or line == "")
        text = (
            f"diff --git a/{path} b/{path}\n"
            f"--- a/{path}\n"
            f"+++ b/{path}\n"
            f"@@ -1,{old} +1,{new} @@ {section}\n"
            + "\n".join(body)
            + "\n"
            + trailing
        )
        (patches / "0009-fixture.patch").write_text(text, encoding="utf-8")
        return root

    def rule(self, *declarations, selector="#sunshineWordmark", marker="+"):
        """One complete rule, every line carrying `marker`."""

        return [f"{marker}{selector} {{"] + [f"{marker}  {d}" for d in declarations] + [f"{marker}}}"]

    def failures(self, *declarations, **keywords) -> list[str]:
        marker = keywords.pop("marker", "+")
        selector = keywords.pop("selector", "#sunshineWordmark")
        body = self.rule(*declarations, selector=selector, marker=marker)
        return checker.validate(self.write_patch(body, **keywords))

    def assertFires(self, criterion: str, *declarations, **keywords) -> None:
        failures = self.failures(*declarations, **keywords)
        self.assertTrue(failures, f"{criterion}: the violation was accepted")
        self.assertTrue(
            any(failure.startswith(criterion + " ") for failure in failures),
            f"{criterion} did not fire; got {failures}",
        )

    def assertSilent(self, *declarations, **keywords) -> None:
        self.assertEqual([], self.failures(*declarations, **keywords))

    # -- the repository as it stands --------------------------------------

    def test_the_patch_stack_passes_every_static_criterion(self) -> None:
        """Enforces: S2, S3, S4, S5, S6, S7, S8, S9, S10, S11, S12.

        This check found two real defects on its first run, and both are fixed.

        S8: `font-weight: 650` sat outside the allowed set with no R10 result
        recorded. If the UI font has no continuous weight axis the value snaps,
        so the declaration was a statement about a rendered result that would
        not occur. Now 600 -- inside the set, and what 650 would most likely
        have snapped to anyway, which makes the declaration honest rather than
        merely legal.

        S7: `clamp(2rem, 6vw, 3.5rem)` met every numeric condition but did not
        state its fluid band where the declaration lives, so a later reader
        resizing the window could not tell intended behaviour from accident.
        The band is now on the line.

        A clean run is the claim. The injection tests above are what make it
        mean something.
        """

        self.assertEqual([], checker.validate(REPOSITORY_ROOT))

    def test_upstream_context_lines_are_never_judged(self) -> None:
        """Enforces: S2, S3, S5, S6, S8.

        Every declaration here violates a criterion, and every one of them is
        upstream's. Chromium's own app.css contains lines of exactly this shape;
        a check that reads them has no possible use.
        """

        offences = [
            "color: #fff;",
            "--ntp-theme-text-shadow: none;",
            "font-family: Roboto, sans-serif;",
            "font-size: 14px;",
            "font-weight: 650;",
        ]
        self.assertSilent(*offences, marker=" ")

        failures = self.failures(*offences)
        self.assertEqual(
            ["S2", "S3", "S5", "S6", "S8"],
            sorted({failure.split(" ", 1)[0] for failure in failures}),
            "\n".join(failures),
        )

    def test_a_removed_line_is_not_judged_either(self) -> None:
        """What the patch deletes is not Sunshine-authored CSS."""

        body = [" #logo {", "-  color: #fff;", "+  color: var(--color-x);", " }"]
        self.assertEqual([], checker.validate(self.write_patch(body)))

    def test_the_hunk_header_section_names_the_enclosing_rule(self) -> None:
        """git writes the enclosing selector after the second `@@`.

        It is context, not an added line, so it must seed the rule a declaration
        belongs to without ever being judged itself.
        """

        body = ["+  color: var(--color-x);", " }"]
        root = self.write_patch(body, section="#sunshineWordmark {")
        sheet = checker.read_stylesheets(root)
        self.assertEqual(["#sunshineWordmark"], [d.selector for d in sheet.authored()])

    def test_a_rule_cut_in_half_by_the_hunk_boundary_is_not_guessed_at(self) -> None:
        """Enforces: S12.

        The replacement indicator may sit outside the window, so a rule whose
        braces were not both seen is skipped rather than reported.
        """

        truncated = ["+  outline: none;", " }"]
        self.assertEqual([], checker.validate(self.write_patch(truncated, section="#control {")))
        self.assertFires("S12", "outline: none;", selector="#control")

    def test_the_hunk_body_ends_where_its_arithmetic_says(self) -> None:
        """A second file in the patch must not be parsed as the first one's CSS."""

        body = self.rule("color: var(--color-x);")
        trailing = (
            f"diff --git a/{APP_CSS.replace('.css', '.ts')} b/{APP_CSS.replace('.css', '.ts')}\n"
            f"--- a/x.ts\n+++ b/x.ts\n@@ -1,1 +1,1 @@\n-const a = 1;\n+const b = 'color: #fff';\n"
        )
        self.assertEqual([], checker.validate(self.write_patch(body, trailing=trailing)))

    # -- S1 ---------------------------------------------------------------

    def test_a_token_absent_from_the_pinned_revision_is_rejected(self) -> None:
        """Enforces: S1."""

        root = self.write_patch(self.rule("color: var(--color-sunshine-invented);"))
        failures = checker.check_token_provenance(root, read=pinned_reader())
        self.assertTrue(failures)
        self.assertIn("--color-sunshine-invented", failures[0])
        self.assertIn("kColorSunshineInvented", failures[0])

    def test_the_tokens_the_wordmark_consumes_exist_at_the_pinned_revision(self) -> None:
        """Enforces: S1.

        The real patch stack, against the real needles, with the network stubbed
        so the suite stays offline. The live form runs from `main`.
        """

        self.assertEqual(
            [], checker.check_token_provenance(REPOSITORY_ROOT, read=pinned_reader())
        )
        self.assertEqual(
            {
                # New Tab wordmark, 0002.
                "--color-new-tab-page-primary-foreground",
                "--ntp-logo-margin-bottom",
                "--ntp-theme-text-shadow",
                # The searchbox's normal state, 0022. Read at the pin from
                # chrome_color_id.h line 779, the same header and the same
                # form as the wordmark's token above.
                "--color-searchbox-background",
                # Security Center, 0004. Every one is a role binding that
                # docs/DESIGN_SYSTEM_CONTRACT.md section 3 left unbound, and
                # each was resolved by reading ui/color/color_id.h at the
                # pinned revision rather than by guessing at the name pattern.
                "--color-alert-high-severity",
                "--color-dialog-background",
                "--color-midground",
                "--color-primary-foreground",
                "--color-secondary-foreground",
            },
            set(checker.consumed_tokens(REPOSITORY_ROOT)),
        )

    def test_a_colour_token_is_proven_by_its_colour_id_not_by_a_stylesheet(self) -> None:
        """Enforces: S1.

        Chromium emits `--color-*` from the `ColorId` enumerators and serves
        them through chrome://theme, so the token appears in no CSS file. Asking
        a stylesheet about it fails the build on a token that exists -- the
        false positive `verify_pinned_upstream` was rewritten to avoid.
        """

        paths, needle = checker.token_sources("--color-new-tab-page-primary-foreground")
        self.assertEqual("kColorNewTabPagePrimaryForeground", needle)
        self.assertNotIn(APP_CSS, paths)

        root = self.write_patch(self.rule("color: var(--color-new-tab-page-primary-foreground);"))
        failures = checker.check_token_provenance(
            root,
            read=pinned_reader({"chrome/browser/ui/color/chrome_color_id.h": "nothing here"}),
        )
        self.assertTrue(failures)
        self.assertIn("chrome_color_id.h", failures[0])

    def test_an_ntp_token_is_proven_by_the_stylesheet_that_declares_it(self) -> None:
        """Enforces: S1.

        `--ntp-logo-margin-bottom` is declared in logo.css, not app.css, so a
        one-file lookup would report a token that exists as missing.
        """

        root = self.write_patch(self.rule("margin-bottom: var(--ntp-logo-margin-bottom, 38px);"))
        self.assertEqual([], checker.check_token_provenance(root, read=pinned_reader()))
        failures = checker.check_token_provenance(
            root,
            read=pinned_reader({"chrome/browser/resources/new_tab_page/logo.css": ""}),
        )
        self.assertTrue(failures)
        self.assertIn("--ntp-logo-margin-bottom", failures[0])

    def test_validate_reads_no_pinned_source(self) -> None:
        """S2-S12 must stay offline, or CI pays the network cost twelve times."""

        def explode(*arguments, **keywords):
            raise AssertionError("the offline checks reached the network")

        original = checker.upstream.fetch
        checker.upstream.fetch = explode
        self.addCleanup(setattr, checker.upstream, "fetch", original)
        checker.validate(REPOSITORY_ROOT)

    # -- S2 ---------------------------------------------------------------

    def test_a_literal_colour_is_rejected(self) -> None:
        """Enforces: S2."""

        self.assertFires("S2", "color: #ff0000;")
        self.assertFires("S2", "background-color: rgba(0, 0, 0, 0.5);")
        self.assertFires("S2", "fill: darkslategray;")
        self.assertFires("S2", "--sun-color-primary: oklch(70% 0.1 40);")

    def test_a_reference_that_merely_contains_a_colour_word_is_not_a_literal(self) -> None:
        """Enforces: S2.

        `--color-tomato-surface` is a token name, and `color-mix()` composing
        two references is what §2.2(3) tells Sunshine to do. A check that fires
        on either is unusable.
        """

        self.assertSilent("color: var(--color-tomato-surface);")
        self.assertSilent("--sun-color-on-surface: color-mix(in srgb, var(--color-a), var(--color-b));")
        self.assertSilent("fill: currentColor;", "stroke: none;", "background-color: Canvas;")
        self.assertSilent("fill: url(#sunshineGradient);")

    # -- S3 ---------------------------------------------------------------

    def test_assigning_to_a_chromium_token_is_rejected(self) -> None:
        """Enforces: S3."""

        for offence in (
            "--color-new-tab-page-primary-foreground: var(--x);",
            "--cr-focus-outline-color: var(--x);",
            "--ntp-theme-text-shadow: none;",
        ):
            with self.subTest(declaration=offence):
                self.assertFires("S3", offence)

    def test_reading_a_chromium_token_is_not_assigning_to_one(self) -> None:
        """Enforces: S3. The families are read-only, not untouchable."""

        self.assertSilent("color: var(--color-new-tab-page-primary-foreground);")

    # -- S4 ---------------------------------------------------------------

    def test_a_colour_fallback_is_rejected(self) -> None:
        """Enforces: S4.

        A fallback colour is plausible enough to survive review while silently
        escaping the theme: correct in the light theme, wrong everywhere else.
        """

        self.assertFires("S4", "color: var(--color-new-tab-page-primary-foreground, #fff);")
        self.assertFires("S4", "--sun-color-primary: var(--color-a, var(--color-b));")

    def test_a_documented_non_colour_default_must_be_matched_exactly(self) -> None:
        """Enforces: S4."""

        self.assertSilent("margin-bottom: var(--ntp-logo-margin-bottom, 38px);")
        self.assertFires("S4", "margin-bottom: var(--ntp-logo-margin-bottom, 24px);")
        self.assertFires("S4", "margin-bottom: var(--ntp-logo-margin-bottom);")

    # -- S5 ---------------------------------------------------------------

    def test_declaring_a_typeface_is_rejected(self) -> None:
        """Enforces: S5.

        Chromium's WebUI font selection is localised; a Latin stack degrades the
        Korean-first copy the product targets.
        """

        self.assertFires("S5", "font-family: 'Segoe UI', sans-serif;")
        self.assertFires("S5", "font-family: ui-monospace, monospace;")
        self.assertSilent("font-family: monospace;")

    # -- S6 ---------------------------------------------------------------

    def test_a_font_size_off_the_scale_is_rejected(self) -> None:
        """Enforces: S6."""

        self.assertFires("S6", "font-size: 14px;")
        self.assertFires("S6", "font-size: 0.5rem;")
        self.assertFires("S6", "font-size: 1.125rem;")
        self.assertFires("S6", "font-size: 1rem !important;")
        self.assertSilent("font-size: 0.875rem;")

    # -- S7 ---------------------------------------------------------------

    def test_a_clamp_that_breaks_its_bounding_conditions_is_rejected(self) -> None:
        """Enforces: S7.

        The four conditions of §6.3 in order: rem bounds, a vw or vi preferred
        term, a range no wider than 2, and a fluid band that overlaps 360-1920.
        """

        band = "/* fluid between 533 and 933 px */"
        for declaration, clause in (
            ("font-size: clamp(2rem, 6vw, 5vh);", "§6.3.1"),
            ("font-size: clamp(2rem, 1rem + 2vw, 3rem);", "§6.3.2"),
            ("font-size: clamp(1rem, 6vw, 3rem);", "§6.3.3"),
            ("font-size: clamp(2rem, 0.5vw, 3.5rem);", "§6.3.4"),
        ):
            with self.subTest(declaration=declaration):
                failures = self.failures(band, declaration)
                self.assertTrue(
                    any(f.startswith("S7 ") and clause in f for f in failures),
                    f"{clause} did not fire; got {failures}",
                )

    def test_a_clamp_must_state_its_fluid_band_where_it_lives(self) -> None:
        """Enforces: S7.

        §6.3 requires the band at the declaration so a reviewer does not have to
        derive it. This is the clause the wordmark fails today.
        """

        self.assertFires("S7", "font-size: clamp(2rem, 6vw, 3.5rem);")
        self.assertSilent(
            "/* Fluid between 533px and 933px; max/min = 1.75. */",
            "font-size: clamp(2rem, 6vw, 3.5rem);",
        )

    # -- S8 ---------------------------------------------------------------

    def test_an_unresolvable_weight_is_rejected_until_r10_records_a_result(self) -> None:
        """Enforces: S8."""

        self.assertFires("S8", "font-weight: 650;")
        self.assertFires("S8", "font-weight: bolder;")
        self.assertSilent("font-weight: 600;")
        self.assertSilent("font-weight: bold;")

    def test_a_decision_record_citing_r10_settles_the_weight(self) -> None:
        """Enforces: S8. §11 relaxes a rule only through a decision record."""

        root = self.write_patch(self.rule("font-weight: 650;"))
        self.assertTrue(checker.validate(root))
        decisions = root / "docs/decisions"
        decisions.mkdir(parents=True)
        (decisions / "0004-wordmark-weight.md").write_text(
            "R10 was run on all supported platforms: 650 rasterises distinctly.\n",
            encoding="utf-8",
        )
        self.assertEqual([], checker.validate(root))

    # -- S9 ---------------------------------------------------------------

    def test_a_lockup_using_a_logical_property_without_direction_is_rejected(self) -> None:
        """Enforces: S9.

        Measured at 56px type: without `direction`, `padding-inline-start` flips
        to the same side as the trailing letter-space and doubles a 10.087px
        error instead of cancelling it.
        """

        self.assertFires("S9", "padding-inline-start: 0.18em;")
        self.assertSilent("direction: ltr;", "padding-inline-start: 0.18em;")

    def test_the_direction_rule_applies_to_the_lockup_set_only(self) -> None:
        """Enforces: S9.

        Logical properties remain the default for translated content; §7.2 does
        not license a return to physical properties.
        """

        self.assertSilent("padding-inline-start: 0.18em;", selector="#searchboxContainer")

    def test_direction_declared_in_a_second_rule_for_the_same_element_counts(self) -> None:
        """Enforces: S9. The contract says the same element, not the same rule."""

        body = (
            self.rule("direction: ltr;")
            + self.rule("padding-inline-start: 0.18em;")
        )
        self.assertEqual([], checker.validate(self.write_patch(body)))

    # -- S10 --------------------------------------------------------------

    def test_opting_out_of_forced_colours_is_rejected(self) -> None:
        """Enforces: S10."""

        self.assertFires("S10", "forced-color-adjust: none;")

    def test_a_forced_colours_block_that_restores_appearance_is_rejected(self) -> None:
        """Enforces: S10.

        Under forced colours the user agent substitutes the user's palette and
        drops shadows. Sunshine's obligation is to stay out of the way.
        """

        for prelude, offence in (
            ("@media (forced-colors: active)", "color: var(--sun-color-primary);"),
            ("@media (forced-colors: active)", "text-shadow: 0 0 2px var(--x);"),
            ("@media (prefers-contrast: more)", "background-color: var(--x);"),
            ("@media (prefers-color-scheme: dark)", "--sun-color-primary: var(--x);"),
        ):
            with self.subTest(block=prelude, declaration=offence):
                body = [f"+{prelude} {{"] + self.rule(offence) + ["+}"]
                failures = checker.validate(self.write_patch(body))
                self.assertTrue(failures, "the override was accepted")
                self.assertTrue(any(f.startswith("S10 ") for f in failures), failures)

    def test_a_non_colour_response_to_increased_contrast_is_permitted(self) -> None:
        """Enforces: S10. §5.2 permits thickening a border, not repainting it."""

        body = (
            ["+@media (prefers-contrast: more) {"]
            + self.rule("border-width: 2px;", "--sun-border-strong: 2px;")
            + ["+}"]
        )
        self.assertEqual([], checker.validate(self.write_patch(body)))

    # -- S11 --------------------------------------------------------------

    def test_motion_without_a_reduced_motion_counterpart_is_rejected(self) -> None:
        """Enforces: S11.

        The New Tab patch declares no motion today, so the rule exists before
        the first animation is written rather than after.
        """

        self.assertFires("S11", "transition: opacity 200ms ease;")
        self.assertFires("S11", "scroll-behavior: smooth;")
        # Switching motion off is not motion, and must not demand a counterpart.
        self.assertSilent("transition: none;", "animation: none;")

    def test_a_neutralised_transition_is_accepted(self) -> None:
        """Enforces: S11."""

        body = (
            self.rule("transition: opacity 200ms ease;")
            + ["+@media (prefers-reduced-motion: reduce) {"]
            + self.rule("transition: none;")
            + ["+}"]
        )
        self.assertEqual([], checker.validate(self.write_patch(body)))

    # -- S12 --------------------------------------------------------------

    def test_suppressing_the_focus_indicator_is_rejected(self) -> None:
        """Enforces: S12."""

        self.assertFires("S12", "outline: none;", selector="#control:focus-visible")
        self.assertSilent(
            "outline: 0;",
            "box-shadow: 0 0 0 2px var(--cr-focus-outline-color);",
            selector="#control:focus-visible",
        )

    def test_a_positive_tabindex_is_rejected(self) -> None:
        """Enforces: S12. Focus order is DOM order."""

        path = "chrome/browser/resources/new_tab_page/app.html"
        body = ['+  <div id="sunshineWordmark" tabindex="1">SUNSHINE</div>']
        failures = checker.validate(self.write_patch(body, path=path))
        self.assertTrue(any(f.startswith("S12 ") for f in failures), failures)

        body = ['+  <div id="sunshineWordmark" tabindex="-1">SUNSHINE</div>']
        self.assertEqual([], checker.validate(self.write_patch(body, path=path)))

    # -- markup ------------------------------------------------------------

    def test_an_inline_style_attribute_is_sunshine_authored_css(self) -> None:
        """Enforces: S2. Otherwise the stylesheet checks have a way around them."""

        path = "chrome/browser/resources/new_tab_page/app.html"
        body = ['+  <div id="sunshineWordmark" style="color: #ff0000">SUNSHINE</div>']
        failures = checker.validate(self.write_patch(body, path=path))
        self.assertTrue(any(f.startswith("S2 ") for f in failures), failures)


class DuplicateSelectorTests(unittest.TestCase):
    """S13: the criterion that exists because a build found it first.

    Patch 0022 added a second `#inputWrapper { }` to an upstream stylesheet so
    that no upstream line was edited and the hunk survived a roll. Chromium's
    stylelint config runs `no-duplicate-selectors` over that folder, and native
    build #46 failed on it in twenty seconds -- after S1 through S12, the
    architecture guards and `verify_pinned_upstream` had all passed.
    """

    UPSTREAM = {
        NTP_SEARCHBOX_CSS: (
            "#inputWrapper {\n"
            "  background-color: var(--color-searchbox-background);\n"
            "}\n"
            "\n"
            ":host([in-voice-search-mode]) #inputWrapper {\n"
            "  display: none;\n"
            "}\n"
        ),
    }

    def setUp(self) -> None:
        directory = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, directory, True)
        self.directory = Path(directory)

    def write(self, body: list[str], path: str = NTP_SEARCHBOX_CSS) -> Path:
        root = self.directory / "repo"
        patches = root / "downstream/patches"
        patches.mkdir(parents=True, exist_ok=True)
        old = sum(1 for line in body if line[:1] in (" ", "-"))
        new = sum(1 for line in body if line[:1] in (" ", "+"))
        (patches / "0001-fixture.patch").write_text(
            f"diff --git a/{path} b/{path}\n--- a/{path}\n+++ b/{path}\n"
            f"@@ -1,{old} +1,{new} @@\n" + "\n".join(body) + "\n",
            encoding="utf-8",
        )
        (patches / "series").write_text("0001-fixture.patch\n", encoding="utf-8")
        return root

    def run_check(self, root: Path) -> list[str]:
        return checker.check_no_duplicate_selectors(
            root, read=lambda path: self.UPSTREAM[path])

    def test_repeating_an_upstream_selector_is_rejected(self) -> None:
        """Enforces: S13. The exact shape that failed native build #46."""

        root = self.write([
            " :host([in-voice-search-mode]) #inputWrapper {",
            "   display: none;",
            " }",
            " ",
            "+#inputWrapper {",
            "+  transition: background-color 150ms ease;",
            "+}",
        ])
        failures = self.run_check(root)
        self.assertTrue(failures, "the duplicate selector was accepted")
        self.assertIn("#inputWrapper", failures[0])
        self.assertIn("no-duplicate-selectors", failures[0])

    def test_a_new_selector_is_accepted(self) -> None:
        """The shipped shape: a compound nobody upstream declares."""

        root = self.write([
            " :host([in-voice-search-mode]) #inputWrapper {",
            "   display: none;",
            " }",
            " ",
            "+:host(:not([has-user-input_])) #inputWrapper:not(:focus-within) {",
            "+  background-color: color-mix(in srgb, var(--color-searchbox-background) 65%, transparent);",
            "+}",
        ])
        self.assertEqual([], self.run_check(root))

    def test_adding_to_an_upstream_rule_is_accepted(self) -> None:
        """A declaration inside upstream's own rule adds no selector.

        This is the fix stylelint asks for, so a check that flagged it would
        forbid the only remedy it offers.
        """

        root = self.write([
            " #inputWrapper {",
            "   background-color: var(--color-searchbox-background);",
            "+  transition: background-color 150ms ease;",
            " }",
        ])
        self.assertEqual([], self.run_check(root))

    def test_a_stylesheet_the_stack_creates_is_not_read(self) -> None:
        """Sunshine's own CSS has no upstream, and asking for one is a 404.

        The first run of this check failed exactly that way, on the account
        surface's stylesheet.
        """

        path = "chrome/browser/resources/sunshine/account/app.css"
        root = self.directory / "repo"
        patches = root / "downstream/patches"
        patches.mkdir(parents=True, exist_ok=True)
        (patches / "0001-fixture.patch").write_text(
            f"diff --git a/{path} b/{path}\n--- /dev/null\n+++ b/{path}\n"
            "@@ -0,0 +1,3 @@\n+#inputWrapper {\n+  display: flex;\n+}\n",
            encoding="utf-8",
        )
        (patches / "series").write_text("0001-fixture.patch\n", encoding="utf-8")

        def refuse(path: str) -> str:
            raise AssertionError(f"a created stylesheet was read upstream: {path}")

        self.assertEqual([], checker.check_no_duplicate_selectors(root, read=refuse))

    def test_the_selectors_the_stack_adds_to_upstream_stylesheets(self) -> None:
        """Enforces: S13.

        The live form of this check reads the pinned revision and runs in CI;
        the offline form pins *what would be read*. A patch that adds a bare
        upstream selector -- the shape that failed build #46 -- changes this set
        and has to be looked at, which is the point.
        """

        self.assertEqual(
            {
                # Patch 0002. Every one is Sunshine-namespaced except the two
                # `:host` compounds, which upstream does not spell this way.
                APP_CSS: {
                    "#sunshineBackground",
                    "#sunshineClock",
                    "#sunshineSettings",
                    "#sunshineSettings:focus-visible",
                    "#sunshineSettings:hover",
                    "#sunshineStatus",
                    "#sunshineStatus > *",
                    "#sunshineWordmark",
                    ":host > *:not(#sunshineBackground)",
                    ":host([sunshine-resting]) #sunshineStatus > *:not(#sunshineClock)",
                    ":host([sunshine-resting]) > *:not(#sunshineBackground):not(#sunshineStatus)",
                },
                # Patch 0022. One rule, and a compound upstream has no reason to
                # write: the bare `#inputWrapper` next to it is what broke #46.
                NTP_SEARCHBOX_CSS: {
                    ":host(:not([has-user-input_])) #inputWrapper:not(:focus-within)",
                },
            },
            {
                path: {selector for selector, _patch in entries}
                for path, entries in checker.authored_selectors(REPOSITORY_ROOT).items()
                if path not in manifest.created_paths(
                    REPOSITORY_ROOT, manifest.read_manifest(REPOSITORY_ROOT))
            },
        )


if __name__ == "__main__":
    unittest.main()
