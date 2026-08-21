"""Tests for the web asset and URL scheme guards.

Both guards exist because a decision had been taken and never enforced. ADR 0003
settled that Sunshine registers no URL scheme; nothing checked it, and a later
architecture proposal introduced `sunshine-module://` as the default module
origin without anything objecting. The web asset rules were never written down
at all.

Every case injects the violation. A guard that has only ever seen a clean tree
is indistinguishable from one whose patterns do not match.
"""

from pathlib import Path
import sys
import tempfile
import unittest

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY_ROOT / "scripts"))

import verify_first_party_surfaces as surfaces  # noqa: E402
import verify_web_asset_security as assets  # noqa: E402


class TreeTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory()
        self.root = Path(self.directory.name)
        self.addCleanup(self.directory.cleanup)

    def write(self, relative: str, text: str) -> None:
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")


class SchemeRegistrationTests(TreeTestCase):
    """Enforces: SEC-13."""

    def failures(self) -> list[str]:
        found: list[str] = []
        surfaces.check_no_scheme_registration(self.root, found)
        return found

    def test_a_sunshine_scheme_is_rejected(self) -> None:
        self.write("first_party/registry.json", '{"origin": "sunshine://home/"}')
        self.assertTrue(any("SEC-13" in failure for failure in self.failures()))

    def test_the_module_origin_scheme_a_later_proposal_introduced_is_rejected(self) -> None:
        """`sunshine-module://<id>/` was proposed as the default module origin."""

        self.write("first_party/modules/dev/module.json", '{"entry": "sunshine-module://dev-os/"}')
        self.assertTrue(any("sunshine-module" in failure for failure in self.failures()))

    def test_registering_a_scheme_in_a_patch_is_rejected(self) -> None:
        self.write("downstream/patches/0009-x.patch", "\n".join([
            "--- a/url/url_util.cc",
            "+++ b/url/url_util.cc",
            "@@ -1,2 +1,3 @@",
            '+  url::AddStandardScheme("sunshine", url::SCHEME_WITH_HOST);',
        ]))
        self.assertTrue(any("AddStandardScheme" in failure for failure in self.failures()))

    def test_the_windows_registry_protocol_value_is_rejected(self) -> None:
        """A scheme registered with the OS is the form ADR 0003 cared most about."""

        self.write("config/installer.json", '{"HKCR\\\\sunshine": {"URL Protocol": ""}}')
        self.assertTrue(any("URL Protocol" in failure for failure in self.failures()))

    def test_chromium_schemes_are_not_sunshine_registering_anything(self) -> None:
        self.write("first_party/registry.json", "\n".join([
            '{"a": "chrome://sunshine-security/",',
            ' "b": "chrome-untrusted://preview/",',
            ' "c": "https://api.example.com",',
            ' "d": "devtools://devtools/"}',
        ]))
        self.assertEqual([], self.failures())

    def test_upstream_context_in_a_patch_is_not_sunshine_authored(self) -> None:
        """Context lines are upstream's, and upstream registers many schemes."""

        self.write("downstream/patches/0009-x.patch", "\n".join([
            "--- a/url/url_util.cc",
            "+++ b/url/url_util.cc",
            "@@ -1,3 +1,4 @@",
            '   url::AddStandardScheme("isolated-app", url::SCHEME_WITH_HOST);',
            "+// Sunshine comment",
        ]))
        self.assertEqual([], self.failures())


class WebAssetSecurityTests(TreeTestCase):
    """Enforces: SEC-14."""

    def failures(self) -> list[str]:
        return assets.check(self.root)

    def test_dynamic_code_forms_are_rejected(self) -> None:
        for snippet in (
            "const f = eval(input);",
            "const f = new Function('return 1');",
            "setTimeout('doThing()', 10);",
            "setInterval(\"tick()\", 10);",
            "element.innerHTML = value;",
            "element.outerHTML = value;",
            "document.write(value);",
        ):
            with self.subTest(snippet=snippet):
                self.write("first_party/modules/x/app.ts", snippet)
                self.assertTrue(
                    any("SEC-14" in failure for failure in self.failures()), snippet
                )

    def test_a_remote_script_is_rejected(self) -> None:
        self.write("first_party/modules/x/index.html", '<script src="https://cdn.example.com/a.js"></script>')
        self.assertTrue(any("remote resource" in failure for failure in self.failures()))

    def test_a_remote_font_in_css_is_rejected(self) -> None:
        self.write("first_party/modules/x/app.css", "@font-face { src: url(https://fonts.example.com/a.woff2); }")
        self.assertTrue(any("remote resource" in failure for failure in self.failures()))

    def test_a_url_in_a_comment_is_documentation_not_a_load(self) -> None:
        """The patch stack cites upstream files by URL in its own comments.

        A rule that fired on those would be deleted the first week, which is a
        worse outcome than the rule not existing.
        """

        self.write("first_party/modules/x/app.ts", "\n".join([
            "// See https://github.com/chromium/chromium/blob/152.0.7977.42/base/check.h",
            "/* https://example.com/spec */",
            "const value = 1;",
        ]))
        self.assertEqual([], self.failures())

    def test_added_lines_in_a_non_web_file_are_not_scanned(self) -> None:
        """An added line in a .cc file is not JavaScript, however it looks."""

        self.write("downstream/patches/0009-x.patch", "\n".join([
            "--- a/chrome/browser/thing.cc",
            "+++ b/chrome/browser/thing.cc",
            "@@ -1,2 +1,3 @@",
            '+  // eval( is discussed here, and https://example.com is cited',
        ]))
        self.assertEqual([], self.failures())

    def test_an_added_line_in_a_patched_web_asset_is_scanned(self) -> None:
        self.write("downstream/patches/0009-x.patch", "\n".join([
            "--- a/chrome/browser/resources/new_tab_page/app.ts",
            "+++ b/chrome/browser/resources/new_tab_page/app.ts",
            "@@ -1,2 +1,3 @@",
            "+    this.container.innerHTML = payload;",
        ]))
        self.assertTrue(any("innerHTML" in failure for failure in self.failures()))



