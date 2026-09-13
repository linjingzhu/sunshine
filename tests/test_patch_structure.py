"""Offline structural validation of the Chromium downstream patch stack.

CI applies the full stack against real pinned upstream sources, but that check
needs network access to the upstream host. This suite validates what can be
proven from the patch files alone, so a malformed hunk is caught locally before
it ever reaches the network-dependent gate.
"""

from pathlib import Path
import re
import subprocess
import unittest


ROOT = Path(__file__).resolve().parents[1]
PATCH_DIR = ROOT / "downstream/patches"


def series_entries() -> list[str]:
    return [
        line.strip()
        for line in (PATCH_DIR / "series").read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]


class PatchStructureTests(unittest.TestCase):
    def test_every_patch_has_consistent_hunk_arithmetic(self) -> None:
        """`git apply --numstat` rejects a hunk header that miscounts its body."""

        for entry in series_entries():
            with self.subTest(patch=entry):
                result = subprocess.run(
                    ["git", "apply", "--numstat", str(PATCH_DIR / entry)],
                    capture_output=True,
                    text=True,
                    cwd=ROOT,
                )
                self.assertEqual(0, result.returncode, result.stderr)
                self.assertTrue(result.stdout.strip(), f"{entry} reported no changed file")

    def test_a_miscounted_hunk_is_rejected(self) -> None:
        """Prove the check above actually fails on a corrupt patch."""

        source = (PATCH_DIR / "0002-sunshine-new-tab.patch").read_text(encoding="utf-8")

        # The first hunk header, whatever it happens to be, with its new-side
        # line count reduced by one. An earlier version named a specific
        # header and broke the moment that patch gained a hunk above it -- the
        # test was asserting where the patch's content sat rather than that
        # the arithmetic check works.
        header = re.search(r"^@@ -(\d+),(\d+) \+(\d+),(\d+) @@", source, re.M)
        self.assertIsNotNone(header, "the patch has no hunk header to corrupt")
        assert header is not None
        old_start, old_count, new_start, new_count = header.groups()
        corrupt = source.replace(
            header.group(0),
            f"@@ -{old_start},{old_count} +{new_start},{int(new_count) - 1} @@",
            1,
        )
        self.assertNotEqual(source, corrupt, "hunk header to corrupt was not found")

        result = subprocess.run(
            ["git", "apply", "--numstat", "-"],
            input=corrupt,
            capture_output=True,
            text=True,
            cwd=ROOT,
        )

        self.assertNotEqual(0, result.returncode)
        self.assertIn("corrupt patch", result.stderr)

    def test_the_wordmark_keeps_native_logo_slot_behaviour(self) -> None:
        """The wordmark replaces `ntp-logo`, so it inherits that slot's contract.

        Dropping either behaviour renders the wordmark when Chromium says the
        logo is off, or freezes its spacing when a theme moves it.
        """

        patch = (PATCH_DIR / "0002-sunshine-new-tab.patch").read_text(encoding="utf-8")
        self.assertIn('?hidden="${!this.logoEnabled_}"', patch)
        self.assertIn("margin-bottom: var(--ntp-logo-margin-bottom, 38px);", patch)

    def test_the_wordmark_stays_ltr_in_rtl_locales(self) -> None:
        """Measured: without `direction: ltr` the wordmark sits a full
        letter-space (10.09px at 56px type) left of centre in an RTL UI, because
        `padding-inline-start` flips to the right and stops cancelling the
        trailing letter-space.
        """

        patch = (PATCH_DIR / "0002-sunshine-new-tab.patch").read_text(encoding="utf-8")
        self.assertIn("direction: ltr;", patch)
        self.assertIn("padding-inline-start: 0.18em;", patch)

    def test_borrowed_tokens_are_either_proven_or_checked_upstream(self) -> None:
        """A token used only on added lines is asserted, not proven.

        `--ntp-logo-margin-bottom` is proven: upstream's own `#logo` rule sits in
        the patch context. The other two are checked in CI against the pinned
        revision -- and against the right source for each kind, which is the
        point of `test_the_colour_token_is_checked_where_it_is_defined`.
        """

        patch = (PATCH_DIR / "0002-sunshine-new-tab.patch").read_text(encoding="utf-8")
        context = {line[1:] for line in patch.splitlines() if line.startswith(" ")}
        self.assertTrue(
            any("--ntp-logo-margin-bottom" in line for line in context),
            "the margin token is no longer proven by upstream context",
        )

        checker = (ROOT / "scripts/verify_pinned_upstream.py").read_text(encoding="utf-8")
        self.assertIn("--ntp-theme-text-shadow", patch)
        self.assertIn("--ntp-theme-text-shadow:", checker)
        self.assertIn("--color-new-tab-page-primary-foreground", patch)

    def test_the_colour_token_is_checked_where_it_is_defined(self) -> None:
        """`--color-new-tab-page-*` tokens are not declared in app.css.

        Chromium emits them from the colour IDs in `chrome_color_id.h` and
        serves them through `chrome://theme`, so a token can be entirely valid
        while appearing nowhere in the stylesheet. Verified against the pinned
        tag: `app.css` contains no `--color-new-tab-page-primary-foreground`,
        and `chrome_color_id.h` does define `kColorNewTabPagePrimaryForeground`.

        Grepping app.css for it -- which this check first did -- fails the build
        on a token that exists.
        """

        checker = (ROOT / "scripts/verify_pinned_upstream.py").read_text(encoding="utf-8")
        self.assertIn("chrome/browser/ui/color/chrome_color_id.h", checker)
        self.assertIn("kColorNewTabPagePrimaryForeground", checker)

    def test_the_wordmark_leaves_no_reference_to_the_element_it_replaced(self) -> None:
        """Replacing `ntp-logo` is not finished when the template changes.

        `app.ts` referred to the logo in four places. Removing only the element
        failed the build at `//chrome/browser/resources/new_tab_page:lint_ts`:

            Id 'logo' is listed in the interface definition for AppElement,
            but no element with that ID was found in the template file

        The other three are silent rather than fatal -- an unused type import,
        an inert allowlist that would have made the wordmark inert whenever the
        composebox opened, and a click metric that would have stopped recording.
        """

        patch = (PATCH_DIR / "0002-sunshine-new-tab.patch").read_text(encoding="utf-8")
        removed = [line[1:] for line in patch.splitlines() if line.startswith("-")]
        added = [line[1:] for line in patch.splitlines() if line.startswith("+")]

        self.assertTrue(any('<ntp-logo id="logo"' in line for line in removed))

        for orphan in (
            "    logo: LogoElement,",
            "import type {LogoElement} from './logo.js';",
            "  '#logo',",
            "        case $$(this, 'ntp-logo'):",
        ):
            with self.subTest(reference=orphan.strip()):
                self.assertIn(orphan, removed)

        # The two that are replaced rather than simply dropped must land on the
        # wordmark, or the behaviour is lost instead of carried over.
        self.assertIn("  '#sunshineWordmark',", added)
        self.assertIn("        case $$(this, '#sunshineWordmark'):", added)

    def test_stage_one_does_not_remove_chromium_browser_primitives(self) -> None:
        patch = (PATCH_DIR / "0002-sunshine-new-tab.patch").read_text(encoding="utf-8")
        for primitive in ("ntp-searchbox", "cr-most-visited", "ntp-realbox"):
            with self.subTest(primitive=primitive):
                self.assertNotIn(f"-  <{primitive}", patch)


