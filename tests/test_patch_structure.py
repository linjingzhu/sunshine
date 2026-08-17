"""Offline structural validation of the Chromium downstream patch stack.

CI applies the full stack against real pinned upstream sources, but that check
needs network access to the upstream host. This suite validates what can be
proven from the patch files alone, so a malformed hunk is caught locally before
it ever reaches the network-dependent gate.
"""

from pathlib import Path
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
        corrupt = source.replace("@@ -28,13 +28,9 @@", "@@ -28,13 +28,8 @@", 1)
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

        workflow = (ROOT / ".github/workflows/chromium-architecture-check.yml").read_text(encoding="utf-8")
        self.assertIn("--ntp-theme-text-shadow", patch)
        self.assertIn("--ntp-theme-text-shadow:", workflow)
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

        workflow = (ROOT / ".github/workflows/chromium-architecture-check.yml").read_text(encoding="utf-8")
        self.assertIn("chrome/browser/ui/color/chrome_color_id.h", workflow)
        self.assertIn("kColorNewTabPagePrimaryForeground", workflow)

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