class LitBindingTests(TreeTestCase):
    """Enforces: WA-2."""

    def failures(self) -> list[str]:
        found: list[str] = []
        assets.check_lit_bindings_are_declared(self.root, found)
        return found

    def test_a_binding_without_a_declaration_is_rejected(self) -> None:
        """Build #38's second failure.

        Chromium's lit-reactive-properties rule wants every property a
        template reads declared in the properties block, and
        lit-property-accessor then wants the accessor keyword. Omit the
        declaration and both fire -- one omission seen from two sides.
        """

        self.write("downstream/patches/0093-x.patch", "\n".join([
            "--- a/chrome/browser/resources/new_tab_page/app.html",
            "+++ b/chrome/browser/resources/new_tab_page/app.html",
            "@@ -1,1 +1,2 @@",
            "+  <iframe src=\"${this.sunshineBackgroundPath_}\"></iframe>",
            "--- a/chrome/browser/resources/new_tab_page/app.ts",
            "+++ b/chrome/browser/resources/new_tab_page/app.ts",
            "@@ -1,1 +1,2 @@",
            "+  protected accessor sunshineBackgroundPath_: string = 'x';",
        ]))
        failures = self.failures()
        self.assertTrue(failures, "the violation was accepted")
        self.assertTrue(any("WA-2" in failure for failure in failures), failures)

    def test_a_binding_with_its_declaration_is_accepted(self) -> None:
        self.write("downstream/patches/0094-x.patch", "\n".join([
            "--- a/chrome/browser/resources/new_tab_page/app.html",
            "+++ b/chrome/browser/resources/new_tab_page/app.html",
            "@@ -1,1 +1,2 @@",
            "+  <iframe src=\"${this.sunshineBackgroundPath_}\"></iframe>",
            "--- a/chrome/browser/resources/new_tab_page/app.ts",
            "+++ b/chrome/browser/resources/new_tab_page/app.ts",
            "@@ -1,1 +1,3 @@",
            "+      sunshineBackgroundPath_: {type: String},",
            "+  protected accessor sunshineBackgroundPath_: string = 'x';",
        ]))
        self.assertEqual([], self.failures())

    def test_an_upstream_binding_on_a_context_line_is_not_checked(self) -> None:
        """Upstream declares its own properties upstream.

        A rule that demanded the stack re-declare them would fail on every
        patch that touches a template, which is every patch that touches the
        New Tab page.
        """

        self.write("downstream/patches/0095-x.patch", "\n".join([
            "--- a/chrome/browser/resources/new_tab_page/app.html",
            "+++ b/chrome/browser/resources/new_tab_page/app.html",
            "@@ -1,2 +1,2 @@",
            " <div ?hidden=\"${this.logoEnabled_}\">",
            "+  <div id=\"sunshineWordmark\">SUNSHINE</div>",
        ]))
        self.assertEqual([], self.failures())


