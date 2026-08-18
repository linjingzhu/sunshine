"""What `0004-sunshine-security-webui.patch` must keep being true.

The page states whether Safe Browsing is protecting this browser. A page that
says the wrong thing here is worse than no page: `docs/SECURITY_CENTER_CONTRACT.md`
SC-11 exists because a security surface that overstates protection is the one
failure it cannot afford, and `docs/decisions/0005-google-api-keys.md` records
that the honest answer in a Sunshine build today is "not protected".

None of this can be proven by running the browser -- no native build exists in
this repository. What can be proven is that the patch reads the browser instead
of asserting an answer, and that it reaches the surface the way
`docs/decisions/0003-internal-scheme.md` requires.

Enforces: SC-8, SC-11, SEC-13, SCA-13.
"""

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
PATCH = ROOT / "downstream/patches/0004-sunshine-security-webui.patch"

# The registrations ADR 0003 forbids Sunshine to add. Each is a file the
# decision names by path; touching one is how a scheme would arrive.
SCHEME_REGISTRATION_FILES = (
    "content/common/url_schemes.cc",
    "chrome/common/chrome_content_client.cc",
    "chrome/browser/profiles/profile_io_data.cc",
    "components/omnibox/browser/builtin_provider.cc",
    "chrome/browser/autocomplete/chrome_autocomplete_scheme_classifier.cc",
)


def patch_text() -> str:
    return PATCH.read_text(encoding="utf-8")


def added_lines() -> list[str]:
    return [
        line[1:]
        for line in patch_text().splitlines()
        if line.startswith("+") and not line.startswith("+++")
    ]


def targets() -> set[str]:
    return {
        line[len("+++ b/"):].strip()
        for line in patch_text().splitlines()
        if line.startswith("+++ b/")
    }


class SecurityCenterPatchTests(unittest.TestCase):
    def test_the_patch_exists(self) -> None:
        self.assertTrue(PATCH.is_file(), f"{PATCH} is missing")

    # -- SC-11: the answer is read, never asserted ------------------------

    def test_each_of_the_three_answers_is_read_from_the_browser(self) -> None:
        """Enforces: SC-11.

        Three separate questions, three separate upstream sources. The build
        flag is not the preference and neither is the API key, and answering
        one of them with another is how a page ends up claiming protection a
        build does not have.
        """

        added = "\n".join(added_lines())
        for source in (
            # Is the implementation in the binary? components/safe_browsing/BUILD.gn
            # defines this flag from `safe_browsing_mode` in buildflags.gni.
            "BUILDFLAG(SAFE_BROWSING_AVAILABLE)",
            # Is it on for this profile? The accessor that owns the
            # `safebrowsing.enabled` preference, in
            # components/safe_browsing/core/common/safe_browsing_prefs.h.
            "safe_browsing::IsSafeBrowsingEnabled",
            # Can it reach the service? google_apis/google_api_keys.h.
            "google_apis::HasAPIKeyConfigured()",
        ):
            with self.subTest(source=source):
                self.assertIn(source, added)

    def test_no_answer_is_published_as_a_constant(self) -> None:
        """Enforces: SC-11.

        `AddBoolean("safeBrowsing...", false)` would render the same page and
        be indistinguishable from the real thing on screen.
        """

        for line in added_lines():
            with self.subTest(line=line.strip()):
                self.assertNotRegex(line, r"AddBoolean\([^)]*,\s*(true|false)\s*\)")

    def test_the_protected_verdict_requires_all_three_answers(self) -> None:
        """Enforces: SC-11.

        The one verdict that claims protection must be conditioned on every
        question, not on the two that are true in a Sunshine build.
        """

        added = "\n".join(added_lines())
        self.assertIn(
            "reveal('verdictOn', compiledIn && switchedOn && keyConfigured);", added
        )
        self.assertIn("reveal('verdictAbsent', !compiledIn);", added)
        self.assertIn("reveal('verdictOff', compiledIn && !switchedOn);", added)
        self.assertIn(
            "reveal('verdictUnreachable', compiledIn && switchedOn && !keyConfigured);",
            added,
        )

    # -- SEC-13 and SCA-13: the route ------------------------------------

    def test_the_surface_adds_no_url_scheme(self) -> None:
        """Enforces: SEC-13, SCA-13.

        `docs/decisions/0003-internal-scheme.md` names the files a scheme
        registration would have to touch. The patch touches none of them, and
        the page arrives through content's config map instead.
        """

        for path in SCHEME_REGISTRATION_FILES:
            with self.subTest(upstream=path):
                self.assertNotIn(path, targets())

        added = "\n".join(added_lines())
        for registration in ("AddStandardScheme", "RegisterProtocolHandler",
                             "registerProtocolHandler", "sunshine://"):
            with self.subTest(registration=registration):
                self.assertNotIn(registration, added)

    def test_the_host_is_prefixed_and_registered_through_the_config_map(self) -> None:
        """Enforces: SCA-13.

        A bare `security` host collides with Settings' own `kSecuritySubPage`,
        which is the one collision a security page cannot afford. Registration
        goes through `content::WebUIConfigMap::AddWebUIConfig`, which CHECKs
        that the config is a chrome:// one --
        `content/public/browser/webui_config_map.h`.
        """

        added = "\n".join(added_lines())
        self.assertIn('kChromeUISunshineSecurityHost[] = "sunshine-security";', added)
        self.assertIn("map.AddWebUIConfig(std::make_unique<SunshineSecurityUIConfig>());", added)
        self.assertIn("content::DefaultWebUIConfig<SunshineSecurityUI>", added)
        self.assertIn("content::kChromeUIScheme", added)
        # And it is offered by the built-in provider, which is what
        # ADR 0003 buys in place of a scheme of Sunshine's own.
        self.assertIn("      kChromeUISunshineSecurityHost,", added)
        self.assertNotIn('ChromeWebUIControllerFactory', added)

    # -- SC-8: a privileged surface that renders nothing it was given -----

    def test_the_page_embeds_nothing_and_fetches_nothing(self) -> None:
        """Enforces: SC-8.

        `scripts/verify_web_asset_security.py` already rejects a remote URL and
        dynamic code. What it does not know is that this particular surface is
        also forbidden to frame or embed anything at all.
        """

        markup = [line for line in added_lines() if "<" in line]
        for element in ("<iframe", "<embed", "<object", "<webview"):
            with self.subTest(element=element):
                self.assertFalse(
                    [line for line in markup if element in line],
                    f"{element} appears in a privileged Sunshine surface",
                )


if __name__ == "__main__":
    unittest.main()