if __name__ == "__main__":
    unittest.main()


class SplitSwapDotPaintsTests(unittest.TestCase):
    """A view added to the resize area must own a layer, or it is invisible.

    **This is a defect that shipped.** Build #61's swap dot took clicks and
    swapped the panes while drawing nothing at all. `MultiContentsResizeArea`
    sits between two layer-backed contents containers, so a child that paints
    into its parent's layer ends up beneath them — and event targeting goes by
    view bounds rather than by layers, which is why it *worked* and was
    invisible at the same time.

    `MultiContentsResizeHandle`, the one view in that upstream file known to
    render, calls `SetPaintToLayer(ui::LAYER_TEXTURED)` and
    `SetFillsBoundsOpaquely(false)` before setting its background. The first
    version of this patch copied only the background.

    Nothing in this project compiles Chromium, so a compiler would not have
    caught it and did not: build #61 compiled cleanly and shipped a control
    nobody could see. Reading the patch is the only check available before a
    person looks at a running browser, which makes it worth having.
    """

    def setUp(self) -> None:
        self.patch = (PATCH_DIR / "0027-sunshine-split-swap-button.patch").read_text(
            encoding="utf-8")
        # Added lines only: upstream's own handle does all of this too, and
        # matching its lines would make this test pass on a patch that removed
        # every one of ours.
        self.added = "\n".join(
            line[1:] for line in self.patch.splitlines()
            if line.startswith("+") and not line.startswith("+++"))

    def test_the_dot_is_created_at_all(self) -> None:
        self.assertIn("sunshine_swap_button_ = AddChildView", self.added)

    def test_the_dot_paints_to_its_own_layer(self) -> None:
        self.assertIn("sunshine_swap_button_->SetPaintToLayer(ui::LAYER_TEXTURED);",
                      self.added)

    def test_that_layer_does_not_claim_to_fill_its_bounds(self) -> None:
        """A circle does not fill a square, and saying it does corrupts what is
        drawn behind it."""

        self.assertIn("sunshine_swap_button_->layer()->SetFillsBoundsOpaquely(false);",
                      self.added)

    def test_the_layer_is_established_before_the_background(self) -> None:
        """Order is not cosmetic: the background paints into whatever layer the
        view has when it paints, so the layer has to exist first."""

        layer = self.added.index("sunshine_swap_button_->SetPaintToLayer")
        background = self.added.index("sunshine_swap_button_->SetBackground")
        self.assertLess(layer, background)

    def test_the_dot_keeps_upstreams_divider_width(self) -> None:
        """The whole point of the dot: ten is exactly what upstream already
        reserves for the drag handle, so the splitter does not widen and the
        panes give up nothing."""

        self.assertIn("static constexpr int kSunshineSwapButtonSize = 10;", self.added)

    def test_the_dot_is_round(self) -> None:
        self.assertIn("kSunshineSwapButtonSize / 2", self.added)

    def test_the_tooltip_names_the_action_with_upstreams_own_string(self) -> None:
        self.assertIn("IDS_SPLIT_TAB_REVERSE_VIEWS", self.added)

    def test_the_patch_no_longer_touches_multi_contents_view(self) -> None:
        """A dot has no direction, so the calls that kept an arrow pointing the
        right way are gone — and with them the only reason this patch ever
        edited that file."""

        self.assertNotIn("multi_contents_view.cc", self.patch)