class GuardWiringTests(TreeTestCase):
    """Enforces: WA-1, WA-2 — through the entry point CI actually runs.

    Every other test in this file calls a check function directly, which
    proves the function works and nothing about whether it is reached. An
    adversarial reviewer deleted both calls from `check()` and all nineteen
    tests still passed: the guards were correct and disconnected, and CI would
    have reported success on a violating tree.
    """

    def test_check_reaches_the_backtick_rule(self) -> None:
        self.write("downstream/patches/0096-x.patch", "\n".join([
            "--- a/chrome/browser/resources/new_tab_page/app.html",
            "+++ b/chrome/browser/resources/new_tab_page/app.html",
            "@@ -1,1 +1,2 @@",
            "+  <!-- the `hidden` attribute -->",
        ]))
        self.assertTrue(any("WA-1" in f for f in assets.check(self.root)))

    def test_check_reaches_the_binding_rule(self) -> None:
        self.write("downstream/patches/0097-x.patch", "\n".join([
            "--- a/chrome/browser/resources/new_tab_page/app.html",
            "+++ b/chrome/browser/resources/new_tab_page/app.html",
            "@@ -1,1 +1,2 @@",
            "+  <iframe src=\"${this.sunshineUndeclared_}\"></iframe>",
        ]))
        self.assertTrue(any("WA-2" in f for f in assets.check(self.root)))

    def test_check_reaches_the_binding_rule_through_a_negated_form(self) -> None:
        """`${!this.x}` is the form this repository's own patch uses.

        The first version of WA-2 required `}` immediately after the
        identifier, so it saw one of the two bindings patch 0002 adds and
        would have let build #38's failure recur.
        """

        self.write("downstream/patches/0098-x.patch", "\n".join([
            "--- a/chrome/browser/resources/new_tab_page/app.html",
            "+++ b/chrome/browser/resources/new_tab_page/app.html",
            "@@ -1,1 +1,2 @@",
            "+  <iframe ?hidden=\"${!this.sunshineUndeclared_}\"></iframe>",
        ]))
        self.assertTrue(any("WA-2" in f for f in assets.check(self.root)))

    def test_a_method_call_is_not_a_reactive_property(self) -> None:
        """Lit's rule is about properties. A method needs no declaration, and
        demanding one would fail on correct code."""

        self.write("downstream/patches/0099-x.patch", "\n".join([
            "--- a/chrome/browser/resources/new_tab_page/app.html",
            "+++ b/chrome/browser/resources/new_tab_page/app.html",
            "@@ -1,1 +1,2 @@",
            "+  <iframe src=\"${this.computeSunshineSrc_()}\"></iframe>",
        ]))
        self.assertEqual([], [f for f in assets.check(self.root) if "WA-2" in f])


class HtmlBacktickTests(TreeTestCase):
    """Enforces: WA-1."""

    def _backtick_failures(self) -> list[str]:
        found: list[str] = []
        assets.check_no_backtick_in_html(self.root, found)
        return found

    def test_a_backtick_in_a_patched_html_file_is_rejected(self) -> None:
        """The failure that killed build #38.

        The backtick was inside an HTML comment -- punctuation quoting an
        attribute name. Chromium preprocesses the file into a TypeScript
        template literal, so the backtick ended the string and tsc reported a
        syntax error in a generated file no one had written.
        """

        self.write("downstream/patches/0090-x.patch", "\n".join([
            "--- a/chrome/browser/resources/new_tab_page/app.html",
            "+++ b/chrome/browser/resources/new_tab_page/app.html",
            "@@ -1,1 +1,2 @@",
            "+  <!-- the `hidden` attribute goes on when hidden -->",
        ]))
        failures = self._backtick_failures()
        self.assertTrue(failures, "the violation was accepted")
        self.assertTrue(any("WA-1" in failure for failure in failures), failures)

    def test_a_backtick_in_a_patched_typescript_file_is_accepted(self) -> None:
        """A `.ts` file is already TypeScript.

        Its comments are comments, and backticks in them are punctuation. A
        rule that fired here would forbid ordinary prose in the one place the
        stack writes most of it.
        """

        self.write("downstream/patches/0091-x.patch", "\n".join([
            "--- a/chrome/browser/resources/new_tab_page/app.ts",
            "+++ b/chrome/browser/resources/new_tab_page/app.ts",
            "@@ -1,1 +1,2 @@",
            "+// `ReadInstalledBackground` returns the bytes, or empty.",
        ]))
        self.assertEqual([], self._backtick_failures())

    def test_a_backtick_on_a_context_line_is_not_an_addition(self) -> None:
        """Upstream's own HTML is full of Lit template syntax.

        Those lines arrive as context in every patch that touches the file. A
        rule that read them would fail on the first hunk of the New Tab page
        and never pass again.
        """

        self.write("downstream/patches/0092-x.patch", "\n".join([
            "--- a/chrome/browser/resources/new_tab_page/app.html",
            "+++ b/chrome/browser/resources/new_tab_page/app.html",
            "@@ -1,2 +1,2 @@",
            " ${this.lazyRender_ ? html`",
            "+  <div id=\"sunshineWordmark\">SUNSHINE</div>",
        ]))
        self.assertEqual([], self._backtick_failures())


class RepositoryIsCleanTests(unittest.TestCase):
    def test_the_repository_passes_both_guards_today(self) -> None:
        self.assertEqual([], assets.check(REPOSITORY_ROOT))
        found: list[str] = []
        surfaces.check_no_scheme_registration(REPOSITORY_ROOT, found)
        self.assertEqual([], found)


if __name__ == "__main__":
    unittest.main()
